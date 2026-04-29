# Architecture

Technical reference for the Yousuke audio-reactive visual system.

---

## TouchDesigner Operator Map

All operators live under `/project1/`.

### Input Layer

| Path | Type | Purpose |
|------|------|---------|
| `/project1/cam_in` | videodevinTOP | Camera input (1280x720). Supports MacBook Pro Camera, OBS Virtual Camera, iPhone USB (Bunphone Camera). Switch via `cam_in.par.device`. |
| `/project1/audio_in` | audiodeviceinCHOP | Default microphone / audio interface input |

### Audio Analysis

| Path | Type | Purpose |
|------|------|---------|
| `/project1/audio_analysis` | baseCOMP | Container for spectral analysis chain |
| `/project1/audio_analysis/out1` | outCHOP | Exposes 7 normalized channels (0-1): `rms`, `sub_bass`, `bass`, `mids`, `highs`, `beat`, `onset` |

Internal analysis chain:
- `audiospectrumCHOP` (FFT size=512, output length=256, timeslice=ON)
- `mathCHOP` (gain=10) for spectrum normalization
- `analyzeCHOP` for RMS extraction
- `beatCHOP` for beat trigger detection
- Band extraction via `selectCHOP` + range filters:
  - `sub_bass`: 0-80 Hz
  - `bass`: 80-300 Hz
  - `mids`: 300-3000 Hz
  - `highs`: 3000 Hz+
- `mergeCHOP` combining all channels into `outCHOP`

### Effect baseCOMPs (43 total)

Each effect follows the same internal structure:

```
baseCOMP
├── in1 (inTOP)           # Camera feed input
├── glsl1 (glslTOP)       # Pixel shader
├── prominence (levelTOP) # Audio-driven opacity + beat flash
└── out1 (outTOP)         # Output to router
```

**Original effects (slots 0-20):**

| Slot | Operator Name | Label |
|------|---------------|-------|
| 0 | `fx_confetti_storm` | Confetti Particle Storm |
| 1 | `fx_thermal_posterize` | Thermal Posterize |
| 2 | `fx_fire_scanlines` | Fire Face Scanlines |
| 3 | `fx_echo_trail` | Echo Clone Trail |
| 4 | `fx_rainbow_echo` | Rainbow Echo Spiral |
| 5 | `fx_liquify_wave` | Liquify Wave Body |
| 6 | `fx_pixel_glitch` | Pixel Mosaic Glitch |
| 7 | `fx_datamosh` | Datamosh Freeze |
| 8 | `fx_rgb_explode` | RGB Channel Explosion |
| 9 | `fx_kaleidoscope` | Mirror Kaleidoscope |
| 10 | `fx_plasma_tentacles` | Plasma Tentacles |
| 11 | `fx_strobe_invert` | Strobe Flash Invert |
| 12 | `fx_pixelate_cascade` | Body Pixelate Cascade |
| 13 | `fx_glitch_tear` | Glitch Horizon Tear |
| 14 | `fx_radial_zoom` | Radial Zoom Tunnel |
| 15 | `fx_neon_skeleton` | Neon Skeleton Wire |
| 16 | `fx_solarize_pulse` | Color Solarize Pulse |
| 17 | `fx_triangle_shatter` | Triangle Mesh Shatter |
| 18 | `fx_feedback_spiral` | Feedback Spiral Zoom |
| 19 | `fx_matrix_rain` | Binary Rain Matrix |
| 20 | `fx_chromatic_double` | Chromatic Body Double |

**Mutation effects (slots 21-41):**

