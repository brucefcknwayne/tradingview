"""
Gotham Engine – Auswertung (Basis v1.5.1) + Empfehlung aus sweep.csv. Aufruf nach engine_eval.py.
"""
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

sys.path.insert(0, str(Path(__file__).parent))
from engine_sim import CACHE, OUT  # noqa: E402
from engine_eval import days, rand_cmp, score, summ, to_csv  # noqa: E402

nd = len(days)
E = pd.read_parquet(CACHE / "events_base.parquet")
SW = pd.read_csv(OUT / "sweep.csv")
keep = pickle.load(open(CACHE / "sweep_events.pkl", "rb"))
L = []
P = L.append
pd.set_option("display.width", 250)


def md(df):
    return df.to_markdown(index=False)


A, B = E[E["typ"] == 0].copy(), E[E["typ"] == 1].copy()
P(f"# Gotham Engine v1.5.1 – Nachrechnung auf NQ-Trades\n")
P(f"Daten: Databento GLBX.MDP3, Schema **trades** (Aggressor-Seite), Front-Kontrakt NQZ6, {nd} Handelstage "
  f"{days[0]} bis {days[-1]} (Globex 18:00–17:00 NY). Kein tbbo/mbo (Konto gesperrt) → refill und iceberg leer, Score max. 75 statt 100.\n")
P("## 1) Wie oft?\n")
cnt = pd.DataFrame({"Typ": ["ABSORPTION", "BREAKING"], "gesamt": [len(A), len(B)],
                    "pro Tag": [round(len(A) / nd, 1), round(len(B) / nd, 1)],
                    "RTH (09:30–16:00) pro Tag": [round(A["rth"].sum() / nd, 1), round(B["rth"].sum() / nd, 1)],
                    "Overnight pro Tag": [round((~A["rth"]).sum() / nd, 1), round((~B["rth"]).sum() / nd, 1)]})
P(md(cnt) + "\n")
hr = pd.concat([A.groupby("hour").size().rename("Absorption"), B.groupby("hour").size().rename("Breaking")], axis=1).fillna(0) / nd
hr = hr.sort_index().round(1).reset_index().rename(columns={"hour": "NY-Stunde"})
P("Pro NY-Stunde (Ø je Tag):\n\n" + md(hr) + "\n")
P("## 2) Ergebnisse und Zufallsvergleich (Basis-Einstellung)\n")
rows = []
for name, X in (("ABSORPTION", A), ("BREAKING", B), ("BREAKING RTH", B[B["rth"]]), ("BREAKING Overnight", B[~B["rth"]]),
                ("ABSORPTION Overnight", A[~A["rth"]])):
    if len(X):
        rows.append(dict(Typ=name, **summ(X, nd)))
P(md(pd.DataFrame(rows)) + "\n")
P("Zufall = je Ereignis ein zufälliger Zeitpunkt aus derselben NY-Stunde (alle 20 Tage), gleiche Richtung, 1.000 Wiederholungen. "
  "p = Anteil der Zufalls-Durchläufe, die mindestens so gut sind (klein = Signal besser als Zufall).\n")
P("## 3) Was trennt HELD von FAILED? (Absorption)\n")
loose = keep[("A", 1.5, 3, 0.25)]
for nm, X in (("Basis v1.5.1", A), ("locker (1,5 / 3 Ticks / 0,25) – mehr Fälle", loose)):
    X = X.copy(); X["score"] = score(X)
    h, f = X[X["code"] == 1], X[X["code"] == -1]
    r = []
    for col, lab in (("score", "score"), ("x", "x_normal"), ("conc", "conc"), ("fading", "fading"), ("variant", "nach Push (Anteil)"),
                     ("push", "after_push_ticks"), ("big", "big_orders"), ("move", "move_ticks"), ("act", "activity"), ("V", "volume_20s")):
        if len(h) >= 5 and len(f) >= 5:
            auc = st.mannwhitneyu(h[col], f[col]).statistic / (len(h) * len(f))
            r.append({"Merkmal": lab, "HELD Ø": round(h[col].mean(), 2), "FAILED Ø": round(f[col].mean(), 2),
                      "HELD Median": round(h[col].median(), 2), "FAILED Median": round(f[col].median(), 2), "AUC (0,5 = trennt nicht)": round(auc, 2)})
    P(f"**{nm}:** HELD {len(h)}, FAILED {len(f)}, EXPIRED {int((X['code'] == 0).sum())}\n\n" + (md(pd.DataFrame(r)) if r else "zu wenige Fälle") + "\n")
