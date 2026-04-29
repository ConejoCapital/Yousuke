#!/usr/bin/env python3
"""
¥ØUSUK€ Visual Extender — Python Standalone Visual Engine
AI Psychosis Summit NYC | April 30, 2026

Usage:
    python visuals.py --mode webcam --audio mic
    python visuals.py --mode webcam --audio reference/audio.mp3
    python visuals.py --mode file   --audio reference/audio.mp3
    python visuals.py --mode window --audio mic

Keyboard:
    1-9     Lock to effect (supports >8 if plugins loaded)
    +/=     Cycle forward through all effects
    0       Auto-rotate
    SPACE   Pause
    L       Load audio file mid-session
    Q/ESC   Quit
"""

import argparse
import importlib.util
import math
import os
import random
import sys
import threading
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# ── Optional imports (graceful degradation) ──────────────────────────────────
try:
    import librosa
    import librosa.feature
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("WARNING: librosa not installed. File audio analysis disabled.")

try:
    import sounddevice as sd
    HAS_SOUNDDEVICE = True
except ImportError:
    HAS_SOUNDDEVICE = False
    print("WARNING: sounddevice not installed. Mic input disabled.")

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("WARNING: Pillow not installed. Kanji float effect disabled.")

try:
    import mediapipe as mp
    HAS_MEDIAPIPE = True
    _mp_selfie = mp.solutions.selfie_segmentation
except ImportError:
    HAS_MEDIAPIPE = False

# ── Constants ─────────────────────────────────────────────────────────────────
WINDOW_NAME = "¥ØUSUK€ Visual Extender"
TARGET_FPS  = 30
FRAME_TIME  = 1.0 / TARGET_FPS

AUDIO_BLOCK = 1024
SAMPLE_RATE = 22050

# Inline fallback palettes (used by fallback effect functions)
NEON_COLORS   = [(255, 50, 50), (50, 255, 200), (200, 50, 255), (50, 200, 255), (255, 200, 50)]
GOLD_COLOR    = (0, 165, 255)
KANJI_COLORS  = [(0, 0, 200), (0, 140, 255), (0, 50, 255)]
KANJI_LIST    = list("電音波光火夢狂神血宇虚空界霊")


# ── Audio features data class ──────────────────────────────────────────────────
class AudioFeatures:
    def __init__(self):
        self.energy       = 0.0   # overall RMS 0-1
        self.bass         = 0.0   # 0-300 Hz, 0-1
        self.mids         = 0.0   # 300-3000 Hz, 0-1
        self.highs        = 0.0   # 3000+ Hz, 0-1
        self.sub_bass     = 0.0   # 0-80 Hz, 0-1
        self.beat         = False # beat detected this frame
        self.onset        = False # transient onset this frame
        self.onset_energy = 0.0
        self.kick         = 0.0   # kick detection 0-1
        self._prev_energy = 0.0

    def update_from_block(self, audio_block: np.ndarray, sr: int = SAMPLE_RATE):
        """Update features from a raw audio block."""
        block = audio_block.astype(np.float32)
        if block.ndim > 1:
            block = block.mean(axis=1)

        rms = float(np.sqrt(np.mean(block ** 2)))
        self.energy = min(1.0, rms * 20)

        fft   = np.abs(np.fft.rfft(block))
        freqs = np.fft.rfftfreq(len(block), 1.0 / sr)

        def band_energy(low, high):
            mask = (freqs >= low) & (freqs < high)
            if not mask.any():
                return 0.0
            return min(1.0, float(np.mean(fft[mask])) * 0.01)

        self.sub_bass = band_energy(20,    80)
        self.bass     = band_energy(80,   300)
        self.mids     = band_energy(300,  3000)
        self.highs    = band_energy(3000, 20000)

        energy_delta      = self.energy - self._prev_energy
        self.beat         = energy_delta > 0.15
        self.onset        = energy_delta > 0.25
        self.onset_energy = max(0.0, energy_delta)
        self.kick         = min(1.0, self.sub_bass + self.bass * 0.5)
        self._prev_energy = self.energy

    def simulate(self, t: float):
        """Simulate audio features for testing when no audio available."""
        bpm         = 128.0
        beat_period = 60.0 / bpm
        phase       = (t % beat_period) / beat_period
        self.beat   = phase < 0.05
        self.energy = 0.3 + 0.4 * abs(math.sin(t * bpm / 60 * math.pi))
        self.bass   = 0.4 + 0.4 * abs(math.sin(t * 2.1))
        self.mids   = 0.3 + 0.3 * abs(math.sin(t * 3.7))
        self.highs  = 0.2 + 0.3 * abs(math.sin(t * 5.3))
        self.sub_bass = 0.5 * abs(math.sin(t * 1.1))
        self.kick   = 1.0 if self.beat else 0.0
        self.onset  = self.beat
        self.onset_energy = 0.5 if self.beat else 0.0


