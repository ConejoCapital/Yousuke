# TouchDesigner Network — Instructions for Hermes
## ¥ØUSUK€ Visual Extender | AI Psychosis Summit NYC | April 30, 2026

This document contains exact prompts to give Hermes to build the complete .toe network.
Run these prompts **in order**. Each prompt builds on the previous.

---

## Prerequisites

1. Download TouchDesigner (free): https://derivative.ca/download
2. Install the Hermes TouchDesigner skill in Claude Code
3. Open a new empty project in TouchDesigner
4. Have this file open in a second window for reference

---

## Prompt Sequence

### PROMPT 1 — Project scaffold + audio input
Paste this verbatim into Hermes:

```
Create a new TouchDesigner project with this structure:
1. A Video In TOP named "cam_in" capturing the default webcam at 1280x720
2. An Audio Device In CHOP named "audio_in" using the default audio input device
3. A Container COMP named "audio_analysis" with these output channels:
   - rms (0-1, overall loudness)
   - sub_bass (0-80Hz energy, 0-1)
   - bass (80-300Hz energy, 0-1)
   - mids (300-3000Hz energy, 0-1)
   - highs (3000Hz+ energy, 0-1)
   - beat (0 or 1, beat detection trigger)
   - onset (0-1, transient onset strength)
4. Wire audio_in into audio_analysis
5. Name the output Out CHOP "audio_out"
```

---

### PROMPT 2 — Audio analysis internals
```
Inside the audio_analysis Container COMP, build this signal chain:
1. Audio Spectrum CHOP connected to the input:
   - Output: magnitude
   - Window: hann
2. Math CHOP to extract 5 frequency bands using the Spectrum output:
   - Channel 1: average of bins 0-80Hz → name "sub_bass"
   - Channel 2: average of bins 80-300Hz → name "bass"
   - Channel 3: average of bins 300-3000Hz → name "mids"
   - Channel 4: average of bins 3000-20000Hz → name "highs"
   - Channel 5: overall RMS → name "rms"
3. Analyze CHOP set to RMS on the audio input → name output "rms"
4. Beat CHOP on the audio input → channel "beat"
5. Trigger CHOP detecting onset (threshold 0.3) → channel "onset"
6. Merge CHOP combining all 7 channels
7. Math CHOP to normalize all channels to 0-1 range
8. Out CHOP with all 7 channels
```

---

### PROMPT 3 — Effect 1: Neon Contour
```
Create a Container COMP named "fx_neon_contour" with:
- Input: cam_in TOP
- Edge TOP (method: Sobel, post-process: none) → wire from cam_in
- Blur TOP (size: driven by bass channel from audio_out × 15, min 2)
- HSV Adjust TOP:
  - Hue rotation: rms × 180 degrees
  - Saturation boost: 1.5
- Level TOP:
  - Brightness: 0.3 + bass × 0.7
  - Contrast: 1.2
- Composite TOP (over mode, multiply factor 1.4) blending edges over dark cam_in
- Output: composite result
Wire audio channels: audio_out/bass → blur size, audio_out/rms → hue rotation
```

---

### PROMPT 4 — Effect 2: Particle Confetti
```
Create a Container COMP named "fx_particles" with:
- Input: cam_in TOP
- Threshold TOP (threshold: 0.5) to create silhouette from cam_in
- Edge TOP on threshold result to get boundary pixels
- GPU Particles COMP:
  - Spawn source: edge texture (boundary pixels)
  - Spawn rate: bass_chop × 400 particles per second
  - Initial velocity: random direction, magnitude = bass × 8
  - Color: random from palette [cyan(0,255,255), magenta(255,0,255), yellow(255,255,0)]
  - Lifetime: 2.5 seconds
  - Gravity: 0.3 (downward)
- Point Sprite TOP rendering the particles
- Composite TOP: particles over dark cam_in (add mode, 0.3 opacity on cam)
Wire: audio_out/bass → spawn rate and velocity, audio_out/beat → trigger burst
```

---

