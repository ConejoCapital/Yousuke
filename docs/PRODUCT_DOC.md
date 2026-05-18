> **ARCHIVED** — This is the original product specification written before
> the canonical analysis (Phase C) and the expansion from 8 to 43 effects.
> The current system is documented in [README.md](../README.md). Kept for
> historical reference.

# ¥ØUSUK€ Visual Extender — Product Document
**AI Psychosis Summit NYC | April 30, 2026**

---

## 1. Project Vision

Recreate and extend the visual language of ¥ØUSUK€ ¥UK1MAT$U's legendary Boiler Room Tokyo
× Super Dommune set — a system where every bass hit sculpts geometry, every transient fires a
particle burst, and every sustained note breathes through volumetric rings.

**Two delivery paths run in parallel:**
- **Python Standalone** → runs *right now* on any laptop (MacBook camera + mic or pre-recorded set)
- **TouchDesigner (via Hermes)** → GPU-accelerated, presentation-grade for the Summit

The Python engine is the demo-day fallback **and** the prototype for the TD network.

---

## 2. Visual Reference Catalog

Source video: **CxflYGeSx7Q** (¥ØUSUK€ — Boiler Room Tokyo × Super Dommune)

| # | Effect Name | Visual Description | Audio Trigger |
|---|-------------|-------------------|---------------|
| 1 | **Neon Contour** | Canny edges colorized cyan→magenta, layered bloom glow, thick lines pulse on bass | Line thickness 1→8px, hue rotate (bass) |
| 2 | **Particle Confetti** | Silhouette segmented via depth/mediapipe; confetti erupts from body boundary | Spawn rate × 10 on kick, velocity (bass energy) |
| 3 | **Voxel Explosion** | Frame voxelized into colored cubes; transient = explosion force pushes cubes outward | Explosion radius (onset energy), decay = gravity |
| 4 | **Volumetric Rings** | Concentric elliptical halos layered from center outward; ripple speed (mids) | Ring gap, travel speed (mid energy), new ring per beat |
| 5 | **Shard Burst** | Screen fractures into angular shards; each shard flies then resets to frame | Shard count 20→200 (kick amplitude), spread angle (bass) |
| 6 | **Gold Particle Rain** | Dense downward particle field, golden/amber palette, glitter on transients | Density (highs), temp shift warm→white (energy peak) |
| 7 | **Film Grain Base** | Heavy gaussian noise + radial vignette + slight desaturation; grain animated | Grain scale (overall RMS energy) |
| 8 | **Kanji Float** | Glitch kanji characters drift upward; opacity pulses; color = red/gold | Drift speed + spawn count (bass sub), opacity (beat) |

---

## 3. Tech Path Comparison

```
                      PYTHON STANDALONE          TOUCHDESIGNER (via Hermes)
─────────────────────────────────────────────────────────────────────────────
Run today?            ✓ Yes                      Requires TD install + Hermes
Visual quality        Good (OpenCV/ModernGL)     Superior (GPU, GLSL shaders)
Latency               ~20ms (pygame)             ~5ms (TD render pipeline)
Extensibility         Python ecosystem           TD operators + plugins
Live input            sounddevice (mic)          ASIO / Core Audio direct
Webcam               OpenCV (works now)          TD videoin TOP (better)
Best for              Demo fallback, prototyping  Summit main output
Setup time            5 min (setup.sh)           30 min (TD install + Hermes)
```

**Recommendation:** Run `setup.sh` now. Use Python standalone for April 30th if TD
isn't ready. If Hermes skill is confirmed, install TD (free license, derivative.ca)
and use `touchdesigner/README_FOR_HERMES.md` to build the .toe network Day 2.

---

