# Hypothesen

Status: offen · getestet · verworfen · Kandidat

## H1 – Zera-Reversal (Status: **verworfen** – LOG #1, 2026-10-19)

**Mechanismus-Idee:** Nach einer Serie extremer Abweichungen vom 50-Kerzen-Mittel (|Z| ≥ 2) läuft der Preis
zurück Richtung Mittel, sobald die Abweichung nachlässt (erste neutrale Kerze).

### Vorab-Registrierung (festgelegt am 2026-10-19, VOR jeder Auswertung)

**Daten**
- Databento GLBX.MDP3, Schema `trades`, NQ.FUT; Front-Kontrakt je Handelstag = meistes Volumen, Roll nur vorwärts
  (entspricht NQ.v.0). Rohpreise ohne Back-Adjust. Aggressor = Feld `side`.
- Auswertungszeitraum für ALLE drei Chart-Typen gleich: 2022-09-19 bis 2026-04-16 (Handelstage).
- **Holdout:** Handelstage ab 2026-04-17 (letzte 6 Monate). Werden beim Laden sofort abgeschnitten.
- Zeitzone New York, RTH = 09:30–16:00 ET (Signal-Kerze entscheidet).

**Chart-Typen**
- a) 1m-Zeitkerzen aus denselben Ticks (Minuten ohne Trade = keine Kerze).
- b) 500er und c) 1000er Volume-Bars: Kerze schließt bei genau N Kontrakten; ein Trade über die Grenze wird
  aufgeteilt. Kerzen laufen über Sessiongrenzen weiter, beginnen aber beim Kontraktwechsel neu.

**Indikator:** src = OHLC4, mean/sd (Population) über 50 Kerzen inkl. aktueller, Z = (src − mean)/sd.
Nach jedem Roll startet das Fenster neu (die ersten 49 Kerzen eines Kontrakts haben kein Z).

**Signal:** Serie ≥ 1 Kerze mit |Z| ≥ 2 gleichen Vorzeichens; erste Kerze danach mit |Z| < 2 = Signal.
Wechselt das Vorzeichen direkt (z. B. +2,4 → −2,1), endet die alte Serie ohne Signal und eine neue beginnt.
Richtung: nach +Z Short, nach −Z Long.

**Trade**
- Einstieg Open der Kerze nach der Signal-Kerze. Ziel = mean der Signal-Kerze.
- Liegt der Einstieg schon auf/hinter dem Ziel → kein Trade (wird gezählt und berichtet).
- Stop-Varianten (beide vorab festgelegt, beide berichtet, beide in der Mehrfachtest-Korrektur):
  - **A: 20 Punkte**
  - **B: Extrem der farbigen Serie + 1 Tick** (Short: höchstes Hoch der Serie + 0,25; Long: tiefstes Tief − 0,25).
    Liegt der Einstieg schon hinter diesem Stop → kein Trade.
- Prüfung ab der Einstiegskerze; Stop und Ziel in derselben Kerze → Stop. Timeout: Close der 50. Kerze (inkl. Einstiegskerze).
- Offener Trade beim Kontraktwechsel → Exit zum Close der letzten Kerze des alten Kontrakts.
- Kosten 1,0 Punkt pro Round-Trip. Kein neues Signal, solange ein Trade offen ist (je Chart-Typ und Stop-Variante).
- MFE/MAE über die echte Haltedauer. 6RR: +120 vor −20 Punkten innerhalb von 50 Kerzen ab Einstieg
  (unabhängig vom echten Ziel/Stop; gleiche Kerze → −20 zuerst).

**Aufteilungen je Chart-Typ und Stop-Variante (nur diese):** Gesamt · Magenta erreicht vs. nur Cyan · Long vs. Short ·
RTH vs. Overnight · preisgetrieben vs. nicht preisgetrieben (Preisanteil > 50 % des Z-Rückgangs; Zerlegung wie im Auftrag).
= 9 Gruppen × 3 Chart-Typen × 2 Stops = **54 Tests**, Holm-Bonferroni über alle 54.

