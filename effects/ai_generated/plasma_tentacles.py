"""V4: Plasma Tentacles — Bezier curve tendrils growing from body contour, neon colored."""

import os, sys, math, random
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask

EFFECT_META = {
    "name":        "Plasma Tentacles",
    "description": "Bezier curve tendrils from body contour, animated with sinusoidal noise, neon colored",
    "key_audio":   ["bass", "energy", "kick"],
    "tags":        ["tentacles", "body", "neon", "organic", "maximalist"],
    "order":       99,
}

_NEON_COLORS = [
    (255, 0, 128), (0, 255, 128), (128, 0, 255),
    (0, 255, 255), (255, 128, 0), (255, 0, 255),
]


def _bezier_point(p0, p1, p2, p3, t):
    """Cubic Bezier interpolation."""
    u = 1 - t
    return (u**3 * p0 + 3 * u**2 * t * p1 +
            3 * u * t**2 * p2 + t**3 * p3)


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "t" not in state:
        state["t"] = 0
        state["tentacles"] = []
    state["t"] += 1
    t = state["t"]

    bass = getattr(af, "bass", 0.0)
    energy = getattr(af, "energy", 0.0)
    kick = getattr(af, "kick", 0.0)

    # --- Body mask and silhouette ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]

    # Dark silhouette body
    body_dark = (frame.astype(np.float32) * 0.15 * mask3).astype(np.uint8)

    # Find contour points for tentacle spawning
    mask_u8 = (mask * 255).astype(np.uint8)
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    contour_pts = []
    for c in contours:
        if len(c) > 10:
            # Sample every Nth point
            step = max(1, len(c) // 40)
            for i in range(0, len(c), step):
                contour_pts.append(tuple(c[i][0]))

    # --- Spawn tentacles on kicks ---
    if kick > 0.3 and contour_pts:
        spawn_count = int(10 + energy * 30)
        for _ in range(min(spawn_count, len(contour_pts))):
            origin = random.choice(contour_pts)
            length = 50 + bass * 200
            angle = random.uniform(0, 2 * math.pi)
            color = random.choice(_NEON_COLORS)
            phase = random.uniform(0, 2 * math.pi)
            life = random.uniform(0.8, 1.0)
            state["tentacles"].append({
                "ox": origin[0], "oy": origin[1],
                "length": length, "angle": angle,
                "color": color, "phase": phase, "life": life,
            })

    # --- Background: very dark ---
    out = np.zeros((H, W, 3), dtype=np.uint8)

    # --- Draw tentacles ---
    alive = []
    for tent in state["tentacles"]:
        tent["life"] -= 0.015
        if tent["life"] <= 0:
            continue
        alive.append(tent)

        alpha = min(1.0, tent["life"])
        ox, oy = tent["ox"], tent["oy"]
        length = tent["length"] * alpha
        angle = tent["angle"]
        phase = tent["phase"]

        # Animated Bezier control points with sinusoidal wobble
        wobble = math.sin(t * 0.1 + phase) * 40 * energy
        p0 = np.array([ox, oy], dtype=np.float64)
        p1 = np.array([
            ox + math.cos(angle) * length * 0.33 + wobble,
            oy + math.sin(angle) * length * 0.33 + math.cos(t * 0.08 + phase) * 30,
        ])
        p2 = np.array([
            ox + math.cos(angle) * length * 0.66 - wobble * 0.5,
            oy + math.sin(angle) * length * 0.66 + math.sin(t * 0.12 + phase) * 50,
        ])
        p3 = np.array([
            ox + math.cos(angle) * length + wobble * 0.3,
            oy + math.sin(angle) * length,
        ])

        # Draw curve as polyline
        n_seg = 20
        pts = []
        for i in range(n_seg + 1):
            tt = i / n_seg
            px = _bezier_point(p0[0], p1[0], p2[0], p3[0], tt)
            py = _bezier_point(p0[1], p1[1], p2[1], p3[1], tt)
            pts.append((int(px), int(py)))

        color = tuple(int(c * alpha) for c in tent["color"])
        thickness = max(1, int(2 + bass * 3))
        for i in range(len(pts) - 1):
            cv2.line(out, pts[i], pts[i + 1], color, thickness, cv2.LINE_AA)

    state["tentacles"] = alive[-300:]

    # Bloom on tentacles
    if len(alive) > 0:
        bloom = cv2.GaussianBlur(out, (15, 15), 0)
        out = cv2.add(out, bloom)

    # Composite dark body on top
    out = out.astype(np.float32) * (1.0 - mask3) + \
          (out.astype(np.float32) * 0.3 + body_dark.astype(np.float32)) * mask3
    return np.clip(out, 0, 255).astype(np.uint8)
