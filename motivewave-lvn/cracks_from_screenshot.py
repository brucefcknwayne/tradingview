#!/usr/bin/env python3
"""
Cracks (gelbe LVN-Linien) aus einem MotiveWave-Screenshot → exakte Preise.

Ablauf pro Bild:
 1. Linien finden: Pixelzeilen, die über die Chartbreite gelb sind (gestrichelt ok).
 2. Schild lesen: NUR das Preisschild dieser Linie wird ausgeschnitten, alles
    außer Gelb weggefiltert (türkise Balken, Profile, Kerzen verschwinden),
    vergrößert und mit Tesseract gelesen.
 3. Gegenprobe: aus allen Schildern wird per RANSAC die Gerade y → Preis
    bestimmt (falsch gelesene Schilder fliegen raus). Ein Schild zählt nur,
    wenn es auf dem Raster liegt (NQ: x.50) UND zur Pixel-Höhe passt.
 4. Passt ein Schild nicht (z. B. zwei Schilder überlappen), wird der Preis
    aus der Pixel-Höhe genommen und mit "?" markiert → kurz selbst prüfen.

Beispiel:
  python3 cracks_from_screenshot.py chart.png --copy
  python3 cracks_from_screenshot.py chart.png --low 30289.50 --high 31017.50   (Eichung von Hand)

Installation (Mac):  brew install tesseract && pip3 install numpy pillow pytesseract
Tipp: Screenshot in voller Retina-Auflösung (Cmd+Shift+4, Leertaste, Fenster
anklicken) und Chart möglichst hoch – je mehr Pixel pro Punkt, desto sicherer.
"""
import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

NUM = re.compile(r"\d{3,6}\.\d{1,2}")


# ── 1. Linien ────────────────────────────────────────────────────────────────
def color_mask(rgb, color, tol):
    diff = np.abs(rgb.astype(np.int16) - np.array(color, dtype=np.int16))
    return (diff <= tol).all(axis=2)


def find_lines(mask, min_frac, x0, x1):
    counts = mask[:, x0:x1].sum(axis=1)
    rows = np.where(counts >= min_frac * (x1 - x0))[0]
    groups, g = [], []
    for r in rows:
        if g and r - g[-1] > 1:
            groups.append(g)
            g = []
        g.append(r)
    if g:
        groups.append(g)
    ys = [float(np.average(g, weights=counts[g])) for g in groups]
    return sorted(ys, reverse=True)                  # unten zuerst = niedrigster Preis


# ── 2. Schilder ──────────────────────────────────────────────────────────────
def yellowness(rgb):
    """0…1 je Pixel: wie stark gelb (hält Kantenglättung der Schrift, Türkis/Grau → 0)."""
    r, g, b = (rgb[..., i].astype(np.float32) for i in range(3))
    v = (np.minimum(r, g) - b - 40) / 120
    v[np.abs(r - g) > 60] = 0
    return np.clip(v, 0, 1)


def text_columns(yel, y, x0, x1, gap):
    """Rechte Kante des Schild-Textes: Spalten mit Gelb ober-/unterhalb der Linienzeile."""
    yi = int(round(y))
    band = np.concatenate([yel[max(0, yi - 8):max(0, yi - 2), x0:x1], yel[yi + 3:yi + 9, x0:x1]], axis=0)
    has = band.max(axis=0) > 0.4 if band.size else np.zeros(x1 - x0, bool)
    cols = np.where(has)[0]
    if len(cols) == 0:
        return None
    end = cols[0]
    for c in cols[1:]:
        if c - end > gap:
            break
        end = c
    return x0 + max(0, cols[0] - 2), x0 + end + 3


