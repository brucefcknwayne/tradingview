# Absorption Engine – Eichung auf NQ 1m (2026-09-21 … 2026-10-16, 20 Tage, Databento trades; REFILL nicht prüfbar)

Parameter: {"lookback": 100, "swing": 30, "minStrength": 60, "flipBody": 0.3, "flipDelta": 1.0, "effVol": 2.0, "effRatio": 0.5, "wickZone": 0.25, "wickShare": 0.25, "wickDom": 2.0, "wickLen": 0.5, "wallMult": 2.0, "wallBal": 0.2, "trapDelta": 1.5, "exhGrowth": 2.0, "heldAtr": 0.5, "failAtr": 0.15, "maxBars": 20}

Ereignisse gesamt 4866 · pro Tag 243.3 · RTH pro Tag 71.2 · Overnight pro Tag 172.1

Arten (Anzahl, ein Ereignis kann mehrere haben):

|         |   pro Tag |
|:--------|----------:|
| EFFORT  |      82.5 |
| CVD     |      52   |
| FLIP    |      40.8 |
| WICK    |      39.8 |
| EXHAUST |      24.6 |
| TRAPPED |      21.3 |
| WALL    |      14.2 |

Ergebnis Engine: HELD 69.6 % · FAILED 30.3 % · EXPIRED 0.1 %
Zufall (gleiche Stunde/Richtung, 20×): HELD 60.1 % · FAILED 39.9 % · EXPIRED 0.0 %
Fairer Test – zuerst ±1 ATR ab Schluss in Absorptions-Richtung: Engine 50.3 % (n 4804), Zufall 47.6 %

| Art           |   Ereignisse |   pro RTH-Tag |   HELD % |   FAILED % |   ±1 ATR richtig % |
|:--------------|-------------:|--------------:|---------:|-----------:|-------------------:|
| FLIP          |          815 |           6   |     79.9 |       20   |               50.6 |
| EFFORT        |         1650 |          34.2 |     56.5 |       43.5 |               49.4 |
| WICK          |          797 |           1.8 |     73.8 |       26.2 |               48.5 |
| WALL          |          285 |           9.4 |     82.5 |       17.5 |               53.1 |
| CVD           |         1040 |          18   |     77.3 |       22.4 |               52   |
| TRAPPED       |          426 |           4.6 |     94.1 |        5.9 |               47.5 |
| EXHAUST       |          492 |           7.6 |     53.9 |       46.1 |               51.3 |
| Stärke 60–79  |         1673 |          15.6 |     71.4 |       28.5 |               49.6 |
| Stärke 80–100 |         3193 |          55.6 |     68.7 |       31.2 |               50.6 |