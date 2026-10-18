# IB First – Tief zuerst → Hoch wird geholt (Indikator auf Englisch: „Low first → High gets taken“)

Eigenständiges Projekt (unabhängig von `gotham-zones/IB-Expansion`).

**Idee:** Entsteht in der Initial Balance zuerst das Tief, wird danach meist das IB-Hoch geholt – und umgekehrt.

## Indikator `IB-First.pine` (Englisch, reiner Kontext – keine Strategie)
Frage: **Welche IB-Seite bricht nach dem IB-Ende zuerst?** NQ, ES, RTY, GC (+ Micros), Markt wird erkannt.
Eine Haupt-IB (Startzeit + Länge, Auto = beste Länge je Markt und Start), am IB-Ende:
- klein grau „low formed first“ / „high formed first“
- Linie an der Seite, die laut Statistik zuerst bricht: „15m · High breaks first 76%“ (ab 70 %, einstellbar)
  ✓ = diese Seite brach zuerst · ✗ = die andere Seite brach zuerst (gleicher Bar = ✗), Linie endet
- optional Ausdehnung über diese Seite: „+0.4 IB 81%“ (bis Sitzungsende erreicht, 60–90 % wählbar)
- andere IB-Längen (15/30/45/60) gepunktet, wenn ihre Seite zu ≥ 80 % zuerst brach
Test letztes Jahr (Kalibrierung): „Gegenseite zuerst“ und „Erstseite zuerst“ je Band ±1–4 Pkt. (hohe Bänder eher vorsichtig);
bei 70 %: Linie an grob 60 % der Tage, davon ~84 % richtig (aus den Kalibrierungsbändern abgeleitet).

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
