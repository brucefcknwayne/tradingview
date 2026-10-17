"""
Gotham Zones als Trade: Fade vs. Breakout, TP/SL-Raster.

Z = Zonenhöhe (10 % von σ, aktuell ca. 25-30 Pkt). TP und Puffer in Vielfachen von Z,
damit 2010 und 2026 vergleichbar sind.

Fade:     Limit am Zonenanfang, SL = andere Kante + Puffer, TP = tp ab Einstieg.
Breakout: Stop-Order 1 Tick hinter der anderen Kante, SL = Zonenanfang - Puffer, TP = tp.
Nur erster Touch je Zone und Tag. Exit spätestens Session-Ende.
Gleicher Bar trifft SL und TP -> SL (konservativ). Kosten 1 Pkt/Trade.

Aufruf: python data-lab/gotham_zones_trades.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/gotham_zones_trades.md"
ZONE_PCT = 0.05
LEVELS = [2.0, 1.5, 1.0, 0.5, -0.5, -1.0, -1.5, -2.0]
MODES = ["1D", "9D", "30D"]
TPS = [0.5, 1.0, 1.5, 2.0, 3.0, 4.0]
BUFS = [0.25, 0.5, 1.0]
COST = 1.0
TICK = 0.25
SPLIT = pd.Timestamp("2021-01-01")


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


def first(mask):
    i = np.argmax(mask)
    return i if mask[i] else 10**9


def sim(adv, fav, last_pnl, risk, tp):
    """adv/fav ab Einstieg (adv inkl. Einstiegsbar, fav ab Bar danach)."""
    s, t = first(adv >= risk), first(fav >= tp)
    if s == t == 10**9:
        return last_pnl - COST
    return (-risk if s <= t else tp) - COST


rows = []
for sd, idx in sess.items():
    if len(idx) < 300:
        continue
    a, b = idx[0], idx[-1] + 1
    h, l, c, ref = H[a:b], L[a:b], C[a:b], O[a]
    for mode in MODES:
        v = iv_at.at[sd, mode] if sd in iv_at.index else np.nan
        if not np.isfinite(v) or v <= 0:
            continue
        sig = ref * v / 100 / np.sqrt(252)
        hh = sig * ZONE_PCT
        Z = 2 * hh
        for k in LEVELS:
            lvl = ref + k * sig
            up = k > 0
            start, far = (lvl - hh, lvl + hh) if up else (lvl + hh, lvl - hh)
            reach = h >= start if up else l <= start
            if not reach.any():
                continue
            t0 = np.argmax(reach)
            base = dict(session_date=sd, mode=mode, k=k, Z=Z)
            # Fade: Short an oberer Zone / Long an unterer Zone
            sgn = -1 if up else 1
            e = start
            adv = (h[t0:] - e) if up else (e - l[t0:])
            fav = np.r_[-np.inf, (e - l[t0 + 1:]) if up else (h[t0 + 1:] - e)]
            last = sgn * (c[-1] - e)
            for bf in BUFS:
                risk = Z + bf * Z
                for tp in TPS:
                    rows.append({**base, "strat": "Fade", "buf": bf, "tp": tp,
                                 "pnl": sim(adv, fav, last, risk, tp * Z), "risk": risk})
            # Breakout: Long über oberer Zone / Short unter unterer Zone
            brk = h[t0:] > far + TICK if up else l[t0:] < far - TICK
            if not brk.any():
                continue
            tb = t0 + np.argmax(brk)
            e = far + TICK if up else far - TICK
            sgn = 1 if up else -1
            adv = (e - l[tb:]) if up else (h[tb:] - e)
            fav = np.r_[-np.inf, (h[tb + 1:] - e) if up else (e - l[tb + 1:])]
            last = sgn * (c[-1] - e)
            for bf in BUFS:
                risk = Z + TICK + bf * Z
                for tp in TPS:
                    rows.append({**base, "strat": "Breakout", "buf": bf, "tp": tp,
                                 "pnl": sim(adv, fav, last, risk, tp * Z), "risk": risk})

t = pd.DataFrame(rows)
t["train"] = pd.to_datetime(t["session_date"]) < SPLIT
t["R"] = t["pnl"] / t["risk"]
t["win"] = t["pnl"] > 0
# auf heutige Größe umrechnen: Z der letzten 250 Handelstage je Modus
z_now = t.drop_duplicates(["session_date", "mode"]).groupby("mode").apply(lambda g: g.sort_values("session_date")["Z"].tail(250).median())


def summarize(g):
    return pd.Series({"n": len(g), "Trefferquote %": 100 * g["win"].mean(), "Ø R": g["R"].mean(),
                      "t": g["R"].mean() / g["R"].std(ddof=1) * np.sqrt(len(g)) if len(g) > 2 else np.nan})


grp = ["mode", "strat", "buf", "tp"]
tr = t[t["train"]].groupby(grp).apply(summarize).add_suffix(" Train")
te = t[~t["train"]].groupby(grp).apply(summarize).add_suffix(" Test")
res = tr.join(te, how="outer").reset_index()
res["Z heute Pkt"] = res["mode"].map(z_now).round(0)
res["TP Pkt"] = (res["tp"] * res["Z heute Pkt"]).round(0)
res["SL Pkt"] = ((1 + res["buf"]) * res["Z heute Pkt"]).round(0)
res["Ø Pkt/Trade Test (heute)"] = (res["Ø R Test"] * res["SL Pkt"]).round(1)
res = res.sort_values("Ø R Test", ascending=False)

show = ["mode", "strat", "TP Pkt", "SL Pkt", "n Train", "Trefferquote % Train", "Ø R Train", "n Test",
        "Trefferquote % Test", "Ø R Test", "t Test", "Ø Pkt/Trade Test (heute)"]
fmt = res[show].round(3)
md = ["# Gotham Zones als Trade – TP/SL-Raster", "",
      "Train < 2021, Test ab 2021 (1D nur Test, VIX1D erst ab 2022). Kosten 1 Pkt. "
      "TP/SL in Punkten auf heutige Zonengröße umgerechnet.", "",
      "## Top 15 nach Test", "", fmt.head(15).to_markdown(index=False), "",
      "## Alle Kombinationen", "", fmt.to_markdown(index=False), ""]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
print(fmt.head(15).to_string(index=False))
print("\nAnteil Kombis mit Ø R Test > 0:", round(100 * (res["Ø R Test"] > 0).mean(), 1), "%")
print("Kombis positiv in Train UND Test (9D/30D):",
      len(res[(res["Ø R Train"] > 0) & (res["Ø R Test"] > 0)]))
