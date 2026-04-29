"""S5: Rainbow Echo Spiral — hue-shifted echo copies with neon background lines."""

import os, sys, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, accumulate_frame, draw_neon_line

EFFECT_META = {
    "name":        "Rainbow Echo Spiral",
    "description": "Hue-shifted echo trail copies (red/green/blue/pink) with neon horizontal bands",
    "key_audio":   ["mids", "energy", "bass"],
    "tags":        ["echo", "rainbow", "hue", "neon", "maximalist"],
    "order":       99,
}

_MAX_ECHOES = 4


def fx_function(frame, af, state):
    H, W = frame.shape[:2]
    hH, hW = H // 2, W // 2

    # --- Body mask ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]
    body_frame = (frame.astype(np.float32) * mask3).astype(np.uint8)
    body_half = cv2.resize(body_frame, (hW, hH), interpolation=cv2.INTER_AREA)

    # --- Ring buffer (half-res) ---
    if "echo_buf" not in state:
        state["echo_buf"] = []
    state["echo_buf"].append(body_half)
    if len(state["echo_buf"]) > _MAX_ECHOES:
        state["echo_buf"] = state["echo_buf"][-_MAX_ECHOES:]

    # --- Background: dark with neon horizontal bands ---
    bg = np.zeros((H, W, 3), dtype=np.uint8)
    energy = getattr(af, "energy", 0.0)

    if "bg_t" not in state:
        state["bg_t"] = 0
    state["bg_t"] += 1
    t = state["bg_t"]

    # Draw persistent horizontal neon color bands
    band_colors = [
        (255, 50, 50), (50, 255, 50), (50, 50, 255),
        (255, 50, 255), (50, 255, 255), (255, 255, 50),
    ]
    band_spacing = max(40, int(60 - energy * 20))
    for i, y_base in enumerate(range(0, H, band_spacing)):
        y = y_base + int(math.sin(t * 0.05 + i) * 5)
        y = max(0, min(H - 1, y))
        color = band_colors[i % len(band_colors)]
        brightness = max(20, int(energy * 80))
        color = tuple(min(255, c * brightness // 80) for c in color)
        cv2.line(bg, (0, y), (W, y), color, 1, cv2.LINE_AA)

    # --- Hue-shifted echoes at half-res ---
    mids = getattr(af, "mids", 0.0)
    hue_shift_per = int(30 + mids * 20)
    out_half = cv2.resize(bg, (hW, hH), interpolation=cv2.INTER_AREA).astype(np.float32)
    buf = state["echo_buf"]
    n = len(buf)

    for i in range(n - 1):
        age = n - 1 - i
        echo = buf[i].copy()

        # Hue shift via LUT (faster than per-pixel HSV roundtrip at half-res)
        hsv = cv2.cvtColor(echo, cv2.COLOR_BGR2HSV)
        hsv[:, :, 0] = (hsv[:, :, 0].astype(np.int32) + age * hue_shift_per) % 180
        echo = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # Blur with age
        blur_k = 1 + age * 4
        if blur_k % 2 == 0:
            blur_k += 1
        blur_k = min(blur_k, 21)
        if blur_k > 1:
            echo = cv2.GaussianBlur(echo, (blur_k, blur_k), 0)

        # Offset (scaled for half-res)
        offset_x = age * 4
        M = np.float32([[1, 0, offset_x], [0, 1, age * 1]])
        echo = cv2.warpAffine(echo, M, (hW, hH))

        opacity = max(0.15, 0.7 - age * 0.15)
        echo_mask = (np.max(echo, axis=2) > 8).astype(np.float32)[:, :, None]
        out_half = out_half * (1.0 - echo_mask * opacity) + echo.astype(np.float32) * opacity

    # Upscale composited echoes back to full-res
    out = cv2.resize(np.clip(out_half, 0, 255).astype(np.uint8),
                     (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32)

    # Current body on top (original colors, full-res)
    out = out * (1.0 - mask3) + frame.astype(np.float32) * mask3

    return np.clip(out, 0, 255).astype(np.uint8)
