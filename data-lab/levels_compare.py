"""
Level-Formeln im Vergleich: Reagiert der Preis an diesen Levels besser als an Kontroll-Levels derselben Familie?

Familien (alle nur Berührungen in New York 09:30–16:00, erste Berührung je Level und Tag):
  Gotham IV   18:00-Open ± k·σ(IV)                      k = 0,5/1/1,5/2         Kontrolle 0,25/0,75/1,25/1,75/2,25
  ATR ab Open RTH-Open ± k·ATR14 (Tagesranges)          k = 0,5/1               Kontrolle 0,25/0,75/1,25
  Camarilla   Vortag-RTH: C ± (H−L)·1,1/12·{1,2,3,6}    R1–R4 / S1–S4           Kontrolle {0,5;1,5;2,5;4,5;7,5}
  ORB 15m     OR-Hoch + k·OR, OR-Tief − k·OR            k = 0,5/1/1,5/2         Kontrolle 0,25/0,75/1,25/1,75/2,25
  IB 60m      wie ORB, IB 09:30–10:30                    k = 0,5/1/1,5/2         Kontrolle wie ORB
  VWAP-Bänder VWAP ab 09:30 ± k·σ (volumengewichtet)    k = 1/2/3               Kontrolle 0,5/1,5/2,5/3,5
  Bollinger   5m-Schlusskurse, SMA20 ± k·σ20            k = 2                   Kontrolle 1,5/2,5
Wandernde Bänder (VWAP, Bollinger): Wert der Vorkerze, kein Blick in die Zukunft.

Reaktion: Nach der Berührung ein Rennen. „Abprall“ = Preis kommt zuerst r vom Level zurück (ab der Kerze NACH der
Berührung), „Durchbruch“ = Preis geht zuerst r durch das Level (die Berührungskerze zählt mit). r = 0,15·ATR14
(≈ 0,25σ) und zur Kontrolle r = 0,06·ATR14 (≈ 0,1σ). Gleiche Distanz in beide Richtungen → 50 % = Münzwurf.
Fair: jedes Level gegen den Schnitt seiner direkten Kontroll-Nachbarn (gleiche Familie, gleicher Abstand ±).

Aufruf: python data-lab/levels_compare.py   → results/levels_compare.md (+ .csv, _touches.csv.gz)
"""
import glob
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
MARKETS = ["NQ", "ES", "RTY", "GC"]
NCOL = 1380
RS, RE = 930, 1320            # 09:30, 16:00 (Minuten seit 18:00)
RACES = {"0,15 ATR": 0.15, "0,06 ATR": 0.06}
IV_DIR = HERE / "data/iv"

FAM = {  # Familie: (Levels, Kontrollen, Nachbarn je Level)
    "Gotham IV": ([0.5, 1, 1.5, 2], [0.25, 0.75, 1.25, 1.75, 2.25]),
    "ATR ab Open": ([0.5, 1], [0.25, 0.75, 1.25]),
    "Camarilla": ([1, 2, 3, 6], [0.5, 1.5, 2.5, 4.5, 7.5]),
    "ORB 15m": ([0.5, 1, 1.5, 2], [0.25, 0.75, 1.25, 1.75, 2.25]),
    "IB 60m": ([0.5, 1, 1.5, 2], [0.25, 0.75, 1.25, 1.75, 2.25]),
    "VWAP-Bänder": ([1, 2, 3], [0.5, 1.5, 2.5, 3.5]),
    "Bollinger 5m": ([2], [1.5, 2.5]),
}
CAM_NAME = {1: "R1/S1", 2: "R2/S2", 3: "R3/S3", 6: "R4/S4"}


def load_iv(name):
    df = pd.read_csv(IV_DIR / f"{name}_History.csv")
    df.columns = [c.strip().upper() for c in df.columns]
    col = "CLOSE" if "CLOSE" in df.columns else name
    df["DATE"] = pd.to_datetime(df["DATE"]).astype("datetime64[ns]")
    return df.set_index("DATE")[col].astype(float).rename(name)


def iv_series(mk):
    IV = pd.concat([load_iv(n) for n in ["VIX", "VXN", "VIX1D", "RVX", "GVZ"]], axis=1, sort=True)
    return {"NQ": IV["VIX1D"] * IV["VXN"] / IV["VIX"], "ES": IV["VIX1D"], "RTY": IV["VIX1D"] * IV["RVX"] / IV["VIX"], "GC": IV["GVZ"]}[mk]


