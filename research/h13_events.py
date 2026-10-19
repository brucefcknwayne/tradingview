"""
H13 – Event-Tage intraday, exakt nach Vorab-Registrierung. Ausgabe nur Explore (2011–2019); Trades aller Zeiträume gespeichert.
Event = Volumen der ersten 5 Minuten ab E ≥ R × Median derselben 5 Minuten der letzten 20 Tage.
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
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h13_cache"
CACHE.mkdir(parents=True, exist_ok=True)
EVENTS = {"08:30": 870, "10:00": 960, "14:00": 1200}       # Minuten seit 18:00
rows, evinfo = [], []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    O, H, L, C, V = D["O"], D["H"], D["L"], D["C"], D["V"]
    a, b = D["rth"]
    nan = np.full_like(C, np.nan); F = np.zeros_like(C, dtype=bool)
    for ev, E in EVENTS.items():
        if mk == "GC" and E >= b:
            continue
        v5 = np.nansum(V[:, E:E + 5], 1)
        med = pd.Series(np.where(D["day_ok"], v5, np.nan)).rolling(20, min_periods=15).median().shift(1).to_numpy()
        ratio = v5 / med
        pre = C[:, E - 1]
        for R in (4, 8):
            isev = D["day_ok"] & (ratio >= R)
            evinfo.append(dict(Markt=mk, Event=ev, R=R, **{"Event-Tage Explore": int((isev & (D["period"] == "Explore")).sum())}))
            for M, mode, ex in itertools.product((5, 15, 30), ("Fortsetzung", "Umkehr"), ("E+60", "E+120", "RTH-Ende")):
                t = E + M - 1
                flat = {"E+60": E + 60, "E+120": E + 120, "RTH-Ende": b - 1}[ex]
                if flat <= t + 1:
                    continue
                move = C[:, t] - pre
                up = isev & (move > 0); dn = isev & (move < 0)
                sl = F.copy(); ss = F.copy(); stL = nan.copy(); stS = nan.copy()
                with np.errstate(all="ignore"):
                    hiE = np.nanmax(H[:, E:t + 1], 1); loE = np.nanmin(L[:, E:t + 1], 1)
                if mode == "Fortsetzung":
                    sl[:, t] = up; ss[:, t] = dn
                    stL[:, t] = pre; stS[:, t] = pre
                else:
                    sl[:, t] = dn; ss[:, t] = up
                    stL[:, t] = loE; stS[:, t] = hiE
                T = run(O, H, L, C, sl, ss, stL, stS, nan, nan, F, F, t, t, flat, 1, COST[mk], D["day_ok"])
                name = f"{ev} R{R} M{M} {mode} {ex}"
                np.save(CACHE / f"{mk}_{name.replace(' ', '_').replace(':', '')}.npy", T)
                rows.append({"Markt": mk, "Event": ev, "R": R, "M": M, "Modus": mode, "Ausstieg": ex, **stats(T, D, USD[mk], "Explore")})
    print(mk, flush=True)
    del D
X = pd.DataFrame(rows); EI = pd.DataFrame(evinfo)
X.to_csv(RES / "h13_explore.csv", index=False); EI.to_csv(RES / "h13_eventdays.csv", index=False)
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 500)
print(EI.to_string(index=False))
print(X.groupby(["Event", "Modus", "Markt"])["EW Pkt"].median().round(3).unstack().to_string())
g = X[(X["EW Pkt"] > 0) & (X["PF"] >= 1.15)].sort_values("Sharpe Tag (ann.)", ascending=False)
print(g[["Markt", "Event", "R", "M", "Modus", "Ausstieg", "Trades", "EW Pkt", "Treffer %", "PF", "Max DD Pkt", "Sharpe Tag (ann.)", "Jahre pos"]].head(40).to_string(index=False))
