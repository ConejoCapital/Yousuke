"""
¥ØUSUK€ Visual Extender — Shared Utilities for Hyper-Maximalist Effects

Underscore prefix ensures the plugin loader skips this file.

Usage from any effect:
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from _utils import get_body_mask, make_starfield, apply_displacement
"""

import cv2
import numpy as np
import math

# ---------------------------------------------------------------------------
# Optional: MediaPipe selfie segmentation (graceful fallback)
# ---------------------------------------------------------------------------
_mp_selfie = None
_mp_seg_model = None

def _init_selfie_seg():
    global _mp_selfie, _mp_seg_model
    if _mp_selfie is not None:
        return True
    try:
        import mediapipe as mp
        _mp_selfie = mp.solutions.selfie_segmentation
        _mp_seg_model = _mp_selfie.SelfieSegmentation(model_selection=1)
        return True
    except Exception:
        return False


def get_body_mask(frame, state, threshold=0.5):
    """Return a float32 mask (0-1) of the body region.

    Uses MediaPipe selfie segmentation at half resolution for speed.
    Falls back to a brightness threshold if MediaPipe is unavailable.
    Caches the segmentation model in state for reuse.
    """
    H, W = frame.shape[:2]

    # Try MediaPipe
    if _init_selfie_seg():
        # Process at half res for speed
        small = cv2.resize(frame, (W // 2, H // 2))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        results = _mp_seg_model.process(rgb)
        mask_small = results.segmentation_mask  # float32 H/2 x W/2
        mask = cv2.resize(mask_small, (W, H), interpolation=cv2.INTER_LINEAR)
        mask = (mask > threshold).astype(np.float32)
        return mask

    # Fallback: brightness threshold
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    mask = (gray > 0.15).astype(np.float32)
    # Clean up with morphological ops
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask_u8 = (mask * 255).astype(np.uint8)
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_CLOSE, kernel)
    mask_u8 = cv2.morphologyEx(mask_u8, cv2.MORPH_OPEN, kernel)
    return mask_u8.astype(np.float32) / 255.0


def make_starfield(H, W, state, energy=0.5, key="starfield"):
    """Generate a persistent twinkling star background.

    Stars are stored in state[key] and twinkle based on energy.
    Returns a BGR uint8 image.
    """
    if key not in state:
        rng = np.random.default_rng(42)
        n_stars = max(200, int(H * W * 0.0008))
        stars = []
        for _ in range(n_stars):
            x = rng.integers(0, W)
            y = rng.integers(0, H)
            brightness = rng.uniform(0.3, 1.0)
            phase = rng.uniform(0, 2 * math.pi)
            size = rng.choice([1, 1, 1, 2])
            stars.append((x, y, brightness, phase, size))
        state[key] = {"stars": stars, "t": 0}

    sd = state[key]
    sd["t"] += 1
    t = sd["t"]

    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    for x, y, base_bright, phase, size in sd["stars"]:
        twinkle = 0.5 + 0.5 * math.sin(t * 0.1 + phase + energy * 3.0)
        val = int(base_bright * twinkle * 255)
        val = min(255, max(0, val))
        color = (val, val, val)
        if size == 1:
            if 0 <= y < H and 0 <= x < W:
                canvas[y, x] = color
        else:
            cv2.circle(canvas, (x, y), size, color, -1)

    return canvas


def apply_displacement(frame, dx, dy):
    """Apply displacement map to frame using cv2.remap.

    dx, dy: float32 arrays of same shape as frame[:2], representing
            pixel offsets (not absolute coordinates).
    """
    H, W = frame.shape[:2]
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    map_x = xx + dx.astype(np.float32)
    map_y = yy + dy.astype(np.float32)
    return cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_REPLICATE)


def apply_chromatic_aberration(frame, strength):
    """Apply radial chromatic aberration.

    R channel shifts outward, B shifts inward. Strength in pixels at edges.
    """
    if strength < 0.3:
        return frame
    H, W = frame.shape[:2]
    cx, cy = W * 0.5, H * 0.5
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = xx - cx
    dy = yy - cy
    dist = np.sqrt(dx * dx + dy * dy)
    max_dist = math.sqrt(cx * cx + cy * cy)
    r_norm = dist / max(max_dist, 1e-3)
    safe = np.maximum(dist, 1e-3)
    ux = dx / safe
    uy = dy / safe
    shift_mag = (r_norm * r_norm * strength).astype(np.float32)

    map_R_x = (xx + ux * shift_mag).astype(np.float32)
    map_R_y = (yy + uy * shift_mag).astype(np.float32)
    map_B_x = (xx - ux * shift_mag).astype(np.float32)
    map_B_y = (yy - uy * shift_mag).astype(np.float32)

    B, G, R = cv2.split(frame)
    R = cv2.remap(R, map_R_x, map_R_y, cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_REPLICATE)
    B = cv2.remap(B, map_B_x, map_B_y, cv2.INTER_LINEAR,
                  borderMode=cv2.BORDER_REPLICATE)
    return cv2.merge([B, G, R])


def accumulate_frame(current, state, decay=0.85, key="accum"):
    """Blend current frame with accumulated trail.

    Returns blended frame (same dtype as current).
    decay: 0 = no trail, 1 = infinite trail
    """
    prev = state.get(key)
    if prev is None or prev.shape != current.shape:
        state[key] = current.copy()
        return current.copy()

    blended = cv2.addWeighted(current, 1.0 - decay * 0.5,
                              prev, decay * 0.5, 0)
    state[key] = blended.copy()
    return blended


def draw_neon_line(canvas, pt1, pt2, color, glow=8):
    """Draw a line with additive neon glow effect.

    canvas: BGR uint8 image (modified in place)
    color: BGR tuple
    glow: radius of bloom effect
    """
    # Core line
    cv2.line(canvas, pt1, pt2, color, 2, cv2.LINE_AA)
    # Glow passes
    if glow > 0:
        overlay = np.zeros_like(canvas)
        cv2.line(overlay, pt1, pt2, color, max(1, glow), cv2.LINE_AA)
        blurred = cv2.GaussianBlur(overlay, (0, 0), glow)
        cv2.add(canvas, blurred, canvas)
