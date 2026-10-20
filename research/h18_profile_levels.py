"""
H18 – LVN + Single Prints + VAH/VAL (Vortages-RTH-Profil, 30-Min-TPO), exakt nach Vorab-Registrierung (HYPOTHESEN.md).
Aufruf: python research/h18_profile_levels.py → research/results/h18_*.csv
"""
import sys
from math import erf, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import load_market  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h18_cache"
CACHE.mkdir(parents=True, exist_ok=True)
RTH = {"NQ": (930, 1320), "ES": (930, 1320), "RTY": (930, 1320), "GC": (860, 1170)}
BS = {"NQ": 5.0, "ES": 1.0, "RTY": 0.5, "GC": 1.0}
RS = (0.1, 0.25)
import os
BSMODE = os.environ.get("H18_BS", "fix")   # "fix" = vorab registriert; "atr" = Bucket = ATR14/80 (Nachtrag: fix ist 2011–15 zu grob)
TICKS = {"NQ": 0.25, "ES": 0.25, "RTY": 0.1, "GC": 0.1}
TOL = 2
FAMS = ["VAH", "VAL", "LVN", "SP", "LVN+SP", "LVN+VA", "SP+VA", "LVN+SP+VA"]
rng = np.random.default_rng(18)


# ── aus h15_lvn.py übernommen (dort ohne main-Guard) ──
@njit(cache=True)
def day_profile(H, L, V, a, b, bs):
    lo = 1e18; hi = -1e18
    for t in range(a, b):
        if not np.isnan(H[t]) and not np.isnan(V[t]):
            lo = min(lo, L[t]); hi = max(hi, H[t])
    if hi < lo:
        return -1, np.zeros(0)
    i0 = int(np.floor(lo / bs)); i1 = int(np.floor(hi / bs))
    prof = np.zeros(i1 - i0 + 1)
    for t in range(a, b):
        if np.isnan(H[t]) or np.isnan(V[t]) or V[t] <= 0:
            continue
        j0 = int(np.floor(L[t] / bs)) - i0; j1 = int(np.floor(H[t] / bs)) - i0
        share = V[t] / (j1 - j0 + 1)
        for j in range(j0, j1 + 1):
            prof[j] += share
    return i0, prof


@njit(cache=True)
def race(H, L, C, a, b, lvl, r):
    """Erste Berührung in [a,b): Rückgabe (Minute, Seite +1 von oben/−1 von unten, Abprall 1/0/−1 offen)."""
    for t in range(a, b):
        if np.isnan(H[t]):
            continue
        if L[t] <= lvl <= H[t]:
            pc = C[t - 1]
            if np.isnan(pc) or pc == lvl:
                return t, 0, -1
            side = 1 if pc > lvl else -1
            for k in range(t, b):
                if np.isnan(H[k]):
                    continue
                thru = (L[k] <= lvl - r) if side == 1 else (H[k] >= lvl + r)
                if thru:
                    return t, side, 0
                if k > t:
                    away = (H[k] >= lvl + r) if side == 1 else (L[k] <= lvl - r)
                    if away:
                        return t, side, 1
            return t, side, -1
    return -1, 0, -1


def nodes(prof, p):
    s = pd.Series(prof).rolling(3, center=True, min_periods=1).mean().to_numpy()
    n = len(s); lvn, hvn = [], []
    mean = s.mean()
    for i in range(3, n - 3):
        w = s[i - 3:i + 4]
        if s[i] == w.min() and s[i] < w.max():
            lp = s[max(0, i - 15):i].max(); rp = s[i + 1:i + 16].max()
            if s[i] <= p * min(lp, rp):
                lvn.append(i)
        if s[i] == w.max() and s[i] >= mean:
            hvn.append(i)
    # benachbarte Duplikate (Plateaus) zusammenfassen
    def dedup(ix):
        out = []
        for i in ix:
            if not out or i - out[-1] > 2:
                out.append(i)
        return out
    return dedup(lvn), dedup(hvn)




@njit(cache=True)
def tpo_profile(H, L, a, b, bs, i0, n, per):
    cnt = np.zeros(n)
    t = a
    while t < b:
        lo = 1e18; hi = -1e18
        for k in range(t, min(t + per, b)):
            if not np.isnan(H[k]):
                lo = min(lo, L[k]); hi = max(hi, H[k])
        if hi >= lo:
            j0 = max(0, int(np.floor(lo / bs)) - i0); j1 = min(n - 1, int(np.floor(hi / bs)) - i0)
            for j in range(j0, j1 + 1):
                cnt[j] += 1
        t += per
    return cnt


def value_area(prof):
    tot = prof.sum(); poc = int(np.argmax(prof)); lo = hi = poc; s = prof[poc]
    while s < 0.7 * tot and (lo > 0 or hi < len(prof) - 1):
        up = prof[hi + 1] if hi < len(prof) - 1 else -1
        dn = prof[lo - 1] if lo > 0 else -1
        if up >= dn:
            hi += 1; s += up
        else:
            lo -= 1; s += dn
    return lo, hi


def single_prints(cnt):
    runs, n, i = [], len(cnt), 0
    while i < n:
        if cnt[i] == 1:
            j = i
            while j + 1 < n and cnt[j + 1] == 1:
                j += 1
            if j - i + 1 >= 2 and i > 0 and j < n - 1:
                runs.append((i, j))
            i = j + 1
        else:
            i += 1
    return runs


def ztest(a1, n1, a2, n2):
    if min(n1, n2) < 30:
        return np.nan
    p = (a1 + a2) / (n1 + n2); se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return np.nan
    z = (a1 / n1 - a2 / n2) / se
    return 1 - 0.5 * (1 + erf(z / sqrt(2)))          # einseitig: Level > Kontrolle


