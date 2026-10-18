"""
Projekt ib-first – stabile Analyse und Modell für „Tief zuerst → Hoch wird geholt“ (und umgekehrt).

Je Markt (NQ, ES, RTY, GC) × Startzeit (25) × IB-Länge (15/30/45/60) und Tag (1m-Bars, Tagesende 17:00 vor 09:30,
sonst 16:00; Tage, an denen Hoch und Tief im selben Bar entstehen, fallen raus):
  Merkmale am IB-Ende
    side  1 = Tief zuerst, 0 = Hoch zuerst
    z     IB-Größe: ln(Range / Median der 20 Tage davor), begrenzt auf ±1,2 (≈ 0,3× … 3,3×), dazu z²
    pos   Lage des Schlusskurses am IB-Ende Richtung Gegenseite (0 = an der Erstseite, 1 = an der Gegenseite), dazu pos²
    wd    Wochentag (Di–Fr als Abweichung vom Montag)
  Ziele
    ext   P(Gegenseite + x IB erreicht), x = 0 … 2 IB (x = 0: Gegenseite überhaupt geholt) – EIN Modell mit u = ln(x + 0,05), u²
    zuerst P(Gegenseite wird geholt, BEVOR die Erstseite noch einmal bricht)   („Ziel vor Stop“)
    erst  P(Erstseite wird noch einmal gebrochen)
  Modell: logistische Regression mit Ridge-Dämpfung (Achsenabschnitt und side ungedämpft).

Auswahl (nur Validierung, Testjahr unberührt):
  Merkmalsstufen A (side) · B (+ Größe) · C (+ Lage) · D (+ Wochentag), Dämpfung λ, Fenster 3 oder 5 Jahre
  → Training bis 2 Jahre vor Ende, Validierung = vorletztes Jahr, kleinster Log-Loss über alle Märkte/Starts/Längen.
Test: gewählte Einstellung, Training bis 1 Jahr vor Ende → letztes Jahr (ungesehen): Log-Loss vs. Stufe A, Kalibrierung,
  TP-Modus (weitestes x mit P ≥ 60/70/80/90 %), große IBs (oberstes Zehntel).
Beste IB-Länge je Wochentag: höchste Quote „Ziel vor Stop“ im Trainingsfenster (gedämpft Richtung Längen-Schnitt);
  Test: je Wochentag gewählt vs. eine feste beste Länge vs. immer 30 Min.
Endgültig: Training auf dem jüngsten Fenster bis zum letzten Datentag → results/ib_first_model.json

Aufruf: python data-lab/ib_first_model.py   → results/ib_first_model.md, results/ib_first_model.json
"""
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENGTHS = [15, 30, 45, 60]
NCOL = 1380
XG = np.round(np.arange(0, 2.001, 0.1), 2)            # Ausdehnung über die Gegenseite in IB-Ranges
ZMAX = 1.2
LEVELS = {"A": ["side"], "B": ["side", "z", "z2"], "C": ["side", "z", "z2", "pos", "pos2"],
          "D": ["side", "z", "z2", "pos", "pos2", "w1", "w2", "w3", "w4"]}
FULL = LEVELS["D"]                                    # Reihenfolge der Koeffizienten im Indikator (+ Achsenabschnitt)
LAMS = [1.0, 10.0, 100.0]
WINDOWS = [3, 5]
TP_MODES = [0.6, 0.7, 0.8, 0.9]
CMAX = 19.2
WDN = ["Mo", "Di", "Mi", "Do", "Fr"]


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fit_logit(X, y, w, lam, pen, it=40):
    """Gewichtete logistische Regression, Ridge auf Spalten mit pen = True."""
    b = np.zeros(X.shape[1])
    P = np.diag(pen.astype(float)) * lam + np.eye(X.shape[1]) * 1e-6
    for _ in range(it):
        p = np.clip(sigmoid(X @ b), 1e-6, 1 - 1e-6)
        W = w * p * (1 - p)
        g = X.T @ (w * (y - p)) - P @ b
        Hm = X.T @ (X * W[:, None]) + P
        step = np.linalg.solve(Hm, g)
        b += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return np.clip(b, -CMAX, CMAX)


def logloss(p, y, w=None):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    l = -(y * np.log(p) + (1 - y) * np.log(1 - p))
    return np.average(l, weights=w), (w.sum() if w is not None else len(l))


