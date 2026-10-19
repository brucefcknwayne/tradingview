"""
H2 Zera-Reversal + Orderflow-Filter – Test exakt nach Vorab-Registrierung in research/HYPOTHESEN.md.
Nutzt Indikator, Signal-, Trade- und Zufalls-Logik aus h1_zera_reversal.py unverändert; neu sind nur die Filter F1–F3.

Aufruf: python research/h2_zera_orderflow.py   → research/results/h2_*.csv, h2_report.md
"""
import glob
import sys
from multiprocessing import Pool
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).parent))
import h1_zera_reversal as h1  # noqa: E402

RES, CACHE, DL = h1.RES, h1.CACHE, h1.DL


# ═══════════════════════════ Bars mit Delta ═══════════════════════════
def read_ticks_side(path):
    df = db.DBNStore.from_file(path).to_df()
    if df.empty:
        return None
    df = df[(df["action"] == "T") & ~df["symbol"].str.contains("-")].reset_index()
    sd = (df["ts_event"].dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)).dt.date
    df = df[(df["symbol"] == sd.map(h1.FRONT)) & (sd >= h1.START) & (sd <= h1.CUTOFF)]
    if df.empty:
        return None
    sgn = np.where(df["side"] == "B", 1, np.where(df["side"] == "A", -1, 0)).astype(np.int8)
    return df["ts_event"].astype("int64").to_numpy(), df["price"].to_numpy(float), df["size"].to_numpy(np.int64), df["symbol"].to_numpy(), sgn


def volume_bars_delta(N):
    """Wie h1.volume_bars (genau N Kontrakte, Trades über die Grenze aufgeteilt, Neustart bei Kontraktwechsel), plus Kauf/Verkauf."""
    out = CACHE / f"vbd{N}.parquet"
    if out.exists():
        return pd.read_parquet(out)
    files = sorted(glob.glob(str(DL / "data/raw/trades/glbx-mdp3-*.trades.dbn.zst")))
    files = [f for f in files if pd.Timestamp(Path(f).name[10:18]).date() <= h1.CUTOFF + pd.Timedelta(days=1)]
    rows, carry, cur_sym = [], None, None

    def close_carry():
        t, p, v, s = carry
        rows.append((t[0], p[0], p.max(), p.min(), p[-1], int(v.sum()), int(v[s == 1].sum()), int(v[s == -1].sum()), cur_sym))

    with Pool(4) as pool:
        for res in pool.imap(read_ticks_side, files, chunksize=2):
            if res is None:
                continue
            ts, px, sz, sym, sg = res
            cut = np.flatnonzero(sym[1:] != sym[:-1]) + 1
            for a, b in zip(np.r_[0, cut], np.r_[cut, len(sym)]):
                s = sym[a]
                if s != cur_sym:
                    if carry is not None and len(carry[0]):
                        close_carry()
                    carry, cur_sym = None, s
                t_, p_, z_, g_ = ts[a:b], px[a:b], sz[a:b], sg[a:b]
                if carry is not None:
                    t_, p_, z_, g_ = np.r_[carry[0], t_], np.r_[carry[1], p_], np.r_[carry[2], z_], np.r_[carry[3], g_]
                c_end = np.cumsum(z_)
                b0 = (c_end - z_) // N
                b1 = (c_end - 1) // N
                rep = (b1 - b0 + 1).astype(np.int64)
                bid = np.repeat(b0, rep) + (np.arange(rep.sum()) - np.repeat(np.cumsum(rep) - rep, rep))
                tt, pp, gg = np.repeat(t_, rep), np.repeat(p_, rep), np.repeat(g_, rep)
                lo = np.maximum(np.repeat(c_end - z_, rep), bid * N)
                hi = np.minimum(np.repeat(c_end, rep), (bid + 1) * N)
                vv = hi - lo
                last = int(c_end[-1] // N)
                full = bid < last if c_end[-1] % N else bid <= last
                if full.any():
                    d = pd.DataFrame({"b": bid[full], "t": tt[full], "p": pp[full],
                                      "buy": np.where(gg[full] == 1, vv[full], 0), "sell": np.where(gg[full] == -1, vv[full], 0)})
                    agg = d.groupby("b", sort=True).agg(ts=("t", "first"), open=("p", "first"), high=("p", "max"), low=("p", "min"),
                                                        close=("p", "last"), buy=("buy", "sum"), sell=("sell", "sum"))
                    for r in agg.itertuples(index=False):
                        rows.append((r.ts, r.open, r.high, r.low, r.close, N, int(r.buy), int(r.sell), s))
                rest = ~full
                carry = (tt[rest], pp[rest], vv[rest], gg[rest]) if rest.any() else None
    if carry is not None and len(carry[0]):
        close_carry()
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "buy_vol", "sell_vol", "symbol"])
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    df.to_parquet(out, index=False)
    return df


