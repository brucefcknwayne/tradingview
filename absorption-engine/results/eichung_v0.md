# Absorption Engine – Eichung auf NQ 1m (2026-09-21 … 2026-10-16, 20 Tage, Databento trades; REFILL nicht prüfbar)

Parameter: {"lookback": 100, "swing": 20, "minStrength": 40, "flipBody": 0.3, "flipDelta": 0.8, "effVol": 1.5, "effRatio": 0.6, "wickZone": 0.25, "wickShare": 0.15, "wickDom": 1.3, "wickLen": 0.35, "wallMult": 1.5, "wallBal": 0.2, "trapDelta": 1.5, "exhGrowth": 2.0, "heldAtr": 0.5, "failAtr": 0.15, "maxBars": 20}

Ereignisse gesamt 11010 · pro Tag 550.5 · RTH pro Tag 139.6 · Overnight pro Tag 410.9

Arten (Anzahl, ein Ereignis kann mehrere haben):

|         |   pro Tag |
|:--------|----------:|
| WICK    |     306.8 |
| EFFORT  |     148   |
| CVD     |      72.6 |
| FLIP    |      51   |
| WALL    |      27.8 |
| EXHAUST |      25.7 |
| TRAPPED |      24.3 |

Ergebnis Engine: HELD 69.2 % · FAILED 30.7 % · EXPIRED 0.1 %
Zufall (gleiche Stunde/Richtung, 20×): HELD 61.1 % · FAILED 38.9 % · EXPIRED 0.1 %
Fairer Test – zuerst ±1 ATR ab Schluss in Absorptions-Richtung: Engine 49.8 % (n 10883), Zufall 48.5 %

| Art           |   Ereignisse |   pro RTH-Tag |   HELD % |   FAILED % |   ±1 ATR richtig % |
|:--------------|-------------:|--------------:|---------:|-----------:|-------------------:|
| FLIP          |         1021 |           7.8 |     80   |       19.9 |               51.3 |
| EFFORT        |         2961 |          47.3 |     57.3 |       42.7 |               50.3 |
| WICK          |         6137 |          56.8 |     72.1 |       27.8 |               49.6 |
| WALL          |          557 |          14.2 |     82.6 |       17.4 |               51.3 |
| CVD           |         1453 |          26.7 |     77.5 |       22.4 |               51.3 |
| TRAPPED       |          486 |           5   |     94.7 |        5.3 |               48.1 |
| EXHAUST       |          514 |           7.9 |     54.3 |       45.7 |               51.5 |
| Stärke 40–59  |          303 |           6   |     73.6 |       26.1 |               49   |
| Stärke 60–79  |         4766 |          57.8 |     67.1 |       32.8 |               49.1 |
| Stärke 80–100 |         5941 |          75.8 |     70.7 |       29.2 |               50.4 |