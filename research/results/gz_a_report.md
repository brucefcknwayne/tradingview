# Gotham Zones (ohne Kalibrierung) – HOD/LOD, Modi, Reaktion, Konfluenz

Tag = Session 18:00–17:00 ET. Zone = Level ± 5 % σ (Box wie im Indikator). Kontrolle = gleich breite Bänder bei ±0,25/0,75/1,25/1,75σ.
Explore bis 2024, Validate 2025–04/2026, Holdout nicht enthalten. 1D erst ab Mai 2022.

## 1) HOD/LOD in Zone vs. Kontrolle

| Markt   | Modus   | Zeitraum   |   Tage |   Ø σ Punkte |   HOD in Zone % |   HOD in Kontrolle % |   LOD in Zone % |   LOD in Kontrolle % |   Zone − Nachbarn (Pkt-%) |   wenn berührt → Extrem: Zone − Nachbarn (Pkt-%) |
|:--------|:--------|:-----------|-------:|-------------:|----------------:|---------------------:|----------------:|---------------------:|--------------------------:|-------------------------------------------------:|
| NQ      | 1D      | Explore    |    681 |        190.6 |            16.9 |                 19.8 |            15.6 |                 18.2 |                      0.2  |                                             1.55 |
| NQ      | 1D      | Validate   |    332 |        274.2 |            11.4 |                 20.5 |            14.2 |                 21.1 |                     -0.9  |                                            -2.23 |
| NQ      | 9D      | Explore    |   3585 |        107.4 |            16.4 |                 20   |            13.7 |                 18.9 |                      0.1  |                                            -0.29 |
| NQ      | 9D      | Validate   |    332 |        307.1 |            15.4 |                 22.3 |            13.3 |                 22.9 |                     -0.81 |                                            -3.81 |
| NQ      | 30D     | Explore    |   3587 |        113.2 |            16   |                 19   |            13.7 |                 18.9 |                      0.25 |                                             2.45 |
| NQ      | 30D     | Validate   |    332 |        328.8 |            10.8 |                 24.4 |            16.6 |                 17.2 |                     -0.38 |                                             1.94 |
| ES      | 1D      | Explore    |    681 |         46.2 |            15.6 |                 19.1 |            13.7 |                 17.8 |                      0.05 |                                            -0.47 |
| ES      | 1D      | Validate   |    332 |         64.8 |            13.6 |                 19   |            14.5 |                 19.9 |                     -0.19 |                                            -3.05 |
| ES      | 9D      | Explore    |   3589 |         31.2 |            14.9 |                 20.6 |            13.6 |                 18.9 |                     -0.07 |                                             0.57 |
| ES      | 9D      | Validate   |    332 |         72.1 |            13   |                 21.1 |            11.7 |                 21.1 |                     -0.83 |                                            -3.4  |
| ES      | 30D     | Explore    |   3591 |         32.7 |            14   |                 20.9 |            13.3 |                 18.2 |                     -0.09 |                                            -0.63 |
| ES      | 30D     | Validate   |    332 |         76.8 |            13.6 |                 19.9 |            14.8 |                 20.8 |                     -0.04 |                                             2.11 |
| RTY     | 1D      | Explore    |    680 |         19.7 |            16.2 |                 18.7 |            13.8 |                 17.2 |                      0.01 |                                             1.01 |
| RTY     | 1D      | Validate   |    332 |         23.7 |            20.8 |                 19.6 |            15.4 |                 15.4 |                      0.73 |                                             1.53 |
| RTY     | 9D      | Explore    |   1873 |         20.8 |            14.6 |                 17.5 |            14.3 |                 18.3 |                     -0.09 |                                            -0.37 |
| RTY     | 9D      | Validate   |    332 |         26.4 |            15.4 |                 21.4 |            14.5 |                 17.8 |                     -0.38 |                                            -0.86 |
| RTY     | 30D     | Explore    |   1873 |         21.8 |            15.7 |                 17.6 |            15.3 |                 17.8 |                      0.29 |                                             0.64 |
| RTY     | 30D     | Validate   |    332 |         28.1 |            13.9 |                 19.9 |            16.3 |                 15.7 |                      0.21 |                                             1.62 |
| GC      | GVZ     | Explore    |   3595 |         16.9 |            14.8 |                 19.2 |            14.2 |                 19.5 |                     -0.01 |                                             0.51 |
| GC      | GVZ     | Validate   |    331 |         55.8 |            17.2 |                 19   |            13   |                 19.3 |                      0.08 |                                             2.16 |

## 2) Je Stufe: wie oft berührt, und wenn berührt – wie oft war es das Tages-Extrem?

