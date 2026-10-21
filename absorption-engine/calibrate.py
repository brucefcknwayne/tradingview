"""
Absorption Engine – dieselbe Logik wie AbsorptionEngine.java (Arten 1–4, 6–8; REFILL braucht Bid/Ask-Größen, die das
Databento-Schema trades nicht hat) auf 1m-Kerzen aus echten NQ-Trades. Zweck: Häufigkeit je Tag prüfen und Standardwerte eichen,
dazu HELD/FAILED gegen Zufall (gleiche Kerzen-Anzahl, gleiche Richtungen, zufällige Kerzen derselben Stunde).
Aufruf: python absorption-engine/calibrate.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gotham-engine"))
from engine_sim import NY, TICK, load_sessions  # noqa: E402

OUT = Path(__file__).parent / "results"; OUT.mkdir(exist_ok=True)
P = dict(lookback=100, swing=20, minStrength=40, flipBody=0.30, flipDelta=0.8, effVol=1.5, effRatio=0.6, wickZone=0.25,
         wickShare=0.15, wickDom=1.3, wickLen=0.35, wallMult=1.5, wallBal=0.2, trapDelta=1.5, exhGrowth=2.0,
         heldAtr=0.5, failAtr=0.15, maxBars=20, stackImb=3.0, stackN=3, drevDelta=1.0, drevKeep=0.3, minModes=1)
import json, os
P.update(json.loads(os.environ.get("ABS_P", "{}")))
TAG = os.environ.get("ABS_TAG", "")
TYPES = ["FLIP", "EFFORT", "WICK", "WALL", "REFILL", "CVD", "TRAPPED", "EXHAUST", "STACKED", "D-REV"]
rng_ = np.random.default_rng(3)


def bars_from_trades(S, sec=60):
    t, p, v, sg = S["t"], S["p"] * TICK, S["v"].astype(float), S["sg"]
    b = (t - S["start"]) // (sec * 1000)
    df = pd.DataFrame({"b": b, "p": p, "buy": np.where(sg > 0, v, 0.0), "sell": np.where(sg < 0, v, 0.0), "t": t})
    df["cd"] = (df["buy"] - df["sell"]).groupby(df["b"]).cumsum()
    g = df.groupby("b")
    B = pd.DataFrame({"o": g["p"].first(), "h": g["p"].max(), "l": g["p"].min(), "c": g["p"].last(),
                      "buy": g["buy"].sum(), "sell": g["sell"].sum(), "t0": g["t"].first(),
                      "maxD": g["cd"].max().clip(lower=0), "minD": g["cd"].min().clip(upper=0)})
    rows = df.groupby(["b", "p"])[["buy", "sell"]].sum().reset_index()
    return B.reset_index(), rows


def evaluate_all(B, rows, P):
    n = len(B); o, h, l, c = (B[k].to_numpy() for k in "ohlc")
    buy, sell = B["buy"].to_numpy(), B["sell"].to_numpy()
    vol, delta = buy + sell, buy - sell
    maxD, minD = B["maxD"].to_numpy(), B["minD"].to_numpy()
    rng = h - l
    rowsg = {k: g for k, g in rows.groupby("b")}
    bidx = B["b"].to_numpy()
    maxrow = np.array([(rowsg[k]["buy"] + rowsg[k]["sell"]).max() for k in bidx])
    cvd = np.cumsum(delta)
    tr = np.maximum(h - l, np.maximum(np.abs(h - np.r_[c[0], c[:-1]]), np.abs(l - np.r_[c[0], c[:-1]])))
    atr = pd.Series(tr).rolling(14, min_periods=5).mean().to_numpy()
    lb, sw = P["lookback"], P["swing"]
    med = lambda x: pd.Series(x).rolling(lb, min_periods=10).median().shift(1).to_numpy()  # noqa: E731
    mVol, mDel, mRng, mRow = med(vol), med(np.abs(delta)), med(rng), med(maxrow)
    out = []
    for i in range(min(lb, 30), n):
        if vol[i] <= 0 or not (mVol[i] > 0 and mRng[i] > 0):
            continue
        rv, rd, rr = vol[i] / mVol[i], abs(delta[i]) / max(1e-9, mDel[i]), rng[i] / mRng[i]
        bull, bear = np.zeros(10), np.zeros(10); bullPx, bearPx = l[i], h[i]
        if rng[i] > 0:
            R0 = rowsg[bidx[i]].set_index("p")
            pr = R0.index.to_numpy(); by = R0["buy"].to_numpy(); se = R0["sell"].to_numpy()
            runA = bestA = runB = bestB = 0
            for q in range(len(pr)):
                askI = q > 0 and pr[q] >= h[i] - rng[i] / 3 and by[q] >= P["stackImb"] * max(1, se[q - 1])
                bidI = q < len(pr) - 1 and pr[q] <= l[i] + rng[i] / 3 and se[q] >= P["stackImb"] * max(1, by[q + 1])
                runA = runA + 1 if askI else 0; bestA = max(bestA, runA)
                runB = runB + 1 if bidI else 0; bestB = max(bestB, runB)
            midp = (h[i] + l[i]) / 2
            if bestA >= P["stackN"] and c[i] < midp: bear[8] = 50 + 50 * min(1, (bestA - P["stackN"]) / 3 + 0.2)
            if bestB >= P["stackN"] and c[i] > midp: bull[8] = 50 + 50 * min(1, (bestB - P["stackN"]) / 3 + 0.2)
            mx_, mn_ = maxD[i], minD[i]; need = P["drevDelta"] * mDel[i]
            if mx_ >= need and delta[i] <= P["drevKeep"] * mx_ and c[i] < h[i] - 0.3 * rng[i]:
                bear[9] = 45 + 55 * min(1, (mx_ - delta[i]) / max(1, 2 * mDel[i]))
            if -mn_ >= need and -delta[i] <= P["drevKeep"] * -mn_ and c[i] > l[i] + 0.3 * rng[i]:
                bull[9] = 45 + 55 * min(1, (delta[i] - mn_) / max(1, 2 * mDel[i]))
        body = c[i] - o[i]
        if rng[i] > 0 and abs(body) >= P["flipBody"] * rng[i] and rd >= P["flipDelta"] and np.sign(body) == -np.sign(delta[i]):
            sc = 40 + 30 * min(1, rd / 2) + 30 * min(1, abs(body) / rng[i])
            (bull if body > 0 else bear)[0] = sc
        ratio = rr / max(1e-9, rv)
        if rv >= P["effVol"] and ratio <= P["effRatio"]:
            sc = 40 + 30 * min(1, (rv - 1) / 2) + 30 * min(1, 1 - ratio / P["effRatio"] + 0.3)
            if rd >= 0.5:
                d = -1 if delta[i] > 0 else 1
            else:
                sh, sl = h[max(0, i - sw):i + 1].max(), l[max(0, i - sw):i + 1].min()
                pos = (c[i] - sl) / (sh - sl) if sh > sl else 0.5
                d = 1 if pos <= 0.33 else (-1 if pos >= 0.67 else 0)
            if d > 0: bull[1] = sc
            elif d < 0: bear[1] = sc
        if rng[i] > 0:
            R = rowsg[bidx[i]]; z = P["wickZone"] * rng[i]
            top, bot = R[R["p"] >= h[i] - z], R[R["p"] <= l[i] + z]
            tb, ts, bb, bs = top["buy"].sum(), top["sell"].sum(), bot["buy"].sum(), bot["sell"].sum()
            upW, dnW = h[i] - max(o[i], c[i]), min(o[i], c[i]) - l[i]; wl = P["wickLen"] * rng[i]
            if tb / vol[i] >= P["wickShare"] and tb / max(1, ts) >= P["wickDom"] and upW >= wl and c[i] < h[i] - z:
                bear[2] = 40 + 30 * min(1, tb / vol[i] / (2 * P["wickShare"])) + 30 * min(1, upW / rng[i])
            if bs / vol[i] >= P["wickShare"] and bs / max(1, bb) >= P["wickDom"] and dnW >= wl and c[i] > l[i] + z:
                bull[2] = 40 + 30 * min(1, bs / vol[i] / (2 * P["wickShare"])) + 30 * min(1, dnW / rng[i])
            rv_ = R["buy"] + R["sell"]
            bal = (rv_ > 0) & ((R["buy"] - R["sell"]).abs() / rv_.clip(lower=1e-9) <= P["wallBal"]) & (rv_ >= P["wallMult"] * mRow[i])
            mid = (h[i] + l[i]) / 2
            wt = R[bal & (R["p"] >= h[i] - rng[i] / 3)]; wb = R[bal & (R["p"] <= l[i] + rng[i] / 3)]
            if len(wb) and c[i] > mid:
                k = (wb["buy"] + wb["sell"]).idxmax(); bull[3] = 40 + 60 * min(1, ((wb.loc[k, "buy"] + wb.loc[k, "sell"]) / max(1, mRow[i]) - 1) / 2); bullPx = wb.loc[k, "p"]
            if len(wt) and c[i] < mid:
                k = (wt["buy"] + wt["sell"]).idxmax(); bear[3] = 40 + 60 * min(1, ((wt.loc[k, "buy"] + wt.loc[k, "sell"]) / max(1, mRow[i]) - 1) / 2); bearPx = wt.loc[k, "p"]
        if i >= sw + 1:
            kLo = i - sw + int(np.argmin(l[i - sw:i])); kHi = i - sw + int(np.argmax(h[i - sw:i]))
            if l[i] < l[kLo] and cvd[i] > cvd[kLo] and c[i] > l[i] + 0.25 * rng[i]:
                bull[5] = 45 + 55 * min(1, (cvd[i] - cvd[kLo]) / max(1, 2 * mDel[i]))
            if h[i] > h[kHi] and cvd[i] < cvd[kHi] and c[i] < h[i] - 0.25 * rng[i]:
                bear[5] = 45 + 55 * min(1, (cvd[kHi] - cvd[i]) / max(1, 2 * mDel[i]))
            pd_, prd = delta[i - 1], abs(delta[i - 1]) / max(1e-9, mDel[i])
            if prd >= P["trapDelta"]:
                newHi = h[i - 1] > h[max(0, i - 1 - sw):i - 1].max(); newLo = l[i - 1] < l[max(0, i - 1 - sw):i - 1].min()
                if pd_ > 0 and newHi and c[i] < o[i - 1]: bear[6] = 50 + 50 * min(1, (prd - 1) / 3); bearPx = max(bearPx, h[i - 1])
                if pd_ < 0 and newLo and c[i] > o[i - 1]: bull[6] = 50 + 50 * min(1, (prd - 1) / 3); bullPx = min(bullPx, l[i - 1])
            d0 = np.sign(c[i - 2] - o[i - 2])
            if d0 != 0:
                bb_ = [c[k] - o[k] for k in (i - 2, i - 1, i)]
                if all(np.sign(x) == d0 for x in bb_) and all(np.sign(delta[k]) == d0 for k in (i - 2, i - 1, i)):
                    eff = [vol[k] / max(abs(x), 1e-9) for k, x in zip((i - 2, i - 1, i), bb_)]
                    if eff[1] > eff[0] and eff[2] > eff[1] and eff[2] >= P["exhGrowth"] * eff[0]:
                        sc = 45 + 55 * min(1, (eff[2] / eff[0] - P["exhGrowth"]) / (2 * P["exhGrowth"]) + 0.2)
                        (bear if d0 > 0 else bull)[7] = sc
        best = None
        for arr, d, px in ((bull, 1, bullPx), (bear, -1, bearPx)):
            ks = np.flatnonzero(arr > 0)
            if len(ks):
                s_ = min(100, round(arr.max() + 10 * (len(ks) - 1)))
                if best is None or s_ > best[1]:
                    best = (d, s_, px, "+".join(TYPES[k] for k in ks), len(ks))
        if best and best[1] >= P["minStrength"] and best[4] >= P["minModes"]:
            out.append((i, *best))
    E = pd.DataFrame(out, columns=["i", "dir", "strength", "price", "types", "modes"])
    return E, dict(h=h, l=l, c=c, atr=atr)


def sym(i, d, X, k=1.0, maxb=30):
    """Ab Schluss der Signal-Kerze: zuerst +k·ATR in Richtung d (1) oder −k·ATR (0)? Zufall = 50 %."""
    a = X["atr"][i]
    if not np.isfinite(a) or a <= 0:
        return np.nan
    e = X["c"][i]
    for j in range(i + 1, min(i + 1 + maxb, len(X["h"]))):
        up = X["h"][j] >= e + k * a; dn = X["l"][j] <= e - k * a
        if up and dn:
            return np.nan
        if up or dn:
            return 1.0 if (up and d > 0) or (dn and d < 0) else 0.0
    return np.nan


def outcome(i, d, px, X, P):
    a = X["atr"][i]
    if not np.isfinite(a) or a <= 0:
        return None
    ext = min(px, X["l"][i]) if d > 0 else max(px, X["h"][i])
    for k in range(i + 1, min(i + 1 + P["maxBars"], len(X["h"]))):
        fail = X["l"][k] <= ext - P["failAtr"] * a if d > 0 else X["h"][k] >= ext + P["failAtr"] * a
        held = X["h"][k] >= ext + P["heldAtr"] * a if d > 0 else X["l"][k] <= ext - P["heldAtr"] * a
        if fail:
            return "FAILED"
        if held:
            return "HELD"
    return "EXPIRED"


if __name__ == "__main__":
    sess = load_sessions(); days = sorted(sess)[-20:]
    allE, rand = [], []
    for d in days:
        B, rows = bars_from_trades(sess[d])
        E, X = evaluate_all(B, rows, P)
        E["session"] = d
        tt = pd.to_datetime(B["t0"].to_numpy()[E["i"]], unit="ms", utc=True).tz_convert(NY)
        E["hour"] = tt.hour; mins = tt.hour * 60 + tt.minute; E["rth"] = (mins >= 570) & (mins < 960)
        E["outcome"] = [outcome(i, dd, px, X, P) for i, dd, px in zip(E["i"], E["dir"], E["price"])]
        E["sym"] = [sym(i, dd, X) for i, dd in zip(E["i"], E["dir"])]
        # Zufall: gleiche Anzahl Kerzen derselben Stunde, gleiche Richtungen, Extrem = Tief (long) / Hoch (short) der Kerze
        hrs = pd.to_datetime(B["t0"], unit="ms", utc=True).dt.tz_convert(NY).dt.hour.to_numpy()
        for _ in range(20):
            for (hr, dd) in zip(E["hour"], E["dir"]):
                cand = np.flatnonzero(hrs == hr); j = int(rng_.choice(cand))
                rand.append((outcome(j, dd, X["l"][j] if dd > 0 else X["h"][j], X, P), sym(j, dd, X)))
        allE.append(E)
        print(d, len(E), flush=True)
    E = pd.concat(allE, ignore_index=True)
    E.to_csv(OUT / f"calib_events{TAG}.csv", index=False)
    nd = len(days); RR = pd.DataFrame(rand, columns=["o", "s"]); R = RR["o"]
    L = [f"# Absorption Engine – Eichung auf NQ 1m ({days[0]} … {days[-1]}, {nd} Tage, Databento trades; REFILL nicht prüfbar)\n",
         f"Ereignisse gesamt {len(E)} · pro Tag {len(E) / nd:.1f} · RTH pro Tag {E['rth'].sum() / nd:.1f} · Overnight pro Tag {(~E['rth']).sum() / nd:.1f}\n"]
    ty = pd.Series([t for x in E["types"] for t in x.split("+")]).value_counts()
    L.append("Arten (Anzahl, ein Ereignis kann mehrere haben):\n\n" + (ty / nd).round(1).rename("pro Tag").to_frame().to_markdown() + "\n")
    oc = E["outcome"].value_counts(normalize=True).mul(100).round(1)
    L.append(f"Ergebnis Engine: HELD {oc.get('HELD', 0)} % · FAILED {oc.get('FAILED', 0)} % · EXPIRED {oc.get('EXPIRED', 0)} %")
    rc = R.value_counts(normalize=True).mul(100).round(1)
    L.append(f"Zufall (gleiche Stunde/Richtung, 20×): HELD {rc.get('HELD', 0)} % · FAILED {rc.get('FAILED', 0)} % · EXPIRED {rc.get('EXPIRED', 0)} %")
    L.append(f"Fairer Test – zuerst ±1 ATR ab Schluss in Absorptions-Richtung: Engine {100 * E['sym'].mean():.1f} % (n {E['sym'].notna().sum()}), Zufall {100 * RR['s'].mean():.1f} %\n")
    rows = []
    for t in TYPES:
        m = E["types"].str.contains(t)
        if m.sum() >= 20:
            o = E.loc[m, "outcome"].value_counts(normalize=True).mul(100)
            rows.append({"Art": t, "Ereignisse": int(m.sum()), "pro RTH-Tag": round((m & E["rth"]).sum() / nd, 1),
                         "HELD %": round(o.get("HELD", 0), 1), "FAILED %": round(o.get("FAILED", 0), 1),
                         "±1 ATR richtig %": round(100 * E.loc[m, "sym"].mean(), 1)})
    for mm in (1, 2, 3, 4):
        m = (E["modes"] >= mm) if mm == 4 else (E["modes"] == mm)
        if m.sum():
            o = E.loc[m, "outcome"].value_counts(normalize=True).mul(100)
            rows.append({"Art": f"{mm}{'+' if mm == 4 else ''}/10 Modi", "Ereignisse": int(m.sum()), "pro RTH-Tag": round((m & E["rth"]).sum() / nd, 1),
                         "HELD %": round(o.get("HELD", 0), 1), "FAILED %": round(o.get("FAILED", 0), 1),
                         "±1 ATR richtig %": round(100 * E.loc[m, "sym"].mean(), 1)})
    for lo_, hi_ in ((40, 60), (60, 80), (80, 101)):
        m = (E["strength"] >= lo_) & (E["strength"] < hi_)
        if m.sum():
            o = E.loc[m, "outcome"].value_counts(normalize=True).mul(100)
            rows.append({"Art": f"Stärke {lo_}–{hi_ - 1}", "Ereignisse": int(m.sum()), "pro RTH-Tag": round((m & E["rth"]).sum() / nd, 1),
                         "HELD %": round(o.get("HELD", 0), 1), "FAILED %": round(o.get("FAILED", 0), 1),
                         "±1 ATR richtig %": round(100 * E.loc[m, "sym"].mean(), 1)})
    L.append(pd.DataFrame(rows).to_markdown(index=False))
    L.insert(1, "Parameter: " + json.dumps(P) + "\n")
    (OUT / f"eichung{TAG}.md").write_text("\n".join(L))
    print("\n".join(L))
