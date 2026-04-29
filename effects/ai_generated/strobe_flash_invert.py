"""V5: Strobe Flash Invert — full-frame color inversion on beat with afterimage persistence."""

import cv2
import numpy as np

EFFECT_META = {
    "name":        "Strobe Flash Invert",
    "description": "Full-frame color inversion on beat for 2-3 frames, rapid decay with afterimage persistence",
    "key_audio":   ["beat", "energy", "onset_energy"],
    "tags":        ["strobe", "invert", "flash", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "flash_counter" not in state:
        state["flash_counter"] = 0
        state["accum"] = None

    beat = getattr(af, "beat", False)
    energy = getattr(af, "energy", 0.0)
    onset = getattr(af, "onset_energy", 0.0)

    # Trigger flash on beat
    if beat:
        state["flash_counter"] = max(state["flash_counter"], 3)

    # Apply inversion during flash
    if state["flash_counter"] > 0:
        out = (255 - frame)
        state["flash_counter"] -= 1
    else:
        out = frame.copy()

    # Contrast boost
    contrast = 1.2 + energy * 0.8
    mean = np.mean(out).astype(np.float32)
    out_f = (out.astype(np.float32) - mean) * contrast + mean
    out = np.clip(out_f, 0, 255).astype(np.uint8)

    # Afterimage persistence via accumulator
    prev = state.get("accum")
    if prev is None or prev.shape != out.shape:
        state["accum"] = out.copy()
    else:
        decay = 0.65 + energy * 0.2
        blended = cv2.addWeighted(out, 1.0 - decay * 0.4,
                                  prev, decay * 0.4, 0)
        state["accum"] = blended.copy()
        out = blended

    return out
