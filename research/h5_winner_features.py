"""
H5 – Was haben die großen Reaktionen gemeinsam? Exakt nach Vorab-Registrierung in research/HYPOTHESEN.md.

Universum: Zera-Signale (H1, ungefiltert) auf 1m und Vol 500. Ergebnis-Trade 60/20 (Timeout 120 Kerzen, Kosten 1 Pkt).
Explore 2022-09-19 … 2024-12-31 (Muster suchen), Validate 2025-01-01 … 2026-04-16 (Muster prüfen). Holdout unberührt.

Aufruf: python research/h5_winner_features.py → research/results/h5_*.csv/.md/.png
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).parent))
import h1_zera_reversal as h1  # noqa: E402
import h2_zera_orderflow as h2  # noqa: E402

RES, DL = h1.RES, h1.DL
EXPLORE_END = pd.Timestamp("2024-12-31").date()
STOP, TGT, TOUT, COST = 20.0, 60.0, 120, 1.0
rng = np.random.default_rng(55)


# ═══════════════════════════ Minuten-Kontext (Levels) ═══════════════════════════
def value_area(vp):
    """POC/VAH/VAL je Session aus dem RTH-Volumenprofil (70 %, vom POC aus nach der größeren Nachbarseite erweitert)."""
    out = {}
    for sd, g in vp.groupby("session_date"):
        g = g.sort_values("px"); px = g["px"].to_numpy(); v = (g["buy"] + g["sell"]).to_numpy(float)
        i = int(v.argmax()); lo = hi = i; tot = v.sum(); acc = v[i]
        while acc < 0.7 * tot and (lo > 0 or hi < len(v) - 1):
            up = v[hi + 1] if hi < len(v) - 1 else -1; dn = v[lo - 1] if lo > 0 else -1
            if up >= dn:
                hi += 1; acc += v[hi]
            else:
                lo -= 1; acc += v[lo]
        out[sd] = (px[i] * 0.25, px[hi] * 0.25, px[lo] * 0.25)
    return pd.DataFrame.from_dict(out, orient="index", columns=["poc", "vah", "val"])


def iv_series():
    def load(n):
        d = pd.read_csv(DL / f"data/iv/{n}_History.csv"); d.columns = [c.strip().upper() for c in d.columns]
        d["DATE"] = pd.to_datetime(d["DATE"]).astype("datetime64[ns]"); return d.set_index("DATE")["CLOSE"].astype(float)
    v1, vx, vn = load("VIX1D"), load("VIX"), load("VXN")
    df = pd.concat([v1.rename("v1"), vx.rename("vix"), vn.rename("vxn")], axis=1).sort_index()
    df["iv"] = np.where(df["v1"].notna(), df["v1"] * df["vxn"] / df["vix"], df["vxn"] * 0.75)   # vor 1D: 30D grob skaliert
    return df["iv"].dropna()


def minute_context():
    m = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(DL / "data/nq_of1m/*.parquet"))))
    m["session_date"] = pd.to_datetime(m["session_date"]).dt.date
    m = m[(m["session_date"] >= h1.START) & (m["session_date"] <= h1.CUTOFF)].sort_values("ts_utc").reset_index(drop=True)
    sd = m["session_date"]
    g = m.groupby(sd, sort=False)
    tmin = (m["ts_et"].dt.hour * 60 + m["ts_et"].dt.minute).to_numpy()
    rel = (tmin - 1080) % 1440                                   # Minuten seit 18:00
    m["rel"] = rel
    m["open18"] = g["open"].transform("first")
    m["sessH"] = g["high"].cummax(); m["sessL"] = g["low"].cummin()
    tp = (m["high"] + m["low"] + m["close"]) / 3; v = m["volume"].astype(float)
    cv = v.groupby(sd).cumsum(); cpv = (tp * v).groupby(sd).cumsum(); cp2 = (tp * tp * v).groupby(sd).cumsum()
    m["vwap"] = cpv / cv; m["vsd"] = np.sqrt(np.maximum(cp2 / cv - m["vwap"] ** 2, 0))
    rth = m["rth"].to_numpy()
    vr = v.where(rth, 0.0)
    cvr = vr.groupby(sd).cumsum(); cpvr = (tp * vr).groupby(sd).cumsum(); cp2r = (tp * tp * vr).groupby(sd).cumsum()
    m["rvwap"] = np.where(cvr > 0, cpvr / cvr.replace(0, np.nan), np.nan)
    m["rvsd"] = np.sqrt(np.maximum(cp2r / cvr.replace(0, np.nan) - m["rvwap"] ** 2, 0))
    on = rel < 930
    m["onH"] = m["high"].where(on).groupby(sd).cummax(); m["onL"] = m["low"].where(on).groupby(sd).cummin()
    m[["onH", "onL"]] = m.groupby(sd)[["onH", "onL"]].ffill()
    ib = (rel >= 930) & (rel < 990)
    ibh = m["high"].where(ib).groupby(sd).transform("max"); ibl = m["low"].where(ib).groupby(sd).transform("min")
    m["ibH"] = np.where(rel >= 990, ibh, np.nan); m["ibL"] = np.where(rel >= 990, ibl, np.nan)
    # Vortag (RTH)
    r = m[rth].groupby("session_date").agg(pH=("high", "max"), pL=("low", "min"), pC=("close", "last"))
    sess = pd.Index(sorted(sd.unique()))
    r = r.reindex(sess).shift(1)
    vp = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(DL / "data/nq_vp/*.parquet"))))
    vp = vp[vp["part"] == "RTH"]; vp["session_date"] = pd.to_datetime(vp["session_date"]).dt.date
    va = value_area(vp[vp["session_date"] <= h1.CUTOFF]).reindex(sess).shift(1)
    day = pd.concat([r, va], axis=1)
    # 1D-σ: Wert des Vortags-Schlusses vor dem 18:00-Anker
    anchor = pd.to_datetime(g["ts_et"].transform("first").dt.tz_localize(None).dt.date)
    ivs = iv_series()
    a = pd.DataFrame({"a": anchor.groupby(sd).first()}).reset_index().rename(columns={"index": "session_date"})
    a["a"] = a["a"].astype("datetime64[ns]"); a = a.sort_values("a")
    a = pd.merge_asof(a, ivs.rename("iv").reset_index().rename(columns={"DATE": "d"}).sort_values("d"), left_on="a", right_on="d")
    day["iv"] = a.set_index("session_date")["iv"].reindex(sess)
    m = m.join(day, on="session_date")
    m["sig1d"] = m["open18"] * m["iv"] / 100 / np.sqrt(252)
    for b in (10, 50):
        m[f"cb{b}b"] = m[f"big{b}_buy"].cumsum(); m[f"cb{b}s"] = m[f"big{b}_sell"].cumsum()
    m["tsn"] = m["ts_utc"].astype("int64")
    return m


# ═══════════════════════════ 60/20-Trade ═══════════════════════════
@njit(cache=True)
def bracket(o, h, l, c, seg, e, d, stop, tgt, tout, cost):
    n = len(o); entry = o[e]; last = min(e + tout - 1, n - 1)
    for k in range(e, last + 1):
        if seg[k] != seg[e]:
            return d * (c[k - 1] - entry) - cost, 0, k - 1
        adv = (entry - l[k]) if d == 1 else (h[k] - entry)
        fav = (h[k] - entry) if d == 1 else (entry - l[k])
        if adv >= stop:
            return -stop - cost, 0, k
        if fav >= tgt:
            return tgt - cost, 1, k
    return d * (c[last] - entry) - cost, 0, last


@njit(cache=True)
def all_brackets(o, h, l, c, seg, ent, d, stop, tgt, tout, cost):
    k = len(ent); pnl = np.empty(k); win = np.empty(k, np.int64); ex = np.empty(k, np.int64)
    for j in range(k):
        pnl[j], win[j], ex[j] = bracket(o, h, l, c, seg, ent[j], d[j], stop, tgt, tout, cost)
    return pnl, win, ex


@njit(cache=True)
def random_brackets(o, h, l, c, seg, cand, cand_ptr, hour_e, day, ent, d, nrep, seed, stop, tgt, tout, cost):
    np.random.seed(seed); k = len(ent); out = np.empty((k, nrep))
    for j in range(k):
        a = cand_ptr[hour_e[j]]; b = cand_ptr[hour_e[j] + 1]
        for r in range(nrep):
            while True:
                x = cand[a + np.random.randint(b - a)]
                if day[x] != day[ent[j]]:
                    break
            out[j, r] = bracket(o, h, l, c, seg, x, d[j], stop, tgt, tout, cost)[0]
    return out


# ═══════════════════════════ Merkmale ═══════════════════════════
def features(name, bars, ctx):
    o, h, l, c = (bars[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    buy, sell = bars["buy_vol"].to_numpy(float), bars["sell_vol"].to_numpy(float)
    vol = bars["volume"].to_numpy(float); delta = buy - sell
    sym = bars["symbol"].to_numpy(); seg = np.r_[0, np.cumsum(sym[1:] != sym[:-1])].astype(np.int64)
    src = (o + h + l + c) / 4
    Z, M, S = h1.zscore(src, seg, h1.LOOK)
    si, sdir, sext, sstart, sxi = h2.signals_runs(Z, h, l, seg, h1.Z1)
    keep = (si + 1 < len(o)) & (seg[np.minimum(si + 1, len(o) - 1)] == seg[si])
    si, sdir, sext, sstart, sxi = si[keep], sdir[keep], sext[keep], sstart[keep], sxi[keep]
    e = si + 1; ser = -sdir
    pnl, win, ex = all_brackets(o, h, l, c, seg, e, sdir.astype(np.int64), STOP, TGT, TOUT, COST)
    tsn = bars["ts"].astype("int64").to_numpy()
    # Kontext zur letzten fertigen Minute vor dem Einstieg
    ci = np.searchsorted(ctx["tsn"].to_numpy(), tsn[e] - 60_000_000_000, "right") - 1
    C = ctx.iloc[np.maximum(ci, 0)].reset_index(drop=True)
    C.loc[ci < 0] = np.nan
    X = sext                                                     # Serien-Extrem
    s1 = C["sig1d"].to_numpy()
    F = pd.DataFrame(index=range(len(si)))
    F["dir"] = sdir
    # Serie
    absZ = np.abs(Z)
    F["maxZ"] = [absZ[a:i].max() for a, i in zip(sstart, si)]
    F["run_len"] = si - sstart
    F["z_sig"] = Z[si] * ser
    j = si - 1
    dz = Z[si] - Z[j]
    F["price_share"] = np.where(dz != 0, ((src[si] - src[j]) / S[j]) / dz, np.nan)
    F["tgt_pts"] = sdir * (M[si] - o[e])
    F["tgt_sig"] = F["tgt_pts"] / s1
    F["bar_sd_pts"] = S[si]
    # Zeit
    et = bars["ts"].dt.tz_convert("America/New_York").iloc[e].reset_index(drop=True)
    F["hour"] = et.dt.hour.to_numpy(); F["weekday"] = et.dt.weekday.to_numpy()
    F["rel_min"] = C["rel"].to_numpy(); F["rth"] = C["rth"].astype(float).to_numpy()
    # Volatilität / Trend
    F["sig1d_pts"] = s1
    F["range_used"] = (C["sessH"] - C["sessL"]).to_numpy() / (1.6 * s1)
    F["run_span_sig"] = np.array([h[a:i].max() - l[a:i].min() for a, i in zip(sstart, si)]) / s1
    F["slope50_sig"] = (M[si] - M[np.maximum(si - 10, 0)]) / s1 * ser
    F["pos_open_sig"] = (o[e] - C["open18"].to_numpy()) / s1 * ser
    # Levels (Abstand des Serien-Extrems)
    F["vwap_z_ext"] = (X - C["vwap"].to_numpy()) / C["vsd"].to_numpy() * ser
    F["rvwap_z_ext"] = (X - C["rvwap"].to_numpy()) / C["rvsd"].to_numpy() * ser
    F["d_vwap_band"] = np.min(np.abs(X[:, None] - (C["vwap"].to_numpy()[:, None] + ser[:, None] * np.array([1, 2, 3])[None] * C["vsd"].to_numpy()[:, None])), 1)
    F["new_sess_ext"] = np.where(ser == 1, X >= C["sessH"].to_numpy() - 0.25, X <= C["sessL"].to_numpy() + 0.25).astype(float)
    def dmin(cols):
        return np.nanmin(np.abs(X[:, None] - C[cols].to_numpy(float)), 1)
    F["d_prev_hlc"] = dmin(["pH", "pL", "pC"])
    F["d_on_hl"] = dmin(["onH", "onL"])
    with np.errstate(all="ignore"):
        F["d_ib_hl"] = dmin(["ibH", "ibL"])
    F["d_prev_va"] = dmin(["poc", "vah", "val"])
    F["d_round100"] = np.abs(X - np.round(X / 100) * 100)
    F["d_round500"] = np.abs(X - np.round(X / 500) * 500)
    gz = (X - C["open18"].to_numpy()) / s1
    F["d_gotham_sig"] = np.min(np.abs(gz[:, None] - np.array([-2, -1.5, -1, -0.5, 0.5, 1, 1.5, 2])[None]), 1)
    F["ext_sig_from_open"] = gz * ser
    # Orderflow der Serie
    rv = np.array([vol[a:i].sum() for a, i in zip(sstart, si)])
    rd = np.array([delta[a:i].sum() for a, i in zip(sstart, si)])
    F["run_delta_share"] = rd / np.maximum(rv, 1) * ser
    F["ext_delta_share"] = delta[sxi] / np.maximum(vol[sxi], 1) * ser
    F["sig_delta_share"] = delta[si] / np.maximum(vol[si], 1) * ser
    Ff = h2.filters(si, sdir, sstart, sxi, o, h, l, c, delta, buy, sell)
    F["absorption"] = Ff["F2 Absorption"].astype(float); F["divergence"] = Ff["F3 Delta-Divergenz"].astype(float)
    F["delta_turn"] = Ff["F1 Delta dreht"].astype(float)
    dur = np.diff(tsn, append=tsn[-1]) / 1e9
    med = pd.Series(dur).rolling(500, min_periods=50).median().to_numpy()
    F["run_speed"] = np.array([dur[a:i].sum() for a, i in zip(sstart, si)]) / np.maximum((si - sstart) * med[si], 1e-9)
    mv = pd.Series(vol).rolling(500, min_periods=50).mean().to_numpy()
    F["run_vol_rel"] = rv / np.maximum((si - sstart) * mv[si], 1e-9)
    cts = ctx["tsn"].to_numpy()
    a_i = np.searchsorted(cts, tsn[sstart], "left"); b_i = np.maximum(ci, 0)
    for b in (10, 50):
        cb, cs = ctx[f"cb{b}b"].to_numpy(), ctx[f"cb{b}s"].to_numpy()
        withd = np.where(ser == 1, cb[b_i] - cb[np.maximum(a_i - 1, 0)], cs[b_i] - cs[np.maximum(a_i - 1, 0)])
        agst = np.where(ser == 1, cs[b_i] - cs[np.maximum(a_i - 1, 0)], cb[b_i] - cb[np.maximum(a_i - 1, 0)])
        F[f"big{b}_with"] = withd; F[f"big{b}_against"] = agst
    F["session_date"] = C["session_date"].to_numpy()
    F["win"] = win; F["pnl"] = pnl
    meta = dict(o=o, h=h, l=l, c=c, seg=seg, e=e, ex=ex, sdir=sdir, si=si,
                hour=bars["ts"].dt.tz_convert("America/New_York").dt.hour.to_numpy(),
                day=pd.factorize((bars["ts"].dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)).dt.date)[0].astype(np.int64),
                sess=(bars["ts"].dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)).dt.date.to_numpy())
    print(name, "Signale", len(F), "Gewinner %", round(100 * F["win"].mean(), 1), flush=True)
    return F, meta


FEATS = None


def no_overlap(idx, e, ex):
    sel, busy = [], -1
    for j in idx:
        if e[j] - 1 > busy:
            sel.append(j); busy = ex[j]
    return np.array(sel, dtype=np.int64)


def validate_set(F, meta, mask_sel, label, vmask):
    idx = no_overlap(np.flatnonzero(mask_sel & vmask), meta["e"], meta["ex"])
    if len(idx) == 0:
        return {"Test": label, "Trades": 0}
    pnl = F["pnl"].to_numpy()[idx]
    hour, day, sess = meta["hour"], meta["day"], meta["sess"]
    vb = np.flatnonzero(np.array([s > EXPLORE_END for s in sess]))   # Zufall nur aus der Validate-Periode
    order = vb[np.argsort(hour[vb], kind="stable")].astype(np.int64)
    ptr = np.searchsorted(hour[order], np.arange(25)).astype(np.int64)
    e = meta["e"][idx].astype(np.int64)
    R = random_brackets(meta["o"], meta["h"], meta["l"], meta["c"], meta["seg"], order, ptr, hour[e].astype(np.int64), day, e,
                        meta["sdir"][idx].astype(np.int64), h1.NREP, 99, STOP, TGT, TOUT, COST)
    rmean = R.mean(0)
    boot = rng.choice(pnl, (2000, len(pnl))).mean(1)
    w, ls = pnl[pnl > 0], pnl[pnl <= 0]
    return {"Test": label, "Trades": len(pnl), "Gewinner %": round(100 * (pnl > 0).mean(), 1), "EW netto": round(pnl.mean(), 2),
            "KI95 unten": round(np.percentile(boot, 2.5), 2), "KI95 oben": round(np.percentile(boot, 97.5), 2),
            "PF": round(w.sum() / -ls.sum(), 2) if ls.sum() < 0 else np.nan, "Zufall EW": round(rmean.mean(), 2),
            "p roh": (1 + (rmean >= pnl.mean()).sum()) / (h1.NREP + 1)}


if __name__ == "__main__":
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score
    from sklearn.tree import DecisionTreeClassifier, export_text

    ctx = minute_context()
    print("Kontext Minuten", len(ctx), flush=True)
    charts = [("1m", h2.minute_bars_delta()), ("Vol 500", h2.volume_bars_delta(500))]
    effect_rows, lift_rows, tests, model_info = [], [], [], []
    for name, bars in charts:
        F, meta = features(name, bars, ctx)
        feats = [c for c in F.columns if c not in ("session_date", "win", "pnl")]
        ex_m = (F["session_date"] <= EXPLORE_END).to_numpy(); va_m = ~ex_m
        E = F[ex_m]
        base = E["win"].mean()
        # (a) Gewinner vs. Verlierer + Dezil-Lift (nur Explore)
        for f in feats:
            x = E[f].astype(float); wv = x[E["win"] == 1]; lv = x[E["win"] == 0]
            sd = np.nanstd(x)
            effect_rows.append({"Chart": name, "Merkmal": f, "Ø Gewinner": round(np.nanmean(wv), 3), "Ø Verlierer": round(np.nanmean(lv), 3),
                                "Effekt (SD)": round((np.nanmean(wv) - np.nanmean(lv)) / sd, 3) if sd > 0 else np.nan,
                                "fehlend %": round(100 * x.isna().mean(), 1)})
            xv = F[f].astype(float)
            ok = x.notna()
            if ok.sum() < 500 or x[ok].nunique() < 2:
                continue
            q = np.unique(np.nanquantile(x[ok], np.linspace(0, 1, 11)))
            if len(q) < 3:
                continue
            be = pd.cut(x, q, include_lowest=True, duplicates="drop"); bv = pd.cut(xv[va_m], q, include_lowest=True, duplicates="drop")
            we = E["win"].groupby(be, observed=True).agg(["mean", "size"]); wvv = F.loc[va_m, "win"].groupby(bv, observed=True).agg(["mean", "size"])
            for k_, (iv, r_) in enumerate(we.iterrows()):
                lift_rows.append({"Chart": name, "Merkmal": f, "Bin": k_, "Bereich": str(iv), "Explore Gewinner %": round(100 * r_["mean"], 1),
                                  "Explore n": int(r_["size"]), "Validate Gewinner %": round(100 * wvv["mean"].get(iv, np.nan), 1),
                                  "Validate n": int(wvv["size"].get(iv, 0))})
        # (b) Gradient-Boosting
        Xe, ye = E[feats].astype(float), E["win"].to_numpy()
        gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=200, random_state=0)
        gb.fit(Xe, ye)
        se, sv = gb.predict_proba(Xe)[:, 1], gb.predict_proba(F.loc[va_m, feats].astype(float))[:, 1]
        thr = np.quantile(se, 0.9)
        auc_e, auc_v = roc_auc_score(ye, se), roc_auc_score(F.loc[va_m, "win"], sv)
        # Zeit-CV im Explore (ehrlicher Explore-AUC)
        cut = np.quantile(np.arange(len(E)), [0.5, 0.75])
        cv = []
        for a_, b_ in ((int(cut[0]), int(cut[1])), (int(cut[1]), len(E))):
            g2 = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300, min_samples_leaf=200, random_state=0)
            g2.fit(Xe.iloc[:a_], ye[:a_]); cv.append(roc_auc_score(ye[a_:b_], g2.predict_proba(Xe.iloc[a_:b_])[:, 1]))
        score = np.full(len(F), np.nan); score[ex_m] = se; score[va_m] = sv
        # (c) Baum Tiefe 2 → beste Regel
        Xt = Xe.fillna(-1e9)
        tree = DecisionTreeClassifier(max_depth=2, min_samples_leaf=300, random_state=0).fit(Xt, ye)
        leaves = tree.apply(Xt); lw = pd.Series(ye).groupby(leaves).mean()
        best_leaf = int(lw.idxmax())
        rule_mask = tree.apply(F[feats].astype(float).fillna(-1e9)) == best_leaf
        model_info.append({"Chart": name, "Signale Explore": int(ex_m.sum()), "Signale Validate": int(va_m.sum()),
                           "Grundrate Explore %": round(100 * base, 1), "Grundrate Validate %": round(100 * F.loc[va_m, "win"].mean(), 1),
                           "AUC Explore (in-sample)": round(auc_e, 3), "AUC Explore (Zeit-CV)": " / ".join(f"{x:.3f}" for x in cv),
                           "AUC Validate": round(auc_v, 3), "Top-10%-Schwelle": round(thr, 4),
                           "Regel-Gewinnrate Explore %": round(100 * lw.max(), 1), "Regel": export_text(tree, feature_names=feats).replace("\n", " ⏎ ")})
        print(name, "AUC explore", round(auc_e, 3), "cv", [round(x, 3) for x in cv], "validate", round(auc_v, 3), flush=True)
        print(export_text(tree, feature_names=feats), "beste Blatt-Gewinnrate", round(lw.max(), 3), flush=True)
        # Wichtigkeit (Permutation auf Validate wäre Prüfen → hier nur Explore)
        from sklearn.inspection import permutation_importance
        pi = permutation_importance(gb, Xe, ye, n_repeats=3, random_state=0, scoring="roc_auc")
        for f, imp in zip(feats, pi.importances_mean):
            effect_rows.append({"Chart": name, "Merkmal": f, "Wichtigkeit Modell (Explore)": round(imp, 4)})
        # Prüfung
        tests.append({"Chart": name, **validate_set(F, meta, score >= thr, "V1 Modell Top-10 %", va_m)})
        tests.append({"Chart": name, **validate_set(F, meta, rule_mask, "V2 Baum-Regel", va_m)})
        tests.append({"Chart": name, **validate_set(F, meta, np.ones(len(F), bool), "Referenz: alle Signale (kein Test)", va_m)})
        F.assign(score=score).to_csv(RES / f"h5_features_{name.replace(' ', '')}.csv.gz", index=False)
    T = pd.DataFrame(tests)
    real = ~T["Test"].str.startswith("Referenz")
    T.loc[real, "p Holm"] = h1.holm(T.loc[real, "p roh"].to_numpy())
    T["Edge (Kriterium)"] = np.where(real & (T["p Holm"] < 0.05) & (T["KI95 unten"] > 0) & (T["Trades"] >= 30), "JA", "nein")
    E_ = pd.DataFrame(effect_rows).groupby(["Chart", "Merkmal"]).first().reset_index()
    L_ = pd.DataFrame(lift_rows); MI = pd.DataFrame(model_info)
    T.to_csv(RES / "h5_validate.csv", index=False); E_.to_csv(RES / "h5_effects.csv", index=False)
    L_.to_csv(RES / "h5_lift.csv", index=False); MI.to_csv(RES / "h5_model.csv", index=False)
    print(MI.drop(columns="Regel").to_string()); print(T.to_string())
