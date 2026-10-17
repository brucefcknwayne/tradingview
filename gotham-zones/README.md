# gotham-zones

Gotham Zones (±0.5/1/1.5/2σ um das Daily Open, σ aus VIX1D/VIX9D/VXN) – Auswertung und Strategie.

- `GZ-1s-Breakout_strategy.pine` – Long-Breakout über die +1σ-Zone, erster Touch 09:30–11:00 NY,
  SL 1.5 × Zonenhöhe, TP 2R, flat 16:00.

Ergebnisse (Python, `data-lab/`):
- Zonen pauschal (Fade oder Breakout) haben keinen Vorteil, Reaktion im Median 20–30 Pkt
  (`data-lab/results/gotham_zones_reaction.md`, `gotham_zones_trades.md`).
- Einziger Kandidat aus 1.217 Bedingungs-Tests: +1σ-Breakout am Vormittag
  (`data-lab/results/zones_edge_search.md`, `zones_breakout_check.md`).
  30D Test 2021–26 +0.37R/Trade (t 2.4), 9D +0.14R, 1D +0.02R; 2024–25 schwach.
