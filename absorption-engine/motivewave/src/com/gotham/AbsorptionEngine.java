package com.gotham;

import java.awt.Color;
import java.awt.Font;
import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.StandardOpenOption;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.TimeZone;
import java.util.TreeMap;

import com.motivewave.platform.sdk.common.Coordinate;
import com.motivewave.platform.sdk.common.DataContext;
import com.motivewave.platform.sdk.common.DataSeries;
import com.motivewave.platform.sdk.common.Defaults;
import com.motivewave.platform.sdk.common.Enums;
import com.motivewave.platform.sdk.common.Instrument;
import com.motivewave.platform.sdk.common.Tick;
import com.motivewave.platform.sdk.common.desc.BooleanDescriptor;
import com.motivewave.platform.sdk.common.desc.ColorDescriptor;
import com.motivewave.platform.sdk.common.desc.DoubleDescriptor;
import com.motivewave.platform.sdk.common.desc.IntegerDescriptor;
import com.motivewave.platform.sdk.common.desc.StringDescriptor;
import com.motivewave.platform.sdk.common.desc.ValueDescriptor;
import com.motivewave.platform.sdk.draw.Label;
import com.motivewave.platform.sdk.draw.Marker;
import com.motivewave.platform.sdk.study.Study;
import com.motivewave.platform.sdk.study.StudyHeader;

/**
 * Absorption Engine – erkennt Absorption direkt aus dem Orderflow (Rithmic-Ticks mit Aggressor-Seite und Bid/Ask-Größen).
 *
 * Grundidee: Absorption = Aggression ohne Ergebnis. Aggressive Käufer/Verkäufer handeln viel, aber der Preis kommt nicht voran,
 * weil eine passive Gegenseite alles aufnimmt. Alle Schwellen sind RELATIV zum eigenen Markt (Median der letzten N Kerzen,
 * Anteil der Kerzen-Range, ATR) – keine festen Ticks. Gleiche Einstellungen funktionieren damit auf NQ, ES, GC, MNQ …
 *
 * Arten (jede einzeln schaltbar):
 *  1 FLIP     Delta-Flip: rote Kerze mit positivem Delta (Käufer absorbiert → bärisch) bzw. grüne Kerze mit negativem Delta.
 *  2 EFFORT   Aufwand ohne Ergebnis: Volumen weit über normal, Range klein dafür.
 *  3 WICK     Aggressoren hauen ins Extrem der Kerze (oberes/unteres Viertel), der Preis wird zurückgewiesen (Docht).
 *  4 WALL     Passive Wand: eine Preiszeile mit ungewöhnlich viel Volumen bei Delta nahe null am Extrem (Käufe = Verkäufe).
 *  5 REFILL   Iceberg/Refill: an einem Preis wird ein Vielfaches der sichtbaren Bid-/Ask-Größe gehandelt und der Preis hält.
 *  6 CVD      CVD-Divergenz: neues Tief/Hoch, aber der kumulierte Delta bestätigt es nicht.
 *  7 TRAPPED  Starker Aggressions-Push auf ein neues Extrem, nächste Kerze schließt zurück hinter dessen Open.
 *  8 EXHAUST  Erschöpfung: drei Kerzen in eine Richtung, Volumen je Preisfortschritt steigt stark (Aufwand wird teurer).
 *  9 STACKED  Gestapelte Imbalances (diagonal) im oberen/unteren Drittel, aber die Kerze schließt auf der anderen Seite → Aggressoren gefangen.
 * 10 D-REV    Delta-Umkehr in der Kerze: Delta war stark positiv (negativ), schließt aber fast bei null/dagegen und der Preis kommt nicht voran.
 *
 * Anzeige „3/10“ = wie viele der 10 Modi gleichzeitig Absorption melden (Konfluenz). Mehr Modi = valider.
 *
 * Live: Die laufende Kerze wird bei jedem Tick bewertet → Status ABSORBING / WAITING / BREAKING im Label rechts.
 * Ergebnis je Ereignis: HELD (Preis läuft ≥ x·ATR weg), FAILED (≥ y·ATR durch das Extrem), EXPIRED (nach n Kerzen).
 */
@StudyHeader(
  namespace = "com.gotham",
  id = "ABSORPTION_ENGINE",
  name = "Absorption Engine",
  label = "Absorption Engine",
  desc = "Absorption aus dem Orderflow: Delta-Flip, Aufwand ohne Ergebnis, Wick, passive Wand, Refill/Iceberg, CVD-Divergenz, Trapped, Erschöpfung. Relative Schwellen, keine festen Ticks.",
  menu = "Gotham",
  overlay = true,
  signals = true,
  requiresVolume = true,
  supportsBarUpdates = true,
  barUpdatesByDefault = true)
public class AbsorptionEngine extends Study
{
  enum Values { DELTA, CVD, ABS_DIR, ABS_STRENGTH }
  enum Signals { BULL_ABSORPTION, BEAR_ABSORPTION, ABSORPTION_HELD, ABSORPTION_FAILED }

