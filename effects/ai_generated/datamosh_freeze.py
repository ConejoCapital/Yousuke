"""V1: Datamosh Freeze — amplified frame-difference with frozen motion smear on onsets."""

import cv2
import numpy as np

EFFECT_META = {
    "name":        "Datamosh Freeze",
    "description": "Amplified frame-difference; on onset, freeze motion vectors creating characteristic datamosh smear",
    "key_audio":   ["onset_energy", "bass", "energy"],
    "tags":        ["datamosh", "glitch", "motion", "maximalist"],
    "order":       99,
}


def fx_function(frame, af, state):
    H, W = frame.shape[:2]

    if "prev_frame" not in state:
        state["prev_frame"] = frame.copy()
        state["frozen_diff"] = None
        state["freeze_counter"] = 0
        return frame

    prev = state["prev_frame"]
    onset = getattr(af, "onset_energy", 0.0)
    bass = getattr(af, "bass", 0.0)
    energy = getattr(af, "energy", 0.0)

    # Compute frame difference
    diff = cv2.absdiff(frame, prev)

    # Amplification
    amp = 2 + bass * 6
    diff_amp = np.clip(diff.astype(np.float32) * amp, 0, 255).astype(np.uint8)

    # On onset, freeze the diff
    if onset > 0.3:
        state["frozen_diff"] = diff_amp.copy()
        state["freeze_counter"] = int(onset * 15)

    # If in freeze mode, blend frozen diff into output
    out = frame.copy()

    if state["freeze_counter"] > 0 and state["frozen_diff"] is not None:
        frozen = state["frozen_diff"]
        # Ensure shapes match
        if frozen.shape == out.shape:
            blend = state["freeze_counter"] / max(1, int(onset * 15) if onset > 0.3 else 10)
            blend = min(1.0, blend * 0.7)

            # Smear: displace frame using frozen diff as motion hint
            gray_diff = cv2.cvtColor(frozen, cv2.COLOR_BGR2GRAY).astype(np.float32)
            dx = (gray_diff / 255.0 * 20 - 10).astype(np.float32)
            dy = (np.roll(gray_diff, 1, axis=0) / 255.0 * 20 - 10).astype(np.float32)

            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            map_x = xx + dx * blend
            map_y = yy + dy * blend
            smeared = cv2.remap(frame, map_x, map_y, cv2.INTER_LINEAR,
                                borderMode=cv2.BORDER_REPLICATE)

            # Blend smeared with additive diff
            out = cv2.addWeighted(smeared, 0.7, frozen, 0.3 * blend, 0)

        state["freeze_counter"] -= 1

    # Also add current diff subtly
    out = cv2.addWeighted(out, 0.85, diff_amp, 0.15 * energy, 0)

    state["prev_frame"] = frame.copy()
    return out
