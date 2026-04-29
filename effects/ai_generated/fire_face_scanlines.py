"""S3: Fire Face Scanlines — fire overlay on face region, horizontal metallic scan lines, starfield bg."""

import os, sys, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, make_starfield

EFFECT_META = {
    "name":        "Fire Face Scanlines",
    "description": "Procedural fire on face with horizontal metallic scanlines on starfield background",
    "key_audio":   ["energy", "bass", "kick"],
    "tags":        ["fire", "scanlines", "body", "maximalist"],
    "order":       99,
}


def _make_fire_noise(H, W, t, speed):
    """Generate scrolling fire-like noise pattern."""
    # Work at quarter res for speed
    sh, sw = max(1, H // 4), max(1, W // 4)
    noise = np.random.randint(0, 256, (sh, sw), dtype=np.uint8)
    noise = cv2.GaussianBlur(noise, (7, 7), 0)

    # Scroll upward
    offset = int(t * speed) % sh
    noise = np.roll(noise, -offset, axis=0)

    # Resize to full
    noise = cv2.resize(noise, (W, H), interpolation=cv2.INTER_LINEAR)
    return noise


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "t" not in state:
        state["t"] = 0
    state["t"] += 1
    t = state["t"]

    energy = getattr(af, "energy", 0.0)
    bass = getattr(af, "bass", 0.0)

    # --- Body mask ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    # --- Starfield background ---
    bg = make_starfield(H, W, state, energy)

    # --- Generate fire texture ---
    fire_speed = 2 + energy * 8
    noise = _make_fire_noise(H, W, t, fire_speed).astype(np.float32) / 255.0

    # Color the noise: orange/red gradient
    fire = np.zeros((H, W, 3), dtype=np.float32)
    fire[:, :, 2] = np.clip(noise * 2.0, 0, 1)          # Red: bright
    fire[:, :, 1] = np.clip(noise * 1.2 - 0.2, 0, 1)    # Green: mid-orange
    fire[:, :, 0] = np.clip(noise * 0.4 - 0.3, 0, 1)    # Blue: minimal

    fire = (fire * 255).astype(np.uint8)

    # Apply fire only to upper body (face region ~ top 40% of mask)
    face_mask = mask.copy()
    cutoff = int(H * 0.55)
    face_mask[cutoff:, :] = 0
    face_mask3 = face_mask[:, :, None]

    # Blend fire with body in face region
    body_with_fire = cv2.addWeighted(frame, 0.4, fire, 0.6, 0)
    body_region = frame.astype(np.float32) * (1.0 - face_mask3) + \
                  body_with_fire.astype(np.float32) * face_mask3
    body_region = body_region.astype(np.uint8)

    # --- Metallic scanlines ---
    scanline_spacing = max(3, int(4 + bass * 8))
    scanline_layer = np.zeros((H, W, 3), dtype=np.uint8)

    for y in range(0, H, scanline_spacing):
        # Jitter
        jitter = int(np.sin(y * 0.1 + t * 0.2) * 2)
        y_draw = min(H - 1, max(0, y + jitter))
        brightness = int(120 + 80 * np.sin(y * 0.05 + t * 0.15))
        brightness = min(255, max(40, brightness))
        # Metallic silver color with slight variation
        color = (brightness, brightness, int(brightness * 0.9))
        cv2.line(scanline_layer, (0, y_draw), (W, y_draw), color, 1)

    # Apply scanlines to body region
    body_final = cv2.addWeighted(body_region, 0.85, scanline_layer, 0.15, 0)

    # --- Composite body on bg ---
    out = bg.astype(np.float32) * (1.0 - mask3) + body_final.astype(np.float32) * mask3
    return np.clip(out, 0, 255).astype(np.uint8)
