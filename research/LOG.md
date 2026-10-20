# Test-Log

Fortlaufender Zähler aller Tests (grob, für Mehrfachtest-Bewusstsein). Frühere Studien aus dem Repo sind nachgetragen.

| # | Datum | Was | Ergebnis | Tests (ca.) | Summe |
|---|---|---|---|---|---|
| 0a | bis 2026-10 | `pullback-1r` RSI(2)-Pullback 1:1 | ~51 %, kein Vorteil | 1 | 1 |
| 0b | bis 2026-10 | `multi-10` 10 Standard-Setups 1:1 | alle < 50 % | 10 | 11 |
| 0c | 2026-10 | IB-First Edge-Test (NQ/ES/RTY/GC) | Trefferquote = Geometrie, PF netto ≤ 1,05 | 4 | 15 |
| 0d | 2026-10 | IV-Zonen: Abprall vs. Kontroll-Levels, Konfluenz, HOD/LOD | keine Wand-Wirkung | ~20 | 35 |
| 0e | 2026-10 | Literatur-Tests (Momentum Schluss, runde Zahlen u. a.) | kein Edge, Momentum zuletzt negativ | ~12 | 47 |
| 0f | 2026-10-18 | 7 Level-Formeln vs. Kontroll-Levels (4 Märkte) | kein Edge (1/28 p<0,05) | 28 | 75 |
| 1 | 2026-10-19 | H1 Zera-Reversal: 1m, Vol 500, Vol 1000 × Stop A/B × 9 Gruppen, 2022-09–2026-04, Zufall 1.000× | **kein Edge**: 0/54 nach Holm, EW netto ≈ −1 Pkt = Zufall | 54 | 129 |
| 2 | 2026-10-19 | H2 Zera + Orderflow-Filter (Delta dreht / Absorption / Delta-Divergenz) × 3 Charts × 2 Stops | **kein Edge**: 0/18 nach Holm, EW netto −0,5 bis −3,1 | 18 | 147 |
| 3 | 2026-10-19 | H5 Gewinner-Merkmale (~40 Merkmale, Modell + Baum-Regel), Explore 2022–24 / Validate 2025–26, 1m + Vol 500 | **kein Edge**: 0/4 nach Holm; Gewinner = Volatilität/RTH, nicht Levels | 4 (+ ~80 explorative Vergleiche) | 151 |
| 4 | 2026-10-19 | H7 Teil A: Gotham-Zonen HOD/LOD, Reaktion, Konfluenz (4 Märkte × Modi) | beschreibend: Zonen = Kontroll-Bänder | 0 | 151 |
| 5 | 2026-10-19 | H7 Teil B: Strategie-Suche Explore, 22 Konfluenzen + 14 Biases × 4 Vorlagen | 2.685 Varianten, 3 schwache Kandidaten | 2.685 (explorativ) | 2.836 |
| 6 | 2026-10-19 | H7 Teil C: RTY 1D Fade 2R Abend auf Validate | **durchgefallen**: EW −0,17 R, p 0,84 | 1 | 2.837 |
| 7 | 2026-10-19 | H7 Zusatz: Zonen-Berührungen, die HOD/LOD wurden vs. durchbrochen (Merkmale + Modell Explore→Validate) | vorhersagbar nur „spät/langsam/Range verbraucht“, gilt an Kontrollen genauso; Top-10 % Fade-EW ≈ 0 | 10 (explorativ) | 2.847 |
| 8 | 2026-10-19 | HAR-Bänder vs. IV-Bänder (σ-Kalibrierung, 4 Märkte, Fit Explore / Prüfung Validate) | HAR+IV mind. so gut wie bestes IV, RTY stark verbessert (±1σ 72 % statt 56 %) – Kalibrierung, kein Edge-Test | 0 | 2.847 |
| 9 | 2026-10-19 | H9 Runde 1–3: VWAP-Familien A–L (Band-Fade, Pullback, Ausbruch, Nachmittags-/MTF-Momentum, ORB, Gap), Explore 2011–2019 | 560 Varianten; 3 Kandidaten | 560 (explorativ) | 3.407 |
| 10 | 2026-10-19 | H9 Prüfung K1 (NQ MTF-Momentum 11:30), K2 (RTY 1σ-Ausbruch + Monat), K3 (NQ Momentum energiereiche Tage) auf Validate 2020–24 / Test 2025–26 | **alle durchgefallen** (Validate p 0,34–0,50, Test negativ) | 6 | 3.413 |
| 11 | 2026-10-19 | H10 Landkarte 2022–23 (VWAP-Rücklauf?) | widerlegt: weiterhin Momentum (t bis 2,7) → H10 verworfen | 0 | 3.413 |
| 12 | 2026-10-19 | H11 VWAP-Momentum-Portfolio, 16 Varianten, Explore | **alle negativ** → verworfen | 16 | 3.429 |
| 13 | 2026-10-19 | H12 Intraday-Periodizität (Halbstunden-Fenster, 9 Varianten × 4 Märkte), Explore | **kein Effekt** (brutto ≈ 0, 0/9 Jahre positiv netto) | 9 | 3.438 |
| 14 | 2026-10-19 | H13 Event-Tage (08:30/10:00/14:00, datenbasiert), 3 Uhrzeiten × 2 R × 3 M × 2 Richtungen × 3 Ausstiege × 4 Märkte | kein Kandidat (GC 10:00 Fortsetzung stabil, aber selten/einzeln) | 396 (explorativ) | 3.834 |
| 15 | 2026-10-19 | H15 LVN-Tests (Wand, Beschleuniger, + VWAP-±2σ), 4 Märkte × P1/P5 × 3 Prominenzen, 2021-10 – 2026-04 | **kein Effekt**: Abprall LVN = Kontrolle (47–54 %); „Beschleuniger“ nur scheinbar schlechter (Distanz-Effekt), bei gleicher Distanz ±0–2 Pkt-% | 72 | 3.906 |
| 16 | 2026-10-19 | H16 9:30 ORB: A Statistik (4 Märkte × OR 5/15/30/60), B1 Paper-Regel (3 Zeiträume), B2/B3 Gitter 64 × 4 Märkte (Explore) | Paper-Regel nur NQ positiv, nach Veröffentlichung +0,13 R n. s.; B2/B3 kein Kandidat | 268 | 4.174 |
| 17 | 2026-10-19 | H16b ORB-Tiefe: A Ausdehnung/Leiter/Rennen/2. Ausbruch; B 4 Einstiege × 8 Ziele × 4 Stops × OR × Markt (2.048); C 6 Filter (1.536); Prüfung 5 Kandidaten | Rennen ±k ≈ 50 %; negatives RR = Geometrie; 5 Kandidaten in Validate negativ; Beobachtung NQ Halten bis Schluss ab 2020 (nachträglich) | 3.589 | 7.763 |
| 18 | 2026-10-20 | H17 5-Min-Open-Bias: 4 Märkte × 6 Horizonte × Zeiträume, 7 Kontroll-Kerzen, Größe/Gap/Extreme | kein allgemeiner Bias (Treffer 50–52 %); NQ große Kerze in allen Zeiträumen positiv (nachträglich) | ~130 | ~7.890 |
| 19 | 2026-10-20 | H18 LVN + Single Prints + VAH/VAL (Vortag RTH, 30-Min-TPO), 8 Familien × 4 Märkte × 2 r, 2011–04/2026 (fix + ATR-Buckets) | **kein Effekt**: 0/64 nach Holm in beiden Läufen | 128 | ~8.020 |