## 4. System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AUDIO INPUT LAYER                           │
│   ┌──────────────┐          ┌──────────────────────────────┐   │
│   │  Live Mic /  │          │  Pre-recorded Set File       │   │
│   │  DJ Interface│          │  (MP3 / WAV via librosa)     │   │
│   └──────┬───────┘          └─────────────┬────────────────┘   │
│          └──────────────┬─────────────────┘                    │
│                         ▼                                       │
│              ┌─────────────────────┐                           │
│              │  FEATURE EXTRACTOR  │                           │
│              │  - RMS energy        │                           │
│              │  - Beat/tempo        │                           │
│              │  - Onset detection   │                           │
│              │  - Spectral bands    │                           │
│              │    (sub/bass/mid/hi) │                           │
│              └──────────┬──────────┘                           │
│                         ▼                                       │
│              ┌─────────────────────┐                           │
│              │  EFFECT ROUTER      │                           │
│              │  - Auto-rotate mode  │                           │
│              │  - Manual lock (1-8) │                           │
│              │  - Threshold logic   │                           │
│              └──────────┬──────────┘                           │
└──────────────────────────┼──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     EFFECT ENGINE                               │
│                                                                 │
│  [1] Neon Contour   [2] Particle     [3] Voxel Explode         │
│  [4] Vol. Rings     [5] Shard Burst  [6] Gold Rain             │
│  [7] Film Grain     [8] Kanji Float                            │
│                                                                 │
│  Each effect receives: frame + audio_features dict             │
└──────────────────────────┬──────────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     OUTPUT LAYER                                │
│   ┌────────────────┐    ┌────────────────┐    ┌─────────────┐  │
│   │  Window Mode   │    │  Webcam Mode   │    │  File Mode  │  │
│   │  (fullscreen)  │    │  (cam overlay) │    │  (pre-sync) │  │
│   └────────────────┘    └────────────────┘    └─────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Effect-by-Effect Technical Breakdown

### Effect 1: Neon Contour

**Python implementation:**
```python
# audio_features['bass'] → line thickness (1-8px)
# audio_features['energy'] → hue rotation (0-360)
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(gray, 50, 150)
thickness = int(1 + audio_features['bass'] * 7)
edges_dilated = cv2.dilate(edges, np.ones((thickness, thickness)))
# Apply colormap: COLORMAP_HSV + blue-shift
colored = cv2.applyColorMap(edges_dilated, cv2.COLORMAP_HSV)
# Bloom: blur + addWeighted
bloom = cv2.GaussianBlur(colored, (21, 21), 0)
result = cv2.addWeighted(colored, 1.0, bloom, audio_features['bass'] * 2.0, 0)
```

**TouchDesigner nodes:**
`Video In TOP → Edge TOP (Sobel) → Blur TOP → Level TOP (brightness=bass) → HSV Adjust TOP (hue=energy×360) → Composite TOP`

---

### Effect 2: Particle Confetti

**Python implementation:**
```python
# Particles: list of dicts {x, y, vx, vy, color, life}
# Spawn from webcam silhouette edges on kick
# audio_features['kick'] → spawn_rate multiplier
# audio_features['bass'] → velocity magnitude

if audio_features['kick'] > 0.7:
    for _ in range(int(50 * audio_features['kick'])):
        edge_px = random.choice(edge_pixels)
        particles.append({
            'x': edge_px[0], 'y': edge_px[1],
            'vx': random.gauss(0, audio_features['bass'] * 5),
            'vy': random.gauss(-3, audio_features['bass'] * 3),
            'color': random_neon_color(),
            'life': 1.0
        })
# Update + draw each particle
```

**TouchDesigner nodes:**
`Video In TOP → Threshold TOP → Feedback TOP (edge buffer) → GPU Particles COMP (spawn from edge texture) → Point Sprite TOP → Composite TOP`

---

### Effect 3: Voxel Explosion

