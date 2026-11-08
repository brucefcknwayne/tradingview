package de.hanu.lagercheck.mixin;

import de.hanu.lagercheck.LagerCheck;
import net.minecraft.client.gui.Gui;
import net.minecraft.client.gui.screens.Screen;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Jeder Bildschirmwechsel läuft über Gui.setScreen: hier sehen wir, wann eine Truhe auf- und zugeht. */
@Mixin(Gui.class)
public abstract class GuiMixin {
    @Inject(method = "setScreen", at = @At("HEAD"))
    private void lagercheck$onSetScreen(Screen next, CallbackInfo ci) {
        try {
            LagerCheck.onScreenChange(((Gui) (Object) this).screen(), next);
        } catch (Throwable t) {
            LagerCheck.log("Fehler beim Bildschirmwechsel", t);
        }
    }
}
