---
description: MotiveWave-Cracks (gelbe LVN-Linien) selbst screenshotten, 3× geprüft auslesen, in die Zwischenablage legen
allowed-tools: Bash(open:*), Bash(sleep:*), Bash(screencapture:*), Bash(python3:*), Bash(pbcopy:*), Bash(mkdir:*), Read, Write
---

Du liest die gelben LVN-Linien ("Cracks") aus MotiveWave aus. Arbeite ohne Rückfragen.

## 1. Screenshot machen

```bash
mkdir -p ~/Documents/MotiveWave_Cracks
open -a MotiveWave && sleep 2 && screencapture -x ~/Documents/MotiveWave_Cracks/auto.png
```

Schlägt das fehl oder ist das Bild schwarz: Nutzer bitten, in Systemeinstellungen →
Datenschutz & Sicherheit → Bildschirmaufnahme das Terminal zu erlauben. Dann abbrechen.

## 2. Schilder groß ausschneiden

```bash
python3 - <<'EOF'
from PIL import Image
from pathlib import Path
d = Path.home() / "Documents" / "MotiveWave_Cracks"
im = Image.open(d / "auto.png").convert("RGB")
W, H = im.size
im.resize((W // 2, H // 2)).save(d / "uebersicht.png")          # ganzes Bild zur Orientierung
strip = im.crop((0, 0, int(W * 0.30), H))                        # linker Bereich mit den Schildern
n = 4
for i in range(n):                                               # 4 überlappende Streifen, 2× vergrößert
    y0 = max(0, int(H * i / n) - 40); y1 = min(H, int(H * (i + 1) / n) + 40)
    part = strip.crop((0, y0, strip.width, y1))
    part.resize((part.width * 2, part.height * 2), Image.LANCZOS).save(d / f"teil{i + 1}.png")
    print(f"teil{i + 1}.png: y {y0}–{y1}")
print("Bild", W, "x", H)
EOF
```

Dann `uebersicht.png` und `teil1.png` … `teil4.png` mit dem Read-Tool ansehen.
Findest du die Schilder nicht im linken Bereich (anderes Layout), schneide mit Python passend
neu aus und lies erneut.

## 3. Was zählt

- Cracks = gelbe, gestrichelte, waagerechte Linien über die Chartbreite, mit gelbem Preisschild
  links, z. B. "30289.50".
- NICHT: Preisachse rechts (weiß), Kurs-Schild rechts, magenta POC-Linien ("P: …"), graue
  Profil-Beschriftungen, türkise Balken, kurze gelbe Striche nur am rechten Rand.
- Werte, die in zwei überlappenden Streifen vorkommen, nur einmal zählen.

## 4. Dreifach-Prüfung (Pflicht)

1. Durchgang 1: alle Schilder von oben nach unten, Ziffer für Ziffer → Liste A.
2. Durchgang 2: von unten nach oben, neu ablesen, nicht abschreiben → Liste B.
3. Durchgang 3 (Gegenprobe):
   - gelbe gestrichelte Linien in `uebersicht.png` zählen = Anzahl Werte,
   - NQ/ES: jeder Wert endet auf ".50", Werte fallen von oben nach unten streng,
   - Pixelabstand der Linien passt zum Preisabstand; mit der Preisachse rechts abgleichen,
   - Verwechsler gezielt prüfen: 3↔8, 5↔6, 6↔8, 0↔8, 1↔7, 4↔9.

Nur Werte, bei denen A, B und Gegenprobe exakt übereinstimmen, gelten als sicher. Bei
Abweichung die Stelle nochmal gezielt ausschneiden (Python, stärker vergrößert) und lesen.
Bleibt es unklar: nicht in die Liste, sondern unter UNSICHER mit beiden Lesarten.

## 5. Ausgabe

Sichere Werte aufsteigend, ein Preis pro Zeile, zwei Nachkommastellen, nach
`~/Documents/MotiveWave_Cracks/cracks.txt` schreiben und in die Zwischenablage:

```bash
pbcopy < ~/Documents/MotiveWave_Cracks/cracks.txt
```

Dem Nutzer zeigen (kurz, Deutsch):
- die Liste als Codeblock,
- `Linien gezählt: N · Werte: M · 3× geprüft ✓` bzw. `NICHT vollständig bestätigt`,
- ggf. UNSICHER-Liste,
- "Liegt in der Zwischenablage → TradingView, Cracks-Indikator, Feld NQ, Cmd+V."
