"""
Tagesplan im Indikator (IB-Expansion_ALL.pine) – max. 4 Linien pro Tag, Plätze werden NACHEINANDER gefüllt:
  Ab dem Ende der ersten IB (15 Min) prüft der Indikator auf jedem Bar alle fertigen IBs (15/30/45/60). Ein leerer Platz
  wird gefüllt, sobald es dafür ein Level gibt – danach bleibt er für den Tag fix:
    Protected oben / unten = das nächste Level, das bis Tagesende mit ≥ THR_SL NICHT erreicht wird (über alle IBs)
    TP oben / unten        = das weiteste Level, das bis Tagesende mit ≥ THR_TP erreicht wird und vor dem Protected liegt
  Auf demselben Bar zuerst Protected, dann TP. Neue TPs nicht mehr in den letzten 10 % der Restzeit.

Das „beste“ Level aus 4 IBs ist zu optimistisch (Auswahl-Effekt). Deshalb eine Plan-Korrektur δ je Markt × Startzeit × Art,
die vom % abgezogen wird (auch bei der Auswahl), iterativ geschätzt, gedämpft mit n / (n + 50), begrenzt auf −0,05 … +0,30.
Prüfung: δ aus den 2 Jahren vor dem letzten Jahr → letztes Jahr (dort nicht benutzt), mehrere TP-Schwellen im Vergleich.
Endgültig: δ aus den letzten 3 Jahren → results/ib_ext_coefs.json ("dplan"), dann `ib_ext_model.py --pine`.
Hinweis: Die Formeln selbst enthalten alle 3 Jahre; ihre ungesehene Prüfung steht in ib_ext_model.md.
Nicht simuliert: „TP IB-Rand“ (füllt im Indikator nur einen leeren TP-Platz, eigene Prüfung in ib_ext_model.md).

Aufruf: python data-lab/ib_ext_plan_check.py
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
J = json.loads((HERE / "results/ib_ext_coefs.json").read_text())
A = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENS, NK, NCOL = [15, 30, 45, 60], 31, 1380
THR_SL = 0.80
TP_VARIANTS = [0.70, 0.75, 0.80]
THR_TP = 0.75                       # Standard im Indikator (Begründung: Vergleich in results/ib_ext_plan_check.md)
ARTS = ("TP", "Protected")


def dec(s, p, sc=100):
    a, b = s[p], s[p + 1]
    return np.nan if a not in A or b not in A else (A.index(a) * 62 + A.index(b) - 1922) / sc


def rel(hm):
    h, m = map(int, hm.split(":"))
    return (h * 60 + m - 1080) % 1440


def corr(a, q):
    qq = min(max(q, 0), 1) * 10; i0 = min(int(qq), 9); i1 = min(i0 + 1, 9)
    return a[i0] + (a[i1] - a[i0]) * min(qq - i0, 1)


def prepare(G, dts, mk, st, days):
    s = rel(st); relEnd = 1380 if s < 930 else 1320
    hi, lo, cl = G["high"][days, :relEnd], G["low"][days, :relEnd], G["close"][days, :relEnd]
    wd = np.minimum(dts.weekday.to_numpy()[days], 4)
    W = []
    for L in LENS:
        enc = J["data"][mk].get(f"{st.replace(':', '')}-{L}")
        if enc is None or s + L >= relEnd:
            continue
        cf = np.array([dec(enc, 2 * i) for i in range(len(enc) // 2)])
        if np.isnan(cf[:30]).any() or np.isnan(cf[40:]).any():
            continue
        with np.errstate(all="ignore"):
            Hall = np.nanmax(G["high"][:, s:s + L], 1); Lall = np.nanmin(G["low"][:, s:s + L], 1)
        Rall = Hall - Lall
        vall = (np.isfinite(G["high"][:, s:s + L]).mean(1) >= 0.8) & (Rall > 0) & (dts.weekday < 5)
        med = pd.Series(np.where(vall, Rall, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
        rs = (Rall / med)[days]
        c = np.where(~np.isfinite(rs), 2, np.where(rs <= cf[40], 1, np.where(rs >= cf[41], 3, 2)))
        e0 = s + L
        cumH = np.fmax.accumulate(np.nan_to_num(hi[:, e0:], nan=-np.inf), 1)
        cumL = np.fmin.accumulate(np.nan_to_num(lo[:, e0:], nan=np.inf), 1)
        Bc = [np.stack([cf[((ci - 1) * 2 + side) * 5:((ci - 1) * 2 + side) * 5 + 5] for ci in (1, 2, 3)])[c - 1] for side in (0, 1)]
        Wd = [cf[42 + side * 5 + wd] for side in (0, 1)]
        W.append(dict(e0=e0, H=Hall[days], Lo=Lall[days], R=Rall[days], v=vall[days], cumH=cumH, cumL=cumL, B=Bc, w=Wd))
    if not W:
        return None
    # was nach Bar t noch kommt (für den Ausgang)
    sufH = np.fmax.accumulate(np.nan_to_num(hi, nan=-np.inf)[:, ::-1], 1)[:, ::-1]
    sufL = np.fmin.accumulate(np.nan_to_num(lo, nan=np.inf)[:, ::-1], 1)[:, ::-1]
    sufH = np.concatenate([sufH[:, 1:], np.full((len(days), 1), -np.inf)], 1)
    sufL = np.concatenate([sufL[:, 1:], np.full((len(days), 1), np.inf)], 1)
    return dict(W=W, s=s, relEnd=relEnd, cl=cl, sufH=sufH, sufL=sufL, n=len(days))


def plan(P, DT, DP, thrTP, dTP, dSL):
    """Plätze nacheinander füllen wie im Indikator; Zeilen (Art, angezeigt, eingetreten)."""
    W, n, relEnd = P["W"], P["n"], P["relEnd"]
    ks = np.arange(NK)[None, :]
    Y = np.full((4, n), np.nan); Pc = np.full((4, n), np.nan); T = np.full((4, n), -1)
    for t in range(min(w["e0"] for w in W), relEnd):
        if not np.isnan(Y).any():
            break
        cl = P["cl"][:, t]
        for side in (0, 1):
            sgn = 1 if side == 0 else -1
            iS, iT = 2 + side, side
            needS, needT = np.isnan(Y[iS]), np.isnan(Y[iT])
            if not (needS.any() or needT.any()):
                continue
            ps = []
            for w in W:
                if t < w["e0"]:
                    continue
                q = (t - w["e0"] + 1) / (relEnd - w["e0"])
                vq = np.log(1 - min(max(q, 0), 0.98) + 0.02)
                R = w["R"][:, None]
                lv = (w["H"][:, None] + ks * 0.1 * R) if side == 0 else (w["Lo"][:, None] - ks * 0.1 * R)
                if side == 0:
                    mx = w["cumH"][:, t - w["e0"]]; reached = mx[:, None] >= lv; reached[:, 0] = mx > w["H"]
                else:
                    mn = w["cumL"][:, t - w["e0"]]; reached = mn[:, None] <= lv; reached[:, 0] = mn < w["Lo"]
                u = np.log(np.maximum(sgn * (lv - cl[:, None]) / R, 0) + 0.03)
                B = w["B"][side]
                with np.errstate(all="ignore"):
                    p = 1 / (1 + np.exp(-(B[:, [0]] + B[:, [1]] * u + B[:, [2]] * vq + B[:, [3]] * u * vq + B[:, [4]] * u * u + w["w"][side][:, None])))
                ok = ~reached & w["v"][:, None] & np.isfinite(lv) & np.isfinite(cl)[:, None]
                ps.append((q, lv, p, ok))
            # Protected: nächstes über alle IBs, hinter einem schon gesetzten TP
            if needS.any():
                bestY = np.full(n, np.nan); bestP = np.full(n, np.nan)
                for q, lv, p, ok in ps:
                    pS = 1 - p - corr(DP, q) - dSL
                    behind = np.isnan(Y[iT])[:, None] | (sgn * lv > sgn * Y[iT][:, None])
                    m = ok & (p < 0.5) & (pS >= THR_SL) & behind
                    has = m.any(1); k = np.argmax(m, 1); y = lv[np.arange(n), k]
                    better = has & (np.isnan(bestY) | (sgn * y < sgn * bestY))
                    bestY = np.where(better, y, bestY); bestP = np.where(better, pS[np.arange(n), k], bestP)
                f = needS & np.isfinite(bestY)
                Y[iS][f], Pc[iS][f], T[iS][f] = bestY[f], bestP[f], t
            # TP: weitestes über alle IBs, vor dem Protected
            if needT.any():
                bestY = np.full(n, np.nan); bestP = np.full(n, np.nan)
                for q, lv, p, ok in ps:
                    if q >= 0.9:
                        continue
                    pT = p - corr(DT, q) - dTP
                    before = np.isnan(Y[iS])[:, None] | (sgn * lv < sgn * Y[iS][:, None])
                    m = ok & (p >= 0.5) & (pT >= thrTP) & before
                    has = m.any(1); k = NK - 1 - np.argmax(m[:, ::-1], 1); y = lv[np.arange(n), k]
                    better = has & (np.isnan(bestY) | (sgn * y > sgn * bestY))
                    bestY = np.where(better, y, bestY); bestP = np.where(better, pT[np.arange(n), k], bestP)
                f = needT & np.isfinite(bestY)
                Y[iT][f], Pc[iT][f], T[iT][f] = bestY[f], bestP[f], t
    out = []
    for i in range(4):
        sel = np.flatnonzero(T[i] >= 0)
        if not len(sel):
            continue
        up = i % 2 == 0
        hit = (P["sufH"][sel, T[i][sel]] >= Y[i][sel]) if up else (P["sufL"][sel, T[i][sel]] <= Y[i][sel])
        art = "TP" if i < 2 else "Protected"
        out.append(pd.DataFrame({"Art": art, "Seite": "oben" if up else "unten", "Tag": sel, "angezeigt": Pc[i][sel],
                                 "ok": hit if art == "TP" else ~hit, "Minute": T[i][sel] - P["s"]}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["Art", "Seite", "Tag", "angezeigt", "ok", "Minute"])


def fit_delta(P, DT, DP, thrTP, it=3):
    d = {"TP": 0.0, "Protected": 0.0}
    for _ in range(it):
        X = plan(P, DT, DP, thrTP, d["TP"], d["Protected"])
        for art in ARTS:
            x = X[X["Art"] == art]
            if len(x):
                b = (x["angezeigt"].mean() - x["ok"].mean()) * len(x) / (len(x) + 50)
                d[art] = float(np.clip(d[art] + b, -0.05, 0.30))
    return d


def run_market(mk):
    """Ein Markt (läuft parallel): Prüfzeilen, Plan-Korrektur je Startzeit, Anzahl Testtage."""
    rows, dplan, ndays = [], {}, {}
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2023-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    G["close"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    end = dts.max()
    wk = np.asarray(dts.weekday < 5)
    test = np.flatnonzero(np.asarray(dts > end - pd.DateOffset(years=1)) & wk)
    cal = np.flatnonzero(np.asarray((dts > end - pd.DateOffset(years=3)) & (dts <= end - pd.DateOffset(years=1))) & wk)
    final = np.flatnonzero(np.asarray(dts > end - pd.DateOffset(years=3)) & wk)
    DT = [J["dfin"].get(f"{mk}|Target|{q}", 0.0) for q in range(10)]
    DP = [J["dfin"].get(f"{mk}|Protect|{q}", 0.0) for q in range(10)]
    for st in STARTS:
        Pc_, Pt_ = prepare(G, dts, mk, st, cal), prepare(G, dts, mk, st, test)
        if Pc_ is None:
            continue
        ndays[(mk, st)] = len(test)
        for thr in TP_VARIANTS:
            d0 = fit_delta(Pc_, DT, DP, thr)
            for name, (dt_, ds_) in {"ohne": (0.0, 0.0), "Protected": (0.0, d0["Protected"]), "beide": (d0["TP"], d0["Protected"])}.items():
                rows.append(plan(Pt_, DT, DP, thr, dt_, ds_).assign(Markt=mk, Start=st, TPab=thr, Korrektur=name))
        dF = fit_delta(prepare(G, dts, mk, st, final), DT, DP, THR_TP)
        for art in ARTS:
            dplan[f"{mk}|{st}|{art}"] = round(dF[art], 3)
        print(mk, st, flush=True)
    return rows, dplan, ndays


if __name__ == "__main__":
    from multiprocessing import Pool
    rows, dplan, ndays = [], {}, {}
    with Pool(len(MARKETS)) as pool:
        for r, d, n in pool.map(run_market, MARKETS):
            rows += r; dplan.update(d); ndays.update(n)
    X = pd.concat(rows, ignore_index=True)
    nd = sum(ndays.values())
    f = lambda g: pd.Series({"Linien": len(g), "angezeigt": round(g["angezeigt"].mean(), 3), "eingetreten": round(g["ok"].mean(), 3)})


    def cover(g):
        tp = g[g["Art"] == "TP"].groupby(["Markt", "Start"])["Tag"].nunique().sum()
        return pd.Series({"TP je Tag": round((g["Art"] == "TP").sum() / nd, 2), "Protected je Tag": round((g["Art"] == "Protected").sum() / nd, 2),
                          "Tage mit TP": f"{tp / nd:.0%}"})


    md = ["# IB-Expansion Tagesplan – Prüfung im letzten Jahr", "",
          f"Alle 25 Startzeiten, alle 4 IB-Längen, Plätze werden nacheinander gefüllt (ab Ende der 15-Min-IB). Protected ≥ {THR_SL:.0%}.",
          "Plan-Korrektur aus den 2 Jahren davor (im Testjahr nicht benutzt). Die Formeln selbst enthalten das Testjahr –",
          "ihre ungesehene Prüfung steht in ib_ext_model.md.", "",
          "## Vergleich TP-Schwelle × Korrektur (angezeigt vs. eingetreten)", "",
          X.groupby(["TPab", "Korrektur", "Art"]).apply(f).unstack("Art").to_markdown(), "",
          "## Wie oft gibt es Linien? (je Start und Tag)", "", X[X["Korrektur"] == "beide"].groupby("TPab").apply(cover).to_markdown(), ""]
    S = X[(X["TPab"] == THR_TP) & (X["Korrektur"] == "beide")]
    md += [f"## Standard im Indikator: TP ≥ {THR_TP:.0%}, Korrektur für beide – je Markt", "", S.groupby(["Art", "Markt"]).apply(f).to_markdown(), "",
           "## … je Startzeit", "", S.groupby(["Start", "Art"]).apply(f).unstack("Art").to_markdown(), "",
           "## … nach angezeigtem %", "",
           S.assign(Band=pd.cut(S["angezeigt"], [0.69, 0.8, 0.9, 1.01], labels=["70–80", "80–90", "90–100"])).groupby(["Art", "Band"], observed=True).apply(f).to_markdown(), "",
           "## … wann kommen die Linien? (Minuten nach IB-Start, Median)", "", S.groupby("Art")["Minute"].median().to_frame().to_markdown(), ""]
    (HERE / "results/ib_ext_plan_check.md").write_text("\n".join(md))
    J["dplan"] = dplan
    (HERE / "results/ib_ext_coefs.json").write_text(json.dumps(J))
    print("\n".join(md))
