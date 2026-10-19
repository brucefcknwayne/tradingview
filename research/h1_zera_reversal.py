"""
H1 Zera-Reversal – Test exakt nach Vorab-Registrierung in research/HYPOTHESEN.md (keine Parameter ändern).

Chart-Typen: 1m-Zeitkerzen, 500er und 1000er Volume-Bars (aus NQ-Tickdaten), Zeitraum 2022-09-19 bis 2026-04-16.
Holdout (Handelstage ab 2026-04-17) wird beim Laden abgeschnitten.

Aufruf: python research/h1_zera_reversal.py   → research/results/h1_*.csv, h1_report.md
"""
import glob
import sys
from multiprocessing import Pool
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd
from numba import njit

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "data-lab"
RES = ROOT / "research/results"
CACHE = DL / "data/raw/zera_cache"
START, CUTOFF = pd.Timestamp("2022-09-19").date(), pd.Timestamp("2026-04-16").date()   # Holdout ab 2026-04-17
LOOK, Z1, Z2 = 50, 2.0, 3.0
STOP_A, COST, TIMEOUT, RR6, TICK = 20.0, 1.0, 50, 120.0, 0.25
NREP = 1000
rng = np.random.default_rng(20261019)


# ═══════════════════════════ Bars ═══════════════════════════
def front_map():
    nq = pd.concat(pd.read_parquet(f, columns=["session_date", "symbol"]) for f in sorted(glob.glob(str(DL / "data/nq_1m/*.parquet"))))
    nq["session_date"] = pd.to_datetime(nq["session_date"]).dt.date
    return nq.groupby("session_date")["symbol"].agg(lambda s: s.mode().iat[0]).to_dict()


FRONT = front_map()


def read_ticks(path):
    df = db.DBNStore.from_file(path).to_df()
    if df.empty:
        return None
    df = df[(df["action"] == "T") & ~df["symbol"].str.contains("-")].reset_index()
    sd = (df["ts_event"].dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)).dt.date
    df = df[(df["symbol"] == sd.map(FRONT)) & (sd >= START) & (sd <= CUTOFF)]
    if df.empty:
        return None
    return df["ts_event"].astype("int64").to_numpy(), df["price"].to_numpy(float), df["size"].to_numpy(np.int64), df["symbol"].to_numpy()


