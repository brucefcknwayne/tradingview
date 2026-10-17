# Gotham Zones – Edge-Suche mit Bedingungen

1217 Tests. Bestanden: 2, knapp: 2. R = Gewinn in Vielfachen des Risikos (1.5 Zonenhöhen), nach 1 Pkt Kosten.

| Seite   | Level   | Bedingung                           | Trade        |   n_train |   R_train |   t_train |   n_test |   R_test |   t_test |   hit_test | bestanden   | knapp   |
|:--------|:--------|:------------------------------------|:-------------|----------:|----------:|----------:|---------:|---------:|---------:|-----------:|:------------|:--------|
| oben    | ±1σ     | zeit=RTH früh 09:30-11              | Breakout 1:2 |       323 |     0.346 |      4.18 |      202 |    0.247 |     2.43 |       44.6 | True        | False   |
| oben    | ±1σ     | anlauf=mittel                       | Breakout 1:2 |       350 |     0.249 |      3.41 |      194 |    0.217 |     2.22 |       45.9 | True        | False   |
| oben    | ±1σ     | gegenseite=False                    | Breakout 1:2 |       831 |     0.158 |      3.26 |      534 |    0.11  |     1.87 |       40.6 | False       | True    |
| oben    | ±1σ     | alle                                | Breakout 1:2 |       848 |     0.161 |      3.37 |      547 |    0.089 |     1.53 |       39.9 | False       | True    |
| beide   | ±0.5σ   | gegenseite=True                     | Fade 60 Min  |       940 |    -0.152 |     -3.03 |      573 |    0.255 |     3.35 |       42.2 | False       | False   |
| oben    | ±0.5σ   | gegenseite=True                     | Fade 60 Min  |       474 |    -0.103 |     -1.53 |      297 |    0.395 |     3.35 |       45.8 | False       | False   |
| oben    | alle    | gegenseite=True                     | Fade 60 Min  |       496 |    -0.118 |     -1.81 |      315 |    0.353 |     3.13 |       44.8 | False       | False   |
| beide   | alle    | gegenseite=True                     | Fade 60 Min  |       975 |    -0.171 |     -3.52 |      603 |    0.224 |     3.06 |       41.3 | False       | False   |
| oben    | alle    | montag=True                         | Breakout 1:2 |       739 |    -0.076 |     -1.52 |      448 |    0.19  |     2.9  |       43.5 | False       | False   |
| oben    | alle    | anlauf=mittel                       | Breakout 1:2 |      1426 |    -0.075 |     -2.1  |      739 |    0.144 |     2.85 |       42.4 | False       | False   |
| oben    | ±0.5σ   | termstruktur=invertiert (VIX9D>VIX) | Fade 60 Min  |       921 |    -0.185 |     -4.92 |      438 |    0.25  |     2.76 |       43.4 | False       | False   |
| beide   | ±1σ     | pd_level=True                       | Breakout 1:2 |       165 |     0.087 |      0.77 |      100 |    0.384 |     2.7  |       51   | False       | False   |
| beide   | ±0.5σ   | gegenseite=True                     | Fade 1:2     |       940 |    -0.144 |     -3.27 |      573 |    0.144 |     2.47 |       41.2 | False       | False   |
| oben    | ±1σ     | zeit=RTH Mitte 11-14                | Breakout 1:2 |       251 |     0.104 |      1.23 |      128 |    0.281 |     2.37 |       47.7 | False       | False   |
| oben    | ±0.5σ   | montag=True                         | Breakout 1:2 |       516 |    -0.135 |     -2.24 |      291 |    0.195 |     2.35 |       43   | False       | False   |
| beide   | ±0.5σ   | termstruktur=invertiert (VIX9D>VIX) | Fade 60 Min  |      1708 |    -0.184 |     -5.9  |      795 |    0.134 |     2.26 |       42.6 | False       | False   |
| oben    | ±0.5σ   | zeit=London 03-09:30                | Fade 60 Min  |      1012 |    -0.134 |     -3.98 |      516 |    0.161 |     2.19 |       46.1 | False       | False   |
| beide   | alle    | gegenseite=True                     | Fade 1:2     |       975 |    -0.157 |     -3.64 |      603 |    0.123 |     2.17 |       40.5 | False       | False   |
| oben    | ±0.5σ   | anlauf=mittel                       | Breakout 1:2 |       970 |    -0.197 |     -4.59 |      478 |    0.139 |     2.17 |       41.6 | False       | False   |
| oben    | ±1σ     | montag=True                         | Breakout 1:2 |       172 |     0.071 |      0.67 |      117 |    0.27  |     2.17 |       47   | False       | False   |
| unten   | ±0.5σ   | vola=VXN mittel                     | Fade 1:2     |       895 |    -0.156 |     -3.32 |      506 |    0.139 |     2.16 |       39.5 | False       | False   |
| oben    | ±0.5σ   | montag=False                        | Fade 60 Min  |      2434 |    -0.169 |     -7.04 |     1345 |    0.088 |     2.15 |       42.8 | False       | False   |
| oben    | alle    | zeit=London 03-09:30                | Fade 60 Min  |      1149 |    -0.123 |     -3.88 |      661 |    0.133 |     2.15 |       45.2 | False       | False   |
| oben    | alle    | zeit=RTH Mitte 11-14                | Breakout 1:2 |       651 |    -0.013 |     -0.26 |      338 |    0.155 |     2.14 |       42.3 | False       | False   |
| beide   | ±0.5σ   | vola=VXN mittel                     | Fade 1:2     |      1877 |    -0.124 |     -3.81 |     1008 |    0.094 |     2.09 |       37.8 | False       | False   |
| unten   | ±0.5σ   | gegenseite=True                     | Fade 1:2     |       466 |    -0.182 |     -2.87 |      276 |    0.173 |     2.02 |       41.3 | False       | False   |
| unten   | ±0.5σ   | zeit=RTH spät 14-17                 | Fade 1:2     |       243 |    -0.308 |     -3.97 |      110 |    0.25  |     1.99 |       46.4 | False       | False   |
| beide   | ±0.5σ   | vola=VXN mittel                     | Fade 60 Min  |      1877 |    -0.204 |     -7.3  |     1008 |    0.082 |     1.98 |       45.1 | False       | False   |
| beide   | ±0.5σ   | montag=False                        | Fade 60 Min  |      4595 |    -0.168 |     -8.87 |     2711 |    0.051 |     1.89 |       42.7 | False       | False   |
| oben    | alle    | termstruktur=invertiert (VIX9D>VIX) | Fade 60 Min  |      1501 |    -0.188 |     -6.27 |      731 |    0.114 |     1.78 |       39.8 | False       | False   |
| oben    | ±1σ     | zeit=RTH Mitte 11-14                | Breakout 1:1 |       251 |     0.037 |      0.62 |      128 |    0.145 |     1.71 |       57.8 | False       | False   |
| unten   | ±1σ     | pd_level=True                       | Breakout 1:2 |       104 |    -0.042 |     -0.3  |       53 |    0.342 |     1.7  |       47.2 | False       | False   |
| oben    | alle    | zeit=RTH früh 09:30-11              | Breakout 1:2 |      1100 |     0.028 |      0.64 |      656 |    0.093 |     1.7  |       39.5 | False       | False   |
| unten   | alle    | gegenseite=True                     | Fade 1:2     |       479 |    -0.195 |     -3.14 |      288 |    0.141 |     1.69 |       40.3 | False       | False   |
| oben    | ±0.5σ   | montag=True                         | Breakout 1:1 |       516 |    -0.153 |     -3.5  |      291 |    0.096 |     1.67 |       56   | False       | False   |
| beide   | ±1σ     | pd_level=True                       | Breakout 1:1 |       165 |    -0.074 |     -0.96 |      100 |    0.16  |     1.65 |       60   | False       | False   |
| oben    | alle    | montag=False                        | Fade 60 Min  |      3648 |    -0.208 |    -10.87 |     2082 |    0.053 |     1.65 |       41   | False       | False   |
| unten   | ±0.5σ   | vola=VXN mittel                     | Fade 1:1     |       895 |    -0.167 |     -4.98 |      506 |    0.072 |     1.65 |       54.9 | False       | False   |
| beide   | alle    | zeit=London 03-09:30                | Fade 60 Min  |      2178 |    -0.159 |     -6.37 |     1395 |    0.064 |     1.65 |       43.1 | False       | False   |
| beide   | ±0.5σ   | zeit=RTH spät 14-17                 | Fade 1:2     |       527 |    -0.277 |     -5.52 |      257 |    0.126 |     1.64 |       43.2 | False       | False   |
| beide   | ±0.5σ   | anlauf=mittel                       | Fade 60 Min  |      2189 |    -0.177 |     -6.7  |     1227 |    0.066 |     1.63 |       44.7 | False       | False   |
| beide   | ±1σ     | zeit=RTH früh 09:30-11              | Breakout 1:2 |       661 |     0.084 |      1.47 |      437 |    0.105 |     1.54 |       38.7 | False       | False   |
| unten   | ±0.5σ   | vola=VXN mittel                     | Fade 60 Min  |       895 |    -0.178 |     -3.94 |      506 |    0.093 |     1.54 |       45.1 | False       | False   |
| oben    | alle    | termstruktur=steil (<0.9)           | Breakout 1:2 |       804 |    -0.077 |     -1.62 |      677 |    0.081 |     1.54 |       38.6 | False       | False   |
| beide   | ±0.5σ   | gegenseite=True                     | Fade 1:1     |       940 |    -0.183 |     -5.74 |      573 |    0.062 |     1.53 |       54.3 | False       | False   |
| oben    | ±0.5σ   | anlauf=schnell                      | Fade 60 Min  |       746 |    -0.116 |     -2.21 |      447 |    0.122 |     1.49 |       38   | False       | False   |
| beide   | ±1σ     | zeit=RTH Mitte 11-14                | Breakout 1:2 |       511 |     0.013 |      0.21 |      266 |    0.125 |     1.48 |       40.6 | False       | False   |
| oben    | ±0.5σ   | gegenseite=True                     | Fade 1:2     |       474 |    -0.107 |     -1.74 |      297 |    0.116 |     1.47 |       41.1 | False       | False   |
| beide   | ±0.5σ   | konfluenz=True                      | Fade 60 Min  |      5142 |    -0.178 |    -10.07 |     3097 |    0.036 |     1.47 |       42.3 | False       | False   |
| oben    | alle    | montag=True                         | Breakout 1:1 |       739 |    -0.108 |     -2.97 |      448 |    0.067 |     1.45 |       54.2 | False       | False   |
| unten   | ±1σ     | pd_level=True                       | Breakout 1:1 |       104 |    -0.119 |     -1.21 |       53 |    0.194 |     1.45 |       60.4 | False       | False   |
| oben    | ±0.5σ   | konfluenz=True                      | Fade 60 Min  |      2730 |    -0.169 |     -7.45 |     1572 |    0.052 |     1.44 |       42.2 | False       | False   |
| unten   | ±0.5σ   | zeit=RTH spät 14-17                 | Fade 1:1     |       243 |    -0.365 |     -6.03 |      110 |    0.126 |     1.43 |       55.5 | False       | False   |
| oben    | ±1σ     | konfluenz=True                      | Breakout 1:2 |       580 |     0.149 |      2.56 |      424 |    0.093 |     1.42 |       40.3 | False       | False   |
| beide   | ±0.5σ   | pd_level=False                      | Fade 60 Min  |      4683 |    -0.166 |     -8.9  |     2769 |    0.037 |     1.4  |       41.9 | False       | False   |
| oben    | alle    | gegenseite=True                     | Fade 1:2     |       496 |    -0.121 |     -2.01 |      315 |    0.107 |     1.39 |       40.6 | False       | False   |
| beide   | alle    | zeit=RTH früh 09:30-11              | Breakout 1:2 |      2213 |    -0.089 |     -2.95 |     1342 |    0.053 |     1.38 |       37.1 | False       | False   |
| oben    | alle    | anlauf=langsam                      | Breakout 1:2 |      1197 |    -0.037 |     -0.94 |      732 |    0.07  |     1.38 |       38.5 | False       | False   |
| beide   | ±0.5σ   | termstruktur=invertiert (VIX9D>VIX) | Fade 1:2     |      1708 |    -0.173 |     -5.16 |      795 |    0.069 |     1.38 |       37   | False       | False   |
| oben    | ±1σ     | vola=VXN hoch                       | Breakout 1:2 |       314 |     0.007 |      0.09 |      377 |    0.096 |     1.37 |       40.3 | False       | False   |
