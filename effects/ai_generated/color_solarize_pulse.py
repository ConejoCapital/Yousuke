"""V10: Color Solarize Pulse — dynamic solarization with oscillating per-channel thresholds."""

import math
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Color Solarize Pulse",
    "description": "Dynamic solarization with oscillating threshold per R/G/B channel at different phase offsets",
    "key_audio":   ["energy", "bass", "mids"],
    "tags":        ["solarize", "color", "psychedelic", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "phase" not in state:
        state["phase"] = 0.0

    energy = getattr(af, "energy", 0.0)
    bass = getattr(af, "bass", 0.0)
    mids = getattr(af, "mids", 0.0)

    state["phase"] += 0.08 + energy * 0.2
    phase = state["phase"]

    # Per-channel oscillating thresholds
    thresh_b = 128 + math.sin(phase) * 60
    thresh_g = 128 + math.sin(phase + 2.09) * 60       # +120 degrees
    thresh_r = 128 + math.sin(phase + 4.19) * 60       # +240 degrees

    # Audio modulates amplitude
    thresh_b += bass * 40 * math.sin(phase * 1.5)
    thresh_g += mids * 30 * math.cos(phase * 1.3)
    thresh_r += energy * 35 * math.sin(phase * 0.9)

    B, G, R = cv2.split(frame)
    B_f = B.astype(np.float32)
    G_f = G.astype(np.float32)
    R_f = R.astype(np.float32)

    # Solarize: invert pixels above threshold
    B_out = np.where(B_f > thresh_b, 255.0 - B_f, B_f)
    G_out = np.where(G_f > thresh_g, 255.0 - G_f, G_f)
    R_out = np.where(R_f > thresh_r, 255.0 - R_f, R_f)

    out = cv2.merge([
        np.clip(B_out, 0, 255).astype(np.uint8),
        np.clip(G_out, 0, 255).astype(np.uint8),
        np.clip(R_out, 0, 255).astype(np.uint8),
    ])

    # Boost saturation for psychedelic feel
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    sat_boost = int(30 + energy * 50)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.int32) + sat_boost, 0, 255).astype(np.uint8)
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    # Subtle bloom
    bloom = cv2.GaussianBlur(out, (15, 15), 0)
    out = cv2.addWeighted(out, 0.85, bloom, 0.15 + energy * 0.1, 0)

    return out
