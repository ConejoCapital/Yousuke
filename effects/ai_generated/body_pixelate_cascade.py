"""V6: Body Pixelate Cascade — pixelation varies by vertical position, cascading on beats."""

import os, sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask

EFFECT_META = {
    "name":        "Body Pixelate Cascade",
    "description": "Pixelation level varies vertically on body, boundary cascades downward on beats",
    "key_audio":   ["bass", "energy", "beat"],
    "tags":        ["pixelate", "body", "cascade", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "cascade_pos" not in state:
        state["cascade_pos"] = 0.0
        state["direction"] = 1  # 1=down, -1=up

    bass = getattr(af, "bass", 0.0)
    energy = getattr(af, "energy", 0.0)
    beat = getattr(af, "beat", False)

    # On beat, reverse direction and reset position
    if beat:
        state["direction"] *= -1
        if state["direction"] > 0:
            state["cascade_pos"] = 0.0
        else:
            state["cascade_pos"] = 1.0

    # Advance cascade position
    speed = (3 + energy * 8) / H
    state["cascade_pos"] += speed * state["direction"]
    state["cascade_pos"] = max(0.0, min(1.0, state["cascade_pos"]))

    cascade_y = int(state["cascade_pos"] * H)
    max_pixel_size = max(4, int(8 + bass * 32))

    # --- Body mask ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    out = frame.copy()

    # Apply variable pixelation to body region
    # Above cascade line: heavily pixelated, below: sharp (or reverse)
    if state["direction"] > 0:
        # Top pixelated, bottom sharp
        for y in range(0, H, max(1, max_pixel_size)):
            # Pixel size decreases as we approach cascade_y
            if y < cascade_y:
                ratio = 1.0 - (y / max(cascade_y, 1))
                pix = max(2, int(max_pixel_size * ratio))
            else:
                pix = 1

            if pix <= 1:
                continue

            y_end = min(H, y + pix)
            for x in range(0, W, pix):
                x_end = min(W, x + pix)
                # Check if this block overlaps body
                block_mask = mask[y:y_end, x:x_end]
                if np.mean(block_mask) < 0.3:
                    continue
                # Average the block
                block = frame[y:y_end, x:x_end]
                avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
                out[y:y_end, x:x_end] = avg_color
    else:
        # Bottom pixelated, top sharp
        for y in range(0, H, max(1, max_pixel_size)):
            if y > cascade_y:
                ratio = (y - cascade_y) / max(H - cascade_y, 1)
                pix = max(2, int(max_pixel_size * ratio))
            else:
                pix = 1

            if pix <= 1:
                continue

            y_end = min(H, y + pix)
            for x in range(0, W, pix):
                x_end = min(W, x + pix)
                block_mask = mask[y:y_end, x:x_end]
                if np.mean(block_mask) < 0.3:
                    continue
                block = frame[y:y_end, x:x_end]
                avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
                out[y:y_end, x:x_end] = avg_color

    # Darken non-body slightly
    out_f = out.astype(np.float32)
    out_f = out_f * mask3 + out_f * (1.0 - mask3) * 0.4
    return np.clip(out_f, 0, 255).astype(np.uint8)
