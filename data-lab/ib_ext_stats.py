"""
IB-Expansion: Wahrscheinlichkeit, dass Levels ±0,0 … ±3,0 IB-Range bis Tagesende erreicht werden.
Grundlage für die Pine-Indikatoren gotham-zones/IB-Expansion_<Markt>.pine (Targets / Protects ab 70 %).

Level k = 0 … 30 je Seite: oben IB-Hoch + k·0,1·R (k = 0: IB-Hoch gebrochen, also Docht > IB-Hoch),
unten IB-Tief − k·0,1·R. "Erreicht" = Docht berührt das Level bis Tagesende.
Tagesende 17:00 für IBs vor 09:30, sonst 16:00.

IB-Größe: R / Median der IB-Range derselben Uhrzeit an den 20 Tagen davor
  → Klasse 1 klein / 2 normal / 3 groß (Drittel im Statistik-Zeitraum), 0 = unbekannt (zu wenig Vortage).

Tabellen je Fenster (Start, Länge):
  T1  bei IB-Ende: P(k erreicht) je Größe (0 = alle, 1–3) x zuerst gebildet (0 = egal, 1 = Hoch, 2 = Tief)
  G   danach: P(Level wird noch erreicht | Größe 1–3, Abstand d vom aktuellen Close, vergangene Zeit q)
      q = 0, 10 %, … 90 % der Restzeit; d in 0,1-Schritten bis 2,0, dann 0,25-Schritte bis 3,0, dann > 3,0
  RT  Rücklauf (nur IBs, die bis 09:30 fertig sind): Kurs eröffnet 09:30 über dem IB-Hoch (unter dem IB-Tief) –
      P(IB-Rand wird bis Tagesende noch berührt | Abstand d zum Rand, Zeit q ab 09:30, noch kein Rücklauf)
Live (wie im Indikator): bis zum ersten erreichten Level Übergang T1 → G in den ersten 10 % der Restzeit,
danach G; Zeit linear interpoliert (nach 100 % = 0).
Korrektur: Die Tabellen sind auf neuen Daten zu optimistisch. Je Markt und Zeitstufe wird gemessen, um wie viel
(Prüfjahr direkt nach den Tabellen-Jahren), und davon abgezogen: δ_T (Targets), δ_P (Protects), δ_R (Rücklauf).

1. Test (ehrlich, letztes Jahr nie benutzt): δ aus Tabellen (4–2 Jahre zurück) → Prüfjahr (2–1 Jahre zurück);
   Tabellen aus den 3 Jahren vor dem letzten Jahr; Vorhersage mit Korrektur auf dem letzten Jahr.
   Ausgewertet wird nur, was der Indikator zeigt (Targets / Protects / Rücklauf ≥ 70 % nach Korrektur).
2. Endgültig: Tabellen aus den letzten 3 Jahren, δ aus Tabellen (3–1 Jahre zurück) → letztes Jahr
   → gotham-zones/IB-Expansion_<Markt>.pine (aus IB-Expansion_template.pine)

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
YEARS = 3
K = 31                      # Level 0 … 30  (0,0 … 3,0 IB)
NQB = 10                    # Zeitstufen q = 0, 0,1 … 0,9
ND = 25                     # Abstandsstufen G
NR = 15                     # Abstandsstufen RT
MIN_T1, MIN_C = 30, 20
THR = 0.70
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"  # 62 Zeichen → 0 … 61
NA = "~"
LEN_T1, LEN_G, LEN_RT = 4 * 3 * 2 * K, 3 * 2 * NQB * ND, 2 * NQB * NR


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


REL930 = rel("09:30")


def dbin(d):
    """Abstandsstufe für G: 0,1-Schritte bis 2,0, 0,25-Schritte bis 3,0, dann > 3,0."""
    d = np.maximum(np.asarray(d, float), 0)
    return np.where(d < 2.0, np.floor(d / 0.1), np.where(d < 3.0, 20 + np.floor((d - 2.0) / 0.25), 24)).astype(int)


def rbin(d):
    """Abstandsstufe für RT: 0,1-Schritte bis 1,0, 0,25-Schritte bis 2,0, dann > 2,0."""
    d = np.maximum(np.asarray(d, float), 0)
    return np.where(d < 1.0, np.floor(d / 0.1), np.where(d < 2.0, 10 + np.floor((d - 1.0) / 0.25), 14)).astype(int)


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def window_days(G, fin, wd, s, L, e, eth):
    """Alle Größen eines Fensters für die gültigen Tage."""
    W = slice(s, s + L)
    cov = fin[:, W].sum(1) / L
    with np.errstate(all="ignore"):
        H = np.nanmax(G["high"][:, W], 1)
        Lo = np.nanmin(G["low"][:, W], 1)
    R = H - Lo
    v = (cov >= (0.5 if eth else 0.8)) & fin[:, e - 30:e].any(1) & np.isfinite(R) & (R > 0) & (wd < 5)
    # IB-Größe relativ zum Median der 20 Tage davor (nur gültige Tage)
    rmed = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
    rsize = (R / rmed)[v]
    tH = np.nanargmax(G["high"][v][:, W], 1)
    tL = np.nanargmin(G["low"][v][:, W], 1)
    ff = np.where(tH < tL, 1, np.where(tL < tH, 2, 0))
    cff = pd.DataFrame(G["close"][v][:, :e]).ffill(axis=1).to_numpy()
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
    i930 = REL930 - (s + L) if s + L <= REL930 else -1
    o930 = None
    if i930 >= 0:
        o930 = G["open"][v][:, REL930]
        o930 = np.where(np.isfinite(o930), o930, cff[:, REL930 - 1])
    return dict(v=v, ff=ff, tu=tu, td=td, npost=e - s - L, H=H, Lo=Lo, R=R, Cp=Cp, Hp=Hp, Lp=Lp,
                rsize=rsize, i930=i930, o930=o930)


def classes(rsize, thr):
    c = np.where(rsize <= thr[0], 1, np.where(rsize >= thr[1], 3, 2))
    return np.where(np.isfinite(rsize), c, 0)


def build_t1(D, m, cls):
    T1 = np.full((4, 3, 2, K), np.nan)
    tu, td, ff = D["tu"][m], D["td"][m], D["ff"][m]
    c = cls[m]
    for ci in range(4):
        for f in range(3):
            sel = (c == ci if ci else np.ones_like(c, bool)) & (ff == f if f else np.ones_like(ff, bool))
            if sel.sum() >= MIN_T1:
                T1[ci, f, 0] = np.isfinite(tu[sel]).mean(0)
                T1[ci, f, 1] = np.isfinite(td[sel]).mean(0)
    return T1


def snapshots(D, idx, qi):
    """Zeitstufe qi: je Tag (idx), Seite, Level → (noch offen?, Abstand d, später erreicht?)."""
    t = int(qi * D["npost"] / NQB)
    H, Lo, R = D["H"][idx], D["Lo"][idx], D["R"][idx]
    c = D["Cp"][idx, t]
    ks = np.arange(K)[None, :]
    out = []
    for tt, lv, sgn in [(D["tu"][idx], H[:, None] + 0.1 * ks * R[:, None], 1),
                        (D["td"][idx], Lo[:, None] - 0.1 * ks * R[:, None], -1)]:
        open_ = ~(tt + 1 <= t)
        d = sgn * (lv - c[:, None]) / R[:, None]
        out.append((open_ & (d >= 0), d, np.isfinite(tt)))
    return out


def build_g(D, m, cls):
    hit = np.zeros((3, 2, NQB, ND)); cnt = np.zeros((3, 2, NQB, ND))
    for ci in (1, 2, 3):
        idx = np.flatnonzero(m & (cls == ci))
        if not len(idx):
            continue
        for qi in range(NQB):
            for side, (ok, d, reached) in enumerate(snapshots(D, idx, qi)):
                b = dbin(d)
                np.add.at(cnt[ci - 1, side, qi], b[ok], 1)
                np.add.at(hit[ci - 1, side, qi], b[ok], reached[ok])
    with np.errstate(invalid="ignore"):
        return np.where(cnt >= MIN_C, hit / cnt, np.nan)


def rt_snapshots(D, idx, qi):
    """Rücklauf: je Tag (idx) mit 9:30-Open außerhalb der IB → (gültig?, Abstand, später berührt?) je Seite.
    Zeitstufe qi zählt ab 09:30 (qi = 0: Eröffnung)."""
    i0 = D["i930"]
    if i0 < 0:
        return None
    t = i0 + int(qi * (D["npost"] - i0) / NQB)
    H, Lo, R, o = D["H"][idx], D["Lo"][idx], D["R"][idx], D["o930"][idx]
    Lp, Hp, c = D["Lp"][idx], D["Hp"][idx], D["Cp"][idx, t]
    with np.errstate(all="ignore"):
        lo_before = np.nanmin(Lp[:, i0:t], 1) if t > i0 else np.full(len(idx), np.inf)
        hi_before = np.nanmax(Hp[:, i0:t], 1) if t > i0 else np.full(len(idx), -np.inf)
        lo_after = np.nanmin(Lp[:, t:], 1)
        hi_after = np.nanmax(Hp[:, t:], 1)
    up_ok = (o > H) & ~(lo_before <= H)
    dn_ok = (o < Lo) & ~(hi_before >= Lo)
    return [(up_ok, (c - H) / R, lo_after <= H), (dn_ok, (Lo - c) / R, hi_after >= Lo)]


def build_rt(D, m):
    RT = np.full((2, NQB, NR), np.nan)
    idx = np.flatnonzero(m)
    if D["i930"] < 0 or not len(idx):
        return RT
    hit = np.zeros((2, NQB, NR)); cnt = np.zeros((2, NQB, NR))
    for qi in range(NQB):
        sn = rt_snapshots(D, idx, qi)
        if sn is None:
            continue
        for side, (ok, d, back) in enumerate(sn):
            b = rbin(d)
            np.add.at(cnt[side, qi], b[ok], 1)
            np.add.at(hit[side, qi], b[ok], back[ok])
    with np.errstate(invalid="ignore"):
        return np.where(cnt >= MIN_C, hit / cnt, np.nan)


def t1_lookup(T1, c, f, side, k):
    for cc, ff in [(c, f), (c, 0), (0, f), (0, 0)]:
        x = T1[cc, ff, side, k]
        if np.isfinite(x):
            return x
    return np.nan


def enc(x):
    return NA if not np.isfinite(x) else ALPHA[int(round(min(max(x, 0), 1) * 61))]


def dec(x):
    """Wert nach Kodierung (wie der Indikator ihn sieht)."""
    return np.round(np.clip(x, 0, 1) * 61) / 61


def encode(T1, Gt, RT):
    out = "".join(enc(x) for x in T1.reshape(-1)) + "".join(enc(x) for x in Gt.reshape(-1)) + "".join(enc(x) for x in RT.reshape(-1))
    assert len(out) == LEN_T1 + LEN_G + LEN_RT
    return out


def predict(D, tab, ev, root, key):
    """Tabellen aus Tagen 'tab', Vorhersagen (roh, vor Korrektur) für Tage 'ev' an allen Zeitstufen."""
    rs = D["rsize"]
    thr = np.nanquantile(rs[tab], [1 / 3, 2 / 3])
    cls = classes(rs, thr)
    T1, Gt, RT = build_t1(D, tab, cls), build_g(D, tab, cls), build_rt(D, tab)
    ti = np.flatnonzero(ev)
    out = []
    if not len(ti):
        return pd.DataFrame()
    for qi in range(NQB):
        for side, (ok, d, reached) in enumerate(snapshots(D, ti, qi)):
            r, k = np.nonzero(ok)
            c = cls[ti[r]]
            cg = np.where(c == 0, 2, c) - 1
            pg = dec(Gt[cg, side, qi, dbin(d[r, k])])
            if qi == 0:
                p1 = np.array([t1_lookup(T1, a, b, side, kk) for a, b, kk in zip(c, D["ff"][ti[r]], k)])
                p = dec(np.where(np.isfinite(p1), p1, pg))
            else:
                p = pg
            f = np.isfinite(p) & ((p >= 0.55) | (p <= 0.45))
            hold = 1 - p
            art = np.where(p >= 0.5, "Target", "Protect")
            sicher = np.where(p >= 0.5, p, hold)
            ok_ = reached[r, k]
            out.append(pd.DataFrame({"m": root, "w": key, "q": qi, "art": art[f], "roh": sicher[f],
                                     "richtig": np.where(p >= 0.5, ok_, ~ok_)[f], "groesse": c[f]}))
        sn = rt_snapshots(D, ti, qi)
        if sn is not None:
            for side, (ok, d, back) in enumerate(sn):
                p = dec(RT[side, qi, rbin(d)])
                f = ok & np.isfinite(p) & (p >= 0.55)
                out.append(pd.DataFrame({"m": root, "w": key, "q": qi, "art": "Rücklauf", "roh": p[f],
                                         "richtig": back[f], "groesse": cls[ti][f]}))
    if not out:
        return pd.DataFrame()
    df = pd.concat(out, ignore_index=True)
    # Werte sind kodiert (61 Stufen) → exakt zusammenfassbar
    return df.groupby(["m", "art", "q", "roh", "groesse"])["richtig"].agg(n="size", hits="sum").reset_index()


def deltas(P):
    """Überschätzung je Markt, Art, Zeitstufe: Mittel(angezeigt − eingetreten) über alles, was ≥ 70 % gezeigt würde."""
    x = P[P["roh"] >= THR].assign(rn=lambda t: t["roh"] * t["n"])
    g = x.groupby(["m", "art", "q"])[["rn", "hits", "n"]].sum()
    return ((g["rn"] - g["hits"]) / g["n"]).clip(0, 0.25)


def apply(P, D_):
    P = P.copy()
    P["delta"] = [D_.get((m, a, q), 0.0) for m, a, q in zip(P["m"], P["art"], P["q"])]
    P["sicher"] = P["roh"] - P["delta"]
    return P[P["sicher"] >= THR]


preds = {"val": [], "test": [], "fin": []}
calib, data, overview = [], {m: {} for m in MARKETS}, []
for root in MARKETS:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{root.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2022-06-01")]
    m_ = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = m_ < NCOL
    days = np.array(sorted(df["session_date"].unique()))
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["open", "high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan)
        a[di[keep], m_[keep]] = df[k].to_numpy()[keep]
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
            final = np.asarray(dv > end - pd.DateOffset(years=YEARS))
            key = f"{st.replace(':', '')}-{L}"
            rs = D["rsize"]

            per = lambda y0, y1: np.asarray((dv > end - pd.DateOffset(years=y0)) & (dv <= end - pd.DateOffset(years=y1)))
            for split, (tab, ev) in {"val": (per(4, 2), per(2, 1)), "test": (per(4, 1), per(1, 0)), "fin": (per(3, 1), per(1, 0))}.items():
                preds[split].append(predict(D, tab, ev, root, key))

            # endgültige Tabellen (letzte YEARS Jahre)
            fthr = np.nanquantile(rs[final], [1 / 3, 2 / 3])
            fcls = classes(rs, fthr)
            fT1, fG, fRT = build_t1(D, final, fcls), build_g(D, final, fcls), build_rt(D, final)
            data[root][key] = (encode(fT1, fG, fRT), int(final.sum()), fthr)
            if st in ("08:30", "09:30"):
                for ci, lab in [(0, "alle"), (1, "klein"), (3, "groß")]:
                    row = dict(Markt=root, IB=f"{st} · {L}m", Größe=lab)
                    for k in (5, 10, 15, 20, 25, 30):
                        row[f"±{k / 10:g}"] = round(50 * (fT1[ci, 0, 0, k] + fT1[ci, 0, 1, k]))
                    overview.append(row)
    print(root, "fertig")

PV, PT, PF = (pd.concat(preds[k], ignore_index=True) for k in ("val", "test", "fin"))
d_val = deltas(PV)
d_fin = deltas(PF)
raw = PT[PT["roh"] >= THR].assign(sicher=lambda x: x["roh"])
C = apply(PT, d_val.to_dict())


def summ(X, by):
    X = X.assign(sn=X["sicher"] * X["n"])
    g = X.groupby(by, observed=True)[["n", "sn", "hits"]].sum()
    return pd.DataFrame({"n": g["n"].astype(int), "angezeigt": (g["sn"] / g["n"]).round(3),
                         "eingetreten": (g["hits"] / g["n"]).round(3)})


cal_art = summ(C, ["art", "q"])
cal_raw = summ(raw, ["art", "q"])
cal_m = summ(C, ["m", "art"])
C["Größe"] = C["groesse"].map({0: "unbekannt", 1: "klein", 2: "normal", 3: "groß"})
cal_g = summ(C, ["art", "Größe"])
C["band"] = pd.cut(C["sicher"], [0.69, 0.8, 0.9, 1.01], labels=["70–80 %", "80–90 %", "90–100 %"])
cal_b = summ(C, ["art", "band"])
O = pd.DataFrame(overview)

md = ["# IB-Expansion – Kalibrierung (nur was der Indikator zeigt: ≥ 70 % nach Korrektur)", "",
      f"Test: letztes Jahr (in keinem Schritt benutzt). Tabellen aus den {YEARS} Jahren davor, Korrektur aus dem Prüfjahr davor.",
      "q = Zeitstufe (0 = IB-Ende bzw. 9:30 beim Rücklauf, 9 = 90 % der Restzeit).",
      "'angezeigt' = Sicherheit im Indikator (Target: erreicht, Protect: hält, Rücklauf: berührt), 'eingetreten' = tatsächlich.", "",
      "## Nach Art und Zeitstufe (mit Korrektur)", "", cal_art.to_markdown(), "",
      "## Zum Vergleich: ohne Korrektur", "", cal_raw.to_markdown(), "",
      "## Korrektur im Indikator (δ je Markt, Art, Zeitstufe)", "", d_fin.unstack("q").round(3).to_markdown(), "",
      "## Nach Markt", "", cal_m.to_markdown(), "",
      "## Nach IB-Größe", "", cal_g.to_markdown(), "", "## Nach angezeigter Sicherheit", "", cal_b.to_markdown(), "",
      f"## Erreichen bis Tagesende bei IB-Ende, 08:30 und 09:30 (letzte {YEARS} Jahre, Mittel oben/unten, in %)", "",
      O.to_markdown(index=False), ""]
(HERE / "results/ib_ext_stats.md").write_text("\n".join(md))
print("\n".join(md))

# 3) Eigenständige Indikatoren je Markt
tpl = (ROOT / "gotham-zones/IB-Expansion_template.pine").read_text()
for root in MARKETS:
    # je Fenster eine Anweisung: Startzeit wählt, Länge bestimmt den Platz (15/30/45/60 → 0–3)
    loads = [f'if barstate.isfirst and skey == "{w.split("-")[0]}"\n'
             f'    array.set(DATAS, {LENGTHS.index(int(w.split("-")[1]))}, "{n}|{t[0]:.3f}|{t[1]:.3f}|{d}")'
             for w, (d, n, t) in data[root].items()]
    dl = lambda art: ", ".join(f"{d_fin.get((root, art, q), 0.0):.3f}" for q in range(NQB))
    out = (tpl.replace("{{MARKET}}", root).replace("{{YEARS}}", str(YEARS)).replace("{{END}}", str(end.date()))
              .replace("{{DT}}", dl("Target")).replace("{{DP}}", dl("Protect")).replace("{{DR}}", dl("Rücklauf"))
              .replace("{{LOADS}}", "\n".join(loads)))
    (ROOT / f"gotham-zones/IB-Expansion_{root}.pine").write_text(out)
    print(root, len(out.splitlines()), "Zeilen,", len(out), "Zeichen")
