# H7 Gotham Zones (ohne Kalibrierung) – Abschlussbericht

**Urteil: kein Edge.** Die Zonen sind exakt nachgebaut (Anker 18:00-Open, σ = Open × Wert/100/√252, Box ±5 %) und
verhalten sich in allen Märkten (NQ, ES, RTY, GC) und Modi (1D, 9D, 30D, GVZ) wie gleich breite Kontroll-Bänder direkt daneben.

## Teil A – HOD/LOD (beschreibend, `gz_a_report.md`)
- HOD bzw. LOD liegt an 11–21 % der Tage in einer Zonen-Box – aber gleich oft in gleich breiten Bändern daneben
  (Unterschied je Zone vs. Nachbarn: −0,9 bis +0,7 Prozentpunkte, kein Modus und kein Markt sticht stabil heraus).
- „Wenn berührt, war es das Extrem“: Zone vs. Nachbarn −3,8 bis +2,5 Prozentpunkte, Vorzeichen wechselt zwischen Explore und Validate.
- Reaktion nach einem Zonen-Extrem (Median bis zum Gegen-Extrem danach): NQ 1D 144 (HOD) / 188 (LOD) Pkt, NQ 9D/30D 45–60 Pkt,
  ES 1D ~39 Pkt, RTY 1D ~26–28 Pkt, GC ~11–13 Pkt. Nach Extremen in Kontroll-Bändern ist sie gleich groß oder größer.
- Konfluenz am Extrem (±0,1σ): Vortages-Hoch/-Tief, Overnight, IB, Wochen-Zonen, runde Zahlen, VWAP-Bänder – keine erhöht die
  Wahrscheinlichkeit; Vortag H/T ist bei Zonen-Extremen sogar seltener (0,8×). „Zone eines anderen Modus“ (3,7×) ist ein Gitter-Effekt
  (die Modi liegen 0,7–1,3× auseinander, ihre Zonen fallen zwangsläufig zusammen) und bringt in Teil B keinen EW-Vorteil.
- **Auffällig RTY:** Der Indikator nimmt für RTY VIX/VIX1D (nicht NQ, nicht GC). Die Reaktionen liegen bei 1,0–1,45σ statt 0,5–0,9σ
  wie bei NQ/ES → σ für RTY ist zu klein. Fix: RVX-Skalierung (wie VXN bei NQ).

## Teil B – Strategie-Suche (nur Explore bis 2024)
- Jede erste Berührung (137.000 Ereignisse inkl. Kontrollen), Vorlagen Fade 1R, Fade 2R, Durchbruch 1R, Fade bis Schluss.
- 22 Konfluenz-Formeln (Vortag H/T/C, RTH, Pivots, Camarilla, Volumenprofil, Overnight, IB/ORB-Extensions, VWAP-Bänder, Wochen-/Monats-Open,
  Vorwoche, runde Zahlen, andere Modi) und 14 Biases (Uhrzeit, Range verbraucht, Tempo, Gap, Event-Tag, Kurve, IV-Rang, Vortags-Range,
  Gegenseite berührt, VWAP-Abstand, erste 30 Min., Wochentag, Long/Short, Trend, Turn-of-Month).
- **2.685 Varianten**, alle Grundvarianten negativ (−0,04 bis −0,23 R). 3 erfüllten die Kandidaten-Regel (schwach, t 0,15–1,5 – das
  erwartet man bei so vielen Versuchen durch Zufall); nur einer hatte einen Mechanismus.
- Gegenprobe: Filter wirken an Kontroll-Levels genauso → wenn überhaupt etwas, liegt es nie an der Gotham-Zone.
- Einziges durchgängiges Muster: Durchbrüche in RTH sind ~0,1 R besser als nachts – aber nur bis ~0 (NQ), sonst negativ.

## Teil C – Prüfung (2025 bis 16.04.2026)
- RTY 1D, Fade 2R, Berührungen 18–24 Uhr: 143 Trades, EW −0,17 R (KI −0,39 bis +0,06), Zufall −0,06 R, p = 0,84 → **durchgefallen**.
- Holdout ab 17.04.2026 nicht angefasst.
