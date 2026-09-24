# Arbeitsweise in diesem Repo

- Antworten auf Deutsch, kurz und direkt.
- Änderungen immer selbst in die Dateien einbauen, nicht als Suchen/Ersetzen-Anleitung schicken.
- Danach die komplette, fertige Datei als `.txt` an den Nutzer schicken (zum Kopieren in den Pine-Editor).
- Code ist Pine Script v6 für TradingView, Hauptinstrument NQ/MNQ, meist 1m-Charts.

## Projekte

| Ordner | Inhalt |
|---|---|
| `vwap-tb/` | VWAP ±2σ Top/Bottom mit Footprint-Absorption – Indikator und Strategie (SL hinter dem Extrem, TP1–3, BE nach TP1) |
| `pullback-1r/` | RSI(2)-Pullback 1:1 mit Training/Test-Tabelle (Ergebnis: ~51 %, kein Vorteil) |
| `multi-10/` | 10 Standard-Setups 1:1 in einer Strategie mit Vergleichstabelle (Ergebnis: alle unter 50 %) |
| `orderblocks/` | 1H-Orderblocks auf kleineren Charts |
| `adamcapitals/` | Nutzer-Strategie aus der AdamCapitals-PDF: Failed Zone → Breaker → Inducement (LIQ) → Limit in unmitigated Zone, SL hinter Zone, TP 1:7, Teilgewinn 1:4 + BE, max. 2 Trades/Tag (aktuelles Projekt) |
