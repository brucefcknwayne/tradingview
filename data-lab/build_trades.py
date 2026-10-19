"""
NQ-Tickdaten (Databento trades, jeder Trade mit Aggressor-Seite) → kompakte Orderflow-Daten.

Quelle: data/raw/trades/glbx-mdp3-<YYYYMMDD>.trades.dbn.zst (UTC-Tagesdateien, NQ.FUT, ab 2022-09-19)
Front-Kontrakt je Handelstag wie in data/nq_1m (gleiche Roll-Logik); fehlt der Tag dort, der Kontrakt mit
dem meisten Volumen. Spreads raus. side B = Käufer-Aggressor, A = Verkäufer-Aggressor, N = ohne (selten).

Ausgabe (je Handelsjahr eine Datei):
  data/nq_of1m/nq_of1m_<jahr>.parquet  – 1m-Bars: OHLC, Volumen, Kauf-/Verkaufsvolumen, Delta, Trades,
                                          größte Order, Volumen großer Orders (≥10 / ≥50 Kontrakte), VWAP der Minute
  data/nq_fp/nq_fp_<jahr>.parquet      – Footprint: je Minute und Preis Kauf- und Verkaufsvolumen
  data/nq_vp/nq_vp_<jahr>.parquet      – Volume Profile: je Handelstag, Preis und Teil (ETH/RTH) Kauf/Verkauf

„Order“ = alle Prints mit gleichem Zeitstempel, gleicher Seite und gleichem Kontrakt (eine aggressive Order,
die mehrere Preise frisst, wird von der Börse in mehrere Prints zerlegt).

Aufruf: python data-lab/build_trades.py   (nutzt 4 Prozesse, Zwischenstände in data/raw/trades/_parts/)
"""
import glob
import sys
from multiprocessing import Pool
from pathlib import Path

import databento as db
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
RAW = HERE / "data/raw/trades"
PARTS = RAW / "_parts"
TICK = 0.25
BIG = (10, 50)


def front_map():
    nq = pd.concat(pd.read_parquet(f, columns=["session_date", "symbol", "volume"]) for f in sorted(glob.glob(str(HERE / "data/nq_1m/*.parquet"))))
    nq["session_date"] = pd.to_datetime(nq["session_date"]).dt.date
    return nq.groupby("session_date")["symbol"].agg(lambda s: s.mode().iat[0]).to_dict()


FRONT = front_map()


