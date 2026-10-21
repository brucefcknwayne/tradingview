"""
Gotham Engine – Ereignisse, Ergebnisse, Zufallsvergleich, Kalibrierung aus den Kern-Kennzahlen von engine_sim.py.
Aufruf (nach engine_sim.py): python gotham-engine/engine_eval.py
"""
import itertools
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from engine_sim import CACHE, NY, OUT, TICK, C, gen_events, load_sessions, outcome  # noqa: E402

COST_T = 2.0            # Kosten + Slippage je Round-Trip in Ticks (für die Sim-PnL)
N_RAND = 1000
rng = np.random.default_rng(7)

meta = pickle.load(open(CACHE / "sess_meta.pkl", "rb"))
days = sorted(meta)
sess_all = load_sessions()
S = {d: sess_all[d] for d in days}
del sess_all
ROWS = {W: dict(np.load(CACHE / f"rows_W{W}.npz")) for W in (20000, 10000, 5000)}
POOL = pd.read_parquet(CACHE / "random_pool.parquet")
POOL_BY_H = {h: g[["r1", "r5", "r15"]].to_numpy() for h, g in POOL.groupby("hour")}


def events(W, absMult=2.5, absTicks=2, minConc=0.35, brkMult=1.5, brkTicks=4, dup=0, do_abs=True, do_brk=True, full=True):
    out = []
    for d in days:
        R = ROWS[W][str(d)]
        E = gen_events(R, absMult, absTicks, minConc, brkMult, brkTicks, 20000.0, float(dup), do_abs, do_brk)
        t, p = S[d]["t"], S[d]["p"]
        for r, typ, di, var in E:
            x = R[int(r)]; dirn = 1 if di == 0 else -1
            T = int(x[C["T"]]); last = x[C["last"]]
            if typ == 0:
                ref = np.nan; price = x[C["wall"]]
            else:
                ref = x[C["ph"]] if dirn == 1 else x[C["pl"]]; price = last
            code, sec, r1, r5, r15, best, worst = outcome(t, p, T, float(last), dirn, int(typ), float(x[C["wall"]]), float(ref) if np.isfinite(ref) else 0.0)
            i3 = np.searchsorted(t, T + 180000, side="right") - 1
            p3 = p[i3]
            if typ == 0:
                exitp = x[C["wall"]] + dirn * 8 if code == 1 else (x[C["wall"]] - dirn * 4 if code == -1 else p3)
            else:
                exitp = last + dirn * 16 if code == 1 else (ref - dirn * 4 if code == -1 else p3)
            normal = x[C["d80"]] * x[C["act"]]
            out.append(dict(session=d, T=T, typ=int(typ), dirn=dirn, variant=int(var), price=price, last=last, ref=ref,
                            D=x[C["D"]], V=x[C["V"]], move=x[C["move"]], push=x[C["push"]], conc=x[C["conc"]], big=x[C["big"]],
                            fading=x[C["fading"]], act=x[C["act"]], normal=normal, x=abs(x[C["D"]]) / normal,
                            code=code, sec=sec, r1=r1, r5=r5, r15=r15, best=best, worst=worst,
                            pnl=dirn * (exitp - last) - COST_T))
    E = pd.DataFrame(out)
    if len(E) and full:
        et = pd.to_datetime(E["T"], unit="ms", utc=True).dt.tz_convert(NY)
        E["hour"] = et.dt.hour; E["time_ny"] = et.dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
        mins = et.dt.hour * 60 + et.dt.minute
        E["rth"] = (mins >= 570) & (mins < 960)
    return E


def score(E):
    x = E["x"]; mv = E["move"]
    s = (30 * np.clip(np.minimum(1, (x - 1) / 2 + 0.34), 0, None) + 20 * np.maximum(0, 1 - np.maximum(0, mv) / 3)
         + 15 * np.minimum(1, E["conc"] / 0.6) + 0 + 0 + 5 * E["fading"] + 5 * (E["big"] > 0))   # refill/iceberg ohne tbbo/mbo = 0
    return s.round(1)


def rand_cmp(E, col):
    """Zufall: je Ereignis ein Zeitpunkt aus derselben NY-Stunde, gleiche Richtung; 1.000 Wiederholungen."""
    if len(E) == 0:
        return np.nan, np.nan
    ci = {"r1": 0, "r5": 1, "r15": 2}[col]
    means = np.zeros(N_RAND)
    for h, g in E.groupby("hour"):
        pool = POOL_BY_H.get(h)
        if pool is None:
            continue
        idx = rng.integers(0, len(pool), size=(N_RAND, len(g)))
        means += (pool[idx, ci] * g["dirn"].to_numpy()[None, :]).sum(1)
    means /= len(E)
    sig = E[col].mean()
    return means.mean(), (means >= sig).mean()


