"""V8: Radial Zoom Tunnel — infinite zoom from body center with layered depth and hue tinting."""

import os, sys, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, accumulate_frame

EFFECT_META = {
    "name":        "Radial Zoom Tunnel",
    "description": "Polar coordinate warp creating infinite zoom from body center with progressive hue tinting",
    "key_audio":   ["beat", "mids", "energy", "bass"],
    "tags":        ["zoom", "tunnel", "radial", "body", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]
    cx, cy = W / 2, H / 2

    beat = getattr(af, "beat", False)
    mids = getattr(af, "mids", 0.0)
    energy = getattr(af, "energy", 0.0)
    bass = getattr(af, "bass", 0.0)

    if "angle" not in state:
        state["angle"] = 0.0
        state["prev_layer"] = None

    # Rotation accumulates
    state["angle"] += mids * 5
    angle = state["angle"]

    # Zoom factor — closer to 1.0 = slower zoom
    zoom = 0.96 + bass * 0.03
    if beat:
        zoom = min(1.0, zoom + 0.04)

    # --- Get body centroid ---
    mask = get_body_mask(frame, state)
    mask_u8 = (mask * 255).astype(np.uint8)
    moments = cv2.moments(mask_u8)
    if moments["m00"] > 0:
        cx = moments["m10"] / moments["m00"]
        cy = moments["m01"] / moments["m00"]

    # --- Scale + rotate previous layer ---
    prev = state.get("prev_layer")
    if prev is not None and prev.shape == frame.shape:
        # Build affine: scale down toward center + rotate
        M = cv2.getRotationMatrix2D((cx, cy), angle, zoom)
        scaled_prev = cv2.warpAffine(prev, M, (W, H),
                                     borderMode=cv2.BORDER_REPLICATE)

        # Hue tint the previous layer progressively
        hsv = cv2.cvtColor(scaled_prev, cv2.COLOR_BGR2HSV)
        # Shift toward magenta/cyan
        hue_shift = int(3 + energy * 5)
        hsv[:, :, 0] = ((hsv[:, :, 0].astype(np.int32) + hue_shift) % 180).astype(np.uint8)
        # Slight desaturation
        hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.int32) - 5, 0, 255).astype(np.uint8)
        scaled_prev = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # Composite: current body on top of zoomed previous
        mask3 = mask[:, :, None]
        out = scaled_prev.astype(np.float32) * (1.0 - mask3) + \
              frame.astype(np.float32) * mask3
        out = np.clip(out, 0, 255).astype(np.uint8)
    else:
        out = frame.copy()

    state["prev_layer"] = out.copy()

    # Bloom for depth illusion
    bloom = cv2.GaussianBlur(out, (21, 21), 0)
    out = cv2.addWeighted(out, 0.85, bloom, 0.15 + energy * 0.1, 0)

    return out
