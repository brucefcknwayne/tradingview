"""
Tagesplan im Indikator (IB-Expansion_ALL.pine): Sobald alle 4 IBs (15/30/45/60) fertig sind, werden über alle IBs je Seite
das nächste Protected (≥ 80 % hält) und das weiteste TP (≥ 80 % erreicht, vor dem Protected) gewählt – max. 4 Linien.

Die Auswahl des nächsten Protected aus 4 IBs ist zu optimistisch (Auswahl-Effekt, dazu die 09:30-Eröffnung). Deshalb eine
eigene Plan-Korrektur δ je Markt × Startzeit für Protected, die vom % abgezogen wird (auch bei der Auswahl). Für TP hat eine
solche Korrektur im Testjahr nicht geholfen (verglichen mit TP ab 70 / 75 / 80 %) – dort hält die höhere Schwelle 80 % ehrlich:
  δ wird iterativ geschätzt (Auswahl hängt von δ ab), gedämpft mit n / (n + 50), begrenzt auf −0,05 … +0,30.
Prüfung: δ aus den 2 Jahren vor dem letzten Jahr → angewendet auf das letzte Jahr (dort nicht benutzt).
Endgültig: δ aus den letzten 3 Jahren → results/ib_ext_coefs.json ("dplan"), dann `ib_ext_model.py --pine`.
Hinweis: Die Formeln selbst enthalten alle 3 Jahre; ihre ungesehene Prüfung steht in ib_ext_model.md.

Aufruf: python data-lab/ib_ext_plan_check.py
"""
import glob
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
REPO = HERE.parent
J = json.loads((HERE / "results/ib_ext_coefs.json").read_text())
A = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENS, NK, NCOL = [15, 30, 45, 60], 31, 1380
THR_TP, THR_SL = 0.80, 0.80
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


