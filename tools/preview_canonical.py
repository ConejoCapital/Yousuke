"""
Live preview of a single canonical plugin on webcam + mic.

Usage:
    python tools/preview_canonical.py effects/canonical/chiaroscuro_magenta.py
    python tools/preview_canonical.py effects/canonical/chiaroscuro_magenta.py --duration 12
    python tools/preview_canonical.py effects/canonical/chiaroscuro_magenta.py --simulate

Opens a window titled with the effect name. Press Q or ESC to quit early,
otherwise exits automatically after --duration seconds (default 12).
"""
import argparse
import importlib.util
import math
import sys
import threading
import time
from pathlib import Path

import cv2
import numpy as np

SAMPLE_RATE = 22050
BLOCK       = 1024


class AudioFeatures:
    """Matches the AudioFeatures class in standalone/visuals.py."""
    def __init__(self):
        self.energy       = 0.0
        self.bass         = 0.0
        self.mids         = 0.0
        self.highs        = 0.0
        self.sub_bass     = 0.0
        self.beat         = False
        self.onset        = False
        self.onset_energy = 0.0
        self.kick         = 0.0
        self._prev_energy = 0.0

    def update_from_block(self, block: np.ndarray, sr: int = SAMPLE_RATE):
        b = block.astype(np.float32)
        if b.ndim > 1:
            b = b.mean(axis=1)
        rms = float(np.sqrt(np.mean(b ** 2)))
        self.energy = min(1.0, rms * 20)
        fft = np.abs(np.fft.rfft(b))
        freqs = np.fft.rfftfreq(len(b), 1.0 / sr)

        def be(lo, hi):
            m = (freqs >= lo) & (freqs < hi)
            return 0.0 if not m.any() else min(1.0, float(np.mean(fft[m])) * 0.01)

        self.sub_bass = be(20, 80)
        self.bass     = be(80, 300)
        self.mids     = be(300, 3000)
        self.highs    = be(3000, 20000)
        d = self.energy - self._prev_energy
        self.beat  = d > 0.15
        self.onset = d > 0.25
        self.onset_energy = max(0.0, d)
        self.kick = min(1.0, self.sub_bass + self.bass * 0.5)
        self._prev_energy = self.energy

    def simulate(self, t: float):
        bpm = 128.0
        beat_period = 60.0 / bpm
        phase = (t % beat_period) / beat_period
        self.beat = phase < 0.05
        self.energy = 0.3 + 0.4 * abs(math.sin(t * bpm / 60 * math.pi))
        self.bass = 0.4 + 0.4 * abs(math.sin(t * 2.1))
        self.mids = 0.3 + 0.3 * abs(math.sin(t * 3.7))
        self.highs = 0.2 + 0.3 * abs(math.sin(t * 5.3))
        self.sub_bass = 0.5 * abs(math.sin(t * 1.1))
        self.kick = 1.0 if self.beat else 0.0
        self.onset = self.beat
        self.onset_energy = 0.5 if self.beat else 0.0


