"""
Gotham Zones: Edge-Suche mit Bedingungen.

Events = erster Touch je Zone/Tag/Modus (9D, 30D; 1D nur als Zusatz-Check, da erst ab 2022).
Je Event 5 Trade-Varianten (Z = Zonenhöhe, Risiko immer 1.5 Z):
  Fade 1:1, Fade 1:2, Fade Zeit-Exit 60 Min, Breakout 1:1, Breakout 1:2
Bedingungen: Seite x Levelgruppe x Merkmal (Uhrzeit, Anlauf, Vola, Termstruktur, Wochentag,
Konfluenz mit anderem Modus, PDH/PDL/Vortages-Close in der Nähe, Gegenseite schon berührt).
Bestanden: t Train >= 2.5, t Test >= 2.0, Ø R Test > 0. Kosten 1 Pkt.

Aufruf: python data-lab/zones_edge_search.py
"""
import glob
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/zones_edge_search.md"
ZONE_PCT = 0.05
LEVELS = [2.0, 1.5, 1.0, 0.5, -0.5, -1.0, -1.5, -2.0]
MODES = ["1D", "9D", "30D"]
COST, TICK = 1.0, 0.25
RISK = 1.5
SPLIT = pd.Timestamp("2021-01-01")
T_TRAIN, T_TEST = 2.5, 2.0


def load_iv(name):
    df = pd.read_csv(HERE / f"data/iv/{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    df["DATE"] = pd.to_datetime(df["DATE"]).astype("datetime64[ns]")
    return df.set_index("DATE")["CLOSE"].astype(float).rename(name)


iv = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX9D", "VIX1D"]], axis=1, sort=True)
scale = iv["VXN"] / iv["VIX"]
iv_mode = pd.DataFrame({"1D": iv["VIX1D"] * scale, "9D": iv["VIX9D"] * scale, "30D": iv["VXN"],
                        "VXN": iv["VXN"], "TERM": iv["VIX9D"] / iv["VIX"]})

nq = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / "data/nq_1m/*.parquet"))))
nq = nq.sort_values("ts_utc").reset_index(drop=True)
sess = nq.groupby("session_date", sort=True).indices
anchors = nq.groupby("session_date")["ts_et"].first()
anchor_day = pd.to_datetime(anchors.dt.tz_localize(None).dt.date).astype("datetime64[ns]")
iv_at = pd.merge_asof(
    pd.DataFrame({"anchor_day": anchor_day.values, "session_date": anchors.index}).sort_values("anchor_day"),
    iv_mode.reset_index().rename(columns={"DATE": "iv_day"}).dropna(subset=["30D"]),
    left_on="anchor_day", right_on="iv_day", direction="backward",
).set_index("session_date")
iv_at.loc[(iv_at["anchor_day"] - iv_at["iv_day"]).dt.days > 5, MODES + ["VXN", "TERM"]] = np.nan

H, L, O, C = (nq[c].to_numpy() for c in ["high", "low", "open", "close"])
MIN = (nq["ts_et"].dt.hour * 60 + nq["ts_et"].dt.minute).to_numpy()
RTH = nq["rth"].to_numpy()
ADJ = nq["adj"].to_numpy()

# Vortageslevels (RTH), auf heutigen Kontrakt umgerechnet
dd = nq[nq["rth"]].groupby("session_date").agg(hi=("high", "max"), lo=("low", "min"), cl=("close", "last"), adj=("adj", "first"))
prevlv = pd.DataFrame({k: (dd[k] + dd["adj"]).shift(1) for k in ["hi", "lo", "cl"]})


def first(mask):
    i = np.argmax(mask) if len(mask) else 0
    return i if len(mask) and mask[i] else 10**9


def sim(adv, fav, last_pnl, risk, tp, horizon=None, horizon_pnl=None):
    if horizon is not None:
        adv, fav = adv[:horizon + 1], fav[:horizon + 1]
    s, t = first(adv >= risk), first(fav >= tp)
    if s == t == 10**9:
        return (horizon_pnl if horizon is not None else last_pnl) - COST
    return (-risk if s <= t else tp) - COST


def bucket_time(m):
    if m >= 18 * 60 or m < 3 * 60:
        return "Nacht 18-03"
    if m < 9 * 60 + 30:
        return "London 03-09:30"
    if m < 11 * 60:
        return "RTH früh 09:30-11"
    if m < 14 * 60:
        return "RTH Mitte 11-14"
    return "RTH spät 14-17"