**Python implementation:**
```python
# Downsample frame to voxel grid (e.g. 32x18 cells)
# On onset: apply radial force to each voxel
GRID_W, GRID_H = 32, 18
cell_w, cell_h = frame.shape[1] // GRID_W, frame.shape[0] // GRID_H

if audio_features['onset']:
    explosion_r = audio_features['onset_energy'] * 200
    # Push each cell outward from center
    for cell in voxels:
        dx = cell.x - center_x
        dy = cell.y - center_y
        dist = max(1, math.sqrt(dx*dx + dy*dy))
        force = explosion_r / dist
        cell.vx += dx/dist * force
        cell.vy += dy/dist * force

# Draw each voxel as colored rectangle at current displaced position
for cell in voxels:
    color = sample_frame_color(frame, cell.orig_x, cell.orig_y)
    cv2.rectangle(canvas, (int(cell.x), int(cell.y)),
                  (int(cell.x + cell_w), int(cell.y + cell_h)), color, -1)
    cell.vx *= 0.92  # friction
    cell.vy *= 0.92
    cell.vy += 0.3   # gravity
```

**TouchDesigner nodes:**
`Video In TOP → Reorder TOP (point cloud) → Instanced Geometry COMP (box per pixel) → Transform CHOP (force = onset CHOP) → Render TOP`

---

### Effect 4: Volumetric Rings

**Python implementation:**
```python
# Rings: list of {radius, opacity, speed}
# New ring spawned on each beat
# audio_features['mids'] → ring travel speed
# audio_features['beat'] → spawn new ring

if audio_features['beat']:
    rings.append({'r': 10, 'opacity': 1.0,
                  'speed': 2 + audio_features['mids'] * 8,
                  'color': mid_color(audio_features['mids'])})

for ring in rings[:]:
    cv2.ellipse(canvas, (cx, cy), (ring['r'], int(ring['r'] * 0.6)),
                0, 0, 360, ring['color'],
                thickness=max(1, int(3 * ring['opacity'])))
    ring['r'] += ring['speed']
    ring['opacity'] -= 0.015
    if ring['opacity'] <= 0:
        rings.remove(ring)
```

**TouchDesigner nodes:**
`Beat CHOP → Trigger CHOP → Feedback TOP (ring accumulator) → Circle SOP (radius=ring_r CHOP) → Level TOP (opacity=fade CHOP) → Composite TOP`

---

### Effect 5: Shard Burst

**Python implementation:**
```python
# Shards: Voronoi-like fracture of current frame
# audio_features['kick'] → trigger fracture + shard count
# Shards fly outward then fade back

if audio_features['kick'] > 0.8 and not shard_active:
    n_shards = int(20 + audio_features['kick'] * 180)
    shards = generate_voronoi_shards(frame, n_shards)
    shard_active = True

if shard_active:
    for shard in shards:
        # Translate shard polygon outward
        shard.translate(shard.vx, shard.vy)
        shard.vx *= 0.95
        shard.vy *= 0.95
        draw_polygon_with_texture(canvas, shard)
    if all(s.speed < 0.1 for s in shards):
        shard_active = False
```

**TouchDesigner nodes:**
`Video In TOP → Feedback TOP → GLSL TOP (Voronoi fracture shader, seed=kick CHOP) → Transform COMP (per-shard matrix) → Composite TOP`

---

### Effect 6: Gold Particle Rain

**Python implementation:**
```python
# Dense downward particle field, gold palette
# audio_features['highs'] → density multiplier
# audio_features['energy'] → color temperature (gold→white)

GOLD_BASE = (0, 165, 255)   # BGR gold
for _ in range(int(audio_features['highs'] * 200)):
    rain_particles.append({
        'x': random.randint(0, W), 'y': 0,
        'vy': random.uniform(2, 8),
        'brightness': random.uniform(0.5, 1.0),
        'size': random.randint(1, 3)
    })

for p in rain_particles[:]:
    t = audio_features['energy']
    color = lerp_color(GOLD_BASE, (255, 255, 255), t)
    cv2.circle(canvas, (int(p['x']), int(p['y'])), p['size'],
               tuple(int(c * p['brightness']) for c in color), -1)
    p['y'] += p['vy']
    if p['y'] > H:
        rain_particles.remove(p)
```