def ocr(img, scale, psm):
    import pytesseract
    im = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    im = ImageOps.expand(im, border=24, fill=255)
    txt = pytesseract.image_to_string(im, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789.")
    m = NUM.search(txt.replace(" ", "").replace("\n", ""))
    return float(m.group()) if m else None


def read_label(yel, y, lx0, lx1, half_h):
    h = yel.shape[0]
    cols = text_columns(yel, y, lx0, lx1, gap=max(4, int(half_h)))
    if cols is None:
        return None
    y0, y1 = max(0, int(y - half_h)), min(h, int(y + half_h) + 2)
    crop = yel[y0:y1, cols[0]:cols[1]]
    img = Image.fromarray((255 - crop * 255).astype(np.uint8))     # dunkle Schrift auf weiß
    a, b = ocr(img, 4, 7), ocr(img, 6, 8)
    return a if a is not None and a == b else None                   # nur wenn beide Läufe gleich


# ── 3. Eichung ───────────────────────────────────────────────────────────────
def ransac(pairs, tol_px):
    best, best_in = None, []
    for i in range(len(pairs)):
        for j in range(i + 1, len(pairs)):
            (ya, pa), (yb, pb) = pairs[i], pairs[j]
            if abs(ya - yb) < 20 or pa == pb:
                continue
            a = (pa - pb) / (ya - yb)
            if a >= 0:
                continue
            b = pa - a * ya
            inl = [(y, p) for y, p in pairs if abs((p - b) / a - y) <= tol_px]
            if len(inl) > len(best_in):
                best, best_in = (a, b), inl
    if best is None or len(best_in) < 3:
        return None
    a, b = np.polyfit([y for y, _ in best_in], [p for _, p in best_in], 1)
    return a, b


def on_grid(p, step, off):
    return abs(((p - off) / step) - round((p - off) / step)) < 1e-6


# ── Hauptprogramm ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="MotiveWave-Cracks aus Screenshot")
    ap.add_argument("image")
    ap.add_argument("--tick", type=float, default=0.25, help="Tickgröße (NQ/ES 0.25, GC 0.10)")
    ap.add_argument("--rows", type=int, default=4, help="Tick Interval der Study")
    ap.add_argument("--offset", type=float, default=0.5, help="Rasterversatz (NQ: 0.5 → x.50)")
    ap.add_argument("--low", type=float, help="Eichung von Hand: Preis der untersten Linie")
    ap.add_argument("--high", type=float, help="Eichung von Hand: Preis der obersten Linie")
    ap.add_argument("--color", default="ffff00", help="Linienfarbe hex")
    ap.add_argument("--tol", type=int, default=70, help="Farbtoleranz je Kanal")
    ap.add_argument("--min-frac", type=float, default=0.25, help="Mindestanteil Gelb pro Zeile")
    ap.add_argument("--label-w", type=float, default=0.055, help="Schildbreite als Anteil der Bildbreite")
    ap.add_argument("--label-side", choices=["left", "right"], default="left")
    ap.add_argument("--out", help="Ausgabedatei (Standard: <bild>_cracks.txt)")
    ap.add_argument("--copy", action="store_true", help="in die Zwischenablage (pbcopy)")
    ap.add_argument("--debug", action="store_true", help="Tabelle y / Schild / Schätzung")
    args = ap.parse_args()

    img = Image.open(args.image).convert("RGB")
    rgb = np.asarray(img)
    H, W, _ = rgb.shape
    color = tuple(int(args.color[i:i + 2], 16) for i in (0, 2, 4))
    mask = color_mask(rgb, color, args.tol)
    step = args.tick * args.rows
    off = args.offset % step

    lw = int(W * args.label_w)
    lx0, lx1 = (0, lw) if args.label_side == "left" else (W - lw, W)
    cx0, cx1 = (lw, W) if args.label_side == "left" else (0, W - lw)

    ys = find_lines(mask, args.min_frac, cx0, cx1)
    if len(ys) < 2:
        sys.exit(f"Nur {len(ys)} Linie(n) gefunden – --color/--tol/--min-frac prüfen.")

    gaps = np.diff(sorted(ys))
    half_h = 0.0048 * W                                  # halbe Schrifthöhe (MotiveWave-Standard)
    yel = yellowness(rgb)
    labels = [read_label(yel, y, lx0, lx1, max(half_h, 0.0045 * W)) for y in ys]

    # Eichung
    if args.low is not None and args.high is not None:
        a, b = np.polyfit([ys[0], ys[-1]], [args.low, args.high], 1)
    else:
        pairs = [(y, p) for y, p in zip(ys, labels) if p is not None and on_grid(p, step, off)]
        fitres = ransac(pairs, tol_px=1.5)
        if fitres is None:
            sys.exit("Eichung fehlgeschlagen (zu wenige lesbare Schilder). Mit --low/--high von Hand eichen.")
        a, b = fitres
    tol_price = lambda a: max(0.6 * step, 1.5 * abs(a))  # Schild muss innerhalb ±1.5 px passen
    for _ in range(3):                                   # Gerade nur über bestätigte Schilder
        ok = [(y, l) for y, l in zip(ys, labels)
              if l is not None and on_grid(l, step, off) and abs(l - (a * y + b)) <= tol_price(a)]
        if len(ok) >= 3 and args.low is None:
            a, b = np.polyfit([y for y, _ in ok], [l for _, l in ok], 1)
    px_per_step = step / abs(a)

    result, unsure = [], []
    for y, lab in zip(ys, labels):
        est = a * y + b
        snapped = off + round((est - off) / step) * step
        if lab is not None and on_grid(lab, step, off) and abs(lab - est) <= tol_price(a):
            result.append((lab, ""))
        else:
            result.append((snapped, "?"))
            unsure.append((snapped, lab))
        if args.debug:
            print(f"y={y:8.1f}  Schild={lab}  Schätzung={est:10.2f}  → {result[-1][0]:.2f}{result[-1][1]}")

    dec = max(2, -int(math.floor(math.log10(args.tick))))
    fmt = f"{{:.{dec}f}}"
    seen, final = set(), []
    for p, flag in sorted(result):
        k = round(p, 6)
        if k not in seen:
            seen.add(k)
            final.append(fmt.format(p))
    text = "\n".join(final) + "\n"

    out = Path(args.out) if args.out else Path(args.image).with_name(Path(args.image).stem + "_cracks.txt")
    out.write_text(text)
    print(text, end="")
    print(f"--- {len(final)} Cracks ({len(ys)} Linien) → {out}")
    print(f"Auflösung: {px_per_step:.1f} px pro Rasterschritt")
    if unsure:
        print(f"PRÜFEN ({len(unsure)}): Schild unlesbar/unpassend, Preis aus Pixel-Höhe genommen:")
        for p, lab in unsure:
            print(f"   {fmt.format(p)}   (Schild gelesen: {lab})")
        if px_per_step < 3:
            print("   Bei unter 3 px/Schritt kann dieser Wert ±1 Schritt daneben liegen.")
    else:
        print("Alle Linien per Schild UND Pixel-Höhe bestätigt.")
    if args.copy:
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
        print("In Zwischenablage kopiert.")


if __name__ == "__main__":
    main()
