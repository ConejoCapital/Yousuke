# ¥ØUSUK€ Visual Extender
## AI Psychosis Summit NYC — April 30, 2026

Audio-reactive live visuals inspired by ¥ØUSUK€ ¥UK1MAT$U's Boiler Room Tokyo × Super Dommune set.
Two delivery paths: GPU-accelerated TouchDesigner network + Python standalone fallback.

---

## QUICK START (Day of Show)

```bash
cd ~/Desktop/Yousuke

# Option A — TouchDesigner (recommended, GPU, best quality)
bash launch_summit.sh --mode td

# Option B — Python fallback (if TD fails, works on any laptop)
bash launch_summit.sh --mode python

# Option C — Both simultaneously (safety net)
bash launch_summit.sh --mode both
```

**Controls (same for both paths):**

| Key | Action |
|-----|--------|
| `1` | Neon Contour |
| `2` | Particle Confetti |
| `3` | Voxel Explosion |
| `4` | Volumetric Rings |
| `5` | Shard Burst |
| `6` | Gold Particle Rain |
| `7` | Film Grain |
| `8` | Kanji Float |
| `0` | Auto-rotate mode |
| `Space` | Cycle to next effect |
| `Esc` | Exit fullscreen / quit |

---

## TOUCHDESIGNER NETWORK (visuals.toe)

### Architecture

```
audio_in (AudioDeviceIn CHOP)
    └── audio_analysis (baseCOMP)
            ├── spectrum → band_extract scriptCHOP
            │       Outputs: rms, sub_bass, bass, mids, highs, beat
            └── out1 → feeds all 8 fx_ containers

cam_in (VideoDeviceIn TOP, 1280×720)
    └── feeds into all 8 fx_ containers

fx_neon_contour ──┐
fx_particles ─────┤
fx_voxel ─────────┤
fx_rings ─────────┼── effect_router (switchTOP) ─→ router_out ─→ main_output (windowCOMP)
fx_shards ────────┤
fx_gold_rain ─────┤
fx_grain ─────────┤
fx_kanji ─────────┘

active_effect (constantCHOP, 0-7) → switchTOP index
auto_rotate (chopExecuteDAT) → advances index every 8s / 32 beats
keyboard_control (keyboardinDAT) → manual 1-8 lock / 0 auto / Space cycle
```

### Operator Map

| Path | Type | Purpose |
|------|------|---------|
| `/project1/cam_in` | videodeviceinTOP | MacBook Pro Camera input, 1280×720 |
| `/project1/audio_in` | audiodeviceinCHOP | Default mic / audio interface |
| `/project1/audio_analysis` | baseCOMP | Frequency band extraction + beat |
| `/project1/audio_analysis/out1` | outCHOP | 6 channels: rms sub_bass bass mids highs beat |
| `/project1/fx_neon_contour` | baseCOMP | Effect 1: cyan Sobel edges + bloom |
| `/project1/fx_particles` | baseCOMP | Effect 2: edge → noise color → feedback trails |
| `/project1/fx_voxel` | baseCOMP | Effect 3: GLSL pixelate grid + radial explosion |
| `/project1/fx_rings` | baseCOMP | Effect 4: GLSL expanding rings + feedback |
| `/project1/fx_shards` | baseCOMP | Effect 5: GLSL Voronoi shard fracture |
| `/project1/fx_gold_rain` | baseCOMP | Effect 6: GLSL gold rain particles |
| `/project1/fx_grain` | baseCOMP | Effect 7: perlin noise grain + vignette GLSL |
| `/project1/fx_kanji` | baseCOMP | Effect 8: GLSL procedural kanji glyphs + feedback |
| `/project1/effect_router` | switchTOP | 8-way switcher, index = active_effect |
| `/project1/active_effect` | constantCHOP | Effect index 0-7, default 0 |
| `/project1/auto_rotate` | chopexecuteDAT | Auto-advances on time (8s) or beat count (32) |
| `/project1/keyboard_control` | keyboardinDAT | Keys 1-8, 0, Space |
| `/project1/router_out` | nullTOP | Clean output signal |
| `/project1/main_output` | windowCOMP | 1280×720 borderless presentation window |

### Audio Channels Used Per Effect

| Effect | rms | sub_bass | bass | mids | highs | beat |
|--------|-----|----------|------|------|-------|------|
| Neon Contour | hue | — | blur size, brightness | — | — | — |
| Particles | — | — | spawn opacity | color speed | — | opacity pulse |
| Voxel | — | explosion force | blast strength | — | — | — |
| Rings | — | — | ring thickness | speed, color | — | ring trigger |
| Shards | — | burst trigger | shard count | — | — | seed reset |
| Gold Rain | — | — | brightness | — | density | — |
| Film Grain | grain amp | — | brightness | — | — | — |
| Kanji | — | spawn rate, speed | — | — | — | opacity pulse |

### Opening the Output Window

In TouchDesigner after loading visuals.toe:
1. Find `main_output` (windowCOMP) in the network
2. Right-click → **Open Window** (or pulse `winopen` parameter)
3. Window opens at 1280×720 centered on screen
4. Move to projector/secondary monitor, drag to fill

Or via Python console in TD:
```python
op('/project1/main_output').par.winopen.pulse()
```

---

## PYTHON STANDALONE (standalone/visuals.py)

Runs on any laptop, no TD required. Uses OpenCV + sounddevice.

```bash
# Webcam + mic
python standalone/visuals.py --mode webcam --audio mic

# Pre-recorded audio file
python standalone/visuals.py --mode file --audio reference/audio.mp3

# With reference video
python standalone/visuals.py --mode file --video reference/video.mp4
```

