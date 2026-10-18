"""
Tests aus der Literatur-Recherche (IV / Intraday) mit eigenen Daten: NQ, ES, RTY, GC (Databento CME 1m, ab 2011).

1) Intraday-Momentum am Sitzungsende (Baltussen/Da/Lammers/Martens 2021, JFE; Gao/Han/Li/Zhou 2018):
   Rendite Vortag 16:00 → 15:30 (bzw. Vortag 16:00 → 10:00) sagt die Rendite 15:30 → 16:00 voraus?
   Handel: um 15:30 in Richtung der Tagesrendite, Ausstieg 16:00, minus 2 Ticks. GC: Fenster 13:00 → 13:30 (COMEX-Settlement).
   Studien-Daten bis 2020 → 2021–2026 ist ein echter Test nach Veröffentlichung.
2) Restbewegung je Uhrzeit: Wie weit läuft der Kurs ab Uhrzeit t bis 16:00 noch (in σ)? Vergleich mit der Theorie
   (Median des Maximums einer Brownschen Bewegung ≈ 0,674·σ·√Restanteil der Tagesvarianz), abhängig davon, wie viel
   Range bis t schon gelaufen ist.
3) IV-Prognose des Folgetags (Albers 2025): roh, mit Prämienkorrektur (σ × Median RV/σ der letzten 250 Tage),
   HAR-RV und HAR-RV+IV; Test = letztes Jahr (MSE der Vol, QLIKE). Dazu Aufteilung RV in Nacht (18:00–09:30) und RTH.
4) Wochentag: RV/σ und Range je Wochentag (Albers & Kestner 2024: Montags-Effekt).
5) Runde Zahlen (Osler 2000/2003): Abprall an Vielfachen von 100/500 (NQ), 25/100 (ES), 10/50 (RTY), 10/50 (GC) gegen
   um ein halbes Raster versetzte Kontroll-Levels; erste Berührung je Level und Tag in RTH, Rennen ±0,1σ (30D-σ).

Aufruf: python data-lab/lit_tests.py   → results/lit_tests.md
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
_src = (HERE / "iv_walls_deep.py").read_text().split("acc, acc_by, hourly, react, conf, best = [], [], [], [], [], []")[0]
ns = {"__file__": str(HERE / "iv_walls_deep.py")}
exec(_src, ns)
MARKETS, MODES, NCOL = ns["MARKETS"], ns["MODES"], ns["NCOL"]
TICK = {"NQ": 0.25, "ES": 0.25, "RTY": 0.1, "GC": 0.1}
GRID = {"NQ": (100, 500), "ES": (25, 100), "RTY": (10, 50), "GC": (10, 50)}
WDN = ["Mo", "Di", "Mi", "Do", "Fr"]


def rel(hm):
    h, m = map(int, hm.split(":"))
    return (h * 60 + m - 1080) % 1440


def tstat(x):
    x = np.asarray(x, float); x = x[np.isfinite(x)]
    return round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2) if len(x) > 2 else np.nan


mom, mom_year, rem, rem_cond, fc, sess_rv, wdr, rnd = [], [], [], [], [], [], [], []
for mk in MARKETS:
    dts, G, anchor_day = ns["load"](mk)
    IVv, ev = ns["iv_at"](mk, anchor_day, dts)
    n = len(dts); end = dts.max()
    yr = dts.year.to_numpy(); wd = dts.weekday.to_numpy()
    cff = G["cff"]
    consec = np.r_[False, np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4]
    valid = (np.isfinite(G["high"]).mean(1) >= 0.6) & (wd < 5)
    ref = G["open"][:, 0]

    # ═══ 1) Momentum am Sitzungsende ═══
    if mk == "GC":
        a, b, mid = rel("13:00"), rel("13:30"), rel("10:00")
    else:
        a, b, mid = rel("15:30"), rel("16:00"), rel("10:00")
    c_prev = np.r_[np.nan, cff[:-1, b - 1]]; c_prev[~consec] = np.nan
    ca, cb, cm = cff[:, a - 1], cff[:, b - 1], cff[:, mid - 1]
    r_rod = np.log(ca / c_prev); r_first = np.log(cm / c_prev); r_last = np.log(cb / ca)
    ok = valid & np.isfinite(r_rod) & np.isfinite(r_last) & np.isfinite(r_first)
    pnl = np.sign(r_rod) * (cb - ca) - 2 * TICK[mk]
    pnl_f = np.sign(r_first) * (cb - ca) - 2 * TICK[mk]
    # starke Tage: |Tagesrendite| im oberen Drittel der letzten 250 Tage (nur Vergangenheit)
    q67 = pd.Series(np.where(ok, np.abs(r_rod), np.nan)).rolling(250, min_periods=100).quantile(2 / 3).shift(1).to_numpy()
    strong = ok & (np.abs(r_rod) >= q67)
    for pn, pm in {"2011–2020 (wie Studie)": (yr <= 2020), "2021–2026 (nach Veröffentlichung)": (yr >= 2021), "letzte 3 Jahre": np.asarray(dts > end - pd.DateOffset(years=3))}.items():
        for fname, f in [("alle Tage", ok), ("starke Tage (oberes Drittel |Tagesrendite|)", strong)]:
            m = f & pm
            if m.sum() < 50:
                continue
            beta = np.polyfit(r_rod[m], r_last[m], 1)[0]
            mom.append(dict(Markt=mk, Zeitraum=pn, Tage=fname, n=int(m.sum()),
                            **{"Korrelation (Tagesrendite → letzte 30 Min)": round(np.corrcoef(r_rod[m], r_last[m])[0, 1], 3),
                               "Steigung β": round(beta, 4), "Trefferquote %": round(100 * np.mean(np.sign(r_rod[m]) == np.sign(r_last[m])), 1),
                               "Ø Pkt/Trade netto": round(pnl[m].mean(), 2), "t-Wert": tstat(pnl[m]),
                               "Sharpe p.a.": round(pnl[m].mean() / pnl[m].std() * np.sqrt(252), 2),
                               "nur 1. halbe Std. als Signal: Ø Pkt": round(pnl_f[m].mean(), 2), "t-Wert (1. halbe Std.)": tstat(pnl_f[m])}))
    for y in np.unique(yr[ok]):
        m = ok & (yr == y)
        mom_year.append(dict(Markt=mk, Jahr=int(y), n=int(m.sum()), **{"Ø Pkt netto": round(pnl[m].mean(), 2), "Summe Pkt": round(pnl[m].sum(), 0),
                                                                        "starke Tage Ø Pkt": round(pnl[m & strong].mean(), 2) if (m & strong).sum() > 10 else np.nan}))

    # ═══ 3) Realisierte Vol (5m) gesamt / Nacht / RTH ═══
    def rv(c0, c1):
        c5 = cff[:, c0 + 4:c1:5]
        with np.errstate(all="ignore"):
            r = np.diff(np.log(c5), axis=1)
        return np.sqrt(np.nansum(r ** 2, 1))
    RV, RVn, RVr = rv(0, NCOL), rv(0, 930), rv(930, 1320)
    test = np.asarray(dts > end - pd.DateOffset(years=1))
    rvl = pd.Series(np.where(valid, RV, np.nan))
    har = pd.DataFrame({"d": rvl.shift(1), "w": rvl.shift(1).rolling(5, min_periods=3).mean(), "m": rvl.shift(1).rolling(22, min_periods=10).mean()}).to_numpy()
    for mi, mode in enumerate(MODES):
        s_iv = IVv[:, mi] / 100 / np.sqrt(252)
        okm = valid & np.isfinite(s_iv) & (s_iv > 0) & (RV > 0)
        if okm.sum() < 300:
            continue
        ratio = RV / s_iv
        for pn, pm in {"letzte 3 Jahre": np.asarray(dts > end - pd.DateOffset(years=3)), "seit 2011": np.ones(n, bool)}.items():
            m = okm & pm
            sess_rv.append(dict(Markt=mk, Modus=mode, Zeitraum=pn, Tage=int(m.sum()),
                                **{"RV gesamt / IV": round(np.nanmedian(ratio[m]), 2), "RV RTH / IV": round(np.nanmedian((RVr / s_iv)[m]), 2),
                                   "RV Nacht / IV": round(np.nanmedian((RVn / s_iv)[m]), 2), "Anteil Varianz Nacht %": round(100 * np.nanmedian((RVn ** 2 / RV ** 2)[m]), 0)}))
        # Prognose des Folgetags
        adj = pd.Series(np.where(okm, ratio, np.nan)).rolling(250, min_periods=60).median().shift(1).to_numpy()
        tr = okm & ~test & np.isfinite(har).all(1)
        te = okm & test & np.isfinite(har).all(1) & np.isfinite(adj)
        if tr.sum() < 200 or te.sum() < 50:
            continue
        X1 = np.column_stack([np.ones(n), har]); X2 = np.column_stack([X1, s_iv])
        b1 = np.linalg.lstsq(X1[tr], RV[tr], rcond=None)[0]; b2 = np.linalg.lstsq(X2[tr], RV[tr], rcond=None)[0]
        F = {"IV roh": s_iv, "IV × Albers-Korrektur": s_iv * adj, "HAR-RV": X1 @ b1, "HAR-RV + IV": X2 @ b2}
        y = RV[te]
        for fn, f in F.items():
            ft = np.maximum(f[te], 1e-6)
            fc.append(dict(Markt=mk, Modus=mode, Modell=fn, Testtage=int(te.sum()),
                           **{"MSE (Vol in %²)": round(np.mean((100 * (y - ft)) ** 2), 4),
                              "QLIKE": round(np.mean(y ** 2 / ft ** 2 - np.log(y ** 2 / ft ** 2) - 1), 4),
                              "Ø Prognose / Ist": round(np.mean(ft) / np.mean(y), 2)}))
        # ═══ 4) Wochentag ═══
        if mode in ("1D", "30D"):
            m3 = okm & np.asarray(dts > end - pd.DateOffset(years=3))
            rng = (np.nanmax(G["high"], 1) - np.nanmin(G["low"], 1)) / (ref * s_iv)
            for d in range(5):
                mm = m3 & (wd == d)
                wdr.append(dict(Markt=mk, Modus=mode, Tag=WDN[d], Tage=int(mm.sum()),
                                **{"RV / IV": round(np.nanmedian(ratio[mm]), 2), "Range in σ": round(np.nanmedian(rng[mm]), 2)}))

    # ═══ 2) Restbewegung je Uhrzeit (1D-σ, sonst 30D) ═══
    for mode in ("1D", "30D"):
        mi = MODES.index(mode)
        sig = ref * IVv[:, mi] / 100 / np.sqrt(252)
        m3 = valid & np.isfinite(sig) & (sig > 0) & np.asarray(dts > end - pd.DateOffset(years=3))
        if m3.sum() < 200:
            continue
        E = rel("16:00")
        # Anteil der RTH-Tagesvarianz, der nach Uhrzeit t noch kommt (aus 5m-Renditen, Mittel über Tage)
        c5 = cff[:, 4:E:5]
        with np.errstate(all="ignore"):
            r2 = np.diff(np.log(c5), axis=1) ** 2
        r2 = np.where(np.isfinite(r2), r2, 0)
        cum = np.cumsum(r2[m3].mean(0)); tot = cum[-1]
        for hh in ["08:00", "09:30", "10:00", "10:30", "11:00", "12:00", "13:00", "14:00", "15:00"]:
            c = rel(hh)
            p = cff[:, c - 1]
            with np.errstate(all="ignore"):
                Hs, Ls = np.nanmax(G["high"][:, :c], 1), np.nanmin(G["low"][:, :c], 1)
                Ha, La = np.nanmax(G["high"][:, c:E], 1), np.nanmin(G["low"][:, c:E], 1)
            up, dn = (Ha - p) / sig, (p - La) / sig
            k5 = max(min((c - 4) // 5 - 1, len(cum) - 1), 0)
            share = 1 - cum[k5] / tot
            done = (Hs - Ls) / sig
            mm = m3 & np.isfinite(up) & np.isfinite(dn)
            rem.append(dict(Markt=mk, Modus=mode, Uhrzeit=hh, Tage=int(mm.sum()),
                            **{"Restanteil Varianz %": round(100 * share, 0), "Range bis jetzt (Median, σ)": round(np.nanmedian(done[mm]), 2),
                               "Theorie Median max. Weg (σ)": round(0.674 * np.sqrt(share), 2),
                               "Median max. Weg oben (σ)": round(np.nanmedian(up[mm]), 2), "Median max. Weg unten (σ)": round(np.nanmedian(dn[mm]), 2),
                               "80 % max. Weg (σ)": round(np.nanquantile(np.maximum(up[mm], dn[mm]), 0.8), 2),
                               "neues Tageshoch %": round(100 * np.mean((Ha > Hs)[mm]), 0), "neues Tagestief %": round(100 * np.mean((La < Ls)[mm]), 0),
                               "Median max. Weg in Pkt": round(np.nanmedian(np.maximum(up, dn)[mm] * sig[mm]), 1)}))
            if hh in ("10:30", "12:00"):
                q = np.nanquantile(done[mm], [1 / 3, 2 / 3])
                for lab, cm_ in [("wenig gelaufen", done <= q[0]), ("mittel", (done > q[0]) & (done < q[1])), ("viel gelaufen", done >= q[1])]:
                    c2 = mm & cm_
                    rem_cond.append(dict(Markt=mk, Modus=mode, Uhrzeit=hh, Gruppe=lab,
                                         **{"Range bis jetzt (σ)": f"≤ {q[0]:.2f}" if lab == "wenig gelaufen" else (f"≥ {q[1]:.2f}" if lab == "viel gelaufen" else "dazwischen"),
                                            "Tage": int(c2.sum()), "Median max. Weg (σ)": round(np.nanmedian(np.maximum(up, dn)[c2]), 2),
                                            "neues Hoch oder Tief %": round(100 * np.mean(((Ha > Hs) | (La < Ls))[c2]), 0),
                                            "Range bis 16:00 wächst um ≥ 0,5σ %": round(100 * np.mean(((np.maximum(Ha, Hs) - np.minimum(La, Ls)) / sig - done >= 0.5)[c2]), 0)}))

    # ═══ 5) Runde Zahlen vs. versetzte Kontroll-Levels (RTH, erste Berührung je Level und Tag) ═══
    sig30 = ref * IVv[:, MODES.index("30D")] / 100 / np.sqrt(252)
    s0, E = rel("09:30"), rel("16:00")
    for step in GRID[mk]:
        for art, off in (("rund", 0.0), ("Kontrolle (halbes Raster versetzt)", 0.5)):
            res = {"3J": [], "alle": []}
            recent = np.asarray(dts > end - pd.DateOffset(years=3))
            for d in np.flatnonzero(valid & np.isfinite(sig30) & (sig30 > 0)):
                hi, lo, cl = G["high"][d, s0:E], G["low"][d, s0:E], cff[d, s0:E]
                if not np.isfinite(hi).any():
                    continue
                lvls = (np.arange(np.floor(np.nanmin(lo) / step) - 1, np.ceil(np.nanmax(hi) / step) + 2) + off) * step
                rr = 0.1 * sig30[d]
                start = cff[d, s0 - 1]
                for L in lvls:
                    t = np.flatnonzero((lo <= L) & (hi >= L))
                    if not len(t):
                        continue
                    t = t[0]
                    side = np.sign((cl[t - 1] if t > 0 else start) - L)
                    if side == 0:
                        continue
                    hh, ll = hi[t:], lo[t:]
                    away = (hh >= L + rr) if side > 0 else (ll <= L - rr)
                    thru = (ll <= L - rr) if side > 0 else (hh >= L + rr)
                    ia = np.argmax(away) if away.any() else np.inf; ib = np.argmax(thru) if thru.any() else np.inf
                    if np.isfinite(ia) or np.isfinite(ib):
                        v = 1.0 if ia < ib else 0.0
                        res["alle"].append(v)
                        if recent[d]:
                            res["3J"].append(v)
            for pn, vals in res.items():
                rnd.append(dict(Markt=mk, Raster=step, Art=art, Zeitraum=pn, Berührungen=len(vals), **{"Abprall %": round(100 * np.mean(vals), 1) if vals else np.nan}))
    print(mk, "fertig", flush=True)

T = {k: pd.DataFrame(v) for k, v in dict(mom=mom, mom_year=mom_year, rem=rem, rem_cond=rem_cond, fc=fc, sess=sess_rv, wd=wdr, rnd=rnd).items()}
for k, df in T.items():
    df.to_csv(HERE / f"results/lit_tests_{k}.csv", index=False)
md = ["# Tests aus der Literatur-Recherche (NQ, ES, RTY, GC)", "",
      "## 1) Momentum am Sitzungsende (Baltussen et al. 2021)", "",
      "Signal: Rendite Vortag-Schluss → 15:30 (GC: → 13:00); Trade 15:30 → 16:00 (GC 13:00 → 13:30) in diese Richtung, minus 2 Ticks.", "",
      T["mom"].to_markdown(index=False), "", "### Jahr für Jahr (alle Tage, Ø Punkte netto je Trade)", "",
      T["mom_year"].pivot_table(index="Jahr", columns="Markt", values="Ø Pkt netto").to_markdown(), "",
      "Summe Punkte je Jahr:", "", T["mom_year"].pivot_table(index="Jahr", columns="Markt", values="Summe Pkt").to_markdown(), "",
      "## 2) Restbewegung je Uhrzeit bis 16:00 (letzte 3 Jahre)", "",
      "„max. Weg“ = wie weit der Kurs ab der Uhrzeit noch maximal läuft (oben/unten) in σ. Theorie = 0,674·√(Restanteil Varianz).", "",
      T["rem"].to_markdown(index=False), "", "### Abhängig davon, wie viel bis 10:30 / 12:00 schon gelaufen ist", "",
      T["rem_cond"].to_markdown(index=False), "",
      "## 3) IV-Prognose des Folgetags (Test: letztes Jahr) und Nacht vs. RTH", "",
      T["fc"].to_markdown(index=False), "", "Kleiner = besser (MSE, QLIKE). „Ø Prognose / Ist“ > 1 = überschätzt.", "",
      T["sess"].to_markdown(index=False), "",
      "## 4) Wochentag: RV/IV und Range (letzte 3 Jahre)", "", T["wd"].to_markdown(index=False), "",
      "## 5) Runde Zahlen vs. versetzte Kontroll-Levels (RTH, Rennen ±0,1σ)", "",
      T["rnd"].pivot_table(index=["Markt", "Raster", "Zeitraum"], columns="Art", values=["Abprall %", "Berührungen"]).to_markdown(), ""]
(HERE / "results/lit_tests.md").write_text("\n".join(md))
print("geschrieben")