**Zufall:** Für jeden echten Trade 1.000 Zufallstrades: zufälliger anderer Handelstag im selben Zeitraum, Kerze in derselben
ET-Stunde, gleiche Richtung, **gleiche Stop- und Zielentfernung in Punkten** wie der echte Trade, gleiche Timeout-/Kosten-Regeln.
p = (1 + Anzahl Wiederholungen mit Zufalls-Erwartungswert ≥ echtem) / 1.001.

**Kennzahlen:** n, Trefferquote, Ø Gewinn/Verlust, Erwartungswert netto, Profit Factor, Max Drawdown (Punkte, Trade-Reihenfolge),
95 %-Bootstrap-KI (2.000 Ziehungen), p roh und Holm, Ø MFE/MAE, Anteil 6RR. Gruppen < 30 Trades = „zu wenig Daten“.

**Erfolgskriterium (vorab):** Edge nur, wenn eine Gruppe nach Holm p < 0,05 hat UND der Erwartungswert netto > 0 mit
KI-Untergrenze > 0 ist. Sonst: kein Edge.

**Ergebnis (2026-10-19):** 0 von 54 Tests nach Holm signifikant. Erwartungswert vor Kosten ≈ 0, nach Kosten ≈ −1 Pkt,
genau wie Zufallseinstiege mit gleichem Stop/Ziel. Bester Rohwert: Magenta-Serien (1m Stop B p roh 0,003; Vol 1000 Stop A p roh 0,022),
nach Korrektur nicht signifikant, KI schließt 0 ein. → verworfen.

## H2 – Zera-Reversal + Orderflow-Filter (Status: **verworfen** – LOG #2, 2026-10-19)
**Mechanismus:** Ein Rücklauf nach Extrem sollte nur halten, wenn der Druck wirklich nachlässt: Aggressoren drehen,
Absorption am Extrem oder Delta-Divergenz. H1 zeigt: der Preis allein (Z) unterscheidet sich nicht vom Zufall –
Orderflow ist eine zusätzliche, unabhängige Information.

### Vorab-Registrierung (2026-10-19, VOR jeder Auswertung)
Alles wie H1 (Daten, Zeitraum 2022-09-19 bis 2026-04-16, Holdout ab 2026-04-17 unberührt, Chart-Typen 1m / Vol 500 / Vol 1000,
Indikator, Signal, Einstieg, Ziel, Stop A 20 Pkt und Stop B Serien-Extrem, Timeout, Kosten, kein Signal bei offenem Trade,
Zufalls-Baseline mit 1.000 Wiederholungen). Neu: Ein Signal zählt nur, wenn sein Filter erfüllt ist (nur bei Kerzenschluss
bekannte Werte). Delta = Käufer-Aggressor-Volumen − Verkäufer-Aggressor-Volumen je Kerze (aus `side`).
„Serie“ = die farbigen Kerzen vor dem Signal; „Extrem-Kerze“ = Kerze mit dem höchsten Hoch (nach +Z) bzw. tiefsten Tief (nach −Z) der Serie.

- **F1 Delta dreht:** Delta der Signal-Kerze gegen die Serien-Richtung (nach +Z: Delta < 0; nach −Z: Delta > 0).
- **F2 Absorption am Extrem:** In der Extrem-Kerze ≥ 60 % des Aggressor-Volumens in Serien-Richtung (nach +Z: Kauf-Anteil ≥ 0,60)
  UND Schluss in der Gegenhälfte der Kerze (nach +Z: Close ≤ Mitte von Hoch/Tief; nach −Z: Close ≥ Mitte).
- **F3 Delta-Divergenz:** Serie hat ≥ 2 Kerzen und die Extrem-Kerze ist nicht die erste; ihr Delta ist kleiner als das größte Delta
  der Serien-Kerzen davor (nach +Z) bzw. größer als das kleinste (nach −Z).

