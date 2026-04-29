"""S6: Liquify Wave Body — wavy purple/pink body distortion with edge glow on starfield."""

import os, sys, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, make_starfield, apply_displacement

EFFECT_META = {
    "name":        "Liquify Wave Body",
    "description": "Sinusoidal displacement on body region with purple/pink colormap and glowing edge outline",
    "key_audio":   ["bass", "energy", "mids"],
    "tags":        ["distortion", "liquify", "wave", "body", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "phase" not in state:
        state["phase"] = 0.0
    energy = getattr(af, "energy", 0.0)
    bass = getattr(af, "bass", 0.0)
    state["phase"] += 0.15 + energy * 0.3

    # --- Body mask ---
    mask = get_body_mask(frame, state)

    # --- Sinusoidal displacement on body ---
    amplitude = 5 + bass * 25
    freq = 0.03 + af.mids * 0.02
    phase = state["phase"]

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = (np.sin(yy * freq + phase) * amplitude * mask).astype(np.float32)
    dy = (np.cos(xx * freq + phase * 0.7) * amplitude * 0.6 * mask).astype(np.float32)

    warped = apply_displacement(frame, dx, dy)

    # --- Purple/pink colormap overlay on body ---
    mask3 = mask[:, :, None]
    # Create purple-pink tint
    purple_tint = np.zeros_like(warped, dtype=np.uint8)
    purple_tint[:, :, 0] = 200  # B
    purple_tint[:, :, 1] = 50   # G
    purple_tint[:, :, 2] = 200  # R

    body_tinted = cv2.addWeighted(warped, 0.6, purple_tint, 0.4, 0)
    body_result = (warped.astype(np.float32) * (1.0 - mask3 * 0.6) +
                   body_tinted.astype(np.float32) * mask3 * 0.6).astype(np.uint8)

    # --- Glowing edge outline ---
    mask_u8 = (mask * 255).astype(np.uint8)
    # Dilate for thicker edge
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    dilated = cv2.dilate(mask_u8, kernel)
    eroded = cv2.erode(mask_u8, kernel)
    edge = cv2.subtract(dilated, eroded)

    # Glow the edge
    edge_color = np.zeros((H, W, 3), dtype=np.uint8)
    edge_color[:, :, 0] = edge  # Blue glow
    edge_color[:, :, 2] = edge  # + Red = magenta glow

    glow_size = max(3, int(5 + energy * 15))
    if glow_size % 2 == 0:
        glow_size += 1
    edge_glow = cv2.GaussianBlur(edge_color, (glow_size, glow_size), 0)

    # --- Starfield background ---
    bg = make_starfield(H, W, state, energy)

    # --- Composite ---
    out = bg.astype(np.float32) * (1.0 - mask3) + body_result.astype(np.float32) * mask3
    out = np.clip(out, 0, 255).astype(np.uint8)

    # Add edge glow additively
    out = cv2.add(out, edge_glow)

    return out
