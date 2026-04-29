"""S4: Echo Clone Trail — multiple body copies trailing with sparkle background."""

import os, sys
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, make_starfield

EFFECT_META = {
    "name":        "Echo Clone Trail",
    "description": "Ring buffer of body-segmented frames composited at decreasing opacity with progressive blur",
    "key_audio":   ["bass", "energy", "kick"],
    "tags":        ["echo", "trail", "body", "maximalist"],
    "order":       99,
}

_MAX_ECHOES = 5
_HALF_SCALE = 0.5


def fx_function(frame, af, state):
    H, W = frame.shape[:2]
    hH, hW = H // 2, W // 2

    # --- Body mask ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    # Body-only frame (black bg) — store at half-res to save memory + blur cost
    body_frame = (frame.astype(np.float32) * mask3).astype(np.uint8)
    body_half = cv2.resize(body_frame, (hW, hH), interpolation=cv2.INTER_AREA)

    # --- Ring buffer of previous body frames (half-res) ---
    if "echo_buffer" not in state:
        state["echo_buffer"] = []

    state["echo_buffer"].append(body_half)
    if len(state["echo_buffer"]) > _MAX_ECHOES:
        state["echo_buffer"] = state["echo_buffer"][-_MAX_ECHOES:]

    # --- Starfield background ---
    bg = make_starfield(H, W, state, af.energy)

    # --- Number of echoes driven by audio ---
    bass = getattr(af, "bass", 0.0)
    n_echoes = min(len(state["echo_buffer"]), int(2 + bass * 3))
    blur_inc = int(3 + af.energy * 8)

    # --- Composite echoes at half-res then upscale ---
    out_half = cv2.resize(bg, (hW, hH), interpolation=cv2.INTER_AREA).astype(np.float32)
    buf = state["echo_buffer"]
    n = len(buf)

    for i in range(max(0, n - n_echoes), n):
        age = n - 1 - i  # 0 = most recent
        opacity = max(0.1, 1.0 - age * 0.22)
        blur_size = 1 + age * blur_inc
        if blur_size % 2 == 0:
            blur_size += 1
        blur_size = min(blur_size, 31)

        echo = buf[i].astype(np.float32)

        # Progressive blur at half-res (much cheaper)
        if blur_size > 1:
            echo = cv2.GaussianBlur(echo, (blur_size, blur_size), 0)

        # Directional offset (trail spreads slightly)
        offset_x = age * 3
        offset_y = age * 2
        if offset_x > 0 or offset_y > 0:
            M = np.float32([[1, 0, offset_x], [0, 1, offset_y]])
            echo = cv2.warpAffine(echo.astype(np.uint8), M, (hW, hH)).astype(np.float32)

        # Additive composite
        echo_mask = (np.max(echo, axis=2) > 5).astype(np.float32)[:, :, None]
        out_half = out_half * (1.0 - echo_mask * opacity) + echo * opacity

    # Upscale composited echoes back to full-res
    out = cv2.resize(np.clip(out_half, 0, 255).astype(np.uint8),
                     (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)

    # --- Composite current body on top at full-res ---
    out = out * (1.0 - mask3) + frame.astype(np.float32) * mask3

    return np.clip(out, 0, 255).astype(np.uint8)
