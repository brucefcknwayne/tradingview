# data-lab

Rohdaten für eigene Strategie-Forschung (Python), Quelle Databento (CME Globex MDP 3.0).

## Daten

`data/nq_1m/nq_1m_<jahr>.parquet` – NQ 1m Endlos-Reihe, 2010-06 bis 2026-10-16, ca. 5,5 Mio. Bars.

| Spalte | Inhalt |
|---|---|
| `ts_utc`, `ts_et` | Bar-Öffnungszeit (UTC / New York) |
| `session_date` | Handelstag (beginnt 18:00 ET am Vortag) |
| `symbol`, `instrument_id` | aktiver Kontrakt (z. B. NQZ6) |
| `open`, `high`, `low`, `close`, `volume` | Rohpreise des Kontrakts |
| `rth` | 09:30–16:00 ET |
| `roll` | erster Bar nach Kontraktwechsel |
| `adj` | additiver Back-Adjust: `preis + adj` = rollbereinigte Reihe |

- Front-Month = Kontrakt mit meistem Tagesvolumen, Roll nur vorwärts. Spreads entfernt.
- Minuten ohne Trade fehlen (Databento schreibt nur Bars mit Umsatz).
- Rohpreise für Intraday-Level, `+ adj` für alles über mehrere Tage (MAs, Swings über Roll).

Weitere Märkte im gleichen Format: `data/es_1m/`, `data/gc_1m/` (RTH 08:20–13:30), `data/rty_1m/` (ab 2017-07).

## Orderflow (Tickdaten NQ, ab 2022-09-19)

Aus Databento `trades` (jeder Trade mit Aggressor-Seite), gebaut mit `build_trades.py`. Front-Kontrakt wie in `nq_1m`.
Abgleich mit `nq_1m`: Hoch/Tief 99,99 %, Volumen 99,6 % gleich, Kontrakt 100 %.

| Ordner | Inhalt |
|---|---|
| `data/nq_of1m/` | 1m-Bars: OHLC, `volume`, `buy_vol`/`sell_vol` (Aggressor), `delta`, `trades`, `vwap`, `max_order`, Volumen großer Orders `big10_*`/`big50_*` (≥10/≥50 Kontrakte), `rth` |
| `data/nq_fp/` | Footprint: je `session_date`, Minute (`ts_utc`) und Preis (`px` in Ticks, Preis = px × 0,25) `buy`/`sell` |
| `data/nq_vp/` | Volume Profile: je `session_date`, `part` (ETH/RTH) und `px` `buy`/`sell` |

„Order“ = alle Prints mit gleichem Zeitstempel und gleicher Seite (eine aggressive Order über mehrere Preise).
Kein Orderbuch (keine Limit Orders/Cancels). Letzter Tag 2026-10-19 nur angebrochen.
Neu bauen: Rohdateien nach `data/raw/trades/` legen, dann `python data-lab/build_trades.py`.

## Neu bauen

Rohdatei (`*.dbn.zst`, nicht im Repo) nach `data/raw/` legen, dann:

```
pip install databento pandas pyarrow
python data-lab/build_continuous.py data-lab/data/raw/<datei>.dbn.zst [ROOT ...]
```

## Laden

```python
import pandas as pd, glob
nq = pd.concat(pd.read_parquet(f) for f in sorted(glob.glob("data-lab/data/nq_1m/*.parquet")))
```
