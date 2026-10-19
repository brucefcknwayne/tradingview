"""
HAR-Bänder vs. IV-Bänder (Gotham) – welches σ passt am besten zur echten Tagesbewegung?

Tages-Varianz (Session 18:00–17:00, wie die CME-Tageskerze in TradingView) nach Garman-Klass:
  GK = 0,5·ln(H/L)² − (2·ln2 − 1)·ln(C/O)²
log-HAR: log GK_t = b0 + b1·log GK_{t−1} + b2·log Ø GK_{t−5..t−1} + b3·log Ø GK_{t−22..t−1} [+ b4·log(Wert/100)²/252]
σ_t = √(exp(Vorhersage + s²/2)) · Open_t  (s² = Rest-Varianz, Lognormal-Korrektur)

Modelle: IV 1D/9D/30D (wie Indikator, roh), HAR, HAR+9D (bzw. HAR+GVZ bei GC), HAR+1D (ab Mai 2022).
Anpassung nur auf Explore (bis 2024), Bewertung auf Validate (2025 – 2026-04-16). Holdout unberührt.
Kriterien: Schluss in ±1σ (Soll 68,3 %), in ±2σ (Soll 95,4 %), Median Range/σ (Soll ≈ 1,50), Fehler (QLIKE auf GK).

Aufruf: python research/har_bands.py → research/results/har_bands.md, har_coefs.json
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import MARKETS, RES, load_market  # noqa: E402

LN2 = 2 * np.log(2) - 1


def ols(X, y):
    X1 = np.c_[np.ones(len(X)), X]
    b, *_ = np.linalg.lstsq(X1, y, rcond=None)
    res = y - X1 @ b
    return b, res.var(ddof=X1.shape[1])


rows, coefs = [], {}
for mk in MARKETS:
    M = load_market(mk)
    O, H, L, C = M["ref"], M["H"], M["L"], M["C"]
    ok = M["valid"] & np.isfinite(O) & np.isfinite(H) & np.isfinite(L) & np.isfinite(C) & (L > 0)
    with np.errstate(all="ignore"):
        gk = 0.5 * np.log(H / L) ** 2 - LN2 * np.log(C / O) ** 2
    gk = np.where(ok & (gk > 1e-10), gk, np.nan)
    s = pd.Series(gk)
    lag1 = s.shift(1); m5 = s.shift(1).rolling(5, min_periods=4).mean(); m22 = s.shift(1).rolling(22, min_periods=18).mean()
    feats = {"x1": np.log(lag1), "x5": np.log(m5), "x22": np.log(m22)}
    ivv = {m: (M["sig"][m] / O) ** 2 for m in M["sig"]}                 # (Wert/100)²/252 je Modus
    y = np.log(s)
    expl = M["period"] == "Explore"; val = M["period"] == "Validate"
    ret = (C - O) / O
    rng = (H - L) / O

    def evaluate(name, sig_frac, per_mask):
        mm = per_mask & ok & np.isfinite(sig_frac) & (sig_frac > 0)
        if mm.sum() < 60:
            return
        z = ret[mm] / sig_frac[mm]
        q = gk[mm] / sig_frac[mm] ** 2
        rows.append(dict(Markt=mk, Modell=name, Zeitraum="Explore" if per_mask is expl else "Validate", Tage=int(mm.sum()),
                         **{"Schluss in ±1σ %": round(100 * np.mean(np.abs(z) <= 1), 1), "Schluss in ±2σ %": round(100 * np.mean(np.abs(z) <= 2), 1),
                            "Median Range/σ": round(np.median(rng[mm] / sig_frac[mm]), 2),
                            "QLIKE": round(np.nanmean(q - np.log(q) - 1), 4)}))

    # IV roh (wie Indikator)
    for m, v in ivv.items():
        for per in (expl, val):
            evaluate(f"IV {m}", np.sqrt(v), per)
    # HAR-Varianten
    specs = {"HAR": []}
    if "9D" in ivv:
        specs["HAR+9D"] = ["9D"]
    if "GVZ" in ivv:
        specs["HAR+GVZ"] = ["GVZ"]
    if "1D" in ivv:
        specs["HAR+1D"] = ["1D"]
    for name, ivs in specs.items():
        Xall = np.c_[feats["x1"], feats["x5"], feats["x22"]] if True else None
        for m in ivs:
            Xall = np.c_[Xall, np.log(ivv[m])]
        fit = expl & np.all(np.isfinite(Xall), 1) & np.isfinite(y)
        if fit.sum() < 200:
            continue
        b, s2 = ols(Xall[fit], y[fit])
        pred = np.full(len(y), np.nan)
        good = np.all(np.isfinite(Xall), 1)
        pred[good] = np.c_[np.ones(good.sum()), Xall[good]] @ b
        sig_frac = np.sqrt(np.exp(pred + s2 / 2))
        for per in (expl, val):
            evaluate(name, sig_frac, per)
        coefs.setdefault(mk, {})[name] = {"b": [round(float(x), 6) for x in b], "s2": round(float(s2), 6), "Tage_fit": int(fit.sum()),
                                           "Explore_von": str(M["days"][fit][0]), "Explore_bis": str(M["days"][fit][-1])}
    print(mk, "fertig", flush=True)

R = pd.DataFrame(rows)
R["Abweichung ±1σ (Pkt)"] = (R["Schluss in ±1σ %"] - 68.3).round(1)
R.to_csv(RES / "har_bands.csv", index=False)
(RES / "har_coefs.json").write_text(json.dumps(coefs, indent=1))
V = R[R["Zeitraum"] == "Validate"].sort_values(["Markt", "QLIKE"])
md = ["# HAR-Bänder vs. IV-Bänder (Gotham)", "",
      "Soll: Schluss in ±1σ = 68,3 %, in ±2σ = 95,4 %, Median Range/σ ≈ 1,50. QLIKE: kleiner = bessere σ-Prognose.",
      "HAR-Gewichte nur auf Explore (bis 2024) geschätzt, Bewertung auf Validate (2025 – 04/2026).", "",
      "## Validate (ungesehen)", "", V.to_markdown(index=False), "", "## Explore (Anpassungszeitraum)", "",
      R[R["Zeitraum"] == "Explore"].sort_values(["Markt", "QLIKE"]).to_markdown(index=False), "",
      "## Gewichte", "", "```json", json.dumps(coefs, indent=1), "```"]
(RES / "har_bands.md").write_text("\n".join(md))
pd.set_option("display.width", 200)
print(V.to_string(index=False))
