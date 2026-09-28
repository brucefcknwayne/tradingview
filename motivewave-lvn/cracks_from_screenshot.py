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

Normalfall – Bild aus der ZWISCHENABLAGE, nichts speichern:
  1. Cmd+Ctrl+Shift+4 → Leertaste → MotiveWave-Chartfenster anklicken
  2. python3 cracks_from_screenshot.py
  3. Die Preise liegen jetzt in der Zwischenablage → in TradingView Cmd+V

Weitere Aufrufe:
  python3 cracks_from_screenshot.py oben.png unten.png     (Dateien, mehrere zusammenführen)
  python3 cracks_from_screenshot.py --low 30289.50 --high 31017.50   (Eichung von Hand)

Installation (Mac):  brew install tesseract && pip3 install numpy pillow pytesseract
Tipp: Chartfenster möglichst hoch – je mehr Pixel pro Punkt, desto sicherer.
"""
import argparse
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageGrab, ImageOps

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
def load_images(paths):
    """(Name, Bild)-Liste: Dateien, oder ohne Angabe das Bild aus der Zwischenablage."""
    if paths:
        return [(Path(p).name, Image.open(p)) for p in paths]
    try:
        clip = ImageGrab.grabclipboard()
    except Exception as e:                            # z. B. Linux ohne xclip
        sys.exit(f"Zwischenablage nicht lesbar ({e}). Bilddatei als Argument angeben.")
    if isinstance(clip, list):                        # Datei im Finder kopiert → Pfad(e)
        clip = [Image.open(c) for c in clip if str(c).lower().endswith((".png", ".jpg", ".jpeg", ".tif", ".tiff"))]
        return [(f"Zwischenablage {i + 1}", im) for i, im in enumerate(clip)] or sys.exit("Kein Bild in der Zwischenablage.")
    if clip is None:
        sys.exit("Kein Bild in der Zwischenablage. Screenshot mit Cmd+Ctrl+Shift+4 machen (Ctrl = in die Zwischenablage).")
    try:                                              # zur Kontrolle ablegen
        d = Path.home() / "Documents" / "MotiveWave_Cracks"
        d.mkdir(parents=True, exist_ok=True)
        clip.save(d / "letzter_screenshot.png")
    except Exception:
        pass
    return [("Zwischenablage", clip)]


def diagnose(path, rgb, mask, x0, x1, min_frac):
    H, W, _ = rgb.shape
    frac = mask[:, x0:x1].sum(axis=1) / max(1, x1 - x0)
    print(f"DIAGNOSE {path}: Bild {W}×{H} px, gelbe Pixel gesamt {mask.mean() * 100:.2f} %")
    print(f"  beste Zeile: {frac.max() * 100:.1f} % gelb (nötig: {min_frac * 100:.0f} %) bei y={int(frac.argmax())}")
    px = rgb.reshape(-1, 3)
    sat = px[(px.max(axis=1).astype(int) - px.min(axis=1)) > 80]
    if len(sat):
        cols, cnt = np.unique((sat // 16) * 16, axis=0, return_counts=True)
        top = cols[np.argsort(-cnt)[:6]]
        print("  häufigste kräftige Farben (RGB):", ", ".join(f"({c[0]},{c[1]},{c[2]})" for c in top))
    if W < 600 or H < 400:
        print("  Bild sehr klein – war wirklich der Chart in der Zwischenablage?")
    print("  → Schick mir diese Ausgabe (und ~/Documents/MotiveWave_Cracks/letzter_screenshot.png).")


def process(name, image, args, step, off, color):
    path = name
    rgb = np.asarray(image.convert("RGB"))
    H, W, _ = rgb.shape
    yel = yellowness(rgb)
    # Gelb = nah an der Linienfarbe ODER allgemein gelblich (dunkleres Gelb, Farbprofil, Kantenglättung)
    mask = color_mask(rgb, color, args.tol) | (yel > 0.3)

    lw = int(W * args.label_w)
    lx0, lx1 = (0, lw) if args.label_side == "left" else (W - lw, W)
    cx0, cx1 = (lw, W) if args.label_side == "left" else (0, W - lw)

    ys = find_lines(mask, args.min_frac, cx0, cx1)
    if len(ys) < 2:
        diagnose(path, rgb, mask, cx0, cx1, args.min_frac)
        sys.exit(f"{path}: nur {len(ys)} Linie(n) gefunden.")

    half_h = 0.0048 * W                                  # halbe Schrifthöhe (MotiveWave-Standard)
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
            print(f"{path}: y={y:8.1f}  Schild={lab}  Schätzung={est:10.2f}  → {price:.2f}{'' if good else '?'}")
    print(f"{path}: {len(ys)} Linien, {px_per_step:.1f} px pro Rasterschritt, "
          f"{sum(r[1] for r in res)} bestätigt")
    return res, px_per_step


# ── Hauptprogramm ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="MotiveWave-Cracks aus Screenshot(s)")
    ap.add_argument("images", nargs="*", help="Screenshot-Dateien; ohne Angabe: Bild aus der Zwischenablage")
    ap.add_argument("--tick", type=float, default=0.25, help="Tickgröße (NQ/ES 0.25, GC 0.10)")
    ap.add_argument("--rows", type=int, default=4, help="Tick Interval der Study")
    ap.add_argument("--offset", type=float, default=0.5, help="Rasterversatz (NQ: 0.5 → x.50)")
    ap.add_argument("--low", type=float, help="Eichung von Hand (nur 1 Bild): Preis der untersten Linie")
    ap.add_argument("--high", type=float, help="Eichung von Hand (nur 1 Bild): Preis der obersten Linie")
    ap.add_argument("--color", default="ffff00", help="Linienfarbe hex")
    ap.add_argument("--tol", type=int, default=70, help="Farbtoleranz je Kanal")
    ap.add_argument("--min-frac", type=float, default=0.2, help="Mindestanteil Gelb pro Zeile")
    ap.add_argument("--label-w", type=float, default=0.055, help="Schildbreite als Anteil der Bildbreite")
    ap.add_argument("--label-side", choices=["left", "right"], default="left")
    ap.add_argument("--out", help="Ausgabedatei (Standard: ~/Documents/MotiveWave_Cracks/cracks.txt)")
    ap.add_argument("--no-copy", action="store_true", help="Ergebnis NICHT in die Zwischenablage legen")
    ap.add_argument("--copy", action="store_true", help=argparse.SUPPRESS)   # alt, ist jetzt Standard
    ap.add_argument("--debug", action="store_true", help="Tabelle y / Schild / Schätzung")
    args = ap.parse_args()
    images = load_images(args.images)
    if args.low is not None and len(images) > 1:
        sys.exit("--low/--high geht nur mit einem Bild.")

    step = args.tick * args.rows
    off = args.offset % step
    color = tuple(int(args.color[i:i + 2], 16) for i in (0, 2, 4))

    confirmed, cand = set(), []
    for name, image in images:
        res, pxs = process(name, image, args, step, off, color)
        for price, good, lab in res:
            if good:
                confirmed.add(price)
            else:
                cand.append((pxs, price, lab))
    # Unsichere Werte: ±1 Schritt um einen bestätigten → verwerfen; sonst gewinnt das
    # schärfere Bild (Cracks liegen bei Sensitivity 10 nie nur 1 Schritt auseinander).
    unsure = {}
    for pxs, p, lab in sorted(cand, key=lambda c: -c[0]):
        near = lambda q: abs(p - q) <= step + 1e-9
        if any(near(c) for c in confirmed) or any(near(u) for u in unsure):
            continue
        unsure[p] = (lab, pxs)

    dec = max(2, -int(math.floor(math.log10(args.tick))))
    fmt = f"{{:.{dec}f}}"
    final = [fmt.format(p) for p in sorted(confirmed | set(unsure))]
    text = "\n".join(final) + "\n"

    out = Path(args.out) if args.out else Path.home() / "Documents" / "MotiveWave_Cracks" / "cracks.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(text, end="")
    print(f"--- {len(final)} Cracks → {out}")
    if unsure:
        print(f"PRÜFEN ({len(unsure)}): Schild unlesbar/unpassend, Preis aus Pixel-Höhe genommen:")
        for p in sorted(unsure):
            lab, pxs = unsure[p]
            hint = "  ← kann ±1 Schritt daneben liegen" if pxs < 3 else ""
            print(f"   {fmt.format(p)}   (Schild gelesen: {lab}){hint}")
        print("   Tipp: diesen Bereich reingezoomt zusätzlich screenshotten (Cmd+Shift+4 = Datei) und beide")
        print("         Dateien übergeben: python3 cracks_from_screenshot.py bild1.png bild2.png")
    else:
        print("Alle Linien per Schild UND Pixel-Höhe bestätigt.")
    if not args.no_copy:
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            print("Preise in der Zwischenablage → in TradingView mit Cmd+V einfügen.")
        except (OSError, subprocess.CalledProcessError):
            print("Zwischenablage nicht verfügbar (kein Mac?) – Datei nutzen.")


if __name__ == "__main__":
    main()