| Slot | Operator Name | Label |
|------|---------------|-------|
| 21 | `fx_mut_acid_confetti` | Acid Confetti |
| 22 | `fx_mut_xray_thermal` | X-Ray Thermal |
| 23 | `fx_mut_ice_scanlines` | Ice Scanlines |
| 24 | `fx_mut_echo_kaleidoscope` | Echo Kaleidoscope |
| 25 | `fx_mut_rainbow_shatter` | Rainbow Shatter |
| 26 | `fx_mut_liquify_vortex` | Liquify Vortex |
| 27 | `fx_mut_pixel_rain` | Pixel Rain |
| 28 | `fx_mut_datamosh_strobe` | Datamosh Strobe |
| 29 | `fx_mut_rgb_spiral` | RGB Spiral |
| 30 | `fx_mut_hyper_kaleidoscope` | Hyper Kaleidoscope |
| 31 | `fx_mut_plasma_web` | Plasma Web |
| 32 | `fx_mut_strobe_posterize` | Strobe Posterize |
| 33 | `fx_mut_cascade_mirror` | Cascade Mirror |
| 34 | `fx_mut_glitch_feedback` | Glitch Feedback |
| 35 | `fx_mut_radial_neon` | Radial Neon |
| 36 | `fx_mut_skeleton_fire` | Skeleton Fire |
| 37 | `fx_mut_negative_solarize` | Negative Solarize |
| 38 | `fx_mut_voronoi_feedback` | Voronoi Feedback |
| 39 | `fx_mut_double_spiral` | Double Spiral |
| 40 | `fx_mut_kanji_matrix` | Kanji Matrix |
| 41 | `fx_mut_chromatic_prism` | Chromatic Prism |

**Canon shards (slot 42):**

| Slot | Operator Name | Label |
|------|---------------|-------|
| 42 | `fx_canon_shards` | Canon Shards |

### 3-Layer Compositing Chain

```
effect_router (switchTOP, 43 inputs)  ─┐
                                        ├── blend_add1 (compositetTOP, add mode)
layer2_router (switchTOP, 43 inputs)  ─┘
                                              │
layer3_router (switchTOP, 43 inputs)  ────── blend_add2 (compositeTOP, add mode)
                                              │
                                        blend_level (levelTOP, output scaling)
                                              │
                                        main_output (windowCOMP, 1280x720)
```

All three routers have the same 43 effects wired. The auto-rotate system
picks 3 different random effects per switch event using
`random.sample(range(N), 3)`, assigning one to each router. The result is
always a layered composite of three independent visual streams.

### Control Layer

| Path | Type | Purpose |
|------|------|---------|
| `/project1/active_effect` | constantCHOP | Stores current state: `par.value0` = effect index, `par.value1` = auto-rotate toggle |
| `/project1/auto_rotate` | chopexecuteDAT | Auto-advance logic using `whileOn` callback (fires every frame). Switches on 1.5s interval or 5-beat threshold. |
| `/project1/keyboard_control` | keyboardinDAT | `focusselect='anywhere'`. Maps keys 0-9 to effect selection, Space to cycle. |

---

## GLSL Shader Architecture

### Common Header

All 43 GLSL shaders share a common header that defines audio uniforms and
utility functions:

```glsl
// uAudio  = (time, rms, bass, sub_bass)
// uAudio2 = (sub_bass, mids, highs, beat)

uniform vec4 uAudio;
uniform vec4 uAudio2;

out vec4 fragColor;

#define iTime   uAudio.x
#define energy  uAudio.y
#define bass    uAudio.z
#define sub     uAudio.w
#define mids    uAudio2.y
#define highs   uAudio2.z
#define beat    uAudio2.w
```

### Utility Functions

The header also provides:

- `hash(vec2)` — Pseudo-random hash for procedural noise
- `noise(vec2)` — Value noise via hash interpolation
- `fbm(vec2)` — 4-octave fractal Brownian motion

### Shader Structure

Each shader's `main()` function:

1. Samples the camera texture at `vUV.st` from `sTD2DInputs[0]`
2. Computes a body mask from luminance (`smoothstep` on luma)
3. Generates background elements (starfield, particles, noise)
4. Applies the effect transform driven by audio uniforms
5. Composites body + background + effect
6. Outputs via `TDOutputSwizzle(vec4(result, 1.0))`

### Prominence levelTOP

Inserted between `glsl1` and `out1` in each baseCOMP:

- **Opacity**: `0.6 + <band_channel> * 0.4` (expression mode)
  - Effects 0-13: bass-driven
  - Effects 14-28: mids-driven
  - Effects 29-42: highs-driven
- **Brightness**: `1.0 + beat * 0.3` (30% beat flash)

---

## Audio Analysis Pipeline

### TouchDesigner Path

```
audio_in (audiodeviceinCHOP)
    │
    ├── audiospectrumCHOP
    │     FFT size: 512
    │     Output: 256 frequency bins
    │     Timeslice: ON
    │
    ├── mathCHOP (gain=10, normalization)
    │
    ├── analyzeCHOP → rms channel
    │
    ├── beatCHOP → beat trigger channel
    │
    ├── selectCHOP → band filters
    │     sub_bass: bins 0-80 Hz
    │     bass:     bins 80-300 Hz
    │     mids:     bins 300-3000 Hz
    │     highs:    bins 3000+ Hz
    │
    └── mergeCHOP → outCHOP
          Channels: rms, sub_bass, bass, mids, highs, beat, onset
          All normalized to [0, 1]
```

