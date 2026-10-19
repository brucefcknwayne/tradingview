"""
H7 Teil B – Strategie-Suche NUR auf Explore (bis 2024-12-31). Validate-Daten werden hier nicht gelesen.

Für jede Kombination Markt × Modus × Vorlage (fade1/fade2/brk1) und jede Bedingung (Bias/Konfluenz):
EW in R nach Kosten an Gotham-Zonen UND an Kontroll-Levels (Gegenprobe), Jahres-Konsistenz, Zählung aller Varianten.
Kandidaten-Regel (vorab festgelegt, H7): EW > 0, positiv in jedem Explore-Jahr mit ≥ 30 Trades (mind. 2 solche Jahre),
gleiches Vorzeichen in ≥ 2 Märkten, Mechanismus benennbar (manuell).

Aufruf: python research/gz_b_explore.py → research/results/gz_b_slices.csv, gz_b_report.md
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research/results"
E = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(ROOT / "data-lab/data/raw/gz_cache/gz_b_events_*.parquet"))))
E = E[E["Zeitraum"] == "Explore"].copy()           # Validate bleibt ungesehen
E["uhrblock"] = pd.cut((E["t"] + 1080) % 1440, [0, 120, 480, 570, 720, 960, 1020, 1440], right=False,
                       labels=["00-02", "02-08", "08-09:30", "09:30-12", "12-16", "16-17", "18-24"]).astype(str)
E["mehrfach_konfl_2+"] = E["n_konfluenz"] >= 2
E["mehrfach_konfl_3+"] = E["n_konfluenz"] >= 3
BIN = ["rth", "gegenseite_beruehrt", "erste30_mit", "mehrfach_konfl_2+", "mehrfach_konfl_3+"] + [c for c in E.columns if c.startswith("k_")]
CONT = ["range_used", "tempo15", "gap_sig", "vortag_range_sig", "event_1d_9d", "curve_9d_30d", "iv_rang", "vwap_abst_sig"]
CAT = ["uhrblock", "wochentag", "k"]
TPL = ["fade1", "fade2", "brk1"]


def slices(df):
    """Bedingungen als (Name, Maske) – Terzil-Grenzen aus den Zonen-Ereignissen dieses Markts/Modus."""
    z = df["Art"] == "Zone"
    out = [("alle", np.ones(len(df), bool))]
    for c in BIN:
        v = df[c]
        if v.isna().all():
            continue
        out += [(f"{c}=ja", (v == 1).to_numpy()), (f"{c}=nein", (v == 0).to_numpy())]
    for c in CONT:
        x = df[c].astype(float)
        q = np.nanquantile(x[z], [1 / 3, 2 / 3]) if x[z].notna().sum() > 100 else None
        if q is None or not np.all(np.isfinite(q)):
            continue
        out += [(f"{c}<=T1({q[0]:.2f})", (x <= q[0]).to_numpy()), (f"{c} T2", ((x > q[0]) & (x <= q[1])).to_numpy()), (f"{c}>T2({q[1]:.2f})", (x > q[1]).to_numpy())]
    for c in CAT:
        for v in sorted(df[c].dropna().unique()):
            out.append((f"{c}={v}", (df[c] == v).to_numpy()))
    return out


rows = []
for (mk, mode), df in E.groupby(["Markt", "Modus"]):
    df = df.reset_index(drop=True)
    zone = (df["Art"] == "Zone").to_numpy(); ctrl = ~zone
    yrs = df["Jahr"].to_numpy()
    for name, m in slices(df):
        for tp in TPL:
            r = df[tp].to_numpy(float)
            for art, am in (("Zone", zone), ("Kontrolle", ctrl)):
                s = m & am & np.isfinite(r)
                if s.sum() < 30:
                    continue
                x = r[s]
                yr = pd.Series(x).groupby(yrs[s]).agg(["mean", "size"])
                big = yr[yr["size"] >= 30]
                rows.append(dict(Markt=mk, Modus=mode, Vorlage=tp, Bedingung=name, Art=art, n=int(s.sum()),
                                 EW_R=round(x.mean(), 4), t=round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2) if len(x) > 1 else np.nan,
                                 Treffer=round((x > 0).mean(), 3), Jahre_30=len(big), Jahre_pos=int((big["mean"] > 0).sum()),
                                 schlechtestes_Jahr=round(big["mean"].min(), 3) if len(big) else np.nan))
    print(mk, mode, flush=True)

S = pd.DataFrame(rows)
S.to_csv(RES / "gz_b_slices.csv", index=False)
Z = S[S["Art"] == "Zone"].copy(); K = S[S["Art"] == "Kontrolle"].set_index(["Markt", "Modus", "Vorlage", "Bedingung"])
Z["EW_Kontrolle"] = K["EW_R"].reindex(pd.MultiIndex.from_frame(Z[["Markt", "Modus", "Vorlage", "Bedingung"]])).to_numpy()
Z["Zone−Kontrolle"] = Z["EW_R"] - Z["EW_Kontrolle"]
n_var = len(Z)
# Kandidaten-Regel
Z["konsistent"] = (Z["EW_R"] > 0) & (Z["Jahre_30"] >= 2) & (Z["Jahre_pos"] == Z["Jahre_30"])
Z["Modus_typ"] = Z["Modus"].replace({"GVZ": "30D"})
pos = Z[Z["EW_R"] > 0].groupby(["Modus_typ", "Vorlage", "Bedingung"])["Markt"].nunique().rename("Märkte_pos")
Z = Z.join(pos, on=["Modus_typ", "Vorlage", "Bedingung"])
Z["Märkte_pos"] = Z["Märkte_pos"].fillna(0).astype(int)
Z["Kandidat"] = Z["konsistent"] & (Z["Märkte_pos"] >= 2)
Z.to_csv(RES / "gz_b_zone_slices.csv", index=False)

base = Z[Z["Bedingung"] == "alle"][["Markt", "Modus", "Vorlage", "n", "EW_R", "EW_Kontrolle", "Treffer", "Jahre_30", "Jahre_pos"]]
top = Z.sort_values("t", ascending=False).head(40)
cand = Z[Z["Kandidat"]].sort_values("t", ascending=False)
md = ["# H7 Teil B – Strategie-Suche (nur Explore bis 2024)", "",
      f"Varianten insgesamt (Zonen-Bedingungen × Markt × Modus × Vorlage): **{n_var}** – bei so vielen Versuchen sind zufällige „Treffer“ sicher.", "",
      "## Grundlage: alle Berührungen (EW in R nach Kosten)", "", base.to_markdown(index=False), "",
      "## Top 40 nach t-Wert (Zonen) – mit Gegenprobe an Kontroll-Levels", "",
      top[["Markt", "Modus", "Vorlage", "Bedingung", "n", "EW_R", "t", "Treffer", "Jahre_30", "Jahre_pos", "EW_Kontrolle", "Zone−Kontrolle", "Märkte_pos", "Kandidat"]].to_markdown(index=False), "",
      f"## Kandidaten nach Vorab-Regel ({len(cand)})", "",
      cand[["Markt", "Modus", "Vorlage", "Bedingung", "n", "EW_R", "t", "Jahre_30", "Jahre_pos", "schlechtestes_Jahr", "EW_Kontrolle", "Zone−Kontrolle", "Märkte_pos"]].to_markdown(index=False), ""]
(RES / "gz_b_report.md").write_text("\n".join(md))
print("Varianten:", n_var, "Kandidaten:", len(cand))
print(base.to_string())
print(cand.head(30)[["Markt", "Modus", "Vorlage", "Bedingung", "n", "EW_R", "t", "Jahre_30", "Jahre_pos", "EW_Kontrolle", "Märkte_pos"]].to_string())
