"""
„Tief zuerst → Hoch wird geholt“ – Statistik zur Reihenfolge der IB-Extreme (NQ, ES, RTY, GC; 15/30/45/60 Min; alle Startzeiten).

In der IB wird festgestellt, ob das Tief oder das Hoch zuerst entstanden ist (erstes Auftreten des Extrems, 1m-Bars;
gleicher Bar = unentschieden, ausgelassen). Danach bis Tagesende (17:00 für IBs vor 09:30, sonst 16:00):
  Gegenseite geholt   = bei „Tief zuerst“ wird das IB-Hoch überschritten (bei „Hoch zuerst“ das IB-Tief unterschritten)
  Erstseite nochmal   = das zuerst gebildete Extrem wird noch einmal gebrochen
  Gegenseite zuerst   = die Gegenseite wird VOR der Erstseite gebrochen
  +0,5 / +1 IB        = Ausdehnung über die Gegenseite hinaus (in IB-Ranges)
  Minuten             = Median-Zeit bis die Gegenseite geholt ist (ab IB-Ende)
Vergleich mit allen Tagen (Basis) und Zeiträume: Statistik = 3 Jahre vor dem letzten Jahr, Test = letztes Jahr (ungesehen).

Aufruf: python data-lab/ib_first_side.py   → data-lab/results/ib_first_side.md
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENGTHS = [15, 30, 45, 60]
NCOL = 1380
FOCUS = ["18:00", "03:00", "08:30", "09:30", "10:00"]


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


rows = []
for mk in MARKETS:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2021-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    end = dts.max()
    per = {"Statistik": np.asarray((dts > end - pd.DateOffset(years=4)) & (dts <= end - pd.DateOffset(years=1))),
           "Test": np.asarray(dts > end - pd.DateOffset(years=1))}
    for st in STARTS:
        s = rel(st); e = NCOL if s < rel("09:30") else rel("16:00")
        for L in LENGTHS:
            if s + L > e - 30:
                continue
            Hw, Lw = G["high"][:, s:s + L], G["low"][:, s:s + L]
            cov = np.isfinite(Hw).mean(1)
            with np.errstate(all="ignore"):
                H, Lo = np.nanmax(Hw, 1), np.nanmin(Lw, 1)
            R = H - Lo
            v = (cov >= 0.8) & (R > 0) & (dts.weekday < 5) & np.isfinite(G["high"][:, e - 30:e]).any(1)
            iH = np.argmax(np.nan_to_num(Hw, nan=-np.inf), 1); iL = np.argmin(np.nan_to_num(Lw, nan=np.inf), 1)
            first = np.where(iL < iH, "Tief zuerst", np.where(iH < iL, "Hoch zuerst", "gleich"))
            Hp, Lp = G["high"][:, s + L:e], G["low"][:, s + L:e]
            with np.errstate(invalid="ignore"):
                tu = first_true(Hp > H[:, None]); td = first_true(Lp < Lo[:, None])
                up = (np.nanmax(Hp, 1) - H) / R; dn = (Lo - np.nanmin(Lp, 1)) / R
            for pname, pm in per.items():
                base = v & pm
                if base.sum() < 50:
                    continue
                bu, bd = np.isfinite(tu[base]).mean(), np.isfinite(td[base]).mean()
                for side in ("Tief zuerst", "Hoch zuerst"):
                    m = base & (first == side)
                    if m.sum() < 20:
                        continue
                    lf = side == "Tief zuerst"
                    t_opp, t_same = (tu, td) if lf else (td, tu)
                    ext = up if lf else dn
                    rows.append(dict(Markt=mk, Start=st, IB=L, Zeitraum=pname, Erstes=side, Tage=int(m.sum()),
                                     Anteil=m.sum() / base.sum(),
                                     Gegenseite=np.isfinite(t_opp[m]).mean(), Basis=bu if lf else bd,
                                     Erstseite=np.isfinite(t_same[m]).mean(),
                                     GegenZuerst=(t_opp[m] < t_same[m]).mean(),
                                     Ext05=(ext[m] >= 0.5).mean(), Ext10=(ext[m] >= 1.0).mean(),
                                     Minuten=np.median(t_opp[m][np.isfinite(t_opp[m])]) + 1 if np.isfinite(t_opp[m]).any() else np.nan))
    print(mk, "fertig", flush=True)

X = pd.DataFrame(rows)
X["Vorteil"] = X["Gegenseite"] - X["Basis"]
pct = lambda c: (X[c] * 100).round(0)
S = X.pivot_table(index=["Markt", "Start", "IB", "Erstes"], columns="Zeitraum",
                  values=["Gegenseite", "Basis", "Erstseite", "GegenZuerst", "Ext05", "Ext10", "Minuten", "Tage"])
S.columns = [f"{a} {b}" for a, b in S.columns]
S = S.reset_index()


def tab(sub):
    t = sub[["Markt", "Start", "IB", "Erstes", "Tage Statistik", "Gegenseite Statistik", "Basis Statistik", "Gegenseite Test",
             "Erstseite Statistik", "GegenZuerst Statistik", "Ext05 Statistik", "Ext10 Statistik", "Minuten Statistik"]].copy()
    for c in t.columns:
        if c not in ("Markt", "Start", "IB", "Erstes", "Tage Statistik", "Minuten Statistik"):
            t[c] = (t[c] * 100).round(0)
    t.columns = ["Markt", "Start", "IB", "Erstes", "Tage", "Gegenseite %", "alle Tage %", "Gegenseite Test %",
                 "Erstseite nochmal %", "Gegenseite zuerst %", "+0,5 IB %", "+1 IB %", "Min. bis Gegenseite"]
    return t.to_markdown(index=False)


agg = X.groupby(["Zeitraum", "Erstes"]).apply(lambda g: pd.Series({
    "Gegenseite %": round(100 * np.average(g["Gegenseite"], weights=g["Tage"]), 1),
    "alle Tage %": round(100 * np.average(g["Basis"], weights=g["Tage"]), 1),
    "Erstseite nochmal %": round(100 * np.average(g["Erstseite"], weights=g["Tage"]), 1)}))
diff = S.assign(d=S["Gegenseite Test"] - S["Gegenseite Statistik"])["d"]
md = ["# IB: Tief zuerst → Hoch wird geholt?", "",
      "Erstes Extrem in der IB (1m), danach bis Tagesende (17:00 vor 09:30, sonst 16:00). Statistik = 3 Jahre vor dem",
      "letzten Jahr, Test = letztes Jahr (ungesehen). „alle Tage“ = wie oft dieselbe Seite an allen Tagen geholt wird.", "",
      "## Gesamt (alle Märkte, Startzeiten, Längen, nach Tagen gewichtet)", "", agg.to_markdown(), "",
      f"Stabilität: Abweichung Test − Statistik je Zeile: Median {diff.median() * 100:+.1f} Pkt., 90 % zwischen "
      f"{diff.quantile(0.05) * 100:+.1f} und {diff.quantile(0.95) * 100:+.1f} Pkt.", ""]
for st in FOCUS:
    md += [f"## Start {st}", "", tab(S[S["Start"] == st]), ""]
md += ["## Alle Startzeiten", "", tab(S), ""]
(HERE / "results/ib_first_side.md").write_text("\n".join(md))
X.to_csv(HERE / "results/ib_first_side.csv", index=False)
print("\n".join(md[:14]))
print(tab(S[(S["Start"] == "09:30")]))