### Python Standalone Path

`standalone/visuals.py` uses the `AudioFeatures` class:

- Live mic input via `sounddevice` (22050 Hz, 1024-sample blocks)
- File audio via `librosa` (pre-analyzed with `librosa.onset.onset_detect`,
  `librosa.beat.beat_track`, `librosa.feature.rms`)
- Band extraction via `scipy.signal.butter` bandpass filters
- Beat detection: rising edge detection (fires once, does not retrigger
  on steady state)
- All features normalized to [0, 1]

---

## Python Standalone Architecture

### Plugin Loader

The loader (`effects/__init__.py` contract) scans three directories:

1. `effects/` — 8 hand-coded built-in effects
2. `effects/ai_generated/` — 21 AI-generated effects
3. `effects/canonical/` — 2 vision-verified canonical effects

Files must export:

```python
EFFECT_META = {
    "name":        str,          # Display name
    "description": str,          # One-line description
    "key_audio":   list[str],    # e.g. ["bass", "onset"]
    "tags":        list[str],    # e.g. ["edges", "neon"]
    "order":       int,          # Sort key (1-8 built-in, 99 AI)
}

def fx_function(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
    """
    Args:
        frame: BGR uint8, shape (H, W, 3)
        af:    AudioFeatures with .energy, .bass, .mids, .highs,
               .sub_bass (float 0-1), .beat, .onset (bool),
               .onset_energy, .kick (float 0-1)
        state: Mutable dict persisted across frames
    Returns:
        BGR uint8, same shape as input
    """
```

Files starting with `_` or named `__init__.py` are skipped. Built-in
effects are loaded first (sorted by `order`), then AI-generated.

### Render Loop

```
┌─────────────────────────────┐
│ 1. Capture frame (webcam    │
│    or video file)           │
├─────────────────────────────┤
│ 2. Extract audio features   │
│    (mic or file, 22050 Hz)  │
├─────────────────────────────┤
│ 3. Route to active effect   │
│    (manual lock or rotate)  │
├─────────────────────────────┤
│ 4. Call fx_function(frame,  │
│    af, state)               │
├─────────────────────────────┤
│ 5. Display via cv2.imshow   │
│    (30 fps target)          │
└─────────────────────────────┘
```

### Auto-Rotate (Python)

- Cycle interval: configurable (default based on beat count or time)
- On beat threshold exceeded: switch to next effect in rotation
- Keyboard override: `1-9` locks to effect, `0` returns to auto

---

## MCP Bridge Protocol

### twozero MCP Bridge

- **Transport**: JSON-RPC 2.0 over HTTP
- **Endpoint**: `http://localhost:40404/mcp`
- **Method**: `tools/call`

### Request Format

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "td_execute_python",
        "arguments": {
            "code": "print(op('/project1/cam_in').par.device)"
        }
    }
}
```

### Response Format

```json
{
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "content": [
            { "type": "text", "text": "MacBook Pro Camera" }
        ]
    }
}
```

### Key Tools Used

| Tool | Purpose |
|------|---------|
| `td_execute_python` | Execute arbitrary Python inside TD |
| `td_create_operator` | Create an operator (type, name, parent, pars) |
| `td_set_operator_pars` | Set parameters on an existing operator |
| `td_write_dat` | Write text content to a DAT operator |
| `td_get_focus` | Get active project path |
| `td_get_errors` | Check for compile/runtime errors |
| `td_get_screenshot` | Capture current output |
| `td_get_perf` | Read FPS and performance counters |

### Retry Logic

All MCP calls use a retry wrapper with:
- 2 retries on failure
- 1-second delay between retries
- 120-second timeout per request

### Build Script Architecture

The build scripts (`tools/td_build_*.py`) follow a common pattern:

1. Define effect metadata (name, label, GLSL shader source)
2. For each effect:
   - Create baseCOMP container
   - Create inTOP, glslTOP, outTOP inside it
   - Write shader source to glslTOP
   - Wire input/output connectors
   - Set audio uniform expressions
3. Verify with `td_get_errors`
