package com.cracks;

import com.motivewave.platform.sdk.profile.VolumeProfile;
import com.motivewave.platform.sdk.profile.VolumeRow;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeSet;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Schreibt die LVN-Preise ("Cracks") in eine Textdatei, die 1:1 in den
 * TradingView-Indikator "Cracks · MotiveWave LVN" eingefügt werden kann.
 *
 * Datei: ~/Documents/MotiveWave_Cracks/<SYMBOL>.txt  (ein Preis pro Zeile, Dezimalpunkt)
 *
 * Gedacht zum Einbau in den OFFIZIELLEN Quellcode der Volume-Profile-Study
 * (von MotiveWave, siehe Anleitung): genau an der Stelle, an der die Study
 * ihre LVN-Linien zeichnet, wird export(...) mit denselben Preisen aufgerufen.
 * So werden exakt die gezeichneten Werte exportiert – keine eigene Rechnung.
 */
public final class LvnFileExport {

    private static final Path DIR = Paths.get(System.getProperty("user.home"), "Documents", "MotiveWave_Cracks");
    private static final Map<String, String> LAST = new ConcurrentHashMap<>();

    private LvnFileExport() {}

    /** Variante A: Preise direkt übergeben (die Preise, mit denen die Study die LVN-Linie zeichnet). */
    public static void export(String symbol, Collection<? extends Number> prices) {
        TreeSet<String> sorted = new TreeSet<>((a, b) -> Double.compare(Double.parseDouble(a), Double.parseDouble(b)));
        for (Number p : prices) {
            if (p == null || Double.isNaN(p.doubleValue())) continue;
            sorted.add(String.format(Locale.US, "%.2f", p.doubleValue()));
        }
        write(symbol, String.join("\n", sorted) + "\n");
    }

    /**
     * Variante B: aus einem SDK-VolumeProfile. Achtung: getLVNs() liefert
     * Zeilen-INDIZES in getRows(), keine Preise – hier wird umgerechnet.
     */
    public static void export(String symbol, VolumeProfile vp, int sensitivity) {
        if (vp == null) return;
        int[] idx = vp.getLVNs(sensitivity);
        List<VolumeRow> rows = vp.getRows();
        List<Double> prices = new ArrayList<>();
        if (idx != null && rows != null) {
            for (int i : idx) {
                if (i >= 0 && i < rows.size()) prices.add((double) rows.get(i).getRowPrice());
            }
        }
        export(symbol, prices);
    }

    /** Schreibt nur, wenn sich der Inhalt geändert hat (atomar über Temp-Datei). */
    private static void write(String symbol, String content) {
        String key = symbol == null || symbol.isEmpty() ? "UNKNOWN" : symbol.replaceAll("[^A-Za-z0-9_.-]", "_");
        if (content.equals(LAST.get(key))) return;
        try {
            Files.createDirectories(DIR);
            Path tmp = DIR.resolve(key + ".tmp");
            Files.write(tmp, content.getBytes(StandardCharsets.UTF_8));
            Files.move(tmp, DIR.resolve(key + ".txt"), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            LAST.put(key, content);
        } catch (IOException e) {
            System.err.println("LvnFileExport: " + e.getMessage());
        }
    }
}
