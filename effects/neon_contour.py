"""Effect 1: Neon Contour — edge detect + colormap + bloom."""
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Neon Contour",
    "description": "Canny edges colorized via HSV colormap with bloom glow; thickness pulses on bass",
    "key_audio":   ["bass", "energy"],
    "tags":        ["edges", "neon", "colormap", "bloom"],
    "order":       1,
}


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 1: Neon Contour — edge detect + colormap + bloom."""
    H, W = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold based on bass
    low_thresh  = int(30 + af.bass * 40)
    high_thresh = int(100 + af.bass * 80)
    edges = cv2.Canny(gray, low_thresh, high_thresh)

    # Dilate edges based on bass energy
    thickness = max(1, int(1 + af.bass * 7))
    kernel = np.ones((thickness, thickness), np.uint8)
    edges  = cv2.dilate(edges, kernel)

    # Colorize with HSV-shifted colormap
    colored = cv2.applyColorMap(edges, cv2.COLORMAP_HSV)

    # Hue rotation based on energy
    hue_shift = int(af.energy * 120)
    hsv = cv2.cvtColor(colored, cv2.COLOR_BGR2HSV).astype(np.int32)
    hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
    colored = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    # Bloom
    bloom_strength = 0.8 + af.bass * 1.5
    blur   = cv2.GaussianBlur(colored, (21, 21), 0)
    result = cv2.addWeighted(colored, 1.0, blur, bloom_strength, 0)

    # Blend over dark frame (keep slight camera ghost)
    dark = (frame.astype(np.float32) * 0.15).astype(np.uint8)
    return cv2.add(dark, result)
