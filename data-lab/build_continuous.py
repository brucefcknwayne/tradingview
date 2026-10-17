"""
1m Endlos-Reihen aus Databento OHLCV-1m (Parent-Symbole wie NQ.FUT, ES.FUT, GC.FUT, RTY.FUT).

- Spreads raus, nur Outrights
- Pro Handelstag der Kontrakt mit dem meisten Volumen (Roll nur vorwärts)
- Zeit in New York, Handelstag ab 18:00 ET, RTH/ETH-Markierung (Index 09:30-16:00, Gold 08:20-13:30)
- Rohpreise + additiver Back-Adjust-Offset (close_adj = close + adj)
- Ausgabe: data/<root>_1m/<root>_1m_<jahr>.parquet

Aufruf: python data-lab/build_continuous.py <datei.dbn.zst> [ROOT ...]
        ohne ROOT: alle Roots in der Datei
"""
import sys
from pathlib import Path

import databento as db
import pandas as pd

HERE = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data/raw/glbx-mdp3-20100606-20261016.ohlcv-1m.dbn.zst"
MONTHS = dict(zip("FGHJKMNQUVXZ", range(1, 13)))
RTH = {"GC": (8 * 60 + 20, 13 * 60 + 30)}
RTH_DEFAULT = (9 * 60 + 30, 16 * 60)

raw = db.DBNStore.from_file(SRC).to_df(map_symbols=True)
raw = raw[~raw["symbol"].str.contains("-")].reset_index()  # Spreads raus
raw = raw.rename(columns={"ts_event": "ts_utc"})
raw["root"] = raw["symbol"].str[:-2]
roots = sys.argv[2:] or sorted(raw["root"].unique())


def build(df, root):
    df = df.copy()
    df["ts_et"] = df["ts_utc"].dt.tz_convert("America/New_York")
    # Handelstag beginnt 18:00 ET am Vortag
    df["session_date"] = (df["ts_et"] + pd.Timedelta(hours=6)).dt.date

    # Verfall pro instrument_id (Symbol-Jahr ist einstellig, z.B. NQM0 = 2010 oder 2020)
    first_seen = df.groupby("instrument_id")["ts_utc"].min()
    sym = df.groupby("instrument_id")["symbol"].first()
    expiry = {}
    for iid, s in sym.items():
        digit, y = int(s[-1]), first_seen[iid].year
        while y % 10 != digit:
            y += 1
        expiry[iid] = y * 100 + MONTHS[s[-2]]

    # Front-Month = meistes Volumen am Handelstag, nie zurück auf älteren Kontrakt
    vol = df.groupby(["session_date", "instrument_id"])["volume"].sum().reset_index()
    front = vol.loc[vol.groupby("session_date")["volume"].idxmax()].copy()
    front["expiry"] = front["instrument_id"].map(expiry)
    front = front.sort_values("session_date")
    front["expiry"] = front["expiry"].cummax()
    exp_to_iid = {v: k for k, v in expiry.items()}
    front["instrument_id"] = front["expiry"].map(exp_to_iid)
    front = front[["session_date", "instrument_id"]]

    out = df.merge(front, on=["session_date", "instrument_id"])
    out = out.sort_values("ts_utc").reset_index(drop=True)

    # Additiver Back-Adjust: Gap am Roll = Close neuer Kontrakt - Close alter Kontrakt
    # zur letzten gemeinsamen Minute vor dem Roll
    out["roll"] = out["instrument_id"] != out["instrument_id"].shift()
    out.loc[0, "roll"] = False
    gaps = pd.Series(0.0, index=out.index)
    for i in out.index[out["roll"]]:
        old_iid, new_iid = out.at[i - 1, "instrument_id"], out.at[i, "instrument_id"]
        pair = df[df["instrument_id"].isin([old_iid, new_iid])]
        prev = pair[pair["ts_utc"] < out.at[i, "ts_utc"]]
        both = prev.pivot_table(index="ts_utc", columns="instrument_id", values="close").dropna()
        if len(both):
            last = both.iloc[-1]
            gaps[i] = last[new_iid] - last[old_iid]
        else:
            gaps[i] = out.at[i, "open"] - out.at[i - 1, "close"]
    # Offset gilt rückwärts: alles vor einem Roll wird um dessen Gap verschoben
    out["adj"] = gaps[::-1].cumsum()[::-1].shift(-1, fill_value=0.0)

    t = out["ts_et"].dt.hour * 60 + out["ts_et"].dt.minute
    a, b = RTH.get(root, RTH_DEFAULT)
    out["rth"] = (t >= a) & (t < b)

    cols = ["ts_utc", "ts_et", "session_date", "symbol", "instrument_id",
            "open", "high", "low", "close", "volume", "rth", "roll", "adj"]
    out = out[cols]

    dst = HERE / f"data/{root.lower()}_1m"
    dst.mkdir(parents=True, exist_ok=True)
    for year, part in out.groupby(out["ts_et"].dt.year):
        part.to_parquet(dst / f"{root.lower()}_1m_{year}.parquet", compression="zstd", index=False)

    rolls = out[out["roll"]]
    print(f"{root}: {len(out):,} Bars, {out['session_date'].nunique():,} Handelstage, {len(rolls)} Rolls, "
          f"{out['ts_et'].min()} -> {out['ts_et'].max()}")
    print(rolls[["ts_et", "symbol"]].tail(4).to_string(index=False))


for r in roots:
    build(raw[raw["root"] == r], r)
