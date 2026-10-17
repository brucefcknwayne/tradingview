"""
Gotham Zones Statistik (NQ 1m, 2010-2026)

Nachbau des Indikators:
- Anker = erster Bar des Handelstags (18:00 ET), ref = dessen Open
- σ = ref * IV/100 / sqrt(252)
- 1D  = VIX1D * VXN/VIX, 9D = VIX9D * VXN/VIX, 30D = VXN
- IV = letzter Cboe-Tagesschluss vor dem Anker (um 18:00 ET ist das der 16:15-Close)
- Zonen bei ±0.5/1/1.5/2σ, Höhe ± 5 % von σ
- Kontroll-Levels bei ±0.25/0.75/1.25/1.75σ (gleiche Logik, keine Zone im Indikator)

Pro Zone und Tag:
- touch     = Preis erreicht die Zone (Docht reicht)
- break     = ein 1m-Close jenseits der Zone (bis Session-Ende)
- held      = berührt, aber kein Close jenseits
- pierce    = Docht jenseits der Zone
- race      = nach Touch: zuerst 0.25σ Reaktion weg vom Level oder 0.25σ durch (gleicher Bar = durch)
- MFE/MAE   = max. Reaktion / max. Gegenbewegung nach Touch in 15/30/60 Min und bis Session-Ende
- HOD/LOD   = Tageshoch/-tief liegt in der Zone

Aufruf: python data-lab/gotham_zones_stats.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
IV_DIR = HERE / "data/iv"
OUT = HERE / "results/gotham_zones.md"
ZONE_PCT = 0.05
ZONES = [0.5, 1.0, 1.5, 2.0]
CONTROLS = [0.25, 0.75, 1.25, 1.75]
RACE = 0.25
WINDOWS = [15, 30, 60]
MODES = ["1D", "9D", "30D"]


def load_iv(name):
    df = pd.read_csv(IV_DIR / f"{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    df["DATE"] = pd.to_datetime(df["DATE"]).astype("datetime64[ns]")
    return df.set_index("DATE")["CLOSE"].astype(float).rename(name)


iv = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX9D", "VIX1D"]], axis=1).sort_index()
scale = iv["VXN"] / iv["VIX"]
iv_mode = pd.DataFrame({
    "1D": iv["VIX1D"] * scale,
    "9D": iv["VIX9D"] * scale,
    "30D": iv["VXN"],
})

nq = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / "data/nq_1m/*.parquet"))))
nq = nq.sort_values("ts_utc").reset_index(drop=True)

# Sessions
sess = nq.groupby("session_date", sort=True).indices
anchors = nq.groupby("session_date")["ts_et"].first()
# IV-Wert: letzter Tagesschluss mit Datum <= Kalendertag des Ankers
anchor_day = pd.to_datetime(anchors.dt.tz_localize(None).dt.date).astype("datetime64[ns]")
iv_at = pd.merge_asof(
    pd.DataFrame({"anchor_day": anchor_day.values, "session_date": anchors.index}).sort_values("anchor_day"),
    iv_mode.reset_index().rename(columns={"DATE": "iv_day"}).dropna(subset=["30D"]),
    left_on="anchor_day", right_on="iv_day", direction="backward",
).set_index("session_date")
# veralteter IV-Wert (> 5 Tage) = keine Daten
iv_at.loc[(iv_at["anchor_day"] - iv_at["iv_day"]).dt.days > 5, MODES] = np.nan

H, L, C, O = (nq[c].to_numpy() for c in ["high", "low", "close", "open"])
MIN = nq["ts_et"].dt.hour.to_numpy() * 60 + nq["ts_et"].dt.minute.to_numpy()
RTH = nq["rth"].to_numpy()


def first(mask):
    i = np.flatnonzero(mask)
    return i[0] if len(i) else -1


rows, days = [], []
for sd, idx in sess.items():
    if len(idx) < 300:  # verkürzte Feiertags-Sessions raus
        continue
    a, b = idx[0], idx[-1] + 1
    h, l, c = H[a:b], L[a:b], C[a:b]
    ref = O[a]
    hod, lod = h.max(), l.min()
    for mode in MODES:
        v = iv_at.at[sd, mode] if sd in iv_at.index else np.nan
        if not np.isfinite(v) or v <= 0:
            continue
        sig = ref * v / 100 / np.sqrt(252)
        hh = sig * ZONE_PCT
        days.append(dict(session_date=sd, mode=mode, sig=sig, ref=ref,
                         hod_s=(hod - ref) / sig, lod_s=(ref - lod) / sig, close_s=(c[-1] - ref) / sig))
        for k in ZONES + CONTROLS:
            for side in (1, -1):
                lvl = ref + side * k * sig
                # in "Richtung Zone"-Koordinaten: x > 0 = jenseits des Levels
                far = (h - lvl) if side == 1 else (lvl - l)     # Docht Richtung Zone
                back = (lvl - l) if side == 1 else (h - lvl)    # Bewegung zurück
                cl = (c - lvl) * side
                ext = hod if side == 1 else lod
                r = dict(session_date=sd, mode=mode, k=k * side, control=k in CONTROLS, sig=sig,
                         in_zone_ext=abs(ext - lvl) <= hh)
                i0 = first(far >= -hh)
                r["touch"] = i0 >= 0
                if i0 >= 0:
                    ib = first(cl[i0:] > hh)
                    r["break"] = ib >= 0
                    r["pierce"] = bool((far[i0:] > hh).any())
                    r["rth_touch"] = bool(RTH[a + i0])
                    r["touch_hour"] = MIN[a + i0] // 60
                    r["mins_to_break"] = ib if ib >= 0 else np.nan
                    # Race
                    up = first(far[i0:] >= RACE * sig)
                    dn = first(back[i0 + 1:] >= RACE * sig)
                    dn = dn + 1 if dn >= 0 else -1
                    if up < 0 and dn < 0:
                        r["race"] = np.nan
                    else:
                        r["race"] = float(dn >= 0 and (up < 0 or dn < up))
                    # MFE / MAE in σ
                    for w in WINDOWS:
                        seg_b = back[i0 + 1:i0 + 1 + w]
                        r[f"mfe{w}"] = max(seg_b.max(), 0) / sig if len(seg_b) else 0.0
                        r[f"mae{w}"] = max(far[i0:i0 + 1 + w].max(), 0) / sig
                    r["mfe_eod"] = max(back[i0 + 1:].max(), 0) / sig if i0 + 1 < len(back) else 0.0
                    r["mae_eod"] = max(far[i0:].max(), 0) / sig
                    end = i0 + ib if ib >= 0 else len(back)
                    r["mfe_before_break"] = max(back[i0 + 1:end].max(), 0) / sig if end > i0 + 1 else 0.0
                rows.append(r)

z = pd.DataFrame(rows)
d = pd.DataFrame(days)


def pct(x):
    return f"{100 * np.nanmean(x):.1f}" if len(x) else "-"


def med(x):
    return f"{np.nanmedian(x):.2f}" if len(x) else "-"


def zone_table(z, d):
    out = ["| Level | Tage | Touch % | Gehalten % | Durch-Docht gehalten % | Bruch % | Reaktion 0.25σ zuerst % "
           "| MFE 30m σ | MAE 30m σ | MFE bis Bruch σ | HOD/LOD in Zone % | HOD/LOD in Zone bei Touch % | Touch in RTH % |",
           "|" + "---|" * 13]
    for k in sorted(z["k"].unique(), reverse=True):
        g = z[z["k"] == k]
        t = g[g["touch"]]
        name = f"{k:+.2f}σ" + (" (Kontrolle)" if g["control"].iat[0] else "")
        held = ~t["break"].astype(bool)
        out.append("| " + " | ".join([
            name, str(len(g)), pct(g["touch"]), pct(held),
            pct(held & t["pierce"].astype(bool)), pct(t["break"].astype(bool)),
            pct(t["race"].dropna()), med(t["mfe30"]), med(t["mae30"]), med(t["mfe_before_break"]),
            pct(g["in_zone_ext"]), pct(t["in_zone_ext"]), pct(t["rth_touch"].astype(bool)),
        ]) + " |")
    return "\n".join(out)


def range_table(d):
    out = ["| | Tage | σ Median (Pkt, letzte 250 Tage) | HOD ≤ +1σ % | LOD ≥ −1σ % | Range in ±1σ % "
           "| Range in ±2σ % | Close in ±0.5σ % | HOD Median σ | LOD Median σ |", "|" + "---|" * 10]
    for m in MODES:
        g = d[d["mode"] == m]
        if g.empty:
            continue
        out.append("| " + " | ".join([
            m, str(len(g)), f"{g['sig'].tail(250).median():.0f}",
            pct(g["hod_s"] <= 1), pct(g["lod_s"] <= 1),
            pct((g["hod_s"] <= 1) & (g["lod_s"] <= 1)), pct((g["hod_s"] <= 2) & (g["lod_s"] <= 2)),
            pct(g["close_s"].abs() <= 0.5), med(g["hod_s"]), med(g["lod_s"]),
        ]) + " |")
    return "\n".join(out)


def ext_dist(d):
    bins = [0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, np.inf]
    labels = ["0–0.25", "0.25–0.5", "0.5–0.75", "0.75–1", "1–1.25", "1.25–1.5", "1.5–1.75", "1.75–2", "2–2.5", ">2.5"]
    out = ["| HOD/LOD-Abstand vom Open (σ) | " + " | ".join(MODES) + " |", "|" + "---|" * (len(MODES) + 1)]
    cols = {}
    for m in MODES:
        g = d[d["mode"] == m]
        ext = pd.concat([g["hod_s"], g["lod_s"]]).clip(lower=0)
        cols[m] = pd.cut(ext, bins, labels=labels, right=False).value_counts(normalize=True).reindex(labels) * 100
    for lab in labels:
        out.append(f"| {lab} | " + " | ".join(f"{cols[m][lab]:.1f}" for m in MODES) + " |")
    return "\n".join(out)


def by_year(z):
    g = z[~z["control"] & z["touch"]].copy()
    g["year"] = pd.to_datetime(g["session_date"]).dt.year
    g["absk"] = g["k"].abs()
    g["held"] = ~g["break"].astype(bool)
    t = g.pivot_table(index="year", columns=["mode", "absk"], values="held", aggfunc="mean") * 100
    t.columns = [f"{m} ±{k:g}σ" for m, k in t.columns]
    return t.round(1).to_markdown()


def by_session(z):
    g = z[~z["control"] & z["touch"]].copy()
    g["held"] = ~g["break"].astype(bool)
    g["absk"] = g["k"].abs()
    g["teil"] = np.where(g["rth_touch"].astype(bool), "RTH", "ETH")
    t = g.pivot_table(index=["mode", "absk"], columns="teil", values="held", aggfunc=["mean", "size"])
    t.columns = [f"{'Gehalten %' if a == 'mean' else 'n'} {b}" for a, b in t.columns]
    for col in t.columns:
        if col.startswith("Gehalten"):
            t[col] = (t[col] * 100).round(1)
    return t.to_markdown()


common = d.groupby("session_date")["mode"].nunique()
common = set(common[common == len(MODES)].index)

md = ["# Gotham Zones – Statistik NQ 1m", "",
      f"Daten: {d['session_date'].min()} bis {d['session_date'].max()}. "
      "Definitionen siehe Kopf von `gotham_zones_stats.py`. Alle Prozent bei Touch-Spalten beziehen sich auf berührte Zonen.", ""]
for title, zz, dd in [
    ("Gemeinsamer Zeitraum (alle 3 Modi verfügbar)", z[z["session_date"].isin(common)], d[d["session_date"].isin(common)]),
    ("Voller Zeitraum je Modus", z, d),
]:
    md += [f"## {title}", "", "### Tagesrange vs. σ", "", range_table(dd), "", ext_dist(dd), ""]
    for m in MODES:
        g = zz[zz["mode"] == m]
        if g.empty:
            continue
        md += [f"### {m}", "", zone_table(g, dd[dd["mode"] == m]), ""]

md += ["## Gehalten % nach Jahr (nur echte Zonen, beide Seiten)", "", by_year(z), "",
       "## Gehalten % nach erstem Touch in RTH / ETH", "", by_session(z), ""]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
z.to_parquet(HERE / "results/gotham_zones_touches.parquet", index=False)
d.to_parquet(HERE / "results/gotham_zones_days.parquet", index=False)
print("\n".join(md[:60]))