# ── Plugin loader ─────────────────────────────────────────────────────────────

def _load_effects_from_dir(effects_dir: Path) -> tuple:
    """
    Load all effect plugins from effects_dir and effects_dir/ai_generated.
    Built-ins are sorted by EFFECT_META["order"]; ai_generated/ loaded after.
    Returns (effects_list, names_list, load_report_lines).
    """
    t_start = time.time()
    collected_effects: list = []
    collected_names:   list = []
    report_lines:      list = []

    # ── Load built-ins (sorted by order) ──
    built_in_candidates = []
    if effects_dir.exists():
        for py_file in effects_dir.glob("*.py"):
            if py_file.name in ("__init__.py",) or py_file.name.startswith("_"):
                continue
            built_in_candidates.append(py_file)

    loaded_tuples = []
    for py_file in built_in_candidates:
        try:
            spec   = importlib.util.spec_from_file_location(py_file.stem, py_file)
            m      = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            fn     = getattr(m, "fx_function", None)
            meta   = getattr(m, "EFFECT_META", {})
            if callable(fn):
                loaded_tuples.append((meta.get("order", 99), meta.get("name", py_file.stem), fn, py_file.name))
        except Exception as e:
            report_lines.append(f"  [plugin] WARNING: {py_file.name}: {e}")

    loaded_tuples.sort(key=lambda x: x[0])
    for _, name, fn, fname in loaded_tuples:
        idx = len(collected_effects) + 1
        collected_effects.append(fn)
        collected_names.append(name)
        report_lines.append(f"  [plugin] {idx:2d}. {name:<24} ({fname})")

    # ── Load ai_generated/ ──
    ai_dir = effects_dir / "ai_generated"
    if ai_dir.exists():
        ai_files = sorted(f for f in ai_dir.glob("*.py")
                          if not f.name.startswith("_"))
        for py_file in ai_files:
            try:
                spec   = importlib.util.spec_from_file_location(py_file.stem, py_file)
                m      = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                fn     = getattr(m, "fx_function", None)
                meta   = getattr(m, "EFFECT_META", {})
                if callable(fn):
                    idx = len(collected_effects) + 1
                    collected_effects.append(fn)
                    name = meta.get("name", py_file.stem)
                    collected_names.append(name)
                    report_lines.append(f"  [ai]    {idx:2d}. {name:<24} ({py_file.name})")
            except Exception as e:
                report_lines.append(f"  [ai] WARNING: {py_file.name}: {e}")

    # ── Load canonical/ (vision-verified ¥ØUSUK€ effects) ──
    # These are loaded LAST but sorted to the FRONT of the rotation via
    # EFFECT_META["order"] (use negative ints for canonical; defaults keep
    # order=1..8 for deprecated built-ins).
    canonical_dir = effects_dir / "canonical"
    canonical_tuples = []
    if canonical_dir.exists():
        for py_file in sorted(canonical_dir.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            try:
                spec   = importlib.util.spec_from_file_location(py_file.stem, py_file)
                m      = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                fn     = getattr(m, "fx_function", None)
                meta   = getattr(m, "EFFECT_META", {})
                if callable(fn):
                    canonical_tuples.append((meta.get("order", -1),
                                             meta.get("name", py_file.stem),
                                             fn, py_file.name))
            except Exception as e:
                report_lines.append(f"  [canonical] WARNING: {py_file.name}: {e}")

    canonical_tuples.sort(key=lambda x: x[0])
    # Prepend canonical effects to the front of the rotation
    for _, name, fn, fname in reversed(canonical_tuples):
        collected_effects.insert(0, fn)
        collected_names.insert(0, name)
        report_lines.insert(0, f"  [canon] {name:<24} ({fname})")

    elapsed = time.time() - t_start
    return collected_effects, collected_names, report_lines, elapsed


# ── Startup banner + plugin load ──────────────────────────────────────────────

_EFFECTS_DIR = Path(__file__).parent.parent / "effects"

print(f"\n=== ¥ØUSUK€ Visual Extender ===")
print(f"  Loading effects from: {_EFFECTS_DIR}\n")

_loaded_effects, _loaded_names, _report_lines, _load_time = _load_effects_from_dir(_EFFECTS_DIR)

for line in _report_lines:
    print(line)

if _loaded_effects:
    print(f"\n  ✓ {len(_loaded_effects)} effects loaded in {_load_time:.2f}s")
    print(f"  → Fallback: NONE (all loaded from plugins)")
    EFFECTS      = _loaded_effects
    EFFECT_NAMES = _loaded_names
else:
    print("  WARNING: No plugins found — using inline fallback effects")


# ── Inline fallback effect implementations ────────────────────────────────────
# Only used if the effects/ directory is missing or all files fail to load.

def _fx_neon_contour(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    low_thresh  = int(30 + af.bass * 40)
    high_thresh = int(100 + af.bass * 80)
    edges = cv2.Canny(gray, low_thresh, high_thresh)
    thickness = max(1, int(1 + af.bass * 7))
    kernel = np.ones((thickness, thickness), np.uint8)
    edges  = cv2.dilate(edges, kernel)
    colored = cv2.applyColorMap(edges, cv2.COLORMAP_HSV)
    hue_shift = int(af.energy * 120)
    hsv = cv2.cvtColor(colored, cv2.COLOR_BGR2HSV).astype(np.int32)
    hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
    colored = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    bloom_strength = 0.8 + af.bass * 1.5
    blur   = cv2.GaussianBlur(colored, (21, 21), 0)
    result = cv2.addWeighted(colored, 1.0, blur, bloom_strength, 0)
    dark = (frame.astype(np.float32) * 0.15).astype(np.uint8)
    return cv2.add(dark, result)


def _fx_particle_confetti(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    if "particles" not in state:
        state["particles"] = []
    particles = state["particles"]
    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    edge_ys, edge_xs = np.where(edges > 0)
    spawn_count = 0
    if af.kick > 0.4 and len(edge_xs) > 0:
        spawn_count = int(20 + af.kick * 80)
    for _ in range(spawn_count):
        idx   = random.randint(0, len(edge_xs) - 1)
        color = random.choice(NEON_COLORS)
        speed = 1 + af.bass * 6
        angle = random.uniform(0, 2 * math.pi)
        particles.append({
            "x": float(edge_xs[idx]), "y": float(edge_ys[idx]),
            "vx": math.cos(angle) * speed * random.uniform(0.5, 1.5),
            "vy": math.sin(angle) * speed * random.uniform(0.5, 1.5) - 2,
            "color": color, "life": 1.0,
            "decay": random.uniform(0.02, 0.05), "size": random.randint(1, 4),
        })
    canvas = (frame.astype(np.float32) * 0.3).astype(np.uint8)
    alive  = []
    for p in particles:
        p["x"] += p["vx"]; p["y"] += p["vy"]; p["vy"] += 0.15; p["vx"] *= 0.98
        p["life"] -= p["decay"]
        if p["life"] > 0 and 0 <= int(p["x"]) < W and 0 <= int(p["y"]) < H:
            c = tuple(int(ch * p["life"]) for ch in p["color"])
            cv2.circle(canvas, (int(p["x"]), int(p["y"])), p["size"], c, -1)
            alive.append(p)
    state["particles"] = alive[-2000:]
    return canvas


def _fx_voxel_explosion(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    GW, GH = 48, 27; cw, ch = W // GW, H // GH
    if "voxels" not in state:
        state["voxels"] = []
        for gy in range(GH):
            for gx in range(GW):
                cx_pos = gx * cw + cw // 2; cy_pos = gy * ch + ch // 2
                state["voxels"].append({"ox": float(cx_pos), "oy": float(cy_pos),
                                         "x": float(cx_pos), "y": float(cy_pos), "vx": 0.0, "vy": 0.0})
    voxels = state["voxels"]; cx, cy = W // 2, H // 2
    if af.onset and af.onset_energy > 0.3:
        r = af.onset_energy * 300
        for v in voxels:
            dx = v["x"] - cx; dy = v["y"] - cy; dist = max(1.0, math.sqrt(dx*dx + dy*dy))
            force = r / dist * random.uniform(0.8, 1.2)
            v["vx"] += (dx/dist)*force; v["vy"] += (dy/dist)*force
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    for v in voxels:
        ox = max(0, min(W-1, int(v["ox"]))); oy = max(0, min(H-1, int(v["oy"])))
        color = tuple(int(c) for c in frame[oy, ox])
        x1, y1 = int(v["x"]) - cw//2, int(v["y"]) - ch//2; x2, y2 = x1+cw, y1+ch
        if 0 <= x1 < W and 0 <= y1 < H and x2 > 0 and y2 > 0:
            cv2.rectangle(canvas, (max(0,x1), max(0,y1)), (min(W,x2), min(H,y2)), color, -1)
        v["vx"] *= 0.92; v["vy"] *= 0.92; v["vy"] += 0.4; v["x"] += v["vx"]; v["y"] += v["vy"]
        v["x"] = v["x"]*0.95 + v["ox"]*0.05; v["y"] = v["y"]*0.95 + v["oy"]*0.05
    return canvas


def _fx_volumetric_rings(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]; cx, cy = W//2, H//2
    if "rings" not in state:
        state["rings"] = []; state["beat_count"] = 0
    rings = state["rings"]
    if af.beat:
        state["beat_count"] += 1
        r_color = (int(50+af.mids*200), int(100+af.highs*155), int(200+af.energy*55))
        rings.append({"r": 5.0, "opacity": 1.0, "speed": 2.0+af.mids*8.0, "color": r_color,
                       "thickness": max(1, int(3+af.bass*4))})
    canvas = (frame.astype(np.float32) * 0.2).astype(np.uint8); alive = []
    for ring in rings:
        alpha = ring["opacity"]; c = tuple(int(ch*alpha) for ch in ring["color"])
        axes = (int(ring["r"]), int(ring["r"]*0.6))
        if axes[0] > 0 and axes[1] > 0:
            cv2.ellipse(canvas, (cx, cy), axes, 0, 0, 360, c, ring["thickness"])
        ring["r"] += ring["speed"]; ring["opacity"] -= 0.012
        if ring["opacity"] > 0: alive.append(ring)
    state["rings"] = alive[-50:]
    return canvas


def _make_shards_inline(frame, n):
    H, W = frame.shape[:2]; cx, cy = W//2, H//2; shards = []
    for i in range(n):
        angle_start = (i/n)*360; angle_end = ((i+1)/n)*360
        r1 = random.uniform(50, min(W,H)*0.3); r2 = random.uniform(r1, min(W,H)*0.7)
        pts = []
        for a, r in [(angle_start,r1),(angle_end,r1),(angle_end,r2),(angle_start,r2)]:
            rad = math.radians(a + random.uniform(-5,5))
            x = cx + r*math.cos(rad) + random.uniform(-20,20)
            y = cy + r*math.sin(rad) + random.uniform(-20,20)
            pts.append([max(0,min(W-1,int(x))), max(0,min(H-1,int(y)))])
        dx = pts[0][0]-cx; dy = pts[0][1]-cy; dist = max(1, math.sqrt(dx*dx+dy*dy))
        speed = random.uniform(2,8)
        shards.append({"pts": np.array(pts,dtype=np.float32), "x":0.0,"y":0.0,
                        "vx":(dx/dist)*speed,"vy":(dy/dist)*speed,"angle":0.0,
                        "rot_speed":random.uniform(-3,3)})
    return shards


def _fx_shard_burst(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    if "shards" not in state:
        state["shards"] = []; state["active"] = False
    if af.kick > 0.75 and not state["active"]:
        state["shards"] = _make_shards_inline(frame, int(20+af.kick*160)); state["active"] = True
    canvas = np.zeros((H, W, 3), dtype=np.uint8)
    if state["active"]:
        all_stopped = True
        for shard in state["shards"]:
            shard["x"] += shard["vx"]; shard["y"] += shard["vy"]
            shard["vx"] *= 0.94; shard["vy"] *= 0.94; shard["angle"] += shard["rot_speed"]
            if abs(shard["vx"]) > 0.2 or abs(shard["vy"]) > 0.2: all_stopped = False
            pts = shard["pts"].copy().astype(np.float32); cx_s, cy_s = pts.mean(axis=0)
            angle_rad = math.radians(shard["angle"]); cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
            for i, pt in enumerate(pts):
                dx, dy = pt[0]-cx_s, pt[1]-cy_s
                pts[i] = [cx_s+dx*cos_a-dy*sin_a+shard["x"], cy_s+dx*sin_a+dy*cos_a+shard["y"]]
            pts_int = pts.astype(np.int32); mask = np.zeros((H,W),dtype=np.uint8)
            cv2.fillPoly(mask,[pts_int],255); masked = cv2.bitwise_and(frame,frame,mask=mask)
            canvas = cv2.add(canvas, masked)
        if all_stopped: state["active"]=False; state["shards"]=[]
    else:
        canvas = frame.copy()
    return canvas


def _fx_gold_particle_rain(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    if "rain" not in state: state["rain"] = []
    rain = state["rain"]
    spawn = int(af.highs*150 + af.energy*50)
    for _ in range(spawn):
        t = af.energy
        rain.append({"x":random.uniform(0,W),"y":random.uniform(-20,0),
                      "vy":random.uniform(3,10),"brightness":random.uniform(0.5,1.0),
                      "size":random.randint(1,3),"color":(int(t*200),int(165+t*90),255)})
    canvas = (frame.astype(np.float32)*0.4).astype(np.uint8); alive = []
    for p in rain:
        b = p["brightness"]; c = tuple(int(ch*b) for ch in p["color"])
        xi, yi = int(p["x"]), int(p["y"])
        if 0 <= yi < H: cv2.circle(canvas,(xi,yi),p["size"],c,-1)
        p["y"] += p["vy"]
        if p["y"] < H+10: alive.append(p)
    state["rain"] = alive[-3000:]
    return canvas


def _fx_film_grain(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    grain_scale = 0.3 + af.energy * 0.7
    noise   = np.random.normal(0, grain_scale*50, (H,W,3)).astype(np.int16)
    grained = np.clip(frame.astype(np.int16)+noise, 0, 255).astype(np.uint8)
    if "vignette" not in state or state.get("vig_shape") != (H,W):
        Y, X = np.ogrid[:H,:W]
        dist = np.sqrt(((X-W/2)/(W/2))**2 + ((Y-H/2)/(H/2))**2)
        state["vignette"] = np.clip(1.0-dist*0.5, 0, 1); state["vig_shape"]=(H,W)
    vig = state["vignette"][:,:,np.newaxis]
    grained = (grained.astype(np.float32)*vig).astype(np.uint8)
    sat_factor = 0.5 + af.energy * 0.5
    hsv = cv2.cvtColor(grained, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:,:,1] *= sat_factor
    return cv2.cvtColor(np.clip(hsv,0,255).astype(np.uint8), cv2.COLOR_HSV2BGR)


def _load_kanji_font_inline() -> Optional[str]:
    candidates = [
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/Library/Fonts/Osaka.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _fx_kanji_float(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]
    if "floats" not in state:
        state["floats"] = []; state["font"] = _load_kanji_font_inline()
    floats = state["floats"]; font = state["font"]
    if af.sub_bass > 0.35:
        for _ in range(int(af.sub_bass * 3)):
            floats.append({"char":random.choice(KANJI_LIST),"x":random.randint(30,W-60),
                            "y":float(H+20),"vy":-(1.5+af.sub_bass*5),"opacity":1.0,
                            "decay":random.uniform(0.004,0.01),"size":random.randint(28,80),
                            "color":random.choice(KANJI_COLORS)})
    canvas = (frame.astype(np.float32)*0.5).astype(np.uint8)
    if HAS_PIL and font:
        img_pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        draw    = ImageDraw.Draw(img_pil, "RGBA"); alive = []
        for k in floats:
            beat_pulse = 0.7 + 0.3*(1.0 if af.beat else 0.0)
            alpha = int(255*k["opacity"]*beat_pulse)
            if alpha > 0:
                try:
                    try: f = ImageFont.truetype(font, k["size"])
                    except: f = ImageFont.load_default()
                    r,g,b = k["color"][2],k["color"][1],k["color"][0]
                    draw.text((k["x"],int(k["y"])),k["char"],font=f,fill=(r,g,b,alpha))
                except: pass
            k["y"] += k["vy"]; k["opacity"] -= k["decay"]
            if k["opacity"] > 0: alive.append(k)
        state["floats"] = alive[-100:]
        canvas = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    else:
        alive = []
        for k in floats:
            c = tuple(int(ch*k["opacity"]) for ch in k["color"])
            cv2.putText(canvas, k["char"], (int(k["x"]),int(k["y"])),
                        cv2.FONT_HERSHEY_SIMPLEX, k["size"]/30.0, c, 2, cv2.LINE_AA)
            k["y"] += k["vy"]; k["opacity"] -= k["decay"]
            if k["opacity"] > 0: alive.append(k)
        state["floats"] = alive[-100:]
    return canvas


# ── Apply fallback if plugins failed ─────────────────────────────────────────
if not _loaded_effects:
    EFFECTS = [
        _fx_neon_contour, _fx_particle_confetti, _fx_voxel_explosion, _fx_volumetric_rings,
        _fx_shard_burst, _fx_gold_particle_rain, _fx_film_grain, _fx_kanji_float,
    ]
    EFFECT_NAMES = [
        "Neon Contour", "Particle Confetti", "Voxel Explosion", "Volumetric Rings",
        "Shard Burst", "Gold Particle Rain", "Film Grain Base", "Kanji Float",
    ]
    print(f"  → Fallback: ACTIVE — {len(EFFECTS)} inline effects loaded")
    for i, name in enumerate(EFFECT_NAMES, 1):
        print(f"  [fallback] {i:2d}. {name}")


# ── Audio backends ────────────────────────────────────────────────────────────

class MicAudio:
    """Captures live microphone input in a background thread."""

    def __init__(self, sr: int = SAMPLE_RATE, block: int = AUDIO_BLOCK):
        self.sr      = sr
        self.block   = block
        self._buf    = np.zeros(block, dtype=np.float32)
        self._lock   = threading.Lock()
        self._stream = None

    def start(self):
        if not HAS_SOUNDDEVICE:
            print("sounddevice not available — using simulated audio")
            return
        try:
            self._stream = sd.InputStream(
                samplerate=self.sr,
                channels=1,
                blocksize=self.block,
                dtype="float32",
                callback=self._callback,
            )
            self._stream.start()
            print(f"Mic started: {sd.query_devices(kind='input')['name']}")
        except Exception as e:
            print(f"WARNING: Mic init failed: {e} — using simulated audio")

    def _callback(self, indata, frames, time_info, status):
        with self._lock:
            self._buf = indata[:, 0].copy()

    def get_block(self) -> np.ndarray:
        with self._lock:
            return self._buf.copy()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()


class FileAudio:
    """Reads pre-recorded audio file, provides blocks in sync with playback time."""

    def __init__(self, path: str, sr: int = SAMPLE_RATE, block: int = AUDIO_BLOCK):
        self.path        = path
        self.sr          = sr
        self.block       = block
        self._data       = None
        self._pos        = 0
        self._start_time = None

    def load(self) -> bool:
        if not HAS_LIBROSA:
            print("librosa not installed — cannot load audio file")
            return False
        try:
            print(f"Loading audio: {self.path}")
            self._data, _ = librosa.load(self.path, sr=self.sr, mono=True)
            self._start_time = time.time()
            print(f"  Duration: {len(self._data)/self.sr:.1f}s")
            return True
        except Exception as e:
            print(f"WARNING: Could not load {self.path}: {e}")
            return False

    def get_block(self) -> np.ndarray:
        if self._data is None or self._start_time is None:
            return np.zeros(self.block)
        elapsed = time.time() - self._start_time
        pos = int(elapsed * self.sr)
        if pos >= len(self._data):
            self._start_time = time.time()
            pos = 0
        end   = min(pos + self.block, len(self._data))
        chunk = self._data[pos:end]
        if len(chunk) < self.block:
            chunk = np.pad(chunk, (0, self.block - len(chunk)))
        return chunk


# ── Main engine ───────────────────────────────────────────────────────────────

class VisualEngine:
    def __init__(self, args):
        self.args            = args
        self.af              = AudioFeatures()
        self.effect_states   = [{} for _ in range(len(EFFECTS))]
        self.active_effect   = 0   # 0-indexed; 0 = first effect in auto-rotate
        self.locked_effect   = None
        self.paused          = False
        self.running         = True
        self.frame_count     = 0
        self.last_switch     = time.time()
        self.switch_cooldown = 8.0  # seconds between auto-rotations
        self._beat_count     = 0
        self._error_counts   = {}   # per-effect error suppression
        self.fps_times: list = []   # rolling FPS tracker

        # Audio backend
        self.audio = self._init_audio()

        # Webcam
        self.cap = None
        if args.mode == "webcam":
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                print("WARNING: Could not open webcam — using blank frame")
                self.cap = None

    def _init_audio(self):
        if self.args.audio == "mic":
            backend = MicAudio()
            backend.start()
            return backend
        else:
            backend = FileAudio(self.args.audio)
            if not backend.load():
                print("Falling back to simulated audio")
                return None
            return backend

    def _get_frame(self) -> np.ndarray:
        if self.cap:
            ret, frame = self.cap.read()
            if ret:
                return frame
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    def _update_audio(self):
        t = time.time()
        if self.audio is not None:
            block = self.audio.get_block()
            self.af.update_from_block(block)
        else:
            self.af.simulate(t)

        if self.af.beat:
            self._beat_count += 1

    def _auto_rotate(self):
        """Switch effect based on energy thresholds or beat count."""
        now = time.time()
        if self.locked_effect is not None:
            self.active_effect = self.locked_effect
            return

        time_ok      = (now - self.last_switch) >= self.switch_cooldown
        beats_ok     = self._beat_count >= 16
        energy_spike = self.af.onset_energy > 0.4 and (now - self.last_switch) >= 3.0

        if time_ok or beats_ok or energy_spike:
            self.active_effect = (self.active_effect + 1) % len(EFFECTS)
            self.last_switch   = now
            self._beat_count   = 0
            print(f"  → Effect {self.active_effect + 1}: {EFFECT_NAMES[self.active_effect]}")

    def _draw_hud(self, frame: np.ndarray) -> np.ndarray:
        """Draw minimal HUD: effect name + audio bars + FPS."""
        H, W = frame.shape[:2]
        out  = frame.copy()

        # Rolling FPS
        now = time.time()
        self.fps_times.append(now)
        self.fps_times = [t for t in self.fps_times if now - t < 1.0]
        fps = len(self.fps_times)

        # Effect name
        name     = EFFECT_NAMES[self.active_effect]
        lock_str = " [LOCKED]" if self.locked_effect is not None else ""
        label    = f"{self.active_effect + 1}: {name}{lock_str}"
        cv2.putText(out, label, (15, H - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 180, 180), 1, cv2.LINE_AA)

        # FPS counter (bottom-right)
        cv2.putText(out, f"{fps} fps", (W - 80, H - 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

        # Audio bars (bottom-left)
        bar_x, bar_y = 15, H - 60
        bar_h = 30
        for i, (val, color, lbl) in enumerate([
            (self.af.sub_bass, (200, 80,  50),  "SUB"),
            (self.af.bass,     (200, 120, 50),  "BSS"),
            (self.af.mids,     (100, 200, 100), "MID"),
            (self.af.highs,    (50,  150, 200), "HGH"),
        ]):
            bx       = bar_x + i * 45
            filled_h = int(bar_h * val)
            cv2.rectangle(out, (bx, bar_y), (bx + 30, bar_y - bar_h), (50, 50, 50), -1)
            cv2.rectangle(out, (bx, bar_y), (bx + 30, bar_y - filled_h), color, -1)
            cv2.putText(out, lbl, (bx, bar_y + 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.3, (160, 160, 160), 1)

        # Beat flash
        if self.af.beat:
            cv2.circle(out, (W - 30, H - 30), 10, (0, 255, 255), -1)

        return out

    def _handle_key(self, key: int) -> bool:
        """Handle keyboard input. Returns False if should quit."""
        if key == -1:
            return True

        k = key & 0xFF

        if k in (ord("q"), 27):  # Q or ESC
            return False

        if ord("1") <= k <= ord("9"):
            idx = k - ord("1")
            if idx < len(EFFECTS):
                self.locked_effect = idx
                self.active_effect = idx
                print(f"  Locked to effect {idx + 1}: {EFFECT_NAMES[idx]}")

        elif k in (ord("+"), ord("=")):
            # Cycle forward through all effects (including beyond 9)
            next_idx = (self.active_effect + 1) % len(EFFECTS)
            self.locked_effect = next_idx
            self.active_effect = next_idx
            print(f"  Locked to effect {next_idx + 1}: {EFFECT_NAMES[next_idx]}")

        elif k == ord("0"):
            self.locked_effect = None
            print("  Auto-rotate mode")

        elif k == ord(" "):
            self.paused = not self.paused
            print(f"  {'Paused' if self.paused else 'Resumed'}")

        elif k == ord("l") or k == ord("L"):
            self._prompt_load_audio()

        return True

    def _prompt_load_audio(self):
        """Attempt to load a new audio file at runtime."""
        print("\n  Enter audio file path (or press Enter to cancel):")
        try:
            path = input("  > ").strip()
            if path and os.path.exists(path):
                new_backend = FileAudio(path)
                if new_backend.load():
                    if hasattr(self.audio, "stop"):
                        self.audio.stop()
                    self.audio = new_backend
                    print(f"  Loaded: {path}")
            else:
                print("  Cancelled / file not found")
        except EOFError:
            pass

    def run(self):
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 1280, 720)

        n = len(EFFECTS)
        print(f"\n¥ØUSUK€ Visual Extender running")
        print(f"Mode: {self.args.mode} | Audio: {self.args.audio}")
        print(f"Effects loaded: {n}")
        print(f"Controls: 1-9 lock effect | +/= next effect | 0 auto | SPACE pause | L load audio | Q quit\n")
        print(f"Starting with: {EFFECT_NAMES[self.active_effect]}")

        while self.running:
            loop_start = time.time()

            self._update_audio()

            if not self.paused:
                raw_frame  = self._get_frame()
                frame_base = raw_frame.copy()

                self._auto_rotate()

                eff_idx = self.active_effect
                try:
                    result = EFFECTS[eff_idx](frame_base, self.af, self.effect_states[eff_idx])
                except Exception as e:
                    key = f"err_{eff_idx}"
                    if key not in self._error_counts:
                        self._error_counts[key] = 0
                    self._error_counts[key] += 1
                    if self._error_counts[key] <= 3:
                        print(f"  [effect error] {EFFECT_NAMES[eff_idx]}: {e}")
                    result = frame_base  # fall back to raw frame

                if not self.args.no_hud:
                    result = self._draw_hud(result)
                cv2.imshow(WINDOW_NAME, result)

            self.frame_count += 1

            key = cv2.waitKey(1)
            if not self._handle_key(key):
                break

            elapsed = time.time() - loop_start
            sleep   = FRAME_TIME - elapsed
            if sleep > 0:
                time.sleep(sleep)

        self.cleanup()

    def cleanup(self):
        print("\nShutting down...")
        if self.cap:
            self.cap.release()
        if hasattr(self.audio, "stop"):
            self.audio.stop()
        cv2.destroyAllWindows()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="¥ØUSUK€ Visual Extender — Audio-reactive visual engine"
    )
    parser.add_argument(
        "--mode",
        choices=["webcam", "file", "window"],
        default="webcam",
        help="Visual input mode (default: webcam)",
    )
    parser.add_argument(
        "--audio",
        default="mic",
        help="Audio source: 'mic' for live input or path to audio file (default: mic)",
    )
    parser.add_argument(
        "--effect",
        type=int,
        default=None,
        help="Start locked on a specific effect (1-N)",
    )
    parser.add_argument(
        "--no-hud",
        action="store_true",
        help="Disable HUD overlay",
    )
    args = parser.parse_args()

    if args.audio != "mic" and not os.path.exists(args.audio):
        print(f"WARNING: Audio file not found: {args.audio}")
        print("  Falling back to simulated audio.")
        args.audio = None

    engine = VisualEngine(args)
    if args.effect and 1 <= args.effect <= len(EFFECTS):
        engine.locked_effect = args.effect - 1
        engine.active_effect = args.effect - 1

    engine.run()


if __name__ == "__main__":
    main()
