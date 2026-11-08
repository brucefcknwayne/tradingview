package de.hanu.lagercheck.mixin;

import de.hanu.lagercheck.Commands;
import net.minecraft.client.multiplayer.ClientPacketListener;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Fängt /lc und /lagercheck ab, bevor sie an den Server gehen. */
@Mixin(ClientPacketListener.class)
public abstract class ClientPacketListenerMixin {
    @Inject(method = "sendCommand", at = @At("HEAD"), cancellable = true)
    private void lagercheck$onCommand(String command, CallbackInfo ci) {
        try {
            if (Commands.handle(command)) ci.cancel();
        } catch (Throwable t) {
            ci.cancel();
            de.hanu.lagercheck.LagerCheck.log("Fehler im Befehl /" + command, t);
            de.hanu.lagercheck.LagerCheck.chat("§c[Lagercheck] Fehler: " + t);
        }
    }
}
