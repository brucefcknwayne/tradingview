# gotham-zones

Gotham Zones (±0.5/1/1.5/2σ um das Daily Open, σ aus VIX1D/VIX9D/VXN) – Auswertung und Strategie.

- `GZ-1s-Breakout_strategy.pine` – Long-Breakout über die +1σ-Zone, erster Touch 09:30–11:00 NY,
  SL 1.5 × Zonenhöhe, TP 2R, flat 16:00.

- `GZ-IV-Noise_strategy.pine` – Intraday-Momentum (Noise Area mit IV-Grenzen), NQ, ~0.8 Trades/Tag,
  Checkpoints alle 30 Min 10:00–15:30, Exit unter max(Grenze, VWAP), flat 16:00.
  NQ Test 2021–26 Sharpe 1.02 (t 2.4), Train Sharpe 0.74 (t 2.4). Auf ES/RTY/GC kein Edge.

- `IB-Levels_indicator.pine` – IB-Hoch/-Tief für jede Startzeit (jede volle Stunde + 08:30/09:30/10:30,
  15/30/45/60 Min), Linien als „geschützt“ / „bricht“ mit Wahrscheinlichkeit (NQ, ES, RTY, GC, 1J/3J/5J).
  Wird von `data-lab/ib_levels_stats.py` aus `IB-Levels_template.pine` gebaut – nicht von Hand ändern, sondern das Template.

- `IB-Expansion_ALL.pine` – **ein** Indikator für NQ, ES, RTY und GC (Markt wird automatisch erkannt), ~59.000 Zeichen, 444 Zeilen.
  Gleiche Anzeige wie die Einzel-Versionen, aber die Statistik steckt als kleine Formel (logistische Regression je
  IB-Fenster, Größenklasse und Seite) statt als Tabelle im Skript – rund 30× kleiner, im Prüfjahr gleich gut kalibriert.
  Einstufung bleibt: Ein Level, das einmal ≥ 70 % hat, bleibt Target/Protect (mit % beim Erscheinen) bis Treffer oder Tagesende
  (Prüfung: `data-lab/results/ib_ext_lock_check.md`). Alarme für Treffer/Brüche und neue Levels.
  Gesperrt, weil im Test nicht verlässlich: neue Targets in den letzten 10 % der Restzeit, späte Rückläufe.
  Wird von `data-lab/ib_ext_model.py` aus `IB-Expansion-ALL_template.pine` gebaut. Prüfung: `data-lab/results/ib_ext_model.md`.

- `IB-Expansion_<Markt>.pine` – ältere Tabellen-Version, ein Indikator je Markt (NQ, ES, RTY, GC), Daten im Skript. Vier IBs gleichzeitig
  (15/30/45/60 Min ab derselben Startzeit), je IB Levels ±0,1 … ±3,0 IB-Range,
  gezeigt wird nur ≥ 70 %: Targets (werden erreicht), Protects (halten), Rücklauf zum IB-Rand nach 09:30 (nur IBs bis 09:30).
  Live nach IB-Größe (klein/normal/groß ggü. 20 Vortagen), Abstand zum Kurs und Restzeit, mit Korrektur aus dem Prüfjahr.
  Wird von `data-lab/ib_ext_stats.py` aus `IB-Expansion_template.pine` gebaut. Prüfung: `data-lab/results/ib_ext_stats.md`.

Ergebnisse (Python, `data-lab/`):
- Zonen pauschal (Fade oder Breakout) haben keinen Vorteil, Reaktion im Median 20–30 Pkt
  (`data-lab/results/gotham_zones_reaction.md`, `gotham_zones_trades.md`).
- Einziger Kandidat aus 1.217 Bedingungs-Tests: +1σ-Breakout am Vormittag
  (`data-lab/results/zones_edge_search.md`, `zones_breakout_check.md`).
  30D Test 2021–26 +0.37R/Trade (t 2.4), 9D +0.14R, 1D +0.02R; 2024–25 schwach.
- Intraday-Scan über NQ/ES/RTY/GC: `data-lab/results/intraday_scan.md`.