def minute_bars_delta():
    df = pd.concat(pd.read_parquet(f, columns=["ts_utc", "session_date", "symbol", "open", "high", "low", "close", "volume", "buy_vol", "sell_vol"])
                   for f in sorted(glob.glob(str(DL / "data/nq_of1m/*.parquet"))))
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    df = df[(df["session_date"] >= h1.START) & (df["session_date"] <= h1.CUTOFF)].sort_values("ts_utc")
    return df.rename(columns={"ts_utc": "ts"})[["ts", "open", "high", "low", "close", "volume", "buy_vol", "sell_vol", "symbol"]].reset_index(drop=True)


# ═══════════════════════════ Signale mit Serien-Infos ═══════════════════════════
@njit(cache=True)
def signals_runs(Z, h, l, seg, z1):
    """Wie h1.signals, zusätzlich Start der Serie und Index der Extrem-Kerze (erste Kerze mit dem Serien-Extrem)."""
    n = len(Z)
    o_i = []; o_d = []; o_ext = []; o_start = []; o_xi = []
    run_sign = 0; run_hi = -1e18; run_lo = 1e18; start = -1; xi = -1
    for i in range(n):
        if i > 0 and seg[i] != seg[i - 1]:
            run_sign = 0
        z = Z[i]
        if np.isnan(z):
            run_sign = 0; continue
        sg = 1 if z >= z1 else (-1 if z <= -z1 else 0)
        if sg != 0:
            if sg != run_sign:
                run_sign = sg; run_hi = -1e18; run_lo = 1e18; start = i
            if sg == 1 and h[i] > run_hi:
                xi = i
            if sg == -1 and l[i] < run_lo:
                xi = i
            run_hi = max(run_hi, h[i]); run_lo = min(run_lo, l[i])
        elif run_sign != 0:
            o_i.append(i); o_d.append(-run_sign); o_ext.append(run_hi if run_sign == 1 else run_lo)
            o_start.append(start); o_xi.append(xi)
            run_sign = 0
    return np.array(o_i), np.array(o_d), np.array(o_ext), np.array(o_start), np.array(o_xi)


def filters(si, sdir, sstart, sxi, o, h, l, c, delta, buy, sell):
    ser = -sdir                                            # Serien-Richtung: +1 nach +Z
    f1 = np.sign(delta[si]) == -ser                        # Delta der Signal-Kerze gegen die Serie
    agg = buy[sxi] + sell[sxi]
    share = np.where(agg > 0, np.where(ser == 1, buy[sxi], sell[sxi]) / np.maximum(agg, 1), 0.0)
    mid = (h[sxi] + l[sxi]) / 2
    f2 = (share >= 0.60) & np.where(ser == 1, c[sxi] <= mid, c[sxi] >= mid)
    f3 = np.zeros(len(si), bool)
    for j in range(len(si)):
        a, x = sstart[j], sxi[j]
        if x > a:                                          # Serie ≥ 2 Kerzen, Extrem nicht die erste
            prev = delta[a:x]
            f3[j] = delta[x] < prev.max() if ser[j] == 1 else delta[x] > prev.min()
    return {"F1 Delta dreht": f1, "F2 Absorption": f2, "F3 Delta-Divergenz": f3}


