#!/usr/bin/env python3
"""
YOUSUKE Live Showcase — All Effects Rotating with Blend + Regular Modes

Cycles through every loaded effect with two transition modes:
  REGULAR — hard cut, switches instantly
  BLEND   — crossfade over configurable duration

Usage:
    python tools/live_showcase.py                          # webcam + mic
    python tools/live_showcase.py --no-cam --simulate      # synthetic, no hardware
    python tools/live_showcase.py --speed 2 --blend-time 1 # faster cycle, longer fade

Keyboard:
    B           Toggle blend/regular mode
    F           Toggle fullscreen
    Space       Pause/resume rotation
    Right/+/=   Next effect
    Left/-      Previous effect
    Up          Faster (shorter dwell)
    Down        Slower (longer dwell)
    1-9         Lock to specific effect
    0           Return to auto-rotate
    Q/ESC       Quit
"""
from __future__ import annotations

import argparse
import io
import math
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

# ── Wire up imports ──────────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "standalone"))
sys.path.insert(0, str(HERE))

# Import visuals — suppress banner in quiet mode (pre-check argv before argparse runs)
_quiet_import = "--quiet" in sys.argv
if _quiet_import:
    _real_stdout = sys.stdout
    sys.stdout = io.StringIO()
from visuals import EFFECTS, EFFECT_NAMES, AudioFeatures  # noqa: E402
if _quiet_import:
    sys.stdout = _real_stdout

# Reuse test-frame generator from render_reel
from render_reel import make_reference_frame  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────
WINDOW_NAME = "YOUSUKE Live Showcase"
SAMPLE_RATE = 22050
BLOCK = 1024
SPEED_MIN = 0.5
SPEED_MAX = 30.0
SPEED_STEP = 0.5


# ── Mic helper (from preview_canonical pattern) ─────────────────────────────
def _try_open_mic(af: AudioFeatures):
    """Start a background mic stream feeding af. Returns stream or False."""
    try:
        import sounddevice as sd
    except ImportError:
        return False

    def _cb(indata, frames, tinfo, status):
        try:
            af.update_from_block(indata.copy(), SAMPLE_RATE)
        except Exception:
            pass

    try:
        stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            blocksize=BLOCK,
            callback=_cb,
        )
        stream.start()
        return stream
    except Exception as e:
        print(f"  [mic] failed ({e}) -- falling back to simulate")
        return False


