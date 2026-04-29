"""V2: RGB Channel Explosion — split R/G/B channels radially displaced from body centroid."""

import os, sys, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, apply_chromatic_aberration

EFFECT_META = {
    "name":        "RGB Channel Explosion",
    "description": "Split B/G/R channels radially displaced from body centroid, spike on kicks",
    "key_audio":   ["kick", "bass", "energy"],
    "tags":        ["rgb", "channel", "split", "body", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    kick = getattr(af, "kick", 0.0)
    energy = getattr(af, "energy", 0.0)

    # Smoothed offset for less jarring movement
    if "r_off" not in state:
        state["r_off"] = 0.0
        state["b_off"] = 0.0

    target_r = 3 + kick * 30
    target_b = -(2 + kick * 20)
    state["r_off"] += (target_r - state["r_off"]) * 0.3
    state["b_off"] += (target_b - state["b_off"]) * 0.3

    r_off = state["r_off"]
    b_off = state["b_off"]

    # --- Body mask for centroid ---
    mask = get_body_mask(frame, state)
    mask_u8 = (mask * 255).astype(np.uint8)

    # Find body centroid
    moments = cv2.moments(mask_u8)
    if moments["m00"] > 0:
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]
    else:
        cx, cy = W / 2, H / 2

    # --- Radial displacement per channel ---
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx
    dy = yy - cy
    dist = np.sqrt(dx * dx + dy * dy)
    safe = np.maximum(dist, 1e-3)
    ux = dx / safe
    uy = dy / safe

    B, G, R = cv2.split(frame)

    # R shifts outward
    map_r_x = (xx + ux * r_off).astype(np.float32)
    map_r_y = (yy + uy * r_off).astype(np.float32)
    R = cv2.remap(R, map_r_x, map_r_y, cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_REPLICATE)

    # B shifts inward
    map_b_x = (xx + ux * b_off).astype(np.float32)
    map_b_y = (yy + uy * b_off).astype(np.float32)
    B = cv2.remap(B, map_b_x, map_b_y, cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_REPLICATE)

    # G stays centered

    out = cv2.merge([B, G, R])

    # --- Darken background slightly for contrast ---
    mask3 = mask[:, :, None]
    bg_darken = (out.astype(np.float32) * (1.0 - mask3) * 0.3 +
                 out.astype(np.float32) * mask3)
    out = np.clip(bg_darken, 0, 255).astype(np.uint8)

    # Extra bloom on body
    if energy > 0.3:
        body_only = (out.astype(np.float32) * mask3).astype(np.uint8)
        bloom = cv2.GaussianBlur(body_only, (21, 21), 0)
        out = cv2.addWeighted(out, 1.0, bloom, energy * 0.4, 0)

    return out
