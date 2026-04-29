"""V14: Chromatic Body Double — body split into R/G/B copies at different offsets, additive composite."""

import os, sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, apply_chromatic_aberration

EFFECT_META = {
    "name":        "Chromatic Body Double",
    "description": "Body segmented into 3 R/G/B copies at different spatial offsets, composited additively",
    "key_audio":   ["kick", "bass", "energy"],
    "tags":        ["chromatic", "body", "rgb", "double", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    kick = getattr(af, "kick", 0.0)
    bass = getattr(af, "bass", 0.0)
    energy = getattr(af, "energy", 0.0)

    # Smoothed offsets
    if "r_off" not in state:
        state["r_off"] = 0.0
        state["b_off"] = 0.0

    target_r = 5 + kick * 30
    target_b = -(5 + kick * 30)
    state["r_off"] += (target_r - state["r_off"]) * 0.25
    state["b_off"] += (target_b - state["b_off"]) * 0.25

    r_off = int(state["r_off"])
    b_off = int(state["b_off"])

    # --- Body mask ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    # Extract body
    body = (frame.astype(np.float32) * mask3).astype(np.uint8)

    # Split into single-channel copies
    B_ch, G_ch, R_ch = cv2.split(body)

    # Create R-only, G-only, B-only images
    r_img = np.zeros((H, W, 3), dtype=np.uint8)
    g_img = np.zeros((H, W, 3), dtype=np.uint8)
    b_img = np.zeros((H, W, 3), dtype=np.uint8)

    r_img[:, :, 2] = R_ch  # Red channel
    g_img[:, :, 1] = G_ch  # Green channel
    b_img[:, :, 0] = B_ch  # Blue channel

    # Offset R and B images
    if r_off != 0:
        M_r = np.float32([[1, 0, r_off], [0, 1, 0]])
        r_img = cv2.warpAffine(r_img, M_r, (W, H))
    if b_off != 0:
        M_b = np.float32([[1, 0, b_off], [0, 1, 0]])
        b_img = cv2.warpAffine(b_img, M_b, (W, H))

    # Additive composite on black background
    out = np.zeros((H, W, 3), dtype=np.float32)
    out += r_img.astype(np.float32)
    out += g_img.astype(np.float32)
    out += b_img.astype(np.float32)
    out = np.clip(out, 0, 255).astype(np.uint8)

    # Bloom for glow
    if energy > 0.2:
        bloom = cv2.GaussianBlur(out, (21, 21), 0)
        out = cv2.addWeighted(out, 0.8, bloom, 0.2 + energy * 0.15, 0)

    return out
