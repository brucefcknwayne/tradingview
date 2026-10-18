# Aufruf: python data-lab/ib_ext_lock_check.py [Startzeiten, z. B. 08:30,09:30]
# Simulation der Pine-Logik (Einstufung bleibt) auf dem letzten Jahr: % beim Erscheinen vs. eingetreten
import glob, re, sys
import numpy as np, pandas as pd
from pathlib import Path
REPO = str(Path(__file__).resolve().parents[1])
pine = open(f"{REPO}/gotham-zones/IB-Expansion_ALL.pine").read()
A = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
KEYS = re.search(r'KEYS  = "([^"]*)"', pine).group(1).split(" ")
KPB = int(re.search(r'KPB   = (\d+)', pine).group(1))
RAW = {(m, int(b)): s for m, b, s in re.findall(r'mk == "(\w+)" and kb == (\d+) \? "([^"]*)"', pine)}
COR = dict(re.findall(r'COR := barstate.isfirst and mk == "(\w+)" \? "([^"]*)"', pine))
def dec(s, p, sc):
    a, b = s[p], s[p + 1]
    return np.nan if a not in A or b not in A else (A.index(a) * 62 + A.index(b) - 1922) / sc
def rel(hm):
    h, m = map(int, hm.split(":")); return (h * 60 + m - 1080) % 1440
NCOL, LENS, NK = 1380, [15, 30, 45, 60], 31
STARTS = sys.argv[1].split(",") if len(sys.argv) > 1 else ["18:00", "03:00", "08:30", "09:30", "10:30"]
rows = []
for mk in ["NQ", "ES", "RTY", "GC"]:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(f"{REPO}/data-lab/data/{mk.lower()}_1m/*.parquet")))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2024-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low", "close"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    G["close"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    cor = COR[mk]; DT = [dec(cor, 2 * i, 1000) for i in range(10)]; DP = [dec(cor, 20 + 2 * i, 1000) for i in range(10)]
    def corr(a, q):
        qq = np.clip(q, 0, 1) * 10; i0 = np.minimum(np.floor(qq).astype(int), 9); i1 = np.minimum(i0 + 1, 9)
        a = np.array(a); return a[i0] + (a[i1] - a[i0]) * np.minimum(qq - i0, 1)
    test = dts > dts.max() - pd.DateOffset(years=1)
    for st in STARTS:
        ki = KEYS.index(st); blk = RAW[(mk, ki // KPB)]; p0 = (ki % KPB) * 4 * 84
        s = rel(st); relEnd = 1380 if s < 930 else 1320
        for j, L in enumerate(LENS):
            cf = np.array([dec(blk, p0 + (j * 42 + i) * 2, 100) for i in range(42)])
            if np.isnan(cf[:30]).any() or np.isnan(cf[40:]).any() or s + L >= relEnd: continue
            with np.errstate(all="ignore"):
                H = np.nanmax(G["high"][:, s:s + L], 1); Lo = np.nanmin(G["low"][:, s:s + L], 1)
            R = H - Lo; cov = np.isfinite(G["high"][:, s:s + L]).mean(1)
            v = (cov >= 0.8) & (R > 0) & (dts.weekday < 5)
            med = pd.Series(np.where(v, R, np.nan)).rolling(20, min_periods=10).median().shift(1).to_numpy()
            rs = R / med
            e0 = s + L; T = np.arange(e0, relEnd); q = (T - e0 + 1) / (relEnd - e0)
            vv = np.log(1 - np.clip(q, 0, 0.98) + 0.02)[:, None]
            ks = np.arange(NK)[None, :]
            for d in np.flatnonzero(v & test & np.isfinite(rs)):
                c = 1 if rs[d] <= cf[40] else 3 if rs[d] >= cf[41] else 2
                hi = G["high"][d, e0:relEnd]; lo = G["low"][d, e0:relEnd]; cl = G["close"][d, e0:relEnd]
                if np.isnan(hi).all(): continue
                hmax = np.fmax.accumulate(np.nan_to_num(hi, nan=-np.inf)); lmin = np.fmin.accumulate(np.nan_to_num(lo, nan=np.inf))
                for side in (0, 1):
                    lv = H[d] + ks * 0.1 * R[d] if side == 0 else Lo[d] - ks * 0.1 * R[d]
                    reach = (hmax[:, None] >= lv) if side == 0 else (lmin[:, None] <= lv)
                    reach[:, 0] = (hmax > H[d]) if side == 0 else (lmin < Lo[d])
                    dist = ((lv - cl[:, None]) if side == 0 else (cl[:, None] - lv)) / R[d]
                    u = np.log(np.maximum(dist, 0) + 0.03)
                    b = cf[((c - 1) * 2 + side) * 5:((c - 1) * 2 + side) * 5 + 5]
                    p = 1 / (1 + np.exp(-(b[0] + b[1] * u + b[2] * vv + b[3] * u * vv + b[4] * u * u)))
                    pT = p - corr(DT, q)[:, None]; pS = 1 - p - corr(DP, q)[:, None]
                    tp = (p >= 0.5) & (pT >= 0.7) & (q[:, None] < 0.9) & ~reach & np.isfinite(hi)[:, None]
                    sl = (p < 0.5) & (pS >= 0.7) & ~reach & np.isfinite(hi)[:, None]
                    qual = tp | sl
                    for k in np.flatnonzero(qual.any(0)):
                        t = np.argmax(qual[:, k]); hit = reach[-1, k]
                        typ = "Target" if tp[t, k] else "Protect"
                        rows.append((mk, f"{st}-{L}", typ, q[t], pT[t, k] if typ == "Target" else pS[t, k], hit if typ == "Target" else not hit))
    print(mk, len(rows), flush=True)
X = pd.DataFrame(rows, columns=["m", "ib", "art", "q", "angezeigt", "ok"])
X["q10"] = np.minimum((X["q"] * 10).astype(int), 9)
X["band"] = pd.cut(X["angezeigt"], [0.69, 0.8, 0.9, 1.01], labels=["70–80", "80–90", "90–100"])
f = lambda g: pd.Series({"n": len(g), "angezeigt": round(g["angezeigt"].mean(), 3), "eingetreten": round(g["ok"].mean(), 3)})
print(X.groupby("art").apply(f).to_string()); print(X.groupby(["art", "band"], observed=True).apply(f).to_string())
print(X.groupby(["art", "m"]).apply(f).to_string()); print(X.groupby(["art", "q10"]).apply(f).to_string())