Tests: 3 Filter × 3 Chart-Typen × 2 Stops = **18 Tests**, Holm-Bonferroni über alle 18, keine Untergruppen.
Erfolgskriterium wie H1: Holm-p < 0,05 UND EW netto > 0 mit KI-Untergrenze > 0 und ≥ 30 Trades.
Zusätzlich (nur beschreibend, kein Test): EW gefiltert vs. ungefiltert (H1).

**Ergebnis (2026-10-19):** 0 von 18 Tests nach Holm signifikant, alle EW netto negativ (−0,5 bis −3,1). Bester roher Wert: Vol 1000
Stop B + „Delta dreht“ (p roh 0,009, Holm 0,16, EW −0,58). Absorption (F2) ist selten (350–3.700 Trades) und nicht besser.

## H3 – Zera-Reversal nur in Regimen mit Mean Reversion (Status: offen)
**Mechanismus:** Literatur (Dealer long Gamma → mehr Intraday-Reversals). Ohne Gamma-Daten nur über Proxy möglich
(z. B. tiefe 1D-Vol, ruhiger Vortag). Schwach begründet, niedrige Priorität.

## H4 – Rücklauf an VWAP ±2σ/±3σ bzw. LVN (Status: offen)
**Mechanismus:** Extreme an Bändern mit wenig gehandeltem Volumen (LVN) sollen schneller zurücklaufen. Achtung: Level-Tests
(LOG 0f) zeigten keine Wand-Wirkung von VWAP-Bändern → nur mit Orderflow-Zusatz sinnvoll.

## Hinweis Magenta
Magenta-Serien sahen in mehreren Feldern roh besser aus als Zufall (nicht signifikant). Das ist **kein** neuer Test auf denselben
Daten wert; prüfbar nur einmal auf dem Holdout – lohnt sich erst, wenn eine Variante (z. B. H2) auf den Testdaten besteht.

## H5 – Was haben die großen Reaktionen gemeinsam? (Status: **verworfen** – LOG #3, 2026-10-19)
**Idee (Nutzer):** Nur die Zera-Signale anschauen, die eine große Reaktion geliefert haben, und suchen, was sie gemeinsam haben
(Level in der Nähe, Absorption, Zeit, Volatilität …). **Risiko:** Gemeinsamkeiten der Gewinner sind oft auch Gemeinsamkeiten der
Verlierer → immer gegen die Grundrate vergleichen und auf getrennten Daten bestätigen.

### Vorab-Registrierung (2026-10-19, VOR jeder Auswertung)
- **Universum:** alle Zera-Signale aus H1 (ungefiltert) auf **1m** und **Vol 500**.
- **Ergebnis-Trade „60/20“:** Einstieg Open der Kerze nach dem Signal, Stop 20 Pkt, Ziel **+60 Pkt**, Timeout 120 Kerzen (Close),
  gleiche Kerze → Stop, Kontraktwechsel → Exit, Kosten 1 Pkt. **Gewinner** = Ziel erreicht. Ohne Vorteil: ~25 % Gewinner, EW ≈ −1.
- **Suchen (Explore):** 2022-09-19 bis 2024-12-31. **Prüfen (Validate):** 2025-01-01 bis 2026-04-16. **Holdout ab 2026-04-17 bleibt unberührt.**
- **Merkmale** (nur zum Signal-Zeitpunkt bekannte Werte, ca. 40): Serie (max |Z|, Länge, Magenta, Preisanteil, Z der Signal-Kerze,
  Zielabstand), Zeit (Stunde, RTH, Wochentag, Minuten seit 18:00), Volatilität (1D-σ, Range bisher / σ, Serien-Spanne / σ),
  Trend (Steigung 50er-Mittel, Lage zum Tages-Open / VWAP in σ), Levels = Abstand des Serien-Extrems zu: Session-VWAP und
  RTH-VWAP ±1/2/3σ, Session-Hoch/-Tief bisher (neues Extrem ja/nein), Vortag RTH Hoch/Tief/Close, Overnight-Hoch/-Tief, IB-Hoch/-Tief
  (ab 10:30), Vortag POC/VAH/VAL (RTH-Volumenprofil), 100er/500er-Runde, Gotham-Zonen (1D) – Orderflow der Serie (Delta, Delta der
  Extrem- und Signal-Kerze, Absorption wie H2-F2, Divergenz wie H2-F3, Volumen der Serie relativ, Volumen großer Orders ≥10/≥50).
