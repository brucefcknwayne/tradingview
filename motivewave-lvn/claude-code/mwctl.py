#!/usr/bin/env python3
"""
mwctl – MotiveWave fernsteuern (für den Claude-Code-Befehl /cracks).

  python3 ~/.claude/mwctl.py window                 Fenster finden (Position/Größe)
  python3 ~/.claude/mwctl.py shot NAME              Screenshot NUR vom MotiveWave-Fenster → NAME.png
                                                    + NAME_teilN.png (Schildbereich, vergrößert)
  python3 ~/.claude/mwctl.py drag X1 Y1 X2 Y2       Maus ziehen, Koordinaten als Anteil des Fensters
                                                    (0..1), z. B. drag 0.5 0.8 0.5 0.2 = Chart nach oben
  python3 ~/.claude/mwctl.py scroll N [X Y]         Mausrad N Schritte (+ hoch / − runter) an X,Y
  python3 ~/.claude/mwctl.py dblclick X Y           Doppelklick (z. B. Preisachse = Auto-Skalierung)

Bilder landen in ~/Documents/MotiveWave_Cracks/.
Braucht: pip3 install pyobjc-framework-Quartz pillow
Rechte: Systemeinstellungen → Datenschutz & Sicherheit → Bildschirmaufnahme UND Bedienungshilfen → Terminal.
"""
import subprocess
import sys
import time
from pathlib import Path

import Quartz as Q
from PIL import Image

OUT = Path.home() / "Documents" / "MotiveWave_Cracks"
OUT.mkdir(parents=True, exist_ok=True)


def activate():
    subprocess.run(["open", "-a", "MotiveWave"], check=False)
    time.sleep(1.0)


def find_window():
    wins = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly | Q.kCGWindowListExcludeDesktopElements,
                                        Q.kCGNullWindowID)
    best = None
    for w in wins:
        owner = str(w.get("kCGWindowOwnerName", ""))
        if "motivewave" not in owner.lower() or w.get("kCGWindowLayer", 1) != 0:
            continue
        b = w["kCGWindowBounds"]
        area = b["Width"] * b["Height"]
        if best is None or area > best[1]:
            best = (w, area)
    if best is None:
        sys.exit("MotiveWave-Fenster nicht gefunden (läuft MotiveWave? Fenster sichtbar?)")
    w = best[0]
    b = w["kCGWindowBounds"]
    return int(w["kCGWindowNumber"]), b["X"], b["Y"], b["Width"], b["Height"]


def to_screen(fx, fy):
    _, x, y, w, h = find_window()
    return x + float(fx) * w, y + float(fy) * h


def mouse(kind, x, y, clicks=1):
    ev = Q.CGEventCreateMouseEvent(None, kind, (x, y), Q.kCGMouseButtonLeft)
    if clicks > 1:
        Q.CGEventSetIntegerValueField(ev, Q.kCGMouseEventClickState, clicks)
    Q.CGEventPost(Q.kCGHIDEventTap, ev)


def drag(fx1, fy1, fx2, fy2):
    activate()
    x1, y1 = to_screen(fx1, fy1)
    x2, y2 = to_screen(fx2, fy2)
    mouse(Q.kCGEventMouseMoved, x1, y1)
    time.sleep(0.1)
    mouse(Q.kCGEventLeftMouseDown, x1, y1)
    time.sleep(0.1)
    steps = 25
    for i in range(1, steps + 1):
        mouse(Q.kCGEventLeftMouseDragged, x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps)
        time.sleep(0.02)
    mouse(Q.kCGEventLeftMouseUp, x2, y2)
    time.sleep(0.6)
    print("gezogen", (round(x1), round(y1)), "→", (round(x2), round(y2)))


def scroll(n, fx=0.5, fy=0.5):
    activate()
    x, y = to_screen(fx, fy)
    mouse(Q.kCGEventMouseMoved, x, y)
    n = int(n)
    for _ in range(abs(n)):
        ev = Q.CGEventCreateScrollWheelEvent(None, Q.kCGScrollEventUnitLine, 1, 1 if n > 0 else -1)
        Q.CGEventPost(Q.kCGHIDEventTap, ev)
        time.sleep(0.03)
    time.sleep(0.6)
    print("gescrollt", n)


def dblclick(fx, fy):
    activate()
    x, y = to_screen(fx, fy)
    for c in (1, 2):
        mouse(Q.kCGEventLeftMouseDown, x, y, c)
        mouse(Q.kCGEventLeftMouseUp, x, y, c)
        time.sleep(0.05)
    time.sleep(0.6)
    print("Doppelklick", (round(x), round(y)))


def shot(name):
    activate()
    wid = find_window()[0]
    png = OUT / f"{name}.png"
    subprocess.run(["screencapture", "-x", "-o", "-l", str(wid), str(png)], check=True)
    im = Image.open(png).convert("RGB")
    W, H = im.size
    im.resize((W // 2, H // 2)).save(OUT / f"{name}_uebersicht.png")
    strip = im.crop((0, 0, int(W * 0.30), H))                     # Schilder sitzen links
    n = max(2, round(H / 450))
    parts = []
    for i in range(n):
        y0 = max(0, int(H * i / n) - 40)
        y1 = min(H, int(H * (i + 1) / n) + 40)
        p = strip.crop((0, y0, strip.width, y1))
        f = OUT / f"{name}_teil{i + 1}.png"
        p.resize((p.width * 2, p.height * 2), Image.LANCZOS).save(f)
        parts.append(f"{f.name} (y {y0}–{y1})")
    print(f"Bild {W}×{H}: {png}")
    print("Übersicht:", OUT / f"{name}_uebersicht.png")
    print("Schild-Teile:", ", ".join(parts))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == "window":
        wid, x, y, w, h = find_window()
        print(f"Fenster {wid}: x={x} y={y} b={w} h={h}")
    elif cmd == "shot":
        shot(a[0] if a else "shot")
    elif cmd == "drag":
        drag(*a[:4])
    elif cmd == "scroll":
        scroll(*a[:3])
    elif cmd == "dblclick":
        dblclick(*a[:2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
