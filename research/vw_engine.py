"""
H9 – Backtest-Engine (1m, je Tag): Signal bei Kerzenschluss t → Einstieg Open t+1.
Stop (Preis-Gitter zum Signalzeitpunkt) intrabar, Ziel (Preis-Gitter) intrabar, gleiche Kerze → Stop zuerst.
Optional Close-Ausstieg (bool-Gitter: bei Kerzenschluss raus, Ausführung Open der nächsten Kerze). Flat zu flat_col (Close).
Max. Trades je Tag, keine Überlappung, Kosten je Round-Trip in Punkten.
"""
import numpy as np
import pandas as pd
from numba import njit


@njit(cache=True)
def run(O, H, L, C, sigL, sigS, stopL, stopS, tgtL, tgtS, exL, exS, t0, t_last, flat, max_tr, cost, day_ok):
    n, m = O.shape
    cap = n * max_tr
    out = np.empty((cap, 7))           # Tag, Einstieg-Min, Ausstieg-Min, Richtung, Einstiegspreis, Ausstiegspreis, PnL netto
    k = 0
    for d in range(n):
        if not day_ok[d]:
            continue
        tr = 0; t = t0
        while t <= t_last and tr < max_tr:
            dirn = 0
            if sigL[d, t]:
                dirn = 1
            elif sigS[d, t]:
                dirn = -1
            if dirn == 0 or t + 1 >= m or np.isnan(O[d, t + 1]):
                t += 1; continue
            e = t + 1; ep = O[d, e]
            sp = stopL[d, t] if dirn == 1 else stopS[d, t]
            tp = tgtL[d, t] if dirn == 1 else tgtS[d, t]
            if np.isnan(sp) or (dirn == 1 and sp >= ep) or (dirn == -1 and sp <= ep):
                t += 1; continue
            xp = np.nan; xi = -1
            j = e
            while j <= flat:
                hj = H[d, j]; lj = L[d, j]
                if not np.isnan(hj):
                    if dirn == 1 and lj <= sp:
                        xp = min(sp, O[d, j]) if not np.isnan(O[d, j]) else sp; xi = j; break
                    if dirn == -1 and hj >= sp:
                        xp = max(sp, O[d, j]) if not np.isnan(O[d, j]) else sp; xi = j; break
                    if not np.isnan(tp):
                        if dirn == 1 and hj >= tp:
                            xp = tp; xi = j; break
                        if dirn == -1 and lj <= tp:
                            xp = tp; xi = j; break
                    if j < flat and ((dirn == 1 and exL[d, j]) or (dirn == -1 and exS[d, j])):
                        # Close-Ausstieg: Open der nächsten Kerze
                        jj = j + 1
                        while jj <= flat and np.isnan(O[d, jj]):
                            jj += 1
                        if jj <= flat:
                            xp = O[d, jj]; xi = jj
                        else:
                            xp = C[d, flat]; xi = flat
                        break
                j += 1
            if xi < 0:
                xp = C[d, flat]; xi = flat
            out[k, 0] = d; out[k, 1] = e; out[k, 2] = xi; out[k, 3] = dirn; out[k, 4] = ep; out[k, 5] = xp
            out[k, 6] = dirn * (xp - ep) - cost
            k += 1; tr += 1
            t = xi + 1
    return out[:k]


def stats(T, D, usd, period=None):
    """Kennzahlen aus Trade-Array (Spalten wie run). D = vw_common.load(...)."""
    if len(T) == 0:
        return {"Trades": 0}
    days = D["days"]; per = D["period"]
    di = T[:, 0].astype(int)
    df = pd.DataFrame({"d": di, "pnl": T[:, 6], "per": per[di], "yr": pd.to_datetime(days[di]).year})
    if period is not None:
        df = df[df["per"] == period]
    if len(df) == 0:
        return {"Trades": 0}
    daily = df.groupby("d")["pnl"].sum()
    n_days = int(((per == period) if period is not None else np.ones(len(per), bool))[D["day_ok"]].sum())
    eq = daily.cumsum().to_numpy(); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    w, l = df["pnl"][df["pnl"] > 0], df["pnl"][df["pnl"] <= 0]
    yr = df.groupby("yr")["pnl"].sum()
    full = np.zeros(n_days); full[:len(daily)] = daily.to_numpy()
    return {"Trades": len(df), "Trades/Tag": round(len(df) / max(n_days, 1), 2), "EW Pkt": round(df["pnl"].mean(), 3),
            "Summe Pkt": round(df["pnl"].sum(), 1), "Treffer %": round(100 * (df["pnl"] > 0).mean(), 1),
            "PF": round(w.sum() / -l.sum(), 3) if l.sum() < 0 else np.nan, "Max DD Pkt": round(dd, 1), "Max DD $": round(dd * usd, 0),
            "schlechtester Tag Pkt": round(daily.min(), 1), "Sharpe Tag (ann.)": round(full.mean() / full.std() * np.sqrt(252), 2) if full.std() > 0 else np.nan,
            "Jahre pos": f"{int((yr > 0).sum())}/{len(yr)}"}
