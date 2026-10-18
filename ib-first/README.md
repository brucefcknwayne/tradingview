# IB First – Tief zuerst → Hoch wird geholt

Eigenständiges Projekt (unabhängig von `gotham-zones/IB-Expansion`).

**Idee:** Entsteht in der Initial Balance zuerst das Tief, wird danach meist das IB-Hoch geholt – und umgekehrt.

## Indikator `IB-First.pine`
NQ, ES, RTY, GC (+ Micros), Markt wird erkannt. Eine IB je Tag: Startzeit + Länge (Auto = beste Länge je Markt und Start).
Am IB-Ende:
- **Gegenseite**: „Hoch wird geholt 89% · vor Stop 89%“ (vor Stop = bevor das zuerst gebildete Extrem noch einmal bricht)
- **TP**: weitestes Ziel über der Gegenseite mit mindestens der gewählten Sicherheit (TP-Modus 60 / 70 / 80 / 90 %)
- **Stop-Seite**: „Tief nochmal 58%“
Linien bis Berührung (✓) oder Tagesende, Alarme für IB-Ende und Treffer.

Die % hängen ab von Markt, Startzeit, IB-Länge, was zuerst kam, **IB-Größe ggü. den 20 Tagen davor** (News-IB!) und
**Lage des Kurses am IB-Ende**. Logistische Modelle, Koeffizienten im Skript.
Gebaut: `python data-lab/ib_first_model.py` (Analyse, ~8 Min) → `python data-lab/ib_first_build.py` (Pine aus `IB-First_template.pine`).

## Analyse (`data-lab/results/ib_first_model.md`)
Auswahl nur auf der Validierung (vorletztes Jahr), Test im letzten Jahr (ungesehen):
- Lage des Kurses bringt am meisten, IB-Größe etwas; **Wochentag bringt nichts** (Modell mit Wochentag minimal schlechter).
- **Beste Länge je Wochentag bringt nichts**: Testjahr „Ziel vor Stop“ 68,9 % (je Wochentag) = 68,9 % (feste beste Länge),
  immer 30 Min 68,1 % → Auto nimmt die feste beste Länge je Markt und Start.
- Kalibrierung im Test gut (Gegenseite, Ziel vor Stop, Stop-Seite je Band ±2 Pkt.).
- TP-Modus im Test: 60 % → 65 % erreicht (98 % der Tage mit TP, Ø +1,35 IB), 70 % → 71 % (94 %, +1,18), 80 % → 79 % (84 %, +0,92),
  90 % → 89 % (63 %, +0,48). Angezeigt jeweils 2–3 Pkt. über eingetreten.
- Große IBs (oberstes Zehntel): Modell eher vorsichtig (z. B. NQ 84 % angezeigt, 88 % eingetreten).

Ältere einfache Auswertung: `data-lab/ib_first_side.py` → `results/ib_first_side.md`.