def load(mk):
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) >= pd.Timestamp("2011-01-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["open", "high", "low", "close", "volume"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy(float)[keep]; G[k] = a
    G["cff"] = pd.DataFrame(G["close"]).ffill(axis=1).to_numpy()
    first_ts = df.groupby("session_date")["ts_et"].first().reindex(days)
    anchor_day = pd.to_datetime(first_ts.dt.tz_localize(None).dt.date.values).astype("datetime64[ns]")
    return dts, G, anchor_day


def first_true(mask):
    idx = np.argmax(mask, axis=1).astype(float)
    idx[~mask.any(axis=1)] = np.inf
    return idx


def race(H, L, d, t, z, sgn, r):
    """1 = Abprall (zuerst r zurück, ab t+1), 0 = Durchbruch (zuerst r durch, ab t), nan = offen."""
    thru = (H[d, t:] >= z + r) if sgn == 1 else (L[d, t:] <= z - r)
    away = (L[d, t + 1:] <= z - r) if sgn == 1 else (H[d, t + 1:] >= z + r)
    ib = np.argmax(thru) if thru.any() else np.inf
    ia = 1 + np.argmax(away) if away.any() else np.inf
    if not (np.isfinite(ia) or np.isfinite(ib)):
        return np.nan
    return 1.0 if ia < ib else 0.0


def run(mk):
    dts, G, anchor_day = load(mk)
    H, L, C, O, V, CF = G["high"], G["low"], G["close"], G["open"], G["volume"], G["cff"]
    nd = len(dts)
    with np.errstate(all="ignore"):
        DR = np.nanmax(H, 1) - np.nanmin(L, 1)
        rH, rL = np.nanmax(H[:, RS:RE], 1), np.nanmin(L[:, RS:RE], 1)
    rC = CF[:, RE - 1]
    valid = (np.isfinite(H[:, RS:RE]).mean(1) >= 0.9) & (dts.weekday < 5) & (np.isfinite(H).mean(1) >= 0.6)
    atr = pd.Series(np.where(valid, DR, np.nan)).rolling(14, min_periods=10).mean().shift(1).to_numpy()
    gap = np.r_[False, np.diff(dts.values).astype("timedelta64[D]").astype(int) <= 4]
    pH, pL, pC = [np.where(gap & np.r_[False, valid[:-1]], np.r_[np.nan, x[:-1]], np.nan) for x in (rH, rL, rC)]
    ok = valid & np.isfinite(atr) & (atr > 0)

    # IV-σ (Gotham): Schlusskurs des Vortags vor dem Anker, max. 5 Tage alt
    ivs = iv_series(mk).dropna()
    left = pd.DataFrame({"a": anchor_day, "i": np.arange(nd)}).sort_values("a")
    m = pd.merge_asof(left, pd.DataFrame({"d": ivs.index, "v": ivs.values}).sort_values("d"), left_on="a", right_on="d",
                      direction="backward").sort_values("i")
    ivv = np.where((m["a"] - m["d"]).dt.days.to_numpy() > 5, np.nan, m["v"].to_numpy())
    ref18 = O[:, 0]
    sig = ref18 * ivv / 100 / np.sqrt(252)

    rows = []

    def fixed(fam, base_up, base_dn, unit, ks, start, label=lambda k: k):
        """Feste Levels: oben base_up + k·unit, unten base_dn − k·unit; Seite = Lage zum Preis beim Start."""
        lv, ct = FAM[fam]
        for k in sorted(set(lv) | set(ct)):
            art = "Level" if k in lv else "Kontrolle"
            for sgn_lvl, z in ((1, base_up + k * unit), (-1, base_dn - k * unit)):
                px = CF[:, start - 1]
                good = ok & np.isfinite(z) & np.isfinite(px) & (z != px)
                side = np.where(z > px, 1, -1)
                touch = np.where(side[:, None] == 1, H[:, start:RE] >= z[:, None], L[:, start:RE] <= z[:, None])
                t0 = first_true(touch & good[:, None])
                for d in np.flatnonzero(np.isfinite(t0)):
                    t = start + int(t0[d])
                    res = {rn: race(H, L, d, t, z[d], side[d], f * atr[d]) for rn, f in RACES.items()}
                    rows.append((mk, dts[d], fam, sgn_lvl * k, art, side[d], t, *res.values()))

    def dynamic(fam, mid, sd, ks, start):
        """Wandernde Bänder: Wert der Vorkerze; oben Berührung mit Hoch, unten mit Tief."""
        lv, ct = FAM[fam]
        for k in sorted(set(lv) | set(ct)):
            art = "Level" if k in lv else "Kontrolle"
            for sgn in (1, -1):
                band = mid + sgn * k * sd                          # Wert bis Kerze t (inkl.)
                prev = np.full_like(band, np.nan); prev[:, 1:] = band[:, :-1]
                seg = prev[:, start:RE]
                touch = (H[:, start:RE] >= seg) if sgn == 1 else (L[:, start:RE] <= seg)
                t0 = first_true(touch & ok[:, None] & np.isfinite(seg))
                for d in np.flatnonzero(np.isfinite(t0)):
                    t = start + int(t0[d]); z = prev[d, t]
                    res = {rn: race(H, L, d, t, z, sgn, f * atr[d]) for rn, f in RACES.items()}
                    rows.append((mk, dts[d], fam, sgn * k, art, sgn, t, *res.values()))

    fixed("Gotham IV", ref18, ref18, sig, None, RS)
    ro = O[:, RS]
    fixed("ATR ab Open", ro, ro, atr, None, RS + 1)
    u = (pH - pL) * 1.1 / 12
    fixed("Camarilla", pC, pC, u, None, RS)
    with np.errstate(all="ignore"):
        oH, oL = np.nanmax(H[:, RS:RS + 15], 1), np.nanmin(L[:, RS:RS + 15], 1)
        iH, iL = np.nanmax(H[:, RS:RS + 60], 1), np.nanmin(L[:, RS:RS + 60], 1)
    fixed("ORB 15m", oH, oL, oH - oL, None, RS + 15)
    fixed("IB 60m", iH, iL, iH - iL, None, RS + 60)

    # VWAP ab 09:30 mit volumengewichteter Standardabweichung
    tp = (H + L + C) / 3
    v = np.where(np.isfinite(V) & np.isfinite(tp), V, 0.0); p = np.nan_to_num(tp)
    cv = np.zeros_like(v); cpv = np.zeros_like(v); cp2v = np.zeros_like(v)
    cv[:, RS:] = np.cumsum(v[:, RS:], 1); cpv[:, RS:] = np.cumsum((p * v)[:, RS:], 1); cp2v[:, RS:] = np.cumsum((p * p * v)[:, RS:], 1)
    with np.errstate(all="ignore"):
        vw = cpv / cv
        vsd = np.sqrt(np.maximum(cp2v / cv - vw ** 2, 0))
    vw[:, :RS] = np.nan; vsd[:, :RS] = np.nan
    dynamic("VWAP-Bänder", vw, vsd, None, RS + 15)

    # Bollinger(20, 2) auf 5-Minuten-Schlusskursen, gilt ab der Folgekerze des fertigen 5m-Bars
    c5 = CF[:, 4::5]
    s5 = pd.DataFrame(c5.T)
    ma = s5.rolling(20).mean().to_numpy().T; sd5 = s5.rolling(20).std(ddof=0).to_numpy().T
    bm = np.full((nd, NCOL), np.nan); bs = np.full((nd, NCOL), np.nan)
    j = np.arange(NCOL) // 5 - 1                                 # letzter fertiger 5m-Bar vor Kerze t (Wert gilt ab t)
    jj = np.clip(j, 0, c5.shape[1] - 1)
    # dynamic() nimmt den Wert der Vorkerze → hier schon um 1 Kerze nach vorn schieben
    bm[:, :-1] = np.where(j >= 0, ma[:, jj], np.nan)[:, 1:]; bs[:, :-1] = np.where(j >= 0, sd5[:, jj], np.nan)[:, 1:]
    dynamic("Bollinger 5m", bm, bs, None, RS + 15)

    print(mk, "fertig", len(rows), flush=True)
    return rows


def ztest(a1, n1, a2, n2):
    if min(n1, n2) < 20:
        return np.nan
    p = (a1 + a2) / (n1 + n2); se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return np.nan
    from math import erf, sqrt
    z = (a1 / n1 - a2 / n2) / se
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


if __name__ == "__main__":
    with Pool(4) as pool:
        out = pool.map(run, MARKETS)
    T = pd.DataFrame([r for o in out for r in o], columns=["Markt", "Tag", "Familie", "k", "Art", "Seite", "Minute", *RACES])
    T.to_csv(HERE / "results/levels_compare_touches.csv.gz", index=False)
    end = T["Tag"].max()
    PER = {"3J": T["Tag"] > end - pd.DateOffset(years=3), "Alles": pd.Series(True, index=T.index)}

    rows, summ = [], []
    for pn, pm in PER.items():
        for rn in RACES:
            X = T[pm & T[rn].notna()]
            for (mk, fam), g in X.groupby(["Markt", "Familie"]):
                lv, ct = FAM[fam]
                g = g.assign(absk=g["k"].abs())
                st = g.groupby("absk")[rn].agg(["sum", "count"])
                la, ln_, nbs, dsum = 0, 0, set(), 0.0
                for k in lv:
                    if k not in st.index:
                        continue
                    lo = max([x for x in ct if x < k], default=None); hi = min([x for x in ct if x > k], default=None)
                    nb = [c for c in (lo, hi) if c is not None and c in st.index]
                    if not nb:
                        continue
                    a, n = st.loc[k, "sum"], st.loc[k, "count"]
                    na, nn = st.loc[nb, "sum"].sum(), st.loc[nb, "count"].sum()
                    nrate = np.mean([st.loc[c, "sum"] / st.loc[c, "count"] for c in nb])
                    name = CAM_NAME.get(k, f"±{k:g}") if fam == "Camarilla" else f"±{k:g}"
                    rows.append(dict(Zeitraum=pn, Rennen=rn, Markt=mk, Familie=fam, Level=name, Berührungen=int(n),
                                     **{"Abprall Level %": round(100 * a / n, 1), "Abprall Nachbarn %": round(100 * nrate, 1),
                                        "Differenz Pkt": round(100 * (a / n - nrate), 1), "p-Wert": round(ztest(a, n, na, nn), 3)}))
                    la += a; ln_ += n; nbs |= set(nb); dsum += n * (a / n - nrate)
                if ln_ and nbs:
                    ca, cn = st.loc[sorted(nbs), "sum"].sum(), st.loc[sorted(nbs), "count"].sum()
                    summ.append(dict(Zeitraum=pn, Rennen=rn, Markt=mk, Familie=fam, **{
                        "Berührungen Level": int(ln_), "Abprall Level %": round(100 * la / ln_, 1),
                        "Berührungen Kontrolle": int(cn), "Abprall Kontrolle %": round(100 * ca / cn, 1),
                        "Differenz fair Pkt": round(100 * dsum / ln_, 1), "p-Wert": round(ztest(la, ln_, ca, cn), 3)}))
    R, S = pd.DataFrame(rows), pd.DataFrame(summ)
    R.to_csv(HERE / "results/levels_compare.csv", index=False)
    S.to_csv(HERE / "results/levels_compare_summary.csv", index=False)

    main = S[(S["Zeitraum"] == "3J") & (S["Rennen"] == "0,15 ATR")]
    n_tests = len(S[(S["Rennen"] == "0,15 ATR") & (S["Zeitraum"] == "3J")])
    md = ["# Level-Formeln im Vergleich: Reagiert der Preis dort besser als an Kontroll-Levels?", "",
          "Nur Berührungen in New York 09:30–16:00, erste Berührung je Level und Tag. Rennen: zuerst r zurück (Abprall) oder r durch "
          "(Durchbruch), r = 0,15·ATR14 ≈ 0,25σ. 50 % = Münzwurf. **Entscheidend ist die Differenz zu den Kontroll-Levels derselben Familie** "
          "(gleiche Formel, Faktor dazwischen) – nicht die Abprallquote allein.", "",
          f"Mehrfach-Test-Hinweis: {n_tests} Familien-Vergleiche je Zeitraum. Bei 5 % Signifikanz sind ca. {n_tests * 0.05:.0f} Zufallstreffer zu erwarten; "
          f"streng (Bonferroni) gilt erst p < {0.05 / n_tests:.4f}.", "",
          "## 1) Zusammenfassung je Familie (letzte 3 Jahre, r = 0,15 ATR)", "",
          main.drop(columns=["Zeitraum", "Rennen"]).sort_values(["Familie", "Markt"]).to_markdown(index=False), "",
          "## 2) Stabilität: seit 2011, r = 0,15 ATR (Gotham IV nur mit 1D-IV, also erst ab 2022; GC mit GVZ 30D)", "",
          S[(S["Zeitraum"] == "Alles") & (S["Rennen"] == "0,15 ATR")].drop(columns=["Zeitraum", "Rennen"]).sort_values(["Familie", "Markt"]).to_markdown(index=False), "",
          "## 3) Engeres Rennen r = 0,06 ATR ≈ 0,1σ (letzte 3 Jahre)", "",
          S[(S["Zeitraum"] == "3J") & (S["Rennen"] == "0,06 ATR")].drop(columns=["Zeitraum", "Rennen"]).sort_values(["Familie", "Markt"]).to_markdown(index=False), "",
          "## 4) Je Level (letzte 3 Jahre, r = 0,15 ATR)", "",
          R[(R["Zeitraum"] == "3J") & (R["Rennen"] == "0,15 ATR")].drop(columns=["Zeitraum", "Rennen"]).sort_values(["Familie", "Markt"]).to_markdown(index=False), ""]
    (HERE / "results/levels_compare.md").write_text("\n".join(md))
    print("\n".join(md[:12]))
