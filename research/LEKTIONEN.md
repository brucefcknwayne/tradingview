# Lektionen

- Levels aus Formeln (IV-σ, ATR, Camarilla, ORB, IB, VWAP-Bänder, Bollinger) sind Lineale für Entfernung/erwartete
  Bewegung, keine Wände: Abprall-Quoten = Kontroll-Levels daneben (~50 % bei symmetrischem Rennen).
- 1D-IV misst die Tagesbewegung gut (RV/IV ≈ 0,95); 30D überschätzt um 25–45 %.
- Hohe Trefferquoten (z. B. „IB-Gegenseite 85 %“) sind oft reine Geometrie – immer gegen eine Zufalls-/Geometrie-Baseline prüfen.
- Momentum zum Sitzungsende (Literatur) hat sich nach Veröffentlichung umgedreht.
- Median von ln(H/L)/1,6651 ist ~0,9σ – Kalibrierungen damit brauchen einen Ausgleich.
- Z-Score-Reversal (OHLC4 vs. 50er-Mittel, |Z|≥2 → erste neutrale Kerze) ist auf NQ reiner Zufall: vor Kosten ≈ 0 Pkt/Trade,
  auf 1m, 500er und 1000er Volume-Bars gleich. Die Trefferquote (bis 56 % Overnight) täuscht – sie kommt aus der Geometrie
  Ziel nah / Stop weit, der Zufall mit gleichem Stop/Ziel schafft dasselbe.
- „Preisgetrieben“ (Preis läuft wirklich zurück) ist nicht besser als Zufall; „nicht preisgetrieben“ ist am schlechtesten.
- 1 Punkt Kosten ist bei Zielen von 10–20 Punkten das ganze Spiel: Ohne echten Vorteil vor Kosten bleibt netto ≈ −1.
- Einfache Orderflow-Filter (Delta der Signal-Kerze dreht, Absorption am Extrem, Delta-Divergenz) machen das Zera-Signal nicht besser:
  Der Orderflow einer einzelnen Kerze bzw. Serie trägt auf NQ keine verwertbare Information über den Rücklauf.
- „Was haben die Gewinner gemeinsam?“ → vor allem Volatilität und Tageszeit. Das erklärt, WANN große Bewegungen kommen, nicht wohin.
  Ein Modell mit ~40 Merkmalen (Levels, Orderflow, Zeit, Vola) trennt Gewinner/Verlierer nur über die Bewegungsgröße (AUC 0,54–0,64)
  und bringt nach Kosten keinen Vorteil gegenüber Zufall.
- Nähe zu klassischen Levels macht Reversals nicht besser – Gewinner lagen eher weiter von Vortages-Levels/POC entfernt.
- Gotham-Zonen exakt wie im Indikator: HOD/LOD nicht häufiger als in gleich breiten Bändern daneben, in allen Märkten und Modi.
  Keine der 22 getesteten Level-Formeln als Konfluenz und keiner von 14 Biases macht Berührungen handelbar (2.685 Varianten).
- Konfluenz „mehrere Levels an einer Stelle“ ist auf NQ/ES/RTY/GC kein Vorteil; Vortages-Hoch/-Tief liegen bei Zonen-Extremen sogar seltener.
- Long-Fades an unteren Zonen sind weniger schlecht als Short-Fades oben (Index-Drift), aber nicht positiv.
- Durchbrüche laufen in der RTH besser als nachts (~+0,1 R), erreichen aber höchstens null.
- RTY-σ im Indikator ist mit der VIX-Familie zu klein (Reaktionen > 1σ) → RVX verwenden.
- Nur 4–9 % der ersten Zonen-Berührungen werden zum Tages-Extrem. Was sie gemeinsam haben: später am Tag, langsamer Anlauf,
  mehr Range verbraucht, Gegenseite schon berührt – an Kontroll-Levels genauso (oft stärker). Vorhersagbar (AUC Validate 0,56–0,80),
  aber die Fades im besten Zehntel bleiben bei ≈ 0 R: spät am Tag ist auch die Restbewegung klein.
- HAR+IV (log-HAR auf Garman-Klass + Erwartungswert des Modus) liefert das am besten kalibrierte σ: NQ ±1σ 67,7–68,9 % (Soll 68,3),
  RTY 72,5 % statt 55,7 % mit der VIX-Familie. Als Lineal besser, als Level-Wand weiterhin ohne Edge zu erwarten.
- VWAP-Landkarte 2011–2019: Preis läuft eher vom VWAP weg (Momentum), v. a. nachmittags; Mean Reversion zu VWAP-Bändern verliert überall.
- Multi-Timeframe-VWAP-Ausrichtung (Session/Woche/Monat) und energiereiche Tage verstärken das Momentum 2011–2019 deutlich (PF bis 1,5),
  ab 2020 verschwindet es (PF ≈ 1,0), 2025–26 negativ. Vermutete Ursache: 0DTE/Dealer-long-Gamma dämpft Intraday-Momentum.
- Einzel-Setups mit fester Uhrzeit (z. B. 11:30) können in-sample stark aussehen (p 0,001–0,002) und sind trotzdem Zufallsspitzen:
  über mehrere Uhrzeiten/Märkte gemittelt verschwinden sie. Immer Plateau über Uhrzeiten prüfen, nicht nur über Parameter.
- Intraday-Periodizität (gleiches Halbstunden-Fenster an Folgetagen) existiert auf NQ/ES/RTY/GC nicht in handelbarer Größe.
- LVNs (Volumenprofil-Täler, algorithmisch wie gängige TradingView-Finder) sind auf NQ/ES/RTY/GC 2021–2026 weder Wand noch Beschleuniger:
  Abprall = zufällige Preise, Durchlauf zum nächsten HVN bei gleicher Distanz gleich oft und gleich schnell. Auch an VWAP-±2σ-Bändern kein Zusatz.
- Vergleiche immer bei gleicher Distanz: Ein scheinbarer Effekt (LVN schlechter als Kontrolle, Holm p 0,015) war nur der längere Weg zum Ziel.
- 9:30-ORB: Die Richtung der ersten 5-Min-Kerze trägt messbar Information (+0,3–0,6 R gegenüber Gegenrichtung), aber mit Stop an der
  anderen Kerzenseite und Kosten bleibt netto nur NQ leicht positiv (nach Veröffentlichung nicht signifikant). Erstausbruch-Seite ist Münzwurf.
- ORB-Ausdehnung ist Volatilität, nicht Richtung: nach dem Erstausbruch erreicht der Preis +k×OR genauso oft zuerst wie −k×OR (47–53 %).
  „72 % erreichen 1×OR“ (OR5) heißt nichts, wenn die Gegenseite fast genauso oft erreicht wird.
- Negatives RR ändert den Erwartungswert nicht: die Trefferquote steigt exakt auf die Break-even-Quote des Zufallspfads.
- Kosten im Verhältnis zur Range ändern sich über die Jahre stark (NQ 2012: 10–15 % von R, 2025: ~1 %). Ergebnisse über Jahrzehnte immer auch brutto in R vergleichen.
- 5-Min-Open-Kerze: als Tages-Bias praktisch Münzwurf (50–52 %). Nur große Kerzen auf NQ (≥ ~9 % ATR) laufen in allen Zeiträumen weiter;
  kleine Kerzen eher nicht. Die Eröffnung trägt mehr Information als spätere Kerzen, aber wenig.

