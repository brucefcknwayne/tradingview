"""
H9 Runde 3 (nur Explore ausgeben):
I  Pullback in Richtung höherer Zeitebenen: Preis über Woche/Monat-VWAP, Tief berührt RTH-VWAP, Close darüber (10:30–14:30) → Long
J  Opening-Range-Breakout (15/30/60 Min.) mit/ohne VWAP-Ausrichtung, Stop OR-Mitte bzw. Gegenseite, raus RTH-Ende
K  Momentum an energiereichen Tagen: wie G (11:30/12:30, z ≥ k, alle VWAPs ausgerichtet), nur wenn Range bisher ≥ x·ATR
L  Gap zum Vortags-RTH-VWAP bei RTH-Start: mitgehen oder faden, Stop Session-VWAP bzw. 0,3 ATR, raus RTH-Ende
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
    H, L = D["H"], D["L"]; Cf = D["C"]; W, S = D["rVW"], D["rVS"]
    z = (Cf - W) / S
    nan = np.full_like(W, np.nan); F = np.zeros_like(W, dtype=bool)
    upWM = (Cf > D["wVW"]) & (Cf > D["mVW"]); dnWM = (Cf < D["wVW"]) & (Cf < D["mVW"])
    upAll = upWM & (Cf > D["sVW"]); dnAll = dnWM & (Cf < D["sVW"])
    trailL = Cf < W; trailS = Cf > W
    # I
    for al, s, ex, w in itertools.product(("Woche+Monat", "Monat"), (0.5, 1.0), ("close", "trail"), ((60, 300), (60, 180))):
        up = upWM if al == "Woche+Monat" else (Cf > D["mVW"]); dn = dnWM if al == "Woche+Monat" else (Cf < D["mVW"])
        win = F.copy(); win[:, a + w[0]:a + w[1]] = True
        sl = win & up & (L <= W) & (Cf > W); ss = win & dn & (H >= W) & (Cf < W)
        eL, eS = (trailL, trailS) if ex == "trail" else (F, F)
        yield (f"I {al} s{s} {ex} w{w[0]}-{w[1]}", sl, ss, W - s * S, W + s * S, nan, nan, eL, eS, a + w[0], a + w[1], 2)
    # J
    with np.errstate(all="ignore"):
        cumH = np.fmax.accumulate(np.nan_to_num(H, nan=-np.inf), 1); cumL = np.fmin.accumulate(np.nan_to_num(L, nan=np.inf), 1)
    for orm, st, al in itertools.product((15, 30, 60), ("mitte", "gegen"), ("alle", "ohne")):
        e0 = a + orm
        with np.errstate(all="ignore"):
            orH = np.nanmax(H[:, a:e0], 1)[:, None] * np.ones((1, H.shape[1])); orL = np.nanmin(L[:, a:e0], 1)[:, None] * np.ones((1, H.shape[1]))
        win = F.copy(); win[:, e0:b - 90] = True
        up = win & (Cf > orH); dn = win & (Cf < orL)
        if al == "alle":
            up &= upAll; dn &= dnAll
        sl, ss = first_true_mask(up), first_true_mask(dn)
        mid = (orH + orL) / 2
        stL, stS = (mid, mid) if st == "mitte" else (orL, orH)
        yield (f"J OR{orm} stop{st} {al}", sl, ss, stL, stS, nan, nan, F, F, e0, b - 90, 1)
    # K
    rng_sofar = (cumH - cumL) / D["atr"][:, None]
    for T, k, x in itertools.product((a + 120, a + 180), (1.0, 1.5), (0.6, 0.8)):
        sl = F.copy(); ss = F.copy()
        sl[:, T] = (z[:, T] >= k) & upAll[:, T] & (rng_sofar[:, T] >= x); ss[:, T] = (z[:, T] <= -k) & dnAll[:, T] & (rng_sofar[:, T] >= x)
        yield (f"K T+{T - a} k{k} range>={x}", sl, ss, W - 0.5 * S, W + 0.5 * S, nan, nan, F, F, T, T, 1)
    # L
    T = a
    gap = (D["O"][:, a] - D["pRVW"]) / D["atr"]
    for g, mode, stp in itertools.product((0.2, 0.4), ("mit", "fade"), ("sVWAP", "0.3ATR")):
        sl = F.copy(); ss = F.copy()
        upg, dng = gap >= g, gap <= -g
        if mode == "mit":
            sl[:, T] = upg; ss[:, T] = dng
        else:
            sl[:, T] = dng; ss[:, T] = upg
        if stp == "sVWAP":
            stL = stS = D["sVW"]
        else:
            stL = Cf - 0.3 * D["atr"][:, None]; stS = Cf + 0.3 * D["atr"][:, None]
        yield (f"L gap{g} {mode} stop{stp}", sl, ss, stL, stS, nan, nan, F, F, T, T, 1)


rows = []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    flat = D["rth"][1] - 1; nv = 0
    for (name, sl, ss, stL, stS, tL, tS, eL, eS, t0, t1, mx) in variants(D):
        nv += 1
        T = run(D["O"], D["H"], D["L"], D["C"], sl, ss, stL, stS, tL, tS, eL, eS, t0, t1, flat, mx, COST[mk], D["day_ok"])
        np.save(CACHE / f"{mk}_{name.replace(' ', '_').replace('+', 'p').replace('>=', 'ge')}.npy", T)
        rows.append({"Markt": mk, "Variante": name, "Familie": name[0], **stats(T, D, USD[mk], "Explore")})
    print(mk, nv, flush=True)
    del D
X = pd.DataFrame(rows)
X.to_csv(RES / "vw_b3.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print(X.groupby(["Familie", "Markt"])["EW Pkt"].median().round(3).unstack().to_string())
g = X[(X["EW Pkt"] > 0) & (X["PF"] >= 1.1)].sort_values("Sharpe Tag (ann.)", ascending=False)
print(g[["Markt", "Variante", "Trades", "Trades/Tag", "EW Pkt", "Treffer %", "PF", "Max DD Pkt", "Sharpe Tag (ann.)", "Jahre pos"]].to_string(index=False))
