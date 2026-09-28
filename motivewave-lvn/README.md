# MotiveWave-LVN ("Cracks") → TradingView

Ziel: die LVN-Linien der eingebauten MotiveWave-Study *Volume Profile* (90 Day, Tick Interval 4,
Sensitivity 10, Use Historical Minute Bars an) exakt 1:1 in TradingView anzeigen.

| Datei | Zweck |
|---|---|
| `LvnFileExport.java` | Baustein für MotiveWave: schreibt die LVN-Preise nach `~/Documents/MotiveWave_Cracks/<SYMBOL>.txt` |
| `cracks_from_screenshot.py` | Weg ohne MotiveWave-Support: liest die Cracks aus einem Screenshot (Linie per Pixel, Schild per OCR, gegenseitige Prüfung) |
| `Cracks_indicator.pine` | TradingView-Indikator: zeigt eingefügte Preise als gelbe, gestrichelte Linien mit Preisschild |

## Weg ohne MotiveWave-Support (Screenshot)

1. Einmalig: `brew install tesseract` und `pip3 install numpy pillow pytesseract`.
2. MotiveWave: Chart so hoch wie möglich, Preisachse linear, alle Cracks sichtbar.
   Cmd+Shift+4 → Leertaste → Chartfenster anklicken (Retina-Auflösung).
3. `python3 cracks_from_screenshot.py ~/Desktop/<Bildschirmfoto>.png --copy`
4. Mit "PRÜFEN" markierte Werte (meist überlappende Schilder) kurz im Chart ansehen.
5. In TradingView in "Cracks · MotiveWave LVN" → Feld NQ einfügen.

Jede Linie wird zweimal bestimmt: über die Pixel-Höhe (Raster x.50) und über ihr eigenes Schild
(nur Gelb, zwei OCR-Läufe müssen übereinstimmen). Nur wenn beides passt, gilt der Wert als bestätigt.

## Weg mit Quellcode (Alternative)

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
