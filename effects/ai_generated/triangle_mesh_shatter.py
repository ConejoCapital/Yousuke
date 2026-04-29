"""V11: Triangle Mesh Shatter — Delaunay triangulation of body that explodes on kicks."""

import os, sys, random, math
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask

EFFECT_META = {
    "name":        "Triangle Mesh Shatter",
    "description": "Delaunay triangulation of body contour; triangles fly apart on kicks, reassemble between",
    "key_audio":   ["onset_energy", "bass", "kick"],
    "tags":        ["mesh", "triangles", "shatter", "body", "maximalist"],
    "order":       99,
}


def _get_triangles(mask, H, W, n_interior=30):
    """Compute Delaunay triangulation from body contour + interior points."""
    mask_u8 = (mask * 255).astype(np.uint8)
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []

    # Collect contour points (subsample)
    pts = []
    for c in contours:
        step = max(1, len(c) // 50)
        for i in range(0, len(c), step):
            pts.append(c[i][0].tolist())

    # Add interior points
    rng = random.Random(42)
    attempts = 0
    while len(pts) < len(pts) + n_interior and attempts < n_interior * 5:
        x = rng.randint(0, W - 1)
        y = rng.randint(0, H - 1)
        if mask[y, x] > 0.5:
            pts.append([x, y])
            n_interior -= 1
        attempts += 1

    if len(pts) < 3:
        return []

    # Delaunay
    rect = (0, 0, W, H)
    subdiv = cv2.Subdiv2D(rect)
    for p in pts:
        px = max(0, min(W - 1, int(p[0])))
        py = max(0, min(H - 1, int(p[1])))
        try:
            subdiv.insert((px, py))
        except cv2.error:
            continue

    triangles = subdiv.getTriangleList()
    result = []
    for t in triangles:
        p1 = (int(t[0]), int(t[1]))
        p2 = (int(t[2]), int(t[3]))
        p3 = (int(t[4]), int(t[5]))
        # Check all points are in bounds
        if all(0 <= p[0] < W and 0 <= p[1] < H for p in [p1, p2, p3]):
            cx = (p1[0] + p2[0] + p3[0]) // 3
            cy = (p1[1] + p2[1] + p3[1]) // 3
            if 0 <= cy < H and 0 <= cx < W and mask[cy, cx] > 0.3:
                result.append({
                    "pts": np.array([p1, p2, p3], dtype=np.int32),
                    "cx": cx, "cy": cy,
                    "dx": 0.0, "dy": 0.0,
                    "vx": 0.0, "vy": 0.0,
                })
    return result


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    onset = getattr(af, "onset_energy", 0.0)
    bass = getattr(af, "bass", 0.0)
    kick = getattr(af, "kick", 0.0)

    # --- Body mask ---
    mask = get_body_mask(frame, state)

    # --- Recompute triangles periodically ---
    if "tri_frame" not in state:
        state["tri_frame"] = 0
        state["triangles"] = []
    state["tri_frame"] += 1

    # Recompute every 30 frames
    if state["tri_frame"] % 30 == 1 or not state["triangles"]:
        state["triangles"] = _get_triangles(mask, H, W)

    # --- Explode on kick ---
    if kick > 0.6:
        force = onset * 200
        for tri in state["triangles"]:
            angle = math.atan2(tri["cy"] - H / 2, tri["cx"] - W / 2)
            tri["vx"] = math.cos(angle) * force * random.uniform(0.5, 1.5)
            tri["vy"] = math.sin(angle) * force * random.uniform(0.5, 1.5)

    # --- Reassemble between kicks ---
    reassembly = 0.05 + bass * 0.1
    out = np.zeros((H, W, 3), dtype=np.uint8)

    for tri in state["triangles"]:
        # Apply velocity
        tri["dx"] += tri["vx"]
        tri["dy"] += tri["vy"]
        # Dampen and pull back
        tri["vx"] *= 0.92
        tri["vy"] *= 0.92
        tri["dx"] *= (1.0 - reassembly)
        tri["dy"] *= (1.0 - reassembly)

        # Displaced triangle
        offset = np.array([int(tri["dx"]), int(tri["dy"])], dtype=np.int32)
        displaced = tri["pts"] + offset

        # Clip to frame bounds
        displaced[:, 0] = np.clip(displaced[:, 0], 0, W - 1)
        displaced[:, 1] = np.clip(displaced[:, 1], 0, H - 1)

        # Get color from original frame at centroid
        ocx = max(0, min(W - 1, tri["cx"]))
        ocy = max(0, min(H - 1, tri["cy"]))
        color = tuple(int(c) for c in frame[ocy, ocx])

        # Fill triangle with sampled texture
        tri_mask = np.zeros((H, W), dtype=np.uint8)
        cv2.fillPoly(tri_mask, [displaced], 255)

        # Source coordinates for texture
        src_pts = tri["pts"].astype(np.float32)
        dst_pts = displaced.astype(np.float32)

        # Simple: fill with averaged color from original frame
        region = frame.copy()
        region_mask = np.zeros((H, W), dtype=np.uint8)
        cv2.fillPoly(region_mask, [tri["pts"]], 255)
        avg_color = cv2.mean(frame, region_mask)[:3]
        color = tuple(int(c) for c in avg_color)

        cv2.fillPoly(out, [displaced], color)

        # Triangle border
        cv2.polylines(out, [displaced], True, (200, 200, 200), 1, cv2.LINE_AA)

    # Add darkened original underneath where no triangles cover
    gray_out = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    empty = (gray_out < 5).astype(np.float32)[:, :, None]
    dark_frame = (frame.astype(np.float32) * 0.15).astype(np.uint8)
    out = (out.astype(np.float32) * (1.0 - empty) +
           dark_frame.astype(np.float32) * empty).astype(np.uint8)

    return out
