"""
H12 – Intraday-Periodizität, exakt nach Vorab-Registrierung. Ausgabe nur Explore; Trades aller Zeiträume gespeichert.
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, USD, load  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h12_cache"
CACHE.mkdir(parents=True, exist_ok=True)
GRID = list(itertools.product((20, 40, 60), (0.0, 1.0, 1.5)))

out = {g: [] for g in GRID}
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    a, b = D["rth"]; O, C = D["O"], D["C"]
    starts = list(range(a, b - 29, 30))
    ok = D["day_ok"]
    R = np.full((D["n"], len(starts)), np.nan)
    for j, s in enumerate(starts):
        o = O[:, s]; c = C[:, s + 29]
        R[:, j] = np.where(ok & np.isfinite(o) & np.isfinite(c), c - o, np.nan)
    Rdf = pd.DataFrame(R)
    for L, tau in GRID:
        mu = Rdf.rolling(L, min_periods=int(0.8 * L)).mean().shift(1).to_numpy()
        sd = Rdf.rolling(L, min_periods=int(0.8 * L)).std().shift(1).to_numpy()
        t = mu / (sd / np.sqrt(L))
        tt = np.where(np.abs(t) >= tau, np.abs(t), np.nan)
        # je Tag die 3 Fenster mit größtem |t|
        rank = np.argsort(-np.nan_to_num(tt, nan=-1), axis=1)[:, :3]
        rows = []
        for d in np.flatnonzero(ok):
            for j in rank[d]:
                if np.isnan(tt[d, j]) or np.isnan(R[d, j]):
                    continue
                pnl = np.sign(mu[d, j]) * R[d, j] - COST[mk]
                rows.append((mk, D["days"][d], D["period"][d], j, pnl, pnl / D["atr"][d]))
        out[(L, tau)].append(pd.DataFrame(rows, columns=["Markt", "Tag", "Zeitraum", "Fenster", "pnl_pkt", "pnl_atr"]))
    print(mk, flush=True)
    del D

res = []
for g in GRID:
    df = pd.concat(out[g], ignore_index=True)
    df.to_parquet(CACHE / f"h12_L{g[0]}_t{g[1]}.parquet", index=False)
    e = df[df["Zeitraum"] == "Explore"]
    daily = e.groupby("Tag")["pnl_atr"].sum()
    yr = e.groupby(pd.to_datetime(e["Tag"]).dt.year)["pnl_atr"].sum()
    w, l = e["pnl_atr"][e["pnl_atr"] > 0], e["pnl_atr"][e["pnl_atr"] <= 0]
    eq = daily.cumsum().to_numpy()
    res.append({"L": g[0], "τ": g[1], "Trades": len(e), "EW % ATR": round(100 * e["pnl_atr"].mean(), 3), "PF": round(w.sum() / -l.sum(), 3),
                "Treffer %": round(100 * (e["pnl_atr"] > 0).mean(), 1), "Sharpe Tag": round(daily.mean() / daily.std() * np.sqrt(252), 2),
                "Max DD % ATR": round(100 * float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq])), 1),
                "Jahre pos": f"{int((yr > 0).sum())}/{len(yr)}",
                **{f"EW Pkt {m}": round(e[e['Markt'] == m]['pnl_pkt'].mean(), 3) for m in ["NQ", "ES", "RTY", "GC"]}})
X = pd.DataFrame(res)
X.to_csv(RES / "h12_explore.csv", index=False)
pd.set_option("display.width", 250)
print(X.to_string(index=False))