def to_csv(E, path):
    if len(E) == 0:
        pd.DataFrame(columns=COLS).to_csv(path, index=False); return
    A = E["typ"] == 0
    df = pd.DataFrame({
        "symbol": E["session"].map(lambda d: meta[d]["symbol"]), "time_ny": E["time_ny"], "epoch_ms": E["T"],
        "type": np.where(A, "ABSORPTION", "BREAKING"), "dir": np.where(E["dirn"] == 1, "up", "down"),
        "price": E["price"] * TICK, "last_price": E["last"] * TICK, "ref_price": (E["ref"] * TICK).where(~A),
        "score": score(E).where(A), "x_normal": E["x"].round(2), "delta_20s": E["D"].astype(int), "volume_20s": E["V"].astype(int),
        "move_ticks": E["move"].astype(int), "after_push_ticks": E["push"].where(A & (E["variant"] == 1)),
        "conc": E["conc"].round(3), "refill": "", "iceberg": "", "big_orders": E["big"].astype(int),
        "fading": E["fading"].astype(int).where(A), "at_level": "", "activity": E["act"].round(2),
        "outcome": np.where(A, np.select([E["code"] == 1, E["code"] == -1], ["HELD", "FAILED"], "EXPIRED"),
                            np.select([E["code"] == 1, E["code"] == -1], ["CONTINUED", "FAILED"], "EXPIRED")),
        "outcome_sec": E["sec"].round(1), "ret_1m": E["r1"], "ret_5m": E["r5"], "ret_15m": E["r15"],
        "best_15m": E["best"], "worst_15m": E["worst"]})
    df.to_csv(path, index=False)


COLS = "symbol,time_ny,epoch_ms,type,dir,price,last_price,ref_price,score,x_normal,delta_20s,volume_20s,move_ticks,after_push_ticks,conc,refill,iceberg,big_orders,fading,at_level,activity,outcome,outcome_sec,ret_1m,ret_5m,ret_15m,best_15m,worst_15m".split(",")


def summ(E, ndays):
    if len(E) == 0:
        return {"Ereignisse/Tag": 0.0, "davon RTH/Tag": 0.0}
    r5m, r5p = rand_cmp(E, "r5"); r15m, r15p = rand_cmp(E, "r15")
    return {"Ereignisse": len(E), "Ereignisse/Tag": round(len(E) / ndays, 1), "davon RTH/Tag": round(E["rth"].sum() / ndays, 1),
            "Treffer % (HELD/CONT.)": round(100 * (E["code"] == 1).mean(), 1), "FAILED %": round(100 * (E["code"] == -1).mean(), 1),
            "EXPIRED %": round(100 * (E["code"] == 0).mean(), 1),
            "Ø ret_5m": round(E["r5"].mean(), 2), "Median ret_5m": float(E["r5"].median()), "Ø ret_15m": round(E["r15"].mean(), 2),
            "Zufall Ø ret_5m": round(r5m, 2), "Edge 5m": round(E["r5"].mean() - r5m, 2), "p 5m": round(r5p, 3),
            "Zufall Ø ret_15m": round(r15m, 2), "Edge 15m": round(E["r15"].mean() - r15m, 2), "p 15m": round(r15p, 3),
            "Sim-PnL Ticks/Ereignis": round(E["pnl"].mean(), 2), "Sim-PnL Ticks/Tag": round(E["pnl"].sum() / ndays, 1)}


if __name__ == "__main__":
    nd = len(days)
    # ── Basis = Engine v1.5.1 ──
    E = events(20000)
    to_csv(E, OUT / "events.csv")
    E.to_parquet(CACHE / "events_base.parquet", index=False)
    print("Basis:", len(E), "Ereignisse", E.groupby("typ").size().to_dict(), flush=True)
    # ── Kalibrierung ──
    sweep, keep = [], {}
    for am, at, mc in itertools.product((1.5, 2.0, 2.5, 3.0), (1, 2, 3), (0.25, 0.35, 0.45)):
        Ea = events(20000, absMult=am, absTicks=at, minConc=mc, do_brk=False)
        sweep.append(dict(Typ="ABSORPTION", Fenster_s=20, Mult=am, Ticks=at, minConc=mc, Duplikatfilter="", **summ(Ea, nd)))
        keep[("A", am, at, mc)] = Ea
        print("A", am, at, mc, len(Ea), flush=True)
    for W, bm, bt, dup in itertools.product((20000, 10000, 5000), (1.0, 1.5, 2.0), (2, 3, 4, 6), (0, 30000)):
        Eb = events(W, brkMult=bm, brkTicks=bt, dup=dup, do_abs=False)
        sweep.append(dict(Typ="BREAKING", Fenster_s=W // 1000, Mult=bm, Ticks=bt, minConc="", Duplikatfilter="ja" if dup else "nein", **summ(Eb, nd)))
        keep[("B", W, bm, bt, dup)] = Eb
        print("B", W, bm, bt, dup, len(Eb), flush=True)
    SW = pd.DataFrame(sweep); SW.to_csv(OUT / "sweep.csv", index=False)
    pickle.dump(keep, open(CACHE / "sweep_events.pkl", "wb"))
    print("fertig", flush=True)
