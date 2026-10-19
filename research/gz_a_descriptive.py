"""
H7 Teil A (beschreibend): Gotham Zones – HOD/LOD in Zonen, Modus-Vergleich, Reaktionsgröße, Konfluenzen.
Immer Zone vs. gleich breites Kontroll-Band (±0,25/0,75/1,25/1,75/2,25σ). Keine Tests, keine Signifikanz-Behauptungen.

Aufruf: python research/gz_a_descriptive.py → research/results/gz_a_*.csv, gz_a_report.md
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import (BOX, CONTROLS, LEVELS, MARKETS, NCOL, RES, ROUND, load_market)  # noqa: E402

TOL = 0.10        # Konfluenz: anderes Level innerhalb ±0,1σ des Extrems


def session_levels(M):
    G = M["G"]; n = len(M["days"])
    h, l, c, v = G["high"], G["low"], G["close"], G["volume"]
    with np.errstate(all="ignore"):
        rH, rL = np.nanmax(h[:, 930:1320], 1), np.nanmin(l[:, 930:1320], 1)
        onH, onL = np.nanmax(h[:, :930], 1), np.nanmin(l[:, :930], 1)
        ibH, ibL = np.nanmax(h[:, 930:990], 1), np.nanmin(l[:, 930:990], 1)
    gap = np.r_[False, np.diff(M["dts"].values).astype("timedelta64[D]").astype(int) <= 4]
    prev = lambda x: np.where(gap, np.r_[np.nan, x[:-1]], np.nan)  # noqa: E731
    # RTH-VWAP (typischer Preis), kumuliert ab 09:30
    tp = (h + l + c) / 3; vv = np.where(np.isfinite(v) & np.isfinite(tp), v, 0.0); tpz = np.nan_to_num(tp)
    cv = np.cumsum(vv[:, 930:], 1); cpv = np.cumsum((tpz * vv)[:, 930:], 1); cp2 = np.cumsum((tpz * tpz * vv)[:, 930:], 1)
    with np.errstate(all="ignore"):
        vw = cpv / cv; vsd = np.sqrt(np.maximum(cp2 / cv - vw ** 2, 0))
    VW = np.full((n, NCOL), np.nan); VS = np.full((n, NCOL), np.nan)
    VW[:, 930:] = vw; VS[:, 930:] = vsd
    return dict(pH=prev(M["H"]), pL=prev(M["L"]), prH=prev(rH), prL=prev(rL), onH=onH, onL=onL, ibH=ibH, ibL=ibL, VW=VW, VS=VS)


def weekly_levels(M, sig9):
    """Wochen-Zonen wie im Indikator: Wochen-Open (erste Session der Woche), 9D-Wert, √(Tage/252), ±1/±2σ."""
    dts = M["dts"]; wk = (dts - pd.to_timedelta(dts.weekday, unit="D")).normalize()
    df = pd.DataFrame({"wk": wk, "ref": M["ref"], "s9": sig9})
    g = df.groupby("wk")
    wo = g["ref"].transform("first").to_numpy(); s9 = g["s9"].transform("first").to_numpy()
    nd = g["ref"].transform("size").to_numpy()
    sw = s9 * np.sqrt(nd)                       # σ_9D(Tag) × √Tage = Wochen-σ
    return np.stack([wo + k * sw for k in (-2, -1, 1, 2)], 1)


rows, react, conf = [], [], []
for mk in MARKETS:
    M = load_market(mk)
    S = session_levels(M)
    G = M["G"]; n = len(M["days"])
    t_hod = np.argmax(np.nan_to_num(G["high"], nan=-np.inf), 1); t_lod = np.argmin(np.nan_to_num(G["low"], nan=np.inf), 1)
    low_after = np.array([np.nanmin(G["low"][i, t:]) for i, t in enumerate(t_hod)])
    high_after = np.array([np.nanmax(G["high"][i, t:]) for i, t in enumerate(t_lod)])
    modes = list(M["sig"].keys())
    s9 = M["sig"].get("9D", M["sig"][modes[0]])
    WL = weekly_levels(M, s9)
    for mode in modes:
        sig = M["sig"][mode]
        ok = M["valid"] & np.isfinite(sig) & (sig > 0)
        if ok.sum() < 100:
            continue
        hp, lp = (M["H"] - M["ref"]) / sig, (M["ref"] - M["L"]) / sig
        for per in ("Explore", "Validate"):
            m = ok & (M["period"] == per)
            if m.sum() < 60:
                continue
            row = dict(Markt=mk, Modus=mode, Zeitraum=per, Tage=int(m.sum()), **{"Ø σ Punkte": round(np.nanmean(sig[m]), 1)})
            zH = np.zeros(n, bool); zL = np.zeros(n, bool); cH = np.zeros(n, bool); cL = np.zeros(n, bool)
            for k in LEVELS:
                zH |= np.abs(hp - k) <= BOX; zL |= np.abs(lp - k) <= BOX
            for k in CONTROLS[:4]:
                cH |= np.abs(hp - k) <= BOX; cL |= np.abs(lp - k) <= BOX
            row.update({"HOD in Zone %": round(100 * zH[m].mean(), 1), "HOD in Kontrolle %": round(100 * cH[m].mean(), 1),
                        "LOD in Zone %": round(100 * zL[m].mean(), 1), "LOD in Kontrolle %": round(100 * cL[m].mean(), 1)})
            # fair: jede Zone gegen ihre beiden Nachbar-Bänder, und „wenn berührt → Extrem“
            fair, fair_t = [], []
            for k in LEVELS:
                for pos in (hp, lp):
                    rz = np.mean(np.abs(pos[m] - k) <= BOX)
                    rn = np.mean([np.mean(np.abs(pos[m] - c) <= BOX) for c in (k - 0.25, k + 0.25)])
                    tz = pos[m] >= k - BOX
                    tzr = np.mean(np.abs(pos[m][tz] - k) <= BOX) if tz.sum() >= 20 else np.nan
                    tn = [np.mean(np.abs(pos[m][pos[m] >= c - BOX] - c) <= BOX) for c in (k - 0.25, k + 0.25) if (pos[m] >= c - BOX).sum() >= 20]
                    fair.append(rz - rn); fair_t.append(tzr - np.mean(tn) if tn else np.nan)
            row["Zone − Nachbarn (Pkt-%)"] = round(100 * np.nanmean(fair), 2)
            row["wenn berührt → Extrem: Zone − Nachbarn (Pkt-%)"] = round(100 * np.nanmean(fair_t), 2)
            for k in LEVELS:
                th = hp[m] >= k - BOX; tl = lp[m] >= k - BOX
                row[f"±{k:g}σ berührt %"] = round(50 * (th.mean() + tl.mean()), 1)
                row[f"±{k:g}σ berührt→Extrem %"] = round(100 * (np.sum(np.abs(hp[m][th] - k) <= BOX) + np.sum(np.abs(lp[m][tl] - k) <= BOX)) / max(th.sum() + tl.sum(), 1), 1)
            rows.append(row)

        # Reaktion und Konfluenz (Explore + Validate zusammen, je Modus)
        mm = ok
        for side, pos, X, t_ex, rx, cl in (("HOD", hp, M["H"], t_hod, M["H"] - low_after, M["H"] - M["C"]),
                                           ("LOD", lp, M["L"], t_lod, high_after - M["L"], M["C"] - M["L"])):
            kind = np.full(n, "sonst", object)
            for k in LEVELS:
                kind[np.abs(pos - k) <= BOX] = "Zone"
            for c in CONTROLS[:4]:
                kind[np.abs(pos - c) <= BOX] = "Kontrolle"
            for kd in ("Zone", "Kontrolle", "sonst"):
                s = mm & (kind == kd)
                if s.sum() < 20:
                    continue
                react.append(dict(Markt=mk, Modus=mode, Extrem=side, Lage=kd, Tage=int(s.sum()),
                                  **{"Reaktion danach Median Pkt": round(np.median(rx[s]), 1), "Reaktion danach Median σ": round(np.median(rx[s] / sig[s]), 2),
                                     "Reaktion danach 25 % Pkt": round(np.percentile(rx[s], 25), 1), "Reaktion danach 75 % Pkt": round(np.percentile(rx[s], 75), 1),
                                     "bis Schluss Median Pkt": round(np.median(cl[s]), 1),
                                     "Extrem in RTH %": round(100 * np.mean((t_ex[s] >= 930) & (t_ex[s] < 1320)), 1),
                                     "Ø Uhrzeit Extrem (ET)": f"{int(((np.median(t_ex[s]) + 1080) % 1440) // 60):02d}:{int((np.median(t_ex[s]) + 1080) % 60):02d}"}))
            # Konfluenz am Extrem (Zone vs. Kontrolle)
            tol = TOL * sig
            vw = S["VW"][np.arange(n), t_ex]; vs = S["VS"][np.arange(n), t_ex]
            other = [M["sig"][o] for o in modes if o != mode]
            flags = {
                "Vortag Hoch/Tief": np.minimum(np.abs(X - S["pH"]), np.abs(X - S["pL"])) <= tol,
                "Vortag RTH Hoch/Tief": np.minimum(np.abs(X - S["prH"]), np.abs(X - S["prL"])) <= tol,
                "Overnight Hoch/Tief (Extrem in RTH)": (t_ex >= 930) & (np.minimum(np.abs(X - S["onH"]), np.abs(X - S["onL"])) <= tol),
                "IB Hoch/Tief (Extrem nach 10:30)": (t_ex >= 990) & (np.minimum(np.abs(X - S["ibH"]), np.abs(X - S["ibL"])) <= tol),
                "RTH-VWAP ±2σ": (t_ex >= 930) & (t_ex < 1320) & (np.minimum(np.abs(X - (vw + 2 * vs)), np.abs(X - (vw - 2 * vs))) <= tol),
                "Wochen-Zone": np.min(np.abs(X[:, None] - WL), 1) <= tol,
                "Zone eines anderen Modus": np.zeros(n, bool) if not other else np.any(
                    [np.min(np.abs(X[:, None] - (M["ref"][:, None] + np.array([-2, -1.5, -1, -.5, .5, 1, 1.5, 2])[None] * o[:, None])), 1) <= tol for o in other], 0),
                "Runde Zahl": np.abs(X - np.round(X / ROUND[mk]) * ROUND[mk]) <= tol,
            }
            for fn, fl in flags.items():
                rz = fl[mm & (kind == "Zone")]; rc = fl[mm & (kind == "Kontrolle")]
                if len(rz) < 20 or len(rc) < 20:
                    continue
                conf.append(dict(Markt=mk, Modus=mode, Extrem=side, Konfluenz=fn, **{"bei Zone-Extrem %": round(100 * rz.mean(), 1),
                                 "bei Kontroll-Extrem %": round(100 * rc.mean(), 1), "Verhältnis": round(rz.mean() / rc.mean(), 2) if rc.mean() > 0 else np.nan,
                                 "n Zone": len(rz), "n Kontrolle": len(rc)}))
    print(mk, "fertig", flush=True)

A, R, K = pd.DataFrame(rows), pd.DataFrame(react), pd.DataFrame(conf)
A.to_csv(RES / "gz_a_hodlod.csv", index=False); R.to_csv(RES / "gz_a_reaction.csv", index=False); K.to_csv(RES / "gz_a_confluence.csv", index=False)
core = ["Markt", "Modus", "Zeitraum", "Tage", "Ø σ Punkte", "HOD in Zone %", "HOD in Kontrolle %", "LOD in Zone %", "LOD in Kontrolle %",
        "Zone − Nachbarn (Pkt-%)", "wenn berührt → Extrem: Zone − Nachbarn (Pkt-%)"]
md = ["# Gotham Zones (ohne Kalibrierung) – HOD/LOD, Modi, Reaktion, Konfluenz", "",
      "Tag = Session 18:00–17:00 ET. Zone = Level ± 5 % σ (Box wie im Indikator). Kontrolle = gleich breite Bänder bei ±0,25/0,75/1,25/1,75σ.",
      "Explore bis 2024, Validate 2025–04/2026, Holdout nicht enthalten. 1D erst ab Mai 2022.", "",
      "## 1) HOD/LOD in Zone vs. Kontrolle", "", A[core].to_markdown(index=False), "",
      "## 2) Je Stufe: wie oft berührt, und wenn berührt – wie oft war es das Tages-Extrem?", "",
      A[["Markt", "Modus", "Zeitraum"] + [c for c in A.columns if "σ berührt" in c]].to_markdown(index=False), "",
      "## 3) Reaktion nach dem Extrem (Punkte bis zum Gegen-Extrem danach)", "", R.to_markdown(index=False), "",
      "## 4) Konfluenz am Extrem: Zone-Extrem vs. Kontroll-Extrem (±0,1σ)", "", K.to_markdown(index=False), ""]
(RES / "gz_a_report.md").write_text("\n".join(md))
print(A[core].to_string())
