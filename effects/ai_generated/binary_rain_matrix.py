"""V13: Binary Rain Matrix — falling hex character columns with body shown green-tinted."""

import os, sys, random
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask

EFFECT_META = {
    "name":        "Binary Rain Matrix",
    "description": "Falling hex character columns (Matrix style) with green-tinted body, burst from contour on kicks",
    "key_audio":   ["highs", "energy", "kick"],
    "tags":        ["matrix", "rain", "text", "body", "maximalist"],
    "order":       99,
}

_HEX_CHARS = list("0123456789ABCDEF@#$%&*!?><{}[]")
_FONT = cv2.FONT_HERSHEY_SIMPLEX
_CHAR_H = 14
_CHAR_W = 10


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "columns" not in state:
        state["columns"] = []
        state["t"] = 0
    state["t"] += 1

    highs = getattr(af, "highs", 0.0)
    energy = getattr(af, "energy", 0.0)
    kick = getattr(af, "kick", 0.0)

    # --- Body mask and green tint ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    # Green-tinted body
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    green_body = np.zeros_like(frame)
    green_body[:, :, 1] = gray  # Green channel only
    green_body = (green_body.astype(np.float32) * mask3 * 0.5).astype(np.uint8)

    # --- Background: very dark green ---
    bg = np.zeros((H, W, 3), dtype=np.uint8)
    bg[:, :, 1] = 5  # barely visible green

    # Composite
    out = bg.astype(np.float32) + green_body.astype(np.float32)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # --- Spawn new columns ---
    # Regular density
    n_cols = W // _CHAR_W
    density = int(20 + highs * 60)
    spawn_chance = density / max(n_cols, 1)

    for col_x in range(0, W, _CHAR_W):
        if random.random() < spawn_chance * 0.02:
            length = random.randint(8, 25)
            speed = 2 + energy * 8
            state["columns"].append({
                "x": col_x, "y": -length * _CHAR_H,
                "length": length, "speed": speed,
                "chars": [random.choice(_HEX_CHARS) for _ in range(length)],
            })

    # Burst columns from body contour on kick
    if kick > 0.5:
        mask_u8 = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        burst = int(kick * 30)
        for _ in range(burst):
            if contours:
                c = random.choice(contours)
                if len(c) > 0:
                    pt = c[random.randint(0, len(c) - 1)][0]
                    x = int(pt[0]) // _CHAR_W * _CHAR_W
                else:
                    x = random.randint(0, n_cols - 1) * _CHAR_W
            else:
                x = random.randint(0, n_cols - 1) * _CHAR_W

            length = random.randint(5, 15)
            state["columns"].append({
                "x": x, "y": -length * _CHAR_H,
                "length": length,
                "speed": 4 + energy * 10,
                "chars": [random.choice(_HEX_CHARS) for _ in range(length)],
            })

    # --- Update and draw columns ---
    alive = []
    for col in state["columns"]:
        col["y"] += col["speed"]

        if col["y"] > H + 20:
            continue
        alive.append(col)

        # Occasionally mutate characters
        if random.random() < 0.1:
            idx = random.randint(0, col["length"] - 1)
            col["chars"][idx] = random.choice(_HEX_CHARS)

        for i, ch in enumerate(col["chars"]):
            cy = int(col["y"] + i * _CHAR_H)
            if cy < -_CHAR_H or cy > H:
                continue

            # Leading char = bright white, trailing = dark green fade
            if i == 0:
                color = (200, 255, 200)
            else:
                fade = max(0.1, 1.0 - i / col["length"])
                color = (0, int(200 * fade), 0)

            cv2.putText(out, ch, (col["x"], cy),
                        _FONT, 0.4, color, 1, cv2.LINE_AA)

    state["columns"] = alive[-500:]

    return out