def analyse(name, bars):
    o, h, l, c = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    buy, sell = bars["buy_vol"].to_numpy(float), bars["sell_vol"].to_numpy(float)
    delta = buy - sell
    sym = bars["symbol"].to_numpy()
    seg = np.r_[0, np.cumsum(sym[1:] != sym[:-1])].astype(np.int64)
    src = (o + h + l + c) / 4
    Z, M, S = h1.zscore(src, seg, h1.LOOK)
    si, sdir, sext, sstart, sxi = signals_runs(Z, h, l, seg, h1.Z1)
    F = filters(si, sdir, sstart, sxi, o, h, l, c, delta, buy, sell)
    et = bars["ts"].dt.tz_convert("America/New_York")
    hour = et.dt.hour.to_numpy()
    day = pd.factorize((et + pd.Timedelta(hours=6)).dt.date)[0].astype(np.int64)
    order = np.argsort(hour, kind="stable"); cand = order.astype(np.int64)
    cand_ptr = np.searchsorted(hour[order], np.arange(25)).astype(np.int64)
    rows, desc = [], []
    for vi, vname in ((0, "A: 20 Pkt"), (1, "B: Serien-Extrem")):
        base, _ = h1.run_trades(o, h, l, c, seg, M, si, sdir, sext, vi)
        base_ev = np.nanmean(base[:, 0])
        for fname, fm in F.items():
            res, skipped = h1.run_trades(o, h, l, c, seg, M, si[fm], sdir[fm], sext[fm], vi)
            ok = ~np.isnan(res[:, 0])
            pnl, e = res[ok, 0], res[ok, 7].astype(np.int64)
            R = h1.random_pnl(o, h, l, c, seg, cand, cand_ptr, hour[e].astype(np.int64), day, e, sdir[fm][ok].astype(np.int64),
                              res[ok, 5], res[ok, 6], h1.NREP, 11 + vi)
            st = h1.stats(pnl, R, res[ok, 2], res[ok, 3], res[ok, 4])
            rows.append({"Chart": name, "Stop": vname, "Filter": fname, "Signale mit Filter": int(fm.sum()),
                         "Anteil Signale %": round(100 * fm.mean(), 1), **st, "EW ungefiltert (H1)": round(base_ev, 2)})
            print(name, vname, fname, "Trades", ok.sum(), "EW", st.get("EW netto"), "p", round(st.get("p roh", np.nan), 4), flush=True)
    return rows, len(bars), len(si)


if __name__ == "__main__":
    RES.mkdir(parents=True, exist_ok=True)
    charts = [("1m", minute_bars_delta()), ("Vol 500", volume_bars_delta(500)), ("Vol 1000", volume_bars_delta(1000))]
    allrows, info = [], []
    for name, bars in charts:
        print(name, "Kerzen", len(bars), flush=True)
        r, nb, ns = analyse(name, bars)
        allrows += r; info.append((name, nb, ns))
    X = pd.DataFrame(allrows)
    X["p Holm"] = h1.holm(X["p roh"].to_numpy())
    X["p roh"] = X["p roh"].round(4); X["p Holm"] = X["p Holm"].round(4)
    X["Edge (Kriterium)"] = np.where((X["p Holm"] < 0.05) & (X["KI95 unten"] > 0) & (X["Trades"] >= 30), "JA", "nein")
    X.to_csv(RES / "h2_groups.csv", index=False)
    md = ["# H2 Zera-Reversal + Orderflow-Filter – Ergebnisse", "",
          f"Zeitraum 2022-09-19 bis 2026-04-16 (Holdout ab 2026-04-17 nicht angefasst). {len(X)} Tests, Holm-Bonferroni über alle.", "",
          "| Chart | Kerzen | Signale ungefiltert |", "|---|---|---|"] + [f"| {a} | {b:,} | {c:,} |" for a, b, c in info] + ["",
          X.to_markdown(index=False)]
    (RES / "h2_report.md").write_text("\n".join(md))
    print(X[["Chart", "Stop", "Filter", "Trades", "Treffer %", "EW netto", "KI95 unten", "KI95 oben", "Zufall EW", "EW ungefiltert (H1)", "p roh", "p Holm", "Edge (Kriterium)"]].to_string())
