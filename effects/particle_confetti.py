"""Effect 2: Particle Confetti — body edge particles."""
import math
import random

import cv2
import numpy as np

EFFECT_META = {
    "name":        "Particle Confetti",
    "description": "Neon particles spawn from silhouette edges on kick; gravity + decay",
    "key_audio":   ["kick", "bass"],
    "tags":        ["particles", "neon", "confetti", "kick"],
    "order":       2,
}

# Neon color palette (BGR)
_NEON_COLORS = [(255, 50, 50), (50, 255, 200), (200, 50, 255), (50, 200, 255), (255, 200, 50)]


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 2: Particle Confetti — body edge particles."""
    H, W = frame.shape[:2]

    if "particles" not in state:
        state["particles"] = []
    particles = state["particles"]

    # Get edge pixels for spawn source
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_ys, edge_xs = np.where(edges > 0)

    # Spawn particles on kick/beat
    spawn_count = 0
    if af.kick > 0.4 and len(edge_xs) > 0:
        spawn_count = int(20 + af.kick * 80)

    for _ in range(spawn_count):
        idx   = random.randint(0, len(edge_xs) - 1)
        color = random.choice(_NEON_COLORS)
        speed = 1 + af.bass * 6
        angle = random.uniform(0, 2 * math.pi)
        particles.append({
            "x":     float(edge_xs[idx]),
            "y":     float(edge_ys[idx]),
            "vx":    math.cos(angle) * speed * random.uniform(0.5, 1.5),
            "vy":    math.sin(angle) * speed * random.uniform(0.5, 1.5) - 2,
            "color": color,
            "life":  1.0,
            "decay": random.uniform(0.02, 0.05),
            "size":  random.randint(1, 4),
        })

    # Update and draw
    canvas = (frame.astype(np.float32) * 0.3).astype(np.uint8)
    alive  = []
    for p in particles:
        p["x"]  += p["vx"]
        p["y"]  += p["vy"]
        p["vy"] += 0.15   # gravity
        p["vx"] *= 0.98
        p["life"] -= p["decay"]

        if p["life"] > 0 and 0 <= int(p["x"]) < W and 0 <= int(p["y"]) < H:
            alpha = p["life"]
            c = tuple(int(ch * alpha) for ch in p["color"])
            cv2.circle(canvas, (int(p["x"]), int(p["y"])), p["size"], c, -1)
            alive.append(p)

    state["particles"] = alive[-2000:]  # cap particle count
    return canvas