- **Methode (Explore):** (a) Gewinner vs. Verlierer je Merkmal (Effektstärke) und Gewinnrate je Merkmals-Dezil (Lift ggü. Grundrate);
  (b) Gradient-Boosting (fest: max_depth 3, learning_rate 0,05, 300 Iterationen, min_samples_leaf 200);
  (c) Entscheidungsbaum Tiefe 2 (min_samples_leaf 300) → das Blatt mit der höchsten Gewinnrate = Regel.
- **Prüfung (Validate), genau 4 Tests:** je Chart-Typ (V1) Modell-Top-10 % (Schwelle = 90 %-Quantil der Explore-Scores) und
  (V2) die Baum-Regel. Trades ohne Überlappung, gegen Zufall (gleiche Stunde, gleicher 60/20-Bracket, 1.000×), Holm über 4.
- **Erfolg:** Holm-p < 0,05 UND EW netto > 0 mit KI-Untergrenze > 0 und ≥ 30 Trades. Sonst: Muster nicht echt.

**Ergebnis H5 (2026-10-19):** 0 von 4 Prüf-Tests nach Holm signifikant (bester: 1m Modell-Top-10 % EW −0,41, p roh 0,059, Holm 0,24).
Gemeinsam haben die Gewinner vor allem **Bewegung**: RTH/Nachmittag, hohe Kerzen-Volatilität, viel verbrauchte Tagesrange.
Nähe zu Levels (Vortag H/T/C, POC/VAH/VAL, VWAP-Bänder, runde Zahlen, Gotham-Zonen) bringt nichts – Gewinner liegen eher WEITER weg.
Starkes Delta in Serien-Richtung → weniger Gewinner (beschreibend, nicht geprüft). Modell: AUC Validate 0,64 (1m) / 0,54 (Vol 500),
d. h. es erkennt, WANN große Bewegungen kommen, aber nicht die Richtung → kein EW-Vorteil.

## H6 – Volatilitäts-Timing statt Richtung (Status: offen)
**Mechanismus:** H5 zeigt, dass große Reaktionen vorhersagbar häufiger in bewegten Phasen kommen (Volatilität clustert).
Das ist eine Aussage über die **Größe** der Bewegung, nicht die Richtung. Nutzbar evtl. als Filter für Zielgröße/Stop
(große Ziele nur bei hoher Volatilität), nicht als Einstiegssignal. Niedrige Priorität für Richtungs-Edge.

## H7 – Gotham Zones (ohne Auto-Kalibrierung): HOD/LOD, Modus-Vergleich, Strategie-Suche (Status: **verworfen** – LOG #4–#6, 2026-10-19; Bericht `results/gz_report.md`)
**Auftrag (Nutzer, 2026-10-19):** Wie oft liefern die Zonen HOD/LOD je Modus und Asset, wie groß ist die Reaktion, welche Konfluenzen
gab es, und lässt sich daraus eine Strategie mit Alpha bauen?

### Vorab festgelegtes Vorgehen (2026-10-19, vor jeder Auswertung)
- **Indikator exakt wie Pine-Code:** Anker = erstes Open der Session (18:00 ET), σ = Open × Wert/100/√252, Wert = letzter Schluss vor
  dem Anker. NQ: 1D = VIX1D·VXN/VIX, 9D = VIX9D·VXN/VIX, 30D = VXN (Fallback 30D, wenn 1D/9D fehlt – wie im Code).
  ES und RTY (Code: weder NQ noch GC): VIX1D / VIX9D / VIX. GC: GVZ in jedem Modus. Zonen ±0,5/1/1,5/2σ, Box ±5 % von σ. Keine Kalibrierung.
- **Zeiträume:** Explore bis 2024-12-31 · Validate 2025-01-01 bis 2026-04-16 · **Holdout ab 2026-04-17 unberührt**.
  1D-Daten gibt es erst ab Mai 2022.
