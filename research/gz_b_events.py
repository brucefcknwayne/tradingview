"""
H7 Teil B – Ereignis-Tabelle: jede erste Berührung einer Gotham-Zone (und der Kontroll-Levels) je Tag, mit
Konfluenzen (unabhängige Level-Formeln), Bias-Merkmalen und Ergebnissen fester Trade-Vorlagen.

Vorlagen (Stop/Ziel in σ des Modus, Ausstieg spätestens 16:59 ET, Kosten je Markt):
  fade1: Limit am Level (Füllung, wenn Preis 1 Tick durch), Stop Level ± 0,25σ, Ziel 0,25σ zurück  (1R)
  fade2: wie fade1, Ziel 0,5σ zurück                                                              (2R)
  brk1 : Stop-Einstieg an der Box-Außenkante (Level ± 0,05σ) + 1 Tick, Stop 0,25σ, Ziel 0,25σ weiter (1R)
Füll-Kerze: Stop zählt, wenn in derselben Minute erreicht; Ziel erst ab der nächsten Minute (konservativ).

Aufruf: python research/gz_b_events.py → research/results/gz_b_events_<MARKT>.parquet (nicht im Repo, Cache)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import (BOX, COST, IV, LEVELS, MARKETS, NCOL, ROUND, TICK, first_true, load_market)  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "data-lab/data/raw/gz_cache"
CTRL = [0.25, 0.75, 1.25, 1.75, 2.25]
TOL = 0.10


@njit(cache=True)
def sim(H, L, C, di, t0, entry, d, stop, tgt, last_col):
    """Ein Trade in Tag di ab Minute t0 (Füll-Minute). d=+1 long, −1 short. Rückgabe: Ergebnis in Punkten (brutto), Ausstiegsminute."""
    sp = entry - d * stop; tp = entry + d * tgt
    for k in range(t0, last_col + 1):
        hk = H[di, k]; lk = L[di, k]
        if np.isnan(hk):
            continue
        if (d == 1 and lk <= sp) or (d == -1 and hk >= sp):
            return -stop, k
        if k > t0 and ((d == 1 and hk >= tp) or (d == -1 and lk <= tp)):
            return tgt, k
    # Ausstieg zum letzten Close
    for k in range(last_col, t0 - 1, -1):
        if not np.isnan(C[di, k]):
            return d * (C[di, k] - entry), k
    return 0.0, t0


@njit(cache=True)
def sim_all(H, L, C, dis, t0s, entries, ds, stops, tgts, last_col):
    n = len(dis); out = np.empty(n); ex = np.empty(n, np.int64)
    for j in range(n):
        out[j], ex[j] = sim(H, L, C, dis[j], t0s[j], entries[j], ds[j], stops[j], tgts[j], last_col)
    return out, ex


def vp_levels(G):
    """Vortags-Volumenprofil (RTH) aus 1m-Daten: Volumen auf den Close gelegt (Näherung). POC, VAH, VAL (70 %)."""
    n = G["close"].shape[0]; out = np.full((n, 3), np.nan)
    for i in range(n):
        c = G["close"][i, 930:1320]; v = G["volume"][i, 930:1320]; ok = np.isfinite(c) & np.isfinite(v)
        if ok.sum() < 100:
            continue
        s = pd.Series(v[ok]).groupby(np.round(c[ok], 2)).sum().sort_index()
        px, vol = s.index.to_numpy(), s.to_numpy(float)
        k = int(vol.argmax()); lo = hi = k; acc = vol[k]; tot = vol.sum()
        while acc < 0.7 * tot and (lo > 0 or hi < len(vol) - 1):
            up = vol[hi + 1] if hi < len(vol) - 1 else -1; dn = vol[lo - 1] if lo > 0 else -1
            if up >= dn:
                hi += 1; acc += vol[hi]
            else:
                lo -= 1; acc += vol[lo]
        out[i] = (px[k], px[hi], px[lo])
    return out


def build(mk):
    M = load_market(mk)
    G = M["G"]; H, L, C, O, V = G["high"], G["low"], G["cff"], G["open"], G["volume"]
    n = len(M["days"]); dts = M["dts"]; ref = M["ref"]
    with np.errstate(all="ignore"):
        cumH = np.fmax.accumulate(np.nan_to_num(H, nan=-np.inf), 1); cumL = np.fmin.accumulate(np.nan_to_num(L, nan=np.inf), 1)
        rH, rL = np.nanmax(H[:, 930:1320], 1), np.nanmin(L[:, 930:1320], 1)
        onH, onL = np.nanmax(H[:, :930], 1), np.nanmin(L[:, :930], 1)
        ibH, ibL = np.nanmax(H[:, 930:990], 1), np.nanmin(L[:, 930:990], 1)
        orH, orL = np.nanmax(H[:, 930:945], 1), np.nanmin(L[:, 930:945], 1)
    rC = C[:, 1319]
    gap = np.r_[False, np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4]
    prev = lambda x: np.where(gap, np.r_[np.nan, x[:-1]], np.nan)  # noqa: E731
    pH, pL, pC, prH, prL, prC = prev(M["H"]), prev(M["L"]), prev(M["C"]), prev(rH), prev(rL), prev(rC)
    vp = vp_levels(G); pPOC, pVAH, pVAL = prev(vp[:, 0]), prev(vp[:, 1]), prev(vp[:, 2])
    P = (prH + prL + prC) / 3
    piv = np.stack([P, 2 * P - prL, 2 * P - prH, P + (prH - prL), P - (prH - prL)], 1)
    cam = np.stack([prC + s * (prH - prL) * 1.1 * f for s in (1, -1) for f in (1 / 12, 1 / 6, 1 / 4, 1 / 2)], 1)
    # Wochen-/Monats-Open, Vorwochen-Hoch/-Tief
    wk = (dts - pd.to_timedelta(dts.weekday, unit="D")).normalize(); mo = dts.to_period("M")
    dfw = pd.DataFrame({"wk": wk, "mo": mo, "ref": ref, "H": M["H"], "L": M["L"]})
    wOpen = dfw.groupby("wk")["ref"].transform("first").to_numpy(); mOpen = dfw.groupby("mo")["ref"].transform("first").to_numpy()
    wHL = dfw.groupby("wk").agg(h=("H", "max"), l=("L", "min")).shift(1).reindex(wk).to_numpy()
    # VWAP (Session ab 18:00 und RTH ab 09:30), Wert der Vorminute
    tp = (H + L + G["close"]) / 3; vv = np.where(np.isfinite(V) & np.isfinite(tp), V, 0.0); tpz = np.nan_to_num(tp)
    def vwap(a):
        cv = np.cumsum(vv[:, a:], 1); cpv = np.cumsum((tpz * vv)[:, a:], 1); cp2 = np.cumsum((tpz * tpz * vv)[:, a:], 1)
        with np.errstate(all="ignore"):
            w = cpv / cv; s = np.sqrt(np.maximum(cp2 / cv - w ** 2, 0))
        W = np.full((n, NCOL), np.nan); S = np.full((n, NCOL), np.nan); W[:, a:] = w; S[:, a:] = s
        return W, S
    sVW, sVS = vwap(0); rVW, rVS = vwap(930)
    # Modus-Werte für Regime-Merkmale
    av = {}
    for nm in ("VIX1D", "VIX9D", "VIX"):
        s = IV[nm].dropna()
        x = pd.merge_asof(pd.DataFrame({"a": (dts - pd.Timedelta(days=1)).astype("datetime64[ns]")}), pd.DataFrame({"d": s.index.astype("datetime64[ns]"), "v": s.values}), left_on="a", right_on="d")
        av[nm] = x["v"].to_numpy()
    modes = list(M["sig"].keys())
    rows = []
    for mode in modes:
        sig = M["sig"][mode]
        ok = M["valid"] & np.isfinite(sig) & (sig > 0)
        val_mode = sig / ref * 100 * np.sqrt(252)
        rank = pd.Series(val_mode).rolling(250, min_periods=60).rank(pct=True).to_numpy()
        prev_rng = prev(M["H"] - M["L"]) / sig
        other = [M["sig"][o] for o in modes if o != mode]
        for kind, lv in (("Zone", LEVELS), ("Kontrolle", CTRL)):
            for k in lv:
                for side in (1, -1):
                    z = ref + side * k * sig
                    tick = TICK[mk]
                    touch = (H >= (z + tick)[:, None]) if side == 1 else (L <= (z - tick)[:, None])
                    t0 = first_true(touch & ok[:, None])
                    dis = np.flatnonzero(np.isfinite(t0))
                    if len(dis) == 0:
                        continue
                    t = t0[dis].astype(np.int64); zz = z[dis]; ss = sig[dis]; d_f = -side * np.ones(len(dis), np.int64)
                    out = {}
                    for nm, (ent, dd, stp, tg) in {
                        "fade1": (zz, d_f, 0.25 * ss, 0.25 * ss),
                        "fade2": (zz, d_f, 0.25 * ss, 0.50 * ss),
                    }.items():
                        r, ex = sim_all(H, L, G["close"], dis, t, ent, dd, stp, tg, NCOL - 1)
                        out[nm] = (r - COST[mk]) / stp; out[nm + "_ex"] = ex
                    # Durchbruch: Einstieg an der Außenkante + 1 Tick
                    be = z + side * (BOX * sig + tick)
                    btouch = (H >= be[:, None]) if side == 1 else (L <= be[:, None])
                    tb = first_true(btouch & ok[:, None])
                    hasb = np.isfinite(tb[dis])
                    rb = np.full(len(dis), np.nan)
                    if hasb.any():
                        db = dis[hasb]; tbb = tb[db].astype(np.int64)
                        r, _ = sim_all(H, L, G["close"], db, tbb, be[db], side * np.ones(len(db), np.int64), 0.25 * sig[db], 0.25 * sig[db], NCOL - 1)
                        rb[hasb] = (r - COST[mk]) / (0.25 * sig[db])
                    X = zz
                    def near(arr):
                        a = np.atleast_2d(arr.T).T if arr.ndim == 1 else arr
                        a = a[dis] if a.shape[0] == n else a
                        return (np.nanmin(np.abs(X[:, None] - a), 1) <= TOL * ss)
                    with np.errstate(all="ignore"):
                        F = {
                            "Markt": mk, "Modus": mode, "Art": kind, "k": k, "Seite": side, "Tag": M["days"][dis], "t": t,
                            "fade1": out["fade1"], "fade2": out["fade2"], "brk1": rb,
                            "wurde_Extrem": (np.abs((M["H"][dis] - zz) / ss) <= BOX) if side == 1 else (np.abs((zz - M["L"][dis]) / ss) <= BOX),
                            # Bias-Merkmale (nur bis zur Berührung bekannt)
                            "rth": (t >= 930) & (t < 1320), "uhr": ((t + 1080) % 1440) // 60,
                            "range_used": (cumH[dis, np.maximum(t - 1, 0)] - cumL[dis, np.maximum(t - 1, 0)]) / (1.6 * ss),
                            "tempo15": side * (C[dis, t] - C[dis, np.maximum(t - 15, 0)]) / ss,
                            "gegenseite_beruehrt": (cumL[dis, np.maximum(t - 1, 0)] <= ref[dis] - 0.5 * ss) if side == 1 else (cumH[dis, np.maximum(t - 1, 0)] >= ref[dis] + 0.5 * ss),
                            "gap_sig": side * (ref[dis] - pC[dis]) / ss, "vortag_range_sig": prev_rng[dis],
                            "event_1d_9d": av["VIX1D"][dis] / av["VIX9D"][dis], "curve_9d_30d": av["VIX9D"][dis] / av["VIX"][dis],
                            "iv_rang": rank[dis], "wochentag": dts.weekday.to_numpy()[dis],
                            "vwap_abst_sig": side * (zz - sVW[dis, np.maximum(t - 1, 0)]) / ss,
                            "erste30_mit": np.where(t >= 960, np.sign(C[dis, 959] - O[dis, 930]) == side, np.nan),
                            # Konfluenzen: unabhängige Level-Formeln innerhalb ±0,1σ
                            "k_vortag_hl": near(np.stack([pH, pL], 1)), "k_vortag_rth_hlc": near(np.stack([prH, prL, prC], 1)),
                            "k_overnight_hl": (t >= 930) & near(np.stack([onH, onL], 1)),
                            "k_ib_hl": (t >= 990) & near(np.stack([ibH, ibL], 1)),
                            "k_ib_ext": (t >= 990) & near(np.stack([ibH + f * (ibH - ibL) for f in (0.5, 1, 2)] + [ibL - f * (ibH - ibL) for f in (0.5, 1, 2)], 1)),
                            "k_orb_ext": (t >= 945) & near(np.stack([orH + f * (orH - orL) for f in (0.5, 1, 2)] + [orL - f * (orH - orL) for f in (0.5, 1, 2)], 1)),
                            "k_pivots": near(piv), "k_camarilla": near(cam), "k_vp_vortag": near(np.stack([pPOC, pVAH, pVAL], 1)),
                            "k_wochen_monats_open": near(np.stack([wOpen, mOpen], 1)), "k_vorwoche_hl": near(wHL),
                            "k_rth_vwap_bands": (t >= 930) & (np.nanmin(np.abs(X[:, None] - (rVW[dis, np.maximum(t - 1, 0)][:, None] + np.array([-3, -2, -1, 1, 2, 3])[None] * rVS[dis, np.maximum(t - 1, 0)][:, None])), 1) <= TOL * ss),
                            "k_sess_vwap_bands": np.nanmin(np.abs(X[:, None] - (sVW[dis, np.maximum(t - 1, 0)][:, None] + np.array([-3, -2, -1, 1, 2, 3])[None] * sVS[dis, np.maximum(t - 1, 0)][:, None])), 1) <= TOL * ss,
                            "k_runde_zahl": np.abs(X - np.round(X / ROUND[mk]) * ROUND[mk]) <= TOL * ss,
                            "k_anderer_modus": np.zeros(len(dis), bool) if not other else np.any([near(ref[:, None] + np.array([-2, -1.5, -1, -.5, .5, 1, 1.5, 2])[None] * o[:, None]) for o in other], 0),
                        }
                    rows.append(pd.DataFrame(F))
        print(mk, mode, "fertig", flush=True)
    E = pd.concat(rows, ignore_index=True)
    kc = [c for c in E.columns if c.startswith("k_")]
    E["n_konfluenz"] = E[kc].sum(1)
    E["Zeitraum"] = np.where(pd.to_datetime(E["Tag"]) <= pd.Timestamp("2024-12-31"), "Explore", "Validate")
    E["Jahr"] = pd.to_datetime(E["Tag"]).dt.year
    OUT.mkdir(parents=True, exist_ok=True)
    E.to_parquet(OUT / f"gz_b_events_{mk}.parquet", index=False)
    return len(E)


if __name__ == "__main__":
    for mk in (sys.argv[1:] or MARKETS):
        print(mk, build(mk), "Ereignisse", flush=True)