| Markt   | Modus   | Zeitraum   |   ±0.5σ berührt % |   ±0.5σ berührt→Extrem % |   ±1σ berührt % |   ±1σ berührt→Extrem % |   ±1.5σ berührt % |   ±1.5σ berührt→Extrem % |   ±2σ berührt % |   ±2σ berührt→Extrem % |
|:--------|:--------|:-----------|------------------:|-------------------------:|----------------:|-----------------------:|------------------:|-------------------------:|----------------:|-----------------------:|
| NQ      | 1D      | Explore    |              61.8 |                     13.3 |            29.4 |                   15   |              13.6 |                     19.5 |             5.2 |                   18.3 |
| NQ      | 1D      | Validate   |              62.2 |                      9.7 |            31.5 |                   12.9 |              12.5 |                     13.3 |             4.8 |                   21.9 |
| NQ      | 9D      | Explore    |              56.2 |                     15.6 |            23.3 |                   17.6 |               8.9 |                     18.7 |             2.9 |                   17.6 |
| NQ      | 9D      | Validate   |              57.2 |                     13.2 |            26.7 |                   19.8 |               9.2 |                     11.5 |             2.9 |                   15.8 |
| NQ      | 30D     | Explore    |              53.4 |                     16.3 |            21.5 |                   18.2 |               8   |                     21   |             2.7 |                   20.7 |
| NQ      | 30D     | Validate   |              54.5 |                     14.1 |            22.7 |                   18.5 |               8.4 |                     17.9 |             2   |                   15.4 |
| ES      | 1D      | Explore    |              58.8 |                     14.7 |            26.4 |                   13.9 |              10   |                     19.1 |             3.5 |                   10.4 |
| ES      | 1D      | Validate   |              59.6 |                     14.1 |            25.3 |                   13.1 |               8.7 |                     19   |             3.5 |                   17.4 |
| ES      | 9D      | Explore    |              52.6 |                     16.3 |            19.9 |                   19.2 |               6.5 |                     20.7 |             2.2 |                   22.6 |
| ES      | 9D      | Validate   |              52.7 |                     13.4 |            20.8 |                   14.5 |               6.9 |                     26.1 |             2.1 |                   21.4 |
| ES      | 30D     | Explore    |              49.8 |                     17.3 |            18.3 |                   19.1 |               6.1 |                     19.8 |             1.8 |                   19.2 |
| ES      | 30D     | Validate   |              50.3 |                     17.7 |            18.2 |                   16.5 |               6.3 |                     31   |             1.5 |                   20   |
| RTY     | 1D      | Explore    |              71.8 |                      8.5 |            45   |                    8   |              28.7 |                     11   |            16.2 |                   13.1 |
| RTY     | 1D      | Validate   |              73.8 |                      9.6 |            47.9 |                   10.4 |              28.5 |                     14.8 |            13.9 |                   13   |
| RTY     | 9D      | Explore    |              68.2 |                      9   |            38.9 |                   11.2 |              20.1 |                     12.9 |             9.3 |                   14.3 |
| RTY     | 9D      | Validate   |              69.4 |                      9.8 |            40.8 |                   10.3 |              19.9 |                     12.1 |             9.6 |                   15.6 |
| RTY     | 30D     | Explore    |              66.2 |                     10.6 |            36.1 |                   13.5 |              17.6 |                     13.8 |             7.7 |                   15   |
| RTY     | 30D     | Validate   |              65.4 |                      8.5 |            36.6 |                   14.4 |              17.3 |                     16.5 |             7.7 |                   17.6 |
| GC      | GVZ     | Explore    |              55.9 |                     14.7 |            23.9 |                   16.5 |               9.3 |                     19.4 |             3.3 |                   16.9 |
| GC      | GVZ     | Validate   |              59.4 |                     12.5 |            29.2 |                   13   |              13.1 |                     21.8 |             5   |                   21.2 |

## 3) Reaktion nach dem Extrem (Punkte bis zum Gegen-Extrem danach)

