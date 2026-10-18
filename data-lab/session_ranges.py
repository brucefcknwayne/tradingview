"""
Session-Ranges (Asia, London, New York) – Expansion, genommene Hochs/Tiefs, Ketten, PDH/PDL, Tageshoch/-tief.

Zeiten New York, Handelstag ab 18:00 (Spalte = Minute ab 18:00, Daten bis 17:00):
  Standard   Asia 18:00–02:00 · London 02:00–08:00 · New York 09:30–16:00
  Kill-Zones Asia 20:00–00:00 · London 02:00–05:00 · New York 09:30–12:00
Gültig: ≥ 80 % der Minuten mit Daten, Range > 0. Folgetag = nächster Handelstag (max. 4 Kalendertage Abstand).

Messfenster nach Session-Ende:
  nächste Session  (Asia → London, London → New York, New York → Asia des nächsten Tages)
  bis Tagesende    (bis 17:00 desselben Handelstags; bei New York also nur 16:00–17:00)
  24 Stunden       (bis zum Start derselben Session am nächsten Handelstag)
Hoch „genommen“ = ein Hoch über dem Session-Hoch (Docht), Tief entsprechend. Expansion x = (Hoch danach − Session-Hoch) / Range.
Zeiträume: 1J, 3J (bis zum letzten Datentag), Alles (seit 2010).

Aufruf: python data-lab/session_ranges.py   → results/session_ranges.md, results/session_ranges_*.csv
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
NCOL = 1380
KS = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
DEFS = {
    "Standard": {"Asia": (0, 480), "London": (480, 840), "New York": (930, 1320)},
    "Kill-Zones": {"Asia": (120, 360), "London": (480, 660), "New York": (930, 1080)},
}
ORDER = ["Asia", "London", "New York"]
WDN = ["Mo", "Di", "Mi", "Do", "Fr"]


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def pct(x):
    x = np.asarray(x, float)
    return round(100 * np.nanmean(x), 1) if np.isfinite(x).any() else np.nan


def load(mk):
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    # Folgetag anhängen (2 Tage nebeneinander), nur wenn wirklich der nächste Handelstag
    nxt_ok = np.r_[(np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4), False]
    for k in ["high", "low"]:
        nx = np.full_like(G[k], np.nan); nx[:-1] = G[k][1:]; nx[~nxt_ok] = np.nan
        G[k + "2"] = np.concatenate([G[k], nx], 1)
    return dts, G


def periods(dts):
    end = dts.max()
    wk = np.asarray(dts.weekday < 5)
    return {"1J": wk & np.asarray(dts > end - pd.DateOffset(years=1)),
            "3J": wk & np.asarray(dts > end - pd.DateOffset(years=3)),
            "Alles": wk}


def session(G, s, e):
    Hw, Lw = G["high"][:, s:e], G["low"][:, s:e]
    with np.errstate(all="ignore"):
        H, L = np.nanmax(Hw, 1), np.nanmin(Lw, 1)
    R = H - L
    v = (np.isfinite(Hw).mean(1) >= 0.8) & (R > 0)
    tH = np.argmax(np.nan_to_num(Hw, nan=-np.inf), 1) + s; tL = np.argmin(np.nan_to_num(Lw, nan=np.inf), 1) + s
    return H, L, R, v, tH, tL


def window(G, H, L, R, a, b):
    """Werte im Fenster [a, b) der 2-Tage-Spalten: Expansion oben/unten, Zeitpunkt des ersten Bruchs je Seite."""
    hp, lp = G["high2"][:, a:b], G["low2"][:, a:b]
    ok = np.isfinite(hp).mean(1) >= 0.5
    with np.errstate(all="ignore"):
        up = (np.nanmax(hp, 1) - H) / R; dn = (L - np.nanmin(lp, 1)) / R
        tu = first_true(hp > H[:, None]); td = first_true(lp < L[:, None])
    return dict(up=up, dn=dn, tu=tu, td=td, ok=ok, a=a)


def next_window(name, s, e, sess):
    i = ORDER.index(name)
    if i < 2:
        ns, ne = sess[ORDER[i + 1]]
    else:
        ns, ne = sess["Asia"][0] + NCOL, sess["Asia"][1] + NCOL
    return {"nächste Session": (ns, ne), "bis Tagesende": (e, NCOL), "24 Stunden": (e, s + NCOL)}


def clock(col):
    m = (int(col) % NCOL + 1080) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


out = {k: [] for k in ["size", "taken", "ext", "first", "timing", "cls", "chain", "pd", "hodlod", "wd", "year"]}
for mk in MARKETS:
    dts, G = load(mk)
    P = periods(dts)
    wd = dts.weekday.to_numpy(); yr = dts.year.to_numpy()
    with np.errstate(all="ignore"):
        DH, DL = np.nanmax(G["high"], 1), np.nanmin(G["low"], 1)
    dvalid = np.isfinite(G["high"]).mean(1) >= 0.6
    for dname, sess in DEFS.items():
        S = {n: session(G, *se) for n, se in sess.items()}
        for n, (s, e) in sess.items():
            H, L, R, v, tH, tL = S[n]
            med20 = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
            rs = R / med20
            for pn, pm in P.items():
                m = v & pm
                if m.sum() < 30:
                    continue
                if dname == "Standard":
                    out["size"].append(dict(Markt=mk, Session=n, Zeitraum=pn, Tage=int(m.sum()),
                                            **{"Median Pkt": round(np.median(R[m]), 2), "25 %": round(np.quantile(R[m], .25), 2),
                                               "75 %": round(np.quantile(R[m], .75), 2), "Anteil an Tagesrange %": pct((R / (DH - DL))[m])}))
                for wn, (a, b) in next_window(n, s, e, sess).items():
                    W = window(G, H, L, R, a, b)
                    mm_ = m & W["ok"]
                    if mm_.sum() < 30:
                        continue
                    up, dn, tu, td = W["up"][mm_], W["dn"][mm_], W["tu"][mm_], W["td"][mm_]
                    hi, lo = up > 0, dn > 0
                    out["taken"].append(dict(Def=dname, Markt=mk, Session=n, Fenster=wn, Zeitraum=pn, Tage=int(mm_.sum()),
                                             **{"Hoch genommen %": pct(hi), "Tief genommen %": pct(lo), "beide %": pct(hi & lo),
                                                "nur Hoch %": pct(hi & ~lo), "nur Tief %": pct(lo & ~hi), "keins %": pct(~hi & ~lo)}))
                    row = dict(Def=dname, Markt=mk, Session=n, Fenster=wn, Zeitraum=pn, Tage=int(mm_.sum()))
                    for k in KS:
                        row[f"oben ≥{k:g}x %"] = pct(up >= k); row[f"unten ≥{k:g}x %"] = pct(dn >= k)
                        row[f"eine Seite ≥{k:g}x %"] = pct(np.maximum(up, dn) >= k)
                    row["Median max. Expansion x"] = round(float(np.nanmedian(np.maximum(up, dn))), 2)
                    out["ext"].append(row)
                    if wn == "24 Stunden":
                        fh = tu < td; fl = td < tu; anyb = np.isfinite(np.minimum(tu, td))
                        out["first"].append(dict(Def=dname, Markt=mk, Session=n, Zeitraum=pn, Tage=int(mm_.sum()),
                                                 **{"Hoch zuerst %": pct(fh[anyb]), "Tief zuerst %": pct(fl[anyb]),
                                                    "nach Hoch zuerst auch Tief %": pct(lo[fh]), "nach Tief zuerst auch Hoch %": pct(hi[fl]),
                                                    "nach Hoch zuerst ≥1x oben %": pct(up[fh] >= 1), "nach Tief zuerst ≥1x unten %": pct(dn[fl] >= 1)}))
                        if pn == "3J" and dname == "Standard":
                            # wann wird das erste Extrem genommen (Uhrzeit, Stundenblöcke)
                            tf = np.minimum(tu, td)[anyb] + W["a"]
                            hrs = pd.Series([clock(c)[:2] + ":00" for c in tf]).value_counts(normalize=True).head(8) * 100
                            out["timing"].append(dict(Markt=mk, Session=n, **{"häufigste Stunden (erster Bruch, %)": ", ".join(f"{h} {p:.0f}" for h, p in hrs.items()),
                                                                                "Median Uhrzeit": clock(np.median(tf))}))
                    if wn == "nächste Session" and dname == "Standard":
                        q = np.nanquantile(rs[m], [1 / 3, 2 / 3])
                        for cl, cm in [("klein", rs <= q[0]), ("normal", (rs > q[0]) & (rs < q[1])), ("groß", rs >= q[1])]:
                            c2 = mm_ & cm
                            if c2.sum() < 20:
                                continue
                            u2, d2 = W["up"][c2], W["dn"][c2]
                            out["cls"].append(dict(Markt=mk, Session=n, Zeitraum=pn, Größe=cl, Tage=int(c2.sum()),
                                                   **{"Range ggü. 20 Tage": f"≤ {q[0]:.2f}×" if cl == "klein" else (f"≥ {q[1]:.2f}×" if cl == "groß" else "dazwischen"),
                                                      "Hoch genommen %": pct(u2 > 0), "Tief genommen %": pct(d2 > 0), "beide %": pct((u2 > 0) & (d2 > 0)),
                                                      "eine Seite ≥1x %": pct(np.maximum(u2, d2) >= 1), "eine Seite ≥2x %": pct(np.maximum(u2, d2) >= 2)}))
                        if pn == "3J":
                            for d in range(5):
                                c2 = mm_ & (wd == d)
                                out["wd"].append(dict(Markt=mk, Session=n, Tag=WDN[d], Tage=int(c2.sum()),
                                                      **{"Hoch genommen %": pct(W["up"][c2] > 0), "Tief genommen %": pct(W["dn"][c2] > 0),
                                                         "beide %": pct((W["up"][c2] > 0) & (W["dn"][c2] > 0)), "eine Seite ≥1x %": pct(np.maximum(W["up"][c2], W["dn"][c2]) >= 1)}))
                        if pn == "Alles":
                            for y in np.unique(yr[mm_]):
                                c2 = mm_ & (yr == y)
                                out["year"].append(dict(Markt=mk, Session=n, Jahr=int(y), Tage=int(c2.sum()),
                                                        **{"mind. eine Seite genommen %": pct((W["up"][c2] > 0) | (W["dn"][c2] > 0)),
                                                           "beide %": pct((W["up"][c2] > 0) & (W["dn"][c2] > 0)),
                                                           "eine Seite ≥1x %": pct(np.maximum(W["up"][c2], W["dn"][c2]) >= 1)}))
        # ═══ Ketten: London ggü. Asia → was macht New York? ═══
        if dname == "Standard":
            (aH, aL, aR, av, _, _), (lH, lL, lR, lv, _, _), (nH, nL, nR, nv, _, _) = S["Asia"], S["London"], S["New York"]
            ls, le = sess["London"]; ns_, ne_ = sess["New York"]
            with np.errstate(all="ignore"):
                lmx, lmn = np.nanmax(G["high"][:, ls:le], 1), np.nanmin(G["low"][:, ls:le], 1)
                nmx, nmn = np.nanmax(G["high"][:, ns_:ne_], 1), np.nanmin(G["low"][:, ns_:ne_], 1)
                pre_mx, pre_mn = np.nanmax(G["high"][:, le:ns_], 1), np.nanmin(G["low"][:, le:ns_], 1)
            lah, lal = lmx > aH, lmn < aL
            cat = np.where(lah & lal, "London nahm beide", np.where(lah, "London nahm nur Asia-Hoch", np.where(lal, "London nahm nur Asia-Tief", "London innerhalb Asia")))
            for pn, pm in P.items():
                m = av & lv & nv & pm
                for c in ["London nahm nur Asia-Hoch", "London nahm nur Asia-Tief", "London nahm beide", "London innerhalb Asia"]:
                    cm = m & (cat == c)
                    if cm.sum() < 20:
                        continue
                    out["chain"].append(dict(Markt=mk, Zeitraum=pn, Fall=c, Tage=int(cm.sum()), **{"Anteil %": pct(cm[m]),
                                             "NY nimmt London-Hoch %": pct(nmx[cm] > lH[cm]), "NY nimmt London-Tief %": pct(nmn[cm] < lL[cm]),
                                             "NY nimmt Asia-Hoch %": pct(nmx[cm] > aH[cm]), "NY nimmt Asia-Tief %": pct(nmn[cm] < aL[cm]),
                                             "NY schließt über London-Hoch %": pct(G["close"][cm, ne_ - 1] > lH[cm]),
                                             "NY schließt unter London-Tief %": pct(G["close"][cm, ne_ - 1] < lL[cm])}))
            # ═══ Vortages-Hoch/-Tief: in welcher Session zuerst genommen? ═══
            pDH = np.r_[np.nan, DH[:-1]]; pDL = np.r_[np.nan, DL[:-1]]
            gap = np.r_[False, (np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4)]
            pDH[~gap] = np.nan; pDL[~gap] = np.nan
            bounds = [("Asia", 0, 480), ("London", 480, 840), ("08:00–09:30", 840, 930), ("New York", 930, 1320), ("16:00–17:00", 1320, NCOL)]
            for pn, pm in P.items():
                m = dvalid & pm & np.isfinite(pDH)
                for lvl, ref, cmp in [("PDH", pDH, "gt"), ("PDL", pDL, "lt")]:
                    arr = G["high"] if cmp == "gt" else G["low"]
                    hit = (arr > ref[:, None]) if cmp == "gt" else (arr < ref[:, None])
                    t = first_true(hit)
                    row = dict(Markt=mk, Zeitraum=pn, Level=lvl, Tage=int(m.sum()), **{"genommen %": pct(np.isfinite(t[m]))})
                    for bn, b0, b1 in bounds:
                        row[f"zuerst in {bn} %"] = pct(((t >= b0) & (t < b1))[m])
                    out["pd"].append(row)
                both = (DH > pDH) & (DL < pDL)
                out["pd"].append(dict(Markt=mk, Zeitraum=pn, Level="PDH und PDL", Tage=int(m.sum()), **{"genommen %": pct(both[m])}))
            # ═══ Wann entsteht das Tageshoch / Tagestief? ═══
            iH = np.argmax(np.nan_to_num(G["high"], nan=-np.inf), 1); iL = np.argmin(np.nan_to_num(G["low"], nan=np.inf), 1)
            for pn, pm in P.items():
                m = dvalid & pm
                for lvl, ii in [("Tageshoch", iH), ("Tagestief", iL)]:
                    row = dict(Markt=mk, Zeitraum=pn, Extrem=lvl, Tage=int(m.sum()))
                    for bn, b0, b1 in bounds:
                        row[bn + " %"] = pct(((ii >= b0) & (ii < b1))[m])
                    out["hodlod"].append(row)
    print(mk, "fertig", flush=True)

T = {k: pd.DataFrame(v) for k, v in out.items()}
for k, df in T.items():
    df.to_csv(HERE / f"results/session_ranges_{k}.csv", index=False)


def md_tab(df, idx=None):
    return df.to_markdown(index=False) if idx is None else df.set_index(idx).to_markdown()


ext = T["ext"]
core = ext[(ext["Def"] == "Standard") & (ext["Zeitraum"] == "3J")]
ecols = ["Markt", "Session", "Fenster", "Tage"] + [f"eine Seite ≥{k:g}x %" for k in KS] + ["Median max. Expansion x"]
sides = ["Markt", "Session", "Fenster"] + [f"oben ≥{k:g}x %" for k in KS] + [f"unten ≥{k:g}x %" for k in KS]
tk = T["taken"]
md = ["# Session-Ranges: Asia · London · New York (NQ, ES, RTY, GC)", "",
      "Zeiten New York. **Standard:** Asia 18:00–02:00 · London 02:00–08:00 · New York 09:30–16:00. "
      "**Kill-Zones:** Asia 20:00–00:00 · London 02:00–05:00 · New York 09:30–12:00.",
      "„genommen“ = Docht über Session-Hoch bzw. unter Session-Tief. Expansion x = Weg über das Hoch / unter das Tief in Session-Ranges.",
      "Fenster ab Session-Ende: **nächste Session** (Asia→London, London→NY, NY→Asia des Folgetags), **bis Tagesende** (17:00; NY: bis 17:00 am Folgetag), "
      "**24 Stunden** (bis zum Start derselben Session am Folgetag). Zeiträume: 1J, 3J, Alles (seit 2010).", "",
      "## 1. Range-Größen (Punkte)", "", md_tab(T["size"][T["size"]["Zeitraum"] != "Alles"]), "",
      "## 2. Werden Session-Hoch/-Tief genommen? (Standard, 3J)", "",
      md_tab(tk[(tk["Def"] == "Standard") & (tk["Zeitraum"] == "3J")].drop(columns=["Def", "Zeitraum"])), "",
      "### Stabilität: dasselbe für 1J und Alles (nur nächste Session)", "",
      md_tab(tk[(tk["Def"] == "Standard") & (tk["Fenster"] == "nächste Session") & (tk["Zeitraum"] != "3J")].drop(columns=["Def"])), "",
      "## 3. Expansion – mindestens eine Seite erreicht x Ranges (Standard, 3J)", "", md_tab(core[ecols]), "",
      "### Expansion getrennt nach oben / unten (Standard, 3J)", "", md_tab(core[sides]), "",
      "### Expansion im letzten Jahr (Standard, 1J)", "", md_tab(ext[(ext["Def"] == "Standard") & (ext["Zeitraum"] == "1J")][ecols]), "",
      "## 4. Welche Seite zuerst – und kommt danach die andere? (Fenster 24 Stunden)", "",
      md_tab(T["first"][T["first"]["Zeitraum"] == "3J"].drop(columns=["Zeitraum"])), "",
      "### Uhrzeit des ersten Bruchs (Standard, 3J, 24 Stunden)", "", md_tab(T["timing"]), "",
      "## 5. Kleine vs. große Range (ggü. Median der 20 Tage davor) → nächste Session", "",
      md_tab(T["cls"][T["cls"]["Zeitraum"] == "3J"].drop(columns=["Zeitraum"])), "",
      "## 6. Ketten: Was London mit Asia macht → was New York macht (Standard)", "",
      md_tab(T["chain"][T["chain"]["Zeitraum"] == "3J"].drop(columns=["Zeitraum"])), "",
      "### dasselbe im letzten Jahr", "", md_tab(T["chain"][T["chain"]["Zeitraum"] == "1J"].drop(columns=["Zeitraum"])), "",
      "## 7. Vortages-Hoch/-Tief (PDH/PDL): genommen und in welcher Session zuerst", "",
      md_tab(T["pd"][T["pd"]["Zeitraum"] == "3J"].drop(columns=["Zeitraum"])), "",
      "## 8. In welcher Session entsteht Tageshoch / Tagestief? (Handelstag 18:00–17:00)", "",
      md_tab(T["hodlod"][T["hodlod"]["Zeitraum"] != "Alles"]), "",
      "## 9. Wochentage (Standard, 3J, nächste Session)", "", md_tab(T["wd"]), "",
      "## 10. Jedes Jahr (Standard, nächste Session) – wie stabil?", "",
      md_tab(T["year"].pivot_table(index=["Markt", "Session"], columns="Jahr", values="mind. eine Seite genommen %").reset_index()), "",
      "Werte: mind. eine Seite in der nächsten Session genommen (%). Weitere Spalten in results/session_ranges_year.csv.", "",
      "## 11. Kill-Zones (3J) – genommen und Expansion", "",
      md_tab(tk[(tk["Def"] == "Kill-Zones") & (tk["Zeitraum"] == "3J")].drop(columns=["Def", "Zeitraum"])), "",
      md_tab(ext[(ext["Def"] == "Kill-Zones") & (ext["Zeitraum"] == "3J")][ecols]), ""]
(HERE / "results/session_ranges.md").write_text("\n".join(md))
print("geschrieben:", HERE / "results/session_ranges.md", len("\n".join(md)), "Zeichen")