**TouchDesigner nodes:**
`Particle SOP (emit from top, gravity=+y) → Point Sprite TOP (color CHOP: highs→gold LUT) → Composite TOP`

---

### Effect 7: Film Grain Base

**Python implementation:**
```python
# Gaussian noise overlay + radial vignette + slight desaturation
# audio_features['energy'] → grain scale

grain_scale = 0.3 + audio_features['energy'] * 0.7
noise = np.random.normal(0, grain_scale * 60, frame.shape).astype(np.int16)
grained = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

# Vignette
Y, X = np.ogrid[:H, :W]
vignette = 1 - np.sqrt(((X - W/2)/(W/2))**2 + ((Y - H/2)/(H/2))**2) * 0.5
grained = (grained * vignette[:, :, np.newaxis]).astype(np.uint8)

# Slight desaturation
hsv = cv2.cvtColor(grained, cv2.COLOR_BGR2HSV).astype(np.float32)
hsv[:, :, 1] *= (1 - 0.3 * (1 - audio_features['energy']))
result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
```

**TouchDesigner nodes:**
`Noise TOP (type=Gaussian, amplitude=energy CHOP) → Composite TOP (add mode) → Level TOP (saturation=(1-0.3×energy)) → Vignette GLSL TOP`

---

### Effect 8: Kanji Float

**Python implementation:**
```python
# Pre-loaded list of kanji glyphs rendered to surfaces
# audio_features['sub_bass'] → spawn rate + drift speed
# audio_features['beat'] → opacity pulse

KANJI_LIST = ['電', '音', '波', '光', '火', '夢', '狂', '神', '血', '宇']

if audio_features['sub_bass'] > 0.5:
    for _ in range(int(audio_features['sub_bass'] * 3)):
        kanji_floats.append({
            'char': random.choice(KANJI_LIST),
            'x': random.randint(50, W-50), 'y': H,
            'vy': -(1 + audio_features['sub_bass'] * 4),
            'opacity': 1.0,
            'size': random.randint(24, 72),
            'color': random.choice([(0, 0, 180), (0, 140, 255)])  # red/gold BGR
        })

for k in kanji_floats[:]:
    # PIL draw for CJK font support
    img_pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, 'RGBA')
    alpha = int(255 * k['opacity'] * (0.7 + 0.3 * audio_features['beat']))
    draw.text((k['x'], k['y']), k['char'], font=kanji_font, fill=(*k['color'][::-1], alpha))
    canvas = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    k['y'] += k['vy']
    k['opacity'] -= 0.008
    if k['opacity'] <= 0:
        kanji_floats.remove(k)
```

**TouchDesigner nodes:**
`Text TOP (font=NotoSansCJK, string=kanji_chop CHOP) → Transform TOP (y+=bass CHOP) → Level TOP (opacity=beat CHOP) → Composite TOP`

---

## 6. Hermes Prompting Guide

Use these prompts in order with the Hermes TouchDesigner skill.

### Prompt 1: Project scaffold
```
Create a new TouchDesigner project with:
- A Video In TOP named "cam_in" capturing the default webcam
- An Audio Device In CHOP named "audio_in" capturing default input
- A base container called "audio_analysis" that outputs 6 channels:
  rms, bass (0-300hz), mids (300-3000hz), highs (3000hz+), beat (0/1), onset (0-1)
- Wire audio_in into audio_analysis
```

### Prompt 2: Audio analysis network
```
Inside the audio_analysis base, build:
1. Analyze CHOP on audio_in → outputs RMS
2. Audio Spectrum CHOP → bands 0-300, 300-3000, 3000-20000
3. Beat CHOP (tempo detect) → beat trigger channel
4. Math CHOP to normalize all channels 0-1
5. Export these as out channels: rms, bass, mids, highs, beat, onset
```

