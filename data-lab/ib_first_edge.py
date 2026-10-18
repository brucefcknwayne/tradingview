"""
Projekt ib-first – ist „welche IB-Seite bricht zuerst“ ein Edge?

Die Trefferquote allein reicht nicht: Steht der Kurs am IB-Ende nah an einer Seite, bricht diese auch ohne jeden Vorteil oft
zuerst. Bei reinem Zufall (Kurs ohne Drift) ist P(nahe Seite zuerst) = Abstand zur anderen Seite / IB-Range („Geometrie“).
Ein Edge liegt nur vor, wenn
  1) die Seite öfter zuerst bricht, als die Geometrie sagt, und
  2) sich das in Punkten auszahlt: Einstieg am Schluss des IB-Endes Richtung der favorisierten Seite, Ziel = diese Seite,
     Stop = die andere Seite, sonst Ausstieg am Sitzungsende; abzüglich Kosten (2 Ticks je Trade).
Wie im Indikator: Länge „Auto“ je Markt und Start, Signal ab 70 %. Modell nur mit Daten VOR dem Testjahr trainiert
(5 Jahre, Stufe C, gleiche Einstellungen wie ib_first_model.py), Test = letztes Jahr.

Aufruf: python data-lab/ib_first_edge.py   → results/ib_first_edge.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
# Funktionen und Einstellungen aus ib_first_model.py übernehmen (nur der Teil vor dem Laden der Daten)
_src = (HERE / "ib_first_model.py").read_text().split("# ═══ Daten laden ═══")[0]
ns = {"__file__": str(HERE / "ib_first_model.py")}
exec(_src, ns)
J = json.loads((HERE / "results/ib_first_model.json").read_text())
COLS, LAM, WIN = J["cols"], J["lam"], J["window"]
TICK = {"NQ": 0.25, "ES": 0.25, "RTY": 0.1, "GC": 0.1}
SIG = 0.70
rel, sigmoid, design, fit_all, window_days = ns["rel"], ns["sigmoid"], ns["design"], ns["fit_all"], ns["window_days"]

rows = []
for mk in ns["MARKETS"]:
    import glob
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2019-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < ns["NCOL"]
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low", "close"]:
        a = np.full((len(days), ns["NCOL"]), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    end = dts.max()
    yrs = lambda a, b: np.asarray((dts > end - pd.DateOffset(years=a)) & (dts <= end - pd.DateOffset(years=b)))
    for st in ns["STARTS"]:
        L = J["bestLall"].get(f"{mk}|{st}")
        if L is None:
            continue
        s = rel(st); e = ns["NCOL"] if s < rel("09:30") else rel("16:00")
        D = window_days(G, dts, s, L, e)
        it, ix = np.flatnonzero(D["v"] & yrs(1 + WIN, 1)), np.flatnonzero(D["v"] & yrs(1, 0))
        if len(it) < 150 or len(ix) < 30:
            continue
        _, bz, bs = fit_all(D, it, COLS, LAM)
        X = design(D, ix, COLS)
        pO, pS = sigmoid(X @ bz), sigmoid(X @ bs)
        # Preise je Testtag
        with np.errstate(all="ignore"):
            H = np.nanmax(G["high"][ix, s:s + L], 1); Lo = np.nanmin(G["low"][ix, s:s + L], 1)
        lf = D["F"]["side"].to_numpy()[ix] == 1
        entry = G["cff"][ix, s + L - 1]
        exitc = G["cff"][ix, e - 1]
        Hp, Lp = G["high"][ix, s + L:e], G["low"][ix, s + L:e]
        with np.errstate(invalid="ignore"):
            tu = ns["first_true"](Hp > H[:, None]); td = ns["first_true"](Lp < Lo[:, None])
        opp = pO >= pS
        p = np.where(opp, pO, pS)
        up = opp == lf                                    # favorisierte Seite = IB-Hoch
        sig = p >= SIG
        fav = np.where(up, H, Lo); oth = np.where(up, Lo, H)
        d_f = np.abs(fav - entry); d_o = np.abs(oth - entry)
        geo = d_o / (d_f + d_o)                           # Zufall ohne Drift: nahe Seite zuerst
        t_f, t_o = np.where(up, tu, td), np.where(up, td, tu)
        won = np.isfinite(t_f) & (t_f < t_o)
        lost = np.isfinite(t_o) & (t_o <= t_f)            # gleicher Bar = verloren (wie Statistik)
        pnl = np.where(won, d_f, np.where(lost, -d_o, np.where(up, exitc - entry, entry - exitc)))
        cost = 2 * TICK[mk]
        for i in np.flatnonzero(sig):
            rows.append(dict(Markt=mk, Start=st, IB=L, p=p[i], geo=geo[i], won=won[i], lost=lost[i],
                             pnl=pnl[i], netto=pnl[i] - cost, R=pnl[i] / d_o[i] if d_o[i] > 0 else np.nan,
                             d_f=d_f[i], d_o=d_o[i], range=H[i] - Lo[i]))
    print(mk, "fertig", flush=True)

X = pd.DataFrame(rows)


def summ(g):
    w, l = g.loc[g["won"], "pnl"], g.loc[g["lost"], "pnl"]
    gp, gl = g.loc[g["netto"] > 0, "netto"].sum(), -g.loc[g["netto"] < 0, "netto"].sum()
    return pd.Series({"Signale": len(g), "angezeigt %": round(100 * g["p"].mean(), 1), "zuerst gebrochen %": round(100 * g["won"].mean(), 1),
                      "Geometrie %": round(100 * g["geo"].mean(), 1), "Ø Gewinn Pkt": round(w.mean(), 2), "Ø Verlust Pkt": round(l.mean(), 2),
                      "Ø Ergebnis Pkt (netto)": round(g["netto"].mean(), 2), "Ø Ergebnis in R": round(g["R"].mean(), 3),
                      "Profit-Faktor (netto)": round(gp / gl, 2) if gl > 0 else np.nan})


KEY = ["18:00", "03:00", "08:30", "09:30", "10:00"]
md = ["# IB First – Edge-Prüfung (letztes Jahr, ungesehen)", "",
      "Einstieg am IB-Ende Richtung der favorisierten Seite (Signal ≥ 70 %, Länge Auto), Ziel = diese Seite, Stop = andere Seite,",
      "sonst Ausstieg am Sitzungsende; netto = minus 2 Ticks. „Geometrie“ = was reiner Zufall wegen der Abstände erwarten lässt.",
      "R = Ergebnis geteilt durch den Abstand zum Stop.", "",
      "## Je Markt (alle Startzeiten)", "", X.groupby("Markt").apply(summ).to_markdown(), "",
      "## Wichtige Startzeiten", "", X[X["Start"].isin(KEY)].groupby(["Markt", "Start"]).apply(summ).to_markdown(), "",
      "## Nach angezeigter Wahrscheinlichkeit (alle)", "",
      X.assign(Band=pd.cut(X["p"], [0.69, 0.8, 0.9, 1.01], labels=["70–80", "80–90", "90–100"])).groupby("Band", observed=True).apply(summ).to_markdown(), ""]
(HERE / "results/ib_first_edge.md").write_text("\n".join(md))
print("\n".join(md))
