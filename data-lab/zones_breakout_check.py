"""
Robustheits-Check Kandidat: Long-Breakout über +1σ-Zone (Touch der Zone 09:30-11:00 ET).

Einstieg: Stop-Order 1 Tick über der Zonen-Oberkante (Docht reicht), nur erster Touch je Tag.
SL/TP in Vielfachen der Zonenhöhe Z. Exit spätestens 16:00 ET (nicht erst Session-Ende).
Gleicher Bar SL+TP -> SL. Kosten 1 Pkt.
Prüft: je Modus, je Jahr, TP/SL-Raster, andere Zeitfenster, Short-Spiegel an -1σ.

Aufruf: python data-lab/zones_breakout_check.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/zones_breakout_check.md"
ZONE_PCT = 0.05
MODES = ["1D", "9D", "30D"]
COST, TICK = 1.0, 0.25
SPLIT = pd.Timestamp("2021-01-01")
RISKS = [1.0, 1.5, 2.0]
RRS = [1.0, 1.5, 2.0, 2.5, 3.0]
WINDOWS = {"09:30-11:00": (570, 660), "11:00-14:00": (660, 840), "14:00-16:00": (840, 960), "ETH (vor 09:30)": (-1, 570)}


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

H, L, O, C = (nq[c].to_numpy() for c in ["high", "low", "open", "close"])
MIN = (nq["ts_et"].dt.hour * 60 + nq["ts_et"].dt.minute).to_numpy()
# Minuten relativ zum Session-Start, damit ETH (18:00-09:30) < RTH sortiert
MREL = (MIN - 18 * 60) % 1440


def first(mask):
    if not len(mask):
        return 10**9
    i = np.argmax(mask)
    return i if mask[i] else 10**9


rows = []
for sd, idx in sess.items():
    if len(idx) < 300:
        continue
    a, b = idx[0], idx[-1] + 1
    h, l, c, mins, mrel, ref = H[a:b], L[a:b], C[a:b], MIN[a:b], MREL[a:b], O[a]
    end = np.flatnonzero(mrel <= (16 * 60 - 18 * 60) % 1440)  # bis 16:00 ET
    if not len(end):
        continue
    last_i = end[-1]
    for mode in MODES:
        v = iv_at.at[sd, mode] if sd in iv_at.index else np.nan
        if not np.isfinite(v) or v <= 0:
            continue
        sig = ref * v / 100 / np.sqrt(252)
        hh = sig * ZONE_PCT
        Z = 2 * hh
        for side in (1, -1):
            lvl = ref + side * sig
            start, far = lvl - side * hh, lvl + side * hh
            reach = (h >= start) if side == 1 else (l <= start)
            reach = reach[:last_i + 1]
            if not reach.any():
                continue
            t0 = int(np.argmax(reach))
            m0 = mins[t0]
            win = next((w for w, (x, y) in WINDOWS.items()
                        if (x == -1 and (m0 >= 18 * 60 or m0 < 570)) or (x <= m0 < y)), None)
            seg_h, seg_l = h[t0:last_i + 1], l[t0:last_i + 1]
            brk = (seg_h > far + TICK) if side == 1 else (seg_l < far - TICK)
            if not brk.any():
                rows.append(dict(session_date=sd, mode=mode, side=side, win=win, Z=Z, broke=False))
                continue
            tb = t0 + int(np.argmax(brk))
            e = far + side * TICK
            adv = (e - l[tb:last_i + 1]) if side == 1 else (h[tb:last_i + 1] - e)
            fav = np.r_[-np.inf, (h[tb + 1:last_i + 1] - e) if side == 1 else (e - l[tb + 1:last_i + 1])]
            fin = side * (c[last_i] - e)
            r = dict(session_date=sd, mode=mode, side=side, win=win, Z=Z, broke=True)
            for rk in RISKS:
                risk = rk * Z
                s = first(adv >= risk)
                for rr in RRS:
                    t = first(fav >= rr * risk)
                    pnl = fin if s == t == 10**9 else (-risk if s <= t else rr * risk)
                    r[f"R_{rk}_{rr}"] = (pnl - COST) / risk
                    r[f"P_{rk}_{rr}"] = pnl - COST
            rows.append(r)

T = pd.DataFrame(rows)
T["year"] = pd.to_datetime(T["session_date"]).dt.year
T["train"] = pd.to_datetime(T["session_date"]) < SPLIT
B = T[T["broke"]]
key = "R_1.5_2.0"


def st(x):
    x = x.dropna()
    if len(x) < 10:
        return "-"
    return f"{x.mean():+.2f}R (t {x.mean() / x.std(ddof=1) * np.sqrt(len(x)):.1f}, n {len(x)}, Treffer {100 * (x > 0).mean():.0f} %)"


md = ["# Check: Long-Breakout über +1σ-Zone", ""]
cand = B[(B["side"] == 1) & (B["win"] == "09:30-11:00")]
md += ["## Kandidat (oben, Touch 09:30-11:00, Risiko 1.5 Z, TP 2R) je Modus", "",
       "| Modus | Train < 2021 | Test ≥ 2021 |", "|---|---|---|"]
for m in MODES:
    g = cand[cand["mode"] == m]
    md.append(f"| {m} | {st(g[g['train']][key])} | {st(g[~g['train']][key])} |")
md += ["", "## Je Jahr (9D + 30D zusammen, Ø R)", ""]
y = cand[cand["mode"] != "1D"].groupby("year")[key].agg(["mean", "size"]).round(2)
y1 = cand[cand["mode"] == "1D"].groupby("year")[key].agg(["mean", "size"]).round(2)
y = y.join(y1, rsuffix=" 1D", how="outer")
y.columns = ["Ø R 9D+30D", "n", "Ø R 1D", "n 1D"]
md += [y.to_markdown(), ""]

md += ["## TP/SL-Raster (9D+30D, Test ≥ 2021, Ø R)", "", "| Risiko \\ TP | " + " | ".join(f"{rr}R" for rr in RRS) + " |",
       "|" + "---|" * (len(RRS) + 1)]
gt = cand[(cand["mode"] != "1D")]
for rk in RISKS:
    cells = []
    for rr in RRS:
        a, b2 = gt[gt["train"]][f"R_{rk}_{rr}"], gt[~gt["train"]][f"R_{rk}_{rr}"]
        cells.append(f"{a.mean():+.2f} / {b2.mean():+.2f}")
    md.append(f"| {rk} Z | " + " | ".join(cells) + " |")
md += ["", "(Zelle: Train / Test)", ""]

md += ["## Andere Zeitfenster und Short-Spiegel an −1σ (9D+30D, Risiko 1.5 Z, TP 2R)", "",
       "| Seite | Fenster | Train | Test |", "|---|---|---|---|"]
for side, sl in [(1, "Long über +1σ"), (-1, "Short unter −1σ")]:
    for w in WINDOWS:
        g = B[(B["side"] == side) & (B["win"] == w) & (B["mode"] != "1D")]
        md.append(f"| {sl} | {w} | {st(g[g['train']][key])} | {st(g[~g['train']][key])} |")

zt = T[T["mode"] != "1D"].drop_duplicates(["session_date", "mode"]).sort_values("session_date").groupby("mode")["Z"].apply(lambda s: s.tail(250).median())
md += ["", "## Größen heute (Median letzte 250 Tage)", ""]
for m, zv in zt.items():
    md.append(f"- {m}: Zonenhöhe {zv:.0f} Pkt → Risiko 1.5 Z = {1.5 * zv:.0f} Pkt, TP 2R = {3 * zv:.0f} Pkt")
cnt = cand[~cand["train"]].groupby("mode").size() / ((pd.Timestamp("2026-10-16") - SPLIT).days / 365.25)
md += ["", "Trades pro Jahr (Test): " + ", ".join(f"{m} {v:.0f}" for m, v in cnt.items())]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
print("\n".join(md))
