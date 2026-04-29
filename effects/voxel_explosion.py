"""Effect 3: Voxel Explosion — grid of colored cubes with physics."""
import math
import random

import cv2
import numpy as np

EFFECT_META = {
    "name":        "Voxel Explosion",
    "description": "Frame voxelized into colored cubes; transient onset fires radial explosion force",
    "key_audio":   ["onset", "onset_energy"],
    "tags":        ["voxel", "explosion", "physics", "grid"],
    "order":       3,
}


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 3: Voxel Explosion — grid of colored cubes with physics."""
    H, W = frame.shape[:2]
    GW, GH = 48, 27   # grid dimensions
    cw, ch = W // GW, H // GH

    if "voxels" not in state:
        state["voxels"] = []
        for gy in range(GH):
            for gx in range(GW):
                cx_pos = gx * cw + cw // 2
                cy_pos = gy * ch + ch // 2
                state["voxels"].append({
                    "ox": float(cx_pos), "oy": float(cy_pos),
                    "x":  float(cx_pos), "y":  float(cy_pos),
                    "vx": 0.0,           "vy": 0.0,
                })

    voxels = state["voxels"]
    cx, cy = W // 2, H // 2

    # Trigger explosion on onset
    if af.onset and af.onset_energy > 0.3:
        r = af.onset_energy * 300
        for v in voxels:
            dx   = v["x"] - cx
            dy   = v["y"] - cy
            dist = max(1.0, math.sqrt(dx * dx + dy * dy))
            force = r / dist * random.uniform(0.8, 1.2)
            v["vx"] += (dx / dist) * force
            v["vy"] += (dy / dist) * force

    # Draw
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    for v in voxels:
        ox = max(0, min(W - 1, int(v["ox"])))
        oy = max(0, min(H - 1, int(v["oy"])))
        color = tuple(int(c) for c in frame[oy, ox])

        x1, y1 = int(v["x"]) - cw // 2, int(v["y"]) - ch // 2
        x2, y2 = x1 + cw, y1 + ch
        if 0 <= x1 < W and 0 <= y1 < H and x2 > 0 and y2 > 0:
            cv2.rectangle(canvas,
                          (max(0, x1), max(0, y1)),
                          (min(W, x2),  min(H, y2)),
                          color, -1)

        # Physics
        v["vx"] *= 0.92
        v["vy"] *= 0.92
        v["vy"] += 0.4   # gravity
        v["x"]  += v["vx"]
        v["y"]  += v["vy"]

        # Return to origin
        v["x"] = v["x"] * 0.95 + v["ox"] * 0.05
        v["y"] = v["y"] * 0.95 + v["oy"] * 0.05

    return canvas