def _try_open_mic(af: AudioFeatures):
    """Start a background thread reading mic into af. Returns True on success."""
    try:
        import sounddevice as sd
    except ImportError:
        return False

    stop = threading.Event()

    def _cb(indata, frames, tinfo, status):
        try:
            af.update_from_block(indata.copy())
        except Exception:
            pass

    try:
        stream = sd.InputStream(samplerate=SAMPLE_RATE,
                                 channels=1, blocksize=BLOCK,
                                 callback=_cb)
        stream.start()
        return stream
    except Exception as e:
        print(f"  [mic] failed ({e}) — falling back to simulate")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plugin", help="Path to plugin .py file")
    ap.add_argument("--duration", type=float, default=12.0)
    ap.add_argument("--simulate", action="store_true",
                    help="Use simulated audio instead of mic")
    ap.add_argument("--cam", type=int, default=0)
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    args = ap.parse_args()

    plugin_path = Path(args.plugin)
    if not plugin_path.exists():
        print(f"  ERROR: plugin not found: {plugin_path}")
        sys.exit(1)

    # Load plugin
    spec = importlib.util.spec_from_file_location(plugin_path.stem, plugin_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fx_name = mod.EFFECT_META.get("name", plugin_path.stem)
    win_title = f"¥ØUSUK€ preview — {fx_name}"
    print(f"\n  LIVE PREVIEW: {fx_name}")
    print(f"  duration: {args.duration}s (or press Q/ESC to exit early)")

    # Audio source
    af = AudioFeatures()
    mic_stream = None
    if not args.simulate:
        mic_stream = _try_open_mic(af)
    if mic_stream:
        print(f"  audio: live mic")
    else:
        print(f"  audio: simulated 128bpm (use --simulate flag to force this)")

    # Camera
    cap = cv2.VideoCapture(args.cam)
    if not cap.isOpened():
        print(f"  ERROR: webcam index {args.cam} won't open. "
              f"Check System Settings → Privacy → Camera for your terminal.")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  args.width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)

    # Window — try to bring it to front
    cv2.namedWindow(win_title, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_title, args.width, args.height)
    # macOS-specific nudge to front
    try:
        cv2.setWindowProperty(win_title, cv2.WND_PROP_TOPMOST, 1)
    except Exception:
        pass

    state = {}
    t_start = time.time()
    frame_count = 0
    perf_times = []

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                time.sleep(0.01)
                continue

            t_frame_start = time.time()
            if args.simulate or not mic_stream:
                af.simulate(t_frame_start - t_start)

            try:
                out = mod.fx_function(frame, af, state)
            except Exception as e:
                print(f"  plugin crashed: {e}")
                out = frame
            perf_times.append(time.time() - t_frame_start)

            # HUD
            elapsed = time.time() - t_start
            remaining = max(0.0, args.duration - elapsed)
            fps = frame_count / elapsed if elapsed > 0 else 0.0
            avg_ms = (sum(perf_times[-30:]) / len(perf_times[-30:]) * 1000.0
                      if perf_times else 0.0)
            hud = f"{fx_name}  |  {fps:4.1f}fps  {avg_ms:5.1f}ms  |  {remaining:4.1f}s  |  Q=quit"
            cv2.rectangle(out, (0, 0), (args.width, 32), (0, 0, 0), -1)
            cv2.putText(out, hud, (8, 22), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (255, 255, 255), 1, cv2.LINE_AA)
            # audio bars at bottom
            for i, (lab, val) in enumerate([("sub", af.sub_bass), ("bas", af.bass),
                                              ("mid", af.mids),    ("hi ", af.highs),
                                              ("rms", af.energy)]):
                x = 8 + i * 130
                cv2.rectangle(out, (x, args.height - 28), (x + 120, args.height - 12),
                              (40, 40, 40), -1)
                w = int(np.clip(val, 0, 1) * 120)
                cv2.rectangle(out, (x, args.height - 28), (x + w, args.height - 12),
                              (200, 200, 240), -1)
                cv2.putText(out, f"{lab} {val:.2f}", (x + 4, args.height - 32),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.38, (220, 220, 220), 1, cv2.LINE_AA)

            cv2.imshow(win_title, out)
            k = cv2.waitKey(1) & 0xFF
            if k in (ord("q"), 27):
                print(f"  exited early at {elapsed:.1f}s")
                break
            if elapsed >= args.duration:
                print(f"  duration reached")
                break
            frame_count += 1
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if mic_stream:
            try:
                mic_stream.stop()
                mic_stream.close()
            except Exception:
                pass

    # Final perf report
    if perf_times:
        p50 = np.percentile(perf_times, 50) * 1000
        p95 = np.percentile(perf_times, 95) * 1000
        max_ms = max(perf_times) * 1000
        print(f"  perf: {len(perf_times)} frames, "
              f"p50={p50:.1f}ms  p95={p95:.1f}ms  max={max_ms:.1f}ms")
        budget_ok = "✓" if p95 < 33.3 else "✗ (>33ms = below 30fps)"
        print(f"  30fps budget: {budget_ok}")


if __name__ == "__main__":
    main()