ev = []
for mk in ["NQ", "ES", "RTY", "GC"]:
    M = load_market(mk)
    G = M["G"]; H, L, C, V = G["high"], G["low"], G["cff"], G["volume"]
    a, b = RTH[mk]; bs = BS[mk]; days = M["days"]; sym = M["symbol"]; dts = pd.to_datetime(days)
    atr = pd.Series(np.where(M["valid"], M["H"] - M["L"], np.nan)).rolling(14, min_periods=10).mean().shift(1).to_numpy()
    period = np.where(dts.year <= 2019, "Explore", np.where(dts.year <= 2024, "Validate", "Test"))
    for e in range(1, len(days)):
        d = e - 1
        if not (M["valid"][e] and M["valid"][d] and sym[d] == sym[e] and np.isfinite(atr[e])):
            continue
        if (dts[e] - dts[d]).days > 4:
            continue
        if BSMODE == "atr":
            bs = max(TICKS[mk], round(atr[e] / 80 / TICKS[mk]) * TICKS[mk])
        i0, prof = day_profile(H[d], L[d], V[d], a, b, bs)
        if i0 < 0 or len(prof) < 12 or prof.sum() <= 0:
            continue
        n = len(prof)
        cnt = tpo_profile(H[d], L[d], a, b, bs, i0, n, 30)
        px = lambda i: (i0 + i) * bs  # noqa: E731  Unterkante von Bucket i
        vlo, vhi = value_area(prof)
        vah, val = px(vhi + 1), px(vlo)
        lv, _ = nodes(prof, 0.5)
        lv_px = [px(i) + 0.5 * bs for i in lv]
        sp = single_prints(cnt)
        sp_edges = [px(j + 1) for i, j in sp] + [px(i) for i, j in sp]
        tol = TOL * bs
        in_sp = lambda x: any(px(i) - tol <= x <= px(j + 1) + tol for i, j in sp)  # noqa: E731
        near = lambda x, arr: any(abs(x - y) <= tol for y in arr)  # noqa: E731
        lev = {"VAH": [vah], "VAL": [val], "LVN": lv_px, "SP": sp_edges,
               "LVN+SP": [x for x in lv_px if in_sp(x)],
               "LVN+VA": [x for x in (vah, val) if near(x, lv_px)],
               "SP+VA": [x for x in (vah, val) if near(x, sp_edges) or in_sp(x)],
               "LVN+SP+VA": [x for x in (vah, val) if near(x, lv_px) and (near(x, sp_edges) or in_sp(x))]}
        all_lv = [x for v in lev.values() for x in v]
        lo_p, hi_p = px(0), px(n)
        for fam, xs in lev.items():
            for x in xs:
                # Kontrolle: um 3…8 Buckets verschoben, ≥ 2 Buckets von allen Levels, im Profil
                ctrl = np.nan
                for _ in range(20):
                    c = x + rng.choice([-1, 1]) * rng.integers(3, 9) * bs
                    if lo_p < c < hi_p and all(abs(c - y) >= 2 * bs for y in all_lv):
                        ctrl = c; break
                for r in RS:
                    for kind, lvl in (("Level", x), ("Kontrolle", ctrl)):
                        if not np.isfinite(lvl):
                            continue
                        t, side, res = race(H[e], L[e], C[e], a, b, lvl, r * atr[e])
                        if t >= 0 and res >= 0:
                            ev.append((mk, dts[e], period[e], fam, r, kind, res, t - a, lvl))
    print(mk, "fertig", flush=True)
    del M, G

E = pd.DataFrame(ev, columns=["Markt", "Tag", "Zeitraum", "Familie", "r", "Art", "Abprall", "Minute", "Preis"])
E.to_parquet(CACHE / f"events_{BSMODE}.parquet")
rows = []
for (mk, fam, r), g in E.groupby(["Markt", "Familie", "r"]):
    row = dict(Markt=mk, Familie=fam, r=r)
    for pn in ("Explore", "Validate", "Test", "alle"):
        s = g if pn == "alle" else g[g["Zeitraum"] == pn]
        l, c = s[s["Art"] == "Level"], s[s["Art"] == "Kontrolle"]
        row[f"{pn} n"] = len(l)
        row[f"{pn} Level %"] = round(100 * l["Abprall"].mean(), 1) if len(l) else np.nan
        row[f"{pn} Kontrolle %"] = round(100 * c["Abprall"].mean(), 1) if len(c) else np.nan
        row[f"{pn} Diff"] = round(row[f"{pn} Level %"] - row[f"{pn} Kontrolle %"], 1) if len(l) and len(c) else np.nan
        row[f"{pn} p"] = ztest(l["Abprall"].sum(), len(l), c["Abprall"].sum(), len(c))
    rows.append(row)
X = pd.DataFrame(rows)
ps = X["alle p"].fillna(1).to_numpy(); order = np.argsort(ps); adj = np.empty_like(ps); run = 0
for i, j in enumerate(order):
    run = max(run, min(1, (len(ps) - i) * ps[j])); adj[j] = run
X["Holm p (alle)"] = adj
X["alle 3 Zeiträume besser"] = (X["Explore Diff"] > 0) & (X["Validate Diff"] > 0) & (X["Test Diff"] > 0)
X.to_csv(RES / f"h18_wand_{BSMODE}.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_rows", 200); pd.set_option("display.max_columns", 40)
print(X[["Markt", "Familie", "r", "alle n", "alle Level %", "alle Kontrolle %", "alle Diff", "Explore Diff", "Validate Diff", "Test Diff",
         "Holm p (alle)", "alle 3 Zeiträume besser"]].to_string(index=False))
