"""
Projekt ib-first: „Tief zuerst → Hoch wird geholt“ (und umgekehrt) – Wahrscheinlichkeiten für den Pine-Indikator.

Je Markt (NQ, ES, RTY, GC) × Startzeit (25) × IB-Länge (15/30/45/60) × Erstes Extrem (Tief zuerst / Hoch zuerst),
gemessen auf 1m-Bars, letzte 3 Jahre bis zum letzten Datentag, Tagesende 17:00 für IBs vor 09:30, sonst 16:00:
  Gegenseite  = das andere IB-Extrem wird bis Tagesende geholt (Tief zuerst → IB-Hoch überschritten)
  +0,5 IB     = Ausdehnung über die Gegenseite um mindestens 0,5 IB-Range
  +1 IB       = … um mindestens 1 IB-Range
  Erstseite   = das zuerst gebildete Extrem wird noch einmal gebrochen
Prüfung (3 Jahre davor → ungesehenes letztes Jahr): data-lab/ib_first_side.py → results/ib_first_side.md.

Ausgabe: ib-first/IB-First.pine (aus ib-first/IB-First_template.pine), je Markt eine Datenzeile:
  25 Starts × 4 Längen × 2 (Tief zuerst, Hoch zuerst) × 4 Werte, je Wert 2 Ziffern (Prozent 00–99, „--“ = keine Daten).

Aufruf: python data-lab/ib_first_build.py
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
MIN_DAYS = 40


def rel(hhmm):
    h, m = map(int, hhmm.split(":"))
    return (h * 60 + m - 1080) % 1440


def enc(x):
    return "--" if not np.isfinite(x) else f"{min(int(round(100 * x)), 99):02d}"


data, check, end = {}, [], None
for mk in MARKETS:
    df = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob(str(HERE / f"data/{mk.lower()}_1m/*.parquet"))))
    df = df[pd.to_datetime(df["session_date"]) > pd.Timestamp("2022-06-01")]
    mm = ((df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute).to_numpy() - 1080) % 1440
    keep = mm < NCOL
    days = np.array(sorted(df["session_date"].unique())); dts = pd.to_datetime(days)
    di = pd.Categorical(df["session_date"], categories=days).codes
    G = {}
    for k in ["high", "low"]:
        a = np.full((len(days), NCOL), np.nan); a[di[keep], mm[keep]] = df[k].to_numpy()[keep]; G[k] = a
    end = dts.max()
    per = np.asarray(dts > end - pd.DateOffset(years=YEARS))
    out = []
    for st in STARTS:
        s = rel(st); e = NCOL if s < rel("09:30") else rel("16:00")
        for L in LENGTHS:
            vals = [np.nan] * 8
            if s + L <= e - 30:
                Hw, Lw = G["high"][:, s:s + L], G["low"][:, s:s + L]
                with np.errstate(all="ignore"):
                    H, Lo = np.nanmax(Hw, 1), np.nanmin(Lw, 1)
                R = H - Lo
                v = (np.isfinite(Hw).mean(1) >= 0.8) & (R > 0) & (dts.weekday < 5) & np.isfinite(G["high"][:, e - 30:e]).any(1) & per
                iH = np.argmax(np.nan_to_num(Hw, nan=-np.inf), 1); iL = np.argmin(np.nan_to_num(Lw, nan=np.inf), 1)
                with np.errstate(all="ignore"):
                    mx, mn = np.nanmax(G["high"][:, s + L:e], 1), np.nanmin(G["low"][:, s + L:e], 1)
                for f, m in enumerate([v & (iL < iH), v & (iH < iL)]):       # 0 Tief zuerst, 1 Hoch zuerst
                    if m.sum() < MIN_DAYS:
                        continue
                    if f == 0:
                        opp, ext, same = mx[m] > H[m], (mx[m] - H[m]) / R[m], mn[m] < Lo[m]
                    else:
                        opp, ext, same = mn[m] < Lo[m], (Lo[m] - mn[m]) / R[m], mx[m] > H[m]
                    vals[f * 4:f * 4 + 4] = [opp.mean(), (ext >= 0.5).mean(), (ext >= 1.0).mean(), same.mean()]
                    check.append(dict(Markt=mk, Start=st, IB=L, Erstes=["Tief zuerst", "Hoch zuerst"][f], Tage=int(m.sum()),
                                      Gegenseite=round(100 * opp.mean()), Ext05=round(100 * (ext >= 0.5).mean()),
                                      Ext10=round(100 * (ext >= 1.0).mean()), Erstseite=round(100 * same.mean())))
            out.append("".join(enc(x) for x in vals))
    data[mk] = "".join(out)
    assert len(data[mk]) == len(STARTS) * len(LENGTHS) * 16
    print(mk, "fertig", flush=True)

tpl = (ROOT / "ib-first/IB-First_template.pine").read_text()
loads = "\n".join(f'D := barstate.isfirst and mk == "{mk}" ? "{data[mk]}" : D' for mk in MARKETS)
pine = (tpl.replace("{{LOADS}}", loads).replace("{{KEYS}}", " ".join(STARTS))
           .replace("{{YEARS}}", str(YEARS)).replace("{{END}}", str(end.date())))
assert "{{" not in pine
(ROOT / "ib-first/IB-First.pine").write_text(pine)
C = pd.DataFrame(check)
(HERE / "results/ib_first_build.md").write_text(
    "# IB-First – Werte im Indikator (letzte 3 Jahre, %)\n\n" + C.to_markdown(index=False) + "\n")
print("Indikator:", len(pine.splitlines()), "Zeilen,", len(pine), "Zeichen")
print(C[C["Start"] == "09:30"].to_string(index=False))