| Markt   | Modus   | Extrem   | Lage      |   Tage |   Reaktion danach Median Pkt |   Reaktion danach Median σ |   Reaktion danach 25 % Pkt |   Reaktion danach 75 % Pkt |   bis Schluss Median Pkt |   Extrem in RTH % | Ø Uhrzeit Extrem (ET)   |
|:--------|:--------|:---------|:----------|-------:|-----------------------------:|---------------------------:|---------------------------:|---------------------------:|-------------------------:|------------------:|:------------------------|
| NQ      | 1D      | HOD      | Zone      |    153 |                        143.5 |                       0.76 |                       60   |                      249   |                     79   |              65.4 | 11:43                   |
| NQ      | 1D      | HOD      | Kontrolle |    203 |                        174.2 |                       0.92 |                       71.6 |                      299.5 |                    104.8 |              56.2 | 10:21                   |
| NQ      | 1D      | HOD      | sonst     |    657 |                        185.5 |                       0.91 |                       82.2 |                      311   |                    103   |              49.9 | 10:19                   |
| NQ      | 1D      | LOD      | Zone      |    153 |                        187.8 |                       0.91 |                       97   |                      280.5 |                    127.5 |              66.7 | 11:46                   |
| NQ      | 1D      | LOD      | Kontrolle |    194 |                        216.9 |                       1.04 |                      115.9 |                      316.9 |                    145.4 |              52.1 | 10:02                   |
| NQ      | 1D      | LOD      | sonst     |    666 |                        208.8 |                       1.07 |                      125   |                      313.2 |                    142.8 |              44.6 | 09:35                   |
| NQ      | 9D      | HOD      | Zone      |    638 |                         45   |                       0.62 |                       17.2 |                      115.4 |                     24.8 |              61.1 | 11:40                   |
| NQ      | 9D      | HOD      | Kontrolle |    790 |                         47.4 |                       0.69 |                       19.3 |                      127.7 |                     29.8 |              50.5 | 10:49                   |
| NQ      | 9D      | HOD      | sonst     |   2489 |                         53.8 |                       0.76 |                       22.2 |                      154   |                     31.8 |              49.2 | 10:21                   |
| NQ      | 9D      | LOD      | Zone      |    535 |                         57   |                       0.79 |                       26.1 |                      152.1 |                     42   |              67.5 | 10:47                   |
| NQ      | 9D      | LOD      | Kontrolle |    753 |                         70.2 |                       0.87 |                       32.8 |                      186.8 |                     50   |              54.8 | 10:01                   |
| NQ      | 9D      | LOD      | sonst     |   2629 |                         62.8 |                       0.89 |                       29.8 |                      162   |                     45.2 |              46.3 | 09:44                   |
| NQ      | 30D     | HOD      | Zone      |    609 |                         45   |                       0.57 |                       17.2 |                      116.2 |                     24.8 |              64.5 | 11:55                   |
| NQ      | 30D     | HOD      | Kontrolle |    764 |                         48.2 |                       0.68 |                       22   |                      132.4 |                     29.8 |              53.4 | 10:42                   |
| NQ      | 30D     | HOD      | sonst     |   2546 |                         53.2 |                       0.71 |                       21.5 |                      150.1 |                     31.5 |              47.6 | 10:20                   |
| NQ      | 30D     | LOD      | Zone      |    548 |                         60.2 |                       0.8  |                       27.5 |                      161.9 |                     42.9 |              66.1 | 10:56                   |
| NQ      | 30D     | LOD      | Kontrolle |    735 |                         62.5 |                       0.79 |                       30.9 |                      167.2 |                     44.8 |              55.6 | 09:59                   |
| NQ      | 30D     | LOD      | sonst     |   2636 |                         63.8 |                       0.84 |                       30   |                      164.5 |                     46.2 |              46.3 | 09:43                   |
| ES      | 1D      | HOD      | Zone      |    151 |                         39.2 |                       0.73 |                       20.8 |                       66   |                     25   |              68.9 | 11:56                   |
| ES      | 1D      | HOD      | Kontrolle |    193 |                         35   |                       0.82 |                       17.8 |                       72   |                     21.8 |              53.9 | 10:54                   |
| ES      | 1D      | HOD      | sonst     |    669 |                         36.5 |                       0.79 |                       14.5 |                       65.2 |                     20   |              48.7 | 10:22                   |
| ES      | 1D      | LOD      | Zone      |    141 |                         38.2 |                       0.85 |                       22.8 |                       63   |                     27   |              54.6 | 11:06                   |
| ES      | 1D      | LOD      | Kontrolle |    187 |                         47.2 |                       0.99 |                       27.6 |                       73.4 |                     33.5 |              48.7 | 09:43                   |
| ES      | 1D      | LOD      | sonst     |    685 |                         42.5 |                       0.96 |                       25.8 |                       68.2 |                     29.5 |              47.3 | 09:59                   |
| ES      | 9D      | HOD      | Zone      |    577 |                         14.2 |                       0.51 |                        6   |                       29.5 |                      8   |              60.5 | 12:15                   |
| ES      | 9D      | HOD      | Kontrolle |    810 |                         15.8 |                       0.65 |                        7.2 |                       35.5 |                      8.8 |              51.1 | 10:37                   |
| ES      | 9D      | HOD      | sonst     |   2534 |                         17.6 |                       0.73 |                        8   |                       38.4 |                     10.5 |              45.9 | 10:03                   |
| ES      | 9D      | LOD      | Zone      |    528 |                         19.2 |                       0.73 |                        9.5 |                       36   |                     13   |              65.9 | 11:38                   |
| ES      | 9D      | LOD      | Kontrolle |    750 |                         21   |                       0.81 |                       11.2 |                       42.2 |                     14.6 |              49.2 | 09:55                   |
| ES      | 9D      | LOD      | sonst     |   2643 |                         20.8 |                       0.85 |                       11.5 |                       40.8 |                     15   |              42.9 | 09:23                   |
| ES      | 30D     | HOD      | Zone      |    549 |                         13.8 |                       0.49 |                        5.8 |                       29.5 |                      7.8 |              60.1 | 12:58                   |
| ES      | 30D     | HOD      | Kontrolle |    817 |                         15.8 |                       0.61 |                        6.8 |                       32.2 |                      8.8 |              48.3 | 10:31                   |
| ES      | 30D     | HOD      | sonst     |   2557 |                         18   |                       0.68 |                        8   |                       39   |                     10.5 |              47   | 10:04                   |
| ES      | 30D     | LOD      | Zone      |    526 |                         19   |                       0.69 |                        9.8 |                       36.4 |                     13   |              63.1 | 11:17                   |
| ES      | 30D     | LOD      | Kontrolle |    722 |                         21.1 |                       0.76 |                       11   |                       40.2 |                     14.6 |              50   | 09:59                   |
| ES      | 30D     | LOD      | sonst     |   2675 |                         21   |                       0.79 |                       11.5 |                       40.8 |                     15   |              43.3 | 09:30                   |
| RTY     | 1D      | HOD      | Zone      |    179 |                         28.2 |                       1.37 |                       14   |                       41.4 |                     17   |              60.3 | 09:50                   |
| RTY     | 1D      | HOD      | Kontrolle |    192 |                         27   |                       1.45 |                       13.9 |                       38.1 |                     16.7 |              45.8 | 09:33                   |
| RTY     | 1D      | HOD      | sonst     |    641 |                         25.9 |                       1.35 |                       11.8 |                       40.3 |                     15.9 |              54   | 10:05                   |
| RTY     | 1D      | LOD      | Zone      |    145 |                         25.9 |                       1.29 |                       14.9 |                       40.1 |                     18.6 |              69   | 10:21                   |
| RTY     | 1D      | LOD      | Kontrolle |    168 |                         23.8 |                       1.43 |                       17.2 |                       37.4 |                     17   |              57.1 | 09:53                   |
| RTY     | 1D      | LOD      | sonst     |    699 |                         28   |                       1.44 |                       14.5 |                       40.6 |                     17.9 |              54.4 | 09:55                   |
| RTY     | 9D      | HOD      | Zone      |    325 |                         19.9 |                       1    |                        9.1 |                       33.3 |                     12.7 |              62.5 | 10:56                   |
| RTY     | 9D      | HOD      | Kontrolle |    399 |                         22.5 |                       1.19 |                       10.9 |                       39.5 |                     14.1 |              50.6 | 09:43                   |
| RTY     | 9D      | HOD      | sonst     |   1481 |                         22.5 |                       1.19 |                        9.9 |                       37.6 |                     13.1 |              54   | 10:06                   |
| RTY     | 9D      | LOD      | Zone      |    315 |                         25.2 |                       1.19 |                       12.1 |                       37.5 |                     16.1 |              63.5 | 10:32                   |
| RTY     | 9D      | LOD      | Kontrolle |    402 |                         25.5 |                       1.26 |                       14.4 |                       38.5 |                     17   |              50   | 09:39                   |
| RTY     | 9D      | LOD      | sonst     |   1488 |                         22.3 |                       1.21 |                       12.6 |                       36.7 |                     15.2 |              54.6 | 10:02                   |
| RTY     | 30D     | HOD      | Zone      |    340 |                         18.6 |                       0.91 |                        8   |                       32.7 |                     10.5 |              63.2 | 10:59                   |
| RTY     | 30D     | HOD      | Kontrolle |    395 |                         20.5 |                       1    |                       10.2 |                       35.5 |                     12.9 |              56.2 | 10:05                   |
| RTY     | 30D     | HOD      | sonst     |   1470 |                         23.3 |                       1.12 |                       10.5 |                       38.9 |                     13.7 |              52.2 | 10:01                   |
| RTY     | 30D     | LOD      | Zone      |    341 |                         21.2 |                       1.02 |                       11.4 |                       33.8 |                     13.7 |              66.9 | 10:36                   |
| RTY     | 30D     | LOD      | Kontrolle |    386 |                         25.3 |                       1.14 |                       13.3 |                       38.3 |                     16.7 |              51.6 | 09:52                   |
| RTY     | 30D     | LOD      | sonst     |   1478 |                         23.1 |                       1.16 |                       13   |                       37.6 |                     15.8 |              53.2 | 09:56                   |
| GC      | GVZ     | HOD      | Zone      |    589 |                         10.6 |                       0.67 |                        6.1 |                       19.2 |                      6.7 |              46.2 | 09:48                   |
| GC      | GVZ     | HOD      | Kontrolle |    754 |                         13.6 |                       0.82 |                        7.4 |                       24.3 |                      7.9 |              34.6 | 08:20                   |
| GC      | GVZ     | HOD      | sonst     |   2583 |                         13.6 |                       0.86 |                        7.7 |                       23   |                      8.1 |              34.6 | 08:03                   |
| GC      | GVZ     | LOD      | Zone      |    554 |                         12.5 |                       0.79 |                        7.3 |                       21.2 |                      8.5 |              47.5 | 09:34                   |
| GC      | GVZ     | LOD      | Kontrolle |    766 |                         14.2 |                       0.88 |                        8.5 |                       24.4 |                      9.5 |              32.6 | 07:27                   |
| GC      | GVZ     | LOD      | sonst     |   2606 |                         14.3 |                       0.88 |                        8.5 |                       24.1 |                      9.4 |              33.9 | 07:37                   |

