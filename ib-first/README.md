# IB First – Tief zuerst → Hoch wird geholt

Eigenständiges Projekt (unabhängig von `gotham-zones/IB-Expansion`).

**Idee:** Entsteht in der Initial Balance zuerst das Tief, wird danach meist das IB-Hoch geholt – und umgekehrt.

- `IB-First.pine` – Indikator für NQ, ES, RTY, GC (+ Micros), Markt wird erkannt. Eine IB (Startzeit + 15/30/45/60 Min).
  Am IB-Ende: Linie an der Gegenseite („Hoch wird geholt 85%“), optional +0,5 / +1 IB darüber hinaus und
  „Tief nochmal x%“ an der Erstseite. Linien laufen bis Berührung (✓) oder Tagesende. Alarme für IB-Ende und Treffer.
  Gebaut von `data-lab/ib_first_build.py` aus `IB-First_template.pine` (letzte 3 Jahre, Werte in `data-lab/results/ib_first_build.md`).

**Prüfung** (`data-lab/ib_first_side.py` → `data-lab/results/ib_first_side.md`): 3 Jahre Statistik vs. ungesehenes letztes Jahr.
Beispiel NQ 09:30, Tief zuerst → Hoch geholt: 15m 87 % (Test 92 %), 30m 85 % (85 %), 45m 86 % (82 %), 60m 84 % (81 %);
an allen Tagen wird das Hoch nur zu 78 / 71 / 66 / 63 % geholt. Über alle Märkte, Starts und Längen weicht das Testjahr
im Median 0,5 Pkt. ab. Hinweis: Teilweise mechanisch (das zuletzt gebildete Extrem liegt näher am Kurs); ein
Trade-Test (Einstieg/Stop) steht noch aus.
