#!/usr/bin/env python3
"""
¥ØUSUK€ Visual Extender — Headless Reel Renderer

Renders a fully-deterministic test reel cycling through all 8 effects with
simulated audio features. Useful for:
  - Visual QA without webcam/mic
  - Regression checking after effect edits
  - Generating preview clips for the show producer

Usage:
    python tools/render_reel.py --duration 32 --output reports/reel.mp4
    python tools/render_reel.py --resolution 1920 1080 --duration 60
    python tools/render_reel.py --effect 3 --duration 8        # single effect
"""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Wire up imports
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "standalone"))

from visuals import EFFECTS, EFFECT_NAMES, AudioFeatures  # noqa: E402


def make_reference_frame(W: int, H: int, t: float) -> np.ndarray:
    """A test frame with structure: gradient + moving figure + edges.
    Stands in for a webcam feed when running headless."""
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    # Vertical gradient — gives Canny edges work to do
    grad = np.linspace(20, 180, H, dtype=np.uint8)
    frame[:] = grad[:, None, None]
    # Slowly drifting silhouette so motion-sensitive effects have something
    cx = int(W / 2 + math.sin(t * 0.6) * W * 0.15)
    cy = int(H / 2 + math.cos(t * 0.4) * H * 0.10)
    cv2.circle(frame, (cx, cy), int(min(W, H) * 0.18), (50, 220, 255), -1)
    cv2.rectangle(frame, (int(W * 0.1), int(H * 0.6)),
                  (int(W * 0.3), int(H * 0.85)), (200, 50, 200), -1)
    # Concentric rings give Sobel/Canny strong responses
    for r in (60, 110, 160):
        cv2.circle(frame, (cx, cy), r, (255, 255, 255), 1)
    return frame


def draw_hud(frame: np.ndarray, name: str, idx: int, total: int,
             af: AudioFeatures, fps: float) -> np.ndarray:
    """Burn an overlay describing the active effect + audio levels."""
    out = frame.copy()
    H, W = out.shape[:2]
    # Top bar
    cv2.rectangle(out, (0, 0), (W, 40), (0, 0, 0), -1)
    cv2.putText(out, f"[{idx + 1}/{total}] {name}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, f"{fps:5.1f} fps", (W - 130, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2, cv2.LINE_AA)
    # Audio bars at bottom
    cv2.rectangle(out, (0, H - 30), (W, H), (0, 0, 0), -1)
    bars = [("sub",  af.sub_bass), ("bass", af.bass), ("mid",  af.mids),
            ("hi",   af.highs), ("rms",  af.energy)]
    x = 10
    for label, val in bars:
        cv2.putText(out, label, (x, H - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA)
        bar_w = int(val * 80)
        cv2.rectangle(out, (x + 30, H - 22), (x + 30 + bar_w, H - 8),
                      (0, 220, 255), -1)
        x += 130
    if af.beat:
        cv2.circle(out, (W - 30, H - 15), 7, (0, 100, 255), -1)
    return out


def main():
    p = argparse.ArgumentParser(description="Render a deterministic effects reel")
    p.add_argument("--duration", type=float, default=32.0,
                   help="Total reel duration in seconds (default: 32 = 4s/effect)")
    p.add_argument("--resolution", nargs=2, type=int, default=[1280, 720],
                   metavar=("W", "H"))
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--output", type=str,
                   default=str(ROOT / "reports" / "reel.mp4"))
    p.add_argument("--effect", type=int, default=None,
                   help="Render only this effect (1-N) for the full duration")
    p.add_argument("--no-hud", action="store_true")
    args = p.parse_args()

    W, H = args.resolution
    n_effects = len(EFFECTS)
    if args.effect and not (1 <= args.effect <= n_effects):
        print(f"  --effect must be in 1..{n_effects}")
        return 1

    total_frames = int(args.duration * args.fps)
    secs_per_effect = args.duration if args.effect else args.duration / n_effects
    print(f"\n  Rendering reel: {W}x{H} @ {args.fps}fps, {args.duration}s "
          f"({total_frames} frames)")
    print(f"  {'Single effect:' if args.effect else 'Cycle:'} "
          f"{secs_per_effect:.1f}s per effect")
    print(f"  Output: {args.output}")

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), fourcc, float(args.fps), (W, H))
    if not writer.isOpened():
        print(f"  ERROR: failed to open writer for {out_path}")
        return 1

    af = AudioFeatures()
    states = [{} for _ in EFFECTS]
    fps_window = []
    t0 = time.perf_counter()
    last_effect_idx = -1
    per_effect_ms = {n: [] for n in EFFECT_NAMES}

    for i in range(total_frames):
        t = i / args.fps
        # Active effect
        if args.effect:
            eff_idx = args.effect - 1
        else:
            eff_idx = min(int(t / secs_per_effect), n_effects - 1)

        if eff_idx != last_effect_idx:
            print(f"  [{t:6.2f}s] → fx{eff_idx + 1} {EFFECT_NAMES[eff_idx]}")
            last_effect_idx = eff_idx

        # Drive audio with simulator
        af.simulate(t)
        # Source frame
        frame = make_reference_frame(W, H, t)

        f0 = time.perf_counter()
        result = EFFECTS[eff_idx](frame, af, states[eff_idx])
        per_effect_ms[EFFECT_NAMES[eff_idx]].append((time.perf_counter() - f0) * 1000)

        # Defensive: ensure shape matches writer
        if result.shape[:2] != (H, W):
            result = cv2.resize(result, (W, H))

        # FPS HUD (rolling avg)
        fps_window.append(time.perf_counter())
        fps_window = fps_window[-30:]
        fps = (len(fps_window) - 1) / max(1e-6, fps_window[-1] - fps_window[0])

        if not args.no_hud:
            result = draw_hud(result, EFFECT_NAMES[eff_idx], eff_idx,
                              n_effects, af, fps)

        writer.write(result)

        if (i + 1) % args.fps == 0:
            print(f"    .. {i + 1}/{total_frames} frames "
                  f"({(i + 1) / total_frames * 100:5.1f}%)  "
                  f"render fps={fps:5.1f}")

    writer.release()
    elapsed = time.perf_counter() - t0
    print(f"\n  ✓ Wrote {total_frames} frames in {elapsed:.2f}s "
          f"({total_frames / elapsed:.1f} render fps)")
    print(f"  ✓ {out_path}")

    print("\n  Per-effect render time (ms/frame):")
    for name, samples in per_effect_ms.items():
        if not samples:
            continue
        med = float(np.median(samples))
        print(f"    {name:<22} median={med:5.2f}ms  n={len(samples)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