def prepare(G, dts, mk, st):
    """Je IB-Länge alles, was der Plan am Entscheidungs-Bar braucht (alle Tage auf einmal)."""
    s = rel(st); relEnd = 1380 if s < 930 else 1320
    W = []
    for L in LENS:
        enc = J["data"][mk].get(f"{st.replace(':', '')}-{L}")
        if enc is None or s + L >= relEnd:
            continue
        cf = np.array([dec(enc, 2 * i) for i in range(len(enc) // 2)])
        if np.isnan(cf[:30]).any() or np.isnan(cf[40:]).any():
            continue
        with np.errstate(all="ignore"):
            H = np.nanmax(G["high"][:, s:s + L], 1); Lo = np.nanmin(G["low"][:, s:s + L], 1)
        R = H - Lo
        v = (np.isfinite(G["high"][:, s:s + L]).mean(1) >= 0.8) & (R > 0) & (dts.weekday < 5)
        med = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
        rs = R / med
        c = np.where(~np.isfinite(rs), 2, np.where(rs <= cf[40], 1, np.where(rs >= cf[41], 3, 2)))
        W.append(dict(L=L, cf=cf, H=H, Lo=Lo, R=R, v=v, c=c))
    if not W:
        return None
    tD = s + max(w["L"] for w in W)
    cl = G["close"][:, tD]
    with np.errstate(all="ignore"):
        hiA = np.nanmax(G["high"][:, tD + 1:relEnd], 1); loA = np.nanmin(G["low"][:, tD + 1:relEnd], 1)
    ks = np.arange(NK)[None, :]
    wd = np.minimum(dts.weekday.to_numpy(), 4)
    for w in W:
        e0 = s + w["L"]; q = (tD - e0 + 1) / (relEnd - e0); vq = np.log(1 - min(max(q, 0), 0.98) + 0.02)
        with np.errstate(all="ignore"):
            hmax = np.nanmax(G["high"][:, e0:tD + 1], 1); lmin = np.nanmin(G["low"][:, e0:tD + 1], 1)
        w["q"] = q
        w["lv"], w["p"], w["reached"] = [], [], []
        for side in (0, 1):
            lv = w["H"][:, None] + ks * 0.1 * w["R"][:, None] if side == 0 else w["Lo"][:, None] - ks * 0.1 * w["R"][:, None]
            if side == 0:
                reached = hmax[:, None] >= lv; reached[:, 0] = hmax > w["H"]
            else:
                reached = lmin[:, None] <= lv; reached[:, 0] = lmin < w["Lo"]
            dist = ((lv - cl[:, None]) if side == 0 else (cl[:, None] - lv)) / w["R"][:, None]
            u = np.log(np.maximum(dist, 0) + 0.03)
            B = np.stack([w["cf"][((ci - 1) * 2 + side) * 5:((ci - 1) * 2 + side) * 5 + 5] for ci in (1, 2, 3)])[w["c"] - 1]
            z = B[:, [0]] + B[:, [1]] * u + B[:, [2]] * vq + B[:, [3]] * u * vq + B[:, [4]] * u * u + w["cf"][42 + side * 5 + wd][:, None]
            with np.errstate(all="ignore"):
                w["lv"].append(lv); w["p"].append(1 / (1 + np.exp(-z))); w["reached"].append(reached | ~np.isfinite(lv))
    return dict(W=W, cl=cl, hiA=hiA, loA=loA, ok=np.isfinite(cl) & np.isfinite(hiA))


def plan(P, days, DT, DP, dTP, dSL):
    """Auswahl wie im Indikator; gibt je gewählter Linie (Art, angezeigt, eingetreten) zurück."""
    W, n = P["W"], len(P["cl"])
    out = []
    for side in (0, 1):
        sgn = 1 if side == 0 else -1                    # „weiter weg“ = größer bei oben, kleiner bei unten
        prY = np.full(n, np.nan); prP = np.full(n, np.nan)
        for w in W:                                     # Protected: nächstes über alle IBs
            pS = 1 - w["p"][side] - corr(DP, w["q"]) - dSL
            m = (w["p"][side] < 0.5) & (pS >= THR_SL) & ~w["reached"][side] & w["v"][:, None]
            has = m.any(1); k = np.argmax(m, 1)
            y = w["lv"][side][np.arange(n), k]; pp = pS[np.arange(n), k]
            better = has & (np.isnan(prY) | (sgn * y < sgn * prY))
            prY = np.where(better, y, prY); prP = np.where(better, pp, prP)
        tY = np.full(n, np.nan); tP = np.full(n, np.nan)
        for w in W:                                     # TP: weitestes vor dem Protected
            pT = w["p"][side] - corr(DT, w["q"]) - dTP
            before = np.isnan(prY)[:, None] | (sgn * w["lv"][side] < sgn * prY[:, None])
            m = (w["p"][side] >= 0.5) & (pT >= THR_TP) & (w["q"] < 0.9) & before & ~w["reached"][side] & w["v"][:, None]
            has = m.any(1); k = NK - 1 - np.argmax(m[:, ::-1], 1)
            y = w["lv"][side][np.arange(n), k]; pp = pT[np.arange(n), k]
            better = has & (np.isnan(tY) | (sgn * y > sgn * tY))
            tY = np.where(better, y, tY); tP = np.where(better, pp, tP)
        hit = lambda y: (P["hiA"] >= y) if side == 0 else (P["loA"] <= y)
        for art, Y, Pp in (("TP", tY, tP), ("Protected", prY, prP)):
            sel = days & P["ok"] & np.isfinite(Y)
            h = hit(Y)[sel]
            out.append(pd.DataFrame({"Art": art, "angezeigt": Pp[sel], "ok": h if art == "TP" else ~h}))
    return pd.concat(out, ignore_index=True)


def fit_delta(P, days, DT, DP, it=4):
    d = {"TP": 0.0, "Protected": 0.0}
    for _ in range(it):
        X = plan(P, days, DT, DP, d["TP"], d["Protected"])
        for art in ("Protected",):                       # TP: keine Plan-Korrektur (siehe oben)
            x = X[X["Art"] == art]
            if len(x):
                b = (x["angezeigt"].mean() - x["ok"].mean()) * len(x) / (len(x) + 50)
                d[art] = float(np.clip(d[art] + b, -0.05, 0.30))
    return d


rows, dplan = [], {}
for mk in MARKETS:
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
    test = np.asarray(dts > end - pd.DateOffset(years=1))
    cal = np.asarray((dts > end - pd.DateOffset(years=3)) & ~test)
    final = np.asarray(dts > end - pd.DateOffset(years=3))
    DT = [J["dfin"].get(f"{mk}|Target|{q}", 0.0) for q in range(10)]
    DP = [J["dfin"].get(f"{mk}|Protect|{q}", 0.0) for q in range(10)]
    for st in STARTS:
        P = prepare(G, dts, mk, st)
        if P is None:
            continue
        dc = fit_delta(P, cal, DT, DP)
        for name, (dt_, ds_) in {"ohne Plan-Korrektur": (0.0, 0.0), "mit Plan-Korrektur": (dc["TP"], dc["Protected"])}.items():
            X = plan(P, test, DT, DP, dt_, ds_).assign(Markt=mk, Start=st, Variante=name)
            rows.append(X)
        df_ = fit_delta(P, final, DT, DP)
        dplan[f"{mk}|{st}|Protected"] = round(df_["Protected"], 3)
    print(mk, "fertig", flush=True)

X = pd.concat(rows, ignore_index=True)
X["Tage"] = 1
f = lambda g: pd.Series({"Linien": len(g), "angezeigt": round(g["angezeigt"].mean(), 3), "eingetreten": round(g["ok"].mean(), 3)})
md = ["# IB-Expansion Tagesplan – Prüfung im letzten Jahr", "",
      f"Alle 25 Startzeiten, alle 4 IB-Längen, Entscheidung nach der längsten IB. TP ≥ {THR_TP:.0%}, Protected ≥ {THR_SL:.0%}.",
      "Plan-Korrektur aus den 2 Jahren davor (im Testjahr nicht benutzt). Die Formeln selbst enthalten das Testjahr –",
      "ihre ungesehene Prüfung steht in ib_ext_model.md.", "",
      "## Gesamt", "", X.groupby(["Variante", "Art"]).apply(f).to_markdown(), "",
      "## Je Markt (mit Plan-Korrektur)", "", X[X["Variante"] == "mit Plan-Korrektur"].groupby(["Art", "Markt"]).apply(f).to_markdown(), "",
      "## Je Startzeit (mit Plan-Korrektur)", "", X[X["Variante"] == "mit Plan-Korrektur"].groupby(["Art", "Start"]).apply(f).unstack("Art").to_markdown(), "",
      "## Nach angezeigtem % (mit Plan-Korrektur)", "",
      X[X["Variante"] == "mit Plan-Korrektur"].assign(Band=lambda t: pd.cut(t["angezeigt"], [0.69, 0.8, 0.9, 1.01], labels=["70–80", "80–90", "90–100"]))
       .groupby(["Art", "Band"], observed=True).apply(f).to_markdown(), ""]
(HERE / "results/ib_ext_plan_check.md").write_text("\n".join(md))
J["dplan"] = dplan
(HERE / "results/ib_ext_coefs.json").write_text(json.dumps(J))
print("\n".join(md))
