"""
Gotham Zones: Reaktion in Punkten je σ-Level und Modus.

- Zone = Level ± 5 % von σ (wie im Indikator)
- Zonenanfang = Kante, die der Preis zuerst erreicht (obere Zone: Unterkante, untere Zone: Oberkante)
- Touch = erster Bar, der den Zonenanfang erreicht
- Bruch = erster Docht jenseits der anderen Kante (kein Close nötig)
- Reaktion = größte Bewegung weg vom Zonenanfang zwischen Touch und Bruch (oder Session-Ende).
  Bars, in denen der Bruch passiert, zählen nicht mit (Reihenfolge im Bar unbekannt).

Aufruf: python data-lab/gotham_zones_reaction.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/gotham_zones_reaction.md"
ZONE_PCT = 0.05
LEVELS = [2.0, 1.5, 1.0, 0.5, -0.5, -1.0, -1.5, -2.0]
CONTROLS = [1.75, 1.25, 0.75, 0.25, -0.25, -0.75, -1.25, -1.75]
MODES = ["1D", "9D", "30D"]
THRESH = [25, 50, 100, 150]


def load_iv(name):
    df = pd.read_csv(HERE / f"data/iv/{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    df["DATE"] = pd.to_datetime(df["DATE"]).astype("datetime64[ns]")
    return df.set_index("DATE")["CLOSE"].astype(float).rename(name)


iv = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX9D", "VIX1D"]], axis=1, sort=True)
scale = iv["VXN"] / iv["VIX"]
iv_mode = pd.DataFrame({"1D": iv["VIX1D"] * scale, "9D": iv["VIX9D"] * scale, "30D": iv["VXN"]})

nq = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / "data/nq_1m/*.parquet"))))
nq = nq.sort_values("ts_utc").reset_index(drop=True)
sess = nq.groupby("session_date", sort=True).indices
anchors = nq.groupby("session_date")["ts_et"].first()
anchor_day = pd.to_datetime(anchors.dt.tz_localize(None).dt.date).astype("datetime64[ns]")
iv_at = pd.merge_asof(
    pd.DataFrame({"anchor_day": anchor_day.values, "session_date": anchors.index}).sort_values("anchor_day"),
    iv_mode.reset_index().rename(columns={"DATE": "iv_day"}).dropna(subset=["30D"]),
    left_on="anchor_day", right_on="iv_day", direction="backward",
).set_index("session_date")
iv_at.loc[(iv_at["anchor_day"] - iv_at["iv_day"]).dt.days > 5, MODES] = np.nan

H, L, O = (nq[c].to_numpy() for c in ["high", "low", "open"])
TS = nq["ts_et"]

rows = []
for sd, idx in sess.items():
    if len(idx) < 300:
        continue
    a, b = idx[0], idx[-1] + 1
    h, l, ref = H[a:b], L[a:b], O[a]
    for mode in MODES:
        v = iv_at.at[sd, mode] if sd in iv_at.index else np.nan
        if not np.isfinite(v) or v <= 0:
            continue
        sig = ref * v / 100 / np.sqrt(252)
        hh = sig * ZONE_PCT
        for k in LEVELS + CONTROLS:
            lvl = ref + k * sig
            if k > 0:   # obere Zone: von unten
                start, far = lvl - hh, lvl + hh
                reach, through, away = h >= start, h > far, start - l
            else:       # untere Zone: von oben
                start, far = lvl + hh, lvl - hh
                reach, through, away = l <= start, l < far, h - start
            r = dict(session_date=sd, mode=mode, k=k, control=k in CONTROLS, sig=sig, zone_pts=2 * hh)
            t0 = np.argmax(reach) if reach.any() else -1
            r["touch"] = t0 >= 0
            if t0 >= 0:
                br = np.flatnonzero(through[t0:])
                tb = t0 + br[0] if len(br) else len(h)
                r["broken"] = len(br) > 0
                r["mins_to_break"] = tb - t0 if len(br) else np.nan
                seg = away[t0 + 1:tb]
                r["reaction"] = max(seg.max(), 0.0) if len(seg) else 0.0
                r["mins_to_max"] = int(np.argmax(seg)) + 1 if len(seg) and seg.max() > 0 else 0
                r["touch_hour"] = TS.iat[a + t0].hour
            rows.append(r)

z = pd.DataFrame(rows)
z["year"] = pd.to_datetime(z["session_date"]).dt.year
z["reaction_sig"] = z["reaction"] / z["sig"]


def table(g, pts=True):
    col = "reaction" if pts else "reaction_sig"
    unit = "Pkt" if pts else "% σ"
    mul = 1 if pts else 100
    head = ["Level", "Tage", "Touch %", "Docht-Bruch %", f"Median {unit}", f"Ø {unit}", f"25 % {unit}",
            f"75 % {unit}", f"90 % {unit}", "Sofort gebrochen %"]
    if pts:
        head += [f"≥{x} Pkt %" for x in THRESH]
    head += ["Median Min bis Bruch", "Median Min bis Max-Reaktion"]
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for k in sorted(g["k"].unique(), reverse=True):
        a = g[g["k"] == k]
        t = a[a["touch"]]
        if t.empty:
            continue
        x = t[col] * mul
        cells = [f"{k:+.1f}σ" if k * 10 % 5 == 0 and not a["control"].iat[0] else f"{k:+.2f}σ", str(len(a)),
                 f"{100 * a['touch'].mean():.1f}", f"{100 * t['broken'].astype(bool).mean():.1f}",
                 f"{x.median():.0f}" if pts else f"{x.median():.1f}", f"{x.mean():.0f}" if pts else f"{x.mean():.1f}",
                 f"{x.quantile(.25):.0f}" if pts else f"{x.quantile(.25):.1f}",
                 f"{x.quantile(.75):.0f}" if pts else f"{x.quantile(.75):.1f}",
                 f"{x.quantile(.9):.0f}" if pts else f"{x.quantile(.9):.1f}",
                 f"{100 * (t['reaction'] == 0).mean():.1f}"]
        if pts:
            cells += [f"{100 * (t['reaction'] >= th).mean():.0f}" for th in THRESH]
        cells += [f"{t['mins_to_break'].median():.0f}", f"{t['mins_to_max'].median():.0f}"]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


common = z.groupby("session_date")["mode"].nunique()
common = set(common[common == len(MODES)].index)
zc = z[z["session_date"].isin(common)]
zr = z[~z["control"]]

md = ["# Gotham Zones – Reaktion in Punkten", "",
      "Gemessen vom **Zonenanfang** (erste berührte Kante) bis die Zone per **Docht** durchbrochen ist "
      "oder die Session endet. Reaktion = größte Bewegung weg von der Zone in diesem Zeitraum.", "",
      f"## Punkte, gemeinsamer Zeitraum {min(common)} – {max(common)} (alle 3 Modi)", ""]
for m in MODES:
    g = zc[(zc["mode"] == m) & ~zc["control"]]
    zh = g["zone_pts"].median()
    md += [f"### {m}  (Zonenhöhe Median {zh:.0f} Pkt, 1σ Median {g['sig'].median():.0f} Pkt)", "", table(g), ""]

md += ["## In % von σ, voller Zeitraum je Modus (vergleichbar über alle Jahre)", ""]
for m in MODES:
    g = zr[zr["mode"] == m]
    md += [f"### {m}  ({g['session_date'].min()} – {g['session_date'].max()})", "", table(g, pts=False), ""]

md += ["## Median Reaktion in Punkten je Jahr (nur berührte Zonen, beide Seiten zusammen)", ""]
t = zr[zr["touch"]].assign(absk=zr["k"].abs())
p = t.pivot_table(index="year", columns=["mode", "absk"], values="reaction", aggfunc="median").round(0)
p.columns = [f"{m} ±{k:g}σ" for m, k in p.columns]
md += [p.to_markdown(), ""]

md += ["## Vergleich: Kontroll-Levels zwischen den Zonen (gemeinsamer Zeitraum, Punkte)", "",
       "Gleiche Messung an Levels, die der Indikator nicht zeichnet. Ähnliche Werte = Reaktion ist normale NQ-Bewegung, "
       "kein Zonen-Effekt.", ""]
for m in MODES:
    g = zc[zc["mode"] == m]
    md += [f"### {m}", "", table(g), ""]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
z.to_parquet(HERE / "results/gotham_zones_reaction.parquet", index=False)
print("\n".join(md[:40]))
