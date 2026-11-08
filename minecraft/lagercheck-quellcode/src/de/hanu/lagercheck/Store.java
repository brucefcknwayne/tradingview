package de.hanu.lagercheck;

import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.Identifier;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

/** Speichert pro Truhe, welche Items drin sind. Datei: lagercheck/truhen.txt */
public final class Store {
    public static final class Chest {
        public final String key;
        public final Map<String, Integer> items;
        public final String time;
        Chest(String key, Map<String, Integer> items, String time) { this.key = key; this.items = items; this.time = time; }
    }
    /** Item-Sorte mit Summe über alle Truhen. */
    public static final class Sum {
        public final String id; public long count; public int chests;
        Sum(String id) { this.id = id; }
    }

    public static final Map<String, Chest> chests = new LinkedHashMap<>();
    private static final Map<String, String> nameCache = new HashMap<>();
    private static final DateTimeFormatter TF = DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm");

    private Store() { }

    public static void put(String key, Map<String, Integer> items) {
        chests.put(key, new Chest(key, items, LocalDateTime.now().format(TF)));
        save();
    }

    public static boolean remove(String key) {
        boolean r = chests.remove(key) != null;
        if (r) save();
        return r;
    }

    public static void reset() { chests.clear(); save(); }

    /** Alle Item-Sorten (nur aktueller Server), sortiert nach deutschem Namen. */
    public static List<Sum> sums() {
        String prefix = LagerCheck.server() + "|";
        Map<String, Sum> m = new HashMap<>();
        for (Chest c : chests.values()) {
            if (!c.key.startsWith(prefix)) continue;
            for (var e : c.items.entrySet()) {
                Sum s = m.computeIfAbsent(e.getKey(), Sum::new);
                s.count += e.getValue(); s.chests++;
            }
        }
        List<Sum> l = new ArrayList<>(m.values());
        l.sort(Comparator.comparing((Sum s) -> name(s.id).toLowerCase(Locale.GERMAN)).thenComparing(s -> s.id));
        return l;
    }

    public static int chestCount() {
        String prefix = LagerCheck.server() + "|";
        int n = 0;
        for (String k : chests.keySet()) if (k.startsWith(prefix)) n++;
        return n;
    }

    /** Deutscher Anzeigename eines Items (aus dem Spiel), z. B. "Rote Wolle". */
    public static String name(String id) {
        return nameCache.computeIfAbsent(id, i -> {
            try {
                Identifier rl = Identifier.tryParse(i);
                if (rl == null) return i;
                Item item = BuiltInRegistries.ITEM.getValue(rl);
                return new ItemStack(item).getHoverName().getString();
            } catch (Throwable t) { return i; }
        });
    }

    public static String fmt(long n) { return String.format(Locale.GERMANY, "%,d", n); }

    // ---------------- Datei ----------------
    private static Path file() { return LagerCheck.dir.resolve("truhen.txt"); }

    public static void load() {
        chests.clear();
        try {
            Path f = file();
            if (!Files.exists(f)) return;
            for (String line : Files.readAllLines(f, StandardCharsets.UTF_8)) {
                if (line.isBlank() || line.startsWith("#")) continue;
                String[] p = line.split("\t", -1);
                if (p.length < 3) continue;
                Map<String, Integer> items = new TreeMap<>();
                if (!p[2].isEmpty()) for (String kv : p[2].split(",")) {
                    int eq = kv.lastIndexOf('=');
                    if (eq > 0) items.put(kv.substring(0, eq), Integer.parseInt(kv.substring(eq + 1)));
                }
                chests.put(p[0], new Chest(p[0], items, p[1]));
            }
        } catch (Exception e) { LagerCheck.log("Laden fehlgeschlagen", e); }
    }

    public static void save() {
        try {
            StringBuilder sb = new StringBuilder("# Lagercheck-Speicher: Truhe<TAB>Zeit<TAB>item=anzahl,...  (Datei löschen = alles zurücksetzen)\n");
            for (Chest c : chests.values()) {
                sb.append(c.key).append('\t').append(c.time).append('\t');
                boolean first = true;
                for (var e : c.items.entrySet()) {
                    if (!first) sb.append(',');
                    sb.append(e.getKey()).append('=').append(e.getValue()); first = false;
                }
                sb.append('\n');
            }
            Files.writeString(file(), sb, StandardCharsets.UTF_8);
            export();
        } catch (Exception e) { LagerCheck.log("Speichern fehlgeschlagen", e); }
    }

    /** Schreibt items.txt (lesbar) und export.txt (für den Lager-Bau). Gibt den Pfad zurück. */
    public static Path export() throws Exception {
        List<Sum> l = sums();
        String now = LocalDateTime.now().format(TF);
        StringBuilder a = new StringBuilder();
        a.append("Lagercheck – Stand ").append(now).append("  (Server: ").append(LagerCheck.server()).append(")\n");
        a.append(chestCount()).append(" Truhen, ").append(l.size()).append(" Item-Sorten\n\n");
        for (Sum s : l) a.append(String.format(Locale.GERMANY, "%-40s %10s Stück  in %d Truhe(n)%n", name(s.id), fmt(s.count), s.chests));
        Files.writeString(LagerCheck.dir.resolve("items.txt"), a, StandardCharsets.UTF_8);

        StringBuilder b = new StringBuilder();
        b.append("# Lagercheck-Export ").append(now).append(" | Server: ").append(LagerCheck.server()).append('\n');
        b.append("# Truhen: ").append(chestCount()).append(" | Item-Sorten: ").append(l.size()).append('\n');
        b.append("# id|Name|Stück|Truhen\n");
        for (Sum s : l) b.append(s.id).append('|').append(name(s.id)).append('|').append(s.count).append('|').append(s.chests).append('\n');
        b.append("# --- Truhen ---\n");
        String prefix = LagerCheck.server() + "|";
        for (Chest c : chests.values()) {
            if (!c.key.startsWith(prefix)) continue;
            b.append("#T ").append(c.key.substring(prefix.length())).append(" | ");
            boolean first = true;
            for (var e : c.items.entrySet()) { if (!first) b.append(", "); b.append(e.getKey()).append('=').append(e.getValue()); first = false; }
            b.append('\n');
        }
        Path p = LagerCheck.dir.resolve("export.txt");
        Files.writeString(p, b, StandardCharsets.UTF_8);
        return p;
    }
}
