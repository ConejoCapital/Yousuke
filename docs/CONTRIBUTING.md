# Contributing

Guidelines for extending the Yousuke audio-reactive visual system.

---

## Adding a Python Effect Plugin

### Plugin Contract

Create a `.py` file in `effects/` (or `effects/ai_generated/` for
AI-generated effects). The file must export exactly two names:

```python
import numpy as np

EFFECT_META = {
    "name":        "My Effect",           # Display name
    "description": "One-line description of the visual",
    "key_audio":   ["bass", "onset"],     # Audio channels this effect responds to
    "tags":        ["glitch", "color"],   # Searchable tags
    "order":       99,                    # Sort key (1-8 for built-ins, 99 for custom)
}

def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """
    Args:
        frame: BGR uint8 array, shape (H, W, 3)
        af:    AudioFeatures instance with attributes:
                 energy, bass, mids, highs, sub_bass  — float 0-1
                 beat, onset                           — bool
                 onset_energy, kick                    — float 0-1
        state: Mutable dict persisted across frames for this effect.
               Use for particles, trails, accumulators, etc.

    Returns:
        BGR uint8 array, same shape as input.
    """
    # Your effect logic here
    return frame
```

### Rules

- Output shape must equal input shape.
- Do not mutate the input `frame` — copy it first if modifying in place.
- Keep per-frame time under 16ms at 1280x720 (30 FPS budget).
- Use `state` for temporal effects (particles, feedback, trails). Do not
  use module-level globals.
- Files starting with `_` are skipped by the loader.

### Auto-Discovery

Place the file in `effects/` or `effects/ai_generated/`. The plugin loader
discovers it automatically at next startup — no configuration needed.

---

## Adding a GLSL Shader to TouchDesigner

### Shader Structure

All TD effects use the common GLSL header from
`tools/td_build_effects.py`. Your shader receives:

```glsl
uniform vec4 uAudio;   // (time, rms, bass, sub_bass)
uniform vec4 uAudio2;  // (sub_bass, mids, highs, beat)
```

With convenience defines: `iTime`, `energy`, `bass`, `sub`, `mids`,
`highs`, `beat`.

Camera input is sampled from `sTD2DInputs[0]` at `vUV.st`.

Output via `fragColor = TDOutputSwizzle(vec4(result, 1.0));`

### Adding to the Build Script

1. Add your effect to the `EFFECTS` list in `tools/td_build_effects.py`
   (or `tools/td_build_mutations.py` for mutations):

   ```python
   {
       "name": "fx_my_effect",
       "label": "My Effect",
       "shader": GLSL_HEADER + """
   void main() {
       vec2 uv = vUV.st;
       vec4 src = texture(sTD2DInputs[0], uv);
       // Your shader logic
       fragColor = TDOutputSwizzle(vec4(result, 1.0));
   }
   """,
   },
   ```

2. Run the build script with TD and the twozero MCP bridge active:

   ```bash
   python tools/td_build_effects.py --effect <index>
   ```

3. Re-wire with `tools/td_wire_all.py` to include the new effect in the
   router.

---

## Using AI to Generate Effects

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...

# From a video frame (best quality — uses Claude vision)
python pipeline/generate_effect.py --from-frame path/to/frame.jpg --name "Effect Name"

# From text description
python pipeline/generate_effect.py --describe "visual description here"

# Extend an existing effect
python pipeline/generate_effect.py --extend existing_effect_name

# From canonical catalog entry
python pipeline/generate_effect.py --from-canonical reference/canonical_effects.json --id 7
```

Generated effects are validated automatically (syntax, exports, test run,
shape match) with up to 2 retry attempts on failure.

---

## Running the Test Suite

```bash
# Run all 234 tests
pytest

# Run a specific test file
pytest tests/test_effects_render.py

# Run with verbose output
pytest -v

# Run performance benchmarks only
pytest tests/test_perf.py
```

### What the Tests Cover

- Smoke tests: imports, basic pipeline sanity
- Audio feature extraction: validated against pure sine waves at known
  frequencies
- Plugin loader: discovery, malformed file handling, AI plugin integration
- Effect rendering: all effects produce visible (non-black) output, don't
  mutate inputs, handle both silent and beat conditions
- Performance: per-effect latency benchmarks at 1280x720
- Video analysis: feature extraction determinism and value ranges
- Effect generation: validation pipeline correctness (rejects bad syntax,
  missing exports, wrong shapes)

---

## Code Style

- Python 3.11+ (type hints encouraged but not required)
- NumPy for array operations; avoid pure-Python loops over pixels
- OpenCV (`cv2`) for image processing
- No module-level mutable state in effect plugins — use the `state` dict
- Keep effects self-contained: each `.py` file should work independently