def window_days(G, dts, s, L, e):
    Hw, Lw = G["high"][:, s:s + L], G["low"][:, s:s + L]
    with np.errstate(all="ignore"):
        H, Lo = np.nanmax(Hw, 1), np.nanmin(Lw, 1)
    R = H - Lo
    v = (np.isfinite(Hw).mean(1) >= 0.8) & (R > 0) & (dts.weekday < 5) & np.isfinite(G["high"][:, e - 30:e]).any(1)
    med = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
    iH = np.argmax(np.nan_to_num(Hw, nan=-np.inf), 1); iL = np.argmin(np.nan_to_num(Lw, nan=np.inf), 1)
    lf = iL < iH
    v &= (iL != iH) & np.isfinite(med)
    c = G["cff"][:, s + L - 1]
    pr = (c - Lo) / R
    pos = np.clip(np.where(lf, pr, 1 - pr), 0, 1)
    z = np.clip(np.log(R / med), -ZMAX, ZMAX)
    Hp, Lp = G["high"][:, s + L:e], G["low"][:, s + L:e]
    with np.errstate(invalid="ignore", all="ignore"):
        tu = first_true(Hp > H[:, None]); td = first_true(Lp < Lo[:, None])
        mx, mn = np.nanmax(Hp, 1), np.nanmin(Lp, 1)
    opp = np.where(lf, mx > H, mn < Lo)
    ext = np.where(lf, (mx - H) / R, (Lo - mn) / R)
    same = np.where(lf, mn < Lo, mx > H)
    t_o, t_s = np.where(lf, tu, td), np.where(lf, td, tu)
    first = np.isfinite(t_o) & (t_o < t_s)
    wd = dts.weekday.to_numpy()
    F = pd.DataFrame({"side": lf.astype(float), "z": z, "z2": z * z, "pos": pos, "pos2": pos * pos,
                      **{f"w{k}": (wd == k).astype(float) for k in range(1, 5)}})
    return dict(v=v, F=F, opp=opp, ext=np.nan_to_num(ext, nan=-1), first=first, same=same, wd=np.minimum(wd, 4), R=R, z=z)


def design(D, idx, cols):
    return np.column_stack([np.ones(len(idx))] + [D["F"][c].to_numpy()[idx] for c in cols])


def ext_rows(D, idx, cols):
    X0 = design(D, idx, cols)
    u = np.log(XG + 0.05)
    X = np.vstack([np.column_stack([X0, np.full(len(idx), ui), np.full(len(idx), ui * ui)]) for ui in u])
    y = np.concatenate([(D["opp"][idx] if x == 0 else D["ext"][idx] >= x) for x in XG]).astype(float)
    w = np.full(len(y), 1.0 / len(XG))                    # jeder Tag zählt insgesamt einmal
    return X, y, w


def fit_all(D, idx, cols, lam):
    pen = np.array([False] + [c not in ("side",) for c in cols])
    Xe, ye, we = ext_rows(D, idx, cols)
    be = fit_logit(Xe, ye, we, lam, np.concatenate([pen, [False, False]]))
    X = design(D, idx, cols)
    bf = fit_logit(X, D["first"][idx].astype(float), np.ones(len(idx)), lam, pen)
    bs = fit_logit(X, D["same"][idx].astype(float), np.ones(len(idx)), lam, pen)
    return be, bf, bs


def evaluate(D, idx, cols, B):
    be, bf, bs = B
    Xe, ye, we = ext_rows(D, idx, cols)
    X = design(D, idx, cols)
    return {"ext": logloss(sigmoid(Xe @ be), ye, we), "zuerst": logloss(sigmoid(X @ bf), D["first"][idx].astype(float)),
            "erst": logloss(sigmoid(X @ bs), D["same"][idx].astype(float))}


def to_full(b, cols, extra=0):
    """Koeffizienten in die volle Reihenfolge [1] + FULL (+ u, u²) bringen, fehlende = 0."""
    out = np.zeros(1 + len(FULL) + extra)
    out[0] = b[0]
    for i, c in enumerate(cols):
        out[1 + FULL.index(c)] = b[1 + i]
    if extra:
        out[-extra:] = b[-extra:]
    return out


def p_ext(be_full, F_row, x):
    xr = np.concatenate([[1.0], F_row])
    u = np.log(x + 0.05)
    return sigmoid(xr @ be_full[:-2] + be_full[-2] * u + be_full[-1] * u * u)


