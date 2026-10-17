"""
Intraday-Scan über mehrere Märkte (NQ, ES, RTY, GC), nur RTH, flat zum RTH-Ende.

Strategien
- NOISE-HIST: Noise-Area-Momentum (Zarattini/Aziz/Barbon 2024). Grenzen um max/min(Open, Vortages-Close)
  ± Ø |Bewegung seit Open| der letzten 14 Tage zur gleichen Minute. An Checkpoints (alle 30/15 Min):
  über oberer Grenze long, unter unterer short. Exit an Checkpoints, wenn Preis unter max(Grenze, VWAP)
  (Short spiegelbildlich), sonst zum RTH-Ende.
- NOISE-IV: wie oben, Grenzen = m * σ_IV * sqrt(Minuten seit Open / RTH-Minuten) (σ_IV aus VXN/VIX/RVX/GVZ).
- ORB5-Richtung: Richtung der ersten 5-Min-Kerze, Einstieg 5 Min nach Open, Stop am Extrem der Kerze, Exit RTH-Ende.
- ORB15/30: Stop-Entry am Ausbruch der Opening Range, Stop andere Seite, Exit RTH-Ende.
- REVERSAL: 5-Min-Bewegung > 3 Std-Abw. (rollend 60 Min) -> Gegenrichtung 15 Min, max. 1 offen.

Kosten je Round-Trip in Punkten (2 Ticks Slippage + Gebühr E-Mini). Train < 2021, Test >= 2021.

Aufruf: python data-lab/intraday_scan.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/intraday_scan.md"
SPLIT = pd.Timestamp("2021-01-01")
MARKETS = {  # root: (IV-Index, Kosten Pkt, Punktwert $, RTH Start, RTH Minuten)
    "NQ": ("VXN", 0.75, 20, 570, 390),
    "ES": ("VIX", 0.6, 50, 570, 390),
    "RTY": ("RVX", 0.3, 50, 570, 390),
    "GC": ("GVZ", 0.25, 100, 500, 310),
}


def load_iv(name):
    df = pd.read_csv(HERE / f"data/iv/{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    return pd.Series(df.iloc[:, -1].astype(float).values,
                     index=pd.to_datetime(df["DATE"]).astype("datetime64[ns]"), name=name)


def load_market(root, iv_name, start, n):
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{root.lower()}_1m/*.parquet"))))
    df = df.sort_values("ts_utc").reset_index(drop=True)
    m = (df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy()
    days = np.array(sorted(df["session_date"].unique()))
    di = pd.Categorical(df["session_date"], categories=days).codes
    sel = (m >= start) & (m < start + n)
    G = {}
    for k in ["open", "high", "low", "close", "volume"]:
        a = np.full((len(days), n), np.nan)
        a[di[sel], m[sel] - start] = df[k].to_numpy()[sel]
        G[k] = a
    G["volume"] = np.nan_to_num(G["volume"])
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    full = ((G["volume"] > 0).sum(1) >= 0.97 * n) & np.isfinite(G["close"][:, -5:]).any(1)
    adj = df.groupby(di)["adj"].first().reindex(range(len(days))).to_numpy()
    op = G["open"][:, 0]
    op = np.where(np.isfinite(op), op, G["cff"][:, 0])
    close = G["cff"][:, -1]
    prev_close = np.r_[np.nan, close[:-1] + adj[:-1] - adj[1:]]
    tp = (G["high"] + G["low"] + G["close"]) / 3
    vw = np.nancumsum(np.nan_to_num(tp) * G["volume"], 1) / np.maximum(np.cumsum(G["volume"], 1), 1)
    # IV zum Vortag (letzter Close vor Session)
    iv = load_iv(iv_name)
    anchor = pd.to_datetime(days).astype("datetime64[ns]") - pd.Timedelta(days=1)
    ivd = pd.merge_asof(pd.DataFrame({"a": anchor}), iv.rename("v").rename_axis("d").reset_index(), left_on="a", right_on="d")
    ivv = np.where((ivd["a"] - ivd["d"]).dt.days <= 5, ivd["v"], np.nan)
    return dict(days=pd.to_datetime(days), G=G, full=full, op=op, close=close, prev_close=prev_close, vw=vw,
                sig=op * ivv / 100 / np.sqrt(252), n=n)


def noise_sim(M, cost, bound_fn, step):
    """Gibt Liste (tag_idx, pnl_pkt, richtung) zurück."""
    G, n = M["G"], M["n"]
    cps = list(range(30, n, step))
    trades = []
    for i in np.flatnonzero(M["full"] & np.isfinite(M["prev_close"])):
        bnd = bound_fn(i)
        if bnd is None:
            continue
        ub, lb = bnd
        pos, entry = 0, 0.0
        for cp in cps:
            px = G["cff"][i, cp - 1]
            vw = M["vw"][i, cp - 1]
            if pos == 1 and px < max(ub[cp], vw):
                trades.append((i, px - entry - cost, 1))
                pos = 0
            elif pos == -1 and px > min(lb[cp], vw):
                trades.append((i, entry - px - cost, -1))
                pos = 0
            if pos == 0:
                if px > ub[cp]:
                    pos, entry = 1, px
                elif px < lb[cp]:
                    pos, entry = -1, px
        if pos != 0:
            px = M["close"][i]
            trades.append((i, pos * (px - entry) - cost, pos))
    return trades


def hist_bounds(M):
    G, op = M["G"], M["op"]
    mv = np.abs(G["cff"] / op[:, None] - 1)
    sig_t = pd.DataFrame(np.where(M["full"][:, None], mv, np.nan)).rolling(14, min_periods=10).mean().shift(1).to_numpy()
    sig_t = np.c_[np.zeros(len(op)), sig_t[:, :-1]]  # Index cp = Preis zum Zeitpunkt cp (Close Bar cp-1)
    hi = np.maximum(op, M["prev_close"])
    lo = np.minimum(op, M["prev_close"])

    def f(i):
        if not np.isfinite(sig_t[i, 30]):
            return None
        return hi[i] * (1 + sig_t[i]), lo[i] * (1 - sig_t[i])
    return f


def iv_bounds(M, mult):
    t = np.arange(M["n"])
    root = np.sqrt(t / M["n"])

    def f(i):
        s = M["sig"][i]
        if not np.isfinite(s):
            return None
        hi = max(M["op"][i], M["prev_close"][i])
        lo = min(M["op"][i], M["prev_close"][i])
        return hi + mult * s * root, lo - mult * s * root
    return f


def orb5(M, cost):
    G, out = M["G"], []
    for i in np.flatnonzero(M["full"]):
        o, c = G["open"][i, 0], G["cff"][i, 4]
        hi, lo = np.nanmax(G["high"][i, :5]), np.nanmin(G["low"][i, :5])
        if not np.isfinite(o) or c == o:
            continue
        d = 1 if c > o else -1
        e, stop = c, (lo if d == 1 else hi)
        path = G["low"][i, 5:] if d == 1 else G["high"][i, 5:]
        hit = np.flatnonzero((path <= stop) if d == 1 else (path >= stop))
        pnl = (stop - e) * d if len(hit) else (M["close"][i] - e) * d
        out.append((i, pnl - cost, d))
    return out


def orb_break(M, cost, k):
    G, out = M["G"], []
    for i in np.flatnonzero(M["full"]):
        hi, lo = np.nanmax(G["high"][i, :k]), np.nanmin(G["low"][i, :k])
        H, L = G["high"][i, k:], G["low"][i, k:]
        up, dn = np.flatnonzero(H > hi), np.flatnonzero(L < lo)
        tu = up[0] if len(up) else 10**9
        td = dn[0] if len(dn) else 10**9
        if tu == td == 10**9 or tu == td:
            continue
        d, e, stop, t = (1, hi, lo, tu) if tu < td else (-1, lo, hi, td)
        path = L[t:] if d == 1 else H[t:]
        hit = np.flatnonzero((path <= stop) if d == 1 else (path >= stop))
        pnl = (stop - e) * d if len(hit) else (M["close"][i] - e) * d
        out.append((i, pnl - cost, d))
    return out


def reversal(M, cost, z=3.0, hold=15):
    G, out = M["G"], []
    c = G["cff"]
    r5 = c[:, 5:] - c[:, :-5]
    sd = pd.DataFrame(r5.T).rolling(60, min_periods=40).std().shift(1).T.to_numpy()
    for i in np.flatnonzero(M["full"]):
        t = 30
        while t < M["n"] - hold - 1:
            j = t - 5
            if np.isfinite(sd[i, j]) and sd[i, j] > 0 and abs(r5[i, j]) > z * sd[i, j]:
                d = -np.sign(r5[i, j])
                out.append((i, d * (c[i, t + hold] - c[i, t]) - cost, d))
                t += hold
            t += 1
    return out


def stats(M, trades, pv):
    if not trades:
        return {}
    T = pd.DataFrame(trades, columns=["i", "pnl", "d"])
    T["date"] = M["days"][T["i"].to_numpy()]
    T["train"] = T["date"] < SPLIT
    ndays = pd.Series(M["full"], index=M["days"])
    res = {}
    for part, g in [("Train", T[T["train"]]), ("Test", T[~T["train"]])]:
        dmask = (ndays.index < SPLIT) if part == "Train" else (ndays.index >= SPLIT)
        nd = int(ndays[dmask].sum())
        if len(g) < 30 or nd < 50:
            continue
        daily = g.groupby("date")["pnl"].sum().reindex(ndays[dmask & ndays.values].index, fill_value=0.0) * pv
        eq = daily.cumsum()
        res[part] = dict(
            trades_tag=len(g) / nd, n=len(g), pkt=g["pnl"].mean(), win=100 * (g["pnl"] > 0).mean(),
            pf=g.loc[g["pnl"] > 0, "pnl"].sum() / max(-g.loc[g["pnl"] < 0, "pnl"].sum(), 1e-9),
            sharpe=daily.mean() / daily.std() * np.sqrt(252) if daily.std() > 0 else np.nan,
            t=daily.mean() / daily.std() * np.sqrt(len(daily)) if daily.std() > 0 else np.nan,
            usd_jahr=daily.mean() * 252, maxdd=(eq - eq.cummax()).min(),
        )
    res["per_year"] = T.groupby(T["date"].dt.year)["pnl"].sum() * pv
    return res


rows, years = [], {}
for root, (ivn, cost, pv, start, n) in MARKETS.items():
    M = load_market(root, ivn, start, n)
    strats = {
        "NOISE-HIST 30m": noise_sim(M, cost, hist_bounds(M), 30),
        "NOISE-HIST 15m": noise_sim(M, cost, hist_bounds(M), 15),
        "NOISE-IV 0.5σ 30m": noise_sim(M, cost, iv_bounds(M, 0.5), 30),
        "NOISE-IV 0.75σ 30m": noise_sim(M, cost, iv_bounds(M, 0.75), 30),
        "NOISE-IV 1.0σ 30m": noise_sim(M, cost, iv_bounds(M, 1.0), 30),
        "NOISE-IV 0.75σ 15m": noise_sim(M, cost, iv_bounds(M, 0.75), 15),
        "ORB5-Richtung": orb5(M, cost),
        "ORB15-Break": orb_break(M, cost, 15),
        "ORB30-Break": orb_break(M, cost, 30),
        "REVERSAL 5m>3σ": reversal(M, cost),
    }
    for name, tr in strats.items():
        s = stats(M, tr, pv)
        years[(root, name)] = s.get("per_year")
        for part in ["Train", "Test"]:
            if part in s:
                rows.append(dict(Markt=root, Strategie=name, Teil=part, **s[part]))
    print(root, "fertig")

R = pd.DataFrame(rows)
piv = R.pivot_table(index=["Strategie", "Markt"], columns="Teil",
                    values=["trades_tag", "pkt", "win", "pf", "sharpe", "t", "usd_jahr", "maxdd"])
piv.columns = [f"{a} {b}" for a, b in piv.columns]
cols = ["trades_tag Test", "win Train", "win Test", "pf Train", "pf Test", "sharpe Train", "sharpe Test",
        "t Train", "t Test", "usd_jahr Test", "maxdd Test"]
piv = piv[[c for c in cols if c in piv.columns]].round(2)

# Bestanden: in >= 3 Märkten Train t >= 2 und Test t >= 2 (RTY: Train ab 2017)
ok = R.pivot_table(index=["Strategie", "Markt"], columns="Teil", values="t")
ok["beide"] = (ok.get("Train", np.nan) >= 2) & (ok.get("Test", np.nan) >= 2)
summary = ok.groupby("Strategie")["beide"].sum().sort_values(ascending=False)

yr = pd.DataFrame({f"{r} {s}": v for (r, s), v in years.items() if v is not None}).round(0)

md = ["# Intraday-Scan NQ / ES / RTY / GC (RTH, flat zum Ende)", "",
      "Werte pro 1 E-Mini-Kontrakt nach Kosten. Sharpe auf Tages-PnL. Train < 2021, Test ≥ 2021.", "",
      "## Wie viele Märkte bestehen (t ≥ 2 in Train UND Test)", "", summary.to_frame("Märkte bestanden").to_markdown(), "",
      "## Details", "", piv.to_markdown(), "",
      "## PnL je Jahr in $ (1 Kontrakt)", "", yr.to_markdown(), ""]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
print(summary.to_string())
print(piv.to_string())