def one(path):
    name = Path(path).name.split(".")[0]
    out = {k: PARTS / f"{name}.{k}.parquet" for k in ("of1m", "fp", "vp")}
    if all(p.exists() for p in out.values()):
        return name, "da"
    df = db.DBNStore.from_file(path).to_df()
    if df.empty:
        return name, "leer"
    df = df[(df["action"] == "T") & ~df["symbol"].str.contains("-")].reset_index()
    df["ts_et"] = df["ts_event"].dt.tz_convert("America/New_York")
    df["session_date"] = (df["ts_et"] + pd.Timedelta(hours=6)).dt.date
    # Front-Kontrakt je Handelstag
    fm = df["session_date"].map(FRONT)
    miss = fm.isna()
    if miss.any():
        top = df[miss].groupby(["session_date", "symbol"])["size"].sum().reset_index()
        top = top.loc[top.groupby("session_date")["size"].idxmax()].set_index("session_date")["symbol"]
        fm[miss] = df.loc[miss, "session_date"].map(top)
    df = df[df["symbol"] == fm].copy()
    if df.empty:
        return name, "kein Front"

    df["minute"] = df["ts_event"].dt.floor("min")
    df["buy"] = np.where(df["side"] == "B", df["size"], 0)
    df["sell"] = np.where(df["side"] == "A", df["size"], 0)
    df["pv"] = df["price"] * df["size"]

    # Orders: gleiche Nanosekunde + Seite → eine aggressive Order
    od = df[df["side"].isin(["A", "B"])].groupby(["ts_event", "side"], sort=False).agg(size=("size", "sum"), minute=("minute", "first")).reset_index()
    big = {}
    for b in BIG:
        o = od[od["size"] >= b]
        big[f"big{b}_buy"] = o[o["side"] == "B"].groupby("minute")["size"].sum()
        big[f"big{b}_sell"] = o[o["side"] == "A"].groupby("minute")["size"].sum()
    ordmax = od.groupby("minute")["size"].max()

    g = df.groupby("minute", sort=True)
    m = g.agg(session_date=("session_date", "first"), symbol=("symbol", "first"),
              open=("price", "first"), high=("price", "max"), low=("price", "min"), close=("price", "last"),
              volume=("size", "sum"), buy_vol=("buy", "sum"), sell_vol=("sell", "sum"), trades=("size", "size"), pv=("pv", "sum"))
    m["delta"] = m["buy_vol"] - m["sell_vol"]
    m["vwap"] = m["pv"] / m["volume"]
    m["max_order"] = ordmax.reindex(m.index).fillna(0).astype("int32")
    for k, s in big.items():
        m[k] = s.reindex(m.index).fillna(0).astype("int32")
    m = m.drop(columns="pv").reset_index().rename(columns={"minute": "ts_utc"})
    m["ts_et"] = m["ts_utc"].dt.tz_convert("America/New_York")
    t = m["ts_et"].dt.hour * 60 + m["ts_et"].dt.minute
    m["rth"] = (t >= 570) & (t < 960)
    for c in ("volume", "buy_vol", "sell_vol", "delta", "trades"):
        m[c] = m[c].astype("int32")
    m.to_parquet(out["of1m"], index=False)

    df["px"] = np.rint(df["price"] / TICK).astype("int32")      # Preis in Ticks
    fp = df.groupby(["minute", "px"], sort=True).agg(buy=("buy", "sum"), sell=("sell", "sum")).reset_index()
    fp = fp.rename(columns={"minute": "ts_utc"})
    fp["buy"] = fp["buy"].astype("int32"); fp["sell"] = fp["sell"].astype("int32")
    fp.to_parquet(out["fp"], index=False)

    tt = df["ts_et"].dt.hour * 60 + df["ts_et"].dt.minute
    df["part"] = np.where((tt >= 570) & (tt < 960), "RTH", "ETH")
    vp = df.groupby(["session_date", "part", "px"], sort=True).agg(buy=("buy", "sum"), sell=("sell", "sum")).reset_index()
    vp.to_parquet(out["vp"], index=False)
    return name, f"{len(m)} Min, {len(df)} Trades"


def combine():
    for k, dirname in (("of1m", "nq_of1m"), ("fp", "nq_fp"), ("vp", "nq_vp")):
        parts = sorted(PARTS.glob(f"*.{k}.parquet"))
        d = pd.concat(pd.read_parquet(p) for p in parts)
        if k == "fp":
            # Handelstag aus der Minute (18:00 ET = neuer Tag)
            d["session_date"] = (d["ts_utc"].dt.tz_convert("America/New_York") + pd.Timedelta(hours=6)).dt.date
            d = d.groupby(["session_date", "ts_utc", "px"], sort=True)[["buy", "sell"]].sum().reset_index()
        elif k == "vp":
            d = d.groupby(["session_date", "part", "px"], sort=True)[["buy", "sell"]].sum().reset_index()
        else:
            d = d.sort_values("ts_utc")
        for c in ("px", "buy", "sell"):
            if c in d:
                d[c] = d[c].astype("int32")
        od = HERE / f"data/{dirname}"
        od.mkdir(exist_ok=True)
        yrs = pd.to_datetime(d["session_date"]).dt.year
        for y, part in d.groupby(yrs):
            part.to_parquet(od / f"{dirname}_{y}.parquet", index=False, compression="zstd")
            print(dirname, y, len(part), flush=True)


if __name__ == "__main__":
    PARTS.mkdir(exist_ok=True)
    files = sorted(glob.glob(str(RAW / "glbx-mdp3-*.trades.dbn.zst")))
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        files = files[-3:]
    with Pool(4) as pool:
        for i, (n, s) in enumerate(pool.imap_unordered(one, files), 1):
            if i % 50 == 0 or i == len(files) or "--test" in sys.argv:
                print(i, "/", len(files), n, s, flush=True)
    if "--test" not in sys.argv:
        combine()
