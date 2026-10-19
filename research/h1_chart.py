"""Grafik H1: Erwartungswert netto je Gruppe (Punkt + 95%-KI) vs. Zufall, 6 Felder (Chart-Typ × Stop)."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

R = Path(__file__).parent / "results"
X = pd.read_csv(R / "h1_groups.csv")
SIG, RND, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#1f1e1c", "#6b6a64", "#e6e5e0"
groups = list(dict.fromkeys(X["Gruppe"]))
fig, axes = plt.subplots(2, 3, figsize=(15, 8.5), sharey=True, facecolor="#fcfcfb")
for ci, chart in enumerate(["1m", "Vol 500", "Vol 1000"]):
    for si, stop in enumerate(["A: 20 Pkt", "B: Serien-Extrem"]):
        ax = axes[si, ci]; ax.set_facecolor("#fcfcfb")
        d = X[(X["Chart"] == chart) & (X["Stop"] == stop)].set_index("Gruppe").loc[groups]
        y = range(len(groups))
        ax.axvline(0, color=MUTED, lw=1)
        ax.hlines(y, d["KI95 unten"], d["KI95 oben"], color=SIG, lw=2)
        ax.scatter(d["EW netto"], y, s=64, color=SIG, zorder=3, edgecolor="#fcfcfb", linewidth=2, label="Signal (95%-KI)")
        ax.scatter(d["Zufall EW"], y, s=64, marker="D", color=RND, zorder=3, edgecolor="#fcfcfb", linewidth=2, label="Zufall")
        ax.set_yticks(list(y)); ax.set_yticklabels(groups, color=INK, fontsize=9); ax.invert_yaxis()
        ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(GRID); ax.tick_params(colors=MUTED, length=0)
        ax.set_title(f"{chart} · Stop {stop}", color=INK, fontsize=11, loc="left")
        if si == 1:
            ax.set_xlabel("Erwartungswert pro Trade nach Kosten (Punkte)", color=MUTED, fontsize=9)
h, l = axes[0, 0].get_legend_handles_labels()
fig.legend(h, l, loc="upper right", frameon=False, fontsize=10)
fig.suptitle("H1 Zera-Reversal: Signal vs. Zufall – kein Edge (0 von 54 Tests nach Holm signifikant)", x=0.01, ha="left", color=INK, fontsize=13)
fig.tight_layout(rect=(0, 0, 1, 0.95))
fig.savefig(R / "h1_ev_vs_random.png", dpi=130)
