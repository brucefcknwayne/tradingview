"""
Bedingte IB-Wahrscheinlichkeiten für den Pine-Indikator "IB Levels" (geschützt / bricht).

Je Markt x Fenster (Start jede volle Stunde 18:00-15:00 + 08:30/09:30/10:30, Länge 15/30/45/60) x Zeitraum (1J/3J/5J):
  n        gültige Tage
  hH, hL   P(IB-Hoch / IB-Tief wird bis Tagesende per Docht gebrochen | Hoch zuerst gebildet)
  lH, lL   dasselbe | Tief zuerst gebildet
  uL       P(IB-Tief bricht auch | erster Bruch war oben)
  dH       P(IB-Hoch bricht auch | erster Bruch war unten)
  u5, u10  P(+0,5 / +1 IB erreicht | IB-Hoch gebrochen)
  d5, d10  P(−0,5 / −1 IB erreicht | IB-Tief gebrochen)
Alle Werte in ganzen Prozent, -1 = weniger als 20 Fälle.
Tagesende 17:00 für Fenster vor 09:30, sonst 16:00 (wie im Dashboard).

Schreibt data-lab/results/ib_levels.csv und baut gotham-zones/IB-Levels_indicator.pine aus IB-Levels_template.pine.

Aufruf: python data-lab/ib_levels_stats.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENGTHS = [15, 30, 45, 60]
PERIODS = {"1J": 12, "3J": 36, "5J": 60}
NCOL = 1380
MIN_N = 20
FIELDS = ["n", "hH", "hL", "lH", "lL", "uL", "dH", "u5", "u10", "d5", "d10"]


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1)
    return np.where(mask.any(axis=1), idx, 10**9)


def pct(a, b):
    return int(round(100 * a / b)) if b >= MIN_N else -1


out = []
for root in MARKETS:
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
    fin = np.isfinite(G["close"])
    dts = pd.to_datetime(days)
    end = dts.max()
    wd = dts.weekday.to_numpy()

    for st in STARTS:
        for L in LENGTHS:
            s = rel(st)
            eth = s < rel("09:30")
            e = NCOL if eth else rel("16:00")
            if s + L > e - 30:
                continue
            W = slice(s, s + L)
            cov = fin[:, W].sum(1) / L
            with np.errstate(all="ignore"):
                ibh = np.nanmax(G["high"][:, W], 1)
                ibl = np.nanmin(G["low"][:, W], 1)
            R = ibh - ibl
            valid = (cov >= (0.5 if eth else 0.8)) & fin[:, e - 30:e].any(1) & np.isfinite(R) & (R > 0) & (wd < 5)
            v = valid
            tH = np.nanargmax(G["high"][v][:, W], 1)
            tL = np.nanargmin(G["low"][v][:, W], 1)
            ibh, ibl, R = ibh[v], ibl[v], R[v]
            Hp, Lp = G["high"][v][:, s + L:e], G["low"][v][:, s + L:e]
            with np.errstate(all="ignore"):
                mxH, mnL = np.nanmax(Hp, 1), np.nanmin(Lp, 1)
            mxH = np.where(np.isfinite(mxH), mxH, ibh)
            mnL = np.where(np.isfinite(mnL), mnL, ibl)
            bh, bl = first_true(Hp > ibh[:, None]), first_true(Lp < ibl[:, None])
            up, dn = (mxH - ibh) / R, (ibl - mnL) / R
            bu, bd = up > 0, dn > 0
            hf, lf = tH < tL, tL < tH
            fu, fd = bh < bl, bl < bh  # erster Bruch oben / unten (gleiche Minute: keiner)
            dv = dts[v]
            for pname, months in PERIODS.items():
                p = dv > end - pd.DateOffset(months=months)
                rec = {"m": root, "w": f"{st.replace(':', '')}-{L}", "p": pname, "n": int(p.sum()),
                       "hH": pct((p & hf & bu).sum(), (p & hf).sum()), "hL": pct((p & hf & bd).sum(), (p & hf).sum()),
                       "lH": pct((p & lf & bu).sum(), (p & lf).sum()), "lL": pct((p & lf & bd).sum(), (p & lf).sum()),
                       "uL": pct((p & fu & bd).sum(), (p & fu).sum()), "dH": pct((p & fd & bu).sum(), (p & fd).sum()),
                       "u5": pct((p & bu & (up >= 0.5)).sum(), (p & bu).sum()), "u10": pct((p & bu & (up >= 1)).sum(), (p & bu).sum()),
                       "d5": pct((p & bd & (dn >= 0.5)).sum(), (p & bd).sum()), "d10": pct((p & bd & (dn >= 1)).sum(), (p & bd).sum())}
                out.append(rec)
    print(root, "fertig")

T = pd.DataFrame(out)
T.to_csv(HERE / "results/ib_levels.csv", index=False)

# Pine-Datenblock: ein String je Markt, Zeitraum und Längen-Gruppe (a = 15/30, b = 45/60),
# Einträge "HHMM-L:n,hH,…;" – getrennt, weil Pine-Strings höchstens 4096 Zeichen haben
lines = []
for root in MARKETS:
    for pname in PERIODS:
        for part, lens in [("a", (15, 30)), ("b", (45, 60))]:
            g = T[(T.m == root) & (T.p == pname) & T.w.str.split("-").str[1].astype(int).isin(lens)]
            body = ";".join(f"{r.w}:" + ",".join(str(getattr(r, f)) for f in FIELDS) for r in g.itertuples())
            assert len(body) < 4000, (root, pname, part, len(body))
            lines.append(f'const string D_{root}_{pname}{part} = "{body}"')
block = "\n".join(lines)
(HERE / "results/ib_levels_pine_block.txt").write_text(block + "\n")
tpl = (HERE.parent / "gotham-zones/IB-Levels_template.pine").read_text()
(HERE.parent / "gotham-zones/IB-Levels_indicator.pine").write_text(tpl.replace("{{DATA}}", block))
print(len(T), "Zeilen; längster String", max(len(x) for x in lines))
print(T[(T.m == "NQ") & (T.w == "0930-45")].to_string(index=False))