rows = []
for sd, idx in sess.items():
    if len(idx) < 300:
        continue
    a, b = idx[0], idx[-1] + 1
    h, l, c, ref = H[a:b], L[a:b], C[a:b], O[a]
    adj = ADJ[a]
    pv = prevlv.loc[sd] - adj if sd in prevlv.index else pd.Series({"hi": np.nan, "lo": np.nan, "cl": np.nan})
    ivr = iv_at.loc[sd] if sd in iv_at.index else None
    if ivr is None:
        continue
    sigs = {m: ref * ivr[m] / 100 / np.sqrt(252) for m in MODES if np.isfinite(ivr[m]) and ivr[m] > 0}
    all_lv = {m: [ref + k * s for k in LEVELS] for m, s in sigs.items()}
    hi_run, lo_run = np.maximum.accumulate(h), np.minimum.accumulate(l)
    for mode, sig in sigs.items():
        hh = sig * ZONE_PCT
        Z = 2 * hh
        for k in LEVELS:
            lvl = ref + k * sig
            up = k > 0
            start, far = (lvl - hh, lvl + hh) if up else (lvl + hh, lvl - hh)
            reach = h >= start if up else l <= start
            if not reach.any():
                continue
            t0 = int(np.argmax(reach))
            p30 = c[max(t0 - 30, 0)]
            opp = ref - k * sig
            opp_start = opp + hh if up else opp - hh
            ev = dict(
                session_date=sd, mode=mode, k=k, side="oben" if up else "unten",
                grp={0.5: "±0.5σ", 1.0: "±1σ"}.get(abs(k), "±1.5/2σ"),
                zeit=bucket_time(MIN[a + t0]),
                anlauf="schnell" if abs(start - p30) > 0.3 * sig else ("mittel" if abs(start - p30) > 0.15 * sig else "langsam"),
                vxn=ivr["VXN"], term=ivr["TERM"],
                montag=pd.Timestamp(sd).weekday() == 0,
                konfluenz=any(abs(x - lvl) <= Z for m2, lv in all_lv.items() if m2 != mode for x in lv),
                pd_level=bool(np.nanmin(np.abs(np.array([pv["hi"], pv["lo"], pv["cl"]]) - lvl)) <= Z) if np.isfinite(pv["hi"]) else False,
                gegenseite=bool((lo_run[t0] <= opp_start) if up else (hi_run[t0] >= opp_start)),
            )
            risk = RISK * Z
            # Fade
            e, sgn = start, (-1 if up else 1)
            adv = (h[t0:] - e) if up else (e - l[t0:])
            fav = np.r_[-np.inf, (e - l[t0 + 1:]) if up else (h[t0 + 1:] - e)]
            last = sgn * (c[-1] - e)
            hz = min(60, len(c) - 1 - t0)
            hp = sgn * (c[t0 + hz] - e)
            ev["Fade 1:1"] = sim(adv, fav, last, risk, risk) / risk
            ev["Fade 1:2"] = sim(adv, fav, last, risk, 2 * risk) / risk
            ev["Fade 60 Min"] = sim(adv, fav, last, risk, 10**9, hz, hp) / risk
            # Breakout
            brk = h[t0:] > far + TICK if up else l[t0:] < far - TICK
            if brk.any():
                tb = t0 + int(np.argmax(brk))
                e, sgn = (far + TICK, 1) if up else (far - TICK, -1)
                adv = (e - l[tb:]) if up else (h[tb:] - e)
                fav = np.r_[-np.inf, (h[tb + 1:] - e) if up else (e - l[tb + 1:])]
                last = sgn * (c[-1] - e)
                ev["Breakout 1:1"] = sim(adv, fav, last, risk, risk) / risk
                ev["Breakout 1:2"] = sim(adv, fav, last, risk, 2 * risk) / risk
            rows.append(ev)

E = pd.DataFrame(rows)
E["train"] = pd.to_datetime(E["session_date"]) < SPLIT
q = E[E["train"]]["vxn"].quantile([1 / 3, 2 / 3]).to_numpy()
E["vola"] = np.where(E["vxn"] <= q[0], "VXN niedrig", np.where(E["vxn"] >= q[1], "VXN hoch", "VXN mittel"))
E["termstruktur"] = np.where(E["term"] > 1.0, "invertiert (VIX9D>VIX)", np.where(E["term"] < 0.9, "steil (<0.9)", "normal"))
E.to_parquet(HERE / "results/zones_events.parquet", index=False)

TRADES = ["Fade 1:1", "Fade 1:2", "Fade 60 Min", "Breakout 1:1", "Breakout 1:2"]
FEATS = {
    "alle": None, "zeit": None, "anlauf": None, "vola": None, "termstruktur": None,
    "montag": None, "konfluenz": None, "pd_level": None, "gegenseite": None,
}


def tstat(x):
    x = x.dropna()
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x)) if len(x) > 20 and x.std() > 0 else np.nan


disc = E[E["mode"] != "1D"]
res = []
for side, grp in product(["beide", "oben", "unten"], ["alle", "±0.5σ", "±1σ", "±1.5/2σ"]):
    g0 = disc if side == "beide" else disc[disc["side"] == side]
    g0 = g0 if grp == "alle" else g0[g0["grp"] == grp]
    for feat in FEATS:
        values = [None] if feat == "alle" else g0[feat].dropna().unique()
        for v in values:
            g = g0 if v is None else g0[g0[feat] == v]
            for tr_name in TRADES:
                a, b = g[g["train"]][tr_name].dropna(), g[~g["train"]][tr_name].dropna()
                if len(a) < 100 or len(b) < 50:
                    continue
                res.append(dict(Seite=side, Level=grp, Bedingung="alle" if v is None else f"{feat}={v}",
                                Trade=tr_name, n_train=len(a), R_train=a.mean(), t_train=tstat(a),
                                n_test=len(b), R_test=b.mean(), t_test=tstat(b),
                                hit_test=100 * (b > 0).mean()))
R = pd.DataFrame(res)
R["bestanden"] = (R["t_train"] >= T_TRAIN) & (R["t_test"] >= T_TEST) & (R["R_test"] > 0)
R["knapp"] = ~R["bestanden"] & (R["t_train"] >= 2.0) & (R["t_test"] >= 1.5) & (R["R_test"] > 0)
R = R.sort_values(["bestanden", "knapp", "t_test"], ascending=False)

fmt = R.round({"R_train": 3, "t_train": 2, "R_test": 3, "t_test": 2, "hit_test": 1})
md = ["# Gotham Zones – Edge-Suche mit Bedingungen", "",
      f"{len(R)} Tests. Bestanden: {int(R['bestanden'].sum())}, knapp: {int(R['knapp'].sum())}. "
      "R = Gewinn in Vielfachen des Risikos (1.5 Zonenhöhen), nach 1 Pkt Kosten.", "",
      fmt.head(60).to_markdown(index=False), ""]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
R.to_csv(HERE / "results/zones_edge_search.csv", index=False)
print(md[2])
print(fmt.head(25).to_string(index=False))
