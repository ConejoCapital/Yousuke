# Process — How AI Agents Built a Live Visual System

This document narrates the complete build process of the Yousuke
audio-reactive visual system, from initial concept to production-ready
deployment. It is both a technical record and a reflection on what worked,
what failed, and what was learned about AI-human collaboration in creative
technical work.

---

## Table of Contents

1. [Motivation](#1-motivation)
2. [Phase A: Project Scaffolding & Python Standalone](#2-phase-a-project-scaffolding--python-standalone)
3. [Phase B: Test Scaffold & Engine Hardening](#3-phase-b-test-scaffold--engine-hardening)
4. [Phase C: Algorithmic Video Analysis](#4-phase-c-algorithmic-video-analysis)
5. [Phase C.5: Human-in-the-Loop Frame Curation](#5-phase-c5-human-in-the-loop-frame-curation)
6. [Phase D: AI Effect Generation & Extension](#6-phase-d-ai-effect-generation--extension)
7. [Phase E: TouchDesigner Construction via AI Agents](#7-phase-e-touchdesigner-construction-via-ai-agents)
8. [Phase F: Multi-Camera Support & Production Polish](#8-phase-f-multi-camera-support--production-polish)
9. [Lessons Learned](#9-lessons-learned)

---

## 1. Motivation

The central research question:

> Can AI agents extract a human artist's live visual identity from video,
> reproduce it in TouchDesigner, and generate novel extensions of that
> identity?

The subject: YOUSUKE YUKIMATSU's Boiler Room Tokyo x Super Dommune set
— a 93-minute live performance whose visuals (by Bridge) define a specific
aesthetic language. The goal was not to build generic audio-reactive
visuals, but to capture *this particular artist's* visual identity and
extend it.

The venue: AI Psychosis Summit NYC, April 30, 2026. The system needed to
run live, in real time, processing audio input and driving visual output
on a projector.

The tools: Claude Opus 4.7 (Anthropic) for vision analysis and code
generation, Hermes (Nous Research) for autonomous TouchDesigner
construction, twozero MCP bridge by 404.zero for TD communication.

---

## 2. Phase A: Project Scaffolding & Python Standalone

The first phase established the dual-delivery architecture:

- **Python standalone** (`standalone/visuals.py`) — a complete visual engine
  using OpenCV, sounddevice, and librosa that runs on any laptop with a
  webcam and microphone
- **TouchDesigner network** — the GPU-accelerated production path, to be
  built via AI agents in a later phase

Eight effects were hand-coded based on watching the Boiler Room set:

1. Neon Contour (Canny edges + HSV colormap + bloom)
2. Particle Confetti (silhouette edge spawning)
3. Voxel Explosion (pixelated grid displacement)
4. Volumetric Rings (concentric expanding halos)
5. Shard Burst (Voronoi fracture)
6. Gold Particle Rain (golden downward cascade)
7. Film Grain (noise + vignette + desaturation)
8. Kanji Float (drifting CJK glyphs)

These effects were designed from memory and intuition after watching the
set. They would later prove to be substantially incorrect, but they
served their purpose: establishing the plugin architecture, audio feature
extraction pipeline, and render loop that the AI-generated effects would
later plug into.

The plugin contract was defined early and never changed:

```python
EFFECT_META = {
    "name": str, "description": str,
    "key_audio": list[str], "tags": list[str], "order": int,
}

def fx_function(frame, af, state) -> np.ndarray:
    # frame: BGR uint8, af: AudioFeatures, state: mutable dict
    # returns: BGR uint8, same shape
```

---

## 3. Phase B: Test Scaffold & Engine Hardening

Before generating any AI content, the system needed a comprehensive test
suite to validate that generated effects would work correctly.

**96 tests were written across 7 test files** (the Phase B scaffold; the
suite has since grown to 234 tests as effects were added):

| File | Tests | Coverage |
|------|-------|----------|
| `test_smoke.py` | 12 | Import checks, basic pipeline |
| `test_audio_features.py` | 11 | Band extraction vs pure sine waves |
| `test_plugin_loader.py` | 7 | Plugin discovery, malformed file handling |
| `test_effects_render.py` | 40 | All effects render, produce visible output, don't mutate input |
| `test_perf.py` | 9 | Per-effect latency benchmarks |
| `test_analyze_video.py` | 7 | Feature extraction determinism |
| `test_generate_effect.py` | 10 | Validation pipeline correctness |

**Two critical performance bugs were found and fixed during testing:**

1. **Shard Burst** — O(n^2) full-frame mask allocation per shard. Fixed
   with vectorized rotation and single `fillPoly` + `bitwise_and`.
   42.5ms -> 1.4ms per frame (-97%).

2. **Film Grain** — Full-resolution Gaussian RNG + HSV roundtrip. Fixed
   with half-resolution uniform RNG + `cv2.resize` + `addWeighted`
   desaturation (no HSV conversion). 35ms -> 7.8ms per frame (-78%).

After optimization, the slowest effect (Kanji Float, 11.72ms) ran at an
effective 85 FPS — well within the 33.3ms budget for 30 FPS.

---

## 4. Phase C: Algorithmic Video Analysis

### The Pipeline

`pipeline/analyze_video.py` was built to objectively analyze the source video's
visual language. It operates in 5 stages:

1. **Frame sampling** — Seek to every 3 seconds, extract 1,871 frames
   from the 93-minute set
2. **Feature extraction** — Per frame: 19-float vector (15 dominant color
   floats via k-means on 64x64, edge density, brightness, saturation
   mean, color variance)
3. **K-means clustering** — `sklearn.cluster.KMeans` (k=40) on
   `StandardScaler`-normalized feature matrix
4. **Representative selection** — Frame with minimum L2 distance to
   cluster centroid
5. **Catalog build** — JSON with visual signatures + representative
   frame JPEGs saved to `reference/`

### The Canonical Correction

The clustering analysis produced a finding that fundamentally changed the
project: **7 of 8 hand-guessed effects were wrong.**

The actual visual grammar of the YOUSUKE YUKIMATSU set is:

- **Chiaroscuro-bloom-chromatic** with soft, indistinct light-boundary
  edges
- Narrow palettes (magenta/pink/white/black dominant)
- Heavy bloom and diffusion, not sharp contours
- Chromatic aberration at luminance boundaries
- Motion blur and slow-shutter ghosting

It is **not**:

- Sharp TRON-cyberpunk contour outlines (Neon Contour was wrong)
- Confetti particle spawning (doesn't appear in the set)
- Gold rain cascades (gold colors appear only as LED reflections)
- Drawn concentric ring shapes (the "rings" were feedback echoes)
- Voronoi fracture patterns (the actual shards are pixel-sort extrusions)
- Kanji overlays (no CJK text in the set; only the broadcast watermark)
- Voxelized grids (no pixelated block look anywhere)

The k-means `edge_density: high` metric had been detecting luminance
contrast boundaries between bloomed highlights and crushed blacks — not
actual edge-detected contours. This distinction is subtle but critical:
the set's visual identity lives in the *diffusion* of light, not in its
*sharp delineation*.

The 7 consolidated canonical techniques:

1. Chiaroscuro magenta bloom (~45% of set)
2. Chiaroscuro cyan/cool bloom (~12%)
3. Crushed-black silhouette (~15%)
4. Hazy low-contrast dream (~3%)
5. Dark atmospheric macro (~4%)
6. Pixel-sort radial shards (~3%)
7. Feedback echo tunnel (~7%)

Full catalog: [reference/CANONICAL_CATALOG.md](../reference/CANONICAL_CATALOG.md)

---

## 5. Phase C.5: Human-in-the-Loop Frame Curation

While algorithmic clustering provided statistical accuracy, it missed
aesthetic intent. The operator (the human) took screenshots of specific
frames from the set that captured the *feeling* of the visual identity —
mood, atmosphere, emotional weight — qualities that a 19-float feature
vector cannot encode.

These screenshots were fed directly to Claude Opus 4.7 via the Hermes
harness as vision input. The AI analyzed each frame's visual properties
(luminance distribution, color palette, edge characteristics, bloom
behavior) and generated GLSL shaders or Python effects that reproduced
the style.

**This hybrid approach dramatically improved output quality** compared to
either method alone:

- **Clustering alone** produced statistically representative effects that
  lacked aesthetic soul — they captured the *average* but missed the
  *exceptional*
- **Human selection alone** would have been limited by the operator's
  ability to articulate visual properties in technical terms
- **Together** they produced a visual vocabulary that neither could
  achieve alone: the human curates intent, the AI executes with
  precision; the AI catches statistical patterns the human misses, the
  human catches emotional resonance the AI misses

This is the central finding of the project: AI-driven visual identity
extraction works best as a collaboration, not an automation.

---

## 6. Phase D: AI Effect Generation & Extension

### The Generation Pipeline

`pipeline/generate_effect.py` uses Claude Opus 4.7 to write runnable effect code.
It supports four modes:

1. **From frame** — Vision input: a screenshot is sent as a base64-encoded
   image alongside the plugin contract spec
2. **From description** — Text prompt describing the desired visual
3. **Extend** — An existing effect's source code is sent for variation
4. **From canonical** — A catalog entry's visual signature + representative
   frame seeds the generation

### Validation

Every generated effect passes through a 4-step validation pipeline before
being saved to disk:

1. `ast.parse()` — Catches syntax errors
2. Export check — `EFFECT_META` dict and `fx_function` callable must exist
3. Test run — The function is called with a zero frame and mock audio
   features; must return a `(480, 640, 3)` uint8 array
4. Shape match — Output shape must equal input shape

On failure, the error message and rejected code are fed back to the model
for up to 2 automatic retries. This self-correcting loop significantly
improved the first-pass success rate.

### The Extension Strategy

**First pass — 21 original effects:** Generated to faithfully reproduce
the source material's visual identity as characterized by the canonical
analysis and human frame curation.

**Second pass — 21 mutation effects:** The harness was instructed to
produce variations of the originals. Each mutation shares the visual DNA
of its parent effect but introduces controlled variations — different
color mappings, altered displacement functions, inverted masks, layered
feedback. This doubled the visual vocabulary while maintaining aesthetic
coherence.

The mutations are not random perturbations. Each was prompted with the
parent effect's GLSL source and explicit instructions to preserve the
core visual technique while varying at least 3 specific aspects.

### Output

- 21 AI-generated Python effects in `effects/ai_generated/`
- 2 canonical Python effects in `effects/canonical/`
- 42 GLSL shaders (21 original + 21 mutations) embedded in TD build scripts

---

## 7. Phase E: TouchDesigner Construction via AI Agents

### The Agent Stack

- **Hermes Agent** (Nous Research) with TouchDesigner skill providing
  36 native tools
- **twozero MCP bridge** (404.zero + setupdesign) — JSON-RPC server on
  `localhost:40404` that translates MCP tool calls into TouchDesigner
  Python API calls

### Build Sequence

The TD network was constructed through a series of Python scripts that
communicate with TD via the MCP bridge:

1. **`td_build_effects.py`** — Creates 21 baseCOMPs, each containing an
   inTOP, glslTOP (with the full pixel shader source), and outTOP. Wires
   camera input and sets audio uniform expressions. 1,347 lines of GLSL
   across 21 shaders.

2. **`td_build_mutations.py`** — Same architecture, 21 additional
   baseCOMPs with mutation shader variants. 1,358 lines of GLSL.

3. **`td_wire_all.py`** — Disconnects all existing router inputs, wires
   camera to each mutation's input connector, then wires all 43 effect
   outputs to the `effect_router` switchTOP in order (slots 0-20 originals,
   21-41 mutations, 42 canon_shards). Also creates and wires
   `layer2_router` and `layer3_router` for the 3-layer compositing chain.

4. **`td_add_prominence.py`** — Inserts a `levelTOP` named "prominence"
   between the glslTOP and outTOP inside each baseCOMP. Sets opacity to a
   frequency-band expression (bass for 0-13, mids for 14-28, highs for
   29-42) and brightness to a beat flash expression (+30% on beat detect).

5. **`td_update_rotation.py`** — Writes the auto-rotate chopexecuteDAT
   script with aggressive parameters: 1.5s switch interval, 5-beat
   threshold, `random.sample(range(N), 3)` for per-switch selection of
   3 different effects across the 3 compositing layers.

### The Compositing Architecture

The 3-layer system emerged from the creative desire for visual density.
A single effect at a time felt sparse; three effects additively composited
created the layered, overwhelming visual presence that matched the source
material's aesthetic.

```
effect_router  ──┐
                  ├── blend_add1 ──┐
layer2_router  ──┘                 ├── blend_add2 ── blend_level ── main_output
layer3_router  ────────────────────┘
```

### Verification

After each build phase:
- `td_get_errors(recursive=true)` — Must return empty
- `td_get_perf` — FPS check (target: >=30)
- `td_get_screenshot` — Visual inspection of output

The production `.toe` file (touchdesigner/AIPSummitYousuke.36.toe) passed all
verification gates with 0 compile errors and 60 FPS at 0.2% CPU on a
MacBook Pro.

---

## 8. Phase F: Multi-Camera Support & Production Polish

The final phase addressed production requirements:

### Multi-Camera Support

The `cam_in` videodevinTOP was configured to support multiple sources:

- **MacBook Pro Camera** — Built-in webcam
- **OBS Virtual Camera** — Software video source for screen capture or
  compositing
- **Bunphone Camera** — iPhone connected via USB (Continuity Camera)

Switching is done by changing `cam_in.par.device` to the desired camera
name.

### Keyboard Control Fix

The original keyboard callback script used `int(key)` on all key presses,
including non-numeric keys (arrows, modifiers), causing `ValueError: invalid
literal for int()` spam. Fixed by wrapping in `try/except` and checking
`key.isdigit()` before conversion.

The script also incorrectly used bracket notation (`ae['effect_idx'] = val`)
on the constantCHOP, which does not support item assignment. Fixed to use
`ae.par.value0 = val`.

### Background Cooking

TouchDesigner's `stopplayingwhenminimized` preference was disabled to ensure
the system keeps running when the TD window is minimized or backgrounded.
This is essential for live performance where the operator may need to
interact with other applications while the visuals continue.

---

## 9. Lessons Learned

### Technical Gotchas

**constantCHOP assignment**: Use `ae.par.value0 = val`, never
`ae['effect_idx'] = val`. The constantCHOP does not support item assignment
and will throw a TypeError on every frame if you try.

**Auto-rotate callback**: Use `whileOn`, not `onValueChange`. The
`onValueChange` callback stops firing when audio values go static (e.g.,
during silence). `whileOn` fires every frame regardless, which is necessary
for time-based switching to work.

**Keyboard focus**: Set `focusselect='anywhere'` on the keyboardinDAT.
Without this, the keyboard only responds when the DAT's viewer panel has
focus, which is useless in a performance context.

**Empty switchTOP resolution**: A switchTOP with zero inputs defaults to
128x128 regardless of any custom resolution parameters. Always wire at
least one input before relying on the switch's output resolution.

**f-string escaping in MCP**: Avoid nested quotes inside f-strings sent
through the MCP bridge. The JSON serialization path corrupts them. Use
string concatenation instead.

**Prominence levelTOP wiring**: When inserting a levelTOP between an
existing glslTOP and outTOP, you must explicitly disconnect the outTOP's
existing input first, wire glsl -> level, then wire level -> outTOP. The
initial `td_add_prominence.py` script had a wiring bug that left all 43
outTOP nodes disconnected from their inputs, producing black output.

### Process Insights

**The canonical correction was the most valuable finding.** Without
algorithmic analysis, the system would have shipped with a visual identity
that looked nothing like the source material. Human intuition alone
produced effects that were visually interesting but aesthetically wrong.

**Human curation remained indispensable.** Despite the power of
algorithmic clustering, the best effects were generated from human-selected
frames. The statistical analysis told us *what was common* in the source;
the human selection told us *what was good*.

**Mutation was more valuable than generation.** The 21 mutation effects,
derived from the 21 originals, expanded the visual vocabulary more
efficiently than generating 21 completely new effects would have. Mutations
inherit the parent's core technique while varying specific parameters,
producing a family of related looks rather than a collection of unrelated
ones.

**The MCP bridge approach scales.** Building 43 effects programmatically
through the bridge was substantially faster and more reliable than manual
TouchDesigner interaction would have been. The bridge also enabled
iteration: when a shader didn't look right, the build script could be
re-run with modified source code in seconds.
