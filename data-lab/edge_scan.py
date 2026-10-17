"""
Edge-Scan NQ 1m: viele Hypothesen, Richtung wird nur auf Train (2010-2020) bestimmt,
Test (2021-2026) ist reines Out-of-Sample.

Familien: Uhrzeit, Kalender, Intraday-Momentum, Gap, Overnight-Range, Vortag,
Vola-Regime (VIX-Termstruktur), Volumen, VWAP, Levels (PDH/PDL/ONH/ONL/Runde Zahlen).

Kosten: 1 Punkt pro Round-Trip (Slippage + Gebühren).
Bestanden: |t Train| >= 2.5, Test gleiche Richtung mit t >= 2.0 und netto > 0.

Aufruf: python data-lab/edge_scan.py
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "results/edge_scan.md"
COST_PTS = 1.0
SPLIT = pd.Timestamp("2021-01-01")
T_TRAIN, T_TEST = 2.5, 2.0

# ═════════════════════════════ Daten ═════════════════════════════
nq = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / "data/nq_1m/*.parquet"))))
nq = nq.sort_values("ts_utc").reset_index(drop=True)
mins = (nq["ts_et"].dt.hour * 60 + nq["ts_et"].dt.minute).to_numpy()
days = np.array(sorted(nq["session_date"].unique()))
D = len(days)
di = pd.Categorical(nq["session_date"], categories=days).codes


def grid(mask, col, ncol):
    """OHLCV-Matrix (Tage x Minuten) für die Bars in mask, Spalte = col."""
    out = {}
    for k in ["open", "high", "low", "close", "volume"]:
        a = np.full((D, ncol), np.nan)
        a[di[mask], col[mask]] = nq[k].to_numpy()[mask]
        out[k] = a
    out["close_ff"] = pd.DataFrame(out["close"]).ffill(axis=1).to_numpy()
    out["volume"] = np.nan_to_num(out["volume"])
    return out


m_rth = (mins >= 570) & (mins < 960)
R = grid(m_rth, mins - 570, 390)
m_eth = (mins >= 1080) | (mins < 570)
E = grid(m_eth, (mins - 1080) % 1440, 930)
m_post = (mins >= 960) & (mins < 1020)
PST = grid(m_post, mins - 960, 60)

date = pd.to_datetime(days)
train = date < SPLIT
adj = nq.groupby(di)["adj"].first().reindex(range(D)).to_numpy()
sym = nq.groupby(di)["symbol"].first().reindex(range(D)).to_numpy()

rth_n = (R["volume"] > 0).sum(1)
full = (rth_n >= 380) & np.isfinite(R["close"][:, 385:]).any(1)


def first_valid(a):
    idx = np.argmax(np.isfinite(a), axis=1)
    return a[np.arange(D), idx]


open_rth = np.where(np.isfinite(R["open"][:, 0]), R["open"][:, 0], first_valid(R["open"]))


def P(t):
    """Preis t Minuten nach 09:30 (t=0 Open, sonst Close des Bars davor)."""
    return open_rth if t == 0 else R["close_ff"][:, t - 1]


def EP(t):
    """Preis t Minuten nach 18:00."""
    return first_valid(E["open"]) if t == 0 else E["close_ff"][:, t - 1]


close_rth = P(390)
on_open, on_close = EP(0), EP(930)
on_high, on_low = np.nanmax(E["high"], 1), np.nanmin(E["low"], 1)
rth_high, rth_low = np.nanmax(R["high"], 1), np.nanmin(R["low"], 1)
post_close = np.where(np.isfinite(PST["close_ff"][:, -1]), PST["close_ff"][:, -1], close_rth)


def prev(a):
    """Vortageswert, auf den heutigen Kontrakt umgerechnet (Roll-Gap raus)."""
    out = np.full(D, np.nan)
    out[1:] = a[:-1] + adj[:-1] - adj[1:]
    return out


prev_close, prev_high, prev_low, prev_open = prev(close_rth), prev(rth_high), prev(rth_low), prev(open_rth)
prev_full = np.r_[False, full[:-1]]

# IV zum Anker (letzter Cboe-Close vor 18:00)
def load_iv(n):
    df = pd.read_csv(HERE / f"data/iv/{n}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    return pd.Series(df["CLOSE"].astype(float).values, index=pd.to_datetime(df["DATE"]).astype("datetime64[ns]"), name=n)


iv = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX9D", "VIX1D"]], axis=1, sort=True)
anchor_day = pd.to_datetime(nq.groupby(di)["ts_et"].first().dt.tz_localize(None).dt.date.values).astype("datetime64[ns]")
ivd = pd.merge_asof(pd.DataFrame({"a": anchor_day}), iv.reset_index(names="d").sort_values("d"),
                    left_on="a", right_on="d", direction="backward")
stale = (ivd["a"] - ivd["d"]).dt.days > 5
ivd.loc[stale, ["VIX", "VXN", "VIX9D", "VIX1D"]] = np.nan
vix, vxn, vix9d, vix1d = (ivd[c].to_numpy() for c in ["VIX", "VXN", "VIX9D", "VIX1D"])
vix_prev = np.r_[np.nan, vix[:-1]]
sig = open_rth * vxn / 100 / np.sqrt(252)  # 1σ Tag in Punkten (VXN)

# ═════════════════════════════ Auswertung ═════════════════════════════
results = []


def tstat(x):
    x = x[np.isfinite(x)]
    if len(x) < 10 or x.std() == 0:
        return np.nan
    return x.mean() / x.std(ddof=1) * np.sqrt(len(x))


def add(fam, name, sig_dir, entry, exit_, gross_pts=None, mask=None):
    """sig_dir: +1/-1/0 je Tag. Richtung für Test wird auf Train festgelegt."""
    s = np.asarray(sig_dir, float)
    ok = full & (s != 0) & np.isfinite(s) & np.isfinite(entry)
    if gross_pts is None:
        ok &= np.isfinite(exit_)
        g = s * (exit_ - entry)
    else:
        ok &= np.isfinite(gross_pts)
        g = gross_pts
    if mask is not None:
        ok &= mask
    bps = np.where(ok, g / entry * 1e4, np.nan)
    cost = np.where(ok, COST_PTS / entry * 1e4, np.nan)
    tr, te = bps[train & ok], bps[~train & ok]
    if len(tr) < 30 or len(te) < 15:
        return
    d = np.sign(np.nanmean(tr)) or 1.0
    net_tr = d * tr - cost[train & ok]
    net_te = d * te - cost[~train & ok]
    yrs_te = (date[~train].max() - SPLIT).days / 365.25
    results.append(dict(
        Familie=fam, Hypothese=name + ("" if d > 0 else "  ⟲ umgekehrt"),
        n_train=len(tr), t_train=tstat(d * tr), netto_train=np.mean(net_tr),
        n_test=len(te), trades_jahr=len(te) / yrs_te, t_test=tstat(net_te), netto_test=np.mean(net_te),
        hit_test=100 * np.mean(net_te > 0), pkt_test=np.mean((d * te - cost[~train & ok]) * entry[~train & ok] / 1e4),
    ))


ALL = np.ones(D)

# ── Uhrzeit (immer long, Richtung aus Train) ──
add("Uhrzeit", "Overnight 18:00→09:30", ALL, on_open, open_rth)
add("Uhrzeit", "RTH 09:30→16:00", ALL, open_rth, close_rth)
add("Uhrzeit", "Post 16:00→17:00", ALL, close_rth, post_close)
for a, b, lab in [(0, 120, "18:00→20:00"), (120, 540, "20:00→03:00 Asien"), (540, 870, "03:00→08:30 London"),
                  (870, 900, "08:30→09:00"), (900, 930, "09:00→09:30")]:
    add("Uhrzeit", lab, ALL, EP(a), EP(b) if b < 930 else open_rth)
for k in range(13):
    a, b = 30 * k, 30 * k + 30
    hh = lambda t: f"{(570 + t) // 60:02d}:{(570 + t) % 60:02d}"
    add("Uhrzeit", f"{hh(a)}→{hh(b)}", ALL, P(a), P(b))
add("Uhrzeit", "15:50→16:00", ALL, P(380), P(390))
add("Uhrzeit", "09:30→09:35", ALL, P(0), P(5))

# ── Kalender (Tag mit Bedingung, ganze Session 18:00→17:00 und RTH) ──
wd = date.weekday
month = date.month
nxt = np.r_[date[1:], date[-1:] + pd.Timedelta(days=1)]
prv = np.r_[date[:1] - pd.Timedelta(days=1), date[:-1]]
last_of_month = np.r_[month[1:] != month[:-1], True]
tom_idx = np.zeros(D, int)
for i in range(1, D):
    tom_idx[i] = 1 if month[i] != month[i - 1] else tom_idx[i - 1] + 1
third_fri = (wd == 4) & (date.day >= 15) & (date.day <= 21)
week = date.to_period("W")
opex_week = pd.Series(third_fri).groupby(week).transform("max").to_numpy()
wk_codes = pd.Categorical(week).codes
after_opex = np.zeros(D, bool)
ow = set(wk_codes[opex_week])
after_opex = np.isin(wk_codes - 1, list(ow))
gap_next = (nxt - date).days
gap_prev = (date - prv).days
pre_hol = ((wd < 4) & (gap_next > 1)) | ((wd == 4) & (gap_next > 3))
post_hol = ((wd > 0) & (gap_prev > 1)) | ((wd == 0) & (gap_prev > 3))
roll_day = np.r_[False, sym[1:] != sym[:-1]]
cal = {
    "Montag": wd == 0, "Dienstag": wd == 1, "Mittwoch": wd == 2, "Donnerstag": wd == 3, "Freitag": wd == 4,
    "Turn of Month (letzter + erste 3 Tage)": last_of_month | ((tom_idx >= 1) & (tom_idx <= 3)),
    "Monatsmitte (Tag 8-15 im Monat)": (tom_idx >= 7) & (tom_idx <= 12),
    "OPEX-Freitag": third_fri, "OPEX-Woche": opex_week, "Woche nach OPEX": after_opex,
    "Vor Feiertag": pre_hol, "Nach Feiertag": post_hol, "Roll-Tag": roll_day,
    "Dezember": month == 12, "September": month == 9,
}
for lab, c in cal.items():
    add("Kalender", f"{lab} · Session", c.astype(float), on_open, post_close)
    add("Kalender", f"{lab} · RTH", c.astype(float), open_rth, close_rth)
add("Kalender", "Monatsletzter Tag · 15:00→16:00", last_of_month.astype(float), P(330), P(390))
add("Kalender", "Monatsletzter Tag · 15:50→16:00", last_of_month.astype(float), P(380), P(390))

# ── Intraday-Momentum (Richtung aus früherem Fenster) ──
sgn = np.sign
add("Momentum", "Vortag-Close→10:00 ⇒ 15:30→16:00", sgn(P(30) - prev_close), P(360), P(390))
add("Momentum", "09:30→10:00 ⇒ 15:30→16:00", sgn(P(30) - P(0)), P(360), P(390))
add("Momentum", "09:30→10:00 ⇒ 10:00→16:00", sgn(P(30) - P(0)), P(30), P(390))
add("Momentum", "09:30→09:45 ⇒ 09:45→16:00", sgn(P(15) - P(0)), P(15), P(390))
add("Momentum", "09:30→12:00 ⇒ 12:00→16:00", sgn(P(150) - P(0)), P(150), P(390))
add("Momentum", "09:30→15:00 ⇒ 15:00→16:00", sgn(P(330) - P(0)), P(330), P(390))
add("Momentum", "09:30→15:50 ⇒ 15:50→16:00", sgn(P(380) - P(0)), P(380), P(390))
add("Momentum", "Overnight 18:00→09:30 ⇒ RTH", sgn(open_rth - on_open), open_rth, close_rth)
add("Momentum", "Overnight 18:00→09:30 ⇒ 09:30→10:00", sgn(open_rth - on_open), P(0), P(30))
add("Momentum", "London 03:00→09:30 ⇒ RTH", sgn(open_rth - EP(540)), open_rth, close_rth)
add("Momentum", "Asien 20:00→03:00 ⇒ 03:00→09:30", sgn(EP(540) - EP(120)), EP(540), open_rth)
add("Momentum", "Erste 5 Min ⇒ 09:35→10:30", sgn(P(5) - P(0)), P(5), P(60))

# ── Gap (Open vs. Vortages-RTH-Close, in σ) ──
gap = (open_rth - prev_close) / sig
for lo, hi in [(0.1, 0.3), (0.3, 0.6), (0.6, 1.0), (1.0, 9)]:
    for side, lab in [(1, "hoch"), (-1, "runter")]:
        c = (side * gap > lo) & (side * gap <= hi) & prev_full
        s = np.where(c, -side, 0.0)  # Fade als Ausgangsrichtung
        for t, tl in [(30, "10:00"), (150, "12:00"), (390, "16:00")]:
            add("Gap", f"Gap {lab} {lo}-{hi}σ fade ⇒ bis {tl}", s, P(0), P(t))
# Gap-Fill bis Vortages-Close, sonst Exit 16:00
fill_pts = np.full(D, np.nan)
for i in np.flatnonzero(full & prev_full & (np.abs(gap) > 0.1) & np.isfinite(gap)):
    tgt, e = prev_close[i], open_rth[i]
    hit = (R["low"][i] <= tgt) if e > tgt else (R["high"][i] >= tgt)
    fill_pts[i] = abs(e - tgt) if hit.any() else (e - close_rth[i]) * np.sign(e - tgt)
add("Gap", "Gap >0.1σ Fill-Trade (Ziel Vortages-Close, Exit 16:00)", np.where(np.abs(gap) > 0.1, 1.0, 0), open_rth, None, gross_pts=fill_pts)

# ── Overnight-Range ──
on_rng = (on_high - on_low) / sig
add("Overnight", "Open über ONH ⇒ RTH", np.where(open_rth > on_high - 0.25, 1.0, 0), open_rth, close_rth)
add("Overnight", "Open unter ONL ⇒ RTH", np.where(open_rth < on_low + 0.25, -1.0, 0), open_rth, close_rth)
add("Overnight", "Open über ONH ⇒ 10:00", np.where(open_rth > on_high - 0.25, 1.0, 0), P(0), P(30))
add("Overnight", "Open unter ONL ⇒ 10:00", np.where(open_rth < on_low + 0.25, -1.0, 0), P(0), P(30))
pos = (open_rth - on_low) / (on_high - on_low)
add("Overnight", "Open im oberen ON-Drittel ⇒ RTH", np.where(pos > 2 / 3, 1.0, 0), open_rth, close_rth)
add("Overnight", "Open im unteren ON-Drittel ⇒ RTH", np.where(pos < 1 / 3, -1.0, 0), open_rth, close_rth)
q_on = np.nanquantile(on_rng[train & full], [0.2, 0.8])
add("Overnight", "Enge ON-Range (unterstes 20 %) · Richtung ON ⇒ RTH",
    np.where(on_rng < q_on[0], sgn(open_rth - on_open), 0), open_rth, close_rth)
add("Overnight", "Weite ON-Range (oberstes 20 %) · Richtung ON ⇒ RTH",
    np.where(on_rng > q_on[1], sgn(open_rth - on_open), 0), open_rth, close_rth)

# ── Vortag ──
prev_ret = np.r_[np.nan, ((close_rth - open_rth) / sig)[:-1]]
add("Vortag", "Richtung Vortag-RTH ⇒ RTH", sgn(prev_ret), open_rth, close_rth)
add("Vortag", "Vortag-RTH > +1σ ⇒ RTH", np.where(prev_ret > 1, 1.0, 0), open_rth, close_rth)
add("Vortag", "Vortag-RTH < −1σ ⇒ RTH", np.where(prev_ret < -1, 1.0, 0), open_rth, close_rth)
add("Vortag", "Vortag-RTH < −1σ ⇒ Session", np.where(prev_ret < -1, 1.0, 0), on_open, post_close)
updn = np.sign(close_rth - open_rth)
streak = np.zeros(D)
for i in range(1, D):
    streak[i] = (streak[i - 1] + updn[i - 1]) if np.sign(streak[i - 1]) == updn[i - 1] else updn[i - 1]
add("Vortag", "3+ rote RTH-Tage ⇒ RTH", np.where(streak <= -3, 1.0, 0), open_rth, close_rth)
add("Vortag", "3+ grüne RTH-Tage ⇒ RTH", np.where(streak >= 3, 1.0, 0), open_rth, close_rth)
cl_loc = np.r_[np.nan, ((close_rth - rth_low) / (rth_high - rth_low))[:-1]]
add("Vortag", "Vortag schließt oberes 10 % der Range ⇒ RTH", np.where(cl_loc > 0.9, 1.0, 0), open_rth, close_rth)
add("Vortag", "Vortag schließt unteres 10 % der Range ⇒ RTH", np.where(cl_loc < 0.1, 1.0, 0), open_rth, close_rth)
add("Vortag", "Open über PDH ⇒ RTH", np.where(open_rth > prev_high, 1.0, 0), open_rth, close_rth)
add("Vortag", "Open unter PDL ⇒ RTH", np.where(open_rth < prev_low, -1.0, 0), open_rth, close_rth)
prev_rng = np.r_[np.nan, ((rth_high - rth_low) / sig)[:-1]]

# ── Vola-Regime (Quintile auf Train, Q5 long / Q1 short) ──
def quint(name, x, entry, exit_, fam="Vola"):
    ok = np.isfinite(x) & full
    q = np.nanquantile(x[ok & train], [0.2, 0.8])
    add(fam, f"{name}: oberstes 20 % long / unterstes 20 % short",
        np.where(x >= q[1], 1.0, np.where(x <= q[0], -1.0, 0)), entry, exit_)
    add(fam, f"{name}: nur oberstes 20 % long", np.where(x >= q[1], 1.0, 0), entry, exit_)
    add(fam, f"{name}: nur unterstes 20 % long", np.where(x <= q[0], 1.0, 0), entry, exit_)


quint("VIX9D/VIX (Termstruktur) · Session", vix9d / vix, on_open, post_close)
quint("VIX9D/VIX (Termstruktur) · RTH", vix9d / vix, open_rth, close_rth)
quint("VXN/VIX (Nasdaq-Prämie) · Session", vxn / vix, on_open, post_close)
quint("VIX Tagesänderung % · Session", vix / vix_prev - 1, on_open, post_close)
quint("VIX-Niveau · Session", vix, on_open, post_close)
quint("Vortags-Range / σ (realisiert vs. implizit) · Session", prev_rng, on_open, post_close)
quint("ON-Range / σ · RTH", on_rng, open_rth, close_rth)
quint("Gap / σ · RTH", gap, open_rth, close_rth)

# ── Volumen ──
v30 = R["volume"][:, :30].sum(1)
v30_avg = pd.Series(np.where(full, v30, np.nan)).rolling(20, min_periods=10).mean().shift(1).to_numpy()
rvol = v30 / v30_avg
q_rv = np.nanquantile(rvol[train & full], [1 / 3, 2 / 3])
add("Volumen", "Hohes RVOL 1. halbe Std · Richtung 09:30-10:00 ⇒ 10:00→16:00",
    np.where(rvol > q_rv[1], sgn(P(30) - P(0)), 0), P(30), P(390))
add("Volumen", "Niedriges RVOL 1. halbe Std · Richtung 09:30-10:00 ⇒ 10:00→16:00",
    np.where(rvol < q_rv[0], sgn(P(30) - P(0)), 0), P(30), P(390))
von = E["volume"].sum(1)
von_avg = pd.Series(np.where(full, von, np.nan)).rolling(20, min_periods=10).mean().shift(1).to_numpy()
quint("Overnight-Volumen relativ · RTH", von / von_avg, open_rth, close_rth, fam="Volumen")
# Climax-Bar: Volumen > 4x und |Body| > 3x Schnitt der letzten 30 Bars, erstes Event pro Tag
body = R["close"] - R["open"]
vm = pd.DataFrame(R["volume"]).T.rolling(30, min_periods=20).mean().shift(1).T.to_numpy()
bm = pd.DataFrame(np.abs(body)).T.rolling(30, min_periods=20).mean().shift(1).T.to_numpy()
ev = (R["volume"] > 4 * vm) & (np.abs(body) > 3 * bm)
ev[:, :30] = False
ev[:, 360:] = False
for h in [5, 15, 30]:
    s, en, ex = np.zeros(D), np.full(D, np.nan), np.full(D, np.nan)
    for i in np.flatnonzero(ev.any(1)):
        t = np.argmax(ev[i])
        s[i], en[i], ex[i] = np.sign(body[i, t]), R["close_ff"][i, t], R["close_ff"][i, t + h]
    add("Volumen", f"Climax-Bar (Vol>4x, Body>3x) Richtung ⇒ nächste {h} Min", s, en, ex)

# ── VWAP ──
tp = (R["high"] + R["low"] + R["close"]) / 3
vw = np.nancumsum(np.nan_to_num(tp) * R["volume"], 1) / np.maximum(np.cumsum(R["volume"], 1), 1)
for t, tl in [(60, "10:30"), (150, "12:00"), (270, "14:00")]:
    dv = (P(t) - vw[:, t - 1]) / sig
    for k in [0.3, 0.6]:
        add("VWAP", f"{tl}: Preis > {k}σ über VWAP ⇒ bis 16:00", np.where(dv > k, 1.0, 0), P(t), P(390))
        add("VWAP", f"{tl}: Preis > {k}σ unter VWAP ⇒ bis 16:00", np.where(dv < -k, 1.0, 0), P(t), P(390))

# ═════════════════════════════ Levels: Reaktion vs. Kontrolle ═════════════════════════════
RACE = 0.15  # σ
level_rows = []


def race(level, side, label, shifts=(0.0, -0.3, -0.15, 0.15, 0.3)):
    """side=+1 Widerstand (Annäherung von unten), -1 Unterstützung. Erster RTH-Touch, dann
    wer zuerst: RACE·σ Reaktion vom Level weg oder RACE·σ durch (gleicher Bar = durch)."""
    for sh in shifts:
        lv = level + sh * sig
        out = []
        for i in np.flatnonzero(full & np.isfinite(lv) & np.isfinite(sig)):
            if side * (open_rth[i] - lv[i]) >= 0:
                continue
            far = (R["high"][i] - lv[i]) if side == 1 else (lv[i] - R["low"][i])
            back = (lv[i] - R["low"][i]) if side == 1 else (R["high"][i] - lv[i])
            tt = np.flatnonzero(far >= 0)
            if not len(tt):
                continue
            t0, x = tt[0], RACE * sig[i]
            up = np.flatnonzero(far[t0:] >= x)
            dn = np.flatnonzero(back[t0 + 1:] >= x)
            u = up[0] if len(up) else 10**9
            d = dn[0] + 1 if len(dn) else 10**9
            if u == d == 10**9:
                continue
            out.append((date[i] < SPLIT, d < u))
        o = np.array(out)
        if not len(o):
            continue
        level_rows.append(dict(Level=label, Verschiebung=sh,
                               n_train=int(o[:, 0].sum()), reakt_train=100 * o[o[:, 0], 1].mean(),
                               n_test=int((~o[:, 0].astype(bool)).sum()),
                               reakt_test=100 * o[~o[:, 0].astype(bool), 1].mean()))


race(prev_high, 1, "PDH (Vortageshoch)")
race(prev_low, -1, "PDL (Vortagestief)")
race(on_high, 1, "ONH (Overnight-Hoch)")
race(on_low, -1, "ONL (Overnight-Tief)")
race(prev_close, 1, "Vortages-Close von unten")
race(prev_close, -1, "Vortages-Close von oben")
race(np.ceil(open_rth / 100) * 100, 1, "Runde 100er über Open")
race(np.floor(open_rth / 100) * 100, -1, "Runde 100er unter Open")
race(on_open, 1, "Globex-Open 18:00 von unten")
race(on_open, -1, "Globex-Open 18:00 von oben")

# ═════════════════════════════ Report ═════════════════════════════
res = pd.DataFrame(results)
res["bestanden"] = (res["t_train"] >= T_TRAIN) & (res["t_test"] >= T_TEST) & (res["netto_test"] > 0)
res["knapp"] = ~res["bestanden"] & (res["t_train"] >= 2.0) & (res["t_test"] >= 1.5) & (res["netto_test"] > 0)
res = res.sort_values(["bestanden", "knapp", "t_test"], ascending=False)
lv = pd.DataFrame(level_rows)

fmt = res.copy()
for c in ["t_train", "t_test", "trades_jahr"]:
    fmt[c] = fmt[c].round(1)
for c in ["netto_train", "netto_test", "hit_test", "pkt_test"]:
    fmt[c] = fmt[c].round(2)
fmt = fmt.rename(columns={"netto_train": "netto Train bps", "netto_test": "netto Test bps",
                          "hit_test": "Trefferquote Test %", "pkt_test": "Ø Pkt/Trade Test",
                          "trades_jahr": "Trades/Jahr"})
lvf = lv.copy()
lvf["reakt_train"], lvf["reakt_test"] = lvf["reakt_train"].round(1), lvf["reakt_test"].round(1)
lvf = lvf.rename(columns={"Verschiebung": "Verschiebung σ (0 = echtes Level)",
                          "reakt_train": "Reaktion zuerst % Train", "reakt_test": "Reaktion zuerst % Test"})

md = [
    "# Edge-Scan NQ 1m", "",
    f"Train {date[train].min().date()} – {date[train].max().date()}, Test {date[~train].min().date()} – {date[~train].max().date()}. "
    f"Kosten {COST_PTS} Pkt/Round-Trip. Richtung je Hypothese nur aus Train. {len(res)} Hypothesen getestet.", "",
    f"**Bestanden** (t Train ≥ {T_TRAIN}, t Test ≥ {T_TEST}, netto > 0): {int(res['bestanden'].sum())}  ",
    f"**Knapp** (t Train ≥ 2, t Test ≥ 1.5): {int(res['knapp'].sum())}", "",
    "## Alle Hypothesen", "", fmt.to_markdown(index=False), "",
    f"## Levels: Reaktion {RACE}σ zuerst vs. Kontroll-Levels", "",
    "Erster RTH-Touch, symmetrisches Rennen ±" + f"{RACE}σ ab Level (Zufall ≈ 50 %). Verschiebung ≠ 0 = Kontrolle.", "",
    lvf.to_markdown(index=False), "",
]
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(md))
res.to_csv(HERE / "results/edge_scan.csv", index=False)
show = ["Familie", "Hypothese", "n_train", "t_train", "n_test", "Trades/Jahr", "t_test", "netto Test bps", "Ø Pkt/Trade Test", "Trefferquote Test %"]
print(fmt[show].head(40).to_string(index=False))
print()
print(lvf.to_string(index=False))
