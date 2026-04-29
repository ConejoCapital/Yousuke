"""Effect 4: Volumetric Rings — concentric halos from center."""
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Volumetric Rings",
    "description": "Concentric elliptical halos expand outward from center; new ring spawned per beat",
    "key_audio":   ["beat", "mids", "bass", "energy", "highs"],
    "tags":        ["rings", "halos", "beat", "volumetric"],
    "order":       4,
}


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 4: Volumetric Rings — concentric halos from center."""
    H, W = frame.shape[:2]
    cx, cy = W // 2, H // 2

    if "rings" not in state:
        state["rings"]      = []
        state["beat_count"] = 0
    rings = state["rings"]

    # Spawn ring on beat
    if af.beat:
        state["beat_count"] += 1
        r_color = (
            int(50  + af.mids   * 200),
            int(100 + af.highs  * 155),
            int(200 + af.energy * 55),
        )
        rings.append({
            "r":         5.0,
            "opacity":   1.0,
            "speed":     2.0 + af.mids * 8.0,
            "color":     r_color,
            "thickness": max(1, int(3 + af.bass * 4)),
        })

    # Draw: dark frame + rings
    canvas = (frame.astype(np.float32) * 0.2).astype(np.uint8)
    alive  = []
    for ring in rings:
        alpha = ring["opacity"]
        c     = tuple(int(ch * alpha) for ch in ring["color"])
        axes  = (int(ring["r"]), int(ring["r"] * 0.6))
        if axes[0] > 0 and axes[1] > 0:
            cv2.ellipse(canvas, (cx, cy), axes, 0, 0, 360, c, ring["thickness"])
        ring["r"]       += ring["speed"]
        ring["opacity"] -= 0.012
        if ring["opacity"] > 0:
            alive.append(ring)

    state["rings"] = alive[-50:]  # max 50 active rings
    return canvas
