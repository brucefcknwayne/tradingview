"""
Analyse der 08:30-IB (NY) – NQ, ES, RTY, GC, IB-Länge 15/30/45/60 Min.

Zeitraum: letzte 3 Jahre bis zum letzten Datentag; zur Stabilität dieselben Werte für 2010 bis 3 Jahre vorher.
Tagesende 17:00 (wie Indikator), RTH-Close 16:00 für Close-Fragen.

Kennzahlen:
  Größe        IB-Range in Punkten (Median letzte 250 Tage) und im Verhältnis zur 9:30-IB gleicher Länge
  Brüche       IB-Hoch / IB-Tief gebrochen (Docht), beide, keiner
  Erster Bruch Seite und Uhrzeit (vor 9:30, 9:30–10:00, 10–11, später)
  Ausdehnung   P(±0,5 / ±1 / ±1,5 / ±2 / ±3 IB erreicht) bis 17:00
  9:30-Open    Lage zur 8:30-IB (über / in / unter) und was danach passiert
  Trade-Test   nach erstem Bruch: erreicht +0,5 IB (bzw. +1 IB) vor Rückkehr zur IB-Mitte?
  Größe        große vs. kleine IB (oberes / unteres Drittel relativ zum 20-Tage-Median)
  Wochentage   Double-Break und ±1 IB je Wochentag

Aufruf: python data-lab/ib830_analysis.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/ib830_analysis.md"
MARKETS = ["NQ", "ES", "RTY", "GC"]
LENGTHS = [15, 30, 45, 60]
NCOL = 1380
YEARS = 3


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def load(root):
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{root.lower()}_1m/*.parquet"))))
    m = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = m < NCOL
    days = np.array(sorted(df["session_date"].unique()))
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["open", "high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan)
        a[di[keep], m[keep]] = df[k].to_numpy()[keep]
        G[k] = a
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    return pd.to_datetime(days), G


def ib(G, s, L):
    W = slice(s, s + L)
    cov = np.isfinite(G["close"][:, W]).mean(1)
    with np.errstate(all="ignore"):
        H, Lo = np.nanmax(G["high"][:, W], 1), np.nanmin(G["low"][:, W], 1)
    return H, Lo, H - Lo, cov


def pct(x):
    x = np.asarray(x, float)
    return round(100 * np.nanmean(x), 1) if len(x) else np.nan


rows, opens, trades, sizes, wds, timing = [], [], [], [], [], []
for root in MARKETS:
    dts, G = load(root)
    end = dts.max()
    wd = dts.weekday.to_numpy()
    for L in LENGTHS:
        s, e = rel("08:30"), NCOL
        H, Lo, R, cov = ib(G, s, L)
        H9, L9, R9, cov9 = ib(G, rel("09:30"), L)
        v = (cov >= 0.8) & (R > 0) & np.isfinite(G["cff"][:, rel("16:00") - 1]) & (wd < 5) & np.isfinite(G["close"][:, e - 30:e]).any(1)
        Hp, Lp = G["high"][:, s + L:e], G["low"][:, s + L:e]
        mins = (np.arange(s + L, e) + 1080) % 1440                    # Uhrzeit jeder Restzeit-Spalte
        tu = first_true(Hp > H[:, None]); td = first_true(Lp < Lo[:, None])
        with np.errstate(all="ignore"):
            up = (np.nanmax(Hp, 1) - H) / R; dn = (Lo - np.nanmin(Lp, 1)) / R
        mid = (H + Lo) / 2
        i930 = rel("09:30") - (s + L)                                 # Spalte der 9:30-Kerze in der Restzeit
        o930 = G["open"][:, rel("09:30")]
        c16 = G["cff"][:, rel("16:00") - 1]
        # 20-Tage-Median der IB-Größe (nur vergangene Tage)
        rmed = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
        rel_size = R / rmed

        for per, mask in [("3J", v & (dts > end - pd.DateOffset(years=YEARS))),
                          ("2010–3J", v & (dts <= end - pd.DateOffset(years=YEARS)))]:
            idx = np.flatnonzero(mask)
            if not len(idx):
                continue
            bu, bd = np.isfinite(tu[idx]), np.isfinite(td[idx])
            first_up = tu[idx] < td[idx]; first_dn = td[idx] < tu[idx]
            r = dict(Markt=root, IB=f"8:30 · {L}m", Zeitraum=per, Tage=len(idx),
                     **{"Hoch gebrochen": pct(bu), "Tief gebrochen": pct(bd), "Beide": pct(bu & bd), "Keiner": pct(~bu & ~bd),
                        "Erst oben": pct(first_up), "Erst unten": pct(first_dn)})
            for lv in [0.5, 1, 1.5, 2, 3]:
                r[f"±{lv:g} IB"] = pct(((up[idx] >= lv).astype(float) + (dn[idx] >= lv)) / 2)
            rows.append(r)
            if per != "3J":
                continue
            last = idx[-250:]
            sizes.append(dict(Markt=root, IB=f"8:30 · {L}m", **{"Range Median (Pkt)": round(np.nanmedian(R[last]), 1),
                              "9:30-IB gleich lang (Pkt)": round(np.nanmedian(R9[last]), 1),
                              "8:30 / 9:30": round(np.nanmedian(R[last] / R9[last]), 2)}))
            # Timing erster Bruch
            tf = np.minimum(tu[idx], td[idx]); tf = tf[np.isfinite(tf)].astype(int)
            clock = mins[tf]
            buckets = pd.cut((clock - 1080) % 1440, [-1, rel("09:30") - 1, rel("10:00") - 1, rel("11:00") - 1, 1440],
                             labels=["vor 9:30", "9:30–10:00", "10:00–11:00", "nach 11:00"])
            tb = pd.Series(buckets).value_counts(normalize=True).reindex(["vor 9:30", "9:30–10:00", "10:00–11:00", "nach 11:00"]) * 100
            timing.append(dict(Markt=root, IB=f"8:30 · {L}m", **tb.round(1).to_dict(), **{"kein Bruch": pct(~np.isfinite(np.minimum(tu[idx], td[idx])))}))
            # 9:30-Open-Lage
            if L <= 60 and i930 >= 0:
                o = o930[idx]
                for lab, sel in [("über IB", o > H[idx]), ("in IB", (o <= H[idx]) & (o >= Lo[idx])), ("unter IB", o < Lo[idx])]:
                    ii = idx[sel]
                    if len(ii) < 20:
                        continue
                    back_hi = np.nanmin(Lp[ii, i930:], 1) <= H[ii]     # Retest IB-Hoch nach 9:30
                    back_lo = np.nanmax(Hp[ii, i930:], 1) >= Lo[ii]
                    opens.append(dict(Markt=root, IB=f"8:30 · {L}m", **{"9:30-Open": lab, "Anteil Tage": pct(sel), "n": len(ii),
                                      "Close 16:00 über IB": pct(c16[ii] > H[ii]), "Close in IB": pct((c16[ii] <= H[ii]) & (c16[ii] >= Lo[ii])),
                                      "Close unter IB": pct(c16[ii] < Lo[ii]),
                                      "Retest IB-Hoch nach 9:30": pct(back_hi) if lab == "über IB" else np.nan,
                                      "Retest IB-Tief nach 9:30": pct(back_lo) if lab == "unter IB" else np.nan}))
            # Trade-Test: nach erstem Bruch Ziel vor IB-Mitte
            for tgt in [0.5, 1.0]:
                res = []
                for i in idx:
                    if not np.isfinite(min(tu[i], td[i])) or tu[i] == td[i]:
                        continue
                    upside = tu[i] < td[i]
                    t0 = int(tu[i] if upside else td[i])
                    lvl = H[i] + tgt * R[i] if upside else Lo[i] - tgt * R[i]
                    hitT = first_true(((Hp[i, t0:] >= lvl) if upside else (Lp[i, t0:] <= lvl))[None, :])[0]
                    hitM = first_true(((Lp[i, t0 + 1:] <= mid[i]) if upside else (Hp[i, t0 + 1:] >= mid[i]))[None, :])[0] + 1
                    if np.isfinite(hitT) or np.isfinite(hitM):
                        res.append(hitT < hitM)
                res = np.array(res)
                need = 50.0 if tgt == 0.5 else 33.3
                trades.append(dict(Markt=root, IB=f"8:30 · {L}m", Ziel=f"+{tgt:g} IB vor IB-Mitte", n=len(res),
                                   Treffer=pct(res), **{"nötig (ohne Kosten)": need}))
            # Große vs. kleine IB
            q = np.nanquantile(rel_size[idx], [1 / 3, 2 / 3])
            for lab, sel in [("klein (unteres Drittel)", rel_size[idx] <= q[0]), ("groß (oberes Drittel)", rel_size[idx] >= q[1])]:
                ii = idx[sel]
                wds.append(dict(Markt=root, IB=f"8:30 · {L}m", Gruppe=lab, n=len(ii),
                                **{"Beide gebrochen": pct(np.isfinite(tu[ii]) & np.isfinite(td[ii])),
                                   "±1 IB": pct(((up[ii] >= 1).astype(float) + (dn[ii] >= 1)) / 2),
                                   "±2 IB": pct(((up[ii] >= 2).astype(float) + (dn[ii] >= 2)) / 2)}))
            for w in range(5):
                ii = idx[wd[idx] == w]
                wds.append(dict(Markt=root, IB=f"8:30 · {L}m", Gruppe=["Mo", "Di", "Mi", "Do", "Fr"][w], n=len(ii),
                                **{"Beide gebrochen": pct(np.isfinite(tu[ii]) & np.isfinite(td[ii])),
                                   "±1 IB": pct(((up[ii] >= 1).astype(float) + (dn[ii] >= 1)) / 2),
                                   "±2 IB": pct(((up[ii] >= 2).astype(float) + (dn[ii] >= 2)) / 2)}))
    print(root, "fertig")

T = {k: pd.DataFrame(v) for k, v in dict(main=rows, sizes=sizes, timing=timing, opens=opens, trades=trades, groups=wds).items()}
md = ["# Analyse 08:30-IB", "", f"Letzte {YEARS} Jahre bis zum letzten Datentag, Tagesende 17:00, Brüche per Docht. "
      "'±x IB' = Mittel aus oben und unten.", "",
      "## Größe (letzte 250 Tage)", "", T["sizes"].to_markdown(index=False), "",
      "## Brüche und Ausdehnung (3J vs. 2010 bis 3J vorher)", "", T["main"].to_markdown(index=False), "",
      "## Wann kommt der erste Bruch?", "", T["timing"].to_markdown(index=False), "",
      "## 9:30-Eröffnung relativ zur 8:30-IB", "", T["opens"].to_markdown(index=False), "",
      "## Trade-Test nach erstem Bruch (Docht), Stop an IB-Mitte", "", T["trades"].to_markdown(index=False), "",
      "## Große vs. kleine IB, Wochentage", "", T["groups"].to_markdown(index=False), ""]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
print("\n".join(md))