  // ── Setting-Keys ──
  static final String LOOKBACK = "lookback", MIN_STRENGTH = "minStrength", SWING = "swing";
  static final String USE_FLIP = "useFlip", FLIP_BODY = "flipBody", FLIP_DELTA = "flipDelta";
  static final String USE_EFFORT = "useEffort", EFF_VOL = "effVol", EFF_RATIO = "effRatio";
  static final String USE_WICK = "useWick", WICK_ZONE = "wickZone", WICK_SHARE = "wickShare", WICK_DOM = "wickDom", WICK_LEN = "wickLen";
  static final String USE_WALL = "useWall", WALL_MULT = "wallMult", WALL_BAL = "wallBal";
  static final String USE_REFILL = "useRefill", REFILL_MIN = "refillMin", REFILL_SHARE = "refillShare";
  static final String USE_CVD = "useCvd";
  static final String USE_TRAP = "useTrap", TRAP_DELTA = "trapDelta";
  static final String USE_EXH = "useExh", EXH_GROWTH = "exhGrowth";
  static final String USE_STACK = "useStack", STACK_IMB = "stackImb", STACK_N = "stackN";
  static final String USE_DREV = "useDrev", DREV_DELTA = "drevDelta", DREV_KEEP = "drevKeep";
  static final String MIN_MODES = "minModes";
  static final String HELD_ATR = "heldAtr", FAIL_ATR = "failAtr", MAX_BARS = "maxBars";
  static final String BULL_COLOR = "bullColor", BEAR_COLOR = "bearColor", SHOW_TEXT = "showText", SHOW_STATUS = "showStatus";
  static final String LOG_FILE = "logFile";

  static final String[] TYPE_NAMES = { "FLIP", "EFFORT", "WICK", "WALL", "REFILL", "CVD", "TRAPPED", "EXHAUST", "STACKED", "D-REV" };

  // ── Footprint je Kerze ──
  static final class Row { double buy, sell, maxBidShown, maxAskShown, bidHitVol, askHitVol; }
  static final class BarFP {
    final TreeMap<Float, Row> rows = new TreeMap<>();
    double buy, sell, maxD, minD;
    void add(Tick t) {
      float px = t.getPrice();
      double v = t.getVolumeAsFloat();
      double d = buy - sell + (t.isAskTick() ? v : -v);
      maxD = Math.max(maxD, d); minD = Math.min(minD, d);
      Row r = rows.computeIfAbsent(px, k -> new Row());
      if (t.isAskTick()) {
        buy += v; r.buy += v;
        if (t.getAskPrice() == px) { r.maxAskShown = Math.max(r.maxAskShown, t.getAskSizeAsFloat()); r.askHitVol += v; }
      }
      else {
        sell += v; r.sell += v;
        if (t.getBidPrice() == px) { r.maxBidShown = Math.max(r.maxBidShown, t.getBidSizeAsFloat()); r.bidHitVol += v; }
      }
    }
    double delta() { return buy - sell; }
    double vol() { return buy + sell; }
    double maxRowVol() { double m = 0; for (Row r : rows.values()) m = Math.max(m, r.buy + r.sell); return m; }
  }

  /** Ergebnis einer Bewertung (ganze oder laufende Kerze). */
  static final class Hit {
    int dir, modes; double strength; double price; final List<String> types = new ArrayList<>();
    String typeText() { return String.join("+", types); }
  }

  /** Offene Absorption für die Ergebnis-Auswertung. */
  static final class Active { int dir, bar; double extreme, atr; long time; String text; }

  private final Map<Long, BarFP> fps = new HashMap<>();
  private final List<Tick> pending = new ArrayList<>();
  private final List<Active> active = new ArrayList<>();
  private boolean ticksLoaded = false;
  private long lastLoadedTick = Long.MIN_VALUE;
  private int lastDone = -1;
  private double cvd = 0;
  private final List<Double> cvdAt = new ArrayList<>();
  private Label statusLabel;
  private int nAbs, nHeld, nFail, nExp;
  private String lastOutcome = "–";

