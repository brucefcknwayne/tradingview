package de.hanu.lagercheck;

import java.nio.file.Path;
import java.util.List;
import java.util.Map;

/** Befehle: /lc ... oder /lagercheck ... (werden nicht an den Server geschickt). */
public final class Commands {
    private static final int PER_PAGE = 12;
    private Commands() { }

    /** @return true, wenn der Befehl uns gehört (dann wird er nicht gesendet). */
    public static boolean handle(String command) {
        String c = command.trim();
        String[] p = c.split("\\s+");
        if (p.length == 0) return false;
        String root = p[0].toLowerCase();
        if (!root.equals("lc") && !root.equals("lagercheck")) return false;
        String sub = p.length > 1 ? p[1].toLowerCase() : "hilfe";
        switch (sub) {
            case "liste", "list", "l" -> liste(p.length > 2 ? parse(p[2], 1) : 1);
            case "truhe", "t" -> truhe();
            case "status", "s" -> status();
            case "export", "e" -> export();
            case "entfernen", "del" -> entfernen();
            case "reset" -> reset(p.length > 2 && p[2].equalsIgnoreCase("ja"));
            default -> hilfe();
        }
        return true;
    }

    private static void hilfe() {
        LagerCheck.chat("§6===== Lagercheck =====");
        LagerCheck.chat("§fÖffne Truhen ganz normal – der Inhalt wird beim Schließen gemerkt.");
        LagerCheck.chat("§e/lc liste [Seite] §7– alle geloggten Items");
        LagerCheck.chat("§e/lc truhe §7– was in der Truhe ist, auf die du schaust");
        LagerCheck.chat("§e/lc status §7– Anzahl Truhen / Item-Sorten");
        LagerCheck.chat("§e/lc export §7– Dateien schreiben (lagercheck/export.txt)");
        LagerCheck.chat("§e/lc entfernen §7– angeschaute Truhe aus dem Log löschen");
        LagerCheck.chat("§e/lc reset ja §7– alles löschen");
    }

    private static void liste(int page) {
        List<Store.Sum> l = Store.sums();
        if (l.isEmpty()) { LagerCheck.chat("§e[Lagercheck] §fNoch nichts geloggt. Öffne ein paar Truhen."); return; }
        int pages = (l.size() + PER_PAGE - 1) / PER_PAGE;
        page = Math.max(1, Math.min(page, pages));
        LagerCheck.chat("§6===== Geloggte Items (" + l.size() + " Sorten, " + Store.chestCount() + " Truhen) – Seite " + page + "/" + pages + " =====");
        for (int i = (page - 1) * PER_PAGE; i < Math.min(l.size(), page * PER_PAGE); i++) {
            Store.Sum s = l.get(i);
            LagerCheck.chat("§7" + (i + 1) + ". §f" + Store.name(s.id) + " §7– §e" + Store.fmt(s.count) + "§7 Stück in " + s.chests + " Truhe(n)");
        }
        if (page < pages) LagerCheck.chat("§7Weiter: §e/lc liste " + (page + 1) + "§7   |   Alles als Datei: §elagercheck/items.txt");
    }

    private static void truhe() {
        String key = LagerCheck.lookedAtChestKey();
        if (key == null) { LagerCheck.chat("§c[Lagercheck] Schau direkt auf eine Truhe."); return; }
        Store.Chest c = Store.chests.get(key);
        if (c == null) { LagerCheck.chat("§e[Lagercheck] §fDiese Truhe ist noch nicht geloggt. Öffne sie einmal."); return; }
        LagerCheck.chat("§6===== Truhe (geloggt " + c.time + ") =====");
        if (c.items.isEmpty()) LagerCheck.chat("§7(leer)");
        for (Map.Entry<String, Integer> e : c.items.entrySet())
            LagerCheck.chat("§f" + Store.name(e.getKey()) + " §7– §e" + Store.fmt(e.getValue()) + "§7 Stück");
    }

    private static void status() {
        List<Store.Sum> l = Store.sums();
        long total = 0; for (Store.Sum s : l) total += s.count;
        int lager = (l.size() + 383) / 384;
        LagerCheck.chat("§6[Lagercheck] §fServer: §e" + LagerCheck.server());
        LagerCheck.chat("§f" + Store.chestCount() + " Truhen geloggt, §e" + l.size() + "§f Item-Sorten, §e" + Store.fmt(total) + "§f Stück");
        LagerCheck.chat("§fDafür reicht " + (lager <= 1 ? "§e1 Lager Quadrat XL" : "§e" + lager + " Lager Quadrat XL") + " §7(384 Sorten pro Lager)");
    }

    private static void export() {
        try {
            Path p = Store.export();
            LagerCheck.chat("§a[Lagercheck] §fGespeichert: §e" + p.toAbsolutePath());
            LagerCheck.chat("§7Diese Datei (export.txt) kannst du Claude schicken.");
        } catch (Exception e) {
            LagerCheck.log("Export fehlgeschlagen", e);
            LagerCheck.chat("§c[Lagercheck] Export fehlgeschlagen: " + e.getMessage());
        }
    }

    private static void entfernen() {
        String key = LagerCheck.lookedAtChestKey();
        if (key == null) { LagerCheck.chat("§c[Lagercheck] Schau direkt auf eine Truhe."); return; }
        LagerCheck.chat(Store.remove(key) ? "§a[Lagercheck] §fTruhe aus dem Log entfernt." : "§e[Lagercheck] §fDiese Truhe war nicht geloggt.");
    }

    private static void reset(boolean confirmed) {
        if (!confirmed) { LagerCheck.chat("§e[Lagercheck] §fWirklich ALLES löschen? Dann: §c/lc reset ja"); return; }
        Store.reset();
        LagerCheck.chat("§a[Lagercheck] §fAlles gelöscht. Öffne deine Truhen neu.");
    }

    private static int parse(String s, int def) {
        try { return Integer.parseInt(s); } catch (NumberFormatException e) { return def; }
    }
}