### Prompt 3: Effect 1 — Neon Contour
```
Create a container called "fx_neon_contour":
- Input: cam_in TOP
- Edge TOP (Sobel method)
- Blur TOP (size driven by bass CHOP × 20)
- HSV Adjust TOP (hue rotation = energy_chop × 360)
- Level TOP (brightness = 0.5 + bass × 0.5)
- Composite TOP (over mode, multiply = 1.2)
- Output: rendered neon contour frame
```

### Prompt 4: Effect 2 — Particle Confetti
```
Create a container called "fx_particles":
- Threshold the cam_in edge texture to get silhouette boundary
- GPU Particles COMP:
  - Spawn source: edge texture pixels
  - Spawn rate: bass_chop × 500 per frame
  - Initial velocity: random ± (bass × 8)
  - Color: random from neon palette LUT
  - Lifetime: 60 frames
- Composite particles over cam_in
```

### Prompts 5-8: Repeat pattern for remaining effects
Use the technical specs in Section 5 above. Each effect follows:
`"Create a container called fx_[name] that implements [description]. Drive [param] with [chop_channel] × [scale]"`

### Prompt 9: Effect router
```
Create a Switch TOP called "effect_router":
- 8 inputs (one per fx_ container)
- index driven by a Constant CHOP named "active_effect" (int 0-7)
- Add a CHOP Execute DAT that auto-advances active_effect when:
  rms > 0.8 for 4 seconds OR beat_count > 32
```

### Prompt 10: Output
```
Wire effect_router → Window COMP (fullscreen, monitor 2 if available)
Add a Perform Mode button
Save as visuals.toe
```

---

## 7. MVP Checklist — April 30th

### Must-have (Day 1)
- [ ] `bash setup.sh` completes without errors
- [ ] `python standalone/visuals.py --mode webcam --audio mic` opens window with neon contour
- [ ] All 8 effects render (can be janky, must be visible)
- [ ] Audio reactivity confirmed on at least 3 effects (kick triggers visible change)
- [ ] Keyboard 1-8 switches effects
- [ ] Auto-rotate mode cycles effects
- [ ] Demo script timed at < 5 minutes

### Should-have (Day 2)
- [ ] TouchDesigner .toe network running (via Hermes)
- [ ] `reference/video.mp4` downloaded for analysis
- [ ] Framerate ≥ 30fps on MacBook
- [ ] Webcam + mic latency < 100ms perceptually

### Nice-to-have
- [ ] Pre-recorded set file sync (`--audio reference/audio.mp3`)
- [ ] Custom font for kanji
- [ ] Smooth effect transitions (crossfade ~500ms)
- [ ] BPM display overlay

---

## 8. Quick Start

```bash
# Install everything + download video + pull frames
bash ~/Desktop/Yousuke/setup.sh

# Run the visual engine RIGHT NOW (webcam + mic)
python ~/Desktop/Yousuke/standalone/visuals.py --mode webcam --audio mic

# Run with pre-recorded audio (after setup.sh)
python ~/Desktop/Yousuke/standalone/visuals.py --mode file --audio ~/Desktop/Yousuke/reference/audio.mp3
```

**Keyboard controls:**
- `1-8` — Lock to effect
- `0` — Return to auto-rotate
- `SPACE` — Pause
- `L` — Load audio file mid-session
- `Q` / `ESC` — Quit

---

---

## 9. Canonical Effects Catalog

### Purpose

`analyze_video.py` samples the full reference video at regular intervals, extracts 19-float
visual feature vectors per frame, clusters them with k-means, and saves a representative
frame + JSON entry for each cluster. The result is a machine-generated catalog of every
distinct visual style that appears in the set — far more than the 8 hand-coded effects.

### Pipeline (5 stages)