# ═══ Daten laden ═══
cache = {}
for mk in MARKETS:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2018-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    end = dts.max()
    yrs = lambda a, b, dts=dts, end=end: np.asarray((dts > end - pd.DateOffset(years=a)) & (dts <= end - pd.DateOffset(years=b)))
    for st in STARTS:
        s = rel(st); e = NCOL if s < rel("09:30") else rel("16:00")
        for L in LENGTHS:
            if s + L > e - 30:
                continue
            D = window_days(G, dts, s, L, e)
            D["yrs"] = yrs
            cache[(mk, st, L)] = D
    print(mk, "geladen", flush=True)
END = str(end.date())

# ═══ 1) Auswahl auf der Validierung ═══
val = []
for (mk, st, L), D in cache.items():
    yrs, v = D["yrs"], D["v"]
    iv = np.flatnonzero(v & yrs(2, 1))
    if len(iv) < 60:
        continue
    for wn in WINDOWS:
        it = np.flatnonzero(v & yrs(2 + wn, 2))
        if len(it) < 150:
            continue
        for lv, cols in LEVELS.items():
            for lam in (LAMS if lv != "A" else [1.0]):
                ev = evaluate(D, iv, cols, fit_all(D, it, cols, lam))
                for tgt, (ll, n) in ev.items():
                    val.append(dict(Markt=mk, Start=st, IB=L, Fenster=wn, Stufe=lv, lam=lam, Ziel=tgt, ll=ll, n=n))
    print("Validierung", mk, st, L, flush=True) if st == "09:30" else None
V = pd.DataFrame(val)
# nur Kombinationen, die in allen Varianten vorhanden sind, vergleichen
keyc = ["Markt", "Start", "IB", "Ziel"]
V = V.groupby(keyc).filter(lambda g: len(g) == g.groupby(["Fenster", "Stufe", "lam"]).ngroups and g["Fenster"].nunique() == len(WINDOWS))
VS = V.assign(lln=V["ll"] * V["n"]).groupby(["Ziel", "Fenster", "Stufe", "lam"]).agg(lln=("lln", "sum"), n=("n", "sum"))
VS["Log-Loss"] = VS["lln"] / VS["n"]
best = {tgt: VS.loc[tgt]["Log-Loss"].idxmin() for tgt in ("ext", "zuerst", "erst")}
print("Auswahl:", best, flush=True)
# eine gemeinsame Einstellung für alle drei Ziele (einfacher im Indikator): die mit der kleinsten Summe
tot = VS.reset_index().groupby(["Fenster", "Stufe", "lam"])["Log-Loss"].sum()
WIN, LEV, LAM = tot.idxmin()
COLS = LEVELS[LEV]
print("gemeinsam:", WIN, LEV, LAM, flush=True)

# ═══ 2) Test im letzten Jahr ═══
test_ll, calib, tpm, bigiv, rows_first = [], [], [], [], []
for (mk, st, L), D in cache.items():
    yrs, v = D["yrs"], D["v"]
    it, ix = np.flatnonzero(v & yrs(1 + WIN, 1)), np.flatnonzero(v & yrs(1, 0))
    if len(it) < 150 or len(ix) < 60:
        continue
    B = fit_all(D, it, COLS, LAM)
    BA = fit_all(D, it, LEVELS["A"], 1.0)
    for name, cols, b in (("gewählt", COLS, B), ("nur Erstes (A)", LEVELS["A"], BA)):
        for tgt, (ll, n) in evaluate(D, ix, cols, b).items():
            test_ll.append(dict(Markt=mk, Modell=name, Ziel=tgt, ll=ll, n=n))
    X = design(D, ix, COLS)
    pz, ps = sigmoid(X @ B[1]), sigmoid(X @ B[2])
    be = to_full(B[0], COLS, 2)
    Fx = np.column_stack([D["F"][c].to_numpy()[ix] for c in FULL])
    po = np.array([p_ext(be, f, 0.0) for f in Fx])
    calib += [pd.DataFrame({"Ziel": "Gegenseite", "p": po, "y": D["opp"][ix]}),
              pd.DataFrame({"Ziel": "Ziel vor Stop", "p": pz, "y": D["first"][ix]}),
              pd.DataFrame({"Ziel": "Erstseite nochmal", "p": ps, "y": D["same"][ix]})]
    # große IBs (oberstes Zehntel der Größe im Trainingsfenster)
    zq = np.quantile(D["z"][it], 0.9)
    big = D["z"][ix] >= zq
    bigiv.append(pd.DataFrame({"Markt": mk, "p": po[big], "y": D["opp"][ix][big]}))
    # TP-Modus: weitestes x mit P ≥ Schwelle (von 0 aufwärts, bis zum ersten Unterschreiten)
    PX = np.array([[p_ext(be, f, x) for x in XG] for f in Fx])
    for thr in TP_MODES:
        okm = PX >= thr
        stop = np.where(okm.all(1), len(XG), np.argmin(okm, 1))       # erster Index unter der Schwelle
        has = stop > 0
        k = np.maximum(stop - 1, 0)
        xs = XG[k]
        hit = np.where(xs == 0, D["opp"][ix], D["ext"][ix] >= xs)
        tpm.append(pd.DataFrame({"Markt": mk, "Start": st, "IB": L, "Modus": f"≥ {thr:.0%}", "hat": has,
                                 "x": np.where(has, xs, np.nan), "p": np.where(has, PX[np.arange(len(ix)), k], np.nan), "hit": hit}))
    # für die beste Länge je Wochentag: Quote „Ziel vor Stop“ je Tag
    rows_first.append(pd.DataFrame({"Markt": mk, "Start": st, "IB": L, "Tag": D["wd"][np.concatenate([it, ix])],
                                    "Zeitraum": ["Training"] * len(it) + ["Test"] * len(ix),
                                    "zuerst": D["first"][np.concatenate([it, ix])]}))
    print("Test", mk, st, L, flush=True) if st == "09:30" else None

