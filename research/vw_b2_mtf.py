"""
H9 Runde 2 (nur Explore ausgeben): Multi-Timeframe-VWAP-Momentum.
G  Uhrzeit T: z_RTH ≥ k und Preis über Session-, Wochen- und Monats-VWAP (oder nur RTH + Monat) → Long (Spiegel Short).
   Ausstieg: (a) mitlaufend – Close unter RTH-VWAP → raus, harter Stop VWAP − 1σ; (b) fester Stop VWAP − 0,5σ. Sonst RTH-Ende.
H  Erstes Mal nach RTH+30 Min.: Close über +kσ (RTH) mit Ausrichtung → Long, Ausstiege wie G.
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, USD, load  # noqa: E402
from vw_engine import run, stats  # noqa: E402
from vw_b_explore import first_true_mask, CACHE  # noqa: E402

RES = Path(__file__).parent / "results"


def variants(D):
    a, b = D["rth"]
    Cf = D["C"]; W, S = D["rVW"], D["rVS"]
    z = (Cf - W) / S
    nan = np.full_like(W, np.nan)
    F = np.zeros_like(W, dtype=bool)
    upAll = (Cf > D["sVW"]) & (Cf > D["wVW"]) & (Cf > D["mVW"]); dnAll = (Cf < D["sVW"]) & (Cf < D["wVW"]) & (Cf < D["mVW"])
    upM = Cf > D["mVW"]; dnM = Cf < D["mVW"]
    trailL = Cf < W; trailS = Cf > W
    for T, k, al, ex in itertools.product((a + 60, a + 120, a + 180, a + 240), (1.0, 1.5), ("alle", "RTH+Monat"), ("trail", "fest")):
        up, dn = (upAll, dnAll) if al == "alle" else (upM, dnM)
        sl = F.copy(); ss = F.copy()
        sl[:, T] = (z[:, T] >= k) & up[:, T]; ss[:, T] = (z[:, T] <= -k) & dn[:, T]
        if ex == "trail":
            yield (f"G T+{T - a} k{k} {al} trail", sl, ss, W - S, W + S, nan, nan, trailL, trailS, T, T, 1)
        else:
            yield (f"G T+{T - a} k{k} {al} fest", sl, ss, W - 0.5 * S, W + 0.5 * S, nan, nan, F, F, T, T, 1)
    for k, al, ex in itertools.product((1.0, 2.0), ("alle", "RTH+Monat"), ("trail", "fest")):
        up, dn = (upAll, dnAll) if al == "alle" else (upM, dnM)
        win = F.copy(); win[:, a + 30:b - 60] = True
        sl = first_true_mask(win & (z >= k) & up); ss = first_true_mask(win & (z <= -k) & dn)
        if ex == "trail":
            yield (f"H k{k} {al} trail", sl, ss, W - S, W + S, nan, nan, trailL, trailS, a + 30, b - 60, 1)
        else:
            yield (f"H k{k} {al} fest", sl, ss, W - 0.5 * S, W + 0.5 * S, nan, nan, F, F, a + 30, b - 60, 1)


rows = []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    flat = D["rth"][1] - 1; nv = 0
    for (name, sl, ss, stL, stS, tL, tS, eL, eS, t0, t1, mx) in variants(D):
        nv += 1
        T = run(D["O"], D["H"], D["L"], D["C"], sl, ss, stL, stS, tL, tS, eL, eS, t0, t1, flat, mx, COST[mk], D["day_ok"])
        np.save(CACHE / f"{mk}_{name.replace(' ', '_').replace('+', 'p')}.npy", T)
        rows.append({"Markt": mk, "Variante": name, "Familie": name[0], **stats(T, D, USD[mk], "Explore")})
    print(mk, nv, flush=True)
    del D
X = pd.DataFrame(rows)
X.to_csv(RES / "vw_b2_mtf.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print(X.groupby(["Familie", "Markt"])["EW Pkt"].median().round(3).unstack().to_string())
g = X[(X["EW Pkt"] > 0) & (X["PF"] >= 1.1)].sort_values("Sharpe Tag (ann.)", ascending=False)
print(g[["Markt", "Variante", "Trades", "Trades/Tag", "EW Pkt", "Treffer %", "PF", "Max DD Pkt", "Sharpe Tag (ann.)", "Jahre pos"]].to_string(index=False))
