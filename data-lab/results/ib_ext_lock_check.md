# IB-Expansion ALL – Prüfung „Einstufung bleibt“

`data-lab/ib_ext_lock_check.py` rechnet die Pine-Logik nach: Ein Level wird beim ersten Erreichen der 70-%-Schwelle
als Target/Protect eingestuft und behält diese Einstufung bis Treffer oder Tagesende. Verglichen wird das % beim
Erscheinen mit dem tatsächlichen Ausgang. Letztes Jahr, Starts 18:00 / 03:00 / 08:30 / 09:30 / 10:30, alle 4 Längen,
NQ/ES/RTY/GC. Tabellen unten: Version ohne Wochentag; mit Wochentag (aktuell) siehe letzte Zeile. Hinweis: Die Formeln im Indikator enthalten dieses Jahr (die echte ungesehene Prüfung steht in
`ib_ext_model.md`). Hier geht es darum, ob das Festhalten der Einstufung die Prozente verzerrt.

| Art | Level-Tage | angezeigt | eingetreten |
|---|---:|---:|---:|
| Protect (hält) | 729.803 | 0,812 | 0,816 |
| Target (erreicht) | 537.201 | 0,760 | 0,791 |

| Art | Band | n | angezeigt | eingetreten |
|---|---|---:|---:|---:|
| Protect | 70–80 % | 385.564 | 0,724 | 0,724 |
| Protect | 80–90 % | 140.424 | 0,853 | 0,856 |
| Protect | 90–100 % | 203.815 | 0,949 | 0,962 |
| Target | 70–80 % | 406.120 | 0,732 | 0,760 |
| Target | 80–90 % | 124.618 | 0,841 | 0,885 |
| Target | 90–100 % | 6.463 | 0,914 | 0,971 |

Je Markt (ohne Wochentag): Protect 0,80–0,83 angezeigt → 0,81–0,82 eingetreten, Target 0,75–0,77 → 0,79–0,80.
Mit Wochentag (aktueller Indikator): Protect 0,80–0,83 → 0,81–0,82, Target 0,75–0,78 → 0,79–0,80 – unverändert gut.
Ergebnis: Mit festgehaltener Einstufung bleiben die Prozente ehrlich; Targets eher vorsichtig.
