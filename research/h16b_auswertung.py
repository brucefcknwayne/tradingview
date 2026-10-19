"""
H16b – Auswertung: Teil A (Ausdehnung nach Erstausbruch) aus dem Cache, Prüfung der Explore-Kandidaten auf Validate/Test.
Aufruf nach h16b_orb_deep.py: python research/h16b_auswertung.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, load  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h16b_cache"
LAST5 = pd.Timestamp("2021-10-18")
KS = (0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3)
TGN = ["0.1", "0.25", "0.5", "0.75", "1", "1.5", "2", "Ende"]
SG = [0.25, 0.5, 1.0, 1.5]

A = pd.read_parquet(CACHE / "h16b_A.parquet")
A["Tag"] = pd.to_datetime(A["Tag"])
B = A[A["brk"].isin([1, -1])].copy()
B["mfe_pkt"] = B["mfe"] * B["R_pkt"]; B["mfe_atr"] = 100 * B["mfe_pkt"] / B["atr"]


def agg(g, base):
    r = {"Tage": len(base), "Ausbruch %": round(100 * len(g) / max(len(base), 1), 1), "Ø OR Pkt": round(g["R_pkt"].mean(), 1)}
    for q in (10, 25, 50, 75, 90):
        r[f"MFE q{q} ×OR"] = round(np.percentile(g["mfe"], q), 2)
    r["MFE Median Pkt"] = round(g["mfe_pkt"].median(), 1); r["MFE Median % ATR"] = round(g["mfe_atr"].median(), 1)
    for k in KS:
        r[f"≥{k}×"] = round(100 * (g["mfe"] >= k).mean(), 1)
    for k in (0.5, 1, 2):
        r[f"vor Fehl ≥{k}×"] = round(100 * (g["mfe_pre"] >= k).mean(), 1)
    r["Fehlausbruch %"] = round(100 * g["fail"].mean(), 1)
    r["Schluss jenseits %"] = round(100 * g["close_beyond"].mean(), 1)
    for k1, k2 in ((0.25, 0.5), (0.5, 1), (1, 1.5), (1, 2), (2, 3)):
        x = g[g["mfe"] >= k1]; r[f"P({k2}|{k1})"] = round(100 * (x["mfe"] >= k2).mean(), 1) if len(x) else np.nan
    r["Min. bis MFE Median"] = float(g["tmfe"].median())
    r["MFE in 1. Stunde RTH %"] = round(100 * (g["clock_mfe"] < 60).mean(), 1)
    r["MFE in letzter Stunde %"] = round(100 * (g["clock_mfe"] >= 330).mean(), 1)
    r["Rücksetzer vor MFE Median ×OR"] = round(g["pull"].median(), 2)
    r["Retest Kante vor +0,5 %"] = round(100 * g["retest_vor_0.5"].mean(), 1)
    for k in (0.25, 0.5, 1.0):
        x = g[f"race_{k}"].dropna()
        p = st.binomtest(int(x.sum()), len(x), 0.5).pvalue if len(x) else np.nan
        r[f"+{k} vor −{k} %"] = round(100 * x.mean(), 1); r[f"p({k})"] = round(p, 4)
    s2 = g["mfe2"].dropna()
    r["2. Ausbruch n"] = len(s2)
    r["2. Ausbruch MFE Median ×OR"] = round(s2.median(), 2) if len(s2) else np.nan
    r["2. Ausbruch ≥1× %"] = round(100 * (s2 >= 1).mean(), 1) if len(s2) else np.nan
    return r


rows, cond, yrs = [], [], []
for (mk, m), g in B.groupby(["Markt", "OR"]):
    base_all = A[(A["Markt"] == mk) & (A["OR"] == m)]
    for pname, sel in (("2011–04/2026", lambda x: np.ones(len(x), bool)), ("letzte 5 J.", lambda x: x["Tag"] >= LAST5),
                       ("Explore", lambda x: x["Zeitraum"] == "Explore"), ("Validate", lambda x: x["Zeitraum"] == "Validate"),
                       ("Test", lambda x: x["Zeitraum"] == "Test")):
        rows.append(dict(Markt=mk, OR=m, Zeitraum=pname, **agg(g[sel(g)], base_all[sel(base_all)])))
    # Bedingungen (2011–04/2026): OR/ATR-Terzil, Ausbruchszeit
    ratio = g["R_pkt"] / g["atr"]
    terz = pd.qcut(ratio, 3, labels=["eng", "mittel", "weit"])
    tb = pd.cut(g["tmin"], [-1, 5, 30, 90, 1000], labels=["≤5 Min", "6–30 Min", "31–90 Min", ">90 Min"])
    for lab, grp in (("OR/ATR", terz), ("Ausbruch nach OR-Ende", tb)):
        for v, x in g.groupby(grp, observed=True):
            r = agg(x, x)
            cond.append(dict(Markt=mk, OR=m, Merkmal=lab, Wert=str(v), n=len(x), **{k: r[k] for k in
                        ("Ø OR Pkt", "MFE q50 ×OR", "MFE Median Pkt", "≥0.5×", "≥1×", "≥2×", "Fehlausbruch %", "+0.5 vor −0.5 %", "p(0.5)")}))
    for y, x in g.groupby(g["Tag"].dt.year):
        yrs.append(dict(Markt=mk, OR=m, Jahr=y, n=len(x), **{"MFE Median ×OR": round(x["mfe"].median(), 2), "≥1× %": round(100 * (x["mfe"] >= 1).mean(), 1),
                    "Fehlausbruch %": round(100 * x["fail"].mean(), 1), "+0.5 vor −0.5 %": round(100 * x["race_0.5"].mean(), 1)}))
X = pd.DataFrame(rows); X.to_csv(RES / "h16b_ausdehnung.csv", index=False)
Cd = pd.DataFrame(cond); Cd.to_csv(RES / "h16b_bedingungen.csv", index=False)
Y = pd.DataFrame(yrs); Y.to_csv(RES / "h16b_jahre.csv", index=False)
pd.set_option("display.width", 320); pd.set_option("display.max_columns", 60); pd.set_option("display.max_rows", 400)
print(X[X["Zeitraum"] == "2011–04/2026"].T.to_string())
print(X[X["Zeitraum"] == "letzte 5 J."][["Markt", "OR", "MFE q50 ×OR", "MFE Median Pkt", "≥0.5×", "≥1×", "≥2×", "Fehlausbruch %", "+0.25 vor −0.25 %", "+0.5 vor −0.5 %", "+1.0 vor −1.0 %"]].to_string(index=False))
print(Cd.to_string(index=False))

# ───────── Prüfung der Kandidaten ─────────
K = pd.read_csv(RES / "h16b_kandidaten.csv") if (RES / "h16b_kandidaten.csv").stat().st_size > 5 else pd.DataFrame()
if len(K):
    out = []
    Ds = {}
    for _, k in K.iterrows():
        mk = k["Markt"]
        if mk not in Ds:
            Ds[mk] = load(mk)
        D = Ds[mk]; per = D["period"]
        arr = np.load(CACHE / f"{mk}_OR{int(k['OR'])}_{k['Einstieg']}_pess.npy")
        dd = np.load(CACHE / f"{mk}_OR{int(k['OR'])}_{k['Einstieg']}_d.npy")
        ti, si = TGN.index(str(k["T"]).replace(".0", "") if str(k["T"]) not in TGN else str(k["T"])), SG.index(float(k["S"]))
        pnl, opp, risk, oc = arr[ti * len(SG) + si]
        fm = np.ones(len(dd), bool)
        if k["Quelle"] == "C":
            raise SystemExit("Filter-Kandidat: Filtermaske nachbauen (siehe h16b_orb_deep.py Teil C)")
        for pname in ("Validate", "Test"):
            ok = (per[dd] == pname) & fm & np.isfinite(pnl)
            p, o = pnl[ok], opp[ok]
            daily = pd.Series(p).groupby(dd[ok]).sum().to_numpy()
            rng = np.random.default_rng(0)
            bs = np.array([rng.choice(daily, len(daily)).mean() for _ in range(5000)])
            w, l = p[p > 0].sum(), -p[p <= 0].sum()
            out.append(dict(Kandidat=f"{mk} OR{int(k['OR'])} {k['Einstieg']} T{k['T']} S{k['S']}", Zeitraum=pname, Trades=int(ok.sum()),
                            **{"EW Pkt": round(p.mean(), 3), "KI 2,5 % (Tag)": round(np.percentile(bs, 2.5), 3), "PF": round(w / l, 3),
                               "p (t, einseitig)": st.ttest_1samp(daily, 0, alternative="greater").pvalue,
                               "p Signal > Gegenrichtung": st.ttest_rel(p, o, alternative="greater").pvalue}))
    V = pd.DataFrame(out)
    for pname in ("Validate", "Test"):
        mm = V["Zeitraum"] == pname
        ps = V.loc[mm, "p (t, einseitig)"].to_numpy(); order = np.argsort(ps); adj = np.empty_like(ps); run = 0
        for i, j in enumerate(order):
            run = max(run, min(1, (len(ps) - i) * ps[j])); adj[j] = run
        V.loc[mm, "Holm p"] = adj
    V.to_csv(RES / "h16b_pruefung.csv", index=False)
    print(V.to_string(index=False))
