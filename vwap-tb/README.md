# VWAP 2σ Top/Bottom (VWAP-TB)

Umkehr-Signale am ±2σ-VWAP-Band mit Footprint-Absorption. Gedacht für NQ/MNQ auf 15s-, 30s- und 1m-Charts.

| Datei | Zweck |
|---|---|
| `VWAP-TB_indicator.pine` | Indikator: Dreiecke, Status-Tabelle, `alert()` |
| `VWAP-TB_strategy.pine` | Gleiche Signale als Strategie: Einstieg, SL, drei Teilziele |

## Strategie-Logik

- **Einstieg:** Dreieck bei Kerzenschluss → Market-Order zur nächsten Eröffnung, nur wenn flat.
- **SL:** hinter dem Absorptions-Extrem + Puffer. Puffer = max(Ticks, ATR × Faktor × Vola-Regime × Volumen-Faktor).
  Vola-Regime = ATR 30 min ÷ ATR 120 min (0.8–1.5), Volumen-Faktor aus dem Relativvolumen der Setup-Kerze (1.0–1.5).
  Mindestens 0.5 × ATR. Über 3 × ATR wird der Trade ausgelassen, statt den Stop enger zu ziehen.
- **Ziele:** TP1/TP2/TP3 = 1R/2R/3R, Aufteilung 33/33/Rest. Hybrid-Modus: TP3 am VWAP, wenn er weiter weg liegt.
- **Management:** nach TP1 SL auf Break Even für den Rest der Position, danach wird er nicht mehr bewegt. Optional Zeit-Stop und Flat vor der CME-Pause.
- **Größe:** fix (mindestens 3 Kontrakte) oder aus dem Risiko in $ (Kontrakte = Risiko ÷ (SL-Abstand × Punktwert)).

Entfernt: die Regel „Farbe gegen Delta“, weil sie in TradingView keine Signale mehr erzeugt hat.