def volume_bars(N):
    """Volume-Bars mit genau N Kontrakten; Trades über die Grenze werden aufgeteilt; Neustart bei Kontraktwechsel."""
    out = CACHE / f"vb{N}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    files = sorted(glob.glob(str(DL / "data/raw/trades/glbx-mdp3-*.trades.dbn.zst")))
    files = [f for f in files if pd.Timestamp(Path(f).name[10:18]).date() <= CUTOFF + pd.Timedelta(days=1)]
    rows = []
    carry = None                                         # angefangene Kerze: (ts, price, size, sym) der bisherigen Trades
    cum0 = 0                                             # Volumen der angefangenen Kerze
    cur_sym = None
    with Pool(4) as pool:
        for res in pool.imap(read_ticks, files, chunksize=2):
            if res is None:
                continue
            ts, px, sz, sym = res
            # nach Kontrakt aufteilen (in Reihenfolge)
            cut = np.flatnonzero(sym[1:] != sym[:-1]) + 1
            for a, b in zip(np.r_[0, cut], np.r_[cut, len(sym)]):
                s = sym[a]
                if s != cur_sym:                         # Kontraktwechsel: angefangene Kerze abschließen
                    if carry is not None and len(carry[0]):
                        rows.append((carry[0][0], carry[1][0], carry[1].max(), carry[1].min(), carry[1][-1], int(carry[2].sum()), cur_sym))
                    carry, cum0, cur_sym = None, 0, s
                t_, p_, z_ = ts[a:b], px[a:b], sz[a:b]
                if carry is not None:
                    t_, p_ = np.r_[carry[0], t_], np.r_[carry[1], p_]
                    z_ = np.r_[carry[2], z_]
                c_end = np.cumsum(z_)
                b0 = (c_end - z_) // N                   # Kerze, in der der Trade beginnt
                b1 = (c_end - 1) // N                    # Kerze, in der er endet
                rep = (b1 - b0 + 1).astype(np.int64)
                bid = np.repeat(b0, rep) + (np.arange(rep.sum()) - np.repeat(np.cumsum(rep) - rep, rep))
                tt, pp = np.repeat(t_, rep), np.repeat(p_, rep)
                # Volumenanteil je (Trade, Kerze)
                lo = np.maximum(np.repeat(c_end - z_, rep), bid * N)
                hi = np.minimum(np.repeat(c_end, rep), (bid + 1) * N)
                vv = hi - lo
                last = int(c_end[-1] // N)               # Kerze, die evtl. unvollständig ist
                full = bid < last if c_end[-1] % N else bid <= last
                if full.any():
                    g = pd.DataFrame({"b": bid[full], "t": tt[full], "p": pp[full]}).groupby("b", sort=True)
                    agg = g.agg(ts=("t", "first"), open=("p", "first"), high=("p", "max"), low=("p", "min"), close=("p", "last"))
                    for r in agg.itertuples(index=False):
                        rows.append((r.ts, r.open, r.high, r.low, r.close, N, s))
                rest = ~full
                carry = (tt[rest], pp[rest], vv[rest]) if rest.any() else None
    if carry is not None and len(carry[0]):
        rows.append((carry[0][0], carry[1][0], carry[1].max(), carry[1].min(), carry[1][-1], int(carry[2].sum()), cur_sym))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "symbol"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    return df


def minute_bars():
    df = pd.concat(pd.read_parquet(f, columns=["ts_utc", "session_date", "symbol", "open", "high", "low", "close", "volume"])
                   for f in sorted(glob.glob(str(DL / "data/nq_of1m/*.parquet"))))
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    df = df[(df["session_date"] >= START) & (df["session_date"] <= CUTOFF)].sort_values("ts_utc")
    return df.rename(columns={"ts_utc": "ts"})[["ts", "open", "high", "low", "close", "volume", "symbol"]].reset_index(drop=True)


# ═══════════════════════════ Indikator + Trades (numba) ═══════════════════════════
@njit(cache=True)
def zscore(src, seg, look):
    n = len(src); Z = np.full(n, np.nan); M = np.full(n, np.nan); S = np.full(n, np.nan)
    start = 0
    for i in range(n):
        if i > 0 and seg[i] != seg[i - 1]:
            start = i
        if i - start + 1 >= look:
            w = src[i - look + 1:i + 1]
            m = w.mean(); sd = np.sqrt(((w - m) ** 2).mean())
            M[i] = m; S[i] = sd
            if sd > 0:
                Z[i] = (src[i] - m) / sd
    return Z, M, S


@njit(cache=True)
def sim(o, h, l, c, seg, e, d, stop_dist, tgt_dist, timeout, cost, rr):
    """Ein Trade ab Einstiegskerze e (Open), Richtung d (+1 long/−1 short). Rückgabe: pnl, exit-Index, mfe, mae, rr6."""
    n = len(o); entry = o[e]
    sp = entry - d * stop_dist; tp = entry + d * tgt_dist
    mfe = 0.0; mae = 0.0; pnl = np.nan; ex = -1
    last = min(e + timeout - 1, n - 1)
    for k in range(e, last + 1):
        if seg[k] != seg[e]:
            pnl = d * (c[k - 1] - entry); ex = k - 1; break
        fav = (h[k] - entry) if d == 1 else (entry - l[k])
        adv = (entry - l[k]) if d == 1 else (h[k] - entry)
        hit_s = adv >= stop_dist
        hit_t = fav >= tgt_dist
        if hit_s:
            mae = max(mae, stop_dist); pnl = -stop_dist; ex = k; break
        mfe = max(mfe, fav); mae = max(mae, adv)
        if hit_t:
            pnl = tgt_dist; ex = k; break
        if k == last:
            pnl = d * (c[k] - entry); ex = k
    # 6RR: +rr vor −20 innerhalb timeout (gleiche Kerze → −20 zuerst)
    r6 = 0
    for k in range(e, last + 1):
        if seg[k] != seg[e]:
            break
        fav = (h[k] - entry) if d == 1 else (entry - l[k])
        adv = (entry - l[k]) if d == 1 else (h[k] - entry)
        if adv >= 20.0:
            break
        if fav >= rr:
            r6 = 1; break
    return pnl - cost, ex, mfe, mae, r6


@njit(cache=True)
def signals(Z, src, M, S, h, l, seg, z1, z2):
    """Signal-Kerzen: erste |Z|<z1 nach Serie gleichen Vorzeichens mit |Z|≥z1."""
    n = len(Z)
    out_i = []; out_dir = []; out_mag = []; out_ext = []; out_price = []
    run_sign = 0; run_mag = False; run_hi = -1e18; run_lo = 1e18; last_col = -1
    for i in range(n):
        if i > 0 and seg[i] != seg[i - 1]:
            run_sign = 0
        z = Z[i]
        if np.isnan(z):
            run_sign = 0; continue
        sg = 1 if z >= z1 else (-1 if z <= -z1 else 0)
        if sg != 0:
            if sg != run_sign:
                run_sign = sg; run_mag = False; run_hi = -1e18; run_lo = 1e18
            run_mag = run_mag or abs(z) >= z2
            run_hi = max(run_hi, h[i]); run_lo = min(run_lo, l[i]); last_col = i
        elif run_sign != 0:
            j = last_col
            dz = Z[i] - Z[j]
            price = (src[i] - src[j]) / S[j]
            share = price / dz if dz != 0 else 0.0
            out_i.append(i); out_dir.append(-run_sign); out_mag.append(1 if run_mag else 0)
            out_ext.append(run_hi if run_sign == 1 else run_lo); out_price.append(1 if share > 0.5 else 0)
            run_sign = 0
    return np.array(out_i), np.array(out_dir), np.array(out_mag), np.array(out_ext), np.array(out_price)


@njit(cache=True)
def run_trades(o, h, l, c, seg, M, sig_i, sig_d, sig_ext, variant):
    n = len(o); k = len(sig_i)
    res = np.full((k, 8), np.nan)       # pnl, exit, mfe, mae, r6, stop, tgt, entry_idx
    busy_until = -1; skipped = 0
    for j in range(k):
        i = sig_i[j]; e = i + 1
        if e >= n or seg[e] != seg[i] or i <= busy_until:
            continue
        d = sig_d[j]; entry = o[e]
        tgt = d * (M[i] - entry)
        if tgt <= 0:
            skipped += 1; continue
        if variant == 0:
            sd = STOP_A
        else:
            sd = d * (entry - (sig_ext[j] - d * TICK)) if d == 1 else (sig_ext[j] + TICK) - entry
            if sd <= 0:
                skipped += 1; continue
        pnl, ex, mfe, mae, r6 = sim(o, h, l, c, seg, e, d, sd, tgt, TIMEOUT, COST, RR6)
        res[j, 0] = pnl; res[j, 1] = ex; res[j, 2] = mfe; res[j, 3] = mae; res[j, 4] = r6
        res[j, 5] = sd; res[j, 6] = tgt; res[j, 7] = e
        busy_until = ex
    return res, skipped


@njit(cache=True)
def random_pnl(o, h, l, c, seg, cand, cand_ptr, hour_of_e, day, ent, d, sd, tg, nrep, seed):
    np.random.seed(seed)
    k = len(ent); out = np.empty((k, nrep))
    for j in range(k):
        hh = hour_of_e[j]; a = cand_ptr[hh]; b = cand_ptr[hh + 1]
        for r in range(nrep):
            while True:
                x = cand[a + np.random.randint(b - a)]
                if day[x] != day[ent[j]]:
                    break
            pnl, ex, mfe, mae, r6 = sim(o, h, l, c, seg, x, d[j], sd[j], tg[j], TIMEOUT, COST, RR6)
            out[j, r] = pnl
    return out


# ═══════════════════════════ Auswertung ═══════════════════════════
def stats(p, rnd, mfe, mae, r6):
    n = len(p)
    if n == 0:
        return {}
    w, ls = p[p > 0], p[p <= 0]
    eq = np.cumsum(p); dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    boot = rng.choice(p, (2000, n)).mean(1)
    rmean = rnd.mean(0)
    return {"Trades": n, "Treffer %": round(100 * (p > 0).mean(), 1), "Ø Gewinn": round(w.mean(), 2) if len(w) else np.nan,
            "Ø Verlust": round(ls.mean(), 2) if len(ls) else np.nan, "EW netto": round(p.mean(), 2),
            "KI95 unten": round(np.percentile(boot, 2.5), 2), "KI95 oben": round(np.percentile(boot, 97.5), 2),
            "PF": round(w.sum() / -ls.sum(), 2) if ls.sum() < 0 else np.nan, "Max DD": round(dd, 1),
            "Zufall EW": round(rmean.mean(), 2), "p roh": (1 + (rmean >= p.mean()).sum()) / (NREP + 1),
            "Ø MFE": round(mfe.mean(), 1), "Ø MAE": round(mae.mean(), 1), "6RR %": round(100 * r6.mean(), 1),
            "Hinweis": "zu wenig Daten" if n < 30 else ""}


def analyse(name, bars):
    o, h, l, c = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    seg = np.r_[0, np.cumsum(bars["symbol"].to_numpy()[1:] != bars["symbol"].to_numpy()[:-1])].astype(np.int64)
    src = (o + h + l + c) / 4
    Z, M, S = zscore(src, seg, LOOK)
    si, sdir, smag, sext, sprice = signals(Z, src, M, S, h, l, seg, Z1, Z2)
    et = bars["ts"].dt.tz_convert("America/New_York")
    hour = et.dt.hour.to_numpy()
    tmin = (et.dt.hour * 60 + et.dt.minute).to_numpy()
    rth = (tmin >= 570) & (tmin < 960)
    day = pd.factorize((et + pd.Timedelta(hours=6)).dt.date)[0].astype(np.int64)
    order = np.argsort(hour, kind="stable"); cand = order.astype(np.int64)
    cand_ptr = np.searchsorted(hour[order], np.arange(25)).astype(np.int64)
    rows, tr_all = [], []
    for vi, vname in ((0, "A: 20 Pkt"), (1, "B: Serien-Extrem")):
        res, skipped = run_trades(o, h, l, c, seg, M, si, sdir, sext, vi)
        ok = ~np.isnan(res[:, 0])
        T = pd.DataFrame({"sig": si[ok], "dir": sdir[ok], "magenta": smag[ok].astype(bool), "preis": sprice[ok].astype(bool),
                          "pnl": res[ok, 0], "mfe": res[ok, 2], "mae": res[ok, 3], "r6": res[ok, 4],
                          "stop": res[ok, 5], "ziel": res[ok, 6], "e": res[ok, 7].astype(np.int64)})
        T["rth"] = rth[T["sig"]]
        T["zeit"] = bars["ts"].to_numpy()[T["sig"]]
        R = random_pnl(o, h, l, c, seg, cand, cand_ptr, hour[T["e"]].astype(np.int64), day, T["e"].to_numpy(np.int64),
                       T["dir"].to_numpy(np.int64), T["stop"].to_numpy(float), T["ziel"].to_numpy(float), NREP, 7 + vi)
        groups = {"Gesamt": np.ones(len(T), bool), "Magenta": T["magenta"].to_numpy(), "nur Cyan": ~T["magenta"].to_numpy(),
                  "Long": (T["dir"] == 1).to_numpy(), "Short": (T["dir"] == -1).to_numpy(), "RTH": T["rth"].to_numpy(),
                  "Overnight": ~T["rth"].to_numpy(), "preisgetrieben": T["preis"].to_numpy(), "nicht preisgetrieben": ~T["preis"].to_numpy()}
        for gname, m in groups.items():
            st = stats(T["pnl"].to_numpy()[m], R[m], T["mfe"].to_numpy()[m], T["mae"].to_numpy()[m], T["r6"].to_numpy()[m])
            rows.append({"Chart": name, "Stop": vname, "Gruppe": gname, **st})
        T["Chart"] = name; T["Stop"] = vname
        tr_all.append(T)
        print(name, vname, "Signale", len(si), "Trades", len(T), "übersprungen (Einstieg hinter Ziel/Stop)", skipped, flush=True)
    return rows, pd.concat(tr_all), len(bars), len(si)


def holm(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); adj = np.empty(m); run = 0.0
    for r, i in enumerate(o):
        run = max(run, (m - r) * p[i]); adj[i] = min(run, 1.0)
    return adj


if __name__ == "__main__":
    RES.mkdir(parents=True, exist_ok=True)
    charts = [("1m", minute_bars()), ("Vol 500", volume_bars(500)), ("Vol 1000", volume_bars(1000))]
    allrows, trades, info = [], [], []
    for name, bars in charts:
        print(name, "Kerzen", len(bars), bars["ts"].min(), "→", bars["ts"].max(), flush=True)
        r, t, nb, ns = analyse(name, bars)
        allrows += r; trades.append(t); info.append((name, nb, ns))
    X = pd.DataFrame(allrows)
    X["p Holm"] = holm(X["p roh"].to_numpy())
    X["p roh"] = X["p roh"].round(4); X["p Holm"] = X["p Holm"].round(4)
    X["Edge (Kriterium)"] = np.where((X["p Holm"] < 0.05) & (X["KI95 unten"] > 0) & (X["Trades"] >= 30), "JA", "nein")
    X.to_csv(RES / "h1_groups.csv", index=False)
    pd.concat(trades).to_csv(RES / "h1_trades.csv.gz", index=False)
    md = ["# H1 Zera-Reversal – Ergebnisse", "",
          f"Zeitraum 2022-09-19 bis 2026-04-16 (Holdout ab 2026-04-17 nicht angefasst). {len(X)} Tests, Holm-Bonferroni über alle.", "",
          "| Chart | Kerzen | Signale |", "|---|---|---|"] + [f"| {a} | {b:,} | {c:,} |" for a, b, c in info] + ["",
          X.to_markdown(index=False)]
    (RES / "h1_report.md").write_text("\n".join(md))
    print(X[["Chart", "Stop", "Gruppe", "Trades", "Treffer %", "EW netto", "KI95 unten", "KI95 oben", "PF", "Zufall EW", "p roh", "p Holm", "6RR %", "Edge (Kriterium)"]].to_string())