T = pd.DataFrame(test_ll).assign(lln=lambda t: t["ll"] * t["n"]).groupby(["Ziel", "Modell"]).agg(lln=("lln", "sum"), n=("n", "sum"))
T["Log-Loss"] = (T["lln"] / T["n"]).round(4)
C = pd.concat(calib, ignore_index=True)
C["Band"] = pd.cut(C["p"], [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0], labels=["< 50", "50–60", "60–70", "70–80", "80–90", "90–100"])
CAL = C.groupby(["Ziel", "Band"], observed=True).agg(Tage=("y", "size"), angezeigt=("p", "mean"), eingetreten=("y", "mean")).round(3)
TP = pd.concat(tpm, ignore_index=True)
TPS = TP.groupby("Modus").apply(lambda g: pd.Series({"Tage mit TP": f"{g['hat'].mean():.0%}",
                                                    "Ø Ausdehnung (IB)": round(g.loc[g["hat"], "x"].mean(), 2),
                                                    "angezeigt": round(g.loc[g["hat"], "p"].mean(), 3),
                                                    "eingetreten": round(g.loc[g["hat"], "hit"].mean(), 3)}))
BIG = pd.concat(bigiv).groupby("Markt").agg(Tage=("y", "size"), angezeigt=("p", "mean"), eingetreten=("y", "mean")).round(3)

# beste IB-Länge je Wochentag: gewählt im Training, geprüft im Test
RF = pd.concat(rows_first, ignore_index=True)
cmp_rows, bestL = [], {}
for (mk, st), g in RF.groupby(["Markt", "Start"]):
    tr, te = g[g["Zeitraum"] == "Training"], g[g["Zeitraum"] == "Test"]
    if tr["IB"].nunique() < 2:
        continue
    rL = tr.groupby("IB")["zuerst"].mean()
    globL = rL.idxmax()
    for d in range(5):
        t = tr[tr["Tag"] == d]
        rr = t.groupby("IB")["zuerst"].agg(["sum", "count"])
        shr = (rr["sum"] + 30 * rL.reindex(rr.index)) / (rr["count"] + 30)
        Ld = shr.idxmax()
        x = te[te["Tag"] == d]
        q = lambda LL: x[x["IB"] == LL]["zuerst"].mean()
        cmp_rows.append(dict(Markt=mk, Start=st, Tag=WDN[d], je_Tag=q(Ld), feste_beste=q(globL), immer_30=q(30) if 30 in rL.index else np.nan,
                             n=len(x[x["IB"] == Ld])))
CMP = pd.DataFrame(cmp_rows)
CMPS = CMP.groupby("Tag")[["je_Tag", "feste_beste", "immer_30"]].mean().reindex(WDN).round(3)
CMPA = CMP[["je_Tag", "feste_beste", "immer_30"]].mean().round(3)

