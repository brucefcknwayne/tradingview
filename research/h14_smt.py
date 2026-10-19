"""
H14 – SMT-Divergenz NQ ↔ ES, exakt nach Vorab-Registrierung. Ausgabe nur Explore; Trades aller Zeiträume gespeichert.
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
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h14_cache"
CACHE.mkdir(parents=True, exist_ok=True)

Dn, De = load("NQ"), load("ES")
common = np.intersect1d(Dn["days"], De["days"])
def sub(D):
    idx = np.searchsorted(D["days"], common)
    out = {k: (v[idx] if isinstance(v, np.ndarray) and v.shape[:1] == (D["n"],) else v) for k, v in D.items()}
    out["n"] = len(common); out["days"] = common
    return out
Dn, De = sub(Dn), sub(De)


def prior_high(H, start):
    X = np.full_like(H, np.nan); x = np.nan_to_num(H[:, start:], nan=-np.inf)
    cm = np.maximum.accumulate(x, 1)
    X[:, start + 1:] = cm[:, :-1]
    X[X == -np.inf] = np.nan
    return X


def prior_low(L, start):
    X = np.full_like(L, np.nan); x = np.nan_to_num(L[:, start:], nan=np.inf)
    cm = np.minimum.accumulate(x, 1)
    X[:, start + 1:] = cm[:, :-1]
    X[X == np.inf] = np.nan
    return X


rows = []
for A, B in ((Dn, De), (De, Dn)):
    mk = A["mk"]
    a, b = A["rth"]
    F = np.zeros_like(A["C"], dtype=bool); nan = np.full_like(A["C"], np.nan)
    win = F.copy(); win[:, 960:1260] = True
    for span, buf, tg in itertools.product(("RTH", "Session"), (0.05, 0.15), ("VWAP", "1R", "2R")):
        st = a if span == "RTH" else 0
        pHa, pLa, pHb, pLb = prior_high(A["H"], st), prior_low(A["L"], st), prior_high(B["H"], st), prior_low(B["L"], st)
        atrA, atrB = A["atr"][:, None], B["atr"][:, None]
        newHa = A["H"] > pHa; newLa = A["L"] < pLa
        failHb = B["H"] <= pHb - 0.05 * atrB; failLb = B["L"] >= pLb + 0.05 * atrB
        ss = win & newHa & failHb; sl = win & newLa & failLb
        stS = A["H"] + buf * atrA; stL = A["L"] - buf * atrA
        Cf = A["C"]
        if tg == "VWAP":
            tS, tL = A["rVW"], A["rVW"]
        else:
            m = 1.0 if tg == "1R" else 2.0
            tS = Cf - m * (stS - Cf); tL = Cf + m * (Cf - stL)
        T = run(A["O"], A["H"], A["L"], A["C"], sl, ss, stL, stS, tL, tS, F, F, 960, 1259, b - 1, 2, COST[mk], A["day_ok"])
        name = f"{mk} {span} buf{buf} {tg}"
        np.save(CACHE / f"{name.replace(' ', '_')}.npy", T)
        rows.append({"Markt": mk, "Spanne": span, "Puffer": buf, "Ziel": tg, **stats(T, A, USD[mk], "Explore")})
X = pd.DataFrame(rows)
X.to_csv(RES / "h14_explore.csv", index=False)
pd.set_option("display.width", 250)
print(X.to_string(index=False))