P("## 4) Wie spät ist Breaking?\n")
late = B["dirn"] * (B["last"] - B["ref"])
P(f"Ticks zwischen gebrochenem 2-min-Hoch/Tief und Erkennungspreis: Median **{late.median():.0f}**, Ø {late.mean():.1f}, "
  f"25 % ≤ {late.quantile(.25):.0f}, 75 % ≤ {late.quantile(.75):.0f} Ticks.\n")
for W in (20, 10, 5):
    k = ("B", W * 1000, 1.5, 4, 0)
    if k in keep and len(keep[k]):
        X = keep[k]; lt = X["dirn"] * (X["last"] - X["ref"])
        P(f"- Fenster {W} s (1,5 × normal, 4 Ticks): Median {lt.median():.0f} Ticks zu spät, Ø ret_5m {X['r5'].mean():.2f}, Treffer {100 * (X['code'] == 1).mean():.1f} %")
P("\n## 5) Kalibrierung\n")
sa = SW[SW["Typ"] == "ABSORPTION"].copy()
sb = SW[SW["Typ"] == "BREAKING"].copy()
cols = ["Fenster_s", "Mult", "Ticks", "minConc", "Duplikatfilter", "Ereignisse/Tag", "davon RTH/Tag", "Treffer % (HELD/CONT.)", "FAILED %",
        "Ø ret_5m", "Edge 5m", "p 5m", "Edge 15m", "p 15m", "Sim-PnL Ticks/Ereignis"]
P("Absorption (alle 36):\n\n" + md(sa[[c for c in cols if c != "Duplikatfilter"]]) + "\n")
P("Breaking (alle 72):\n\n" + md(sb[[c for c in cols if c != "minConc"]]) + "\n")
P(f"Mehrfachtest-Hinweis: {len(SW)} Einstellungen. Bei p < 0,05 sind rein zufällig etwa {len(SW) * 0.05:.0f} „Treffer“ zu erwarten. "
  f"Nach Bonferroni bräuchte eine Einstellung p < {0.05 / len(SW):.4f}.\n")
P("## 6) Simulation 20 Tage (jedes Ereignis gehandelt, Basis v1.5.1)\n")
P("Einstieg = letzter Preis bei Erkennung. Absorption: Ziel Wall ± 8 Ticks, Stop 4 Ticks durch die Wall, sonst Ausstieg nach 3 min. "
  "Breaking: Ziel +16 Ticks, Stop 4 Ticks zurück durch ref_price, sonst 3 min. Kosten 2 Ticks je Trade.\n")
sim = []
for nm, X in (("ABSORPTION", A), ("BREAKING", B), ("BREAKING nur RTH", B[B["rth"]])):
    sim.append({"Typ": nm, "Trades": len(X), "Trades/Tag": round(len(X) / nd, 1), "Ø Ticks/Trade": round(X["pnl"].mean(), 2),
                "Summe Ticks": round(X["pnl"].sum(), 0), "MNQ $ (20 Tage, 1 Kontrakt)": round(X["pnl"].sum() * 0.5, 0),
                "NQ $ (20 Tage, 1 Kontrakt)": round(X["pnl"].sum() * 5, 0), "Tage im Plus": f"{int((X.groupby('session')['pnl'].sum() > 0).sum())}/{nd}"})
P(md(pd.DataFrame(sim)) + "\n")
P("## 7) Umgekehrt gelesen\n")
for nm, X in (("Breaking als Fade (gegen dir)", B), ("Absorption umgekehrt (mit den Aggressoren)", A)):
    r5m, r5p = rand_cmp(X.assign(dirn=-X["dirn"], r5=-X["r5"]), "r5")
    P(f"- {nm}: Ø ret_5m {-X['r5'].mean():+.2f} Ticks, Zufall {r5m:+.2f}, p {r5p:.3f}, nach 2 Ticks Kosten {-X['r5'].mean() - 2:+.2f} Ticks/Trade")
P("\nAchtung: Ereignisse liegen zeitlich dicht beieinander (Cluster), die p-Werte sind deshalb eher zu optimistisch.\n")
(OUT / "auswertung.md").write_text("\n".join(L))
print("\n".join(L))
