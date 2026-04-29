"""V9: Neon Skeleton Wire — MediaPipe Pose wireframe with pulsing neon colors and joint particles."""

import os, sys, math, random
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _utils import get_body_mask, draw_neon_line

EFFECT_META = {
    "name":        "Neon Skeleton Wire",
    "description": "MediaPipe Pose landmarks connected with glowing neon wireframe, joint particle burst on beat",
    "key_audio":   ["bass", "energy", "kick"],
    "tags":        ["skeleton", "pose", "neon", "wireframe", "maximalist"],
    "order":       99,
}

# MediaPipe Pose connections (pairs of landmark indices)
_POSE_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 7),     # face right
    (0, 4), (4, 5), (5, 6), (6, 8),     # face left
    (9, 10),                              # mouth
    (11, 12),                             # shoulders
    (11, 13), (13, 15),                   # left arm
    (12, 14), (14, 16),                   # right arm
    (11, 23), (12, 24),                   # torso
    (23, 24),                             # hips
    (23, 25), (25, 27),                   # left leg
    (24, 26), (26, 28),                   # right leg
    (15, 17), (15, 19), (15, 21),        # left hand
    (16, 18), (16, 20), (16, 22),        # right hand
    (27, 29), (27, 31),                   # left foot
    (28, 30), (28, 32),                   # right foot
]

_LIMB_COLORS = [
    (255, 0, 128), (0, 255, 128), (128, 0, 255),
    (0, 255, 255), (255, 128, 0), (255, 0, 255),
    (0, 128, 255), (255, 255, 0),
]

# Optional: MediaPipe Pose
_mp_pose = None
_pose_model = None


def _init_pose():
    global _mp_pose, _pose_model
    if _mp_pose is not None:
        return True
    try:
        import mediapipe as mp
        _mp_pose = mp.solutions.pose
        _pose_model = _mp_pose.Pose(
            static_image_mode=False,
            model_complexity=0,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        return True
    except Exception:
        return False


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    bass = getattr(af, "bass", 0.0)
    energy = getattr(af, "energy", 0.0)
    kick = getattr(af, "kick", 0.0)

    if "particles" not in state:
        state["particles"] = []
        state["t"] = 0
    state["t"] += 1
    t = state["t"]

    # --- Faint body ghost ---
    mask = get_body_mask(frame, state)
    mask3 = mask[:, :, None]
    ghost = (frame.astype(np.float32) * 0.12 * mask3).astype(np.uint8)
    out = ghost.copy()

    # --- Pose detection ---
    landmarks = None
    if _init_pose():
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = _pose_model.process(rgb)
        if results.pose_landmarks:
            landmarks = []
            for lm in results.pose_landmarks.landmark:
                px = int(lm.x * W)
                py = int(lm.y * H)
                landmarks.append((px, py, lm.visibility))

    if landmarks is None:
        # Fallback: no pose detected, just show ghost with glow edges
        mask_u8 = (mask * 255).astype(np.uint8)
        edges = cv2.Canny(mask_u8, 50, 150)
        edge_color = np.zeros_like(out)
        edge_color[:, :, 0] = edges
        edge_color[:, :, 2] = edges
        glow = cv2.GaussianBlur(edge_color, (15, 15), 0)
        out = cv2.add(out, glow)
        return out

    # --- Draw neon wireframe ---
    thickness = max(1, int(2 + bass * 6))
    glow = int(5 + energy * 15)

    for idx, (i, j) in enumerate(_POSE_CONNECTIONS):
        if i >= len(landmarks) or j >= len(landmarks):
            continue
        pt1 = landmarks[i]
        pt2 = landmarks[j]
        if pt1[2] < 0.3 or pt2[2] < 0.3:
            continue

        color = _LIMB_COLORS[idx % len(_LIMB_COLORS)]
        # Pulse color on energy
        pulse = 0.5 + 0.5 * math.sin(t * 0.15 + idx * 0.5)
        color = tuple(int(c * (0.5 + pulse * 0.5)) for c in color)

        p1 = (pt1[0], pt1[1])
        p2 = (pt2[0], pt2[1])

        # Core line
        cv2.line(out, p1, p2, color, thickness, cv2.LINE_AA)
        # Glow
        overlay = np.zeros_like(out)
        cv2.line(overlay, p1, p2, color, max(1, glow), cv2.LINE_AA)
        glow_blur = cv2.GaussianBlur(overlay, (0, 0), max(1, glow // 2))
        out = cv2.add(out, glow_blur)

    # --- Joint particles on kick ---
    if kick > 0.5:
        n_spawn = int(kick * 20)
        for _ in range(n_spawn):
            lm = random.choice(landmarks)
            if lm[2] < 0.3:
                continue
            state["particles"].append({
                "x": float(lm[0]), "y": float(lm[1]),
                "vx": random.uniform(-4, 4),
                "vy": random.uniform(-4, 4),
                "life": random.uniform(0.5, 1.0),
                "color": random.choice(_LIMB_COLORS),
            })

    # Draw particles
    alive = []
    for p in state["particles"]:
        p["x"] += p["vx"]
        p["y"] += p["vy"]
        p["life"] -= 0.03
        if p["life"] <= 0:
            continue
        alive.append(p)
        px, py = int(p["x"]), int(p["y"])
        if 0 <= px < W and 0 <= py < H:
            alpha = min(1.0, p["life"])
            color = tuple(int(c * alpha) for c in p["color"])
            cv2.circle(out, (px, py), 2, color, -1)

    state["particles"] = alive[-500:]

    return out