  @Override
  public void initialize(Defaults defaults)
  {
    var sd = createSD();
    var tab = sd.addTab("Engine");
    var grp = tab.addGroup("Allgemein");
    grp.addRow(new IntegerDescriptor(LOOKBACK, "Normal = Median der letzten Kerzen", 100, 20, 2000, 10));
    grp.addRow(new IntegerDescriptor(SWING, "Extrem/Divergenz: Kerzen zurück", 60, 3, 500, 1));
    grp.addRow(new IntegerDescriptor(MIN_STRENGTH, "Mindest-Stärke (0–100)", 0, 0, 100, 5));
    grp.addRow(new IntegerDescriptor(MIN_MODES, "Mindestens Modi gleichzeitig (x/10)", 1, 1, 10, 1));

    grp = tab.addGroup("1 Delta-Flip");
    grp.addRow(new BooleanDescriptor(USE_FLIP, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(FLIP_BODY, "Kerzenkörper ≥ Anteil der Range", 0.40, 0.0, 1.0, 0.05));
    grp.addRow(new DoubleDescriptor(FLIP_DELTA, "|Delta| ≥ × normal", 1.5, 0.0, 20.0, 0.1));

    grp = tab.addGroup("2 Aufwand ohne Ergebnis");
    grp.addRow(new BooleanDescriptor(USE_EFFORT, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(EFF_VOL, "Volumen ≥ × normal", 2.5, 1.0, 20.0, 0.1));
    grp.addRow(new DoubleDescriptor(EFF_RATIO, "Ergebnis/Aufwand ≤ (Range-Faktor ÷ Volumen-Faktor)", 0.4, 0.05, 2.0, 0.05));

    grp = tab.addGroup("3 Wick-Absorption");
    grp.addRow(new BooleanDescriptor(USE_WICK, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(WICK_ZONE, "Extrem-Zone = Anteil der Range", 0.25, 0.05, 0.5, 0.05));
    grp.addRow(new DoubleDescriptor(WICK_SHARE, "Aggressor-Volumen in Zone ≥ Anteil des Kerzenvolumens", 0.35, 0.01, 1.0, 0.01));
    grp.addRow(new DoubleDescriptor(WICK_DOM, "Aggressoren / Gegenseite in Zone ≥", 3.0, 1.0, 20.0, 0.1));
    grp.addRow(new DoubleDescriptor(WICK_LEN, "Docht ≥ Anteil der Range", 0.50, 0.0, 1.0, 0.05));

    grp = tab.addGroup("4 Passive Wand");
    grp.addRow(new BooleanDescriptor(USE_WALL, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(WALL_MULT, "Zeilen-Volumen ≥ × normale Max-Zeile", 2.5, 1.0, 20.0, 0.1));
    grp.addRow(new DoubleDescriptor(WALL_BAL, "|Zeilen-Delta| / Zeilen-Volumen ≤", 0.15, 0.0, 1.0, 0.05));

    grp = tab.addGroup("5 Refill / Iceberg (braucht Bid/Ask-Größen)");
    grp.addRow(new BooleanDescriptor(USE_REFILL, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(REFILL_MIN, "Gehandelt ≥ × größte sichtbare Größe", 2.0, 1.0, 50.0, 0.5));
    grp.addRow(new DoubleDescriptor(REFILL_SHARE, "Volumen an dem Preis ≥ Anteil des Kerzenvolumens", 0.08, 0.0, 1.0, 0.01));

    grp = tab.addGroup("6–8 Mehrkerzen-Muster");
    grp.addRow(new BooleanDescriptor(USE_CVD, "6 CVD-Divergenz", true));
    grp.addRow(new BooleanDescriptor(USE_TRAP, "7 Trapped (Push scheitert)", true));
    grp.addRow(new DoubleDescriptor(TRAP_DELTA, "Trapped: Push-|Delta| ≥ × normal", 2.0, 0.5, 20.0, 0.1));
    grp.addRow(new BooleanDescriptor(USE_EXH, "8 Erschöpfung", true));
    grp.addRow(new DoubleDescriptor(EXH_GROWTH, "Erschöpfung: Aufwand je Fortschritt wächst ≥ ×", 3.0, 1.1, 20.0, 0.1));

    grp = tab.addGroup("9 Stacked Imbalance gescheitert");
    grp.addRow(new BooleanDescriptor(USE_STACK, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(STACK_IMB, "Imbalance (diagonal) ≥ ×", 4.0, 1.5, 20.0, 0.5));
    grp.addRow(new IntegerDescriptor(STACK_N, "Mindestens Preiszeilen hintereinander", 4, 2, 20, 1));

    grp = tab.addGroup("10 Delta-Umkehr in der Kerze");
    grp.addRow(new BooleanDescriptor(USE_DREV, "Aktiv", true));
    grp.addRow(new DoubleDescriptor(DREV_DELTA, "Max. Delta in der Kerze ≥ × normal", 2.0, 0.2, 20.0, 0.1));
    grp.addRow(new DoubleDescriptor(DREV_KEEP, "Schluss-Delta ≤ Anteil des Max-Deltas", 0.2, -1.0, 1.0, 0.05));

    tab = sd.addTab("Ergebnis & Anzeige");
    grp = tab.addGroup("Ergebnis (relativ zur ATR)");
    grp.addRow(new DoubleDescriptor(HELD_ATR, "HELD = Preis läuft ≥ × ATR weg", 0.5, 0.05, 10.0, 0.05));
    grp.addRow(new DoubleDescriptor(FAIL_ATR, "FAILED = ≥ × ATR durch das Extrem", 0.15, 0.01, 10.0, 0.01));
    grp.addRow(new IntegerDescriptor(MAX_BARS, "Entscheidung innerhalb Kerzen", 20, 1, 500, 1));
    grp = tab.addGroup("Anzeige");
    grp.addRow(new ColorDescriptor(BULL_COLOR, "Bullische Absorption", new Color(38, 166, 154)));
    grp.addRow(new ColorDescriptor(BEAR_COLOR, "Bärische Absorption", new Color(239, 83, 80)));
    grp.addRow(new BooleanDescriptor(SHOW_TEXT, "Art + Stärke am Marker", true));
    grp.addRow(new BooleanDescriptor(SHOW_STATUS, "Live-Status rechts", true));
    grp = tab.addGroup("Log");
    grp.addRow(new StringDescriptor(LOG_FILE, "CSV-Log (leer = aus)", ""));

    var desc = createRD();
    desc.exportValue(new ValueDescriptor(Values.DELTA, Enums.ValueType.DOUBLE, "Delta"));
    desc.exportValue(new ValueDescriptor(Values.CVD, Enums.ValueType.DOUBLE, "CVD"));
    desc.exportValue(new ValueDescriptor(Values.ABS_DIR, Enums.ValueType.INTEGER, "Absorption Richtung (+1/−1)"));
    desc.exportValue(new ValueDescriptor(Values.ABS_STRENGTH, Enums.ValueType.DOUBLE, "Absorption Stärke"));
    desc.declareSignal(Signals.BULL_ABSORPTION, "Bullische Absorption");
    desc.declareSignal(Signals.BEAR_ABSORPTION, "Bärische Absorption");
    desc.declareSignal(Signals.ABSORPTION_HELD, "Absorption gehalten");
    desc.declareSignal(Signals.ABSORPTION_FAILED, "Absorption gebrochen");
  }

  @Override
  public void clearState()
  {
    super.clearState();
    clearFigures();
    synchronized (this) {
      fps.clear(); pending.clear(); active.clear(); cvdAt.clear();
      ticksLoaded = false; lastLoadedTick = Long.MIN_VALUE; lastDone = -1; cvd = 0;
      statusLabel = null; nAbs = nHeld = nFail = nExp = 0; lastOutcome = "–";
    }
  }

  @Override
  protected void calculateValues(DataContext ctx) { update(ctx); }

  @Override
  public void onBarUpdate(DataContext ctx) { update(ctx); }

  @Override
  public void onBarClose(DataContext ctx) { update(ctx); }

  @Override
  public void onTick(DataContext ctx, Tick tick)
  {
    synchronized (this) {
      if (!ticksLoaded || tick.getTime() <= lastLoadedTick) return;
      var s = ctx.getDataSeries();
      int last = s.size() - 1;
      if (last < 0) return;
      if (tick.getTime() >= s.getEndTime(last)) { pending.add(tick); return; }
      bar(s, last).add(tick);
    }
  }

  // ═════════════════════════════ Hauptablauf ═════════════════════════════
  private synchronized void update(DataContext ctx)
  {
    DataSeries s = ctx.getDataSeries();
    int size = s.size();
    if (size < 3) return;
    if (!ticksLoaded) loadTicks(ctx, s);
    flushPending(s);
    var st = getSettings();
    int lb = st.getInteger(LOOKBACK, 100);

    // abgeschlossene Kerzen
    for (int i = lastDone + 1; i < size - 1; i++) {
      BarFP fp = bar(s, i);
      cvd += fp.delta();
      while (cvdAt.size() <= i) cvdAt.add(Double.NaN);
      cvdAt.set(i, cvd);
      s.setDouble(i, Values.DELTA, fp.delta());
      s.setDouble(i, Values.CVD, cvd);
      resolveActive(ctx, s, i);
      if (i >= Math.min(lb, 30)) {
        Hit h = evaluate(s, i, fp, false);
        if (h != null) emit(ctx, s, i, h);
      }
      s.setComplete(i);
      lastDone = i;
    }
    // laufende Kerze → Live-Status
    int cur = size - 1;
    BarFP live = bar(s, cur);
    s.setDouble(cur, Values.DELTA, live.delta());
    s.setDouble(cur, Values.CVD, cvd + live.delta());
    if (st.getBoolean(SHOW_STATUS, true)) drawStatus(s, cur, lastDone >= lb / 2 ? evaluate(s, cur, live, true) : null);
  }

  private BarFP bar(DataSeries s, int i) { return fps.computeIfAbsent(s.getStartTime(i), k -> new BarFP()); }

  private void loadTicks(DataContext ctx, DataSeries s)
  {
    Instrument ins = ctx.getInstrument();
    long start = s.getStartTime(0), end = s.getEndTime(s.size() - 1);
    final int[] idx = { 0 };
    final long[] lastT = { Long.MIN_VALUE };
    final int n = s.size();
    ins.forEachTick(start, end, true, t -> {
      long tt = t.getTime();
      while (idx[0] < n - 1 && tt >= s.getStartTime(idx[0] + 1)) idx[0]++;
      if (tt < s.getStartTime(idx[0])) return;
      fps.computeIfAbsent(s.getStartTime(idx[0]), k -> new BarFP()).add(t);
      lastT[0] = Math.max(lastT[0], tt);
    });
    lastLoadedTick = lastT[0];
    ticksLoaded = true;
  }

  private void flushPending(DataSeries s)
  {
    if (pending.isEmpty()) return;
    int last = s.size() - 1;
    var keep = new ArrayList<Tick>();
    for (Tick t : pending) {
      if (t.getTime() >= s.getEndTime(last)) { keep.add(t); continue; }
      int i = last;
      while (i > 0 && t.getTime() < s.getStartTime(i)) i--;
      bar(s, i).add(t);
    }
    pending.clear(); pending.addAll(keep);
  }

  // ═════════════════════════════ Bewertung ═════════════════════════════
  /** Bewertet Kerze i. live = laufende Kerze (nur Ein-Kerzen-Arten, Volumen-Normal zeitanteilig). */
  private Hit evaluate(DataSeries s, int i, BarFP fp, boolean live)
  {
    var st = getSettings();
    int lb = st.getInteger(LOOKBACK, 100), sw = st.getInteger(SWING, 60);
    double o = s.getOpen(i), c = s.getClose(i), hi = s.getHigh(i), lo = s.getLow(i);
    double rng = hi - lo, vol = fp.vol(), delta = fp.delta();
    if (vol <= 0) return null;

    // Normalwerte = Median der letzten lb abgeschlossenen Kerzen (ohne i)
    int from = Math.max(0, Math.min(i, lastDone + 1) - lb), to = Math.min(i, lastDone + 1);
    if (to - from < 10) return null;
    double[] vols = new double[to - from], dels = new double[to - from], rngs = new double[to - from], rows = new double[to - from];
    for (int k = from; k < to; k++) {
      BarFP b = bar(s, k);
      vols[k - from] = b.vol(); dels[k - from] = Math.abs(b.delta());
      rngs[k - from] = s.getHigh(k) - s.getLow(k); rows[k - from] = b.maxRowVol();
    }
    double mVol = median(vols), mDel = median(dels), mRng = median(rngs), mRow = median(rows);
    if (mVol <= 0 || mRng <= 0) return null;
    double frac = 1.0;
    if (live) {   // laufende Kerze: Normal-Volumen zeitanteilig
      long len = s.getEndTime(i) - s.getStartTime(i);
      long el = Math.max(1, Math.min(len, getNow(s, i) - s.getStartTime(i)));
      frac = Math.max(0.2, (double) el / Math.max(1, len));
    }
    double rv = vol / (mVol * frac), rd = Math.abs(delta) / Math.max(1e-9, mDel * frac), rr = rng / mRng;

    double[] bull = new double[TYPE_NAMES.length], bear = new double[TYPE_NAMES.length];
    double bullPx = lo, bearPx = hi;

    // 9 Stacked Imbalance gescheitert (diagonal: Kauf auf p gegen Verkauf eine Zeile tiefer)
    if (st.getBoolean(USE_STACK, true) && rng > 0 && fp.rows.size() >= 3) {
      double imb = st.getDouble(STACK_IMB, 4.0); int need = st.getInteger(STACK_N, 4);
      int runA = 0, bestA = 0, runB = 0, bestB = 0;
      for (Map.Entry<Float, Row> e : fp.rows.entrySet()) {
        float px = e.getKey(); Row r = e.getValue();
        var below = fp.rows.lowerEntry(px); var above = fp.rows.higherEntry(px);
        boolean askImb = below != null && px >= hi - rng / 3 && r.buy >= imb * Math.max(1, below.getValue().sell);
        boolean bidImb = above != null && px <= lo + rng / 3 && r.sell >= imb * Math.max(1, above.getValue().buy);
        runA = askImb ? runA + 1 : 0; bestA = Math.max(bestA, runA);
        runB = bidImb ? runB + 1 : 0; bestB = Math.max(bestB, runB);
      }
      double mid = (hi + lo) / 2;
      if (bestA >= need && c < mid) bear[8] = 50 + 50 * Math.min(1, (bestA - need) / 3.0 + 0.2);
      if (bestB >= need && c > mid) bull[8] = 50 + 50 * Math.min(1, (bestB - need) / 3.0 + 0.2);
    }
    // 10 Delta-Umkehr in der Kerze
    if (st.getBoolean(USE_DREV, true) && rng > 0) {
      double need = st.getDouble(DREV_DELTA, 2.0) * mDel * frac, keep = st.getDouble(DREV_KEEP, 0.2);
      if (fp.maxD >= need && delta <= keep * fp.maxD && c < hi - 0.3 * rng)
        bear[9] = 45 + 55 * Math.min(1, (fp.maxD - delta) / Math.max(1, 2 * mDel));
      if (-fp.minD >= need && -delta <= keep * -fp.minD && c > lo + 0.3 * rng)
        bull[9] = 45 + 55 * Math.min(1, (delta - fp.minD) / Math.max(1, 2 * mDel));
    }

    // 1 Delta-Flip
    if (st.getBoolean(USE_FLIP, true) && rng > 0) {
      double body = c - o;
      if (Math.abs(body) >= st.getDouble(FLIP_BODY, 0.4) * rng && rd >= st.getDouble(FLIP_DELTA, 1.5) && Math.signum(body) == -Math.signum(delta)) {
        double sc = 40 + 30 * Math.min(1, rd / 2.0) + 30 * Math.min(1, Math.abs(body) / rng);
        if (body > 0) bull[0] = sc; else bear[0] = sc;
      }
    }
    // 2 Aufwand ohne Ergebnis
    if (st.getBoolean(USE_EFFORT, true)) {
      double ratio = rr / Math.max(1e-9, rv);
      if (rv >= st.getDouble(EFF_VOL, 2.5) && ratio <= st.getDouble(EFF_RATIO, 0.4)) {
        double sc = 40 + 30 * Math.min(1, (rv - 1) / 2.0) + 30 * Math.min(1, 1 - ratio / st.getDouble(EFF_RATIO, 0.4) + 0.3);
        int d = 0;
        if (rd >= 0.5) d = delta > 0 ? -1 : 1;            // die Aggressoren sind nicht vorangekommen
        else {                                            // Delta ausgeglichen → Lage im Swing entscheidet
          double sh = Double.NEGATIVE_INFINITY, sl = Double.POSITIVE_INFINITY;
          for (int k = Math.max(0, i - sw); k <= i; k++) { sh = Math.max(sh, s.getHigh(k)); sl = Math.min(sl, s.getLow(k)); }
          double pos = sh > sl ? (c - sl) / (sh - sl) : 0.5;
          d = pos <= 0.33 ? 1 : pos >= 0.67 ? -1 : 0;
        }
        if (d > 0) bull[1] = sc; else if (d < 0) bear[1] = sc;
      }
    }
    // 3 Wick-Absorption und 4 Passive Wand (Footprint-Zeilen)
    if (rng > 0 && !fp.rows.isEmpty()) {
      double z = st.getDouble(WICK_ZONE, 0.25) * rng;
      double topBuy = 0, topSell = 0, botBuy = 0, botSell = 0;
      double wallTopV = 0, wallBotV = 0, wallTopPx = hi, wallBotPx = lo;
      double wallMin = st.getDouble(WALL_MULT, 2.5) * mRow * (live ? Math.max(frac, 0.5) : 1.0), wallBal = st.getDouble(WALL_BAL, 0.15);
      for (Map.Entry<Float, Row> e : fp.rows.entrySet()) {
        double px = e.getKey(); Row r = e.getValue(); double rvlm = r.buy + r.sell;
        boolean top = px >= hi - z, bot = px <= lo + z;
        if (top) { topBuy += r.buy; topSell += r.sell; }
        if (bot) { botBuy += r.buy; botSell += r.sell; }
        boolean balanced = rvlm > 0 && Math.abs(r.buy - r.sell) / rvlm <= wallBal;
        if (balanced && rvlm >= wallMin) {
          if (px >= hi - rng / 3 && rvlm > wallTopV) { wallTopV = rvlm; wallTopPx = px; }
          if (px <= lo + rng / 3 && rvlm > wallBotV) { wallBotV = rvlm; wallBotPx = px; }
        }
      }
      if (st.getBoolean(USE_WICK, true)) {
        double share = st.getDouble(WICK_SHARE, 0.35), dom = st.getDouble(WICK_DOM, 3.0), wl = st.getDouble(WICK_LEN, 0.5) * rng;
        double upW = hi - Math.max(o, c), dnW = Math.min(o, c) - lo;
        if (topBuy / vol >= share && topBuy / Math.max(1, topSell) >= dom && upW >= wl && c < hi - z)
          bear[2] = 40 + 30 * Math.min(1, topBuy / vol / (2 * share)) + 30 * Math.min(1, upW / rng);
        if (botSell / vol >= share && botSell / Math.max(1, botBuy) >= dom && dnW >= wl && c > lo + z)
          bull[2] = 40 + 30 * Math.min(1, botSell / vol / (2 * share)) + 30 * Math.min(1, dnW / rng);
      }
      if (st.getBoolean(USE_WALL, true)) {
        double mid = (hi + lo) / 2;
        if (wallBotV > 0 && c > mid) { bull[3] = 40 + 60 * Math.min(1, (wallBotV / Math.max(1, mRow) - 1) / 2); bullPx = wallBotPx; }
        if (wallTopV > 0 && c < mid) { bear[3] = 40 + 60 * Math.min(1, (wallTopV / Math.max(1, mRow) - 1) / 2); bearPx = wallTopPx; }
      }
      // 5 Refill / Iceberg
      if (st.getBoolean(USE_REFILL, true)) {
        double rmin = st.getDouble(REFILL_MIN, 2.0), rsh = st.getDouble(REFILL_SHARE, 0.08);
        double bestB = 0, bestA = 0, pxB = lo, pxA = hi;
        for (Map.Entry<Float, Row> e : fp.rows.entrySet()) {
          double px = e.getKey(); Row r = e.getValue();
          if (r.maxBidShown > 0 && r.bidHitVol >= rsh * vol && px <= (hi + lo) / 2 && c > px) {
            double ref = r.bidHitVol / r.maxBidShown; if (ref >= rmin && ref > bestB) { bestB = ref; pxB = px; }
          }
          if (r.maxAskShown > 0 && r.askHitVol >= rsh * vol && px >= (hi + lo) / 2 && c < px) {
            double ref = r.askHitVol / r.maxAskShown; if (ref >= rmin && ref > bestA) { bestA = ref; pxA = px; }
          }
        }
        if (bestB > 0) { bull[4] = 40 + 60 * Math.min(1, (bestB - rmin) / (2 * rmin) + 0.2); if (bull[3] == 0) bullPx = pxB; }
        if (bestA > 0) { bear[4] = 40 + 60 * Math.min(1, (bestA - rmin) / (2 * rmin) + 0.2); if (bear[3] == 0) bearPx = pxA; }
      }
    }
    if (!live && i >= sw + 1) {
      // 6 CVD-Divergenz: neues Swing-Extrem ohne CVD-Bestätigung
      if (st.getBoolean(USE_CVD, true) && i < cvdAt.size()) {
        int kLo = -1, kHi = -1;
        for (int k = i - sw; k < i; k++) {
          if (kLo < 0 || s.getLow(k) < s.getLow(kLo)) kLo = k;
          if (kHi < 0 || s.getHigh(k) > s.getHigh(kHi)) kHi = k;
        }
        double cNow = cvdAt.get(i);
        if (kLo >= 0 && lo < s.getLow(kLo) && !Double.isNaN(cvdAt.get(kLo)) && cNow > cvdAt.get(kLo) && c > lo + 0.25 * rng)
          bull[5] = 45 + 55 * Math.min(1, (cNow - cvdAt.get(kLo)) / Math.max(1, 2 * mDel));
        if (kHi >= 0 && hi > s.getHigh(kHi) && !Double.isNaN(cvdAt.get(kHi)) && cNow < cvdAt.get(kHi) && c < hi - 0.25 * rng)
          bear[5] = 45 + 55 * Math.min(1, (cvdAt.get(kHi) - cNow) / Math.max(1, 2 * mDel));
      }
      // 7 Trapped: Push-Kerze i−1 mit starkem Delta auf neues Extrem, Kerze i schließt hinter deren Open
      if (st.getBoolean(USE_TRAP, true)) {
        BarFP p = bar(s, i - 1);
        double pd = p.delta(), prd = Math.abs(pd) / Math.max(1e-9, mDel);
        if (prd >= st.getDouble(TRAP_DELTA, 2.0)) {
          boolean newHi = true, newLo = true;
          for (int k = Math.max(0, i - 1 - sw); k < i - 1; k++) { if (s.getHigh(k) >= s.getHigh(i - 1)) newHi = false; if (s.getLow(k) <= s.getLow(i - 1)) newLo = false; }
          if (pd > 0 && newHi && c < s.getOpen(i - 1)) { bear[6] = 50 + 50 * Math.min(1, (prd - 1) / 3); bearPx = Math.max(bearPx, s.getHigh(i - 1)); }
          if (pd < 0 && newLo && c > s.getOpen(i - 1)) { bull[6] = 50 + 50 * Math.min(1, (prd - 1) / 3); bullPx = Math.min(bullPx, s.getLow(i - 1)); }
        }
      }
      // 8 Erschöpfung: drei Kerzen gleicher Richtung, Volumen je Preisfortschritt wächst stark
      if (st.getBoolean(USE_EXH, true) && i >= 2) {
        int dir0 = (int) Math.signum(s.getClose(i - 2) - s.getOpen(i - 2));
        boolean same = dir0 != 0;
        double[] eff = new double[3];
        for (int k = 0; k < 3; k++) {
          int b = i - 2 + k; double body = s.getClose(b) - s.getOpen(b); BarFP f = bar(s, b);
          if ((int) Math.signum(body) != dir0 || Math.signum(f.delta()) != dir0) same = false;
          eff[k] = f.vol() / Math.max(Math.abs(body), 1e-9);
        }
        double g = st.getDouble(EXH_GROWTH, 3.0);
        if (same && eff[1] > eff[0] && eff[2] > eff[1] && eff[2] >= g * eff[0]) {
          double sc = 45 + 55 * Math.min(1, (eff[2] / eff[0] - g) / (2 * g) + 0.2);
          if (dir0 > 0) bear[7] = sc; else bull[7] = sc;
        }
      }
    }

    Hit hb = combine(bull, 1, bullPx), ha = combine(bear, -1, bearPx);
    Hit h = hb == null ? ha : ha == null ? hb : (hb.strength >= ha.strength ? hb : ha);
    if (h == null || h.strength < st.getInteger(MIN_STRENGTH, 0) || h.modes < st.getInteger(MIN_MODES, 1)) return null;
    return h;
  }

  private Hit combine(double[] sc, int dir, double px)
  {
    Hit h = new Hit(); double mx = 0; int n = 0;
    for (int k = 0; k < sc.length; k++) if (sc[k] > 0) { h.types.add(TYPE_NAMES[k]); mx = Math.max(mx, sc[k]); n++; }
    if (n == 0) return null;
    h.dir = dir; h.price = px; h.modes = n; h.strength = Math.min(100, Math.round(mx + 10 * (n - 1)));
    return h;
  }

  // ═════════════════════════════ Ausgabe ═════════════════════════════
  private void emit(DataContext ctx, DataSeries s, int i, Hit h)
  {
    var st = getSettings();
    Color col = h.dir > 0 ? st.getColor(BULL_COLOR) : st.getColor(BEAR_COLOR);
    if (col == null) col = h.dir > 0 ? new Color(38, 166, 154) : new Color(239, 83, 80);
    long t = s.getStartTime(i);
    double y = h.dir > 0 ? s.getLow(i) : s.getHigh(i);
    Enums.Size sz = h.modes >= 4 ? Enums.Size.LARGE : h.modes >= 2 ? Enums.Size.MEDIUM : Enums.Size.SMALL;
    var m = new Marker(new Coordinate(t, y), Enums.MarkerType.TRIANGLE, sz,
        h.dir > 0 ? Enums.Position.BOTTOM : Enums.Position.TOP, col, col);
    if (st.getBoolean(SHOW_TEXT, true)) {
      m.setTextValue(h.modes + "/10 " + h.typeText());
      m.setTextPosition(h.dir > 0 ? Enums.Position.BOTTOM : Enums.Position.TOP);
    }
    m.setPopupMessage("Absorption " + (h.dir > 0 ? "bullisch" : "bärisch") + " · " + h.modes + "/10 Modi · Stärke " + (int) h.strength + " · " + h.typeText()
        + " · Preis " + s.getInstrument().format(h.price));
    addFigure(m);
    s.setInt(i, Values.ABS_DIR, h.dir);
    s.setDouble(i, Values.ABS_STRENGTH, h.strength);
    ctx.signal(i, h.dir > 0 ? Signals.BULL_ABSORPTION : Signals.BEAR_ABSORPTION,
        "Absorption " + (h.dir > 0 ? "bullisch" : "bärisch") + " " + h.modes + "/10 " + h.typeText(), s.getClose(i));
    Double atr = s.atr(i, 14);
    var a = new Active();
    a.dir = h.dir; a.bar = i; a.extreme = h.dir > 0 ? Math.min(h.price, s.getLow(i)) : Math.max(h.price, s.getHigh(i));
    a.atr = atr == null ? s.getHigh(i) - s.getLow(i) : atr; a.time = t; a.text = h.typeText();
    active.add(a);
    nAbs++;
    log(s, t, "ABSORPTION", h.dir, h.price, h.strength, h.typeText(), bar(s, i), "modes=" + h.modes);
  }

  private void resolveActive(DataContext ctx, DataSeries s, int i)
  {
    var st = getSettings();
    double heldX = st.getDouble(HELD_ATR, 0.5), failX = st.getDouble(FAIL_ATR, 0.15);
    int maxBars = st.getInteger(MAX_BARS, 20);
    var it = active.iterator();
    while (it.hasNext()) {
      Active a = it.next();
      if (i <= a.bar) continue;
      boolean failed = a.dir > 0 ? s.getLow(i) <= a.extreme - failX * a.atr : s.getHigh(i) >= a.extreme + failX * a.atr;
      boolean held = a.dir > 0 ? s.getHigh(i) >= a.extreme + heldX * a.atr : s.getLow(i) <= a.extreme - heldX * a.atr;
      String res = failed ? "FAILED" : held ? "HELD" : (i - a.bar >= maxBars ? "EXPIRED" : null);
      if (res == null) continue;
      if (res.equals("HELD")) { nHeld++; ctx.signal(i, Signals.ABSORPTION_HELD, "Absorption gehalten (" + a.text + ")", s.getClose(i)); }
      else if (res.equals("FAILED")) { nFail++; ctx.signal(i, Signals.ABSORPTION_FAILED, "Absorption gebrochen (" + a.text + ")", s.getClose(i)); }
      else nExp++;
      lastOutcome = res + " (" + a.text + ")";
      log(s, s.getStartTime(i), "OUTCOME", a.dir, a.extreme, 0, a.text, null, res + ";bars=" + (i - a.bar));
      it.remove();
    }
  }

  private void drawStatus(DataSeries s, int cur, Hit live)
  {
    if (statusLabel != null) removeFigure(statusLabel);
    String state; Color bg;
    var st = getSettings();
    Active br = null;
    for (Active a : active) {
      double px = s.getClose(cur);
      if (a.dir > 0 ? px < a.extreme - st.getDouble(FAIL_ATR, 0.15) * a.atr : px > a.extreme + st.getDouble(FAIL_ATR, 0.15) * a.atr) br = a;
    }
    if (live != null) {
      state = "ABSORBING " + (live.dir > 0 ? "▲ bullisch" : "▼ bärisch") + "  " + live.modes + "/10  " + live.typeText();
      bg = live.dir > 0 ? st.getColor(BULL_COLOR) : st.getColor(BEAR_COLOR);
    }
    else if (br != null) { state = "BREAKING  " + (br.dir > 0 ? "Bid-Absorption bricht" : "Ask-Absorption bricht") + " (" + br.text + ")"; bg = Color.ORANGE.darker(); }
    else { state = "WAITING"; bg = Color.DARK_GRAY; }
    int done = nHeld + nFail + nExp;
    String stats = done > 0 ? String.format("  ·  %d Abs · held %d%% · failed %d%% · zuletzt %s", nAbs,
        Math.round(100.0 * nHeld / done), Math.round(100.0 * nFail / done), lastOutcome) : "  ·  " + nAbs + " Abs";
    statusLabel = new Label(state + stats, new Font("SansSerif", Font.BOLD, 12), Color.WHITE, bg == null ? Color.DARK_GRAY : bg);
    statusLabel.setLocation(s.getEndTime(cur), s.getHigh(cur));
    statusLabel.setPosition(Enums.Position.RIGHT);
    addFigure(statusLabel);
  }

  // ═════════════════════════════ Hilfen ═════════════════════════════
  private long getNow(DataSeries s, int i)
  {
    long latest = s.getStartTime(i);
    BarFP fp = fps.get(s.getStartTime(i));
    return fp == null ? latest : Math.max(latest, System.currentTimeMillis());
  }

  private static double median(double[] a)
  {
    double[] b = Arrays.copyOf(a, a.length); Arrays.sort(b);
    int n = b.length; if (n == 0) return 0;
    return n % 2 == 1 ? b[n / 2] : 0.5 * (b[n / 2 - 1] + b[n / 2]);
  }

  private void log(DataSeries s, long t, String kind, int dir, double px, double strength, String types, BarFP fp, String extra)
  {
    String path = getSettings().getString(LOG_FILE, "");
    if (path == null || path.isBlank()) return;
    try {
      var f = new File(path);
      var fmt = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss.SSS"); fmt.setTimeZone(TimeZone.getTimeZone("America/New_York"));
      String line = String.join(",", fmt.format(new Date(t)), String.valueOf(t), kind, dir > 0 ? "up" : "down",
          String.valueOf(px), String.valueOf((int) strength), types,
          fp == null ? "" : String.valueOf((long) fp.delta()), fp == null ? "" : String.valueOf((long) fp.vol()), extra) + System.lineSeparator();
      if (!f.exists()) Files.writeString(f.toPath(), "time_ny,epoch_ms,kind,dir,price,strength,types,delta,volume,extra" + System.lineSeparator(), StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
      Files.writeString(f.toPath(), line, StandardCharsets.UTF_8, StandardOpenOption.CREATE, StandardOpenOption.APPEND);
    }
    catch (Exception e) { /* Log ist optional */ }
  }
}
