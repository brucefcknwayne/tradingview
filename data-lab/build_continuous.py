"""
NQ 1m Endlos-Reihe aus Databento OHLCV-1m (Parent NQ.FUT).

- Spreads raus, nur Outrights
- Pro Handelstag der Kontrakt mit dem meisten Volumen (Roll nur vorwärts)
- Zeit in New York, Handelstag ab 18:00 ET, RTH/ETH-Markierung
- Rohpreise + additiver Back-Adjust-Offset (close_adj = close + adj)
- Ausgabe: data/nq_1m/nq_1m_<jahr>.parquet

Aufruf: python data-lab/build_continuous.py [pfad/zur/datei.dbn.zst]
"""
import sys
from pathlib import Path

import databento as db
import pandas as pd

HERE = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data/raw/glbx-mdp3-20100606-20261016.ohlcv-1m.dbn.zst"
OUT = HERE / "data/nq_1m"
MONTHS = {"H": 3, "M": 6, "U": 9, "Z": 12}

df = db.DBNStore.from_file(SRC).to_df(map_symbols=True)
df = df[~df["symbol"].str.contains("-")].reset_index()  # Spreads raus
df = df.rename(columns={"ts_event": "ts_utc"})

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
df["expiry"] = df["instrument_id"].map(expiry)

# Front-Month = meistes Volumen am Handelstag, nie zurück auf älteren Kontrakt
vol = df.groupby(["session_date", "instrument_id"])["volume"].sum().reset_index()
front = vol.loc[vol.groupby("session_date")["volume"].idxmax()].copy()
front["expiry"] = front["instrument_id"].map(expiry)
front = front.sort_values("session_date")
front["expiry"] = front["expiry"].cummax()
exp_to_iid = {v: k for k, v in expiry.items()}
front["instrument_id"] = front["expiry"].map(exp_to_iid)
front = front[["session_date", "instrument_id"]]

nq = df.merge(front, on=["session_date", "instrument_id"])
nq = nq.sort_values("ts_utc").reset_index(drop=True)

# Additiver Back-Adjust: Gap am Roll = Close neuer Kontrakt - Close alter Kontrakt
# zur letzten gemeinsamen Minute vor dem Roll
nq["roll"] = nq["instrument_id"] != nq["instrument_id"].shift()
nq.loc[0, "roll"] = False
gaps = pd.Series(0.0, index=nq.index)
by_key = df.set_index(["instrument_id", "ts_utc"])["close"]
for i in nq.index[nq["roll"]]:
    old_iid, new_iid = nq.at[i - 1, "instrument_id"], nq.at[i, "instrument_id"]
    prev = df[(df["ts_utc"] < nq.at[i, "ts_utc"]) & df["instrument_id"].isin([old_iid, new_iid])]
    both = prev.pivot_table(index="ts_utc", columns="instrument_id", values="close").dropna()
    if len(both):
        last = both.iloc[-1]
        gaps[i] = last[new_iid] - last[old_iid]
    else:
        gaps[i] = nq.at[i, "open"] - nq.at[i - 1, "close"]
# Offset gilt rückwärts: alles vor einem Roll wird um dessen Gap verschoben
nq["adj"] = gaps[::-1].cumsum()[::-1].shift(-1, fill_value=0.0)

t = nq["ts_et"].dt.hour * 60 + nq["ts_et"].dt.minute
nq["rth"] = (t >= 9 * 60 + 30) & (t < 16 * 60)

cols = ["ts_utc", "ts_et", "session_date", "symbol", "instrument_id",
        "open", "high", "low", "close", "volume", "rth", "roll", "adj"]
nq = nq[cols]

OUT.mkdir(parents=True, exist_ok=True)
for year, part in nq.groupby(nq["ts_et"].dt.year):
    part.to_parquet(OUT / f"nq_1m_{year}.parquet", compression="zstd", index=False)

rolls = nq[nq["roll"]]
print(f"{len(nq):,} Bars, {nq['session_date'].nunique():,} Handelstage, {len(rolls)} Rolls")
print(f"{nq['ts_et'].min()} -> {nq['ts_et'].max()}")
print(rolls[["ts_et", "symbol"]].tail(8).to_string(index=False))