### PROMPT 5 — Effect 3: Voxel Explosion
```
Create a Container COMP named "fx_voxel" with:
- Input: cam_in TOP
- Reorder TOP (32×18 grid) downsampling cam_in to a point cloud texture
- Instanced Geometry COMP:
  - Geometry: Box SOP (size: 1)
  - Instance count: 32×18 = 576
  - Position: from grid texture (32×18 sampling)
  - Color: sampled from cam_in at each grid position
  - Scale: 0.95
- When onset fires: apply radial outward force to all instances
  (force = onset_energy × 300 / distance_from_center)
- Physics: friction 0.92 per frame, gravity 0.3
- Return-to-origin spring: 5% per frame
- Render TOP → Camera COMP (orthographic, fitted to frame)
Wire: audio_out/onset → explosion force, audio_out/onset → force magnitude
```

---

### PROMPT 6 — Effect 4: Volumetric Rings
```
Create a Container COMP named "fx_rings" with:
- Input: cam_in TOP (used as background at 0.2 opacity)
- Beat CHOP from audio_out → Trigger CHOP
- Feedback TOP (accumulates ring layers with 0.985 decay)
- On each beat trigger: composite a new ellipse layer:
  - Circle SOP with radius starting at 10, traveling outward at mids × 8 px/frame
  - Ellipse aspect ratio: 0.6 (width:height)
  - Color: lerp from blue to cyan based on mids energy
  - Thickness: 2 + bass × 4
  - Center: frame center
- Render rings into Feedback TOP
- Composite TOP: rings over dark cam_in (add mode)
Wire: audio_out/beat → trigger new ring, audio_out/mids → ring speed + color
```

---

### PROMPT 7 — Effect 5: Shard Burst
```
Create a Container COMP named "fx_shards" with:
- Input: cam_in TOP
- GLSL TOP implementing Voronoi fracture shader:
  - On kick trigger: generate N random Voronoi seed points (N = kick × 200, min 20)
  - Each Voronoi cell gets a transform: position, rotation, scale
  - Cell displacement: radial outward from center, speed = kick amplitude × 8
  - Blend back to original as velocity decays (friction 0.94/frame)
  - Shader uniforms: kick_strength (float), seed (float), frame count (int)
- GLSL MAT with the shard fragment shader
- Render TOP
Wire: audio_out/kick → kick_strength uniform, audio_out/beat → seed randomize
```

---

### PROMPT 8 — Effect 6: Gold Particle Rain
```
Create a Container COMP named "fx_gold_rain" with:
- Input: cam_in TOP (at 0.4 opacity background)
- Particle SOP:
  - Emitter: line across top of frame (full width)
  - Emission rate: highs × 300 particles/second
  - Initial velocity: downward (y = -3 to -8, random), no horizontal spread
  - Force: gravity 0.5
  - Lifetime: 3 seconds
- Point Sprite TOP:
  - Color: lerp from gold(1.0, 0.65, 0.0) to white(1,1,1) based on rms
  - Size: 2-6px random
  - Brightness: 0.5-1.0 random per particle
- Composite TOP: add mode over dark cam_in
Wire: audio_out/highs → emission rate, audio_out/rms → color temperature
```

---

### PROMPT 9 — Effect 7: Film Grain
```
Create a Container COMP named "fx_grain" with:
- Input: cam_in TOP
- Noise TOP (type: Gaussian, amplitude: 0.3 + rms × 0.5, monochrome)
- Composite TOP: cam_in + noise (add mode, noise at rms × 0.4 opacity)
- GLSL TOP for radial vignette:
  - formula: color *= 1.0 - length(uv - 0.5) * 0.8
- HSV Adjust TOP: saturation = 0.5 + rms × 0.5 (desaturate on low energy)
- Level TOP: slight contrast boost (1.1)
Wire: audio_out/rms → noise amplitude and saturation
```

---

### PROMPT 10 — Effect 8: Kanji Float
```
Create a Container COMP named "fx_kanji" with:
- Input: cam_in TOP (at 0.5 opacity)
- Text TOP array (10 instances) with:
  - Font: Hiragino Sans GB or NotoSansCJK (must support CJK characters)
  - Characters: random selection from [電音波光火夢狂神血宇]
  - Spawn position: random X, bottom of frame (Y = -1 in UV space)
  - Drift: upward velocity = 0.01 + sub_bass × 0.04 per frame
  - Color: random between red(1,0,0) and gold(1,0.65,0)
  - Size: 28-80px random
  - Opacity: decays 0.008/frame, pulse on beat (+30% opacity)
- Feedback TOP to accumulate floating characters (0.992 decay)
- Composite TOP: kanji over cam_in (over mode)
Wire: audio_out/sub_bass → spawn rate + velocity, audio_out/beat → opacity pulse
```