# ── HUD drawing ──────────────────────────────────────────────────────────────
def draw_hud(
    frame: np.ndarray,
    name: str,
    idx: int,
    total: int,
    af: AudioFeatures,
    fps: float,
    mode: str,
    paused: bool,
    speed: float,
    transition_progress: float,
) -> np.ndarray:
    """Burn overlay: effect info, mode, audio meters, transition bar."""
    out = frame.copy()
    H, W = out.shape[:2]

    # ── Top bar ──
    cv2.rectangle(out, (0, 0), (W, 40), (0, 0, 0), -1)

    pause_str = "  PAUSED" if paused else ""
    label = f"[{idx + 1}/{total}] {name}  |  {mode}  |  {speed:.1f}s{pause_str}"
    cv2.putText(
        out, label, (10, 28),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA,
    )
    cv2.putText(
        out, f"{fps:5.1f} fps", (W - 130, 28),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 200), 2, cv2.LINE_AA,
    )

    # ── Transition progress bar (thin strip below top bar) ──
    if transition_progress > 0.0:
        bar_w = int(W * transition_progress)
        cv2.rectangle(out, (0, 40), (bar_w, 44), (0, 200, 255), -1)
        cv2.rectangle(out, (bar_w, 40), (W, 44), (40, 40, 40), -1)

    # ── Bottom bar: audio meters ──
    cv2.rectangle(out, (0, H - 30), (W, H), (0, 0, 0), -1)
    bars = [
        ("sub", af.sub_bass),
        ("bass", af.bass),
        ("mid", af.mids),
        ("hi", af.highs),
        ("rms", af.energy),
    ]
    x = 10
    for label_txt, val in bars:
        cv2.putText(
            out, label_txt, (x, H - 12),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1, cv2.LINE_AA,
        )
        bar_w = int(np.clip(val, 0, 1) * 80)
        cv2.rectangle(out, (x + 30, H - 22), (x + 30 + bar_w, H - 8), (0, 220, 255), -1)
        x += 130

    # ── Beat indicator ──
    if af.beat:
        cv2.circle(out, (W - 30, H - 15), 7, (0, 100, 255), -1)

    return out


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="YOUSUKE Live Showcase — all effects rotating")
    p.add_argument("--simulate", action="store_true", help="Force simulated audio")
    p.add_argument("--no-cam", action="store_true", help="Use synthetic test frame")
    p.add_argument("--speed", type=float, default=3.0, help="Seconds per effect (default 3)")
    p.add_argument("--blend-time", type=float, default=0.5, help="Crossfade duration in seconds (default 0.5)")
    p.add_argument("--fullscreen", action="store_true", help="Start in fullscreen mode (toggle with F)")
    p.add_argument("--quiet", action="store_true", help="Suppress import banner and per-keystroke prints")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    args = p.parse_args()

    quiet = args.quiet

    W, H = args.width, args.height
    n_effects = len(EFFECTS)
    if n_effects == 0:
        print("  ERROR: no effects loaded")
        return 1

    def qprint(*a, **kw):
        if not quiet:
            print(*a, **kw)

    qprint(f"\n  === YOUSUKE Live Showcase ===")
    qprint(f"  {n_effects} effects loaded")
    qprint(f"  Resolution: {W}x{H}")
    qprint(f"  Dwell: {args.speed}s | Blend time: {args.blend_time}s")

    # ── Audio setup ──
    af = AudioFeatures()
    mic_stream = None
    if not args.simulate:
        mic_stream = _try_open_mic(af)
    if mic_stream:
        qprint(f"  Audio: live mic")
    else:
        qprint(f"  Audio: simulated 128bpm")

    # ── Camera setup ──
    cap = None
    if not args.no_cam:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            qprint("  Webcam unavailable -- falling back to test frame")
            cap = None
        else:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
            qprint(f"  Input: webcam")
    if cap is None:
        qprint(f"  Input: synthetic test frame")

    # ── Window ──
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, W, H)
    is_fullscreen = args.fullscreen
    try:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass
    if is_fullscreen:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # ── State ──
    states = [{} for _ in EFFECTS]
    current_idx = 0
    locked_idx = None          # None = auto-rotate
    paused = False
    blend_mode = True          # True = BLEND, False = REGULAR
    speed = args.speed         # seconds per effect (dwell time)
    blend_time = args.blend_time

    last_switch_time = time.time()
    transitioning = False
    transition_start = 0.0
    outgoing_idx = 0           # effect we're fading FROM

    fps_window: list[float] = []
    t_start = time.time()

    qprint(f"\n  Controls: B=blend/regular  F=fullscreen  Space=pause  Arrows=nav  1-9=lock  0=auto  Q=quit\n")
    qprint(f"  Starting: [{current_idx + 1}/{n_effects}] {EFFECT_NAMES[current_idx]}")

    def _advance(direction: int):
        """Move to next/prev effect, resetting transition state."""
        nonlocal current_idx, last_switch_time, transitioning
        current_idx = (current_idx + direction) % n_effects
        last_switch_time = time.time()
        transitioning = False
        qprint(f"  -> [{current_idx + 1}/{n_effects}] {EFFECT_NAMES[current_idx]}")

    def _start_transition(next_idx: int):
        """Begin a crossfade from current to next_idx."""
        nonlocal transitioning, transition_start, outgoing_idx
        outgoing_idx = current_idx
        transitioning = True
        transition_start = time.time()

    try:
        while True:
            now = time.time()
            t_elapsed = now - t_start

            # ── Audio ──
            if args.simulate or not mic_stream:
                af.simulate(t_elapsed)

            # ── Source frame ──
            if cap is not None:
                ok, src_frame = cap.read()
                if not ok:
                    src_frame = make_reference_frame(W, H, t_elapsed)
            else:
                src_frame = make_reference_frame(W, H, t_elapsed)

            # Ensure resolution matches
            fh, fw = src_frame.shape[:2]
            if (fw, fh) != (W, H):
                src_frame = cv2.resize(src_frame, (W, H))

            # ── Auto-rotate logic ──
            if not paused and locked_idx is None:
                time_since_switch = now - last_switch_time
                if not transitioning and time_since_switch >= speed:
                    next_idx = (current_idx + 1) % n_effects
                    if blend_mode and blend_time > 0:
                        _start_transition(next_idx)
                    else:
                        _advance(1)

            if locked_idx is not None:
                current_idx = locked_idx
                transitioning = False

            # ── Render effect(s) ──
            transition_progress = 0.0

            if transitioning:
                alpha = min(1.0, (now - transition_start) / max(0.01, blend_time))
                transition_progress = alpha
                next_idx = (outgoing_idx + 1) % n_effects

                # Render both effects
                try:
                    out_frame = EFFECTS[outgoing_idx](src_frame.copy(), af, states[outgoing_idx])
                except Exception:
                    out_frame = src_frame.copy()

                try:
                    in_frame = EFFECTS[next_idx](src_frame.copy(), af, states[next_idx])
                except Exception:
                    in_frame = src_frame.copy()

                # Ensure shapes match
                if out_frame.shape[:2] != (H, W):
                    out_frame = cv2.resize(out_frame, (W, H))
                if in_frame.shape[:2] != (H, W):
                    in_frame = cv2.resize(in_frame, (W, H))

                # Crossfade blend
                result = cv2.addWeighted(out_frame, 1.0 - alpha, in_frame, alpha, 0)

                if alpha >= 1.0:
                    # Transition complete
                    current_idx = next_idx
                    last_switch_time = now
                    transitioning = False
                    qprint(f"  -> [{current_idx + 1}/{n_effects}] {EFFECT_NAMES[current_idx]}")
            else:
                try:
                    result = EFFECTS[current_idx](src_frame.copy(), af, states[current_idx])
                except Exception as e:
                    result = src_frame.copy()

                if result.shape[:2] != (H, W):
                    result = cv2.resize(result, (W, H))

            # ── FPS calc ──
            fps_window.append(now)
            fps_window = [t for t in fps_window if now - t < 1.0]
            fps = len(fps_window)

            # ── HUD ──
            mode_str = "BLEND" if blend_mode else "REGULAR"
            display_name = EFFECT_NAMES[current_idx]
            if transitioning:
                next_idx = (outgoing_idx + 1) % n_effects
                display_name = f"{EFFECT_NAMES[outgoing_idx]} -> {EFFECT_NAMES[next_idx]}"

            result = draw_hud(
                result,
                display_name,
                current_idx,
                n_effects,
                af,
                float(fps),
                mode_str,
                paused,
                speed,
                transition_progress,
            )

            cv2.imshow(WINDOW_NAME, result)

            # ── Keyboard ──
            # Use waitKeyEx for full key codes (arrow keys on macOS)
            raw_key = cv2.waitKeyEx(1)
            k = raw_key & 0xFF

            # Arrow key codes: macOS=63232-63235, Linux/GTK=65362-65365
            KEY_UP    = {63232, 65362}
            KEY_DOWN  = {63233, 65363}
            KEY_LEFT  = {63234, 65364}
            KEY_RIGHT = {63235, 65365}

            if k in (ord("q"), 27):  # Q / ESC
                break

            elif k == ord("b") or k == ord("B"):
                blend_mode = not blend_mode
                qprint(f"  Mode: {'BLEND' if blend_mode else 'REGULAR'}")

            elif k == ord("f") or k == ord("F"):
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                else:
                    cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                qprint(f"  Fullscreen: {'ON' if is_fullscreen else 'OFF'}")

            elif k == ord(" "):
                paused = not paused
                if not paused:
                    last_switch_time = time.time()  # reset timer on unpause
                qprint(f"  {'PAUSED' if paused else 'RESUMED'}")

            elif raw_key in KEY_RIGHT or k in (ord("+"), ord("=")):
                next_idx = (current_idx + 1) % n_effects
                if blend_mode and blend_time > 0 and not transitioning:
                    _start_transition(next_idx)
                else:
                    _advance(1)

            elif raw_key in KEY_LEFT or k == ord("-"):
                _advance(-1)

            elif raw_key in KEY_UP:
                speed = max(SPEED_MIN, speed - SPEED_STEP)
                qprint(f"  Speed: {speed:.1f}s per effect")

            elif raw_key in KEY_DOWN:
                speed = min(SPEED_MAX, speed + SPEED_STEP)
                qprint(f"  Speed: {speed:.1f}s per effect")

            elif ord("1") <= k <= ord("9"):
                idx = k - ord("1")
                if idx < n_effects:
                    locked_idx = idx
                    current_idx = idx
                    transitioning = False
                    qprint(f"  Locked: [{idx + 1}/{n_effects}] {EFFECT_NAMES[idx]}")

            elif k == ord("0"):
                locked_idx = None
                last_switch_time = time.time()
                transitioning = False
                qprint(f"  Auto-rotate")

    except KeyboardInterrupt:
        print("\n  Interrupted")
    finally:
        if cap is not None:
            cap.release()
        cv2.destroyAllWindows()
        if mic_stream:
            try:
                mic_stream.stop()
                mic_stream.close()
            except Exception:
                pass

    print(f"  Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
