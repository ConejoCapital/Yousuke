"""S2: Thermal Posterize — blue/orange/white 3-color body with chromatic fringe."""

import os, sys, math, random
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import apply_chromatic_aberration

EFFECT_META = {
    "name":        "Thermal Posterize",
    "description": "Luma quantization to 3 thermal colors with chromatic aberration and floating text",
    "key_audio":   ["bass", "onset_energy", "energy"],
    "tags":        ["posterize", "thermal", "chromatic", "maximalist"],
    "order":       99,
}

# Thermal palette: shadows=blue, mids=orange, highlights=white
_BLUE   = np.array([200, 80, 20], dtype=np.uint8)    # BGR
_ORANGE = np.array([40, 140, 255], dtype=np.uint8)    # BGR
_WHITE  = np.array([255, 255, 255], dtype=np.uint8)   # BGR

_TEXT_FRAGMENTS = [
    "YOUSUKE", "HEAT", "FLUX", "DATA", "NODE",
    "FREQ", "PULSE", "SYNC", "WAVE", "BURN",
    "0xFF", "SYS", "OVER", "LOAD", "PEAK",
]


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    # --- Luma-based posterization ---
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0

    # Audio-reactive thresholds
    bass = getattr(af, "bass", 0.0)
    t_low = 0.30 + bass * 0.1
    t_high = 0.65 - bass * 0.1

    out = np.zeros((H, W, 3), dtype=np.uint8)
    shadow_mask = gray < t_low
    mid_mask = (gray >= t_low) & (gray < t_high)
    high_mask = gray >= t_high

    out[shadow_mask] = _BLUE
    out[mid_mask] = _ORANGE
    out[high_mask] = _WHITE

    # --- Chromatic aberration ---
    onset = getattr(af, "onset_energy", 0.0)
    aberr = 1.5 + onset * 6
    out = apply_chromatic_aberration(out, aberr)

    # --- Floating text fragments ---
    if "text_particles" not in state:
        state["text_particles"] = []
        state["text_t"] = 0

    state["text_t"] += 1
    energy = getattr(af, "energy", 0.0)

    # Spawn new text on energy spikes
    if energy > 0.4 and random.random() < energy * 0.5:
        txt = random.choice(_TEXT_FRAGMENTS)
        x = random.randint(0, W)
        y = random.randint(0, H)
        vx = random.uniform(-1, 1)
        vy = random.uniform(-2, -0.5)
        life = random.uniform(0.6, 1.0)
        scale = random.uniform(0.4, 0.8)
        state["text_particles"].append({
            "txt": txt, "x": x, "y": y, "vx": vx, "vy": vy,
            "life": life, "scale": scale,
        })

    alive = []
    for tp in state["text_particles"]:
        tp["x"] += tp["vx"]
        tp["y"] += tp["vy"]
        tp["life"] -= 0.015

        if tp["life"] <= 0 or tp["y"] < -30:
            continue
        alive.append(tp)

        alpha = min(1.0, tp["life"])
        color = (int(100 * alpha), int(180 * alpha), int(255 * alpha))
        cv2.putText(out, tp["txt"], (int(tp["x"]), int(tp["y"])),
                    cv2.FONT_HERSHEY_SIMPLEX, tp["scale"], color, 1, cv2.LINE_AA)

    state["text_particles"] = alive[-100:]

    return out
