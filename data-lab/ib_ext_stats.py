"""
IB-Expansion: Wahrscheinlichkeit, dass Levels ±0,0 … ±1,5 IB-Range bis Tagesende erreicht werden.
Grundlage für den Pine-Indikator "IB Expansion" (TP-Level / geschützte Level).

Level k = 0 … 15 je Seite: oben IB-Hoch + k·0,1·R (k = 0: IB-Hoch gebrochen, also Docht > IB-Hoch),
unten IB-Tief − k·0,1·R. "Erreicht" = Docht berührt das Level bis Tagesende.
Tagesende 17:00 für IBs vor 09:30, sonst 16:00.

Tabellen je Fenster (Start, Länge):
  T1  bei IB-Ende: P(k erreicht) je Wochentag (0 = alle, 1–5 = Mo–Fr) x zuerst gebildet (0 = egal, 1 = Hoch, 2 = Tief)
  G   danach: P(Level wird noch erreicht | Abstand d vom aktuellen Close in IB-Ranges, vergangene Zeit q)
      q = 0, 10 %, … 90 % der Restzeit, d in 0,1-Schritten bis 3,0 (letzte Stufe: > 3,0), je Seite.
      Gemessen an jedem noch nicht erreichten Level zu genau diesen Zeitpunkten.
Live (wie im Indikator): bis zum ersten erreichten Level T1, danach G mit linearer Interpolation in d und q
(nach 100 % der Restzeit = 0).

1. Kalibrierung: Tabellen aus den 3 Jahren vor dem letzten Jahr, Test auf dem letzten Jahr (ungesehen).
2. Endgültige Tabellen aus den letzten 3 Jahren → Pine-Libraries gotham-zones/IBX_<Markt>_library.pine
   + Indikator gotham-zones/IB-Expansion_indicator.pine (importiert die Libraries)
   + eigenständige Indikatoren gotham-zones/IB-Expansion_<Markt>.pine (Daten im Skript)

Aufruf: python data-lab/ib_ext_stats.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
ROOT = HERE.parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENGTHS = [15, 30, 45, 60]
NCOL = 1380
K = 16                      # Level 0 … 15  (0,0 … 1,5 IB)
NQ_ = 10                    # Zeitstufen q = 0, 0,1 … 0,9
ND = 31                     # Abstandsstufen d = 0,0–0,1 … 2,9–3,0, > 3,0
MIN_T1, MIN_C = 30, 20
YEARS = 3                   # Statistik-Zeitraum (Jahre bis zum letzten Datentag)
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"  # 62 Zeichen → 0 … 61
NA = "~"


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def window_days(G, fin, wd, s, L, e, eth):
    """Gültige Tage eines Fensters und Treffer-Zeitpunkte tu/td (Index in der Restzeit, inf = nie)."""
    W = slice(s, s + L)
    cov = fin[:, W].sum(1) / L
    with np.errstate(all="ignore"):
        H = np.nanmax(G["high"][:, W], 1)
        Lo = np.nanmin(G["low"][:, W], 1)
    R = H - Lo
    v = (cov >= (0.5 if eth else 0.8)) & fin[:, e - 30:e].any(1) & np.isfinite(R) & (R > 0) & (wd < 5)
    cff = pd.DataFrame(G["close"][v][:, :e]).ffill(axis=1).to_numpy()
    tH = np.nanargmax(G["high"][v][:, W], 1)
    tL = np.nanargmin(G["low"][v][:, W], 1)
    ff = np.where(tH < tL, 1, np.where(tL < tH, 2, 0))
    H, Lo, R = H[v], Lo[v], R[v]
    Hp, Lp = G["high"][v][:, s + L:e], G["low"][v][:, s + L:e]
    tu = np.empty((v.sum(), K))
    td = np.empty((v.sum(), K))
    with np.errstate(invalid="ignore"):
        tu[:, 0] = first_true(Hp > H[:, None])
        td[:, 0] = first_true(Lp < Lo[:, None])
        for k in range(1, K):
            tu[:, k] = first_true(Hp >= (H + 0.1 * k * R)[:, None])
            td[:, k] = first_true(Lp <= (Lo - 0.1 * k * R)[:, None])
    Cp = cff[:, s + L - 1:e]  # Index 0 = Close am IB-Ende, i = Close nach i Bars Restzeit
    return v, ff, tu, td, e - s - L, H, Lo, R, Cp


def build_t1(tu, td, wd, ff):
    T1 = np.full((6, 3, 2, K), np.nan)
    for w in range(6):
        for f in range(3):
            m = (wd == w if w else np.ones_like(wd, bool)) & (ff == f if f else np.ones_like(ff, bool))
            if m.sum() >= MIN_T1:
                T1[w, f, 0] = np.isfinite(tu[m]).mean(0)
                T1[w, f, 1] = np.isfinite(td[m]).mean(0)
    return T1


def snapshots(tu, td, H, Lo, R, Cp, npost, qi):
    """Für Zeitstufe qi: je Tag, Seite, Level → (noch offen?, Abstand d, später erreicht?)."""
    t = int(qi * npost / NQ_)
    c = Cp[:, t]
    lv_up = H[:, None] + 0.1 * np.arange(K)[None, :] * R[:, None]
    lv_dn = Lo[:, None] - 0.1 * np.arange(K)[None, :] * R[:, None]
    out = []
    for side, (tt, lv, sgn) in enumerate([(tu, lv_up, 1), (td, lv_dn, -1)]):
        open_ = ~(tt + 1 <= t)                       # bis jetzt nicht erreicht
        d = sgn * (lv - c[:, None]) / R[:, None]
        out.append((open_ & (d >= 0), d, np.isfinite(tt)))
    return out


def build_g(tu, td, H, Lo, R, Cp, npost):
    hit = np.zeros((2, NQ_, ND)); cnt = np.zeros((2, NQ_, ND))
    for qi in range(NQ_):
        for side, (ok, d, reached) in enumerate(snapshots(tu, td, H, Lo, R, Cp, npost, qi)):
            db = np.minimum((d / 0.1).astype(int), ND - 1)
            np.add.at(cnt[side, qi], db[ok], 1)
            np.add.at(hit[side, qi], db[ok], reached[ok])
    with np.errstate(invalid="ignore"):
        Gt = np.where(cnt >= MIN_C, hit / cnt, np.nan)
    return Gt


def g_lookup(Gt, side, qi, d):
    """Lineare Interpolation über Abstands-Mitten (wie im Indikator)."""
    x = d / 0.1 - 0.5
    j0 = int(np.clip(np.floor(x), 0, ND - 1)); j1 = min(j0 + 1, ND - 1)
    fr = float(np.clip(x - j0, 0, 1))
    a, b = Gt[side, qi, j0], Gt[side, qi, j1]
    if not np.isfinite(a):
        return b
    if not np.isfinite(b):
        return a
    return a + (b - a) * fr


def g_vec(Gt, side, qi, d):
    x = d / 0.1 - 0.5
    j0 = np.clip(np.floor(x), 0, ND - 1).astype(int)
    j1 = np.minimum(j0 + 1, ND - 1)
    fr = np.clip(x - j0, 0, 1)
    a, b = Gt[side, qi, j0], Gt[side, qi, j1]
    out = a + (b - a) * fr
    out = np.where(np.isfinite(a), np.where(np.isfinite(b), out, a), b)
    return out


def t1_lookup(T1, w, f, side, k):
    for ww, fff in [(w, f), (0, f), (w, 0), (0, 0)]:
        x = T1[ww, fff, side, k]
        if np.isfinite(x):
            return x
    return np.nan


def enc(x):
    return NA if not np.isfinite(x) else ALPHA[int(round(min(max(x, 0), 1) * 61))]


def encode(T1, Gt):
    out = "".join(enc(x) for x in T1.reshape(-1)) + "".join(enc(x) for x in Gt.reshape(-1))
    assert len(out) == 576 + 2 * NQ_ * ND
    return out


calib, data, ext830 = [], {m: {} for m in MARKETS}, []
for root in MARKETS:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{root.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2019-09-01")]
    m = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = m < NCOL
    days = np.array(sorted(df["session_date"].unique()))
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan)
        a[di[keep], m[keep]] = df[k].to_numpy()[keep]
        G[k] = a
    fin = np.isfinite(G["close"])
    dts = pd.to_datetime(days)
    end = dts.max()
    wd_all = dts.weekday.to_numpy()

    for st in STARTS:
        for L in LENGTHS:
            s = rel(st)
            eth = s < rel("09:30")
            e = NCOL if eth else rel("16:00")
            if s + L > e - 30:
                continue
            v, ff, tu, td, npost, H, Lo, R, Cp = window_days(G, fin, wd_all, s, L, e, eth)
            dv = dts[v]
            wd = wd_all[v] + 1
            final = np.asarray(dv > end - pd.DateOffset(years=YEARS))
            test = np.asarray(dv > end - pd.DateOffset(years=1))
            train = np.asarray(dv > end - pd.DateOffset(years=YEARS + 1)) & ~test
            key = f"{st.replace(':', '')}-{L}"

            # 1) Kalibrierung: Tabellen aus train, Vorhersage auf test (q = 0 mit T1 und mit G, danach G)
            T1 = build_t1(tu[train], td[train], wd[train], ff[train])
            Gt = build_g(tu[train], td[train], H[train], Lo[train], R[train], Cp[train], npost)
            ti = np.flatnonzero(test)
            for qi in [0, 2, 5, 7]:
                snaps = snapshots(tu[ti], td[ti], H[ti], Lo[ti], R[ti], Cp[ti], npost, qi)
                for side, (ok, d, reached) in enumerate(snaps):
                    r, k = np.nonzero(ok)
                    pg = g_vec(Gt, side, qi, d[r, k])
                    hit = reached[r, k]
                    f = np.isfinite(pg)
                    calib.append(pd.DataFrame({"m": root, "w": key, "q": qi / 10, "quelle": "G", "p": pg[f], "hit": hit[f]}))
                    if qi == 0:
                        i = ti[r]
                        p1 = np.array([t1_lookup(T1, a, b, side, c) for a, b, c in zip(wd[i], ff[i], k)])
                        f = np.isfinite(p1)
                        calib.append(pd.DataFrame({"m": root, "w": key, "q": 0.0, "quelle": "T1", "p": p1[f], "hit": hit[f]}))

            # 2) endgültige Tabellen (letzte YEARS Jahre)
            fT1 = build_t1(tu[final], td[final], wd[final], ff[final])
            fG = build_g(tu[final], td[final], H[final], Lo[final], R[final], Cp[final], npost)
            data[root][key] = (encode(fT1, fG), int(final.sum()))
            if st in ("08:30", "09:30"):
                ext830.append(dict(m=root, w=key, n=int(final.sum()),
                                   **{f"+{k / 10:.1f}": round(100 * fT1[0, 0, 0, k]) for k in (0, 3, 5, 10, 15)},
                                   **{f"-{k / 10:.1f}": round(100 * fT1[0, 0, 1, k]) for k in (0, 3, 5, 10, 15)}))
    print(root, "fertig")

C = pd.concat(calib, ignore_index=True)
C.to_parquet(HERE / "results/ib_ext_calibration.parquet", index=False)
C["Gruppe"] = pd.cut(C["p"], [-0.01, 0.3, 0.7, 1.01], labels=["geschützt (≤30 %)", "neutral", "TP (≥70 %)"])
cal = C[C.quelle == "G"].groupby(["m", "Gruppe"], observed=True).agg(n=("hit", "size"), vorhergesagt=("p", "mean"), erreicht=("hit", "mean")).round(3)
cal_q = C.groupby(["quelle", "q", "Gruppe"], observed=True).agg(n=("hit", "size"), vorhergesagt=("p", "mean"), erreicht=("hit", "mean")).round(3)
C["dez"] = (C["p"] * 10).clip(0, 9.999).astype(int)
cal_dec = C[C.quelle == "G"].groupby("dez").agg(n=("hit", "size"), vorhergesagt=("p", "mean"), erreicht=("hit", "mean")).round(3)
E = pd.DataFrame(ext830)

md = ["# IB-Expansion – Kalibrierung und Kennzahlen", "",
      f"Test: letztes Jahr (ungesehen), Tabellen aus den {YEARS} Jahren davor. Vorhersage zu IB-Ende (q = 0) und nach 20/50/70 % der Restzeit,",
      "für jedes noch nicht erreichte Level ±0,0 … ±1,5 IB. 'erreicht' = tatsächlicher Anteil.", "",
      "## Je Markt", "", cal.to_markdown(), "", "## Je Zeitpunkt (alle Märkte)", "", cal_q.to_markdown(), "",
      "## Kalibrierung in 10-%-Schritten (alle Märkte)", "", cal_dec.to_markdown(), "",
      f"## Erreichen bis Tagesende bei IB-Ende, 08:30 und 09:30 (letzte {YEARS} Jahre, alle Tage, in %)", "", E.to_markdown(index=False), ""]
(HERE / "results/ib_ext_stats.md").write_text("\n".join(md))
print("\n".join(md))

# 3) Pine: eine Daten-Library je Markt + Indikator, der sie importiert
for root in MARKETS:
    funcs = [f'// @function IB {w[:2]}:{w[2:4]} · {w.split("-")[1]} Min ({n} Tage)\n'
             f'// @returns Anzahl Tage und kodierte Tabellen\n'
             f'export w{w.replace("-", "_")}() => "{n}|{d}"' for w, (d, n) in data[root].items()]
    lib = (f'//@version=6\n// @description IB-Expansion-Statistik {root} (Databento CME 1m, letzte {YEARS} Jahre bis {end.date()}), '
           f'erzeugt von data-lab/ib_ext_stats.py. Nur Daten, keine Logik.\nlibrary("IBX_{root}")\n\n' + "\n\n".join(funcs) + "\n")
    (ROOT / f"gotham-zones/IBX_{root}_library.pine").write_text(lib)
    print(root, "Library", len(lib), "Zeichen,", len(funcs), "Fenster")
tpl = (ROOT / "gotham-zones/IB-Expansion_template.pine").read_text()
loads = []
for root in MARKETS:
    for w in data[root]:
        loads.append(f'if barstate.isfirst and mk == "{root}" and wkey == "{w}"\n    DATA := d{root}.w{w.replace("-", "_")}()')
(ROOT / "gotham-zones/IB-Expansion_indicator.pine").write_text(tpl.replace("{{LOADS}}", "\n".join(loads)))
print("Indikator", len(tpl.replace("{{LOADS}}", "\n".join(loads))), "Zeichen")

# 4) Eigenständige Indikatoren je Markt (Daten direkt im Skript, nichts zu veröffentlichen)
LIB_NOTE = """//  DATEN kommen aus vier Libraries (IBX_NQ, IBX_ES, IBX_RTY, IBX_GC), die du einmal selbst
//  veröffentlichen musst (privat reicht). Steht dein TradingView-Name anders als unten,
//  die vier import-Zeilen anpassen. Statistik: Databento CME 1m, letzte 3 Jahre."""
IMPORTS = "\n".join(f"import Brucefcknwayne/IBX_{m}/1 as d{m}" for m in MARKETS) + "\n"
for root in MARKETS:
    one = tpl.replace(LIB_NOTE, f"//  Eigenständige Version nur für {root} (Daten im Skript, nichts zu veröffentlichen).\n"
                                f"//  Statistik: Databento CME 1m, letzte {YEARS} Jahre bis {end.date()}.")
    one = one.replace(IMPORTS, "")
    one = one.replace('indicator("IB Expansion · TP & geschützte Level", shorttitle = "IB-Exp"',
                      f'indicator("IB Expansion {root} · TP & geschützte Level", shorttitle = "IB-Exp {root}"')
    assert "import " not in one and "Libraries" not in one
    loads = [f'if barstate.isfirst and mk == "{root}" and wkey == "{w}"\n    DATA := "{n}|{d}"' for w, (d, n) in data[root].items()]
    (ROOT / f"gotham-zones/IB-Expansion_{root}.pine").write_text(one.replace("{{LOADS}}", "\n".join(loads)))
    print(root, "eigenständig", len(one.replace("{{LOADS}}", "\n".join(loads)).splitlines()), "Zeilen")