## 4) Konfluenz am Extrem: Zone-Extrem vs. Kontroll-Extrem (±0,1σ)

| Markt   | Modus   | Extrem   | Konfluenz                           |   bei Zone-Extrem % |   bei Kontroll-Extrem % |   Verhältnis |   n Zone |   n Kontrolle |
|:--------|:--------|:---------|:------------------------------------|--------------------:|------------------------:|-------------:|---------:|--------------:|
| NQ      | 1D      | HOD      | Vortag Hoch/Tief                    |                10.5 |                    14.3 |         0.73 |      153 |           203 |
| NQ      | 1D      | HOD      | Vortag RTH Hoch/Tief                |                 9.8 |                    13.8 |         0.71 |      153 |           203 |
| NQ      | 1D      | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 6.5 |                     9.9 |         0.66 |      153 |           203 |
| NQ      | 1D      | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 6.5 |                     3.9 |         1.66 |      153 |           203 |
| NQ      | 1D      | HOD      | RTH-VWAP ±2σ                        |                47.7 |                    37.4 |         1.27 |      153 |           203 |
| NQ      | 1D      | HOD      | Wochen-Zone                         |                 2   |                     5.4 |         0.36 |      153 |           203 |
| NQ      | 1D      | HOD      | Zone eines anderen Modus            |                52.3 |                    31   |         1.68 |      153 |           203 |
| NQ      | 1D      | HOD      | Runde Zahl                          |                45.8 |                    43.3 |         1.06 |      153 |           203 |
| NQ      | 1D      | LOD      | Vortag Hoch/Tief                    |                11.8 |                    10.8 |         1.09 |      153 |           194 |
| NQ      | 1D      | LOD      | Vortag RTH Hoch/Tief                |                11.8 |                     9.8 |         1.2  |      153 |           194 |
| NQ      | 1D      | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 3.3 |                     8.2 |         0.4  |      153 |           194 |
| NQ      | 1D      | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 4.6 |                     6.7 |         0.68 |      153 |           194 |
| NQ      | 1D      | LOD      | RTH-VWAP ±2σ                        |                32.7 |                    36.6 |         0.89 |      153 |           194 |
| NQ      | 1D      | LOD      | Wochen-Zone                         |                 4.6 |                     5.7 |         0.81 |      153 |           194 |
| NQ      | 1D      | LOD      | Zone eines anderen Modus            |                51.6 |                    26.3 |         1.96 |      153 |           194 |
| NQ      | 1D      | LOD      | Runde Zahl                          |                39.9 |                    45.9 |         0.87 |      153 |           194 |
| NQ      | 9D      | HOD      | Vortag Hoch/Tief                    |                 9.4 |                    17.3 |         0.54 |      638 |           790 |
| NQ      | 9D      | HOD      | Vortag RTH Hoch/Tief                |                10   |                    15.7 |         0.64 |      638 |           790 |
| NQ      | 9D      | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 7.7 |                    12.4 |         0.62 |      638 |           790 |
| NQ      | 9D      | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 8   |                     8.1 |         0.99 |      638 |           790 |
| NQ      | 9D      | HOD      | RTH-VWAP ±2σ                        |                46.4 |                    39.5 |         1.17 |      638 |           790 |
| NQ      | 9D      | HOD      | Wochen-Zone                         |                 3.6 |                     4.1 |         0.89 |      638 |           790 |
| NQ      | 9D      | HOD      | Zone eines anderen Modus            |                74.8 |                    14.3 |         5.23 |      638 |           790 |
| NQ      | 9D      | HOD      | Runde Zahl                          |                26.3 |                    22.3 |         1.18 |      638 |           790 |
| NQ      | 9D      | LOD      | Vortag Hoch/Tief                    |                12.7 |                    13.4 |         0.95 |      535 |           753 |
| NQ      | 9D      | LOD      | Vortag RTH Hoch/Tief                |                14   |                    14.3 |         0.98 |      535 |           753 |
| NQ      | 9D      | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 8   |                     9.7 |         0.83 |      535 |           753 |
| NQ      | 9D      | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 6   |                     5.4 |         1.1  |      535 |           753 |
| NQ      | 9D      | LOD      | RTH-VWAP ±2σ                        |                46.2 |                    38.1 |         1.21 |      535 |           753 |
| NQ      | 9D      | LOD      | Wochen-Zone                         |                 2.6 |                     3.5 |         0.76 |      535 |           753 |
| NQ      | 9D      | LOD      | Zone eines anderen Modus            |                78.1 |                    15.9 |         4.9  |      535 |           753 |
| NQ      | 9D      | LOD      | Runde Zahl                          |                27.9 |                    26   |         1.07 |      535 |           753 |
| NQ      | 30D     | HOD      | Vortag Hoch/Tief                    |                 8.4 |                    16.4 |         0.51 |      609 |           764 |
| NQ      | 30D     | HOD      | Vortag RTH Hoch/Tief                |                 9.7 |                    15.4 |         0.63 |      609 |           764 |
| NQ      | 30D     | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 7.1 |                    13.2 |         0.53 |      609 |           764 |
| NQ      | 30D     | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 9.4 |                     9.4 |         0.99 |      609 |           764 |
| NQ      | 30D     | HOD      | RTH-VWAP ±2σ                        |                50.2 |                    42.8 |         1.17 |      609 |           764 |
| NQ      | 30D     | HOD      | Wochen-Zone                         |                 3.9 |                     3.1 |         1.25 |      609 |           764 |
| NQ      | 30D     | HOD      | Zone eines anderen Modus            |                81.4 |                    18.2 |         4.48 |      609 |           764 |
| NQ      | 30D     | HOD      | Runde Zahl                          |                28.1 |                    24.5 |         1.15 |      609 |           764 |
| NQ      | 30D     | LOD      | Vortag Hoch/Tief                    |                13.1 |                    12.9 |         1.02 |      548 |           735 |
| NQ      | 30D     | LOD      | Vortag RTH Hoch/Tief                |                14.4 |                    15.4 |         0.94 |      548 |           735 |
| NQ      | 30D     | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 8.4 |                    11.2 |         0.75 |      548 |           735 |
| NQ      | 30D     | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 7.5 |                     6.9 |         1.08 |      548 |           735 |
| NQ      | 30D     | LOD      | RTH-VWAP ±2σ                        |                47.1 |                    40.3 |         1.17 |      548 |           735 |
| NQ      | 30D     | LOD      | Wochen-Zone                         |                 4.4 |                     2.7 |         1.61 |      548 |           735 |
| NQ      | 30D     | LOD      | Zone eines anderen Modus            |                78.5 |                    15.9 |         4.93 |      548 |           735 |
| NQ      | 30D     | LOD      | Runde Zahl                          |                26.5 |                    26.5 |         1    |      548 |           735 |
| ES      | 1D      | HOD      | Vortag Hoch/Tief                    |                 9.9 |                    15   |         0.66 |      151 |           193 |
| ES      | 1D      | HOD      | Vortag RTH Hoch/Tief                |                10.6 |                    16.1 |         0.66 |      151 |           193 |
| ES      | 1D      | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                11.3 |                     5.2 |         2.17 |      151 |           193 |
| ES      | 1D      | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 7.3 |                     5.7 |         1.28 |      151 |           193 |
| ES      | 1D      | HOD      | RTH-VWAP ±2σ                        |                52.3 |                    38.9 |         1.35 |      151 |           193 |
| ES      | 1D      | HOD      | Wochen-Zone                         |                 4.6 |                     2.6 |         1.79 |      151 |           193 |
| ES      | 1D      | HOD      | Zone eines anderen Modus            |                53.6 |                    22.3 |         2.41 |      151 |           193 |
| ES      | 1D      | HOD      | Runde Zahl                          |                39.1 |                    43.5 |         0.9  |      151 |           193 |
| ES      | 1D      | LOD      | Vortag Hoch/Tief                    |                12.1 |                     8   |         1.5  |      141 |           187 |
| ES      | 1D      | LOD      | Vortag RTH Hoch/Tief                |                11.3 |                     8.6 |         1.33 |      141 |           187 |
| ES      | 1D      | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 8.5 |                     5.9 |         1.45 |      141 |           187 |
| ES      | 1D      | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 9.9 |                     2.7 |         3.71 |      141 |           187 |
| ES      | 1D      | LOD      | RTH-VWAP ±2σ                        |                36.9 |                    27.3 |         1.35 |      141 |           187 |
| ES      | 1D      | LOD      | Wochen-Zone                         |                 2.8 |                     4.8 |         0.59 |      141 |           187 |
| ES      | 1D      | LOD      | Zone eines anderen Modus            |                48.9 |                    19.8 |         2.47 |      141 |           187 |
| ES      | 1D      | LOD      | Runde Zahl                          |                41.1 |                    43.3 |         0.95 |      141 |           187 |
| ES      | 9D      | HOD      | Vortag Hoch/Tief                    |                13   |                    16   |         0.81 |      577 |           810 |
| ES      | 9D      | HOD      | Vortag RTH Hoch/Tief                |                10.9 |                    17.4 |         0.63 |      577 |           810 |
| ES      | 9D      | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                10.1 |                    11.7 |         0.86 |      577 |           810 |
| ES      | 9D      | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 6.6 |                     7   |         0.94 |      577 |           810 |
| ES      | 9D      | HOD      | RTH-VWAP ±2σ                        |                47   |                    42.1 |         1.12 |      577 |           810 |
| ES      | 9D      | HOD      | Wochen-Zone                         |                 3.8 |                     2.1 |         1.82 |      577 |           810 |
| ES      | 9D      | HOD      | Zone eines anderen Modus            |                78.7 |                    11.6 |         6.78 |      577 |           810 |
| ES      | 9D      | HOD      | Runde Zahl                          |                26.3 |                    27.3 |         0.97 |      577 |           810 |
| ES      | 9D      | LOD      | Vortag Hoch/Tief                    |                10.6 |                    10.3 |         1.03 |      528 |           750 |
| ES      | 9D      | LOD      | Vortag RTH Hoch/Tief                |                11.2 |                    13.9 |         0.81 |      528 |           750 |
| ES      | 9D      | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 8.3 |                     9.3 |         0.89 |      528 |           750 |
| ES      | 9D      | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 7.4 |                     5.3 |         1.38 |      528 |           750 |
| ES      | 9D      | LOD      | RTH-VWAP ±2σ                        |                44.9 |                    34.8 |         1.29 |      528 |           750 |
| ES      | 9D      | LOD      | Wochen-Zone                         |                 2.7 |                     3.5 |         0.76 |      528 |           750 |
| ES      | 9D      | LOD      | Zone eines anderen Modus            |                75.8 |                    12.4 |         6.11 |      528 |           750 |
| ES      | 9D      | LOD      | Runde Zahl                          |                24.6 |                    26.8 |         0.92 |      528 |           750 |
| ES      | 30D     | HOD      | Vortag Hoch/Tief                    |                11.1 |                    16.3 |         0.68 |      549 |           817 |
| ES      | 30D     | HOD      | Vortag RTH Hoch/Tief                |                10.9 |                    18.2 |         0.6  |      549 |           817 |
| ES      | 30D     | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                10   |                    12.4 |         0.81 |      549 |           817 |
| ES      | 30D     | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 7.7 |                     7.8 |         0.98 |      549 |           817 |
| ES      | 30D     | HOD      | RTH-VWAP ±2σ                        |                49   |                    40   |         1.22 |      549 |           817 |
| ES      | 30D     | HOD      | Wochen-Zone                         |                 4.6 |                     2   |         2.33 |      549 |           817 |
| ES      | 30D     | HOD      | Zone eines anderen Modus            |                83.2 |                    14.6 |         5.72 |      549 |           817 |
| ES      | 30D     | HOD      | Runde Zahl                          |                27.5 |                    26.3 |         1.05 |      549 |           817 |
| ES      | 30D     | LOD      | Vortag Hoch/Tief                    |                11   |                    13.4 |         0.82 |      526 |           722 |
| ES      | 30D     | LOD      | Vortag RTH Hoch/Tief                |                12.7 |                    17.6 |         0.72 |      526 |           722 |
| ES      | 30D     | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 7.8 |                    10.5 |         0.74 |      526 |           722 |
| ES      | 30D     | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 5.5 |                     5.4 |         1.02 |      526 |           722 |
| ES      | 30D     | LOD      | RTH-VWAP ±2σ                        |                43.2 |                    35.9 |         1.2  |      526 |           722 |
| ES      | 30D     | LOD      | Wochen-Zone                         |                 2.3 |                     4   |         0.57 |      526 |           722 |
| ES      | 30D     | LOD      | Zone eines anderen Modus            |                80.6 |                    18.4 |         4.38 |      526 |           722 |
| ES      | 30D     | LOD      | Runde Zahl                          |                29.3 |                    28.3 |         1.04 |      526 |           722 |
| RTY     | 1D      | HOD      | Vortag Hoch/Tief                    |                 5.6 |                    10.4 |         0.54 |      179 |           192 |
| RTY     | 1D      | HOD      | Vortag RTH Hoch/Tief                |                 6.7 |                    10.9 |         0.61 |      179 |           192 |
| RTY     | 1D      | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 7.8 |                     7.3 |         1.07 |      179 |           192 |
| RTY     | 1D      | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 3.4 |                     3.6 |         0.92 |      179 |           192 |
| RTY     | 1D      | HOD      | RTH-VWAP ±2σ                        |                33.5 |                    25   |         1.34 |      179 |           192 |
| RTY     | 1D      | HOD      | Wochen-Zone                         |                 2.8 |                     3.6 |         0.77 |      179 |           192 |
| RTY     | 1D      | HOD      | Zone eines anderen Modus            |                51.4 |                    28.6 |         1.79 |      179 |           192 |
| RTY     | 1D      | HOD      | Runde Zahl                          |                41.9 |                    42.7 |         0.98 |      179 |           192 |
| RTY     | 1D      | LOD      | Vortag Hoch/Tief                    |                 6.2 |                    14.9 |         0.42 |      145 |           168 |
| RTY     | 1D      | LOD      | Vortag RTH Hoch/Tief                |                 6.2 |                    14.9 |         0.42 |      145 |           168 |
| RTY     | 1D      | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 9   |                    11.3 |         0.79 |      145 |           168 |
| RTY     | 1D      | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 6.2 |                     4.8 |         1.3  |      145 |           168 |
| RTY     | 1D      | LOD      | RTH-VWAP ±2σ                        |                37.9 |                    26.8 |         1.42 |      145 |           168 |
| RTY     | 1D      | LOD      | Wochen-Zone                         |                 4.8 |                     3   |         1.62 |      145 |           168 |
| RTY     | 1D      | LOD      | Zone eines anderen Modus            |                51.7 |                    30.4 |         1.7  |      145 |           168 |
| RTY     | 1D      | LOD      | Runde Zahl                          |                48.3 |                    44   |         1.1  |      145 |           168 |
| RTY     | 9D      | HOD      | Vortag Hoch/Tief                    |                 7.7 |                    13.3 |         0.58 |      325 |           399 |
| RTY     | 9D      | HOD      | Vortag RTH Hoch/Tief                |                 8   |                    13.8 |         0.58 |      325 |           399 |
| RTY     | 9D      | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 4.3 |                     9   |         0.48 |      325 |           399 |
| RTY     | 9D      | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 5.5 |                     3.5 |         1.58 |      325 |           399 |
| RTY     | 9D      | HOD      | RTH-VWAP ±2σ                        |                39.1 |                    32.8 |         1.19 |      325 |           399 |
| RTY     | 9D      | HOD      | Wochen-Zone                         |                 4.6 |                     3   |         1.53 |      325 |           399 |
| RTY     | 9D      | HOD      | Zone eines anderen Modus            |                68   |                    22.8 |         2.98 |      325 |           399 |
| RTY     | 9D      | HOD      | Runde Zahl                          |                37.8 |                    43.1 |         0.88 |      325 |           399 |
| RTY     | 9D      | LOD      | Vortag Hoch/Tief                    |                 7.9 |                     9.2 |         0.86 |      315 |           402 |
| RTY     | 9D      | LOD      | Vortag RTH Hoch/Tief                |                 7.9 |                    10.7 |         0.74 |      315 |           402 |
| RTY     | 9D      | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 7.3 |                     8.5 |         0.86 |      315 |           402 |
| RTY     | 9D      | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 4.4 |                     4.5 |         0.99 |      315 |           402 |
| RTY     | 9D      | LOD      | RTH-VWAP ±2σ                        |                36.5 |                    28.4 |         1.29 |      315 |           402 |
| RTY     | 9D      | LOD      | Wochen-Zone                         |                 6.3 |                     5.7 |         1.11 |      315 |           402 |
| RTY     | 9D      | LOD      | Zone eines anderen Modus            |                74.3 |                    19.4 |         3.83 |      315 |           402 |
| RTY     | 9D      | LOD      | Runde Zahl                          |                43.8 |                    39.3 |         1.11 |      315 |           402 |
| RTY     | 30D     | HOD      | Vortag Hoch/Tief                    |                10.6 |                    12.7 |         0.84 |      340 |           395 |
| RTY     | 30D     | HOD      | Vortag RTH Hoch/Tief                |                11.5 |                    14.9 |         0.77 |      340 |           395 |
| RTY     | 30D     | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 5.3 |                    10.6 |         0.5  |      340 |           395 |
| RTY     | 30D     | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 4.1 |                     6.3 |         0.65 |      340 |           395 |
| RTY     | 30D     | HOD      | RTH-VWAP ±2σ                        |                45.6 |                    40   |         1.14 |      340 |           395 |
| RTY     | 30D     | HOD      | Wochen-Zone                         |                 4.4 |                     3.5 |         1.24 |      340 |           395 |
| RTY     | 30D     | HOD      | Zone eines anderen Modus            |                70.9 |                    32.2 |         2.2  |      340 |           395 |
| RTY     | 30D     | HOD      | Runde Zahl                          |                43.5 |                    47.6 |         0.91 |      340 |           395 |
| RTY     | 30D     | LOD      | Vortag Hoch/Tief                    |                 7.6 |                     9.3 |         0.82 |      341 |           386 |
| RTY     | 30D     | LOD      | Vortag RTH Hoch/Tief                |                 9.1 |                    12.2 |         0.75 |      341 |           386 |
| RTY     | 30D     | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 7   |                    10.1 |         0.7  |      341 |           386 |
| RTY     | 30D     | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 4.1 |                     4.1 |         0.99 |      341 |           386 |
| RTY     | 30D     | LOD      | RTH-VWAP ±2σ                        |                40.8 |                    28.8 |         1.42 |      341 |           386 |
| RTY     | 30D     | LOD      | Wochen-Zone                         |                 6.2 |                     5.4 |         1.13 |      341 |           386 |
| RTY     | 30D     | LOD      | Zone eines anderen Modus            |                70.1 |                    29.3 |         2.39 |      341 |           386 |
| RTY     | 30D     | LOD      | Runde Zahl                          |                47.8 |                    49.2 |         0.97 |      341 |           386 |
| GC      | GVZ     | HOD      | Vortag Hoch/Tief                    |                 9.7 |                    10.9 |         0.89 |      589 |           754 |
| GC      | GVZ     | HOD      | Vortag RTH Hoch/Tief                |                11   |                    17   |         0.65 |      589 |           754 |
| GC      | GVZ     | HOD      | Overnight Hoch/Tief (Extrem in RTH) |                 9.2 |                     8.6 |         1.06 |      589 |           754 |
| GC      | GVZ     | HOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 5.6 |                     4.5 |         1.24 |      589 |           754 |
| GC      | GVZ     | HOD      | RTH-VWAP ±2σ                        |                35.1 |                    27.6 |         1.27 |      589 |           754 |
| GC      | GVZ     | HOD      | Wochen-Zone                         |                 3.6 |                     3.6 |         1    |      589 |           754 |
| GC      | GVZ     | HOD      | Zone eines anderen Modus            |                 0   |                     0   |       nan    |      589 |           754 |
| GC      | GVZ     | HOD      | Runde Zahl                          |                41.6 |                    35.9 |         1.16 |      589 |           754 |
| GC      | GVZ     | LOD      | Vortag Hoch/Tief                    |                 7.8 |                    12.8 |         0.61 |      554 |           766 |
| GC      | GVZ     | LOD      | Vortag RTH Hoch/Tief                |                11.6 |                    19.7 |         0.59 |      554 |           766 |
| GC      | GVZ     | LOD      | Overnight Hoch/Tief (Extrem in RTH) |                 6.9 |                     7   |         0.97 |      554 |           766 |
| GC      | GVZ     | LOD      | IB Hoch/Tief (Extrem nach 10:30)    |                 4.2 |                     2.3 |         1.77 |      554 |           766 |
| GC      | GVZ     | LOD      | RTH-VWAP ±2σ                        |                33.2 |                    23.9 |         1.39 |      554 |           766 |
| GC      | GVZ     | LOD      | Wochen-Zone                         |                 3.4 |                     3.9 |         0.88 |      554 |           766 |
| GC      | GVZ     | LOD      | Zone eines anderen Modus            |                 0   |                     0   |       nan    |      554 |           766 |
| GC      | GVZ     | LOD      | Runde Zahl                          |                33.6 |                    39.8 |         0.84 |      554 |           766 |