- **Teil A (beschreibend, keine Tests):** HOD/LOD in Zonen-Box vs. gleich breite Kontroll-Bänder dazwischen; „wenn berührt, war es das
  Extrem“; Reaktion in Punkten und σ; Konfluenzen (Vortag H/T, Overnight H/T, IB H/T, RTH-VWAP ±2σ, Wochen-Zonen, Zonen anderer Modi,
  100er) – immer im Vergleich Zone vs. Kontroll-Band.
- **Teil B (Strategie-Suche, nur Explore):** Ereignis = erste Berührung einer Zonen-Box an einem Tag. Feste Trade-Vorlagen
  (Fade und Durchbruch, Stop/Ziel in σ). Bedingungen aus Mechanismus-Überlegungen (Uhrzeit, Restbewegung, Range verbraucht, Event-Tag,
  Modus-Konfluenz u. a.). **Jede ausprobierte Variante wird gezählt.** Kandidat nur, wenn: EW netto > 0 in Explore, positiv in jedem
  Explore-Jahr mit ≥ 30 Trades, in ≥ 2 Märkten gleiches Vorzeichen, und ein Mechanismus benannt ist. Höchstens 5 Kandidaten.
- **Teil C (Prüfung):** Kandidaten unverändert auf Validate, gegen Zufall (gleiche Stunde, gleicher Stop/Ziel, 1.000×), Holm über alle
  Kandidaten. Erfolg: Holm-p < 0,05, EW netto > 0, KI-Untergrenze > 0, ≥ 30 Trades.
- **Kosten je Round-Trip:** NQ 1,0 · ES 0,5 · RTY 0,3 · GC 0,4 Punkte.

## H8 – RTY-Skalierung im Indikator (Status: im HAR-Modus gelöst, 2026-10-19; IV-Modi für RTY weiter zu eng)
RTY nutzt im Pine-Code die VIX-Familie. Reaktionen/Ranges liegen bei 1,0–1,45σ statt ~0,8σ → σ zu klein. RVX-Skalierung
(RVX bzw. VIX1D·RVX/VIX) prüfen: Schluss in ±1σ soll ~68 % ergeben.

## H9 – Intraday-VWAP-Strategie (1–3 Setups/Tag, Prop-Firm-tauglich) (Status: **verworfen** – LOG #9/#10; Momentum nur bis 2019)
**Auftrag (Nutzer, 2026-10-19):** Selbstständig eine Intraday-Strategie mit Edge finden, Startpunkt VWAP (Session-/RTH-VWAP,
±1/2/3σ-Bänder, Multi-Timeframe-/Multi-Session-VWAP). Märkte NQ, ES, RTY, GC. Drawdown möglichst klein (Prop-Firm). Nur vorhandene Daten.

### Vorab festgelegtes Vorgehen (2026-10-19, vor jeder Auswertung)
- **Vier Datentöpfe:** Explore 2011–2019 (suchen) · Validate 2020–2024 (erste Prüfung, unverändert) · Test 2025-01 bis 2026-04-16
  (zweite Prüfung) · **Holdout ab 2026-04-17 unberührt** (nur mit Freigabe des Nutzers, einmal, für den finalen Kandidaten).
  RTY erst ab 2017-07 (Explore dort kürzer).
- **Trades:** Signal bei Kerzenschluss (1m), Einstieg Open der nächsten Minute. Stop vor Ziel bei gleicher Kerze. Spätestens flat zum
  RTH-Ende (Index 15:59, GC 13:29) bzw. Session-Ende bei Nacht-Setups. Max. 3 Trades/Tag/Markt, keine Überlappung.
  Kosten je Round-Trip: NQ 1,0 · ES 0,5 · RTY 0,3 · GC 0,4 Punkte (Kommission + Slippage).
- **Suche:** Setup-Familien mit Mechanismus (Band-Fade, Trend-Pullback an VWAP, Reclaim, Eröffnungs-Position zu VWAPs,
  Schluss-Rücklauf zu VWAP, Multi-Anker-/Multi-Session-VWAP), jeweils kleines festes Parameter-Gitter. **Jede Variante wird gezählt.**
