"""
H7 Teil C – Prüfung des einzigen Kandidaten mit Mechanismus, unverändert auf Validate (2025-01-01 … 2026-04-16):
RTY, Modus 1D, Vorlage fade2 (Limit am Level, Stop 0,25σ, Ziel 0,5σ zurück), nur Berührungen 18:00–24:00 ET, Zonen.
Ohne Überlappung (nächster Trade erst nach Ausstieg). Zufall: 1.000×, gleicher Stop/Ziel in Punkten, gleiche Stunde, anderer Tag.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import COST, NCOL, load_market  # noqa: E402
from gz_b_events import sim  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
mk, mode = "RTY", "1D"
E = pd.read_parquet(ROOT / f"data-lab/data/raw/gz_cache/gz_b_events_{mk}.parquet")
E = E[(E["Zeitraum"] == "Validate") & (E["Modus"] == mode) & (E["Art"] == "Zone")].copy()
E["uhr_et"] = (E["t"] + 1080) % 1440
E = E[(E["uhr_et"] >= 1080) & (E["uhr_et"] < 1440)].sort_values(["Tag", "t"])
M = load_market(mk)
days = pd.Index(M["days"]); H, L, C = M["G"]["high"], M["G"]["low"], M["G"]["close"]
di_all = days.get_indexer(E["Tag"])
sig = M["sig"][mode][di_all]
pn, sel, busy = [], [], (None, -1)
for (i, t, side, k, s) in zip(di_all, E["t"], E["Seite"], E["k"], sig):
    if busy[0] == i and t <= busy[1]:
        continue
    z = M["ref"][i] + side * k * s
    r, ex = sim(H, L, C, i, int(t), z, -side, 0.25 * s, 0.5 * s, NCOL - 1)
    pn.append((r - COST[mk]) / (0.25 * s)); sel.append((i, int(t), -side, 0.25 * s, 0.5 * s)); busy = (i, ex)
pn = np.array(pn)
# Zufall
rng = np.random.default_rng(7)
vdays = np.flatnonzero(np.array([str(p) == "Validate" for p in M["period"]]) & M["valid"])
R = np.empty((len(sel), 1000))
for j, (i, t, d, st, tg) in enumerate(sel):
    hr = t // 60
    for r_ in range(1000):
        while True:
            ii = vdays[rng.integers(len(vdays))]; tt = hr * 60 + rng.integers(60)
            if ii != i and tt < NCOL and np.isfinite(C[ii, tt]):
                break
        x, _ = sim(H, L, C, ii, tt, C[ii, tt], d, st, tg, NCOL - 1)
        R[j, r_] = (x - COST[mk]) / st
rm = R.mean(0)
boot = rng.choice(pn, (2000, len(pn))).mean(1)
p = (1 + (rm >= pn.mean()).sum()) / 1001
res = dict(Kandidat="RTY 1D fade2 Abend 18–24 Uhr", Trades=len(pn), Treffer=round((pn > 0).mean(), 3), EW_R=round(pn.mean(), 3),
           KI95=(round(np.percentile(boot, 2.5), 3), round(np.percentile(boot, 97.5), 3)), Zufall_EW_R=round(rm.mean(), 3), p=round(p, 4),
           Erfolg=bool(p < 0.05 and np.percentile(boot, 2.5) > 0 and pn.mean() > 0 and len(pn) >= 30))
print(res)
pd.DataFrame([res]).to_csv(ROOT / "research/results/gz_c_validate.csv", index=False)
