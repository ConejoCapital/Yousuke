"""Smoke-test a canonical plugin against its reference cluster frame.

Usage:
    python tools/test_canonical.py <plugin_filename> <cluster_id>

Reads reference/canonical_effects_frames/cluster_NN.jpg as input frame,
runs the plugin with simulated audio features, saves before/after side-by-side.
"""
import importlib.util
import sys
from pathlib import Path

import cv2
import numpy as np


class _AF:
    """Simulate mid-energy audio frame (what the plugin will see during playback)."""
    energy       = 0.55
    bass         = 0.50
    mids         = 0.40
    highs        = 0.35
    sub_bass     = 0.30
    beat         = False
    onset        = True
    onset_energy = 0.45
    kick         = 0.40


def main():
    if len(sys.argv) != 3:
        print("usage: python tools/test_canonical.py <plugin_path> <cluster_id>")
        sys.exit(1)

    plugin_path = Path(sys.argv[1])
    cluster_id  = int(sys.argv[2])
    root        = Path(__file__).resolve().parent.parent

    # Load plugin
    spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    print(f"loaded plugin: {mod.EFFECT_META['name']}")

    # Use a neutral INPUT — NOT the reference frame itself, which is post-effect.
    # The reference is the TARGET; we need a raw camera-like frame to transform.
    ref_path = root / "reference" / "canonical_effects_frames" / f"cluster_{cluster_id:02d}.jpg"
    ref = cv2.imread(str(ref_path))
    if ref is None:
        print(f"ERROR: reference not found: {ref_path}")
        sys.exit(1)

    # Create a synthetic "raw cam" input: a neutral-toned version of some arbitrary frame
    # Use a different cluster's raw-ish frame by pulling frame 500 from the video.
    video = str(root / "reference" / "video.mp4")
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, 500)
    ok, raw = cap.read()
    cap.release()
    if not ok:
        print("ERROR: failed to read raw frame from video")
        sys.exit(1)

    # Bring target and raw to same size
    target_h, target_w = ref.shape[:2]
    raw = cv2.resize(raw, (target_w, target_h))
    # Neutralize the raw frame a bit so we're testing the effect transform,
    # not downstream of the broadcast color grade. Bring it closer to log-ish.
    raw_neutral = cv2.convertScaleAbs(raw, alpha=0.85, beta=10)

    # Run plugin
    state = {}
    # Warm up with 4 frames so motion-blur state initializes
    for _ in range(4):
        out = mod.fx_function(raw_neutral, _AF(), state)

    # Side-by-side: [raw input | plugin output | reference target]
    labeled = []
    for img, label in [(raw_neutral, "INPUT (raw cam)"),
                       (out,         f"OUTPUT: {mod.EFFECT_META['name']}"),
                       (ref,         f"TARGET: cluster_{cluster_id:02d}")]:
        copy = img.copy()
        cv2.rectangle(copy, (0, 0), (target_w, 32), (0, 0, 0), -1)
        cv2.putText(copy, label, (8, 22), cv2.FONT_HERSHEY_SIMPLEX,
                    0.55, (255, 255, 255), 1, cv2.LINE_AA)
        labeled.append(copy)

    grid = np.hstack(labeled)
    out_path = root / "reports" / f"canonical_test_{plugin_path.stem}.jpg"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), grid, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"saved: {out_path}")

    # Also print numeric signature comparison
    def sig(img):
        small = cv2.resize(img, (64, 64))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        return dict(
            edge_density = float(np.count_nonzero(edges)) / (64 * 64),
            brightness   = float(np.mean(gray)) / 255.0,
            saturation   = float(np.mean(hsv[:, :, 1])) / 255.0,
            variance     = float(np.std(small.reshape(-1, 3))) / 255.0,
        )

    s_out = sig(out)
    s_tgt = sig(ref)
    print("\n  metric       output    target    delta")
    for k in s_out:
        d = s_out[k] - s_tgt[k]
        print(f"  {k:<12} {s_out[k]:>6.3f}   {s_tgt[k]:>6.3f}   {d:+.3f}")


if __name__ == "__main__":
    main()
