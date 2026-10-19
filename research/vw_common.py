"""
H9 – gemeinsame Basis: Session-Gitter (1m ab 18:00 ET) je Markt und VWAP-Gitter.

Zeiträume: Explore ≤ 2019 · Validate 2020–2024 · Test 2025-01 … 2026-04-16 · Holdout ab 2026-04-17 (beim Laden abgeschnitten).
VWAP: typischer Preis (H+L+C)/3, volumengewichtet; σ = volumengewichtete Standardabweichung um den VWAP.
Alle VWAP-Werte in Minute t enthalten nur Kerzen bis einschließlich t (für Signale bei Kerzenschluss).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import load_market  # noqa: E402

NCOL = 1380
RTH = {"NQ": (930, 1320), "ES": (930, 1320), "RTY": (930, 1320), "GC": (860, 1170)}   # Minuten seit 18:00: 09:30–16:00 bzw. 08:20–13:30
COST = {"NQ": 1.0, "ES": 0.5, "RTY": 0.3, "GC": 0.4}
TICK = {"NQ": 0.25, "ES": 0.25, "RTY": 0.1, "GC": 0.1}
USD = {"NQ": 20.0, "ES": 50.0, "RTY": 50.0, "GC": 100.0}       # $ je Punkt, Standard-Kontrakt (Micro = 1/10)


import os
SPLIT = os.environ.get("VW_SPLIT", "H9")


def period_of(days):
    d = pd.to_datetime(days)
    if SPLIT == "H10":   # neues Regime: Explore 2022–23, Validate 2024–06/2025, Test 07/2025–04/2026, davor „alt“
        return np.where(d < "2022-01-01", "alt", np.where(d <= "2023-12-31", "Explore", np.where(d <= "2025-06-30", "Validate", "Test")))
    y = d.year
    return np.where(y <= 2019, "Explore", np.where(y <= 2024, "Validate", "Test"))


def _vwap_from(tp, vv, start_mask_flat, valid_flat):
    """Kumulierter VWAP über ein flaches Minuten-Array, Neustart wo start_mask_flat True ist."""
    grp = np.cumsum(start_mask_flat)
    v = np.where(valid_flat, vv, 0.0); p = np.where(valid_flat, tp, 0.0)
    df = pd.DataFrame({"g": grp, "v": v, "pv": p * v, "p2v": p * p * v})
    c = df.groupby("g")[["v", "pv", "p2v"]].cumsum().to_numpy()
    with np.errstate(all="ignore"):
        w = c[:, 1] / c[:, 0]; s = np.sqrt(np.maximum(c[:, 2] / c[:, 0] - w ** 2, 0))
    w[c[:, 0] <= 0] = np.nan; s[c[:, 0] <= 0] = np.nan
    return w, s


def load(mk):
    M = load_market(mk)
    G = M["G"]; n = len(M["days"])
    H, L, Cl, V, O = G["high"], G["low"], G["close"], G["volume"], G["open"]
    tp = (H + L + Cl) / 3
    valid = np.isfinite(tp) & np.isfinite(V) & (V > 0)
    a, b = RTH[mk]
    flat_tp, flat_v, flat_ok = tp.ravel(), V.ravel(), valid.ravel()
    col = np.tile(np.arange(NCOL), n)
    dts = M["dts"]
    # Session-VWAP (Neustart 18:00)
    sv, ss = _vwap_from(flat_tp, flat_v, col == 0, flat_ok)
    # RTH-VWAP (Neustart RTH-Beginn, vorher NaN)
    rv, rs = _vwap_from(flat_tp, flat_v, col == a, flat_ok & (col >= a))
    rv[(col < a)] = np.nan; rs[(col < a)] = np.nan
    # Wochen- und Monats-VWAP (Anker: erste Session der Woche/des Monats)
    wk = (dts - pd.to_timedelta(dts.weekday, unit="D")).normalize()
    new_w = np.r_[True, wk[1:] != wk[:-1]]; new_m = np.r_[True, dts.month[1:] != dts.month[:-1]]
    wv, ws = _vwap_from(flat_tp, flat_v, (col == 0) & np.repeat(new_w, NCOL), flat_ok)
    mv, ms = _vwap_from(flat_tp, flat_v, (col == 0) & np.repeat(new_m, NCOL), flat_ok)
    shp = (n, NCOL)
    out = dict(M=M, mk=mk, n=n, O=O, H=H, L=L, C=G["cff"], Cl=Cl, V=V, valid_min=valid,
               sVW=sv.reshape(shp), sVS=ss.reshape(shp), rVW=rv.reshape(shp), rVS=rs.reshape(shp),
               wVW=wv.reshape(shp), wVS=ws.reshape(shp), mVW=mv.reshape(shp), mVS=ms.reshape(shp),
               period=period_of(M["days"]), days=M["days"], dts=dts, rth=(a, b))
    # Asia (18–02) und London (02–08) VWAP am Ende der jeweiligen Session
    out["asiaVW"] = out["sVW"][:, 479]
    lv, _ = _vwap_from(flat_tp, flat_v, col == 480, flat_ok & (col >= 480))
    out["lonVW"] = lv.reshape(shp)[:, 839]
    # Vortag: Session-VWAP am Ende, RTH-VWAP am Ende, ATR14 der Tagesrange
    gap = np.r_[False, np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4]
    prev = lambda x: np.where(gap, np.r_[np.nan, x[:-1]], np.nan)  # noqa: E731
    with np.errstate(all="ignore"):
        last_sv = np.array([r[np.isfinite(r)][-1] if np.isfinite(r).any() else np.nan for r in out["sVW"]])
        last_rv = np.array([r[np.isfinite(r)][-1] if np.isfinite(r).any() else np.nan for r in out["rVW"]])
    out["pSVW"], out["pRVW"] = prev(last_sv), prev(last_rv)
    rng = M["H"] - M["L"]
    out["atr"] = pd.Series(np.where(M["valid"], rng, np.nan)).rolling(14, min_periods=10).mean().shift(1).to_numpy()
    out["day_ok"] = M["valid"] & np.isfinite(out["atr"])
    return out
