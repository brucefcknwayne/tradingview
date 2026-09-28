---
description: MotiveWave-Cracks (gelbe LVN-Linien) selbst suchen – Chart hoch/runter schieben, jede Seite 3× geprüft ablesen, Ergebnis in die Zwischenablage
allowed-tools: Bash(python3:*), Bash(pbcopy:*), Bash(mkdir:*), Bash(sleep:*), Read, Write
---

Du liest ALLE gelben LVN-Linien ("Cracks") aus MotiveWave aus. Sie reichen weiter als ein Bildschirm,
deshalb schiebst du den Chart selbst hoch und runter. Arbeite ohne Rückfragen, bis alles erfasst ist.
Werkzeug: `python3 ~/.claude/mwctl.py …` (Hilfe: ohne Argumente aufrufen).

## Was ein Crack ist
- Gelbe, gestrichelte, waagerechte Linie über die Chartbreite mit gelbem Preisschild links, z. B. "30289.50".
- NICHT: Preisachse rechts (weiß), Kurs-Schild rechts, magenta POC ("P: …"), graue Profil-Zahlen,
  türkise Balken, kurze gelbe Striche nur am rechten Rand.
- NQ/ES: jeder Crack endet auf ".50".

## Ablauf

**0. Start.** `python3 ~/.claude/mwctl.py shot s00` und die ausgegebenen Bilder (Übersicht + Teile)
mit dem Read-Tool ansehen. Fehler "nicht gefunden" / schwarzes Bild / Maus bewegt sich nicht →
Nutzer auf die Rechte hinweisen (Bildschirmaufnahme + Bedienungshilfen für Terminal) und abbrechen.

**1. Lesbar machen.** Überlappen sich Schilder oder sind sie zu klein: Chart vertikal strecken.
In MotiveWave: auf der Preisachse (rechts, x≈0.97) senkrecht ziehen, z. B.
`drag 0.97 0.45 0.97 0.60` (nach unten ziehen = strecken). Danach neu `shot` und prüfen, ob die
Preisachse jetzt einen kleineren Bereich zeigt. Falls es andersherum wirkt, Richtung umdrehen.
Ziel: kein Schild überlappt ein anderes, Ziffern klar lesbar. Nicht mehr strecken als nötig.

**2. Chart verschieben – erst Richtung finden.** Senkrecht im Chart ziehen:
`drag 0.5 0.35 0.5 0.75` (Maus runter = Chart zeigt höhere Preise). Mit `shot` prüfen, ob sich
die Preisachse bewegt hat. Wenn nicht: Mausrad testen (`scroll 5 0.5 0.5`, `scroll -5 …`).
Merk dir, welcher Befehl hoch und welcher runter bewegt.

**3. Nach oben bis zum obersten Crack.** In Schritten von ca. 60 % der Chart-Höhe nach oben
schieben (so überlappen sich zwei Bilder immer um einige Cracks). Jede Seite `shot sNN`.
Oben ist Schluss, wenn zwei Seiten hintereinander keine neuen Cracks mehr zeigen (kein Volume-Profil
mehr / nur leere Fläche).

**4. Von oben nach unten alles ablesen.** Jetzt schrittweise (ca. 60 %) nach unten, jede Seite
`shot sNN` und mit der DREIFACH-PRÜFUNG lesen (unten). Unten ist Schluss wie oben: zwei Seiten ohne
neue Cracks. Maximal 40 Seiten.

**5. Zusammenführen.** Werte, die auf zwei Nachbarseiten vorkommen, müssen identisch sein
(Zusatz-Kontrolle!). Weicht ein doppelter Wert ab: Stelle neu screenshotten und genauer lesen.

## DREIFACH-PRÜFUNG (jede Seite, Pflicht)
1. Durchgang 1: alle Schilder oben → unten, Ziffer für Ziffer → Liste A.
2. Durchgang 2: unten → oben, NEU ablesen, nicht abschreiben → Liste B.
3. Gegenprobe: gelbe gestrichelte Linien in der Übersicht zählen = Anzahl Werte; Endung ".50";
   Werte fallen von oben nach unten; Pixelabstand passt zum Preisabstand; mit Preisachse rechts
   abgleichen; Verwechsler prüfen: 3↔8, 5↔6, 6↔8, 0↔8, 1↔7, 4↔9.
Nur wenn A, B und Gegenprobe exakt gleich sind, ist ein Wert sicher. Sonst: Chart an der Stelle
weiter strecken oder verschieben, neu `shot`, neu lesen. Bleibt es unklar → UNSICHER mit beiden Lesarten.
Schild am Bildrand abgeschnitten → nicht lesen, sondern auf der Nachbarseite lesen.

## Ausgabe
Sichere Werte aufsteigend, ein Preis pro Zeile, zwei Nachkommastellen, nach
`~/Documents/MotiveWave_Cracks/cracks.txt` schreiben, dann `pbcopy < ~/Documents/MotiveWave_Cracks/cracks.txt`.

Dem Nutzer kurz auf Deutsch zeigen:
- die Liste als Codeblock,
- `Seiten: S · Cracks: M · 3× geprüft ✓` bzw. `NICHT vollständig bestätigt`,
- ggf. UNSICHER-Liste,
- "Liegt in der Zwischenablage → TradingView, Cracks-Indikator, Feld NQ, Cmd+V."
- Hinweis: In MotiveWave Doppelklick auf die Preisachse stellt die normale Ansicht wieder her.