1. **Frame sampling** — seek to every N seconds via `cv2.CAP_PROP_POS_MSEC`, save `(timestamp, frame)` pairs
2. **Feature extraction** — per frame: 15 dominant color floats (k-means k=5 on 64×64), edge density, brightness, saturation mean, color variance (19 floats total)
3. **K-means clustering** — `sklearn.cluster.KMeans` on `StandardScaler`-normalized feature matrix
4. **Representative selection** — frame with minimum L2 distance to cluster centroid
5. **Catalog build** — JSON + JPEG saved to `reference/`

### Usage

```bash
# Default: 10s interval, 20 clusters
python analyze_video.py

# High-resolution scan: 5s interval, 30 clusters
python analyze_video.py --interval 5 --clusters 30

# Custom paths
python analyze_video.py --video /path/to/set.mp4 --output /path/to/effects.json
```

### Output JSON schema

```json
{
  "source_video": "https://youtu.be/CxflYGeSx7Q",
  "n_clusters": 20,
  "n_frames_sampled": 540,
  "canonical_effects": [{
    "id": 0,
    "name": "Neon Edge #00",
    "category": "Neon Edge",
    "timestamps": [120.0, 240.5],
    "representative_timestamp": 120.0,
    "representative_frame_path": "reference/canonical_effects_frames/cluster_00.jpg",
    "visual_signature": {
      "dominant_hex": "#00e6ff",
      "edge_density": "high",
      "brightness": "dark",
      "saturation": "colorful"
    },
    "inferred_audio_mapping": "edge_density → bass; hue → energy",
    "cluster_size": 3
  }]
}
```

### Linking to AI generation

Any canonical entry can seed a new effect:

```bash
python generate_effect.py --from-canonical reference/canonical_effects.json --id 7
```

---

## 10. AI Effect Generation

The `generate_effect.py` script uses the Claude API to write new, runnable effect functions
in the plugin format. Generated files are saved to `effects/ai_generated/` and auto-loaded
next time `visuals.py` starts.

### Setup

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```

If the key is not set, the script prints setup instructions and exits with code 1.

### Four generation modes

**1. From a video frame image**
```bash
python generate_effect.py --from-frame reference/frames/frame_05.jpg --name "Plasma Web"
```
The frame is base64-encoded and sent to Claude as a vision input. The effect is
inspired by the visual style in the frame.

**2. From a text description**
```bash
python generate_effect.py --describe "glitchy RGB channel separation with scan lines"
python generate_effect.py --describe "geometric kaleidoscope that pulses on bass hits"
```

**3. Extend an existing effect**
```bash
python generate_effect.py --extend neon_contour
python generate_effect.py --extend kanji_float --name "Kanji Storm"
```
Feeds the existing effect's source code to Claude; outputs a variation that changes
at least 3 visual aspects.

**4. From canonical catalog**
```bash
python generate_effect.py --from-canonical reference/canonical_effects.json --id 7
```
Uses the visual signature and inferred audio mapping from the catalog entry as the seed.

### Validation pipeline

Every generated effect passes 4 checks before being saved:
1. **Syntax** — `ast.parse()` (catches malformed Python)
2. **Required exports** — `EFFECT_META` dict + `fx_function` callable must be present
3. **Test run** — `fx_function(np.zeros((480,640,3)), MockAF(), {})` must return `(480,640,3) uint8`
4. **Shape match** — output shape must equal input shape

On validation failure, the error and prior code are fed back to Claude for up to 2 retries.

### Model selection

```bash
# Default (highest quality, slower)
python generate_effect.py --describe "..." --model claude-opus-4-7-20250626

# Faster/cheaper alternative
python generate_effect.py --describe "..." --model claude-sonnet-4-5
```

### Output location

```
effects/ai_generated/effect_YYYYMMDD_HHMMSS_slug.py
```

The file is auto-discovered by `visuals.py`'s plugin loader at next startup —
no configuration needed.

---

*Generated for: AI Psychosis Summit NYC, April 30, 2026*
*Reference: ¥ØUSUK€ ¥UK1MAT$U — Boiler Room Tokyo × Super Dommune (CxflYGeSx7Q)*
