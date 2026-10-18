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
| `data-lab/` | Python-Rohdaten: NQ/ES/RTY/GC 1m Endlos-Reihen 2010–2026 (Databento) als Parquet, Build- und Statistik-Skripte |
| `gotham-zones/` | Gotham Zones (IV-σ-Zonen ums Daily Open; `Gotham-Zones.pine` = Hauptindikator mit Auto-Kalibrierung, Trefferquoten, Regime, Weekly Zones, Event-Tagen), IB-Levels und IB-Expansion (Targets/Protects/Rücklauf ab 70 %, `IB-Expansion_ALL.pine` = ein Indikator für alle 4 Märkte), Auswertung in `data-lab/` |
| `orderblocks/` | 1H-Orderblocks auf kleineren Charts |
| `adamcapitals/` | Nutzer-Strategie aus der AdamCapitals-PDF: Failed Zone → Breaker → Inducement (LIQ) → Limit in unmitigated Zone, SL hinter Zone, TP 1:7, Teilgewinn 1:4 + BE, max. 2 Trades/Tag |
| `ib-first/` | IB First: Tief der IB zuerst → IB-Hoch wird geholt (und umgekehrt), Linien mit % für Gegenseite, +0,5/+1 IB, Erstseite; Statistik in `data-lab/ib_first_*.py` (aktuelles Projekt) |
