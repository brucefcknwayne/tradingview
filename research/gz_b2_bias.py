"""
H7 Teil B, Runde 2 (nur Explore): Zonen = Ort, Richtung kommt aus einem belegten Bias.
Biases: Seite (Long/Short, Index-Drift), Trend (Schluss über/unter 20-Tage-Schnitt, TSMOM), Turn-of-Month (letzter + erste 3 Handelstage).
Zusätzliche Vorlage „fadeC“: Einstieg am Level, Stop 0,25σ, Ausstieg zum Session-Schluss (16:59) – nimmt Drift + Rücklauf mit.

Aufruf: python research/gz_b2_bias.py → research/results/gz_b2_bias.csv / .md
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from gz_common import COST, NCOL, TICK, load_market, MARKETS  # noqa: E402
from gz_b_events import sim_all  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "research/results"
rows = []
for mk in MARKETS:
    E = pd.read_parquet(ROOT / f"data-lab/data/raw/gz_cache/gz_b_events_{mk}.parquet")
    E = E[E["Zeitraum"] == "Explore"].reset_index(drop=True)
    M = load_market(mk)
    days = pd.Index(M["days"])
    # Tages-Bias (nur Vortage bekannt)
    cl = pd.Series(M["C"], index=days)
    ma20 = cl.rolling(20, min_periods=15).mean()
    trend_up = (cl > ma20).shift(1)                         # Vortag über 20-Tage-Schnitt
    d = pd.to_datetime(days); mon = d.to_period("M")
    pos = pd.Series(np.arange(len(d)), index=days).groupby(mon).rank(method="first").to_numpy()
    cnt = pd.Series(1, index=days).groupby(mon).transform("size").to_numpy()
    tom = (pos <= 3) | (pos == cnt)
    di = days.get_indexer(E["Tag"])
    E["trend_up"] = trend_up.to_numpy()[di]; E["tom"] = tom[di]
    # fadeC: Stop 0,25σ, Ausstieg Session-Schluss
    sig = np.array([M["sig"][m][i] for m, i in zip(E["Modus"], di)])
    z = M["ref"][di] + E["Seite"].to_numpy() * E["k"].to_numpy() * sig
    r, _ = sim_all(M["G"]["high"], M["G"]["low"], M["G"]["close"], di.astype(np.int64), E["t"].to_numpy(np.int64), z,
                   (-E["Seite"]).to_numpy(np.int64), 0.25 * sig, 1e9 * np.ones(len(E)), NCOL - 1)
    E["fadeC"] = (r - COST[mk]) / (0.25 * sig)
    long_ = E["Seite"] == -1                                   # Fade an unterer Zone = Long
    conds = {
        "Long (untere Zone)": long_, "Short (obere Zone)": ~long_,
        "Long + Trend auf": long_ & (E["trend_up"] == True), "Short + Trend ab": ~long_ & (E["trend_up"] == False),  # noqa: E712
        "Long + Trend ab": long_ & (E["trend_up"] == False), "Short + Trend auf": ~long_ & (E["trend_up"] == True),  # noqa: E712
        "Long + Turn-of-Month": long_ & E["tom"], "Long ohne ToM": long_ & ~E["tom"],
        "Mit Trend (Long auf / Short ab)": (long_ & (E["trend_up"] == True)) | (~long_ & (E["trend_up"] == False)),  # noqa: E712
    }
    for (mode, art), g in E.groupby(["Modus", "Art"]):
        for cn, cm in conds.items():
            s = cm.loc[g.index]
            for tp in ("fade1", "fade2", "fadeC"):
                x = g.loc[s, tp].dropna()
                if len(x) < 30:
                    continue
                yr = x.groupby(g.loc[x.index, "Jahr"]).agg(["mean", "size"]); big = yr[yr["size"] >= 30]
                rows.append(dict(Markt=mk, Modus=mode, Art=art, Bedingung=cn, Vorlage=tp, n=len(x), EW_R=round(x.mean(), 4),
                                 t=round(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))), 2), Jahre_30=len(big), Jahre_pos=int((big["mean"] > 0).sum())))
    print(mk, flush=True)

B = pd.DataFrame(rows)
B.to_csv(RES / "gz_b2_bias.csv", index=False)
Z = B[B["Art"] == "Zone"].merge(B[B["Art"] == "Kontrolle"][["Markt", "Modus", "Bedingung", "Vorlage", "EW_R"]].rename(columns={"EW_R": "EW_Kontrolle"}),
                                 on=["Markt", "Modus", "Bedingung", "Vorlage"], how="left")
Z["konsistent"] = (Z["EW_R"] > 0) & (Z["Jahre_30"] >= 2) & (Z["Jahre_pos"] == Z["Jahre_30"])
print("Varianten Runde 2:", len(Z))
md = ["# H7 Runde 2 – Zonen + belegter Richtungs-Bias (nur Explore)", "", f"Varianten: {len(Z)}", "",
      Z.sort_values(["Bedingung", "Vorlage", "Markt", "Modus"]).to_markdown(index=False)]
(RES / "gz_b2_bias.md").write_text("\n".join(md))
pd.set_option("display.width", 220)
print(Z.pivot_table(index=["Bedingung", "Vorlage"], columns=["Markt"], values="EW_R", aggfunc="mean").round(3).to_string())
print(Z[Z["konsistent"]].sort_values("t", ascending=False).to_string())
