"""S1: Confetti Particle Storm — dense multicolor confetti around pink-tinted body on starfield."""

import os, sys, math, random
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, make_starfield

EFFECT_META = {
    "name":        "Confetti Particle Storm",
    "description": "Dense rectangular confetti particles spawned from body contour on kicks with gravity/wind",
    "key_audio":   ["kick", "bass", "mids", "energy"],
    "tags":        ["particles", "confetti", "body", "maximalist"],
    "order":       99,
}

_CONFETTI_COLORS = [
    (0, 0, 255), (0, 128, 255), (0, 255, 255), (0, 255, 128),
    (0, 255, 0), (255, 0, 128), (255, 0, 255), (255, 128, 0),
    (128, 0, 255), (255, 255, 0), (255, 255, 255), (200, 50, 200),
]


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    # --- Body mask & pink tint ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    # Pink tint on body
    pink_tint = np.full_like(frame, (180, 100, 255), dtype=np.uint8)
    body = cv2.addWeighted(frame, 0.5, pink_tint, 0.5, 0)
    body = (body.astype(np.float32) * mask3 + 0).astype(np.uint8)

    # --- Starfield background ---
    bg = make_starfield(H, W, state, af.energy)

    # --- Composite body on bg ---
    out = bg.astype(np.float32) * (1.0 - mask3) + body.astype(np.float32) * mask3
    out = out.astype(np.uint8)

    # --- Confetti particles ---
    if "particles" not in state:
        state["particles"] = []

    # Spawn from body contour on kicks
    kick = getattr(af, "kick", 0.0)
    if kick > 0.3:
        mask_u8 = (mask * 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        spawn_count = int(50 + kick * 200)
        for _ in range(spawn_count):
            if contours:
                c = random.choice(contours)
                if len(c) > 0:
                    pt = c[random.randint(0, len(c) - 1)][0]
                    x, y = float(pt[0]), float(pt[1])
                else:
                    x, y = random.uniform(0, W), random.uniform(0, H)
            else:
                x, y = random.uniform(0, W), random.uniform(0, H)

            vx = random.uniform(-4, 4) + af.mids * 4 * random.choice([-1, 1])
            vy = random.uniform(-6, -1)
            color = random.choice(_CONFETTI_COLORS)
            w = random.randint(3, 8)
            h = random.randint(5, 12)
            angle = random.uniform(0, 360)
            spin = random.uniform(-8, 8)
            life = random.uniform(0.8, 1.0)
            state["particles"].append({
                "x": x, "y": y, "vx": vx, "vy": vy,
                "color": color, "w": w, "h": h,
                "angle": angle, "spin": spin, "life": life,
            })

    # Update and draw particles
    wind = af.mids * 4
    alive = []
    for p in state["particles"]:
        p["x"] += p["vx"] + wind * 0.3
        p["y"] += p["vy"]
        p["vy"] += 0.15  # gravity
        p["angle"] += p["spin"]
        p["life"] -= 0.012

        if p["life"] <= 0 or p["y"] > H + 20 or p["x"] < -20 or p["x"] > W + 20:
            continue
        alive.append(p)

        # Draw rotated rectangle
        cx, cy = int(p["x"]), int(p["y"])
        rect = ((cx, cy), (p["w"], p["h"]), p["angle"])
        box = cv2.boxPoints(rect).astype(np.int32)
        alpha = min(1.0, p["life"])
        color = tuple(int(c * alpha) for c in p["color"])
        cv2.fillPoly(out, [box], color)

    state["particles"] = alive[-3000:]

    return out
