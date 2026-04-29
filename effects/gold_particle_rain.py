"""Effect 6: Gold Particle Rain — dense downward golden cascade."""
import random

import cv2
import numpy as np

EFFECT_META = {
    "name":        "Gold Particle Rain",
    "description": "Dense downward particle field in gold/amber palette; density scales with highs",
    "key_audio":   ["highs", "energy"],
    "tags":        ["particles", "gold", "rain", "cascade"],
    "order":       6,
}


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 6: Gold Particle Rain — dense downward golden cascade."""
    H, W = frame.shape[:2]

    if "rain" not in state:
        state["rain"] = []

    rain = state["rain"]

    # Spawn based on highs energy
    spawn = int(af.highs * 150 + af.energy * 50)
    for _ in range(spawn):
        t = af.energy
        color = (
            int(0   + t * 200),
            int(165 + t * 90),
            int(255),
        )
        rain.append({
            "x":          random.uniform(0, W),
            "y":          random.uniform(-20, 0),
            "vy":         random.uniform(3, 10),
            "brightness": random.uniform(0.5, 1.0),
            "size":       random.randint(1, 3),
            "color":      color,
        })

    canvas = (frame.astype(np.float32) * 0.4).astype(np.uint8)
    alive  = []
    for p in rain:
        b  = p["brightness"]
        c  = tuple(int(ch * b) for ch in p["color"])
        xi, yi = int(p["x"]), int(p["y"])
        if 0 <= yi < H:
            cv2.circle(canvas, (xi, yi), p["size"], c, -1)
        p["y"] += p["vy"]
        if p["y"] < H + 10:
            alive.append(p)

    state["rain"] = alive[-3000:]
    return canvas
