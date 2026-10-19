"""
H15 – LVN-Tests exakt nach Vorab-Registrierung (research/HYPOTHESEN.md).
Profil aus 1m-Daten (Volumen gleichmäßig auf die Buckets zwischen Tief und Hoch), RTH. P1 = Vortag, P5 = letzte 5 Sessions.
Aufruf: python research/h15_lvn.py → research/results/h15_*.csv/.md
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
START, SPLIT = pd.Timestamp("2021-10-18").date(), pd.Timestamp("2025-03-31").date()
RTH = {"NQ": (930, 1320), "ES": (930, 1320), "RTY": (930, 1320), "GC": (860, 1170)}
BS = {"NQ": 5.0, "ES": 1.0, "RTY": 0.5, "GC": 1.0}
PS = (0.35, 0.5, 0.7)
rng = np.random.default_rng(15)


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


@njit(cache=True)
def accel(H, L, C, a, b, lvl, bs, r, ups, dns):
    """Erster Close ≥ 1 Bucket jenseits des Levels (von der Startseite aus) → nächstes HVN erreicht vor Rückfall um r?
    Rückgabe (erfolg 1/0/−1, Minuten, Distanz)."""
    side0 = 0
    for t in range(a, b):
        if np.isnan(C[t]):
            continue
        if side0 == 0:
            side0 = 1 if C[t] > lvl else -1
            continue
        crossed = (side0 == 1 and C[t] <= lvl - bs) or (side0 == -1 and C[t] >= lvl + bs)
        if crossed:
            d = -side0
            tgt = np.nan
            if d == 1:
                for x in ups:
                    if x > C[t] and (np.isnan(tgt) or x < tgt):
                        tgt = x
            else:
                for x in dns:
                    if x < C[t] and (np.isnan(tgt) or x > tgt):
                        tgt = x
            if np.isnan(tgt):
                return -1, 0, 0.0
            for k in range(t + 1, b):
                if np.isnan(H[k]):
                    continue
                if (d == 1 and L[k] <= lvl - r) or (d == -1 and H[k] >= lvl + r):
                    return 0, k - t, abs(tgt - C[t])
                if (d == 1 and H[k] >= tgt) or (d == -1 and L[k] <= tgt):
                    return 1, k - t, abs(tgt - C[t])
            return -1, 0, 0.0
    return -1, 0, 0.0


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


def ztest(a1, n1, a2, n2):
    if min(n1, n2) < 30:
        return np.nan
    p = (a1 + a2) / (n1 + n2); se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return np.nan
    z = (a1 / n1 - a2 / n2) / se
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


ev1, ev2 = [], []
for mk in ["NQ", "ES", "RTY", "GC"]:
    M = load_market(mk)
    G = M["G"]; H, L, C, V = G["high"], G["low"], G["cff"], G["volume"]
    a, b = RTH[mk]; bs = BS[mk]; days = M["days"]; sym = M["symbol"]
    atr = pd.Series(np.where(M["valid"], M["H"] - M["L"], np.nan)).rolling(14, min_periods=10).mean().shift(1).to_numpy()
    # RTH-VWAP ±σ (Wert der Vorminute bei Berührung)
    tp = (H + L + G["close"]) / 3; vv = np.where(np.isfinite(V) & np.isfinite(tp), V, 0.0); tpz = np.nan_to_num(tp)
    cv = np.cumsum(vv[:, a:b], 1); cpv = np.cumsum((tpz * vv)[:, a:b], 1); cp2 = np.cumsum((tpz * tpz * vv)[:, a:b], 1)
    with np.errstate(all="ignore"):
        VW = cpv / cv; VS = np.sqrt(np.maximum(cp2 / cv - VW ** 2, 0))
    profs = [day_profile(H[i], L[i], V[i], a, b, bs) for i in range(len(days))]
    first = int(np.searchsorted(days, START))
    for e in range(max(first, 6), len(days)):
        if not M["valid"][e] or not np.isfinite(atr[e]):
            continue
        per = "A" if days[e] <= SPLIT else "B"
        r = 0.1 * atr[e]
        for pname, lb in (("P1", 1), ("P5", 5)):
            idx = [d for d in range(e - lb, e) if sym[d] == sym[e] and profs[d][0] >= 0 and M["valid"][d]]
            if len(idx) < max(1, lb - 2):
                continue
            i0 = min(profs[d][0] for d in idx); i1 = max(profs[d][0] + len(profs[d][1]) for d in idx)
            prof = np.zeros(i1 - i0)
            for d in idx:
                o = profs[d][0] - i0; prof[o:o + len(profs[d][1])] += profs[d][1]
            for p in PS:
                lv, hv = nodes(prof, p)
                if not lv:
                    continue
                hv_px = np.array([(i0 + i + 0.5) * bs for i in hv])
                ups, dns = hv_px, hv_px
                taken = set()
                for i in lv + hv:
                    taken.update(range(i - 2, i + 3))
                free = [i for i in range(3, len(prof) - 3) if i not in taken]
                ctrl = list(rng.choice(free, size=min(len(lv), len(free)), replace=False)) if free else []
                for kind, ix in (("LVN", lv), ("HVN", hv), ("Kontrolle", ctrl)):
                    for i in ix:
                        lvl = (i0 + i + 0.5) * bs
                        t, side, res = race(H[e], L[e], C[e], a, b, lvl, r)
                        if t >= 0 and res >= 0:
                            vw, vs = VW[e, max(t - a - 1, 0)], VS[e, max(t - a - 1, 0)]
                            band = np.isfinite(vs) and vs > 0 and min(abs(lvl - (vw + 2 * vs)), abs(lvl - (vw - 2 * vs))) <= 0.1 * vs
                            ev1.append((mk, pname, p, per, kind, res, band))
                        if kind != "HVN":
                            ok, mins, dist = accel(H[e], L[e], C[e], a, b, lvl, bs, r, ups, dns)
                            if ok >= 0:
                                ev2.append((mk, pname, p, per, kind, ok, mins, dist))
    print(mk, "fertig", flush=True)

E1 = pd.DataFrame(ev1, columns=["Markt", "Profil", "p", "Teil", "Art", "Abprall", "am_Band"])
E2 = pd.DataFrame(ev2, columns=["Markt", "Profil", "p", "Teil", "Art", "erreicht", "Minuten", "Distanz"])
_C = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h15_cache"; _C.mkdir(parents=True, exist_ok=True)
E1.to_parquet(_C / "e1.parquet"); E2.to_parquet(_C / "e2.parquet")
rows = []
for (mk, pf, p), g in E1.groupby(["Markt", "Profil", "p"]):
    for test, sub in (("1 Wand", g), ("3 Wand am VWAP-±2σ-Band", g[g["am_Band"]])):
        l, c, h = sub[sub["Art"] == "LVN"], sub[sub["Art"] == "Kontrolle"], sub[sub["Art"] == "HVN"]
        row = dict(Markt=mk, Profil=pf, Prominenz=p, Test=test, n_LVN=len(l), n_Kontrolle=len(c),
                   **{"LVN Abprall %": round(100 * l["Abprall"].mean(), 1) if len(l) else np.nan,
                      "Kontrolle Abprall %": round(100 * c["Abprall"].mean(), 1) if len(c) else np.nan,
                      "HVN Abprall %": round(100 * h["Abprall"].mean(), 1) if len(h) else np.nan,
                      "LVN−Kontrolle A": round(100 * (l[l.Teil == "A"]["Abprall"].mean() - c[c.Teil == "A"]["Abprall"].mean()), 1),
                      "LVN−Kontrolle B": round(100 * (l[l.Teil == "B"]["Abprall"].mean() - c[c.Teil == "B"]["Abprall"].mean()), 1),
                      "p": ztest(l["Abprall"].sum(), len(l), c["Abprall"].sum(), len(c))})
        rows.append(row)
for (mk, pf, p), g in E2.groupby(["Markt", "Profil", "p"]):
    l, c = g[g["Art"] == "LVN"], g[g["Art"] == "Kontrolle"]
    spd = lambda x: (x["Distanz"] / x["Minuten"].clip(lower=1))[x["erreicht"] == 1].median()  # noqa: E731
    rows.append(dict(Markt=mk, Profil=pf, Prominenz=p, Test="2 Beschleuniger (HVN erreicht)", n_LVN=len(l), n_Kontrolle=len(c),
                     **{"LVN Abprall %": round(100 * l["erreicht"].mean(), 1), "Kontrolle Abprall %": round(100 * c["erreicht"].mean(), 1),
                        "HVN Abprall %": np.nan,
                        "LVN−Kontrolle A": round(100 * (l[l.Teil == "A"]["erreicht"].mean() - c[c.Teil == "A"]["erreicht"].mean()), 1),
                        "LVN−Kontrolle B": round(100 * (l[l.Teil == "B"]["erreicht"].mean() - c[c.Teil == "B"]["erreicht"].mean()), 1),
                        "p": ztest(l["erreicht"].sum(), len(l), c["erreicht"].sum(), len(c)),
                        "Tempo LVN Pkt/Min": round(spd(l), 2), "Tempo Kontrolle Pkt/Min": round(spd(c), 2)}))
X = pd.DataFrame(rows)
pv = X["p"].to_numpy(float); ok = np.isfinite(pv); adj = np.full(len(pv), np.nan)
o = np.argsort(pv[ok]); m = ok.sum(); run_, tmp = 0.0, np.empty(m)
for rk, i in enumerate(o):
    run_ = max(run_, (m - rk) * pv[ok][i]); tmp[i] = min(run_, 1.0)
adj[ok] = tmp
X["p Holm"] = np.round(adj, 4); X["p"] = X["p"].round(4)
X.to_csv(RES / "h15_lvn.csv", index=False)
md = ["# H15 – LVN-Tests (2021-10-18 bis 2026-04-16, Holdout unberührt)", "",
      "Test 1/3: Abprall-Quote bei erster Berührung (Rennen ±0,1 ATR). Test 2: Anteil, der nach Durchbruch das nächste HVN erreicht, bevor er 0,1 ATR zurückfällt.",
      "„LVN−Kontrolle A/B“ = Unterschied in Prozentpunkten in Teil A (bis 03/2025) und B (danach).", "", X.to_markdown(index=False)]
(RES / "h15_lvn.md").write_text("\n".join(md))
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)
print(X.to_string(index=False))
