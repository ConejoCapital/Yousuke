"""V12: Feedback Spiral Zoom — recursive frame accumulator with scale-down + rotation."""

import os, sys, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask

EFFECT_META = {
    "name":        "Feedback Spiral Zoom",
    "description": "Frame accumulator with scale-down and rotation per frame, body composited on top",
    "key_audio":   ["bass", "mids", "energy"],
    "tags":        ["feedback", "spiral", "zoom", "recursive", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    bass = getattr(af, "bass", 0.0)
    mids = getattr(af, "mids", 0.0)
    energy = getattr(af, "energy", 0.0)

    if "accum" not in state:
        state["accum"] = None
        state["total_angle"] = 0.0

    scale = 0.96 + bass * 0.03
    rotation_deg = 2 + mids * 5
    state["total_angle"] += rotation_deg

    cx, cy = W / 2, H / 2

    # --- Body mask ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    prev = state["accum"]
    if prev is not None and prev.shape == frame.shape:
        # Scale down and rotate the accumulated frame
        M = cv2.getRotationMatrix2D((cx, cy), rotation_deg, scale)
        warped = cv2.warpAffine(prev, M, (W, H),
                                borderMode=cv2.BORDER_REPLICATE)

        # Progressive magenta/cyan tinting
        hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
        # Shift hue toward magenta (150 in OpenCV HSV = ~300 deg = magenta)
        hue_shift = int(2 + energy * 3)
        hsv[:, :, 0] = ((hsv[:, :, 0].astype(np.int32) + hue_shift) % 180).astype(np.uint8)
        # Slight desaturation to prevent blowout
        hsv[:, :, 1] = np.clip(hsv[:, :, 1].astype(np.int32) - 3, 0, 255).astype(np.uint8)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2].astype(np.int32) - 2, 0, 255).astype(np.uint8)
        warped = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # Composite current body on top of feedback
        out = warped.astype(np.float32) * (1.0 - mask3) + \
              frame.astype(np.float32) * mask3
        # Also blend body into feedback regions slightly
        out = np.clip(out, 0, 255).astype(np.uint8)
    else:
        out = frame.copy()

    state["accum"] = out.copy()

    # Bloom
    bloom = cv2.GaussianBlur(out, (21, 21), 0)
    out = cv2.addWeighted(out, 0.85, bloom, 0.15 + energy * 0.1, 0)

    return out
