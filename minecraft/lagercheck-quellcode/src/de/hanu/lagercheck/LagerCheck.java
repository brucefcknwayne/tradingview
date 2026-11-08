package de.hanu.lagercheck;

import net.fabricmc.api.ClientModInitializer;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.gui.screens.inventory.AbstractContainerScreen;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.world.inventory.ChestMenu;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.ChestBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.ChestType;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;

import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.TreeMap;

public class LagerCheck implements ClientModInitializer {
    public static Path dir;
    /** Schlüssel der Truhe, die gerade offen ist (null = keine Truhe / unbekannt). */
    private static String openKey;

    @Override
    public void onInitializeClient() {
        dir = Minecraft.getInstance().gameDirectory.toPath().resolve("lagercheck");
        try { Files.createDirectories(dir); } catch (Exception e) { /* egal */ }
        Store.load();
        log("Lagercheck gestartet, " + Store.chests.size() + " Truhen geladen");
    }

    /** Wird bei jedem Bildschirmwechsel aufgerufen (alter Bildschirm, neuer Bildschirm). */
    public static void onScreenChange(Screen old, Screen next) {
        if (old == next) return;
        // Truhe wird geschlossen -> Inhalt jetzt lesen (dann sind alle Items vom Server da)
        if (openKey != null && old instanceof AbstractContainerScreen<?> acs && acs.getMenu() instanceof ChestMenu menu) {
            Map<String, Integer> items = new TreeMap<>();
            int n = menu.getRowCount() * 9;
            for (int i = 0; i < n && i < menu.slots.size(); i++) {
                ItemStack st = menu.slots.get(i).getItem();
                if (st.isEmpty()) continue;
                String id = BuiltInRegistries.ITEM.getKey(st.getItem()).toString();
                items.merge(id, st.getCount(), Integer::sum);
            }
            Store.put(openKey, items);
            int total = items.values().stream().mapToInt(Integer::intValue).sum();
            overlay("§a[Lagercheck] §fTruhe gespeichert: §e" + items.size() + "§f Sorte(n), §e" + Store.fmt(total) + "§f Stück");
            openKey = null;
        }
        // Truhe wird geöffnet -> merken, welche Truhe das ist (auf die man schaut)
        if (next instanceof AbstractContainerScreen<?> acs2 && acs2.getMenu() instanceof ChestMenu) {
            openKey = lookedAtChestKey();
        } else if (!(next instanceof AbstractContainerScreen<?>)) {
            openKey = null;
        }
    }

    /** Schlüssel der Truhe im Fadenkreuz: server|dimension|x|y|z (Doppeltruhe = immer die kleinere Hälfte). */
    public static String lookedAtChestKey() {
        Minecraft mc = Minecraft.getInstance();
        if (mc.level == null || !(mc.hitResult instanceof BlockHitResult hit) || hit.getType() != HitResult.Type.BLOCK) return null;
        BlockPos pos = hit.getBlockPos();
        BlockState state = mc.level.getBlockState(pos);
        if (!(state.getBlock() instanceof ChestBlock)) return null;
        if (state.hasProperty(ChestBlock.TYPE) && state.getValue(ChestBlock.TYPE) != ChestType.SINGLE) {
            BlockPos other = pos.relative(ChestBlock.getConnectedDirection(state));
            if (compare(other, pos) < 0) pos = other;
        }
        return server() + "|" + mc.level.dimension().identifier() + "|" + pos.getX() + "|" + pos.getY() + "|" + pos.getZ();
    }

    private static int compare(BlockPos a, BlockPos b) {
        if (a.getX() != b.getX()) return Integer.compare(a.getX(), b.getX());
        if (a.getY() != b.getY()) return Integer.compare(a.getY(), b.getY());
        return Integer.compare(a.getZ(), b.getZ());
    }

    public static String server() {
        var sd = Minecraft.getInstance().getCurrentServer();
        return sd == null || sd.ip == null ? "einzelspieler" : sd.ip.toLowerCase().trim();
    }

    public static void chat(String text) {
        Minecraft mc = Minecraft.getInstance();
        mc.gui.hud.getChat().addClientSystemMessage(Component.literal(text));
    }

    public static void overlay(String text) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.player != null) mc.player.sendOverlayMessage(Component.literal(text));
    }

    public static void log(String msg) { log(msg, null); }

    public static void log(String msg, Throwable t) {
        try {
            StringBuilder sb = new StringBuilder();
            sb.append(LocalDateTime.now().format(DateTimeFormatter.ofPattern("dd.MM. HH:mm:ss"))).append("  ").append(msg).append('\n');
            if (t != null) { StringWriter sw = new StringWriter(); t.printStackTrace(new PrintWriter(sw)); sb.append(sw); }
            if (dir != null) Files.writeString(dir.resolve("log.txt"), sb, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE, StandardOpenOption.APPEND);
        } catch (Exception ignored) { }
    }
}
