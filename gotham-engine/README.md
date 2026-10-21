# Gotham Engine – Nachrechnung auf echten NQ-Trades

Live-Orderflow-Study des Nutzers (MotiveWave, v1.5.1): ABSORPTION / BREAKING. Hier die Regeln 1:1 auf Databento-Trades nachgerechnet.

- `engine_sim.py` – lädt NQ-Trades (Schema trades, Front-Kontrakt je Session), rechnet alle 250 ms die Fenster-Kennzahlen (20/10/5 s)
- `engine_eval.py` – Ereignisse (steigende Flanke, Cooldown 20 s), Ergebnisse, Zufallsvergleich, Kalibrierung → `results/events.csv`, `results/sweep.csv`
- `engine_report.py` – `results/auswertung.md`

Daten: 20 Handelstage 2026-09-21 … 2026-10-16, NQZ6. refill/iceberg leer (kein tbbo/mbo; Databento-Konto zum Zeitpunkt gesperrt).
