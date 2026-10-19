"""
H16 – 9:30 ORB, exakt nach Vorab-Registrierung.
A: ORB-Statistik · B1: Paper-Regel (Zarattini/Aziz) · B2: klassischer Ausbruch · B3: Fehlausbruch (B2/B3 nur Explore ausgeben).
Aufruf: python research/h16_orb.py → research/results/h16_*.csv/.md
"""
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from vw_common import COST, USD, load  # noqa: E402
from vw_engine import run, stats  # noqa: E402

RES = Path(__file__).parent / "results"
CACHE = Path(__file__).resolve().parents[1] / "data-lab/data/raw/h16_cache"
CACHE.mkdir(parents=True, exist_ok=True)
LAST5 = pd.Timestamp("2021-10-18"); PUB = pd.Timestamp("2023-05-01")


def first_idx(mask):
    i = np.argmax(mask, 1).astype(float); i[~mask.any(1)] = np.nan
    return i


A_rows, B1_rows, B_rows = [], [], []
for mk in ["NQ", "ES", "RTY", "GC"]:
    D = load(mk)
    O, H, L, C = D["O"], D["H"], D["L"], D["C"]
    a, b = D["rth"]; n = D["n"]; ok = D["day_ok"]
    dts = pd.to_datetime(D["days"])
    nan = np.full_like(C, np.nan); F = np.zeros_like(C, dtype=bool)
    # ── A: Statistik ──
    for m in (5, 15, 30, 60):
        with np.errstate(all="ignore"):
            orH, orL = np.nanmax(H[:, a:a + m], 1), np.nanmin(L[:, a:a + m], 1)
        rng = orH - orL
        Hs, Ls = H[:, a + m:b], L[:, a + m:b]
        tu = first_idx(Hs > orH[:, None]); td = first_idx(Ls < orL[:, None])
        first = np.where(np.isnan(tu) & np.isnan(td), "keiner", np.where(np.isnan(td) | (tu < td), "Hoch", np.where(np.isnan(tu) | (td < tu), "Tief", "gleich")))
        ext, fail, endb = np.full(n, np.nan), np.zeros(n, bool), np.zeros(n, bool)
        for d in range(n):
            if first[d] == "Hoch":
                t = int(tu[d]); ext[d] = (np.nanmax(Hs[d, t:]) - orH[d]) / rng[d]; fail[d] = np.nanmin(Ls[d, t:]) < orL[d]; endb[d] = C[d, b - 1] > orH[d]
            elif first[d] == "Tief":
                t = int(td[d]); ext[d] = (orL[d] - np.nanmin(Ls[d, t:])) / rng[d]; fail[d] = np.nanmax(Hs[d, t:]) > orH[d]; endb[d] = C[d, b - 1] < orL[d]
        ratio = rng / D["atr"]
        terz = pd.Series(ratio).rolling(60, min_periods=40).quantile(1 / 3).shift(1).to_numpy()
        tbreak = np.where(first == "Hoch", tu, td)
        for per, pm in (("2011–2026", ok), ("letzte 5 J.", ok & (dts >= LAST5))):
            for flt, fm in (("alle", np.ones(n, bool)), ("enge OR (unteres Terzil)", ratio <= terz)):
                s = pm & fm & np.isfinite(rng) & (rng > 0)
                br = s & np.isin(first, ["Hoch", "Tief"])
                if s.sum() < 50:
                    continue
                A_rows.append(dict(Markt=mk, OR=m, Zeitraum=per, Filter=flt, Tage=int(s.sum()),
                                   **{"Ø OR/ATR": round(np.nanmean(ratio[s]), 3), "Hoch zuerst %": round(100 * np.mean(first[s] == "Hoch"), 1),
                                      "Tief zuerst %": round(100 * np.mean(first[s] == "Tief"), 1), "kein Ausbruch %": round(100 * np.mean(first[s] == "keiner"), 1),
                                      "Median Minuten bis Ausbruch": float(np.nanmedian(tbreak[br])),
                                      **{f"Ausdehnung ≥{x}×OR %": round(100 * np.mean(ext[br] >= x), 1) for x in (0.5, 1, 1.5, 2, 3)},
                                      "Gegenseite danach (Fehlausbruch) %": round(100 * np.mean(fail[br]), 1),
                                      "Schluss jenseits Ausbruchsseite %": round(100 * np.mean(endb[br]), 1)}))
    # ── B1: Paper-Regel ──
    t5 = a + 4
    o5, c5 = O[:, a], C[:, t5]
    with np.errstate(all="ignore"):
        h5, l5 = np.nanmax(H[:, a:a + 5], 1), np.nanmin(L[:, a:a + 5], 1)
    body = c5 - o5; valid = ok & np.isfinite(body) & (np.abs(body) >= 0.1 * (h5 - l5)) & (h5 > l5)
    res = {}
    for dname, dsign in (("Signal", 1), ("Gegenrichtung", -1)):
        sl, ss = F.copy(), F.copy()
        up = valid & (dsign * body > 0); dn = valid & (dsign * body < 0)
        sl[:, t5] = up; ss[:, t5] = dn
        stL, stS = nan.copy(), nan.copy(); tL, tS = nan.copy(), nan.copy()
        stL[:, t5] = l5; stS[:, t5] = h5
        tL[:, t5] = c5 + 10 * (c5 - l5); tS[:, t5] = c5 - 10 * (h5 - c5)
        T = run(O, H, L, C, sl, ss, stL, stS, tL, tS, F, F, t5, t5, b - 1, 1, COST[mk], ok)
        di = T[:, 0].astype(int)
        risk = np.where(T[:, 3] == 1, T[:, 4] - l5[di], h5[di] - T[:, 4])
        res[dname] = pd.DataFrame({"d": di, "R": T[:, 6] / np.where(risk > 0, risk, np.nan), "pnl": T[:, 6]}).set_index("d")
    sig, opp = res["Signal"], res["Gegenrichtung"]
    for per, lo, hi in (("2011–2015", "2011-01-01", "2015-12-31"), ("2016–04/2023 (Paper-Zeitraum)", "2016-01-01", "2023-04-30"),
                        ("05/2023–04/2026 (nach Veröffentlichung)", "2023-05-01", "2026-04-16")):
        idx = np.flatnonzero((dts >= lo) & (dts <= hi))
        s, o = sig[sig.index.isin(idx)], opp[opp.index.isin(idx)]
        if len(s) < 30:
            continue
        rnd = pd.concat([s["R"], o["R"]]).mean()               # Zufallsrichtung = Ø beider Richtungen
        tt = s["R"].mean() / (s["R"].std() / np.sqrt(len(s)))
        B1_rows.append(dict(Markt=mk, Zeitraum=per, Trades=len(s), **{"EW R netto": round(s["R"].mean(), 3), "t": round(tt, 2),
                            "EW Pkt netto": round(s["pnl"].mean(), 2), "Treffer %": round(100 * (s["R"] > 0).mean(), 1),
                            "Zufallsrichtung EW R": round(rnd, 3), "Signal − Zufall R": round(s["R"].mean() - rnd, 3),
                            "Summe R": round(s["R"].sum(), 1)}))
    # ── B2/B3 ──
    for m in (5, 15, 30, 60):
        e0 = a + m
        with np.errstate(all="ignore"):
            orH, orL = np.nanmax(H[:, a:e0], 1), np.nanmin(L[:, a:e0], 1)
        ratio = (orH - orL) / D["atr"]
        terz = pd.Series(ratio).rolling(60, min_periods=40).quantile(1 / 3).shift(1).to_numpy()
        win = F.copy(); win[:, e0:b - 90] = True
        OH, OL = orH[:, None] * np.ones((1, C.shape[1])), orL[:, None] * np.ones((1, C.shape[1]))
        upC, dnC = win & (C > OH), win & (C < OL)
        cs_u, cs_d = np.cumsum(upC, 1), np.cumsum(dnC, 1)
        firstU, firstD = upC & (cs_u == 1), dnC & (cs_d == 1)
        for flt in ("ohne", "eng"):
            fm = np.ones(n, bool) if flt == "ohne" else (ratio <= terz)
            # B2
            for stp, tg in itertools.product(("Gegenseite", "Mitte"), ("Ende", "1R", "2R")):
                sl, ss = firstU & fm[:, None], firstD & fm[:, None]
                # nur der erste Ausbruch des Tages (welche Seite zuerst)
                tu, td = first_idx(sl), first_idx(ss)
                sl &= ~(np.isfinite(td) & (td < tu))[:, None]; ss &= ~(np.isfinite(tu) & (tu < td))[:, None]
                mid = (OH + OL) / 2
                stL, stS = (OL, OH) if stp == "Gegenseite" else (mid, mid)
                if tg == "Ende":
                    tL = tS = nan
                else:
                    k = 1.0 if tg == "1R" else 2.0
                    tL = C + k * (C - stL); tS = C - k * (stS - C)
                T = run(O, H, L, C, sl, ss, stL, stS, tL, tS, F, F, e0, b - 90, b - 1, 1, COST[mk], ok)
                name = f"B2 OR{m} {flt} stop{stp} ziel{tg}"
                np.save(CACHE / f"{mk}_{name.replace(' ', '_')}.npy", T)
                B_rows.append({"Markt": mk, "Variante": name, **stats(T, D, USD[mk], "Explore")})
            # B3 Fehlausbruch
            for tg in ("Mitte", "Gegenseite"):
                backU = np.zeros_like(F); backD = np.zeros_like(F)
                inside = (C <= OH) & (C >= OL)
                seenU = np.cumsum(firstU, 1) > 0; seenD = np.cumsum(firstD, 1) > 0
                prevU = np.zeros_like(F); prevU[:, 1:] = seenU[:, :-1]; prevD = np.zeros_like(F); prevD[:, 1:] = seenD[:, :-1]
                ss = win & prevU & inside & fm[:, None]; sl = win & prevD & inside & fm[:, None]
                ss = ss & (np.cumsum(ss, 1) == 1); sl = sl & (np.cumsum(sl, 1) == 1)
                hiE = pd.DataFrame(np.where(np.isnan(H), -np.inf, H)).cummax(axis=1).to_numpy()
                loE = pd.DataFrame(np.where(np.isnan(L), np.inf, L)).cummin(axis=1).to_numpy()
                tS = (OH + OL) / 2 if tg == "Mitte" else OL
                tL = (OH + OL) / 2 if tg == "Mitte" else OH
                T = run(O, H, L, C, sl, ss, loE, hiE, tL, tS, F, F, e0, b - 90, b - 1, 1, COST[mk], ok)
                name = f"B3 OR{m} {flt} ziel{tg}"
                np.save(CACHE / f"{mk}_{name.replace(' ', '_')}.npy", T)
                B_rows.append({"Markt": mk, "Variante": name, **stats(T, D, USD[mk], "Explore")})
    print(mk, flush=True)
    del D

A_, B1_, B_ = pd.DataFrame(A_rows), pd.DataFrame(B1_rows), pd.DataFrame(B_rows)
A_.to_csv(RES / "h16_stats.csv", index=False); B1_.to_csv(RES / "h16_paper.csv", index=False); B_.to_csv(RES / "h16_explore.csv", index=False)
pd.set_option("display.width", 280); pd.set_option("display.max_rows", 300)
print(A_[A_["Filter"] == "alle"].to_string(index=False))
print(B1_.to_string(index=False))
g = B_[(B_["EW Pkt"] > 0) & (B_["PF"] >= 1.15)].sort_values("Sharpe Tag (ann.)", ascending=False)
print(g[["Markt", "Variante", "Trades", "Trades/Tag", "EW Pkt", "Treffer %", "PF", "Max DD Pkt", "Sharpe Tag (ann.)", "Jahre pos"]].to_string(index=False))
print("B2/B3 Varianten:", len(B_), "– davon EW>0 & PF≥1,15:", len(g))