- **Auswahl für Validate (nur aus Explore):** EW netto > 0, Profit Factor ≥ 1,15, positiv in ≥ 70 % der Explore-Jahre,
  Nachbar-Parameter ebenfalls positiv (Plateau statt Spitze), Mechanismus benannt. Höchstens 5 Kandidaten.
- **Validate/Test:** Kandidaten unverändert. Erfolg: EW netto > 0 mit 95 %-KI-Untergrenze > 0 (Bootstrap über Tage), PF ≥ 1,1,
  besser als Zufall (gleiche Uhrzeit/Richtung/Stop/Ziel, 1.000×), Holm über alle Kandidaten – in Validate UND Test.
- **Prop-Kennzahlen:** Max Drawdown (Punkte und $ je Kontrakt), schlechtester Tag, Gewinntage %, Trades/Tag, Sharpe der Tages-P&L.

## H10 – Intraday-VWAP-Strategie im neuen Regime (seit 2022) (Status: **verworfen** – Landkarte 2022–23 zeigt Momentum, keine Reversion)
**Begründung:** H9 zeigt einen Strukturbruch: VWAP-Momentum bis 2019 stark, ab 2020 weg. Literatur: 0DTE-Volumen seit 2022 stark
gestiegen, Market Maker meist long Gamma → Hedging dämpft Momentum, fördert Reversals (Dim/Eraker/Vilkov; Amaya et al.).
Hypothese: Seit 2022 funktionieren eher Rücklauf-/Fade-Setups am VWAP bzw. an den Bändern; Momentum-Setups nicht.

### Vorab festgelegt (2026-10-19, bevor irgendein H9/H10-Ergebnis nach 2019 für Fade-Familien angesehen wurde)
- **Zeiträume neu:** Explore 2022-01-01 bis 2023-12-31 · Validate 2024-01-01 bis 2025-06-30 · Test 2025-07-01 bis 2026-04-16 ·
  Holdout ab 2026-04-17 unberührt. Hinweis: Momentum-Kandidaten K1–K3 wurden auf 2020–2026 schon geprüft – Momentum-Familien
  werden in H10 nicht erneut als Kandidaten zugelassen.
- Alle anderen Regeln wie H9 (Ausführung, Kosten, max. 3 Trades/Tag, Kandidaten-Kriterien, Prüfung, Prop-Kennzahlen).
  Jahres-Konsistenz-Kriterium ersetzt durch: positiv in jedem Explore-Halbjahr (4 Halbjahre) mit ≥ 20 Trades.

## H11 – VWAP-Momentum-Portfolio (4 Märkte × 3 Zeitpunkte) (Status: **verworfen** – Explore negativ in allen 16 Varianten; K1/K3 waren Uhrzeit-Spitzen)
**Begründung:** VWAP-Momentum zeigt sich 2011–2019 und (beschreibend) 2022–23; Einzel-Setups scheiterten an zu wenigen Trades.
Ein Portfolio (NQ, ES, RTY, GC; Prüfzeitpunkte RTH+60/+150/+270 Min.) erhöht die Stichprobe auf ~1–3 Setups/Tag.

### Vorab festgelegt (2026-10-19)
- **Regel je Markt:** zu jedem Prüfzeitpunkt, wenn flat: |z_RTH| ≥ k und Preis auf derselben Seite von Session-, Wochen- und Monats-VWAP
  (bzw. nur Monat) → Trade in Richtung z; Stop VWAP ∓ 0,5σ (zum Signalzeitpunkt); Ausstieg RTH-Ende. Max. 3 Trades/Tag/Markt, keine Überlappung.
  Variante mit Energie-Filter (Range bisher ≥ 0,6 ATR). Gitter: k ∈ {1,0; 1,5} × Ausrichtung {alle, Monat} × Zeitpunkte {3, nur 10:30+12:00}
  × Filter {ohne, Range ≥ 0,6 ATR} = 16 Varianten. Portfolio-Ergebnis in R (Gewinn / Stop-Abstand), alle Märkte gleich gewichtet.
