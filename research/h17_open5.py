"""
H17 – 5-Min-Open-Kerze als Tages-Bias, exakt nach Vorab-Registrierung (HYPOTHESEN.md).
Aufruf: python research/h17_open5.py → research/results/h17_*.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, load  # noqa: E402

RES = Path(__file__).parent / "results"
LAST5 = pd.Timestamp("2021-10-20")
rng = np.random.default_rng(0)


def boot_ci(x, n=4000):
    m = np.array([rng.choice(x, len(x)).mean() for _ in range(n)])
    return np.percentile(m, 2.5), np.percentile(m, 97.5)


def summ(s, ret, atr, cost, mask):
    ok = mask & np.isfinite(s) & (s != 0) & np.isfinite(ret) & np.isfinite(atr)
    if ok.sum() < 30:
        return None
    x = s[ok] * ret[ok]; xa = 100 * x / atr[ok]
    up = ret[ok] > 0; g = s[ok] > 0
    lo, hi = boot_ci(xa)
    return {"Tage": int(ok.sum()), "grün %": round(100 * g.mean(), 1),
            "P(steigt|grün) %": round(100 * up[g].mean(), 1), "P(steigt|rot) %": round(100 * up[~g].mean(), 1),
            "Differenz Pkt-%": round(100 * (up[g].mean() - up[~g].mean()), 1),
            "Richtung getroffen %": round(100 * (np.sign(ret[ok]) == s[ok]).mean(), 1),
            "EW % ATR": round(xa.mean(), 2), "KI 2,5 %": round(lo, 2), "KI 97,5 %": round(hi, 2),
            "p (einseitig)": st.ttest_1samp(xa, 0, alternative="greater").pvalue,
            "EW Pkt brutto": round(x.mean(), 2), "EW Pkt netto": round(x.mean() - cost, 2)}


main, ctrl, desc, yrs = [], [], [], []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    O, H, L, C = D["O"], D["H"], D["L"], D["C"]
    a, b = D["rth"]; atr = D["atr"]; ok = D["day_ok"]
    dts = pd.to_datetime(D["days"]); per = D["period"]
    pers = {"Explore": per == "Explore", "Validate": per == "Validate", "Test": per == "Test", "letzte 5 J.": dts >= LAST5, "alle": np.ones(D["n"], bool)}
    s5 = np.sign(C[:, a + 4] - O[:, a]); s5[~ok] = 0
    e0 = O[:, a + 5]
    hz = {"10:00": a + 29, "10:30": a + 59, "11:00": a + 89, "12:00": a + 149, "14:00": a + 269, "RTH-Ende": b - 1}
    for hn, hi in hz.items():
        if hi >= b:
            continue
        ret = C[:, hi] - e0
        for pn, pm in pers.items():
            r = summ(s5, ret, atr, COST[mk], pm)
            if r:
                main.append(dict(Markt=mk, Horizont=hn, Zeitraum=pn, **r))
    # Kontrollen: andere 5-Min-Kerzen, andere Eröffnungslängen (Rest bis RTH-Ende)
    for name, t0, t1 in [("5m 10:00", a + 30, a + 34), ("5m 10:30", a + 60, a + 64), ("5m 11:00", a + 90, a + 94), ("5m 13:00", a + 210, a + 214),
                         ("1m 09:30", a, a), ("15m 09:30", a, a + 14), ("30m 09:30", a, a + 29)]:
        if t1 + 1 >= b:
            continue
        s = np.sign(C[:, t1] - O[:, t0]); s[~ok] = 0
        ret = C[:, b - 1] - O[:, t1 + 1]
        for pn in ("Explore", "Validate", "Test", "alle"):
            r = summ(s, ret, atr, COST[mk], pers[pn])
            if r:
                ctrl.append(dict(Markt=mk, Kerze=name, Zeitraum=pn, **r))
    # Beschreibend (alle Zeiträume)
    ret = C[:, b - 1] - e0
    body = np.abs(C[:, a + 4] - O[:, a]) / atr
    v = ok & (s5 != 0) & np.isfinite(ret) & np.isfinite(body)
    q = pd.qcut(body[v], 5, labels=["Q1 klein", "Q2", "Q3", "Q4", "Q5 groß"])
    for lab in q.categories:
        m = np.zeros(D["n"], bool); m[np.flatnonzero(v)[q == lab]] = True
        r = summ(s5, ret, atr, COST[mk], m)
        desc.append(dict(Markt=mk, Merkmal="Kerzengröße", Wert=str(lab), **r))
    # nachträglich (nicht vorab registriert): Kerzengröße je Zeitraum, Quintil-Grenzen nur aus Explore
    qb = np.nanpercentile(body[v & pers["Explore"]], [20, 40, 60, 80])
    qi = np.digitize(body, qb)
    for k_, lab in enumerate(["Q1 klein", "Q2", "Q3", "Q4", "Q5 groß"]):
        for pn in ("Explore", "Validate", "Test", "letzte 5 J."):
            r = summ(s5, ret, atr, COST[mk], v & (qi == k_) & pers[pn])
            if r:
                desc.append(dict(Markt=mk, Merkmal=f"Kerzengröße {pn}", Wert=lab, **r))
    prev_c = np.r_[np.nan, C[:-1, b - 1]]
    gap = np.sign(O[:, a] - prev_c)
    for lab, m in (("mit Gap", gap == s5), ("gegen Gap", gap == -s5)):
        r = summ(s5, ret, atr, COST[mk], m & v)
        desc.append(dict(Markt=mk, Merkmal="Gap", Wert=lab, **r))
    # Tages-Extrem in den ersten 5 Min. (RTH)
    with np.errstate(all="ignore"):
        rH, rL = np.nanmax(H[:, a:b], 1), np.nanmin(L[:, a:b], 1)
        h5, l5 = np.nanmax(H[:, a:a + 5], 1), np.nanmin(L[:, a:a + 5], 1)
        # MFE ab 09:35 in/gegen Kerzenrichtung
        upx = np.nanmax(H[:, a + 5:b], 1) - e0; dnx = e0 - np.nanmin(L[:, a + 5:b], 1)
    for col, sg in (("grün", 1), ("rot", -1)):
        m = v & (s5 == sg)
        desc.append(dict(Markt=mk, Merkmal="RTH-Tief in ersten 5 Min. %", Wert=col, Tage=int(m.sum()), **{"EW % ATR": round(100 * np.mean(l5[m] <= rL[m]), 1)}))
        desc.append(dict(Markt=mk, Merkmal="RTH-Hoch in ersten 5 Min. %", Wert=col, Tage=int(m.sum()), **{"EW % ATR": round(100 * np.mean(h5[m] >= rH[m]), 1)}))
    mfe_with = np.where(s5 == 1, upx, dnx); mfe_ag = np.where(s5 == 1, dnx, upx)
    desc.append(dict(Markt=mk, Merkmal="MFE mit − gegen Kerze (% ATR)", Wert="alle", Tage=int(v.sum()),
                     **{"EW % ATR": round(100 * np.nanmean((mfe_with - mfe_ag)[v] / atr[v]), 2)}))
    for y in sorted(set(dts.year)):
        r = summ(s5, ret, atr, COST[mk], dts.year == y)
        if r:
            yrs.append(dict(Markt=mk, Jahr=y, **{k: r[k] for k in ("Tage", "Differenz Pkt-%", "EW % ATR", "EW Pkt brutto")}))
    print(mk, flush=True)
    del D

M = pd.DataFrame(main); Cn = pd.DataFrame(ctrl); De = pd.DataFrame(desc); Y = pd.DataFrame(yrs)
# Holm über 4 Märkte je Zeitraum (Haupttest RTH-Ende)
M["Holm p"] = np.nan
for pn in ("Explore", "Validate", "Test"):
    mm = (M["Horizont"] == "RTH-Ende") & (M["Zeitraum"] == pn)
    ps = M.loc[mm, "p (einseitig)"].to_numpy(); order = np.argsort(ps); adj = np.empty_like(ps); run = 0
    for i, j in enumerate(order):
        run = max(run, min(1, (len(ps) - i) * ps[j])); adj[j] = run
    M.loc[mm, "Holm p"] = adj
M.to_csv(RES / "h17_haupt.csv", index=False); Cn.to_csv(RES / "h17_kontrolle.csv", index=False)
De.to_csv(RES / "h17_beschreibend.csv", index=False); Y.to_csv(RES / "h17_jahre.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_rows", 500); pd.set_option("display.max_columns", 30)
print(M[M["Horizont"] == "RTH-Ende"].to_string(index=False))
print(M[M["Zeitraum"] == "alle"].to_string(index=False))
print(M[M["Zeitraum"] == "letzte 5 J."].to_string(index=False))
print(Cn.to_string(index=False))
print(De.to_string(index=False))
print(Y.pivot(index="Jahr", columns="Markt", values="EW % ATR").to_string())
