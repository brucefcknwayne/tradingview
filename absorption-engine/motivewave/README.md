# Absorption Engine (MotiveWave)

Study für MotiveWave mit Rithmic-Daten: zeigt Absorption aus dem Orderflow mit 10 Modi und einer „x/10“-Konfluenz.

## Installieren
1. `dist/AbsorptionEngine.jar` in den Ordner **MotiveWave Extensions** kopieren (macOS: `~/MotiveWave Extensions/`).
2. MotiveWave neu starten. Die Study liegt unter **Study → Gotham → Absorption Engine**.
3. Chart mit Zeit-Kerzen öffnen (getestet ist die Logik auf 1 Minute). Die Engine braucht Tick-Daten (Rithmic liefert sie).
   Für Modus 5 (Refill/Iceberg) müssen die Ticks Bid/Ask-Größen enthalten.

Kompiliert mit JDK 25 gegen `mwave_sdk.jar` (Stand 18.09.2026). Quelle: `src/com/gotham/AbsorptionEngine.java`.

## Die 10 Modi
| # | Modus | Bedeutung |
|---|---|---|
| 1 | FLIP | rote Kerze mit positivem Delta (bärisch) bzw. grüne mit negativem Delta (bullisch) |
| 2 | EFFORT | Volumen weit über normal, Range dafür klein |
| 3 | WICK | Aggressoren hauen ins Extrem, Docht weist zurück |
| 4 | WALL | Preiszeile mit ungewöhnlich viel Volumen bei Delta ≈ 0 am Extrem |
| 5 | REFILL | an einem Preis wird ein Vielfaches der sichtbaren Bid-/Ask-Größe gehandelt (Iceberg) |
| 6 | CVD | neues Swing-Extrem ohne CVD-Bestätigung |
| 7 | TRAPPED | starker Push auf neues Extrem, nächste Kerze schließt hinter dessen Open |
| 8 | EXHAUST | drei Kerzen in eine Richtung, Volumen je Preisfortschritt wird immer teurer |
| 9 | STACKED | gestapelte diagonale Imbalances am Extrem, Kerze schließt auf der anderen Seite |
| 10 | D-REV | Delta war in der Kerze stark, kippt bis zum Schluss fast vollständig |

Alle Schwellen sind relativ (Median der letzten 100 Kerzen, Anteil der Kerzen-Range, ATR) – keine festen Ticks.

## Anzeige
- Dreieck unter/über der Kerze, Text `2/10 CVD+WALL` = 2 Modi gleichzeitig. Größe des Dreiecks wächst mit der Anzahl.
- Label rechts (live): `ABSORBING ▲ 2/10 …`, `BREAKING …` (letzte Absorption bricht) oder `WAITING`, dazu held/failed-Quote.
- Signale für Alerts: Bullische/Bärische Absorption, gehalten, gebrochen. Optional CSV-Log (Pfad in den Einstellungen).
