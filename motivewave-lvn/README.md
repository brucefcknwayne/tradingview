# MotiveWave-LVN ("Cracks") → TradingView

Ziel: die LVN-Linien der eingebauten MotiveWave-Study *Volume Profile* (90 Day, Tick Interval 4,
Sensitivity 10, Use Historical Minute Bars an) exakt 1:1 in TradingView anzeigen.

| Datei | Zweck |
|---|---|
| `LvnFileExport.java` | Baustein für MotiveWave: schreibt die LVN-Preise nach `~/Documents/MotiveWave_Cracks/<SYMBOL>.txt` |
| `Cracks_indicator.pine` | TradingView-Indikator: zeigt eingefügte Preise als gelbe, gestrichelte Linien mit Preisschild |

## Weg zu 1:1

1. Offiziellen Quellcode der Volume-Profile-Study bei MotiveWave holen (SDK-Seite, Quellcode-Paket der
   eingebauten Studies; sonst Support-Anfrage).
2. Als eigene Study kompilieren (neue `namespace`/`id`), `LvnFileExport.export(...)` an der Stelle aufrufen,
   an der die LVN-Linien gezeichnet werden.
3. Mit gleichen Einstellungen neben die Original-Study legen, Linien vergleichen.
4. Datei öffnen, Inhalt in das passende Feld des Pine-Indikators einfügen (täglich, weil 90 Tage rollierend).

## Belegt / vermutet

- Belegt: `getLVNs(int)` liefert Zeilen-Indizes in `getRows()`, keine Preise.
- Belegt (Forum): "Use Historical Minute Bars" verteilt das Volumen einer Minutenkerze gleichmäßig
  zwischen Hoch und Tief; ab Programmstart werden echte Ticks verwendet.
- Vermutet: Linien liegen auf der Mitte einer 4-Tick-Zeile (NQ: 1 Punkt → Preise auf .50).
- Vermutet: kein offizieller Weg, die Linien einer anderen Study per SDK auszulesen.
