"""
Gotham Zones (H7) – gemeinsame Basis: 1m-Daten je Session (18:00–17:00 ET) und Zonen exakt wie im Pine-Indikator (ohne Kalibrierung).

load_market(mk) → dict mit Session-Gitter (Tage × 1380 Minuten ab 18:00) und σ je Modus.
Holdout (Handelstage ab 2026-04-17) wird beim Laden abgeschnitten.
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DL = ROOT / "data-lab"
RES = ROOT / "research/results"
START, CUTOFF = pd.Timestamp("2011-01-01").date(), pd.Timestamp("2026-04-16").date()
EXPLORE_END = pd.Timestamp("2024-12-31").date()
NCOL = 1380
MARKETS = ["NQ", "ES", "RTY", "GC"]
LEVELS = [0.5, 1.0, 1.5, 2.0]
CONTROLS = [0.25, 0.75, 1.25, 1.75, 2.25]
BOX = 0.05                      # Box ±5 % von σ (Default im Indikator)
COST = {"NQ": 1.0, "ES": 0.5, "RTY": 0.3, "GC": 0.4}
TICK = {"NQ": 0.25, "ES": 0.25, "RTY": 0.1, "GC": 0.1}
ROUND = {"NQ": 100.0, "ES": 25.0, "RTY": 10.0, "GC": 10.0}


def load_iv(name):
    df = pd.read_csv(DL / f"data/iv/{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    col = "CLOSE" if "CLOSE" in df.columns else name
    df["DATE"] = pd.to_datetime(df["DATE"]).astype("datetime64[ns]")
    return df.set_index("DATE")[col].astype(float).rename(name)


IV = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX9D", "VIX1D", "GVZ"]], axis=1, sort=True)


def mode_values(mk):
    """Wert je Modus wie im Pine-Code (inkl. Fallback auf den 30D-Wert, wenn 1D/9D fehlt)."""
    if mk == "GC":
        return pd.DataFrame({"GVZ": IV["GVZ"]})
    if mk == "NQ":
        sc = IV["VXN"] / IV["VIX"]
        return pd.DataFrame({"1D": IV["VIX1D"] * sc, "9D": IV["VIX9D"] * sc, "30D": IV["VXN"]})
    return pd.DataFrame({"1D": IV["VIX1D"], "9D": IV["VIX9D"], "30D": IV["VIX"]})


def load_market(mk):
    df = pd.concat(pd.read_parquet(f, columns=["ts_et", "session_date", "symbol", "open", "high", "low", "close", "volume"])
                   for f in sorted(glob.glob(str(DL / f"data/{mk.lower()}_1m/*.parquet"))))
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    df = df[(df["session_date"] >= START) & (df["session_date"] <= CUTOFF)]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique()))
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["open", "high", "low", "close", "volume"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy(float)[keep]; G[k] = a
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    first = df.groupby("session_date")["ts_et"].first().reindex(days)
    anchor = pd.to_datetime(first.dt.tz_localize(None).dt.date.values).astype("datetime64[ns]")
    dts = pd.to_datetime(days)
    # Anker-Open = erstes Open der Session (wie das Open der ersten Kerze im Chart)
    fo = np.argmax(np.isfinite(G["open"]), axis=1)
    ref = G["open"][np.arange(len(days)), fo]
    # Wert je Modus: letzter Schluss am/vor dem Anker-Datum, max. 5 Tage alt
    mv = mode_values(mk)
    left = pd.DataFrame({"a": anchor, "i": np.arange(len(days))}).sort_values("a")
    res = {}
    for m in mv.columns:
        s = mv[m].dropna()
        x = pd.merge_asof(left, pd.DataFrame({"d": s.index, "v": s.values}).sort_values("d"), left_on="a", right_on="d", direction="backward").sort_values("i")
        v = np.where((x["a"] - x["d"]).dt.days.to_numpy() > 5, np.nan, x["v"].to_numpy())
        res[m] = v
    sig = {}
    for m, v in res.items():
        if m in ("1D", "9D"):
            fb = res["30D"]
            v = np.where(np.isfinite(v), v, np.nan)          # 1D/9D ohne Wert → Tag für diesen Modus nicht werten
        sig[m] = ref * v / 100 / np.sqrt(252)
    valid = np.isfinite(ref) & (np.isfinite(G["high"]).mean(1) >= 0.6) & (dts.weekday < 5)
    with np.errstate(all="ignore"):
        H, L = np.nanmax(G["high"], 1), np.nanmin(G["low"], 1)
    C = G["cff"][:, -1]
    period = np.where(np.array([d <= EXPLORE_END for d in days]), "Explore", "Validate")
    return dict(mk=mk, days=days, dts=dts, G=G, ref=ref, sig=sig, valid=valid, H=H, L=L, C=C, period=period,
                symbol=df.groupby("session_date")["symbol"].agg(lambda s: s.mode().iat[0]).reindex(days).to_numpy())


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx
