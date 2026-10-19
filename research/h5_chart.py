"""Grafik H5: Gewinnrate (+60 vor −20) je Merkmals-Dezil, Explore vs. Validate, 1m."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

R = Path(__file__).parent / "results"
L = pd.read_csv(R / "h5_lift.csv"); M = pd.read_csv(R / "h5_model.csv").set_index("Chart")
EXP, VAL, INK, MUTED, GRID, BG = "#2a78d6", "#eb6834", "#1f1e1c", "#6b6a64", "#e6e5e0", "#fcfcfb"
NAMES = {"rel_min": "Uhrzeit (Minuten seit 18:00)", "bar_sd_pts": "Kerzen-Volatilität (Pkt)", "range_used": "Tagesrange verbraucht",
         "d_prev_hlc": "Abstand Vortag Hoch/Tief/Close (Pkt)", "d_prev_va": "Abstand Vortag POC/VAH/VAL (Pkt)", "run_delta_share": "Delta der Serie (Anteil)"}
fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharey=True, facecolor=BG)
for ax, (f, title) in zip(axes.flat, NAMES.items()):
    d = L[(L["Chart"] == "1m") & (L["Merkmal"] == f)].sort_values("Bin")
    ax.set_facecolor(BG)
    ax.plot(d["Bin"] + 1, d["Explore Gewinner %"], color=EXP, lw=2, marker="o", ms=7, mec=BG, mew=2, label="2022–2024 (Suchen)")
    ax.plot(d["Bin"] + 1, d["Validate Gewinner %"], color=VAL, lw=2, marker="D", ms=7, mec=BG, mew=2, label="2025–2026 (Prüfen)")
    ax.axhline(M.loc["1m", "Grundrate Explore %"], color=EXP, lw=1, ls=":")
    ax.axhline(M.loc["1m", "Grundrate Validate %"], color=VAL, lw=1, ls=":")
    ax.axhline(26.25, color=MUTED, lw=1, ls="--")
    ax.set_title(title, color=INK, fontsize=11, loc="left"); ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=MUTED, length=0)
    ax.set_xticks(range(1, 11)); ax.set_xlabel("Dezil (1 = niedrigster Wert)", color=MUTED, fontsize=9)
axes[0, 0].set_ylabel("Gewinner % (+60 vor −20)", color=MUTED); axes[1, 0].set_ylabel("Gewinner % (+60 vor −20)", color=MUTED)
axes[0, 0].text(10, 26.8, "grobe Gewinnschwelle nach Kosten ≈ 26 %", color=MUTED, fontsize=8, ha="right")
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="upper right", frameon=False, fontsize=10)
fig.suptitle("H5 (1m): Gewinner kommen öfter bei Bewegung (RTH, hohe Volatilität) – Levels und Delta machen kaum Unterschied",
             x=0.01, ha="left", color=INK, fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.94)); fig.savefig(R / "h5_lift.png", dpi=130)
