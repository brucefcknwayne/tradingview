"""
H16b – ORB-Tiefenanalyse, exakt nach Vorab-Registrierung (HYPOTHESEN.md).
A: Ausdehnung nach Erstausbruch (beschreibend) · B: Trade-Matrix Einstieg E1–E4 × Stop S × Ziel T · C: Filter (nur Explore).
Auswahl der Kandidaten nur auf Explore, danach unverändert Validate/Test. Holdout ab 2026-04-17 beim Laden abgeschnitten.
Aufruf: python research/h16b_orb_deep.py → research/results/h16b_*.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, TICK, USD, load  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h16b_cache"
CACHE.mkdir(parents=True, exist_ok=True)
LAST5 = pd.Timestamp("2021-10-18")
ORS = (5, 15, 30, 60)
KS = (0.1, 0.25, 0.5, 0.75, 1, 1.5, 2, 3)
TG = np.array([0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, np.nan])        # nan = RTH-Ende
TGN = ["0.1", "0.25", "0.5", "0.75", "1", "1.5", "2", "Ende"]
SG = np.array([0.25, 0.5, 1.0, 1.5])


# ───────────────────────── Teil A: je Tag ein Datensatz ─────────────────────────
def part_a(D, m):
    O, H, L, C = D["O"], D["H"], D["L"], D["C"]
    a, b = D["rth"]; s0 = a + m
    with np.errstate(all="ignore"):
        orH, orL = np.nanmax(H[:, a:s0], 1), np.nanmin(L[:, a:s0], 1)
    R = orH - orL
    rows = []
    for d in np.flatnonzero(D["day_ok"] & np.isfinite(R) & (R > 0)):
        up = H[d, s0:b] > orH[d]; dn = L[d, s0:b] < orL[d]
        iu = np.argmax(up) if up.any() else 10**6; idn = np.argmax(dn) if dn.any() else 10**6
        rec = dict(d=d, R=R[d], brk=0)
        if iu == idn:
            rec["brk"] = 0 if iu == 10**6 else 9          # 9 = beide Seiten in derselben Kerze
            rows.append(rec); continue
        dirn = 1 if iu < idn else -1
        tb = s0 + min(iu, idn)
        h, l = H[d, tb:b], L[d, tb:b]
        if dirn == 1:
            fav, adv = (h - orH[d]) / R[d], (orH[d] - l) / R[d]
        else:
            fav, adv = (orL[d] - l) / R[d], (h - orL[d]) / R[d]
        fav = np.where(np.isnan(fav), -np.inf, fav); adv = np.where(np.isnan(adv), -np.inf, adv)
        mfe = fav.max(); tm = int(np.argmax(fav))
        fi = np.flatnonzero(adv > 1)
        fail = len(fi) > 0; kf = int(fi[0]) if fail else -1
        mfe_pre = fav[:max(kf, 1)].max() if fail else mfe
        pull = adv[1:tm].max() if tm > 1 else 0.0
        rec.update(brk=dirn, tb=tb, tmin=tb - s0, mfe=mfe, tmfe=tm, clock_mfe=tb + tm - a, fail=fail, kf=kf, mfe_pre=mfe_pre,
                   pull=max(pull, 0.0) if np.isfinite(pull) else 0.0, close_beyond=dirn * (C[d, b - 1] - (orH[d] if dirn == 1 else orL[d])) > 0)
        # Retest der Kante (Bars nach der Ausbruchskerze) vor +0,5 bzw. +1 × OR
        for k in (0.5, 1.0):
            ik = np.flatnonzero(fav >= k); ik = int(ik[0]) if len(ik) else len(fav)
            rec[f"retest_vor_{k}"] = bool((adv[1:ik] >= 0).any())
        # Richtungs-Rennen ab Close der Ausbruchskerze: +k×OR vor −k×OR?
        ref = C[d, tb]
        for k in (0.25, 0.5, 1.0):
            res = np.nan
            for j in range(tb + 1, b):
                if np.isnan(H[d, j]):
                    continue
                up_ok = dirn * ((H[d, j] if dirn == 1 else L[d, j]) - ref) >= k * R[d]
                dn_ok = dirn * (ref - (L[d, j] if dirn == 1 else H[d, j])) >= k * R[d]
                if up_ok and dn_ok:
                    break
                if up_ok or dn_ok:
                    res = 1.0 if up_ok else 0.0; break
            rec[f"race_{k}"] = res
        # zweiter Ausbruch nach Fehlausbruch (Gegenkante), nicht in derselben Kerze
        if fail and kf >= 1:
            t2 = tb + kf; h2, l2 = H[d, t2:b], L[d, t2:b]
            fav2 = ((orL[d] - l2) if dirn == 1 else (h2 - orH[d])) / R[d]
            adv2 = ((h2 - orL[d]) if dirn == 1 else (orH[d] - l2)) / R[d]
            rec["mfe2"] = np.nanmax(fav2); rec["fail2"] = bool((adv2[1:] > 1).any())
        rows.append(rec)
    return pd.DataFrame(rows), orH, orL


# ───────────────────────── Teil B: Trade-Simulation ─────────────────────────
@njit(cache=True)
def sim(H, L, O, C, dd, ee, ep, dirn, stop, tgt, flat, hmin, hmax, lmin, lmax, pess):
    """Ein Trade je Zeile. Einstiegskerze: bekannte Spanne nach Einstieg [hmin,hmax]/[lmin,lmax] (pessimistisch: ungünstigste Annahme,
    Stop zuerst; optimistisch: günstigste, Ziel zuerst). Danach Stop vor Ziel je Kerze. Rückgabe: Ausstiegspreis, Ergebnis (1 Ziel, -1 Stop, 0 Zeit)."""
    n = len(dd)
    xp = np.full(n, np.nan); oc = np.zeros(n)
    for i in range(n):
        d = dd[i]; e = ee[i]; s = stop[i]; t = tgt[i]; k = dirn[i]
        if np.isnan(s):
            continue
        # Einstiegskerze
        if k == 1:
            adv_x = lmin[i] if pess else lmax[i]; fav_x = hmin[i] if pess else hmax[i]
            st_hit = adv_x <= s; tg_hit = (not np.isnan(t)) and fav_x >= t
        else:
            adv_x = hmax[i] if pess else hmin[i]; fav_x = lmax[i] if pess else lmin[i]
            st_hit = adv_x >= s; tg_hit = (not np.isnan(t)) and fav_x <= t
        if pess:
            if st_hit:
                xp[i] = s; oc[i] = -1; continue
            if tg_hit:
                xp[i] = t; oc[i] = 1; continue
        else:
            if tg_hit:
                xp[i] = t; oc[i] = 1; continue
            if st_hit:
                xp[i] = s; oc[i] = -1; continue
        done = False
        for j in range(e + 1, flat[i] + 1):
            hj = H[d, j]; lj = L[d, j]
            if np.isnan(hj):
                continue
            if k == 1:
                if lj <= s:
                    xp[i] = min(s, O[d, j]) if not np.isnan(O[d, j]) else s; oc[i] = -1; done = True; break
                if (not np.isnan(t)) and hj >= t:
                    xp[i] = t; oc[i] = 1; done = True; break
            else:
                if hj >= s:
                    xp[i] = max(s, O[d, j]) if not np.isnan(O[d, j]) else s; oc[i] = -1; done = True; break
                if (not np.isnan(t)) and lj <= t:
                    xp[i] = t; oc[i] = 1; done = True; break
        if not done:
            xp[i] = C[d, flat[i]]; oc[i] = 0
    return xp, oc


def entries(D, m, orH, orL, A):
    """Trade-Kandidaten je Einstiegsart als DataFrame: d, e (Einstiegskerze), ep, dirn, edge, hmin/hmax/lmin/lmax, Signalzeit."""
    O, H, L, C = D["O"], D["H"], D["L"], D["C"]
    a, b = D["rth"]; s0 = a + m; tick = TICK[D["mk"]]; last = b - 90
    out = {k: [] for k in ("E1", "E2", "E3", "E4")}

    def brk_bar(d, j, ep, k):            # Stop-Order-Einstieg innerhalb der Kerze j
        if k == 1:
            if O[d, j] >= ep:            # Eröffnung schon jenseits → ganze Kerze nach Einstieg
                return dict(ep=O[d, j], hmin=H[d, j], hmax=H[d, j], lmin=L[d, j], lmax=L[d, j])
            return dict(ep=ep, hmin=H[d, j], hmax=H[d, j], lmin=L[d, j], lmax=min(ep, C[d, j]))
        if O[d, j] <= ep:
            return dict(ep=O[d, j], hmin=H[d, j], hmax=H[d, j], lmin=L[d, j], lmax=L[d, j])
        return dict(ep=ep, hmin=max(ep, C[d, j]), hmax=H[d, j], lmin=L[d, j], lmax=L[d, j])

    for r in A[A["brk"].isin([1, -1])].itertuples():
        d, k, tb = r.d, int(r.brk), int(r.tb)
        edge = orH[d] if k == 1 else orL[d]; oth = orL[d] if k == 1 else orH[d]
        if tb <= last:
            out["E1"].append(dict(d=d, e=tb, dirn=k, edge=edge, **brk_bar(d, tb, edge + k * tick, k)))
        # E2: erster Close jenseits der Kante (gleiche Seite wie Erstausbruch? nein – erster Close jenseits irgendeiner Seite)
        # E4: zweiter Ausbruch nach Fehlausbruch
        if r.fail and r.kf >= 1:
            t2 = tb + int(r.kf)
            if t2 <= last:
                out["E4"].append(dict(d=d, e=t2, dirn=-k, edge=oth, **brk_bar(d, t2, oth - k * tick, -k)))
    # E2/E3 unabhängig vom Erstausbruch: erster Close jenseits OR
    Cs = C[:, s0:last]
    upC = Cs > orH[:, None]; dnC = Cs < orL[:, None]
    for d in np.flatnonzero(D["day_ok"] & np.isfinite(orH - orL) & (orH > orL)):
        iu = np.argmax(upC[d]) if upC[d].any() else 10**6; idn = np.argmax(dnC[d]) if dnC[d].any() else 10**6
        if iu == idn:
            continue
        k = 1 if iu < idn else -1; t = s0 + min(iu, idn)
        edge = orH[d] if k == 1 else orL[d]
        if t + 1 < b and np.isfinite(O[d, t + 1]):
            e = t + 1
            out["E2"].append(dict(d=d, e=e, dirn=k, edge=edge, ep=O[d, e], hmin=H[d, e], hmax=H[d, e], lmin=L[d, e], lmax=L[d, e]))
        # E3: Limit an der Kante nach dem Signal, gültig bis last
        seg = (L[d, t + 1:last + 1] <= edge) if k == 1 else (H[d, t + 1:last + 1] >= edge)
        if seg.any():
            j = t + 1 + int(np.argmax(seg))
            if k == 1:
                ep = min(O[d, j], edge) if np.isfinite(O[d, j]) else edge
                rng = dict(hmin=max(ep, C[d, j]), hmax=H[d, j], lmin=L[d, j], lmax=L[d, j])
            else:
                ep = max(O[d, j], edge) if np.isfinite(O[d, j]) else edge
                rng = dict(hmin=H[d, j], hmax=H[d, j], lmin=L[d, j], lmax=min(ep, C[d, j]))
            out["E3"].append(dict(d=d, e=j, dirn=k, edge=edge, ep=ep, **rng))
    return {k: pd.DataFrame(v) for k, v in out.items()}


def run_grid(D, E, R, tg_list, sg_list, cost, pess=True):
    """Für alle (T,S): PnL netto Signal und Gegenrichtung je Trade. Rückgabe dict[(T,S)] → (pnl_sig, pnl_opp, risk_sig, oc_sig)."""
    O, H, L, C = D["O"], D["H"], D["L"], D["C"]
    b = D["rth"][1]
    dd = E["d"].to_numpy(np.int64); ee = E["e"].to_numpy(np.int64); ep = E["ep"].to_numpy(float); k = E["dirn"].to_numpy(np.int64)
    edge = E["edge"].to_numpy(float); Rr = R[dd]; fl = np.full(len(dd), b - 1, np.int64)
    hmin, hmax, lmin, lmax = (E[c].to_numpy(float) for c in ("hmin", "hmax", "lmin", "lmax"))
    res = {}
    for ti, T in enumerate(tg_list):
        for si, S in enumerate(sg_list):
            st = edge - k * S * Rr
            st = np.where(k * (ep - st) > 0, st, np.nan)            # Stop muss auf der richtigen Seite liegen
            tgt = ep + k * T * Rr if np.isfinite(T) else np.full(len(dd), np.nan)
            xp, oc = sim(H, L, O, C, dd, ee, ep, k, st, tgt, fl, hmin, hmax, lmin, lmax, pess)
            risk = k * (ep - st)
            st_o = ep + k * risk                                       # Gegenrichtung: gleiche Abstände gespiegelt
            tg_o = ep - k * T * Rr if np.isfinite(T) else np.full(len(dd), np.nan)
            xo, _ = sim(H, L, O, C, dd, ee, ep, -k, st_o, tg_o, fl, hmin, hmax, lmin, lmax, pess)
            res[(ti, si)] = (k * (xp - ep) - cost, -k * (xo - ep) - cost, risk, oc)
    return res


def summarize(pnl, opp, risk, oc, dd, D, mask, cost, Tpts):
    ok = mask & np.isfinite(pnl)
    if ok.sum() < 30:
        return None
    p, o, r = pnl[ok], opp[ok], risk[ok]
    yrs = pd.to_datetime(D["days"][dd[ok]]).year
    yr = pd.Series(p).groupby(yrs).sum()
    w, l = p[p > 0].sum(), -p[p <= 0].sum()
    daily = pd.Series(p).groupby(dd[ok]).sum()
    eq = daily.cumsum().to_numpy(); mdd = float(np.max(np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]))
    be = np.nan
    if Tpts is not None:
        tp = Tpts[ok]; be = 100 * np.mean((r + cost) / (tp + r))
    return {"Trades": int(ok.sum()), "Treffer %": round(100 * np.mean(oc[ok] == 1) if Tpts is not None else 100 * np.mean(p > 0), 1),
            "Break-even %": round(be, 1) if np.isfinite(be) else np.nan, "EW Pkt": round(p.mean(), 3), "EW R": round(np.mean(p / r), 3),
            "PF": round(w / l, 3) if l > 0 else np.nan, "Gegenrichtung EW Pkt": round(o.mean(), 3),
            "Signal − Zufall Pkt": round((p.mean() - o.mean()) / 2, 3), "Ø Risiko Pkt": round(r.mean(), 2),
            "Max DD Pkt": round(mdd, 1), "Sharpe (ann.)": round(daily.mean() / daily.std() * np.sqrt(252), 2) if daily.std() > 0 else np.nan,
            "Jahre pos": f"{int((yr > 0).sum())}/{len(yr)}", "Anteil Jahre pos": (yr > 0).mean()}


# ───────────────────────── Hauptlauf ─────────────────────────
A_all, B_rows, C_rows = [], [], []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    a, b = D["rth"]; n = D["n"]; dts = pd.to_datetime(D["days"]); per = D["period"]
    O, H, L, C = D["O"], D["H"], D["L"], D["C"]
    # Merkmale für Teil C
    prev_close = np.r_[np.nan, C[:-1, b - 1]]
    gap = O[:, a] - prev_close
    for m in ORS:
        A, orH, orL = part_a(D, m)
        R = orH - orL
        A["Markt"] = mk; A["OR"] = m; A["Zeitraum"] = per[A["d"]]; A["Tag"] = D["days"][A["d"]]
        A["R_pkt"] = A["R"]; A["atr"] = D["atr"][A["d"]]
        A_all.append(A)
        ratio = R / D["atr"]
        terz_lo = pd.Series(ratio).rolling(60, min_periods=40).quantile(1 / 3).shift(1).to_numpy()
        terz_hi = pd.Series(ratio).rolling(60, min_periods=40).quantile(2 / 3).shift(1).to_numpy()
        orc = C[:, a + m - 1] - O[:, a]
        E = entries(D, m, orH, orL, A)
        for en, Ed in E.items():
            if len(Ed) == 0:
                continue
            dd = Ed["d"].to_numpy(np.int64); k = Ed["dirn"].to_numpy()
            for pess in (True, False):
                if not pess and en == "E2":
                    continue
                res = run_grid(D, Ed, R, TG, SG, COST[mk], pess)
                np.save(CACHE / f"{mk}_OR{m}_{en}_{'pess' if pess else 'opt'}.npy",
                        np.stack([np.stack(res[(ti, si)]) for ti in range(len(TG)) for si in range(len(SG))]))
                np.save(CACHE / f"{mk}_OR{m}_{en}_d.npy", dd)
                for (ti, si), (pnl, opp, risk, oc) in res.items():
                    Tpts = TG[ti] * R[dd] if np.isfinite(TG[ti]) else None
                    for pname in ("Explore", "Validate", "Test", "letzte 5 J."):
                        msk = (per[dd] == pname) if pname != "letzte 5 J." else (dts[dd] >= LAST5)
                        s = summarize(pnl, opp, risk, oc, dd, D, msk, COST[mk], Tpts)
                        if s:
                            B_rows.append(dict(Markt=mk, OR=m, Einstieg=en, Modus="pess" if pess else "opt", T=TGN[ti], S=SG[si], Zeitraum=pname, **s))
                # Teil C – Filter (nur Explore, nur pessimistisch, E1/E2)
                if pess and en in ("E1", "E2"):
                    e_idx = Ed["e"].to_numpy(np.int64)
                    sv = D["sVW"][dd, np.maximum(e_idx - 1, 0)]
                    F = {"OR eng (unteres Terzil)": ratio[dd] <= terz_lo[dd], "OR weit (oberes Terzil)": ratio[dd] >= terz_hi[dd],
                         "Ausbruch = Gap-Richtung": np.sign(gap[dd]) == k, "Ausbruch = OR-Kerze": np.sign(orc[dd]) == k,
                         "Ausbruch ≤ 15 Min nach OR": (e_idx - (a + m)) <= 15, "Ausbruch auf VWAP-Seite": k * (Ed["edge"].to_numpy() - sv) > 0}
                    for ti in (1, 2, 4, 7):
                        for si in (1, 2):
                            pnl, opp, risk, oc = res[(ti, si)]
                            Tpts = TG[ti] * R[dd] if np.isfinite(TG[ti]) else None
                            for fn, fm in F.items():
                                for pname in ("Explore", "Validate", "Test"):
                                    s = summarize(pnl, opp, risk, oc, dd, D, (per[dd] == pname) & fm, COST[mk], Tpts)
                                    if s:
                                        C_rows.append(dict(Markt=mk, OR=m, Einstieg=en, Filter=fn, T=TGN[ti], S=SG[si], Zeitraum=pname, **s))
        print(mk, m, {k: len(v) for k, v in E.items()}, flush=True)
    del D

A_ = pd.concat(A_all, ignore_index=True); A_.to_parquet(CACHE / "h16b_A.parquet", index=False)
B_ = pd.DataFrame(B_rows); B_.to_csv(RES / "h16b_matrix.csv", index=False)
C_ = pd.DataFrame(C_rows); C_.to_csv(RES / "h16b_filter.csv", index=False)

# ───────────────────────── Auswahl nur auf Explore ─────────────────────────
def plateau_ok(row, tab):
    ti, si = TGN.index(row["T"]), list(SG).index(row["S"])
    nb = [(ti + 1, si), (ti - 1, si), (ti, si + 1), (ti, si - 1)]
    for tj, sj in nb:
        if 0 <= tj < len(TGN) and 0 <= sj < len(SG):
            x = tab.get((TGN[tj], SG[sj]))
            if x is None or not (x > 0):
                return False
    return True


cand = []
ex = B_[(B_["Zeitraum"] == "Explore") & (B_["Modus"] == "pess")]
for key, g in ex.groupby(["Markt", "OR", "Einstieg"]):
    tab = {(r["T"], r["S"]): r["EW Pkt"] for _, r in g.iterrows()}
    for _, r in g.iterrows():
        if r["EW Pkt"] > 0 and r["PF"] >= 1.15 and r["Anteil Jahre pos"] >= 0.7 and r["Trades"] >= 100 and r["Signal − Zufall Pkt"] > 0 and plateau_ok(r, tab):
            cand.append(dict(Quelle="B", Filter="ohne", **r.to_dict()))
exC = C_[C_["Zeitraum"] == "Explore"]
TGC = ["0.25", "0.5", "1", "Ende"]
for key, g in exC.groupby(["Markt", "OR", "Einstieg", "Filter"]):
    tab = {(r["T"], r["S"]): r["EW Pkt"] for _, r in g.iterrows()}
    for _, r in g.iterrows():
        ti = TGC.index(r["T"]); nbs = [(TGC[j], r["S"]) for j in (ti - 1, ti + 1) if 0 <= j < 4] + [(r["T"], 1.0 if r["S"] == 0.5 else 0.5)]
        if r["EW Pkt"] > 0 and r["PF"] >= 1.15 and r["Anteil Jahre pos"] >= 0.7 and r["Trades"] >= 100 and r["Signal − Zufall Pkt"] > 0 \
                and all(tab.get(x, -1) > 0 for x in nbs):
            cand.append(dict(Quelle="C", **r.to_dict()))
K = pd.DataFrame(cand)
print("Explore-Kandidaten vor Begrenzung:", len(K))
if len(K):
    K = K.sort_values("Sharpe (ann.)", ascending=False).head(5)
K.to_csv(RES / "h16b_kandidaten.csv", index=False)
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 40)
print(K.to_string(index=False) if len(K) else "keine Kandidaten")
