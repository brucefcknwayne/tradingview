"""
H9 – Landkarte (nur Explore ≤ 2019): Läuft der Preis vom VWAP weg weiter oder zurück?
Zu festen Uhrzeiten: z = (Close − VWAP)/σ_VWAP für RTH-, Session-, Wochen-, Monats-VWAP.
Ergebnis: Ø Rendite bis RTH-Ende (in % ATR, Vorzeichen in Richtung z: + = weiter weg / Trend, − = zurück / Mean Reversion).

Aufruf: python research/vw_d_map.py → research/results/vw_d_map.csv/.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import load  # noqa: E402

RES = Path(__file__).parent / "results"
BINS = [-np.inf, -2, -1, -0.5, 0, 0.5, 1, 2, np.inf]
rows = []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    a, b = D["rth"]
    ok = D["day_ok"] & (D["period"] == "Explore")
    C = D["C"]
    end = C[:, b - 1]
    for off in (30, 60, 90, 150, 210, 270, 330):
        t = a + off
        if t >= b - 5:
            continue
        hhmm = f"{((t + 1080) % 1440) // 60:02d}:{(t + 1080) % 60:02d}"
        fwd = (end - C[:, t]) / D["atr"]
        for vname, W, S in (("RTH", D["rVW"], D["rVS"]), ("Session", D["sVW"], D["sVS"]), ("Woche", D["wVW"], D["wVS"]), ("Monat", D["mVW"], D["mVS"])):
            z = (C[:, t] - W[:, t]) / S[:, t]
            m = ok & np.isfinite(z) & np.isfinite(fwd) & (S[:, t] > 0)
            if m.sum() < 200:
                continue
            sgn = np.sign(z[m]); f = fwd[m] * sgn                    # + = weiter weg vom VWAP
            slope = np.polyfit(z[m], fwd[m], 1)[0]
            row = dict(Markt=mk, Uhrzeit=hhmm, VWAP=vname, Tage=int(m.sum()), **{"Ø weiter weg % ATR": round(100 * f.mean(), 2),
                       "t": round(f.mean() / (f.std() / np.sqrt(len(f))), 2), "Steigung % ATR je σ": round(100 * slope, 2)})
            cut = pd.cut(z[m], BINS)
            g = pd.Series(fwd[m]).groupby(cut, observed=True).agg(["mean", "size"])
            for iv, r in g.iterrows():
                row[f"z {iv}"] = f"{100 * r['mean']:+.1f} ({int(r['size'])})"
            rows.append(row)
    print(mk, flush=True)
X = pd.DataFrame(rows)
import os
suf = "_h10" if os.environ.get("VW_SPLIT") == "H10" else ""
X.to_csv(RES / f"vw_d_map{suf}.csv", index=False)
(RES / f"vw_d_map{suf}.md").write_text("# VWAP-Landkarte (Explore ≤ 2019)\n\n+ = Preis läuft bis RTH-Ende weiter vom VWAP weg (Trend), − = zurück (Mean Reversion). Werte in % der Tages-ATR; Zellen: Ø Rendite (Tage).\n\n" + X.to_markdown(index=False))
pd.set_option("display.width", 250)
print(X[["Markt", "Uhrzeit", "VWAP", "Tage", "Ø weiter weg % ATR", "t", "Steigung % ATR je σ"]].to_string(index=False))
