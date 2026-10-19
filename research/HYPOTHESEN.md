# Hypothesen

Status: offen · getestet · verworfen · Kandidat

## H1 – Zera-Reversal (Status: getestet → siehe LOG #1)

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
