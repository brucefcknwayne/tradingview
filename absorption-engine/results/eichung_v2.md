# Absorption Engine – Eichung auf NQ 1m (2026-09-21 … 2026-10-16, 20 Tage, Databento trades; REFILL nicht prüfbar)

Parameter: {"lookback": 100, "swing": 60, "minStrength": 70, "flipBody": 0.4, "flipDelta": 1.5, "effVol": 2.5, "effRatio": 0.4, "wickZone": 0.25, "wickShare": 0.35, "wickDom": 3.0, "wickLen": 0.5, "wallMult": 2.5, "wallBal": 0.15, "trapDelta": 2.0, "exhGrowth": 3.0, "heldAtr": 0.5, "failAtr": 0.15, "maxBars": 20}

Ereignisse gesamt 2417 · pro Tag 120.8 · RTH pro Tag 46.0 · Overnight pro Tag 74.8

Arten (Anzahl, ein Ereignis kann mehrere haben):

|         |   pro Tag |
|:--------|----------:|
| EFFORT  |      43   |
| CVD     |      32.4 |
| FLIP    |      14.7 |
| EXHAUST |      13.4 |
| TRAPPED |      12.4 |
| WALL    |       9   |
| WICK    |       7.6 |

Ergebnis Engine: HELD 68.8 % · FAILED 31.1 % · EXPIRED 0.1 %
Zufall (gleiche Stunde/Richtung, 20×): HELD 59.9 % · FAILED 40.0 % · EXPIRED 0.0 %
Fairer Test – zuerst ±1 ATR ab Schluss in Absorptions-Richtung: Engine 50.3 % (n 2386), Zufall 46.7 %

| Art           |   Ereignisse |   pro RTH-Tag |   HELD % |   FAILED % |   ±1 ATR richtig % |
|:--------------|-------------:|--------------:|---------:|-----------:|-------------------:|
| FLIP          |          294 |           2   |     78.6 |       21.1 |               48.4 |
| EFFORT        |          861 |          24.4 |     54.9 |       45.1 |               46.7 |
| WICK          |          151 |           0.1 |     66.2 |       33.8 |               49.3 |
| WALL          |          180 |           7   |     80.6 |       19.4 |               53.5 |
| CVD           |          649 |          11.6 |     76.7 |       23   |               53.6 |
| TRAPPED       |          249 |           2.6 |     91.6 |        8.4 |               48   |
| EXHAUST       |          267 |           4   |     61.8 |       38.2 |               53.2 |
| Stärke 60–79  |          392 |           3.8 |     68.1 |       31.9 |               49.4 |
| Stärke 80–100 |         2025 |          42.2 |     68.9 |       31   |               50.5 |