# ═══ 3) Endgültig: jüngstes Fenster bis zum letzten Datentag ═══
final = {}
for (mk, st, L), D in cache.items():
    yrs, v = D["yrs"], D["v"]
    it = np.flatnonzero(v & yrs(WIN, 0))
    if len(it) < 150:
        continue
    B = fit_all(D, it, COLS, LAM)
    final[f"{mk}|{st}|{L}"] = dict(ext=to_full(B[0], COLS, 2).round(4).tolist(), zuerst=to_full(B[1], COLS).round(4).tolist(),
                                   erst=to_full(B[2], COLS).round(4).tolist(), n=int(len(it)))
RFF = []
for (mk, st, L), D in cache.items():
    yrs, v = D["yrs"], D["v"]
    it = np.flatnonzero(v & yrs(WIN, 0))
    if len(it) >= 150:
        RFF.append(pd.DataFrame({"Markt": mk, "Start": st, "IB": L, "Tag": D["wd"][it], "zuerst": D["first"][it]}))
RFF = pd.concat(RFF, ignore_index=True)
for (mk, st), g in RFF.groupby(["Markt", "Start"]):
    rL = g.groupby("IB")["zuerst"].mean()
    for d in range(5):
        rr = g[g["Tag"] == d].groupby("IB")["zuerst"].agg(["sum", "count"])
        shr = (rr["sum"] + 30 * rL.reindex(rr.index)) / (rr["count"] + 30)
        bestL[f"{mk}|{st}|{d}"] = int(shr.idxmax()) if len(shr) else 30
(HERE / "results/ib_first_model.json").write_text(json.dumps({"end": END, "window": int(WIN), "level": LEV, "lam": LAM, "cols": COLS,
                                                               "full": FULL, "xg": XG.tolist(), "zmax": ZMAX, "coef": final, "bestL": bestL}))

BL = pd.DataFrame([dict(Markt=k.split("|")[0], Start=k.split("|")[1], Tag=WDN[int(k.split("|")[2])], IB=v) for k, v in bestL.items()])
md = ["# IB First – stabile Analyse (Tief zuerst → Hoch wird geholt)", "",
      f"Daten bis {END}. Merkmale am IB-Ende: Erstes Extrem, IB-Größe ggü. 20 Vortagen, Lage des Kurses, Wochentag.",
      "Auswahl nur auf der Validierung (vorletztes Jahr); Test = letztes Jahr, in keinem Schritt benutzt.", "",
      "## 1) Auswahl (Validierung, Log-Loss – kleiner = besser)", "",
      "Stufen: A = nur Erstes Extrem · B = + IB-Größe · C = + Lage des Kurses · D = + Wochentag; λ = Dämpfung; Fenster in Jahren.", "",
      VS["Log-Loss"].unstack("Ziel").round(4).to_markdown(), "",
      f"**Gewählt (gemeinsam für alle Ziele): Stufe {LEV}, λ = {LAM:g}, Fenster {WIN} Jahre.** Je Ziel allein am besten: "
      + ", ".join(f"{k}: Stufe {v[1]}, λ {v[2]:g}, {v[0]} J" for k, v in best.items()), "",
      "## 2) Test im letzten Jahr", "", "### Log-Loss gewählt vs. nur Erstes Extrem", "", T[["Log-Loss", "n"]].to_markdown(), "",
      "### Kalibrierung (angezeigt vs. eingetreten)", "", CAL.to_markdown(), "",
      "### TP-Modus: weitestes Ziel mit P ≥ Schwelle", "", TPS.to_markdown(), "",
      "### Große IBs (oberstes Zehntel, z. B. News): Gegenseite geholt", "", BIG.to_markdown(), "",
      "### Beste IB-Länge je Wochentag – Quote „Ziel vor Stop“ im Testjahr", "",
      "je_Tag = Länge je Wochentag im Training gewählt · feste_beste = eine Länge für alle Tage · immer_30 = immer 30 Min", "",
      CMPS.to_markdown(), "", f"Alle Tage: je_Tag {CMPA['je_Tag']:.3f} · feste_beste {CMPA['feste_beste']:.3f} · immer_30 {CMPA['immer_30']:.3f}", "",
      "## 3) Beste IB-Länge je Wochentag im Indikator (jüngstes Fenster)", "",
      BL[BL["Start"].isin(["03:00", "08:30", "09:30", "10:00"])].pivot_table(index=["Markt", "Start"], columns="Tag", values="IB").reindex(columns=WDN).to_markdown(), ""]
(HERE / "results/ib_first_model.md").write_text("\n".join(md))
print("\n".join(md))
