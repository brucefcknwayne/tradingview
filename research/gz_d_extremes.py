"""
H7 Zusatz: Zonen-Berührungen, die zum HOD/LOD wurden, vs. Berührungen, die durchbrochen wurden.
(a) Gemeinsamkeiten (Explore): Anteil/Ø je Merkmal, Effektstärke, Grundrate; Gegenprobe an Kontroll-Levels.
(b) Vorhersage zum Berührungszeitpunkt: Modell auf Explore, Prüfung auf Validate (AUC, Trefferquote im oberen Zehntel).
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research/results"
E = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(ROOT / "data-lab/data/raw/gz_cache/gz_b_events_*.parquet"))))
E["uhr_et"] = ((E["t"] + 1080) % 1440) / 60
E["y"] = E["wurde_Extrem"].astype(int)
FE = ["k", "uhr_et", "rth", "range_used", "tempo15", "gap_sig", "vortag_range_sig", "event_1d_9d", "curve_9d_30d", "iv_rang",
      "gegenseite_beruehrt", "vwap_abst_sig", "erste30_mit", "wochentag", "n_konfluenz"] + [c for c in E.columns if c.startswith("k_")]
eff, mod = [], []
for (mk, mode), g in E.groupby(["Markt", "Modus"]):
    for art in ("Zone", "Kontrolle"):
        x = g[(g["Art"] == art) & (g["Zeitraum"] == "Explore")]
        w, l = x[x["y"] == 1], x[x["y"] == 0]
        for f in FE:
            a, b = w[f].astype(float), l[f].astype(float); sd = x[f].astype(float).std()
            eff.append(dict(Markt=mk, Modus=mode, Art=art, Merkmal=f, Ø_Extrem=round(a.mean(), 3), Ø_durchbrochen=round(b.mean(), 3),
                            Effekt_SD=round((a.mean() - b.mean()) / sd, 3) if sd > 0 else np.nan, n_Extrem=len(w), Grundrate=round(x["y"].mean(), 3)))
    z = g[g["Art"] == "Zone"]; ex, va = z[z["Zeitraum"] == "Explore"], z[z["Zeitraum"] == "Validate"]
    if len(va) < 100 or va["y"].nunique() < 2:
        continue
    m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=200, random_state=0)
    m.fit(ex[FE].astype(float), ex["y"])
    pe, pv = m.predict_proba(ex[FE].astype(float))[:, 1], m.predict_proba(va[FE].astype(float))[:, 1]
    top = pv >= np.quantile(pe, 0.9)
    mod.append(dict(Markt=mk, Modus=mode, Berührungen_Explore=len(ex), Berührungen_Validate=len(va),
                    Grundrate_Validate=round(va["y"].mean(), 3), AUC_Explore=round(roc_auc_score(ex["y"], pe), 3),
                    AUC_Validate=round(roc_auc_score(va["y"], pv), 3), Top10_n=int(top.sum()),
                    Top10_wurde_Extrem=round(va["y"][top].mean(), 3) if top.sum() else np.nan,
                    Top10_fade1_EW_R=round(va["fade1"][top].mean(), 3) if top.sum() else np.nan,
                    Top10_fade2_EW_R=round(va["fade2"][top].mean(), 3) if top.sum() else np.nan))
EF, MO = pd.DataFrame(eff), pd.DataFrame(mod)
EF.to_csv(RES / "gz_d_extremes_effects.csv", index=False); MO.to_csv(RES / "gz_d_extremes_model.csv", index=False)
pd.set_option("display.width", 230)
z = EF[EF["Art"] == "Zone"]; k = EF[EF["Art"] == "Kontrolle"].set_index(["Markt", "Modus", "Merkmal"])["Effekt_SD"]
z = z.assign(Effekt_Kontrolle=k.reindex(pd.MultiIndex.from_frame(z[["Markt", "Modus", "Merkmal"]])).to_numpy())
agg = z.groupby("Merkmal").agg(Effekt_Zone=("Effekt_SD", "mean"), Effekt_Kontrolle=("Effekt_Kontrolle", "mean"),
                               gleiches_Vorzeichen=("Effekt_SD", lambda s: int((np.sign(s) == np.sign(s.mean())).sum())), von=("Effekt_SD", "size"))
print(agg.sort_values("Effekt_Zone", key=abs, ascending=False).round(3).to_string())
print(z[z["Merkmal"] == "k"][["Markt", "Modus", "n_Extrem", "Grundrate"]].to_string(index=False))
print(MO.to_string(index=False))
