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
| `prev-day-va/` | Vortag POC/VAH/VAL (Volume Profile, rechnet wie TV-VP: Row Layout/Size, 2-Zeilen-VA, 1m-Daten), Linien ab Vortagsbeginn bis zum Take |
| `cracks/` | Gotham Levels: MotiveWave-Cracks (7D/30D/60D/90D …) per Paste (Blöcke NQ=/ES=/GC=, Symbol auto erkannt inkl. Micros/Kontraktmonat) als weiße Linien + Multi-TF-RSI-Tabelle |
| `gotham-vwap/` | Gotham Daily VWAP: Blend-VWAP (Overnight → RTH per Volumen-Uhr) aus dem Gotham Signals Indi v2 + 2σ/3σ-Bänder + ±0.5σ-Zone grau gefüllt |
| `adamcapitals/` | Nutzer-Strategie aus der AdamCapitals-PDF: Failed Zone → Breaker → Inducement (LIQ) → Limit in unmitigated Zone, SL hinter Zone, TP 1:7, Teilgewinn 1:4 + BE, max. 2 Trades/Tag (aktuelles Projekt) |