---

## EFFECTS DETAIL

### Effect 1 — Neon Contour
Sobel edge detection → blur (bass-driven) → HSV hue rotation (rms) → additive composite.
Visual: cyan magenta glowing outlines on black. Think TRON cyberpunk.

### Effect 2 — Particle Confetti
Silhouette threshold → edge → noise color multiplication → feedback trail decay (0.88).
Visual: colorful particle streaks tracing body boundaries, persisting as trails.

### Effect 3 — Voxel Explosion
GLSL shader: 32×18 pixelated grid with per-cell displacement from center.
Displacement = sub_bass × sin(time + dist). Each cell color-sampled from cam.
Visual: frame dissolves into dancing colored squares that explode outward.

### Effect 4 — Volumetric Rings
GLSL dual-ring shader with feedback (0.97 decay). Two ring phases offset by 0.5.
Ring speed driven by mids. Beat channel triggers brightness pulse.
Visual: concentric expanding ellipses in cyan→magenta, accumulating into halos.

### Effect 5 — Shard Burst
GLSL Voronoi fracture: hash-based cells, each displaced radially from center.
Seed changes with sub_bass + time, so pattern re-fractures on bass hits.
Edge glow between shards picks random warm/cool color per cell.
Visual: glass-shattering cam frame with glowing fracture lines.

### Effect 6 — Gold Particle Rain
GLSL 80-200 column rain (highs-driven density). Per-column speed + phase stagger.
Gold to white color temperature shift on rms. Glitter flash on highs peak.
Motion trail below each particle.
Visual: dense golden downward shimmer like a gilded snowstorm.

### Effect 7 — Film Grain
Perlin2d noise (audio-animated seed) added to cam. GLSL vignette + desaturation.
Scanline flicker, warm highlight / cool shadow color grade. Contrast 1.15.
Visual: cinematic B&W-ish textured cam with analog film aesthetic.

### Effect 8 — Kanji Float
GLSL procedural 5×7 stroke glyph renderer (12 columns). Each glyph rises from bottom.
Red or gold color per column. Feedback 0.93 decay for trailing ghosts.
Glitch horizontal shift on bass peak.
Visual: drifting red/gold kanji-like symbols on dark cam with ghost trails.

---

## TROUBLESHOOTING

**No webcam in TD:**
- TD → cam_in → Viewer should show camera. Check System Preferences → Privacy → Camera → TouchDesigner

**Audio not responding:**
- Check audio_analysis/out1 viewer shows non-zero channels
- Tap mic or play music, watch rms channel value

**Effect looks black:**
- Check td_get_errors for GLSL compile errors
- All GLSL shaders verified at build time (0 errors)

**Low FPS (< 30fps):**
- Effects are GPU-based GLSL — should be well under 16ms on any modern Mac
- Verified: 60fps at 0.2% CPU budget during build

**Window won't open:**
- `op('/project1/main_output').par.winopen.pulse()` in TD console

**Auto-rotate not switching:**
- Check `auto_rotate` node is active (green, not bypassed)
- Beat detection needs audible music (beatCHOP requires tempo)

---

## FILE MAP

```
~/Desktop/Yousuke/
├── visuals.toe              ← TouchDesigner network (THIS IS THE MAIN FILE)
├── launch_summit.sh         ← One-command launch script
├── SUMMIT_README.md         ← This file
├── .venv/                   ← Python 3.13 venv (all deps installed)
├── effects/                 ← 8 Python effect plugins
│   ├── neon_contour.py
│   ├── particle_confetti.py
│   ├── voxel_explosion.py
│   ├── volumetric_rings.py
│   ├── shard_burst.py       ← optimized (was 42ms → 1.4ms)
│   ├── gold_particle_rain.py
│   ├── film_grain.py        ← optimized (was 35ms → 7.8ms)
│   └── kanji_float.py
├── standalone/
│   └── visuals.py           ← Python visual engine
├── tests/                   ← 96 pytest tests (all passing)
├── tools/render_reel.py     ← Headless reel renderer
└── reports/
    ├── reel.mp4             ← Reference reel (open to preview effects)
    ├── PHASE_D_PLAN.md      ← Original TD build plan
    └── perf_baseline.json   ← Python engine perf data
```

---

## DEMO SCRIPT (5 minutes)

**Suggested flow for Summit presentation:**

```
0:00  Launch: bash launch_summit.sh --mode td
      Open main_output window on projector

0:30  Start with Effect 1 (Neon Contour) — clean, recognizable
      Show edge detection reacting to music → explain audio analysis

1:00  Hit key 5 (Shard Burst) — dramatic on bass hit
      "Every kick fractures the frame into Voronoi shards"

1:30  Hit key 4 (Rings) — meditative, shows mids reactivity
      "Mid frequencies spawn expanding halos"

2:00  Hit key 6 (Gold Rain) — crowd-pleaser
      "High frequency density controls how many gold particles fall"

2:30  Hit key 8 (Kanji) — mysterious + unique
      "Sub-bass spawns glitch kanji that drift upward"

3:00  Key 0 → Auto-rotate mode
      "And when you let it run free, the system breathes with the music"

4:00  Return to Key 1 (Neon Contour) for outro
      Show interaction with live cam (wave / make shapes)

5:00  End
```

---

*Built with TouchDesigner 2025.32460 + Hermes Agent (twozero MCP)*
*Python 3.13, OpenCV, librosa, sounddevice*
*¥ØUSUK€ ¥UK1MAT$U — Boiler Room Tokyo × Super Dommune*
