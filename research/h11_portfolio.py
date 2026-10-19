"""
H11 – VWAP-Momentum-Portfolio (NQ, ES, RTY, GC × Prüfzeitpunkte), exakt nach Vorab-Registrierung.
Ausgabe hier: nur Explore (2011–2019). Trades aller Zeiträume werden für die spätere Prüfung gespeichert.
Ergebnis je Trade in R = Netto-Gewinn / Stop-Abstand (Einstieg ↔ Stop zum Signalzeitpunkt).
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, load  # noqa: E402
from vw_engine import run  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h11_cache"
CACHE.mkdir(parents=True, exist_ok=True)
GRID = list(itertools.product((1.0, 1.5), ("alle", "Monat"), ("3x", "2x"), ("ohne", "range0.6")))


def variant_trades(D, k, al, tp, flt):
    a, b = D["rth"]
    Cf = D["C"]; W, S = D["rVW"], D["rVS"]
    z = (Cf - W) / S
    if al == "alle":
        up = (Cf > D["sVW"]) & (Cf > D["wVW"]) & (Cf > D["mVW"]); dn = (Cf < D["sVW"]) & (Cf < D["wVW"]) & (Cf < D["mVW"])
    else:
        up = Cf > D["mVW"]; dn = Cf < D["mVW"]
    if flt == "range0.6":
        with np.errstate(all="ignore"):
            cH = np.fmax.accumulate(np.nan_to_num(D["H"], nan=-np.inf), 1); cL = np.fmin.accumulate(np.nan_to_num(D["L"], nan=np.inf), 1)
        energy = (cH - cL) / D["atr"][:, None] >= 0.6
    else:
        energy = np.ones_like(up)
    times = [a + 60, a + 150, a + 270] if tp == "3x" else [a + 60, a + 150]
    times = [t for t in times if t < b - 10]
    F = np.zeros_like(up)
    sl, ss = F.copy(), F.copy()
    for t in times:
        sl[:, t] = (z[:, t] >= k) & up[:, t] & energy[:, t]; ss[:, t] = (z[:, t] <= -k) & dn[:, t] & energy[:, t]
    nan = np.full_like(W, np.nan)
    stL, stS = W - 0.5 * S, W + 0.5 * S
    T = run(D["O"], D["H"], D["L"], D["C"], sl, ss, stL, stS, nan, nan, F, F, times[0], times[-1], b - 1, 3, COST[D["mk"]], D["day_ok"])
    if len(T) == 0:
        return pd.DataFrame()
    di, e = T[:, 0].astype(int), T[:, 1].astype(int)
    stop = np.where(T[:, 3] == 1, stL[di, e - 1], stS[di, e - 1])
    risk = np.abs(T[:, 4] - stop)
    return pd.DataFrame({"Markt": D["mk"], "Tag": D["days"][di], "Zeitraum": D["period"][di], "min": e, "dir": T[:, 3],
                         "pnl_pkt": T[:, 6], "risk_pkt": risk, "R": T[:, 6] / risk})


def summarize(df, ndays):
    if len(df) == 0:
        return {}
    daily = df.groupby("Tag")["R"].sum()
    full = np.zeros(ndays); full[:len(daily)] = daily.to_numpy()
    eq = daily.cumsum().to_numpy(); dd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    w, l = df["R"][df["R"] > 0], df["R"][df["R"] <= 0]
    yr = df.groupby(pd.to_datetime(df["Tag"]).dt.year)["R"].sum()
    return {"Trades": len(df), "Trades/Tag": round(len(df) / ndays, 2), "EW R": round(df["R"].mean(), 4), "Summe R": round(df["R"].sum(), 1),
            "Treffer %": round(100 * (df["R"] > 0).mean(), 1), "PF": round(w.sum() / -l.sum(), 3), "Max DD R": round(dd, 1),
            "schlechtester Tag R": round(daily.min(), 2), "Sharpe Tag (ann.)": round(full.mean() / full.std() * np.sqrt(252), 2),
            "Jahre pos": f"{int((yr > 0).sum())}/{len(yr)}", "Ø Risiko Pkt": round(df["risk_pkt"].mean(), 1)}


if __name__ == "__main__":
    allT = {g: [] for g in GRID}
    ndays = {}
    for mk in ["NQ", "ES", "RTY", "GC"]:
        D = load(mk)
        for per in ("Explore", "Validate", "Test"):
            ndays.setdefault(per, set()).update(D["days"][(D["period"] == per) & D["day_ok"]])
        for g in GRID:
            allT[g].append(variant_trades(D, *g))
        print(mk, flush=True)
        del D
    rows = []
    for g in GRID:
        df = pd.concat(allT[g], ignore_index=True)
        df.to_parquet(CACHE / f"h11_{'_'.join(map(str, g))}.parquet", index=False)
        e = df[df["Zeitraum"] == "Explore"]
        rows.append({"k": g[0], "Ausrichtung": g[1], "Zeitpunkte": g[2], "Filter": g[3], **summarize(e, len(ndays["Explore"])),
                     **{f"EW R {m}": round(e[e["Markt"] == m]["R"].mean(), 3) for m in ["NQ", "ES", "RTY", "GC"]}})
    X = pd.DataFrame(rows)
    X.to_csv(RES / "h11_explore.csv", index=False)
    pd.set_option("display.width", 260)
    print(X.to_string(index=False))
