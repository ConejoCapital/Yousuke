# Tools

Scripts for building and managing the TouchDesigner network via the
twozero MCP bridge.

---

## Prerequisites

- TouchDesigner 2025.32460+ running with twozero.tox installed
- MCP bridge active on `localhost:40404`
- Verify connection: `nc -z 127.0.0.1 40404`

---

## Script Reference

### Effect bank builders

| Script | Purpose | Usage |
|--------|---------|-------|
| `td_build_effects.py` | Build the 21 original GLSL effects as baseCOMPs | `python tools/td_build_effects.py` |
| `td_build_mutations.py` | Build the 21 mutation GLSL effects | `python tools/td_build_mutations.py` |
| `td_build_gen3.py` | Build 57 Gen3 effects (originals, palette swaps, intensity mutations) | `python tools/td_build_gen3.py` |
| `td_build_contour.py` | Build the 33 Gen3 body-contour and silhouette effects | `python tools/td_build_contour.py` |
| `td_build_chaos.py` | Build the Chaos Engine variant (per-layer transform + HSV drift) | `python tools/td_build_chaos.py` |

### Wiring and configuration

| Script | Purpose | Usage |
|--------|---------|-------|
| `td_wire_all.py` | Wire all effects to the 3-router topology | `python tools/td_wire_all.py` |
| `td_wire_everything.py` | Wire the complete network in one pass | `python tools/td_wire_everything.py` |
| `td_wire_effects.py` | Wire individual effects | `python tools/td_wire_effects.py` |
| `td_wire_contour.py` | Wire the contour effects | `python tools/td_wire_contour.py` |
| `td_add_prominence.py` | Insert audio-driven levelTOPs (opacity + beat flash) | `python tools/td_add_prominence.py` |
| `td_add_web_input.py` | Add web input sources | `python tools/td_add_web_input.py` |
| `td_update_rotation.py` | Write the aggressive random 3-layer auto-rotate script | `python tools/td_update_rotation.py` |
| `td_fix_rotation.py` | Repair rotation parameters | `python tools/td_fix_rotation.py` |
| `chaos_engine_script.py` | Chaos Engine runtime script (drives the chaos transform/HSV drift) | installed into TD by `td_build_chaos.py` |
| `td_mcp.py` | Minimal MCP bridge helper (import as library) | `from tools.td_mcp import td_call` |

### Utilities

| Script | Purpose | Usage |
|--------|---------|-------|
| `live_showcase.py` | Fullscreen live showcase with all effects rotating | `python tools/live_showcase.py --fullscreen` |
| `render_reel.py` | Headless reel renderer (synthetic audio) | `python tools/render_reel.py` |
| `preview_canonical.py` | Preview canonical effects from cluster data | `python tools/preview_canonical.py` |
| `preview_in_terminal.sh` | Terminal-based preview helper | `bash tools/preview_in_terminal.sh` |
| `test_canonical.py` | Test canonical effects | `python tools/test_canonical.py` |

---

## Build Order

To reconstruct the full 133-effect network from scratch:

```bash
# 1. Build the core bank
python tools/td_build_effects.py      # 21 originals
python tools/td_build_mutations.py    # 21 mutations

# 2. Build the Gen3 expansion
python tools/td_build_gen3.py         # 57 Gen3 effects
python tools/td_build_contour.py      # 33 body-contour effects

# 3. Wire everything to the 3-router topology
python tools/td_wire_all.py

# 4. Add audio-driven prominence (opacity + beat flash)
python tools/td_add_prominence.py

# 5. Set up aggressive auto-rotation
python tools/td_update_rotation.py
```

Each script verifies MCP connectivity before executing and reports
success/failure per operation.

Use `--dry-run` on any script to see what would be done without executing.

---

## GLSL Shader Architecture

All shaders share a common header defining audio uniforms:

```glsl
uniform vec4 uAudio;   // (time, rms, bass, sub_bass)
uniform vec4 uAudio2;  // (sub_bass, mids, highs, beat)
```

Each effect baseCOMP follows the structure:
```
in1 (inTOP) -> glsl1 (glslTOP) -> prominence (levelTOP) -> out1 (outTOP)
```

Camera input enters via `in1`. Audio drives shader uniforms and the
prominence levelTOP's opacity/brightness expressions.

---

## MCP Bridge Protocol

All scripts use JSON-RPC 2.0 over HTTP to `http://localhost:40404/mcp`.
The primary tool is `td_execute_python` which runs arbitrary Python inside
TouchDesigner's interpreter. Retry logic: 2 retries with 1-second delay,
120-second timeout per request.
