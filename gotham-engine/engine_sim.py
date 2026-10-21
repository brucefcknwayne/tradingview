"""
Gotham Engine v1.5.1 – Nachrechnung der Live-Regeln auf echten NQ-Trades (Databento, Schema trades) + Auswertung + Kalibrierung.

Daten: data-lab/data/raw/trades/glbx-mdp3-<UTC-Tag>.trades.dbn.zst (NQ.FUT), je Handelstag (Session 18:00–17:00 NY)
       nur der Front-Kontrakt (meistes Volumen, keine Spreads). side B = +Volumen, A = −Volumen, N = ignoriert.
Nicht berechenbar mit Schema trades: refill (braucht tbbo Bid/Ask-Größen), iceberg (braucht mbo order_id) → leer.
big_orders = Prints mit ≥ 10 Kontrakten (Aggressor-Seite s) im Fenster.

Aufruf: python gotham-engine/engine_sim.py   → gotham-engine/results/*.csv, *.md
"""
import glob
import sys
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd
from numba import njit

HERE = Path(__file__).parent
RAW = HERE.parent / "data-lab/data/raw/trades"
CACHE = HERE.parent / "data-lab/data/raw/engine_cache"
OUT = HERE / "results"
CACHE.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
TICK = 0.25
STEP = 250                       # Bewertung alle 250 ms
N_SIM = 20                       # letzte 20 Handelstage
N_TOD = 8                        # Tageszeit-Profil aus den 8 Tagen davor
NY = "America/New_York"


# ───────────────────────── 1) Trades je Session laden ─────────────────────────
def load_sessions():
    files = sorted(glob.glob(str(RAW / "glbx-mdp3-2026*.trades.dbn.zst")))
    files = [f for f in files if Path(f).name[10:18] >= "20260825"]
    parts = []
    for f in files:
        p = CACHE / (Path(f).name.split(".")[0] + ".parquet")
        if not p.exists():
            df = db.DBNStore.from_file(f).to_df()
            df = df[(df["action"] == "T") & ~df["symbol"].str.contains("-")]
            x = pd.DataFrame({"t": df["ts_event"].astype("int64").to_numpy() // 1_000_000, "px": df["price"].to_numpy(),
                              "v": df["size"].to_numpy().astype(np.int32),
                              "sg": np.where(df["side"].to_numpy() == "B", 1, np.where(df["side"].to_numpy() == "A", -1, 0)).astype(np.int8),
                              "symbol": df["symbol"].to_numpy()})
            x.to_parquet(p, index=False)
        parts.append(pd.read_parquet(p))
    T = pd.concat(parts, ignore_index=True).sort_values("t", kind="stable")
    et = pd.to_datetime(T["t"], unit="ms", utc=True).dt.tz_convert(NY)
    T["session"] = (et + pd.Timedelta(hours=6)).dt.date
    T = T[(et + pd.Timedelta(hours=6)).dt.weekday < 5]          # Sonntag 18:00 gehört zu Montag
    sess = {}
    for d, g in T.groupby("session"):
        front = g.groupby("symbol")["v"].sum().idxmax()
        g = g[g["symbol"] == front]
        if len(g) < 50_000:                                       # unvollständig / Feiertag
            continue
        start = (pd.Timestamp(d) - pd.Timedelta(days=1)).tz_localize(NY) + pd.Timedelta(hours=18)
        sess[d] = dict(symbol=front, t=g["t"].to_numpy(np.int64), p=np.round(g["px"].to_numpy() / TICK).astype(np.int64),
                       v=g["v"].to_numpy(np.int64), sg=g["sg"].to_numpy(np.int64), start=int(start.timestamp() * 1000))
    return sess


