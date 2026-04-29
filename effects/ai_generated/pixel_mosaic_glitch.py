"""S7: Pixel Mosaic Glitch — asymmetric block displacement with color channel shifting."""

import os, sys, random
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Pixel Mosaic Glitch",
    "description": "Random blocks on one body half displaced with color channel swap, drifting back over frames",
    "key_audio":   ["kick", "bass", "energy"],
    "tags":        ["glitch", "pixel", "mosaic", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "blocks" not in state:
        state["blocks"] = []

    kick = getattr(af, "kick", 0.0)
    bass = getattr(af, "bass", 0.0)

    # --- Trigger new blocks on kicks ---
    if kick > 0.4:
        n_blocks = int(kick * 40)
        # Choose which half to glitch (alternates)
        side = state.get("last_side", 0)
        side = 1 - side
        state["last_side"] = side

        for _ in range(n_blocks):
            bw = random.randint(16, 64)
            bh = random.randint(16, 64)
            if side == 0:
                bx = random.randint(0, max(0, W // 2 - bw))
            else:
                bx = random.randint(W // 2, max(W // 2, W - bw))
            by = random.randint(0, max(0, H - bh))

            disp_x = random.randint(-50, 50) + int(bass * 50 * random.choice([-1, 1]))
            disp_y = random.randint(-20, 20)
            # Color channel swap type: 0=BGR->RGB, 1=BGR->GBR, 2=invert
            swap = random.randint(0, 2)
            life = 10  # frames to drift back

            state["blocks"].append({
                "x": bx, "y": by, "w": bw, "h": bh,
                "dx": disp_x, "dy": disp_y,
                "swap": swap, "life": life, "max_life": life,
            })

    # --- Update and render blocks ---
    out = frame.copy()
    alive = []

    for b in state["blocks"]:
        b["life"] -= 1
        if b["life"] <= 0:
            continue
        alive.append(b)

        # Drift back toward origin
        progress = b["life"] / b["max_life"]  # 1 at start, 0 at end
        cur_dx = int(b["dx"] * progress)
        cur_dy = int(b["dy"] * progress)

        # Source region
        sx = max(0, min(W - b["w"], b["x"]))
        sy = max(0, min(H - b["h"], b["y"]))
        block = frame[sy:sy + b["h"], sx:sx + b["w"]].copy()

        # Color channel manipulation
        if b["swap"] == 0:
            block = block[:, :, ::-1]  # BGR -> RGB
        elif b["swap"] == 1:
            block = block[:, :, [1, 0, 2]]  # BGR -> GBR
        elif b["swap"] == 2:
            block = 255 - block  # Invert

        # Target position
        tx = max(0, min(W - b["w"], sx + cur_dx))
        ty = max(0, min(H - b["h"], sy + cur_dy))

        bh_actual = min(b["h"], H - ty, block.shape[0])
        bw_actual = min(b["w"], W - tx, block.shape[1])
        if bh_actual > 0 and bw_actual > 0:
            out[ty:ty + bh_actual, tx:tx + bw_actual] = block[:bh_actual, :bw_actual]

    state["blocks"] = alive[-200:]

    return out
