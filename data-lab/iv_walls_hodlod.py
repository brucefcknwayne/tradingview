"""
IV Walls: Wie oft liegt das Tageshoch / Tagestief IN einer Zone (die Reaktion an der Zone war die Tageswende)?

Zonen und σ wie in iv_walls_deep.py (Anker 18:00-Open, σ = Anker·IV/100/√252, Zonen ±0,5/1/1,5/2σ, Höhe ±5 % σ).
Obere Zonen ↔ Tageshoch, untere Zonen ↔ Tagestief. „In der Zone“ = das Extrem liegt innerhalb [Level ± 0,05σ].
Zum Vergleich gleich breite Kontroll-Bänder bei ±0,25/0,75/1,25/1,75σ: Liegen dort ähnlich viele Extreme, ist die Zone nicht besonders.
Zwei Sichten: ganzer Handelstag (18:00–17:00) und nur New York (09:30–16:00, Extreme dieser Session).
Je Level: Anteil aller Tage · Anteil der Tage, an denen das Level berührt wurde („wenn berührt, war es das Extrem“).

Aufruf: python data-lab/iv_walls_hodlod.py   → results/iv_walls_hodlod.md
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
_src = (HERE / "iv_walls_deep.py").read_text().split("acc, acc_by, hourly, react, conf, best = [], [], [], [], [], []")[0]
ns = {"__file__": str(HERE / "iv_walls_deep.py")}
exec(_src, ns)
MARKETS, MODES, ZONES, CONTROLS, ZH = ns["MARKETS"], ns["MODES"], ns["ZONES"], ns["CONTROLS"], ns["ZH"]
VIEWS = {"Tag 18–17": (0, ns["NCOL"]), "NY 09:30–16": (930, 1320)}

rows = []
for mk in MARKETS:
    dts, G, anchor_day = ns["load"](mk)
    IVv, ev = ns["iv_at"](mk, anchor_day, dts)
    end = dts.max()
    per = {"3J": np.asarray(dts > end - pd.DateOffset(years=3)), "Alles": np.ones(len(dts), bool)}
    ref = G["open"][:, 0]
    base = np.isfinite(ref) & (np.isfinite(G["high"]).mean(1) >= 0.6) & (dts.weekday < 5)
    for vname, (a, b) in VIEWS.items():
        with np.errstate(all="ignore"):
            XH, XL = np.nanmax(G["high"][:, a:b], 1), np.nanmin(G["low"][:, a:b], 1)
        vb = base & np.isfinite(XH)
        for mi, mode in enumerate(MODES):
            sig = ref * IVv[:, mi] / 100 / np.sqrt(252)
            ok = vb & np.isfinite(sig) & (sig > 0)
            if ok.sum() < 200:
                continue
            hpos, lpos = (XH - ref) / sig, (ref - XL) / sig          # Lage der Extreme in σ (vom Anker weg positiv)
            for pn, pm in per.items():
                m = ok & pm
                if m.sum() < 100:
                    continue
                for art, levels in (("Zone", ZONES), ("Kontrolle", CONTROLS)):
                    anyH = np.zeros(len(dts), bool); anyL = np.zeros(len(dts), bool)
                    for k in levels:
                        for side, pos in (("Hoch", hpos), ("Tief", lpos)):
                            inz = np.abs(pos - k) <= ZH
                            touched = pos >= k - ZH
                            if side == "Hoch":
                                anyH |= inz
                            else:
                                anyL |= inz
                            rows.append(dict(Markt=mk, Modus=mode, Sicht=vname, Zeitraum=pn, Art=art, Level=(k if side == "Hoch" else -k),
                                             Extrem=("Tageshoch" if side == "Hoch" else "Tagestief"), Tage=int(m.sum()),
                                             **{"berührt %": round(100 * touched[m].mean(), 1),
                                                "Extrem in Zone (alle Tage) %": round(100 * inz[m].mean(), 1),
                                                "Extrem in Zone, wenn berührt %": round(100 * inz[m & touched].mean(), 1) if (m & touched).sum() >= 20 else np.nan,
                                                "Berührungen": int((m & touched).sum())}))
                    rows.append(dict(Markt=mk, Modus=mode, Sicht=vname, Zeitraum=pn, Art=art, Level="alle", Extrem="Summe", Tage=int(m.sum()),
                                     **{"Hoch in einer Zone %": round(100 * anyH[m].mean(), 1), "Tief in einer Zone %": round(100 * anyL[m].mean(), 1),
                                        "Hoch oder Tief in einer Zone %": round(100 * (anyH | anyL)[m].mean(), 1)}))
    print(mk, "fertig", flush=True)

X = pd.DataFrame(rows)
X.to_csv(HERE / "results/iv_walls_hodlod.csv", index=False)
S = X[X["Level"] == "alle"]
L = X[X["Level"] != "alle"]


def piv(df, val):
    return df.pivot_table(index=["Markt", "Modus", "Extrem"], columns="Level", values=val).to_markdown()


md = ["# IV Walls: Liegt das Tageshoch / Tagestief in einer Zone?", "",
      "„In der Zone“ = Extrem innerhalb Level ± 0,05σ (Zonenhöhe wie im Indikator). Kontroll-Bänder gleich breit bei ±0,25/0,75/1,25/1,75σ.",
      "Hauptwerte: letzte 3 Jahre. Modus 1D erst ab Mai 2022, GC nur 30D.", "",
      "## 1) Wie oft liegt das Extrem in IRGENDEINER Zone? (vs. gleich viele Kontroll-Bänder)", ""]
for v in VIEWS:
    s = S[(S["Sicht"] == v) & (S["Zeitraum"] == "3J")]
    md += [f"### {v}", "", s.pivot_table(index=["Markt", "Modus"], columns="Art",
                                           values=["Hoch in einer Zone %", "Tief in einer Zone %", "Hoch oder Tief in einer Zone %"]).round(1).to_markdown(), ""]
# fairer Vergleich: jede Zone gegen den Schnitt ihrer direkten Nachbar-Bänder (k ± 0,25σ)
fair = []
L3 = L[L["Zeitraum"] == "3J"].copy()
L3["absk"] = L3["Level"].astype(float).abs()
for (mk_, mo, vi, ex), g in L3.groupby(["Markt", "Modus", "Sicht", "Extrem"]):
    gi = g.set_index("absk")
    for k in ZONES:
        nb = [x for x in (k - 0.25, k + 0.25) if x in gi.index]
        if k not in gi.index or not nb:
            continue
        fair.append(dict(Markt=mk_, Modus=mo, Sicht=vi, Extrem=ex, Zone=k,
                         **{"Zone: Extrem dort (alle Tage) %": gi.loc[k, "Extrem in Zone (alle Tage) %"],
                            "Nachbarn: Extrem dort (alle Tage) %": round(gi.loc[nb, "Extrem in Zone (alle Tage) %"].mean(), 1),
                            "Zone: wenn berührt %": gi.loc[k, "Extrem in Zone, wenn berührt %"],
                            "Nachbarn: wenn berührt %": round(gi.loc[nb, "Extrem in Zone, wenn berührt %"].mean(), 1)}))
F = pd.DataFrame(fair)
F["Differenz (alle Tage) Pkt"] = (F["Zone: Extrem dort (alle Tage) %"] - F["Nachbarn: Extrem dort (alle Tage) %"]).round(1)
F.to_csv(HERE / "results/iv_walls_hodlod_fair.csv", index=False)
md += ["## 1b) Fairer Vergleich: Zone vs. direkte Nachbar-Bänder (gleich breit, ±0,25σ daneben; 3J)", "",
       "Extreme liegen nahe am Open grundsätzlich häufiger. Deshalb jede Zone nur mit ihren Nachbarn vergleichen.", "",
       F.groupby(["Sicht", "Markt"])[["Zone: Extrem dort (alle Tage) %", "Nachbarn: Extrem dort (alle Tage) %", "Differenz (alle Tage) Pkt"]].mean().round(2).to_markdown(), "",
       F.to_markdown(index=False), ""]
md += ["## 2) Je Level: Wenn das Level berührt wurde – wie oft war es das Extrem? (3J)", ""]
for v in VIEWS:
    l = L[(L["Sicht"] == v) & (L["Zeitraum"] == "3J")]
    md += [f"### {v}", "", piv(l, "Extrem in Zone, wenn berührt %"), "", "Anteil aller Tage, an denen das Extrem dort lag:", "",
           piv(l, "Extrem in Zone (alle Tage) %"), "", "Wie oft wurde das Level überhaupt berührt (%):", "", piv(l, "berührt %"), ""]
md += ["## 3) Stabilität seit 2011 (Tag 18–17, Summe)", "",
       S[(S["Sicht"] == "Tag 18–17") & (S["Zeitraum"] == "Alles")].pivot_table(index=["Markt", "Modus"], columns="Art",
                                                                               values=["Hoch oder Tief in einer Zone %"]).round(1).to_markdown(), ""]
(HERE / "results/iv_walls_hodlod.md").write_text("\n".join(md))
print("\n".join(md[:40]))
