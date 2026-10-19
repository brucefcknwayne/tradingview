"""
H9 – Prüfung der Kandidaten unverändert auf Validate (2020–2024) und Test (2025 – 2026-04-16).
K1 NQ  G T+120 k1.5 alle fest   (11:30 ET, z_RTH ≥ 1,5 und über Session/Woche/Monat-VWAP; Stop VWAP ∓ 0,5σ; raus RTH-Ende)
K2 RTY H k1.0 RTH+Monat fest    (erster Close ≥ +1σ ab 10:00 und über Monats-VWAP; Stop VWAP ∓ 0,5σ; raus RTH-Ende)
Zufall: gleicher Stop-Abstand (Punkte), gleiche Richtung, Einstieg in derselben Minute (K1) bzw. derselben Stunde (K2) an einem
zufälligen anderen Tag desselben Zeitraums, Ausstieg RTH-Ende; 1.000 Wiederholungen. KI: Bootstrap über Handelstage.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, USD, load  # noqa: E402
from vw_engine import stats  # noqa: E402
from vw_b_explore import CACHE  # noqa: E402

RES = Path(__file__).parent / "results"
CANDS = [("K3", "NQ", "K_Tp120_k1.5_rangege0.6", "minute")]


@njit(cache=True)
def sim_fixed(O, H, L, C, d, e, dirn, sd, flat, cost):
    ep = O[d, e]
    if np.isnan(ep):
        return np.nan
    sp = ep - dirn * sd
    for j in range(e, flat + 1):
        if np.isnan(H[d, j]):
            continue
        if (dirn == 1 and L[d, j] <= sp) or (dirn == -1 and H[d, j] >= sp):
            return -sd - cost
    return dirn * (C[d, flat] - ep) - cost


@njit(cache=True)
def rand_pnl(O, H, L, C, days_pool, ents, dirs, sds, mode_hour, flat, cost, nrep, seed):
    np.random.seed(seed)
    k = len(ents); out = np.full((k, nrep), np.nan)
    for j in range(k):
        for r in range(nrep):
            for _ in range(50):
                d = days_pool[np.random.randint(len(days_pool))]
                e = ents[j, 1]
                if mode_hour:
                    e = (ents[j, 1] // 60) * 60 + np.random.randint(60)
                if d != ents[j, 0] and e <= flat and not np.isnan(O[d, e]):
                    out[j, r] = sim_fixed(O, H, L, C, d, e, dirs[j], sds[j], flat, cost)
                    break
    return out


def holm(p):
    p = np.asarray(p, float); m = len(p); o = np.argsort(p); adj = np.empty(m); run_ = 0.0
    for r, i in enumerate(o):
        run_ = max(run_, (m - r) * p[i]); adj[i] = min(run_, 1.0)
    return adj


rows = []
for cid, mk, name, mode in CANDS:
    D = load(mk)
    T = np.load(CACHE / f"{mk}_{name}.npy")
    flat = D["rth"][1] - 1
    for per in ("Explore", "Validate", "Test"):
        di = T[:, 0].astype(int); sel = D["period"][di] == per
        Tp = T[sel]
        st = stats(T, D, USD[mk], per)
        if len(Tp) == 0:
            rows.append(dict(Kandidat=cid, Markt=mk, Zeitraum=per, **st)); continue
        # Bootstrap-KI über Tage
        daily = pd.Series(Tp[:, 6]).groupby(Tp[:, 0].astype(int)).sum().to_numpy()
        rng = np.random.default_rng(1)
        bt = np.array([rng.choice(daily, len(daily)).sum() / len(Tp) for _ in range(2000)])
        # Zufall
        pool = np.flatnonzero((D["period"] == per) & D["day_ok"]).astype(np.int64)
        sds = np.abs(Tp[:, 4] - np.where(Tp[:, 3] == 1, (D["rVW"] - 0.5 * D["rVS"])[Tp[:, 0].astype(int), Tp[:, 1].astype(int) - 1],
                                         (D["rVW"] + 0.5 * D["rVS"])[Tp[:, 0].astype(int), Tp[:, 1].astype(int) - 1]))
        R = rand_pnl(D["O"], D["H"], D["L"], D["C"], pool, Tp[:, :2].astype(np.int64), Tp[:, 3].astype(np.int64), sds,
                     mode == "hour", flat, COST[mk], 1000, 5)
        rm = np.nanmean(R, 0)
        p = (1 + (rm >= Tp[:, 6].mean()).sum()) / 1001
        rows.append(dict(Kandidat=cid, Markt=mk, Zeitraum=per, **st, **{"KI95 EW unten": round(np.percentile(bt, 2.5), 3),
                         "KI95 EW oben": round(np.percentile(bt, 97.5), 3), "Zufall EW": round(rm.mean(), 3), "p roh": round(p, 4)}))
    print(cid, "fertig", flush=True)
    del D
X = pd.DataFrame(rows)
for per in ("Validate", "Test"):
    m = X["Zeitraum"] == per
    X.loc[m, "p Holm"] = holm(X.loc[m, "p roh"].to_numpy())
X["bestanden"] = (X["Zeitraum"] != "Explore") & (X["EW Pkt"] > 0) & (X["KI95 EW unten"] > 0) & (X["PF"] >= 1.1) & (X["p Holm"] < 0.05)
X.to_csv(RES / f"vw_c_validate_{CANDS[0][0]}.csv", index=False)
pd.set_option("display.width", 260)
print(X.to_string(index=False))
