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