---

### PROMPT 11 — Effect router
```
Create an effect routing system:
1. Switch TOP named "effect_router" with 8 inputs:
   - Input 0: fx_neon_contour output
   - Input 1: fx_particles output
   - Input 2: fx_voxel output
   - Input 3: fx_rings output
   - Input 4: fx_shards output
   - Input 5: fx_gold_rain output
   - Input 6: fx_grain output
   - Input 7: fx_kanji output
2. Constant CHOP named "active_effect" (integer, range 0-7, default 0)
3. Connect active_effect → Switch TOP index input
4. CHOP Execute DAT named "auto_rotate" with this Python script:
   - Track: time since last switch, beat count
   - Auto-advance active_effect when:
     * rms > 0.8 for 4 consecutive seconds, OR
     * beat count > 32 since last switch
   - Reset beat count on switch
5. Keyboard In DAT for manual control:
   - Keys 1-8: set active_effect to 0-7 and lock (disable auto_rotate)
   - Key 0: unlock (re-enable auto_rotate)
   - Key Space: toggle pause
```

---

### PROMPT 12 — Output + final wiring
```
Complete the network:
1. Wire effect_router output → Window COMP:
   - Name: "main_output"
   - Monitor: secondary monitor if available, otherwise primary
   - Resolution: match input (1280x720 or 1920x1080)
   - Full screen: yes
2. Add Performance COMP for frame rate monitoring
3. Add Info DAT showing active effect name and audio levels
4. Save the project as: ~/Desktop/Yousuke/visuals.toe
5. Add a README annotation in the network explaining the signal flow:
   "Audio In → Analysis → Effect Engine → Switch → Output"
```

---

## Node Architecture Summary

```
audio_in (Audio Device In CHOP)
    └── audio_analysis (Container COMP)
            ├── sub_bass channel
            ├── bass channel
            ├── mids channel
            ├── highs channel
            ├── rms channel
            ├── beat channel
            └── onset channel
                    │
                    ├── fx_neon_contour ──┐
                    ├── fx_particles ─────┤
                    ├── fx_voxel ─────────┤
                    ├── fx_rings ─────────┼── effect_router (Switch TOP) → Window COMP
                    ├── fx_shards ────────┤
                    ├── fx_gold_rain ─────┤
                    ├── fx_grain ─────────┤
                    └── fx_kanji ─────────┘

cam_in (Video In TOP) ──────── feeds into all fx_ containers

active_effect (Constant CHOP) ── controls Switch TOP index
auto_rotate (CHOP Execute DAT) ── updates active_effect automatically
```

---

## Connecting the Hermes TouchDesigner Skill

1. Open Claude Code
2. Type `/hermes` or invoke the Hermes skill
3. Tell Hermes: *"I want to build a TouchDesigner .toe network. I have a reference document at ~/Desktop/Yousuke/touchdesigner/README_FOR_HERMES.md — please start with Prompt 1 and build the complete network."*
4. Follow Hermes' instructions for each prompt in sequence
5. After all 12 prompts: test with webcam + mic, then save as `visuals.toe`

---

## Testing Checklist

After Hermes builds the network:
- [ ] Webcam frame appears in cam_in TOP
- [ ] Audio levels respond in audio_analysis CHOP (move/clap near mic)
- [ ] All 8 fx_ containers produce visible output
- [ ] Effect router switches between effects
- [ ] Keys 1-8 lock to each effect
- [ ] Key 0 returns to auto-rotate
- [ ] Beat channel fires on tempo
- [ ] Window COMP shows fullscreen output

---

*Generated for: AI Psychosis Summit NYC, April 30, 2026*
*Reference: ¥ØUSUK€ ¥UK1MAT$U — Boiler Room Tokyo × Super Dommune*
