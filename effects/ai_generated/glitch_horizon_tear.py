"""V7: Glitch Horizon Tear — random horizontal bands shifted with color inversion on kicks."""

import random
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Glitch Horizon Tear",
    "description": "Random horizontal bands shifted left/right with color inversion, spikes on kicks",
    "key_audio":   ["kick", "bass", "energy"],
    "tags":        ["glitch", "horizontal", "tear", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "tears" not in state:
        state["tears"] = []

    kick = getattr(af, "kick", 0.0)
    bass = getattr(af, "bass", 0.0)

    # Trigger new tears on kicks
    if kick > 0.3:
        n_tears = int(3 + kick * 30)
        for _ in range(n_tears):
            y = random.randint(0, H - 1)
            h = random.randint(5, 20)
            shift = random.randint(-100, 100)
            shift = int(shift + bass * 50 * (1 if shift > 0 else -1))
            invert = random.random() < 0.3
            life = 5  # frames to heal
            state["tears"].append({
                "y": y, "h": h, "shift": shift,
                "invert": invert, "life": life, "max_life": life,
            })

    # Apply tears
    out = frame.copy()
    alive = []

    for tear in state["tears"]:
        tear["life"] -= 1
        if tear["life"] <= 0:
            continue
        alive.append(tear)

        progress = tear["life"] / tear["max_life"]
        cur_shift = int(tear["shift"] * progress)

        y_start = max(0, tear["y"])
        y_end = min(H, tear["y"] + tear["h"])
        if y_start >= y_end:
            continue

        band = out[y_start:y_end, :, :].copy()

        # Horizontal shift via np.roll
        if cur_shift != 0:
            band = np.roll(band, cur_shift, axis=1)
            # Black fill on the gap
            if cur_shift > 0:
                band[:, :cur_shift, :] = 0
            else:
                band[:, cur_shift:, :] = 0

        # Color inversion for some bands
        if tear["invert"]:
            band = 255 - band

        out[y_start:y_end, :, :] = band

    state["tears"] = alive[-200:]

    # Subtle scanline overlay for extra glitch feel
    if kick > 0.5:
        scanlines = np.zeros((H, W), dtype=np.uint8)
        scanlines[::2, :] = 30
        out = cv2.subtract(out, cv2.merge([scanlines, scanlines, scanlines]))

    return out
