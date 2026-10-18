"""
Projekt ib-first: baut ib-first/IB-First.pine aus ib-first/IB-First_template.pine und results/ib_first_model.json
(erzeugt von data-lab/ib_first_model.py – dort stehen Analyse, Auswahl und Test).

Je Markt:
  B0/B1  Koeffizienten je Startzeit × IB-Länge: Ausdehnung (12), Ziel vor Stop (10), Stop-Seite (10) = 32 Zahlen,
         je Zahl 2 Zeichen (Basis 62, Schritt 0,01, ±19,2); fehlend = „~“
  BL     beste IB-Länge je Startzeit (über alle Tage; je Wochentag brachte im Test nichts) als Ziffer 1–4 (= 15/30/45/60 Min)

Aufruf: python data-lab/ib_first_build.py
"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent
J = json.loads((HERE / "results/ib_first_model.json").read_text())
MARKETS = ["NQ", "ES", "RTY", "GC"]
STARTS = [f"{(18 + i) % 24:02d}:00" for i in range(22)] + ["08:30", "09:30", "10:30"]
LENGTHS = [15, 30, 45, 60]
ALPHA = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
NCF, KPB, CMAX = 32, 13, 19.2
LEVEL_TXT = {"A": "nur was zuerst kam", "B": "zuerst + IB-Größe", "C": "zuerst + IB-Größe + Lage des Kurses",
             "D": "zuerst + IB-Größe + Lage des Kurses + Wochentag"}


def enc2(x):
    i = int(round(float(np.clip(x, -CMAX, CMAX)) * 100)) + 1922
    return ALPHA[i // 62] + ALPHA[i % 62]


loads = []
for mk in MARKETS:
    bodies = []
    for st in STARTS:
        for L in LENGTHS:
            c = J["coef"].get(f"{mk}|{st}|{L}")
            bodies.append("~" * NCF * 2 if c is None else "".join(enc2(x) for x in c["ext"] + c["zuerst"] + c["erst"]))
    per_key = [("".join(bodies[i * 4:(i + 1) * 4])) for i in range(len(STARTS))]
    for b in range(2):
        blk = "".join(per_key[b * KPB:(b + 1) * KPB])
        assert len(blk) < 4096
        loads.append(f'B{b} := barstate.isfirst and mk == "{mk}" ? "{blk}" : B{b}')
    bl = "".join(str(LENGTHS.index(J["bestLall"].get(f"{mk}|{st}", 30)) + 1) for st in STARTS)
    loads.append(f'BL := barstate.isfirst and mk == "{mk}" ? "{bl}" : BL')
    assert all(len(J["coef"][k]["ext"]) == 12 and len(J["coef"][k]["zuerst"]) == 10 for k in J["coef"] if k.startswith(mk))

tpl = (ROOT / "ib-first/IB-First_template.pine").read_text()
pine = (tpl.replace("{{LOADS}}", "\n".join(loads)).replace("{{KEYS}}", " ".join(STARTS)).replace("{{KPB}}", str(KPB))
           .replace("{{ZMAX}}", str(J["zmax"])).replace("{{END}}", J["end"])
           .replace("{{D60}}", str(J["dtp"]["0.6"])).replace("{{D70}}", str(J["dtp"]["0.7"]))
           .replace("{{D80}}", str(J["dtp"]["0.8"])).replace("{{D90}}", str(J["dtp"]["0.9"]))
           .replace("{{MODEL}}", f"{LEVEL_TXT[J['level']]}, letzte {J['window']} Jahre, Dämpfung {J['lam']:g}"))
assert "{{" not in pine
(ROOT / "ib-first/IB-First.pine").write_text(pine)
print("Indikator:", len(pine.splitlines()), "Zeilen,", len(pine), "Zeichen, längste Zeile", max(map(len, pine.splitlines())))
