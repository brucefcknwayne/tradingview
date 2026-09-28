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
  python3 cracks_from_screenshot.py oben.png unten.png --copy        (mehrere Bilder zusammenführen)
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


# ── ein Bild auswerten ───────────────────────────────────────────────────────
def process(path, args, step, off, color):
    rgb = np.asarray(Image.open(path).convert("RGB"))
    H, W, _ = rgb.shape
    mask = color_mask(rgb, color, args.tol)

    lw = int(W * args.label_w)
    lx0, lx1 = (0, lw) if args.label_side == "left" else (W - lw, W)
    cx0, cx1 = (lw, W) if args.label_side == "left" else (0, W - lw)

    ys = find_lines(mask, args.min_frac, cx0, cx1)
    if len(ys) < 2:
        sys.exit(f"{path}: nur {len(ys)} Linie(n) gefunden – --color/--tol/--min-frac prüfen.")

    half_h = 0.0048 * W                                  # halbe Schrifthöhe (MotiveWave-Standard)
    yel = yellowness(rgb)
    labels = [read_label(yel, y, lx0, lx1, half_h) for y in ys]

    # Eichung
    if args.low is not None and args.high is not None:
        a, b = np.polyfit([ys[0], ys[-1]], [args.low, args.high], 1)
    else:
        pairs = [(y, p) for y, p in zip(ys, labels) if p is not None and on_grid(p, step, off)]
        fitres = ransac(pairs, tol_px=1.5)
        if fitres is None:
            sys.exit(f"{path}: Eichung fehlgeschlagen (zu wenige lesbare Schilder). Mit --low/--high eichen.")
        a, b = fitres
    tol_price = lambda a: max(0.6 * step, 1.5 * abs(a))  # Schild muss innerhalb ±1.5 px passen
    for _ in range(3):                                   # Gerade nur über bestätigte Schilder
        ok = [(y, l) for y, l in zip(ys, labels)
              if l is not None and on_grid(l, step, off) and abs(l - (a * y + b)) <= tol_price(a)]
        if len(ok) >= 3 and args.low is None:
            a, b = np.polyfit([y for y, _ in ok], [l for _, l in ok], 1)
    px_per_step = step / abs(a)

    res = []                                             # (Preis, bestätigt, gelesenes Schild)
    for y, lab in zip(ys, labels):
        est = a * y + b
        good = lab is not None and on_grid(lab, step, off) and abs(lab - est) <= tol_price(a)
        price = lab if good else off + round((est - off) / step) * step
        res.append((round(price, 6), good, lab))
        if args.debug:
            print(f"{Path(path).name}: y={y:8.1f}  Schild={lab}  Schätzung={est:10.2f}  → {price:.2f}{'' if good else '?'}")
    print(f"{Path(path).name}: {len(ys)} Linien, {px_per_step:.1f} px pro Rasterschritt, "
          f"{sum(r[1] for r in res)} bestätigt")
    return res, px_per_step


# ── Hauptprogramm ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="MotiveWave-Cracks aus Screenshot(s)")
    ap.add_argument("images", nargs="+", help="ein oder mehrere Screenshots (z. B. obere + untere Hälfte)")
    ap.add_argument("--tick", type=float, default=0.25, help="Tickgröße (NQ/ES 0.25, GC 0.10)")
    ap.add_argument("--rows", type=int, default=4, help="Tick Interval der Study")
    ap.add_argument("--offset", type=float, default=0.5, help="Rasterversatz (NQ: 0.5 → x.50)")
    ap.add_argument("--low", type=float, help="Eichung von Hand (nur 1 Bild): Preis der untersten Linie")
    ap.add_argument("--high", type=float, help="Eichung von Hand (nur 1 Bild): Preis der obersten Linie")
    ap.add_argument("--color", default="ffff00", help="Linienfarbe hex")
    ap.add_argument("--tol", type=int, default=70, help="Farbtoleranz je Kanal")
    ap.add_argument("--min-frac", type=float, default=0.25, help="Mindestanteil Gelb pro Zeile")
    ap.add_argument("--label-w", type=float, default=0.055, help="Schildbreite als Anteil der Bildbreite")
    ap.add_argument("--label-side", choices=["left", "right"], default="left")
    ap.add_argument("--out", help="Ausgabedatei (Standard: <erstes Bild>_cracks.txt)")
    ap.add_argument("--copy", action="store_true", help="in die Zwischenablage (pbcopy)")
    ap.add_argument("--debug", action="store_true", help="Tabelle y / Schild / Schätzung")
    args = ap.parse_args()
    if args.low is not None and len(args.images) > 1:
        sys.exit("--low/--high geht nur mit einem Bild.")

    step = args.tick * args.rows
    off = args.offset % step
    color = tuple(int(args.color[i:i + 2], 16) for i in (0, 2, 4))

    confirmed, unsure, min_px = set(), {}, 1e9
    for path in args.images:
        res, pxs = process(path, args, step, off, color)
        min_px = min(min_px, pxs)
        for price, good, lab in res:
            if good:
                confirmed.add(price)
            else:
                unsure.setdefault(price, (lab, pxs))
    # unsichere Werte, die in einem anderen Bild bestätigt (±1 Schritt) wurden, verwerfen
    unsure = {p: v for p, v in unsure.items()
              if p not in confirmed and not any(abs(p - c) <= step + 1e-9 for c in confirmed)}

    dec = max(2, -int(math.floor(math.log10(args.tick))))
    fmt = f"{{:.{dec}f}}"
    final = [fmt.format(p) for p in sorted(confirmed | set(unsure))]
    text = "\n".join(final) + "\n"

    first = Path(args.images[0])
    out = Path(args.out) if args.out else first.with_name(first.stem + "_cracks.txt")
    out.write_text(text)
    print(text, end="")
    print(f"--- {len(final)} Cracks → {out}")
    if unsure:
        print(f"PRÜFEN ({len(unsure)}): Schild unlesbar/unpassend, Preis aus Pixel-Höhe genommen:")
        for p in sorted(unsure):
            lab, pxs = unsure[p]
            hint = "  ← kann ±1 Schritt daneben liegen" if pxs < 3 else ""
            print(f"   {fmt.format(p)}   (Schild gelesen: {lab}){hint}")
        print("   Tipp: reingezoomt ein 2. Bild von diesem Bereich machen und beide Bilder übergeben.")
    else:
        print("Alle Linien per Schild UND Pixel-Höhe bestätigt.")
    if args.copy:
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
        print("In Zwischenablage kopiert.")


if __name__ == "__main__":
    main()
