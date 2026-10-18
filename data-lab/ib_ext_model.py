"""
IB-Expansion als kompakte Formel statt Tabelle – alle Märkte in EINEM Pine-Indikator.

Gleiche Größen wie data-lab/ib_ext_stats.py (Levels ±0 … ±3 IB, IB-Größe klein/normal/groß, Rücklauf nach 09:30),
aber die Wahrscheinlichkeit "Level wird bis Tagesende noch erreicht" wird je Fenster x Größe x Seite durch eine
logistische Formel beschrieben:
    logit p = b0 + b1·u + b2·v + b3·u·v + b4·u²,   u = ln(d + 0,03),  v = ln(1 − q + 0,02)
    d = Abstand Level ↔ aktueller Close in IB-Ranges, q = vergangener Anteil der Restzeit
Rücklauf genauso (d = Abstand zum IB-Rand, q ab 09:30).
Angepasst (gewichtete logistische Regression) auf fein gerasterten Zählungen (d in 0,05-Schritten, q in 10 Stufen).

Wochentag: je Seite ein Zuschlag w[Seite, Mo–Fr] auf logit p (gemeinsam für alle Größen), geschätzt mit Dämpfung
Richtung 0 (Ridge, in "Tagen" gemessen: jeder Handelstag zählt als eine Beobachtung). Die Dämpfung λ wird auf dem
Prüfjahr gewählt (kleinster Log-Loss), Test im ungesehenen letzten Jahr gegen die Version ohne Wochentag.

Speicher je Fenster: 6 Formeln (3 Größen x 2 Seiten) + 2 Rücklauf-Formeln = 40 Zahlen + 2 Größen-Schwellen
+ 10 Wochentag-Zuschläge, je Zahl 2 Zeichen → 104 Zeichen.

Prüfung wie in ib_ext_stats.py:
  Korrektur δ aus Prüfjahr (Formel aus Jahren 4–2 zurück → Jahr 2–1 zurück),
  Test: Formel aus den 3 Jahren vor dem letzten Jahr → letztes Jahr (ungesehen), mit Korrektur.
  Endgültig: Formel aus den letzten 3 Jahren, δ aus (3–1 Jahre zurück → letztes Jahr).
Ausgabe: data-lab/results/ib_ext_model.md und gotham-zones/IB-Expansion_ALL.pine (aus IB-Expansion-ALL_template.pine)

Aufruf: python data-lab/ib_ext_model.py          (alles neu, ~15 Min)
       python data-lab/ib_ext_model.py --pine   (nur Pine-Datei neu aus results/ib_ext_coefs.json)
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENGTHS = [15, 30, 45, 60]
NCOL = 1380
YEARS = 3
K = 31
NQB = 10
DSTEP, NDF = 0.05, 81          # feine Abstandsstufen 0 … 4,0 (+ > 4)
THR = 0.70
NCOEF = 5
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
CMAX = 19.2                    # Wertebereich je Koeffizient (2 Zeichen, Schritt 0,01)
NCH = 104                      # Zeichen je Fenster
LAMS = [None, 1, 3, 10, 30]    # Varianten: ohne Wochentag, Wochentag mit Dämpfung λ (in Tagen)
REL930 = (9 * 60 + 30 - 1080) % 1440


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def feats(d, q):
    u = np.log(np.maximum(d, 0) + 0.03)
    v = np.log(1 - np.clip(q, 0, 0.98) + 0.02)
    return np.stack([np.ones_like(u), u, v, u * v, u * u], axis=-1)


def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -30, 30)))


def fit_logit(X, y, w, lam=1e-3, it=30):
    b = np.zeros(X.shape[1])
    for _ in range(it):
        p = np.clip(sigmoid(X @ b), 1e-6, 1 - 1e-6)
        W = w * p * (1 - p)
        z = X @ b + (y - p) / (p * (1 - p))
        A = X.T @ (X * W[:, None]) + lam * np.eye(X.shape[1])
        nb = np.linalg.solve(A, X.T @ (W * z))
        if np.max(np.abs(nb - b)) < 1e-6:
            b = nb
            break
        b = nb
    return np.clip(b, -CMAX, CMAX)


def window_days(G, fin, wd, s, L, e, eth):
    W = slice(s, s + L)
    cov = fin[:, W].sum(1) / L
    with np.errstate(all="ignore"):
        H = np.nanmax(G["high"][:, W], 1)
        Lo = np.nanmin(G["low"][:, W], 1)
    R = H - Lo
    v = (cov >= (0.5 if eth else 0.8)) & fin[:, e - 30:e].any(1) & np.isfinite(R) & (R > 0) & (wd < 5)
    rmed = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
    rsize = (R / rmed)[v]
    cff = pd.DataFrame(G["close"][v][:, :e]).ffill(axis=1).to_numpy()
    H, Lo, R = H[v], Lo[v], R[v]
    Hp, Lp = G["high"][v][:, s + L:e], G["low"][v][:, s + L:e]
    tu = np.empty((v.sum(), K)); td = np.empty((v.sum(), K))
    with np.errstate(invalid="ignore"):
        tu[:, 0] = first_true(Hp > H[:, None]); td[:, 0] = first_true(Lp < Lo[:, None])
        for k in range(1, K):
            tu[:, k] = first_true(Hp >= (H + 0.1 * k * R)[:, None])
            td[:, k] = first_true(Lp <= (Lo - 0.1 * k * R)[:, None])
    Cp = cff[:, s + L - 1:e]
    i930 = REL930 - (s + L) if s + L <= REL930 else -1
    o930 = None
    if i930 >= 0:
        o930 = G["open"][v][:, REL930]
        o930 = np.where(np.isfinite(o930), o930, cff[:, REL930 - 1])
    return dict(v=v, wd=wd[v], tu=tu, td=td, npost=e - s - L, H=H, Lo=Lo, R=R, Cp=Cp, Hp=Hp, Lp=Lp, rsize=rsize, i930=i930, o930=o930)


def classes(rsize, thr):
    c = np.where(rsize <= thr[0], 1, np.where(rsize >= thr[1], 3, 2))
    return np.where(np.isfinite(rsize), c, 0)


def snapshots(D, idx, qi):
    t = int(qi * D["npost"] / NQB)
    H, Lo, R = D["H"][idx], D["Lo"][idx], D["R"][idx]
    c = D["Cp"][idx, t]
    ks = np.arange(K)[None, :]
    out = []
    for tt, lv, sgn in [(D["tu"][idx], H[:, None] + 0.1 * ks * R[:, None], 1),
                        (D["td"][idx], Lo[:, None] - 0.1 * ks * R[:, None], -1)]:
        d = sgn * (lv - c[:, None]) / R[:, None]
        out.append((~(tt + 1 <= t) & (d >= 0), d, np.isfinite(tt)))
    return out


def rt_snapshots(D, idx, qi):
    i0 = D["i930"]
    if i0 < 0:
        return None
    t = i0 + int(qi * (D["npost"] - i0) / NQB)
    H, Lo, R, o = D["H"][idx], D["Lo"][idx], D["R"][idx], D["o930"][idx]
    Lp, Hp, c = D["Lp"][idx], D["Hp"][idx], D["Cp"][idx, t]
    with np.errstate(all="ignore"):
        lo_b = np.nanmin(Lp[:, i0:t], 1) if t > i0 else np.full(len(idx), np.inf)
        hi_b = np.nanmax(Hp[:, i0:t], 1) if t > i0 else np.full(len(idx), -np.inf)
        lo_a, hi_a = np.nanmin(Lp[:, t:], 1), np.nanmax(Hp[:, t:], 1)
    return [((o > H) & ~(lo_b <= H), (c - H) / R, lo_a <= H), ((o < Lo) & ~(hi_b >= Lo), (Lo - c) / R, hi_a >= Lo)]


def wd_offsets(cntw, hitw, B, X, nday, lam):
    """Wochentag-Zuschlag je Seite (logit), Ridge-gedämpft; Gewicht je Wochentag = Anzahl Tage."""
    W = np.zeros((2, 5))
    if lam is None:
        return W
    for side in range(2):
        z = np.concatenate([X @ B[c, side] for c in range(3)])
        for w in range(5):
            n = cntw[w, 1:, side].reshape(-1); h = hitw[w, 1:, side].reshape(-1)
            if n.sum() == 0 or nday[w] == 0:
                continue
            sc = nday[w] / n.sum()
            x = 0.0
            for _ in range(40):
                p = sigmoid(z + x)
                x += ((h - n * p).sum() * sc - lam * x) / ((n * p * (1 - p)).sum() * sc + lam + 1e-9)
            W[side, w] = np.clip(x, -CMAX, CMAX)
    return W


def fit_window(D, m, cls, lams=(None,)):
    """Formeln aus Tagen m: B[größe 1–3, seite] (5 Koeff.), RT[seite] (5 Koeff., NaN wenn nicht anwendbar),
    W[λ] = Wochentag-Zuschläge [seite, Mo–Fr] je Dämpfung λ (None = ohne Wochentag)."""
    B = np.full((3, 2, NCOEF), np.nan)
    pooled = {}
    cntw = np.zeros((5, 4, 2, NQB, NDF)); hitw = np.zeros((5, 4, 2, NQB, NDF))
    for ci in (1, 2, 3):
        idx = np.flatnonzero(m & (cls == ci))
        wdi = D["wd"][idx]
        for qi in range(NQB):
            for side, (ok, d, reached) in (enumerate(snapshots(D, idx, qi)) if len(idx) else []):
                b = np.minimum((d / DSTEP).astype(int), NDF - 1)
                r, k = np.nonzero(ok)
                np.add.at(cntw[:, ci, side, qi], (wdi[r], b[r, k]), 1)
                np.add.at(hitw[:, ci, side, qi], (wdi[r], b[r, k]), reached[r, k])
    cnt, hit = cntw.sum(0), hitw.sum(0)
    cnt[0], hit[0] = cnt[1:].sum(0), hit[1:].sum(0)
    nday = np.array([(m & (cls > 0) & (D["wd"] == w)).sum() for w in range(5)])
    qq = (np.arange(NQB) / NQB)[:, None] * np.ones((1, NDF))
    dd = np.ones((NQB, 1)) * ((np.arange(NDF) + 0.5) * DSTEP)[None, :]
    X = feats(dd.reshape(-1), qq.reshape(-1))
    for side in range(2):
        n0 = cnt[0, side].reshape(-1)
        pooled[side] = fit_logit(X[n0 > 0], hit[0, side].reshape(-1)[n0 > 0] / n0[n0 > 0], n0[n0 > 0])
        for ci in (1, 2, 3):
            n = cnt[ci, side].reshape(-1)
            B[ci - 1, side] = fit_logit(X[n > 0], hit[ci, side].reshape(-1)[n > 0] / n[n > 0], n[n > 0]) if n.sum() >= 2000 else pooled[side]
    RT = np.full((2, NCOEF), np.nan)
    if D["i930"] >= 0:
        rc = np.zeros((2, NQB, NDF)); rh = np.zeros((2, NQB, NDF))
        idx = np.flatnonzero(m)
        for qi in range(NQB):
            for side, (ok, d, back) in enumerate(rt_snapshots(D, idx, qi)):
                b = np.minimum((np.maximum(d, 0) / DSTEP).astype(int), NDF - 1)
                np.add.at(rc[side, qi], b[ok], 1); np.add.at(rh[side, qi], b[ok], back[ok])
        for side in range(2):
            n = rc[side].reshape(-1)
            if n.sum() >= 50:
                RT[side] = fit_logit(X[n > 0], rh[side].reshape(-1)[n > 0] / n[n > 0], n[n > 0])
    return B, RT, {lam: wd_offsets(cntw, hitw, B, X, nday, lam) for lam in lams}


def vname(lam):
    return "ohne" if lam is None else f"wd{lam:g}"


def predict(D, tab, ev, root, key, lams):
    """Vorhersagen für Tage ev mit Formeln aus Tagen tab, je Variante λ: gruppierte Zählungen + Log-Loss."""
    rs = D["rsize"]
    thr = np.nanquantile(rs[tab], [1 / 3, 2 / 3])
    cls = classes(rs, thr)
    B, RT, W = fit_window(D, tab, cls, lams)
    ti = np.flatnonzero(ev)
    out = {vname(l): [] for l in lams}
    ll = {vname(l): np.zeros(2) for l in lams}
    for qi in range(NQB):
        for side, (ok, d, reached) in enumerate(snapshots(D, ti, qi)):
            r, k = np.nonzero(ok)
            c = cls[ti[r]]
            wd = D["wd"][ti[r]]
            cg = np.where(c == 0, 2, c) - 1
            z0 = np.einsum("nf,nf->n", feats(d[r, k], np.full(len(r), qi / NQB)), B[cg, side])
            y = reached[r, k]
            for lam in lams:
                p = sigmoid(z0 + W[lam][side, wd])
                pc = np.clip(p, 1e-6, 1 - 1e-6)
                ll[vname(lam)] += [-(y * np.log(pc) + (~y) * np.log(1 - pc)).sum(), len(p)]
                f = (p >= 0.55) | (p <= 0.45)
                out[vname(lam)].append(pd.DataFrame({"m": root, "q": qi, "wd": wd[f], "art": np.where(p >= 0.5, "Target", "Protect")[f],
                                                     "roh": np.where(p >= 0.5, p, 1 - p)[f],
                                                     "richtig": np.where(p >= 0.5, y, ~y)[f]}))
        sn = rt_snapshots(D, ti, qi)
        if sn is not None:
            for side, (ok, d, back) in enumerate(sn):
                if np.isnan(RT[side]).any():
                    continue
                p = sigmoid(feats(np.maximum(d, 0), np.full(len(d), qi / NQB)) @ RT[side])
                f = ok & (p >= 0.55)
                for v in out:
                    out[v].append(pd.DataFrame({"m": root, "q": qi, "wd": D["wd"][ti][f], "art": "Rücklauf", "roh": p[f], "richtig": back[f]}))
    res = {}
    for v, parts in out.items():
        if not parts:
            res[v] = pd.DataFrame()
            continue
        df = pd.concat(parts, ignore_index=True)
        df["roh"] = (df["roh"] * 100).round() / 100        # 1-%-Stufen zum Zusammenfassen
        res[v] = df.groupby(["m", "art", "q", "wd", "roh"])["richtig"].agg(n="size", hits="sum").reset_index()
    return res, ll


def deltas(P):
    x = P[P["roh"] >= THR].assign(rn=lambda t: t["roh"] * t["n"])
    g = x.groupby(["m", "art", "q"])[["rn", "hits", "n"]].sum()
    return ((g["rn"] - g["hits"]) / g["n"]).clip(0, 0.25)


# Pine: ein Indikator für alle Märkte; je Markt Datenblöcke mit KPB Startzeiten (je 4 Längen x 104 Zeichen, < 4096 Zeichen)
# und eine Korrektur-Zeile (3 Arten x 10 Zeitstufen + Plan-Korrektur Protected und TP je Startzeit, 2 Zeichen, Auflösung 0,001)
KPB = 9
COEF = HERE / "results/ib_ext_coefs.json"


def write_pine(data, dfin, end_date):
    tpl = (ROOT / "gotham-zones/IB-Expansion-ALL_template.pine").read_text()
    loads = []
    for root in MARKETS:
        bodies = ["".join(data[root].get(f"{st.replace(':', '')}-{L}", "~" * NCH) for L in LENGTHS) for st in STARTS]
        assert len(range(0, len(STARTS), KPB)) == 3 and KPB * len(LENGTHS) * NCH < 4096     # Pine: Blöcke B0–B2
        for b in range(0, len(STARTS), KPB):
            loads.append(f'B{b // KPB} := barstate.isfirst and mk == "{root}" ? "{"".join(bodies[b:b + KPB])}" : B{b // KPB}')
        cor = "".join(enc2(dfin.get(f"{root}|{art}|{q}", 0.0) * 10) for art in ("Target", "Protect", "Rücklauf") for q in range(NQB))
        dplan = json.loads(COEF.read_text()).get("dplan", {}) if COEF.exists() else {}     # aus ib_ext_plan_check.py
        cor += "".join(enc2(dplan.get(f"{root}|{st}|{art}", 0.0) * 10) for art in ("Protected", "TP") for st in STARTS)
        loads.append(f'COR := barstate.isfirst and mk == "{root}" ? "{cor}" : COR')
    out = (tpl.replace("{{YEARS}}", str(YEARS)).replace("{{END}}", end_date).replace("{{KEYS}}", " ".join(STARTS))
              .replace("{{KPB}}", str(KPB)).replace("{{LOADS}}", "\n".join(loads)))
    assert "{{" not in out
    (ROOT / "gotham-zones/IB-Expansion_ALL.pine").write_text(out)
    print("Indikator:", len(out.splitlines()), "Zeilen,", len(out), "Zeichen")


def enc2(x):
    i = int(round(float(np.clip(x, -CMAX, CMAX)) * 100)) + 1922
    return ALPHA[i // 62] + ALPHA[i % 62]


def encode(B, RT, thr, W):
    s = "".join(enc2(x) for x in B.reshape(-1))
    s += "".join(enc2(x) if np.isfinite(x) else "~~" for x in RT.reshape(-1))
    s += enc2(thr[0]) + enc2(thr[1])
    s += "".join(enc2(x) for x in W.reshape(-1))
    assert len(s) == NCH
    return s


if "--pine" in sys.argv:                      # nur Pine neu bauen aus gespeicherten Zahlen
    J = json.loads(COEF.read_text())
    write_pine(J["data"], J["dfin"], J["end"])
    sys.exit()

SPLITS = ("val", "test", "fin")
preds = {sp: {vname(l): [] for l in LAMS} for sp in SPLITS}
lls = {sp: {vname(l): np.zeros(2) for l in LAMS} for sp in SPLITS}
fits = {m: {} for m in MARKETS}
for root in MARKETS:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{root.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2022-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique()))
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["open", "high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan)
        a[di[keep], mm[keep]] = df[k].to_numpy()[keep]
        G[k] = a
    fin = np.isfinite(G["close"])
    dts = pd.to_datetime(days)
    end = dts.max()
    wd_all = dts.weekday.to_numpy()
    for st in STARTS:
        for L in LENGTHS:
            s = rel(st)
            eth = s < REL930
            e = NCOL if eth else rel("16:00")
            if s + L > e - 30:
                continue
            D = window_days(G, fin, wd_all, s, L, e, eth)
            dv = dts[D["v"]]
            per = lambda y0, y1: np.asarray((dv > end - pd.DateOffset(years=y0)) & (dv <= end - pd.DateOffset(years=y1)))
            key = f"{st.replace(':', '')}-{L}"
            for split, (tab, ev) in {"val": (per(4, 2), per(2, 1)), "test": (per(4, 1), per(1, 0)), "fin": (per(3, 1), per(1, 0))}.items():
                res, ll = predict(D, tab, ev, root, key, LAMS)
                for v in res:
                    preds[split][v].append(res[v])
                    lls[split][v] += ll[v]
            final = per(YEARS, 0)
            thr = np.nanquantile(D["rsize"][final], [1 / 3, 2 / 3])
            B, RT, W = fit_window(D, final, classes(D["rsize"], thr), LAMS)
            fits[root][key] = (B, RT, thr, W)
    print(root, "fertig")

# Wochentag-Variante: Dämpfung λ mit dem kleinsten Log-Loss im Prüfjahr
LL = pd.DataFrame({sp: {v: lls[sp][v][0] / lls[sp][v][1] for v in lls[sp]} for sp in SPLITS})
best = min((l for l in LAMS if l is not None), key=lambda l: LL.loc[vname(l), "val"])
VB = vname(best)
P = {sp: {v: pd.concat(preds[sp][v], ignore_index=True) for v in preds[sp]} for sp in SPLITS}
PV, PT, PF = P["val"][VB], P["test"][VB], P["fin"][VB]
d_val, d_fin = deltas(PV), deltas(PF)
data = {m: {k: encode(B, RT, thr, W[best]) for k, (B, RT, thr, W) in fits[m].items()} for m in MARKETS}


def apply(P, dd):
    P = P.copy()
    P["sicher"] = P["roh"] - np.array([dd.get((m, a, q), 0.0) for m, a, q in zip(P["m"], P["art"], P["q"])])
    return P[P["sicher"] >= THR]


def summ(X, by):
    X = X.assign(sn=X["sicher"] * X["n"])
    g = X.groupby(by, observed=True)[["n", "sn", "hits"]].sum()
    return pd.DataFrame({"n": g["n"].astype(int), "angezeigt": (g["sn"] / g["n"]).round(3), "eingetreten": (g["hits"] / g["n"]).round(3)})


C = apply(PT, d_val.to_dict())
C0 = apply(P["test"]["ohne"], deltas(P["val"]["ohne"]).to_dict())
WDN = ["Mo", "Di", "Mi", "Do", "Fr"]
cmp = pd.concat({"ohne Wochentag": summ(C0, ["art"]), f"mit Wochentag (λ={best:g})": summ(C, ["art"])}, names=["Variante"])
bywd = pd.concat({"ohne": summ(C0.assign(Tag=C0["wd"].map(dict(enumerate(WDN)))), ["art", "Tag"]),
                  "mit": summ(C.assign(Tag=C["wd"].map(dict(enumerate(WDN)))), ["art", "Tag"])}, axis=1)
raw = PT[PT["roh"] >= THR].assign(sicher=lambda x: x["roh"])
C["band"] = pd.cut(C["sicher"], [0.69, 0.8, 0.9, 1.01], labels=["70–80 %", "80–90 %", "90–100 %"])
md = ["# IB-Expansion als Formel – Kalibrierung (≥ 70 % nach Korrektur)", "",
      "Test: letztes Jahr (in keinem Schritt benutzt). Formeln aus den 3 Jahren davor, Korrektur aus dem Prüfjahr davor.", "",
      f"Im Indikator: mit Wochentag, Dämpfung λ = {best:g} (gewählt im Prüfjahr). Alles unten ist diese Variante,",
      "außer im Vergleich.", "",
      "## Wochentag: Log-Loss je Variante (kleiner = besser; val = Prüfjahr, test = ungesehenes letztes Jahr)", "",
      LL.round(5).to_markdown(), "",
      "## Wochentag: Vergleich im Testjahr (≥ 70 % nach Korrektur)", "", cmp.to_markdown(), "",
      "## Wochentag: je Tag im Testjahr (ohne / mit)", "", bywd.to_markdown(), "",
      "## Nach Art und Zeitstufe (mit Korrektur)", "", summ(C, ["art", "q"]).to_markdown(), "",
      "## Ohne Korrektur", "", summ(raw, ["art", "q"]).to_markdown(), "",
      "## Nach Markt", "", summ(C, ["m", "art"]).to_markdown(), "",
      "## Nach angezeigter Sicherheit", "", summ(C, ["art", "band"]).to_markdown(), "",
      "## Korrektur im Indikator (δ)", "", d_fin.unstack("q").round(3).to_markdown(), ""]
(HERE / "results/ib_ext_model.md").write_text("\n".join(md))
print("\n".join(md))

old = json.loads(COEF.read_text()) if COEF.exists() else {}
COEF.write_text(json.dumps({"data": data, "dfin": {f"{m}|{a}|{q}": float(v) for (m, a, q), v in d_fin.items()},
                            "end": str(end.date()), "lam": best, "dplan": old.get("dplan", {})}))
print("Hinweis: Plan-Korrektur danach neu schätzen: python data-lab/ib_ext_plan_check.py && python data-lab/ib_ext_model.py --pine")
write_pine(data, json.loads(COEF.read_text())["dfin"], str(end.date()))