def minute_volume(S):
    m = ((S["t"] - S["start"]) // 60000).astype(np.int64)
    out = np.zeros(1380); ok = (m >= 0) & (m < 1380)
    np.add.at(out, m[ok], S["v"][ok])
    return out


# ───────────────────────── 2) Kern: Fenster-Kennzahlen alle 250 ms ─────────────────────────
@njit(cache=True)
def core(t, p, v, sg, T0, nev, W, todr, start):
    n = len(t)
    nsl = nev
    # 250-ms-Scheiben: Hoch/Tief/Volumen (Scheibe k = (T_k − 250, T_k])
    shi = np.full(nsl, -1, np.int64); slo = np.full(nsl, -1, np.int64); svol = np.zeros(nsl)
    for i in range(n):
        k = (t[i] - T0 + STEP - 1) // STEP
        if k < 0 or k >= nsl:
            continue
        if shi[k] < 0 or p[i] > shi[k]:
            shi[k] = p[i]
        if slo[k] < 0 or p[i] < slo[k]:
            slo[k] = p[i]
        if sg[i] != 0:
            svol[k] += v[i]
    cs = np.zeros(nsl + 1)
    for k in range(nsl):
        cs[k + 1] = cs[k] + svol[k]
    wsl = W // STEP
    cap = nev
    R = np.full((cap, 24), np.nan)
    nr = 0
    pmin = p.min(); pmax = p.max()
    hist = np.zeros(pmax - pmin + 1)
    ring_v = np.zeros(360); ring_t = np.zeros(360, np.int64); rn = 0; rpos = 0
    d80 = np.nan
    j0 = 0; j1 = -1
    for k in range(nev):
        T = T0 + k * STEP
        while j1 + 1 < n and t[j1 + 1] <= T:
            j1 += 1
        while j0 <= j1 and t[j0] <= T - W:
            j0 += 1
        D = 0.0; V = 0.0; hi = -1; lo = -1
        if j1 >= j0:
            for i in range(j0, j1 + 1):
                if sg[i] != 0:
                    D += sg[i] * v[i]; V += v[i]
                if hi < 0 or p[i] > hi:
                    hi = p[i]
                if lo < 0 or p[i] < lo:
                    lo = p[i]
        # d80: |Δ| alle 5 s, nur wenn in den letzten 60 s gehandelt wurde, Fenster 30 min, max. 360 Werte
        if k % 20 == 0:
            act60 = cs[k + 1] - cs[max(0, k + 1 - 240)]
            if act60 > 0:
                ring_v[rpos] = abs(D); ring_t[rpos] = T; rpos = (rpos + 1) % 360; rn = min(rn + 1, 360)
            vals = np.empty(360); m = 0
            for q in range(rn):
                if ring_t[q] > T - 1800000:
                    vals[m] = ring_v[q]; m += 1
            if m >= 24:
                x = np.sort(vals[:m]); pos = 0.8 * (m - 1); a = int(np.floor(pos)); b = min(a + 1, m - 1)
                d80 = x[a] + (x[b] - x[a]) * (pos - a)
            else:
                d80 = np.nan
        if j1 < j0 or D == 0:
            continue
        s = 1 if D > 0 else -1
        # Push-Variante braucht ggf. |ΔA| ≥ 30 auch bei kleinem |Δ| → Kennzahlen immer wenn V ≥ 30
        if V < 30:
            continue
        first = p[j0]; last = p[j1]
        move = s * (last - first)
        # Wall: Preis mit meistem Aggressor-Volumen der Seite s
        tot_s = 0.0
        for i in range(j0, j1 + 1):
            if sg[i] == s:
                hist[p[i] - pmin] += v[i]; tot_s += v[i]
        best = -1; bv = -1.0
        for pp in range(lo, hi + 1):
            if hist[pp - pmin] > bv:
                bv = hist[pp - pmin]; best = pp
        ext = hi if s > 0 else lo
        wall = best if abs(best - ext) <= 4 else ext
        near = 0.0
        for pp in range(wall - 1, wall + 2):
            if pmin <= pp <= pmax:
                near += hist[pp - pmin]
        conc = near / tot_s if tot_s > 0 else 0.0
        for pp in range(lo, hi + 1):
            hist[pp - pmin] = 0.0
        # fading (Volumen der Seite s je Viertel) und große Prints
        qv = np.zeros(4); big = 0
        for i in range(j0, j1 + 1):
            if sg[i] == s:
                qi = min(3, (t[i] - (T - W)) * 4 // W)
                qv[qi] += v[i]
                if v[i] >= 10:
                    big += 1
        fading = 1.0 if qv[3] < 0.5 * max(qv[0], max(qv[1], qv[2])) else 0.0
        # Push-Variante: erster Kontakt mit der Wall
        c = -1
        for i in range(j0, j1 + 1):
            if s * (p[i] - wall) >= 0:
                c = i; break
        age = (T - t[c]) if c >= 0 else -1
        dA = 0.0; nA = 0
        if c >= 0:
            for i in range(c, j1 + 1):
                if sg[i] != 0:
                    dA += sg[i] * v[i]; nA += 1
        push = s * (wall - first); beyond = s * (last - wall)
        # 2 min vor W (Scheiben)
        ph = -1; pl = -1
        for kk in range(max(0, k - wsl - 480 + 1), max(0, k - wsl + 1)):
            if shi[kk] >= 0:
                if ph < 0 or shi[kk] > ph:
                    ph = shi[kk]
                if pl < 0 or slo[kk] < pl:
                    pl = slo[kk]
        # Aktivität
        mi = (T - start) // 60000
        tod = todr[mi] if 0 <= mi < 1380 else 1.0
        v_2m = cs[max(0, k + 1 - 80)] - cs[max(0, k + 1 - 480)]
        v_30 = cs[k + 1] - cs[max(0, k + 1 - 7200)]
        spike = (v_2m / 100.0) / (v_30 / 1800.0) if v_30 > 0 else 1.0
        act = max(tod, spike) ** 0.75
        act = min(8.0, max(1.0, act))
        R[nr, 0] = k; R[nr, 1] = T; R[nr, 2] = D; R[nr, 3] = V; R[nr, 4] = s; R[nr, 5] = move
        R[nr, 6] = first; R[nr, 7] = last; R[nr, 8] = hi; R[nr, 9] = lo; R[nr, 10] = wall; R[nr, 11] = conc
        R[nr, 12] = ph if ph >= 0 else np.nan; R[nr, 13] = pl if pl >= 0 else np.nan; R[nr, 14] = fading; R[nr, 15] = big
        R[nr, 16] = age; R[nr, 17] = dA; R[nr, 18] = nA; R[nr, 19] = push; R[nr, 20] = beyond
        R[nr, 21] = d80; R[nr, 22] = act; R[nr, 23] = j1 - j0 + 1
        nr += 1
    return R[:nr]


C = dict(k=0, T=1, D=2, V=3, s=4, move=5, first=6, last=7, hi=8, lo=9, wall=10, conc=11, ph=12, pl=13, fading=14, big=15,
         age=16, dA=17, nA=18, push=19, beyond=20, d80=21, act=22, ntr=23)


# ───────────────────────── 3) Ereignisse (steigende Flanke + Cooldown) ─────────────────────────
@njit(cache=True)
def gen_events(R, absMult, absTicks, minConc, brkMult, brkTicks, cooldown, dup_ms, do_abs, do_brk):
    n = R.shape[0]
    ev = np.full((n, 4), -1.0)            # Zeile, Typ (0 Abs, 1 Brk), dir, Variante (0 normal, 1 Push)
    ne = 0
    last_ev = np.full((2, 2), -1e18)      # [Typ, dir(0 up,1 down)]
    last_raw = np.full(2, -1e18)          # Duplikat-Filter Breaking je dir
    prevA = np.zeros(2, np.bool_); prevB = np.zeros(2, np.bool_); prevk = -10
    for r in range(n):
        k = R[r, 0]; T = R[r, 1]; D = R[r, 2]; s = R[r, 4]; d80 = R[r, 21]
        contig = (k == prevk + 1)
        if not contig:
            prevA[:] = False; prevB[:] = False
        prevk = k
        curA = np.zeros(2, np.bool_); curB = np.zeros(2, np.bool_)
        variant = 0
        if not np.isnan(d80) and d80 > 0:
            normal = d80 * R[r, 22]
            if do_abs:
                a_norm = abs(D) >= max(30.0, absMult * normal) and R[r, 5] <= absTicks and R[r, 11] >= minConc
                dA = R[r, 17]
                a_push = (R[r, 16] >= 3000 and dA * s > 0 and abs(dA) >= max(30.0, absMult * normal) and R[r, 19] > 2
                          and R[r, 20] <= absTicks and R[r, 18] >= 3 and R[r, 11] >= minConc)
                if a_norm or a_push:
                    di = 0 if s < 0 else 1          # Verkäufer absorbiert → up
                    curA[di] = True
                    variant = 0 if a_norm else 1
            if do_brk:
                broke = (s > 0 and not np.isnan(R[r, 12]) and R[r, 8] > R[r, 12]) or (s < 0 and not np.isnan(R[r, 13]) and R[r, 9] < R[r, 13])
                if abs(D) >= max(30.0, brkMult * normal) and R[r, 5] >= brkTicks and broke:
                    di = 0 if s > 0 else 1
                    curB[di] = True
        for di in range(2):
            if curA[di] and not prevA[di] and T - last_ev[0, di] >= cooldown:
                ev[ne, 0] = r; ev[ne, 1] = 0; ev[ne, 2] = di; ev[ne, 3] = variant; ne += 1; last_ev[0, di] = T
            if curB[di] and not prevB[di]:
                ok = T - last_ev[1, di] >= cooldown
                if dup_ms > 0 and T - last_raw[di] < dup_ms:
                    ok = False
                if curB[di]:
                    last_raw[di] = T
                if ok:
                    ev[ne, 0] = r; ev[ne, 1] = 1; ev[ne, 2] = di; ev[ne, 3] = 0; ne += 1; last_ev[1, di] = T
        prevA[:] = curA; prevB[:] = curB
    return ev[:ne]


# ───────────────────────── 4) Ergebnis je Ereignis ─────────────────────────
@njit(cache=True)
def outcome(t, p, T, entry, d, typ, wall, ref):
    """Rückgabe: code (1 HELD/CONTINUED, -1 FAILED, 0 EXPIRED), sek, ret1, ret5, ret15, best, worst (Ticks in dir)."""
    n = len(t)
    i = np.searchsorted(t, T, side="right")
    if typ == 0:
        up_lvl = wall + d * 8; fail_lvl = wall - d * 4
    else:
        up_lvl = entry + d * 16; fail_lvl = ref - d * 4
    code = 0; sec = 180.0; done = False
    r1 = np.nan; r5 = np.nan; r15 = np.nan; best = 0.0; worst = 0.0
    last = entry
    j = i
    while j < n and t[j] <= T + 900000:
        x = p[j]
        if not done and t[j] <= T + 180000:
            if d * (x - up_lvl) >= 0:
                code = 1; sec = (t[j] - T) / 1000.0; done = True
            elif d * (x - fail_lvl) <= 0:
                code = -1; sec = (t[j] - T) / 1000.0; done = True
        rr = d * (x - entry)
        if rr > best:
            best = rr
        if rr < worst:
            worst = rr
        if np.isnan(r1) and t[j] > T + 60000:
            r1 = d * (last - entry)
        if np.isnan(r5) and t[j] > T + 300000:
            r5 = d * (last - entry)
        last = x
        j += 1
    if np.isnan(r1):
        r1 = d * (last - entry)
    if np.isnan(r5):
        r5 = d * (last - entry)
    r15 = d * (last - entry)
    return code, sec, r1, r5, r15, best, worst


def fwd_returns(S, Ts, horizons=(60000, 300000, 900000)):
    t, p = S["t"], S["p"]
    i0 = np.searchsorted(t, Ts, side="right") - 1
    base = np.where(i0 >= 0, p[np.maximum(i0, 0)], np.nan).astype(float)
    out = []
    for h in horizons:
        ih = np.searchsorted(t, Ts + h, side="right") - 1
        out.append(p[ih].astype(float) - base)
    return out


# ───────────────────────── Hauptlauf ─────────────────────────
if __name__ == "__main__":
    sess = load_sessions()
    days = sorted(sess)
    sim_days = days[-N_SIM:]
    print("Sessions geladen:", len(days), "Simulation:", sim_days[0], "…", sim_days[-1], flush=True)
    mv = {d: minute_volume(sess[d]) for d in days}
    WINDOWS = (20000, 10000, 5000)
    rows = {W: {} for W in WINDOWS}
    pools = []
    for d in sim_days:
        S = sess[d]; i = days.index(d)
        prev = [mv[x] for x in days[max(0, i - N_TOD):i]]
        exp = np.mean(prev, axis=0) if prev else np.ones(1380)
        cur = mv[d]; todr = np.ones(1380)
        for m in range(1380):
            past = cur[max(0, m - 30):m]; past = past[past > 0]
            if len(past) and past.mean() > 0:
                todr[m] = exp[m] / past.mean()
        T0 = (S["t"][0] // STEP + 1) * STEP
        nev = int((S["t"][-1] - T0) // STEP) + 1
        for W in WINDOWS:
            rows[W][d] = core(S["t"], S["p"], S["v"], S["sg"], T0, nev, W, todr, S["start"])
        # Zufalls-Pool: jede Sekunde mit Handel in der letzten Minute, Vorwärts-Renditen (aufwärts) in Ticks
        Ts = np.arange(T0, S["t"][-1] - 900000, 1000)
        had = np.searchsorted(S["t"], Ts, side="right") - np.searchsorted(S["t"], Ts - 60000, side="right") > 0
        Ts = Ts[had]
        r1, r5, r15 = fwd_returns(S, Ts)
        hr = pd.to_datetime(Ts, unit="ms", utc=True).tz_convert(NY).hour.to_numpy()
        pools.append(pd.DataFrame({"session": d, "T": Ts, "hour": hr, "r1": r1, "r5": r5, "r15": r15}))
        print(d, S["symbol"], len(S["t"]), "Trades", {W: len(rows[W][d]) for W in WINDOWS}, flush=True)
    POOL = pd.concat(pools, ignore_index=True)
    POOL.to_parquet(CACHE / "random_pool.parquet", index=False)
    for W in WINDOWS:
        np.savez_compressed(CACHE / f"rows_W{W}.npz", **{str(d): rows[W][d] for d in sim_days})
    import pickle
    with open(CACHE / "sess_meta.pkl", "wb") as f:
        pickle.dump({d: dict(symbol=sess[d]["symbol"], start=sess[d]["start"]) for d in sim_days}, f)
    print("fertig Kern", flush=True)
