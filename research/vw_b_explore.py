"""
H9 – Setup-Familien auf Explore (≤ 2019). Validate/Test werden hier berechnet, aber NICHT ausgegeben.
Familien (Mechanismus aus der VWAP-Landkarte: Preis läuft eher vom VWAP weg, besonders nachmittags):
  A  Nachmittags-Trend: um Uhrzeit T, wenn z_RTH ≥ k → Long (≤ −k Short), Stop am VWAP (bzw. VWAP ∓ 0,5σ), raus zum RTH-Ende
  B  Trend-Pullback: N Minuten alle Closes über VWAP und VWAP steigt; Tief berührt VWAP+xσ, Close darüber → Long; Stop VWAP − sσ
  C  Band-Ausbruch: Close erstmals über +kσ und VWAP steigt → Long; Stop am (k−1)σ-Band; Ziel Schluss oder +(k+1)σ
  D  Band-Fade (Gegenprobe Mean Reversion): Close zurück innerhalb ±kσ nach Überschreitung → Richtung VWAP; Ziel VWAP/1σ
  F  Eröffnung: 5 Min. nach RTH-Start über London- und Session-VWAP → Long (Spiegel Short), Stop Session-VWAP, raus zum RTH-Ende

Aufruf: python research/vw_b_explore.py → research/results/vw_b_explore.csv (nur Explore-Kennzahlen)
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, USD, load  # noqa: E402
from vw_engine import run, stats  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/vw_cache"
CACHE.mkdir(parents=True, exist_ok=True)


def rolling_all(cond, N):
    """True, wenn cond in den letzten N Minuten (inkl. t) durchgehend wahr war."""
    c = np.cumsum(np.nan_to_num(cond.astype(float)), 1)
    out = np.zeros_like(cond, dtype=bool)
    out[:, N - 1:] = (c[:, N - 1:] - np.c_[np.zeros((c.shape[0], 1)), c[:, :-N]]) >= N
    return out


def first_true_mask(cond):
    """Nur die erste True-Minute je Tag."""
    cs = np.cumsum(cond, 1)
    return cond & (cs == 1)


def variants(D):
    mk = D["mk"]; a, b = D["rth"]; n = D["n"]
    O, H, L, C = D["O"], D["H"], D["L"], D["Cl"]
    Cf = D["C"]
    W, S = D["rVW"], D["rVS"]
    z = (Cf - W) / S
    slope = np.full_like(W, np.nan); slope[:, 30:] = W[:, 30:] - W[:, :-30]
    nan = np.full_like(W, np.nan); F = np.zeros_like(W, dtype=bool)
    win = np.zeros_like(W, dtype=bool)
    flat = b - 1
    # A Nachmittags-Trend
    for T, k, sb in itertools.product((a + 150, a + 210, a + 270), (0.5, 1.0, 1.5), (0.0, 0.5)):
        sl = np.zeros_like(F); ss = np.zeros_like(F)
        sl[:, T] = z[:, T] >= k; ss[:, T] = z[:, T] <= -k
        yield ((f"A T+{T - a} k{k} stop{sb}", sl, ss, W - sb * S, W + sb * S, nan, nan, F, F, T, T, 1))
    # B Trend-Pullback
    w0, w1 = a + 60, b - 60
    win[:] = False; win[:, w0:w1] = True
    for N, x, s, tg in itertools.product((30, 60), (0.0, 0.5), (0.5, 1.0), ("close", "2s")):
        above = rolling_all(Cf > W, N); below = rolling_all(Cf < W, N)
        prevA = np.zeros_like(F); prevA[:, 1:] = above[:, :-1]; prevB = np.zeros_like(F); prevB[:, 1:] = below[:, :-1]
        sl = win & prevA & (slope > 0) & (L <= W + x * S) & (Cf > W + x * S)
        ss = win & prevB & (slope < 0) & (H >= W - x * S) & (Cf < W - x * S)
        tl = W + 2 * S if tg == "2s" else nan; ts = W - 2 * S if tg == "2s" else nan
        yield ((f"B N{N} x{x} s{s} {tg}", sl, ss, W - s * S, W + s * S, tl, ts, F, F, w0, w1, 2))
    # C Band-Ausbruch
    for k, tg, st in itertools.product((1.0, 2.0), ("close", "next"), (a + 30, a + 60)):
        win2 = np.zeros_like(F); win2[:, st:b - 60] = True
        up = win2 & (Cf > W + k * S) & (slope > 0); dn = win2 & (Cf < W - k * S) & (slope < 0)
        sl, ss = first_true_mask(up), first_true_mask(dn)
        tl = W + (k + 1) * S if tg == "next" else nan; ts = W - (k + 1) * S if tg == "next" else nan
        yield ((f"C k{k} {tg} start+{st - a}", sl, ss, W + (k - 1) * S, W - (k - 1) * S, tl, ts, F, F, st, b - 60, 1))
    # D Band-Fade
    for k, tg, st in itertools.product((2.0, 2.5, 3.0), ("vwap", "1s"), (a + 30, a + 90)):
        win3 = np.zeros_like(F); win3[:, st:b - 30] = True
        prevOut_up = np.zeros_like(F); prevOut_up[:, 1:] = (Cf > W + k * S)[:, :-1]
        prevOut_dn = np.zeros_like(F); prevOut_dn[:, 1:] = (Cf < W - k * S)[:, :-1]
        ss = win3 & prevOut_up & (Cf <= W + k * S)            # Short nach Rückkehr von oben
        sl = win3 & prevOut_dn & (Cf >= W - k * S)
        hiE = pd.DataFrame(H).cummax(axis=1).to_numpy(); loE = pd.DataFrame(L).cummin(axis=1).to_numpy()
        tl = W if tg == "vwap" else W - S; ts = W if tg == "vwap" else W + S
        yield ((f"D k{k} {tg} start+{st - a}", sl, ss, loE - 0.5 * S, hiE + 0.5 * S, tl, ts, F, F, st, b - 30, 3))
    # F Eröffnung zu London-/Session-VWAP
    T = a + 5
    for stopv in ("session", "rth"):
        sl = np.zeros_like(F); ss = np.zeros_like(F)
        sl[:, T] = (Cf[:, T] > D["lonVW"]) & (Cf[:, T] > D["sVW"][:, T])
        ss[:, T] = (Cf[:, T] < D["lonVW"]) & (Cf[:, T] < D["sVW"][:, T])
        stp = D["sVW"] if stopv == "session" else W
        yield ((f"F open>London&Session stop{stopv}", sl, ss, stp, stp, nan, nan, F, F, T, T, 1))


rows = []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    flat = D["rth"][1] - 1
    nv = 0
    for (name, sl, ss, stL, stS, tL, tS, eL, eS, t0, t1, mx) in variants(D):
        nv += 1
        T = run(D["O"], D["H"], D["L"], D["C"], sl, ss, stL, stS, tL, tS, eL, eS, t0, t1, flat, mx, COST[mk], D["day_ok"])
        np.save(CACHE / f"{mk}_{name.replace(' ', '_').replace('>', 'gt').replace('&', '_')}.npy", T)
        st = stats(T, D, USD[mk], "Explore")
        rows.append({"Markt": mk, "Variante": name, "Familie": name[0], **st})
    print(mk, nv, "Varianten", flush=True)
    del D
X = pd.DataFrame(rows)
X.to_csv(RES / "vw_b_explore.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 400)
print(X.sort_values(["Familie", "Variante", "Markt"]).to_string(index=False))
