"""
IV Walls – tiefe Analyse (NQ, ES, RTY, GC): Wie genau ist die IV? Reaktion an den Zonen? Kombination mit IB / Sessions?

Zonen wie Gotham Zones: Anker = Open des ersten Bars des Handelstags (18:00 ET), σ = Anker · IV/100 / √252,
Zonen bei ±0,5 / 1 / 1,5 / 2 σ (Höhe ±5 % σ). Kontroll-Levels ±0,25 / 0,75 / 1,25 / 1,75 σ (keine Zone, zum Vergleich).
IV = letzter Cboe-Tagesschluss vor dem Anker (> 5 Tage alt = keine Daten).
  NQ: 30D = VXN,  9D = VIX9D·VXN/VIX,  1D = VIX1D·VXN/VIX
  ES: 30D = VIX,  9D = VIX9D,          1D = VIX1D
  RTY: 30D = RVX, 9D = VIX9D·RVX/VIX,  1D = VIX1D·RVX/VIX
  GC: 30D = GVZ (kein 9D/1D – nur 30D)

A) Genauigkeit: Tagesrange und Schlusskurs relativ zu σ, Vergleich mit dem, was ±σ bei normaler Bewegung bedeuten
   (Schluss in ±1σ ≈ 68 %, ±2σ ≈ 95 %; Hoch und Tief beide in ±1σ ≈ 37 %, ±2σ ≈ 91 %; erwartete Range ≈ 1,6σ),
   realisierte Volatilität (5m) / IV, welcher Modus trifft am besten, nach IV-Höhe, Wochentag, Event-Tag
   (Event-Proxy: VIX1D > 1,1 · VIX9D), Anteil der σ-Range je Uhrzeit.
B) Reaktion: erste und zweite Berührung jeder Zone, „Abprall“ = zuerst 0,25σ weg vom Level, „Durchbruch“ = zuerst
   0,25σ durch (gleicher Bar = Durchbruch); je Level, Session der Berührung, Anlaufgeschwindigkeit (letzte 15 Min),
   IV-Höhe, Event-Tag; Vergleich mit Kontroll-Levels (sind Zonen besser als beliebige Levels?).
C) Konfluenz: liegt bei der Berührung ein weiteres Level innerhalb ±0,1σ – Asia-Hoch/-Tief (ab 02:00), London-Hoch/-Tief
   (ab 08:00), 09:30-IB 60m Hoch/Tief (ab 10:30), Vortages-Hoch/-Tief? Abprall-Quote mit vs. ohne, für Zonen und Kontroll-Levels.
Zeiträume: 3J (Hauptwerte) und Alles (seit 2011 bzw. ab IV-Verfügbarkeit). Modus 1D erst ab Mai 2022.

Aufruf: python data-lab/iv_walls_deep.py   → results/iv_walls_deep.md, results/iv_walls_*.csv
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
IV_DIR = HERE / "data/iv"
MARKETS = ["NQ", "ES", "RTY", "GC"]
NCOL = 1380
ZONES = [0.5, 1.0, 1.5, 2.0]
CONTROLS = [0.25, 0.75, 1.25, 1.75]
ZH = 0.05            # Zonenhöhe ± in σ
RACE = 0.25          # Abprall / Durchbruch in σ
CONF = 0.10          # Konfluenz-Abstand in σ
MODES = ["1D", "9D", "30D"]
WDN = ["Mo", "Di", "Mi", "Do", "Fr"]
SESS_BOUNDS = [("Asia 18–02", 0, 480), ("London 02–08", 480, 840), ("Pre 08–09:30", 840, 930),
               ("NY AM 09:30–12", 930, 1080), ("NY PM 12–16", 1080, 1320), ("16–17", 1320, NCOL)]


def load_iv(name):
    df = pd.read_csv(IV_DIR / f"{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    col = "CLOSE" if "CLOSE" in df.columns else name
    df["DATE"] = pd.to_datetime(df["DATE"]).astype("datetime64[ns]")
    return df.set_index("DATE")[col].astype(float).rename(name)


IV = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX9D", "VIX1D", "RVX", "GVZ"]], axis=1, sort=True)
IVM = {
    "NQ": pd.DataFrame({"1D": IV["VIX1D"] * IV["VXN"] / IV["VIX"], "9D": IV["VIX9D"] * IV["VXN"] / IV["VIX"], "30D": IV["VXN"]}),
    "ES": pd.DataFrame({"1D": IV["VIX1D"], "9D": IV["VIX9D"], "30D": IV["VIX"]}),
    "RTY": pd.DataFrame({"1D": IV["VIX1D"] * IV["RVX"] / IV["VIX"], "9D": IV["VIX9D"] * IV["RVX"] / IV["VIX"], "30D": IV["RVX"]}),
    "GC": pd.DataFrame({"1D": np.nan, "9D": np.nan, "30D": IV["GVZ"]}, index=IV.index),
}
EVENT = (IV["VIX1D"] > 1.1 * IV["VIX9D"]).rename("event")


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def pct(x):
    x = np.asarray(x, float)
    return round(100 * np.nanmean(x), 1) if np.isfinite(x).any() else np.nan


def load(mk):
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) >= pd.Timestamp("2011-01-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["open", "high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    first_ts = df.groupby("session_date")["ts_et"].first().reindex(days)
    anchor_day = pd.to_datetime(first_ts.dt.tz_localize(None).dt.date.values).astype("datetime64[ns]")
    return dts, G, anchor_day


def iv_at(mk, anchor_day, dts):
    src = IVM[mk].copy(); src["event"] = EVENT.reindex(src.index)
    src = src.reset_index().rename(columns={"index": "iv_day", "DATE": "iv_day"})
    src.columns = ["iv_day"] + list(src.columns[1:])
    left = pd.DataFrame({"anchor_day": anchor_day, "i": np.arange(len(dts))}).sort_values("anchor_day")
    m = pd.merge_asof(left, src.dropna(subset=["30D"]).sort_values("iv_day"), left_on="anchor_day", right_on="iv_day", direction="backward")
    m = m.sort_values("i")
    stale = (m["anchor_day"] - m["iv_day"]).dt.days > 5
    m.loc[stale, MODES] = np.nan
    return m[MODES].to_numpy(), m["event"].fillna(False).to_numpy().astype(bool)


acc, acc_by, hourly, react, conf, best = [], [], [], [], [], []
for mk in MARKETS:
    dts, G, anchor_day = load(mk)
    IVv, ev = iv_at(mk, anchor_day, dts)
    end = dts.max()
    per = {"3J": np.asarray(dts > end - pd.DateOffset(years=3)), "Alles": np.ones(len(dts), bool)}
    wd = np.minimum(dts.weekday.to_numpy(), 4)
    ref = G["open"][:, 0]
    with np.errstate(all="ignore"):
        DH, DL = np.nanmax(G["high"], 1), np.nanmin(G["low"], 1)
    C = G["cff"][:, -1]
    valid = np.isfinite(ref) & (np.isfinite(G["high"]).mean(1) >= 0.6) & (dts.weekday < 5)
    # realisierte Volatilität aus 5m-Closes
    c5 = G["cff"][:, 4::5]
    with np.errstate(all="ignore"):
        r5 = np.diff(np.log(c5), axis=1)
        RV = np.sqrt(np.nansum(r5 ** 2, 1))
    # Referenz-Levels je Tag (für Konfluenz)
    with np.errstate(all="ignore"):
        aH, aL = np.nanmax(G["high"][:, 0:480], 1), np.nanmin(G["low"][:, 0:480], 1)
        lH, lL = np.nanmax(G["high"][:, 480:840], 1), np.nanmin(G["low"][:, 480:840], 1)
        iH, iL = np.nanmax(G["high"][:, 930:990], 1), np.nanmin(G["low"][:, 930:990], 1)
    gap = np.r_[False, np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4]
    pH = np.where(gap, np.r_[np.nan, DH[:-1]], np.nan); pL = np.where(gap, np.r_[np.nan, DL[:-1]], np.nan)
    REFS = [("PDH/PDL", pH, pL, 0), ("Asia H/L", aH, aL, 480), ("London H/L", lH, lL, 840), ("IB 09:30-60m H/L", iH, iL, 990)]

    for mi, mode in enumerate(MODES):
        ivd = IVv[:, mi]
        sig = ref * ivd / 100 / np.sqrt(252)
        ok = valid & np.isfinite(sig) & (sig > 0)
        if ok.sum() < 200:
            continue
        up, dn = (DH - ref) / sig, (ref - DL) / sig
        cl = (C - ref) / sig
        rng = (DH - DL) / sig
        ratio = RV / (ivd / 100 / np.sqrt(252))
        lvl = pd.qcut(pd.Series(ivd[ok]), 3, labels=["IV niedrig", "IV mittel", "IV hoch"])
        lvl_all = pd.Series(index=np.flatnonzero(ok), data=lvl.values)
        for pn, pm in per.items():
            m = ok & pm
            if m.sum() < 100:
                continue
            row = dict(Markt=mk, Modus=mode, Zeitraum=pn, Tage=int(m.sum()),
                       **{"Schluss in ±1σ %": pct(np.abs(cl[m]) <= 1), "Schluss in ±2σ %": pct(np.abs(cl[m]) <= 2),
                          "Hoch+Tief in ±1σ %": pct((up[m] <= 1) & (dn[m] <= 1)), "Hoch+Tief in ±2σ %": pct((up[m] <= 2) & (dn[m] <= 2)),
                          "+1σ erreicht %": pct(up[m] >= 1), "−1σ erreicht %": pct(dn[m] >= 1), "+2σ erreicht %": pct(up[m] >= 2), "−2σ erreicht %": pct(dn[m] >= 2),
                          "Ø Range in σ": round(np.nanmean(rng[m]), 2), "Median Range in σ": round(np.nanmedian(rng[m]), 2),
                          "realisierte Vol / IV (Median)": round(np.nanmedian(ratio[m]), 2)})
            acc.append(row)
            if pn == "3J":
                groups = [("IV-Höhe", lvl_all.reindex(np.flatnonzero(m)).astype(str).to_numpy(), np.flatnonzero(m)),
                          ("Wochentag", np.array(WDN)[wd[m]], np.flatnonzero(m)),
                          ("Event-Tag (VIX1D > 1,1·VIX9D)", np.where(ev[m], "Event", "normal"), np.flatnonzero(m))]
                for gname, labs, idx in groups:
                    for g in pd.unique(labs):
                        ii = idx[labs == g]
                        if len(ii) < 30:
                            continue
                        acc_by.append(dict(Markt=mk, Modus=mode, Gruppe=gname, Wert=g, Tage=len(ii),
                                           **{"Hoch+Tief in ±1σ %": pct((up[ii] <= 1) & (dn[ii] <= 1)), "eine Seite ≥1σ %": pct((up[ii] >= 1) | (dn[ii] >= 1)),
                                              "eine Seite ≥2σ %": pct((up[ii] >= 2) | (dn[ii] >= 2)), "Median Range in σ": round(np.nanmedian(rng[ii]), 2),
                                              "realisierte Vol / IV": round(np.nanmedian(ratio[ii]), 2)}))
                # Anteil der späteren Tagesrange je Uhrzeit (wie viel ist bis X schon passiert)
                with np.errstate(all="ignore"):
                    cumH = np.fmax.accumulate(np.nan_to_num(G["high"][m], nan=-np.inf), 1)
                    cumL = np.fmin.accumulate(np.nan_to_num(G["low"][m], nan=np.inf), 1)
                    share = (cumH - cumL) / (DH[m] - DL[m])[:, None]
                for hh in ["20:00", "00:00", "02:00", "05:00", "08:00", "09:30", "10:00", "10:30", "11:00", "12:00", "14:00", "16:00"]:
                    h, mi_ = map(int, hh.split(":")); col = (h * 60 + mi_ - 1080) % 1440 - 1
                    hourly.append(dict(Markt=mk, Modus=mode, Uhrzeit=hh, **{"Anteil Tagesrange %": round(100 * np.nanmedian(share[:, col]), 0),
                                                                             "Range in σ bis dahin (Median)": round(np.nanmedian(((cumH - cumL)[:, col]) / sig[m]), 2)}))
        # Welcher Modus sagt die Tagesrange am besten voraus? (gemeinsame Tage, letzte 3 Jahre)
        best.append(dict(Markt=mk, Modus=mode, **{"Tage": int((ok & per["3J"]).sum()),
                                                   "Fehler log(Range/σ) Streuung": round(np.nanstd(np.log(rng[ok & per["3J"]])), 3),
                                                   "Korrelation Range ↔ σ": round(np.corrcoef((DH - DL)[ok & per["3J"]], sig[ok & per["3J"]])[0, 1], 3)}))

        # ═══ B/C: Berührungen der Zonen und Kontroll-Levels ═══
        if mode not in ("30D", "1D") and mk != "GC":
            pass
        for lvl_k in ZONES + CONTROLS:
            for sgn in (1, -1):
                k = sgn * lvl_k
                z = ref + k * sig
                edge = z - sgn * ZH * sig                            # Zonenrand Richtung Open
                hp, lp = G["high"], G["low"]
                touch = (hp >= edge[:, None]) if sgn == 1 else (lp <= edge[:, None])
                t0 = first_true(touch)
                for tn in (1, 2):
                    has = ok & np.isfinite(t0)
                    if has.sum() < 30:
                        break
                    idx = np.flatnonzero(has)
                    tt = t0[idx].astype(int)
                    res = np.full(len(idx), np.nan); t_res = np.full(len(idx), np.inf)
                    away_lvl = z[idx] - sgn * RACE * sig[idx]; thru_lvl = z[idx] + sgn * RACE * sig[idx]
                    for j, (d, t) in enumerate(zip(idx, tt)):
                        hh_, ll_ = hp[d, t:], lp[d, t:]
                        a = (ll_ <= away_lvl[j]) if sgn == 1 else (hh_ >= away_lvl[j])
                        b = (hh_ >= thru_lvl[j]) if sgn == 1 else (ll_ <= thru_lvl[j])
                        ia = np.argmax(a) if a.any() else np.inf; ib = np.argmax(b) if b.any() else np.inf
                        if np.isfinite(ia) or np.isfinite(ib):
                            res[j] = 1.0 if ia < ib else 0.0
                            t_res[j] = t + (ia if ia < ib else ib)
                    sess = np.select([(tt >= b0) & (tt < b1) for _, b0, b1 in SESS_BOUNDS], [n for n, _, _ in SESS_BOUNDS], "?")
                    t15 = np.maximum(tt - 15, 0)
                    speed = sgn * (G["cff"][idx, tt] - G["cff"][idx, t15]) / sig[idx]
                    spd = np.where(speed >= RACE, "schnell (≥0,25σ in 15 Min)", "langsam")
                    ivl = lvl_all.reindex(idx).astype(str).to_numpy()
                    evd = np.where(ev[idx], "Event", "normal")
                    # Konfluenz: ein anderes Level, das zur Berührungszeit schon bekannt ist, innerhalb ±0,1σ
                    cf = np.zeros(len(idx), bool); cname = np.full(len(idx), "", object)
                    for rn, rh, rl, avail in REFS:
                        rv = rh if sgn == 1 else rl
                        near = (np.abs(rv[idx] - z[idx]) <= CONF * sig[idx]) & (tt >= avail)
                        cname = np.where(near & ~cf, rn, cname); cf |= near
                    for pn, pm in per.items():
                        sel = pm[idx] & np.isfinite(res)
                        if sel.sum() < 15:
                            continue
                        react.append(pd.DataFrame({"Markt": mk, "Modus": mode, "Zeitraum": pn, "Level": k, "Art": "Zone" if lvl_k in ZONES else "Kontrolle",
                                                   "Berührung": tn, "Session": sess[sel], "Tempo": spd[sel], "IV": ivl[sel], "Event": evd[sel],
                                                   "Konfluenz": np.where(cf[sel], "mit Level", "ohne"), "mit": cname[sel], "abprall": res[sel]}))
                    # zweite Berührung: nach einem Abprall erneut in die Zone
                    nxt = np.full(len(t0), np.inf)
                    for j, d in enumerate(idx):
                        if res[j] == 1 and np.isfinite(t_res[j]):
                            tr = int(t_res[j]) + 1
                            seg = touch[d, tr:]
                            if seg.any():
                                nxt[d] = tr + np.argmax(seg)
                    t0 = nxt
    print(mk, "fertig", flush=True)

A, AB, HR, BEST = pd.DataFrame(acc), pd.DataFrame(acc_by), pd.DataFrame(hourly), pd.DataFrame(best)
R = pd.concat(react, ignore_index=True)
for n, df in [("accuracy", A), ("accuracy_groups", AB), ("hourly", HR), ("best_mode", BEST)]:
    df.to_csv(HERE / f"results/iv_walls_{n}.csv", index=False)
R.to_csv(HERE / "results/iv_walls_touches.csv.gz", index=False)


def rate(df, by):
    g = df.groupby(by, observed=True)["abprall"].agg(["size", "mean"]).reset_index()
    g["Abprall %"] = (100 * g["mean"]).round(1)
    return g.drop(columns="mean").rename(columns={"size": "Berührungen"})


R3 = R[R["Zeitraum"] == "3J"]
Z1 = R3[(R3["Berührung"] == 1)]
md = ["# IV Walls – tiefe Analyse (NQ, ES, RTY, GC)", "",
      "Zonen = Anker (18:00-Open) ± k·σ, σ = Anker·IV/100/√252. Hauptwerte: letzte 3 Jahre. Modus 1D (VIX1D) erst ab Mai 2022, GC nur 30D (GVZ).", "",
      "## A) Wie genau ist die IV?", "",
      "Bei normal verteilter Bewegung wären: Schluss in ±1σ ≈ 68 %, ±2σ ≈ 95 %; Hoch UND Tief in ±1σ ≈ 37 %, in ±2σ ≈ 91 %; Ø Range ≈ 1,6σ. "
      "Liegen die echten Werte darüber, war die IV zu hoch (Markt bewegt sich weniger als eingepreist), darunter zu niedrig.", "",
      A[A["Zeitraum"] == "3J"].drop(columns="Zeitraum").to_markdown(index=False), "",
      "### Seit 2011 (Alles)", "", A[A["Zeitraum"] == "Alles"].drop(columns="Zeitraum").to_markdown(index=False), "",
      "### Welcher Modus sagt die Tagesrange am besten voraus? (3J; kleinere Streuung / höhere Korrelation = besser)", "",
      BEST.to_markdown(index=False), "",
      "### Nach IV-Höhe, Wochentag, Event-Tag (3J)", "", AB.to_markdown(index=False), "",
      "### Wie viel der Tagesrange ist bis zu einer Uhrzeit schon gelaufen? (3J, Median)", "",
      HR.pivot_table(index=["Markt", "Modus"], columns="Uhrzeit", values="Anteil Tagesrange %", sort=False).to_markdown(), "",
      "Range in σ bis dahin:", "", HR.pivot_table(index=["Markt", "Modus"], columns="Uhrzeit", values="Range in σ bis dahin (Median)", sort=False).to_markdown(), "",
      "## B) Reaktion an den Zonen (Abprall = zuerst 0,25σ weg, sonst 0,25σ durch)", "",
      "### Zonen vs. Kontroll-Levels – erste Berührung, 3J", "",
      rate(Z1, ["Markt", "Modus", "Art"]).pivot_table(index=["Markt", "Modus"], columns="Art", values="Abprall %").to_markdown(), "",
      "Wenn Zonen und Kontroll-Levels gleich oft abprallen, sind die Zonen nichts Besonderes – dann reagiert Preis an jedem Level so.", "",
      "### Je Level (erste Berührung, 3J)", "", rate(Z1, ["Markt", "Modus", "Level"]).pivot_table(index=["Markt", "Modus"], columns="Level", values="Abprall %").to_markdown(), "",
      "### Erste vs. zweite Berührung (Zonen, 3J)", "", rate(R3[R3["Art"] == "Zone"], ["Markt", "Modus", "Berührung"]).to_markdown(index=False), "",
      "### Nach Session der Berührung (Zonen, erste Berührung, 3J)", "", rate(Z1[Z1["Art"] == "Zone"], ["Markt", "Session"]).to_markdown(index=False), "",
      "### Nach Anlauftempo (Zonen vs. Kontrolle, erste Berührung, 3J)", "", rate(Z1, ["Markt", "Art", "Tempo"]).to_markdown(index=False), "",
      "### Nach IV-Höhe und Event-Tag (Zonen, erste Berührung, 3J)", "", rate(Z1[Z1["Art"] == "Zone"], ["Markt", "IV"]).to_markdown(index=False), "",
      rate(Z1[Z1["Art"] == "Zone"], ["Markt", "Event"]).to_markdown(index=False), "",
      "## C) Konfluenz mit IB / Sessions / Vortag (erste Berührung, 3J)", "",
      "Ein weiteres Level (zur Berührungszeit bekannt) liegt innerhalb ±0,1σ. Wichtig: auch für Kontroll-Levels prüfen – "
      "hilft die Konfluenz dort genauso, liegt der Effekt am anderen Level, nicht an der IV-Zone.", "",
      rate(Z1, ["Markt", "Art", "Konfluenz"]).pivot_table(index=["Markt", "Art"], columns="Konfluenz", values="Abprall %").to_markdown(), "",
      rate(Z1, ["Markt", "Art", "Konfluenz"]).pivot_table(index=["Markt", "Art"], columns="Konfluenz", values="Berührungen").to_markdown(), "",
      "### Welches Level hilft? (Zonen und Kontrolle, erste Berührung, 3J, alle Märkte)", "",
      rate(Z1[Z1["mit"] != ""], ["Art", "mit"]).to_markdown(index=False), "",
      "### Stabilität: dasselbe seit 2011 (Zonen vs. Kontrolle, mit/ohne Konfluenz)", "",
      rate(R[(R["Zeitraum"] == "Alles") & (R["Berührung"] == 1)], ["Markt", "Art", "Konfluenz"]).pivot_table(index=["Markt", "Art"], columns="Konfluenz", values="Abprall %").to_markdown(), ""]
(HERE / "results/iv_walls_deep.md").write_text("\n".join(md))
print("geschrieben", len("\n".join(md)), "Zeichen")