- **Auswahl (nur Explore 2011–2019):** wie H9 (EW > 0, PF ≥ 1,15, ≥ 70 % Jahre positiv, Plateau, max. 2 Kandidaten).
- **Prüfung:** Validate 2020–2024 wird berichtet, ist aber durch die H10-Landkarte (2022–23) teilweise bekannt → nicht entscheidend.
  **Entscheidend: Test 2025-01-01 bis 2026-04-16** (EW in R > 0 mit KI-Untergrenze > 0 über Tage, PF ≥ 1,1, besser als Zufall, Holm über
  alle bisher geprüften Kandidaten K1–K3 + neue). Danach Holdout nur mit Freigabe.

## H12 – Intraday-Periodizität (Heston/Korajczyk/Sadka 2010) (Status: **verworfen** – Explore: brutto ≈ 0 in allen 4 Märkten)
**Mechanismus:** Große Marktteilnehmer handeln wiederkehrend zu festen Uhrzeiten → Renditen eines Halbstunden-Fensters setzen sich
im selben Fenster an Folgetagen fort (für Aktien belegt).
### Vorab festgelegt (2026-10-19)
- RTH in Halbstunden-Fenster (Index 13, GC 10). Signal für Fenster h an Tag t: Ø Rendite im Fenster h der letzten L Tage (L ∈ {20, 40, 60}),
  t-Wert |t| ≥ τ (τ ∈ {0; 1,0; 1,5}). Trade: Einstieg Open zu Fensterbeginn, Richtung = Vorzeichen, Ausstieg Close am Fensterende, kein Stop.
  Max. 3 Trades/Tag/Markt: die 3 Fenster mit dem größten |t|. Kosten wie H9. 9 Varianten × 4 Märkte.
- Zeiträume und Prüfregeln wie H9 (Explore 2011–2019, Validate 2020–2024, Test 2025–04/2026, Holdout unberührt).

## H13 – Event-Tage intraday (08:30 / 10:00 / 14:00 ET) (Status: in Arbeit)
**Mechanismus:** Makro-Zahlen (CPI, NFP, PPI, Retail Sales …) und FOMC-Entscheidungen bringen neue Information; die Verarbeitung ist
nicht immer sofort abgeschlossen → Drift in Richtung der ersten Reaktion möglich (Fortsetzung) – oder bekannte FOMC-Umkehr (Reversal).
### Vorab festgelegt (2026-10-19)
- **Event-Erkennung aus den Daten (ohne Termin-Liste):** Volumen in den ersten 5 Minuten ab 08:30 / 10:00 / 14:00 ET ≥ R × Median
  derselben 5 Minuten der letzten 20 Tage (R ∈ {4, 8}); nur Index-Märkte + GC. Erkennbar zum Zeitpunkt E+5 Min. (kein Blick in die Zukunft).
- **Trades (je Event-Tag max. 1 pro Uhrzeit):** Bei E+M (M ∈ {5, 15, 30} Min.) Richtung = Vorzeichen (Close − Preis vor dem Event).
  Varianten: **Fortsetzung** (mit der Reaktion) und **Umkehr** (gegen die Reaktion). Stop: Preis vor dem Event (Fortsetzung) bzw.
  Event-Extrem bis E+M (Umkehr). Ausstieg: E+60 Min., E+120 Min. oder RTH-Ende (08:30-Events: Ausstieg frühestens 09:30+).
  Gitter: 3 Uhrzeiten × R 2 × M 3 × Richtung 2 × Ausstieg 3 = 108 Varianten je Markt.
- Zeiträume und Prüfung wie H9 (Explore 2011–2019, Validate 2020–2024, Test 2025–04/2026, Holdout unberührt); Kandidaten-Kriterien wie H9,
  Plateau zusätzlich über M (Nachbar-Minuten) und über ≥ 2 Märkte gleiches Vorzeichen.
