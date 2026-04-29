"""V3: Mirror Kaleidoscope — polar coordinate multi-fold reflection centered on body."""

import math
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Mirror Kaleidoscope",
    "description": "Polar coordinate slicing with multi-fold (4/6/8) reflection and hue rotation per fold",
    "key_audio":   ["bass", "energy", "mids"],
    "tags":        ["kaleidoscope", "mirror", "polar", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]
    cx, cy = W / 2, H / 2

    bass = getattr(af, "bass", 0.0)
    energy = getattr(af, "energy", 0.0)

    # Number of folds driven by bass
    n_folds = max(2, int(4 + bass * 4))
    if n_folds % 2 != 0:
        n_folds += 1

    # Rotation angle
    if "angle" not in state:
        state["angle"] = 0.0
    state["angle"] += energy * 2.0
    angle_offset = state["angle"]

    # --- Build polar coordinate lookup ---
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx
    dy = yy - cy

    # Polar coordinates
    r = np.sqrt(dx * dx + dy * dy)
    theta = np.arctan2(dy, dx) + math.radians(angle_offset)

    # Fold: map theta into one slice, then mirror
    slice_angle = 2 * math.pi / n_folds
    theta_mod = np.mod(theta, slice_angle)
    # Mirror every other fold
    mirror_mask = (np.mod(np.floor(theta / slice_angle), 2) > 0.5)
    theta_mod[mirror_mask] = slice_angle - theta_mod[mirror_mask]

    # Back to cartesian (using original angle for source sampling)
    src_x = (cx + r * np.cos(theta_mod)).astype(np.float32)
    src_y = (cy + r * np.sin(theta_mod)).astype(np.float32)

    # Clamp
    src_x = np.clip(src_x, 0, W - 1)
    src_y = np.clip(src_y, 0, H - 1)

    out = cv2.remap(frame, src_x, src_y, cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REPLICATE)

    # --- Hue rotation per fold (subtle) ---
    hsv = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    hue_map = np.mod(np.floor(theta / slice_angle), n_folds).astype(np.int32)
    hue_shift = (hue_map * (180 // n_folds)).astype(np.uint8)
    hsv[:, :, 0] = ((hsv[:, :, 0].astype(np.int32) + hue_shift) % 180).astype(np.uint8)
    out = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    # --- Boost saturation ---
    hsv2 = cv2.cvtColor(out, cv2.COLOR_BGR2HSV)
    hsv2[:, :, 1] = np.clip(hsv2[:, :, 1].astype(np.int32) + 40, 0, 255).astype(np.uint8)
    out = cv2.cvtColor(hsv2, cv2.COLOR_HSV2BGR)

    # --- Center bloom ---
    if energy > 0.3:
        bloom = cv2.GaussianBlur(out, (31, 31), 0)
        out = cv2.addWeighted(out, 0.8, bloom, 0.2 + energy * 0.15, 0)

    return out
