"""
Zählwerte für das Opening-Range-Dashboard (edgeful-Stil), je Markt x Fenster x Wochentag x Jahr.

Fenster = Startzeit (NY) + Länge. Das Fenster ist gleichzeitig "Opening Candle" und "Initial Balance" (IB).
Tag endet um 17:00 (Session-Ende) für Fenster ab 18:00/20:00/02:00/03:00, sonst um 16:00.

Felder (Anzahl Tage):
  n                          gültige Tage
  gc, rc                     grüne / rote Opening Candle (Close Fenster vs. Open Fenster)
  gg, gr, rg, rr             grüner/roter Tag nach grüner/roter Candle (Tag = Close Tagesende vs. Open Fenster)
  gc_up, rc_dn               Rest des Tages läuft weiter (Close Tagesende vs. Close Fenster)
  hf, lf                     IB-Hoch / IB-Tief zuerst gebildet (gleiche Minute zählt zu keinem)
  hf_bh, hf_bl, lf_bh, lf_bl erster Bruch per 5-Min-Close nach oben/unten, getrennt nach hf/lf
  wb_h, wb_l                 erster Bruch per Docht nach oben/unten
  t_up, t_dn, t_db, t_no     nur oben gebrochen / nur unten / beide / keiner (Docht)
  up_25 … up_200             Ausdehnung über IB-Hoch >= 0.25/0.5/1/2 IB-Ranges (alle Tage)
  dn_25 … dn_200             Ausdehnung unter IB-Tief >= …
  tu_up_*, td_dn_*           dasselbe nur an Tagen "nur oben" bzw. "nur unten"
  db_up_*, db_dn_*           dasselbe an Double-Break-Tagen
  ca, ci, cb                 Tages-Close über IB / in IB / unter IB

Aufruf: python data-lab/ib_dashboard_data.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/ib_stats.csv"
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = ["18:00", "20:00", "02:00", "03:00", "08:00", "08:30", "09:30", "10:00", "10:30", "11:00", "13:00", "14:00"]
LENGTHS = [5, 15, 30, 45, 60, 90]
ETH_STARTS = {"18:00", "20:00", "02:00", "03:00"}
LEVELS = [(25, 0.25), (50, 0.5), (100, 1.0), (200, 2.0)]
NCOL = 1380  # 18:00 … 16:59


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1)
    return np.where(mask.any(axis=1), idx, 10**9)


rows = []
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
    cff = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    fin = np.isfinite(G["close"])
    dts = pd.to_datetime(days)
    wd, yr = dts.weekday.to_numpy(), dts.year.to_numpy()
    clock = (np.arange(NCOL) + 1080) % 1440
    is5 = (clock + 1) % 5 == 0  # Bar schließt eine 5-Min-Kerze

    for st in STARTS:
        for L in LENGTHS:
            s = rel(st)
            e = NCOL if st in ETH_STARTS else rel("16:00")
            if s + L > e - 30:
                continue
            W = slice(s, s + L)
            cov = fin[:, W].sum(1) / L
            o_idx = np.argmax(np.isfinite(G["open"][:, W]), axis=1)
            ow = G["open"][np.arange(len(days)), s + o_idx]
            cw = cff[:, s + L - 1]
            with np.errstate(all="ignore"):
                ibh = np.nanmax(G["high"][:, W], 1)
                ibl = np.nanmin(G["low"][:, W], 1)
            R = ibh - ibl
            dc = cff[:, e - 1]
            valid = ((cov >= (0.5 if st in ETH_STARTS else 0.8)) & fin[:, e - 30:e].any(1)
                     & np.isfinite(ow) & np.isfinite(R) & (R > 0) & (wd < 5))
            if not valid.any():
                continue
            v = valid
            Hw, Lw = G["high"][v][:, W], G["low"][v][:, W]
            tH = np.nanargmax(Hw, 1)
            tL = np.nanargmin(Lw, 1)
            ibh, ibl, R, ow, cw, dc = ibh[v], ibl[v], R[v], ow[v], cw[v], dc[v]
            Hp, Lp = G["high"][v][:, s + L:e], G["low"][v][:, s + L:e]
            C5 = cff[v][:, s + L:e][:, is5[s + L:e]]
            with np.errstate(all="ignore"):
                mxH, mnL = np.nanmax(Hp, 1), np.nanmin(Lp, 1)
            mxH = np.where(np.isfinite(mxH), mxH, ibh)
            mnL = np.where(np.isfinite(mnL), mnL, ibl)
            bh_c, bl_c = first_true(C5 > ibh[:, None]), first_true(C5 < ibl[:, None])
            bh_w, bl_w = first_true(Hp > ibh[:, None]), first_true(Lp < ibl[:, None])
            up, dn = (mxH - ibh) / R, (ibl - mnL) / R
            bu, bd = up > 0, dn > 0
            gc, rc = cw > ow, cw < ow
            gd, rd = dc > ow, dc < ow
            hf, lf = tH < tL, tL < tH
            first_h = bh_c < bl_c
            first_l = bl_c < bh_c
            f = {
                "n": np.ones(v.sum(), bool),
                "gc": gc, "rc": rc, "gg": gc & gd, "gr": gc & rd, "rg": rc & gd, "rr": rc & rd,
                "gc_up": gc & (dc > cw), "rc_dn": rc & (dc < cw),
                "hf": hf, "lf": lf, "hf_bh": hf & first_h, "hf_bl": hf & first_l,
                "lf_bh": lf & first_h, "lf_bl": lf & first_l,
                "wb_h": bh_w < bl_w, "wb_l": bl_w < bh_w,
                "t_up": bu & ~bd, "t_dn": bd & ~bu, "t_db": bu & bd, "t_no": ~bu & ~bd,
                "ca": dc > ibh, "ci": (dc <= ibh) & (dc >= ibl), "cb": dc < ibl,
            }
            for tag, lv in LEVELS:
                f[f"up_{tag}"] = up >= lv
                f[f"dn_{tag}"] = dn >= lv
                f[f"tu_up_{tag}"] = bu & ~bd & (up >= lv)
                f[f"td_dn_{tag}"] = bd & ~bu & (dn >= lv)
                f[f"db_up_{tag}"] = bu & bd & (up >= lv)
                f[f"db_dn_{tag}"] = bu & bd & (dn >= lv)
            F = pd.DataFrame({k: x.astype(int) for k, x in f.items()})
            F["wd"], F["y"] = wd[v] + 1, yr[v]
            g = F.groupby(["wd", "y"]).sum().reset_index()
            g.insert(0, "w", f"{st.replace(':', '')}-{L}")
            g.insert(0, "m", root)
            rows.append(g)
    print(root, "fertig")

out = pd.concat(rows, ignore_index=True)
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False)
print(len(out), "Zeilen,", round(OUT.stat().st_size / 1e6, 2), "MB")
# Kontrolle: NQ 09:30-15, alle Jahre
c = out[(out.m == "NQ") & (out.w == "0930-15")].sum(numeric_only=True)
print({k: int(c[k]) for k in ["n", "gc", "gg", "rc", "rr", "hf", "hf_bh", "hf_bl", "lf", "lf_bh", "lf_bl", "t_up", "t_dn", "t_db", "t_no"]})
