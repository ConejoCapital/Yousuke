# CLAUDE.md — Project Context for Claude Code

## What This Is

Yousuke is a conceptual audio visual art piece built for AI Psychosis Summit
NYC (April 30, 2026). It takes live audio + camera input and drives 43 GLSL
pixel shaders through a 3-layer additive compositing system, producing
~6.4 x 10^37 possible visual states.

## Architecture

- **TouchDesigner** (`AIPSummitYousuke.36.toe`) — Production GPU pipeline.
  43 GLSL shaders in baseCOMPs, 3-layer additive compositing via
  `effect_router` / `layer2_router` / `layer3_router`, frequency-band
  prominence, beat-driven auto-rotation.
- **Python standalone** (`standalone/visuals.py`) — Runs on any laptop.
  Plugin architecture loading effects from `effects/`, `effects/ai_generated/`,
  and `effects/canonical/`.

## Key Numbers

- 43 GLSL shaders (21 original + 21 mutations + 1 canon shard)
- 7 audio parameters: rms, sub_bass, bass, mids, highs, beat, onset
- 3-layer additive compositing (commutative: C(43,3) = 12,341 combinations)
- ~6.4 x 10^37 total visual states (~2.5 quintillion universe lifetimes)

## How to Run

```bash
# Python standalone
python standalone/visuals.py --mode webcam --audio mic

# TouchDesigner
open AIPSummitYousuke.36.toe
```

## How to Test

```bash
pytest                    # All 234 tests
pytest -m "not slow"      # Skip slow tests
pytest tests/test_smoke.py  # Smoke tests only
```

## How to Build TD Network from Scratch

Requires TouchDesigner running with twozero MCP bridge on `localhost:40404`.

```bash
python tools/td_build_effects.py      # 21 original GLSL shaders
python tools/td_build_mutations.py    # 21 mutation GLSL shaders
python tools/td_wire_all.py           # Wire to 3-router topology
python tools/td_add_prominence.py     # Audio-driven opacity
python tools/td_update_rotation.py    # Auto-rotate script
```

## How to Generate New Effects

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python generate_effect.py --from-frame reference/frames/frame_05.jpg --name "Effect Name"
python generate_effect.py --describe "description of desired visual effect"
```

## File Organization

| Path | Purpose |
|------|---------|
| `README.md` | Canonical project documentation |
| `ARCHITECTURE.md` | Technical system architecture reference |
| `PROCESS.md` | Narrative of the AI-driven build process |
| `CONTRIBUTING.md` | How to extend the system |
| `standalone/visuals.py` | Python standalone visual engine |
| `effects/` | Python effect plugins (8 hand-coded) |
| `effects/ai_generated/` | 21 AI-generated Python effects |
| `effects/canonical/` | 2 vision-verified canonical effects |
| `tools/` | TD build scripts (see `tools/README.md`) |
| `tools/td_mcp.py` | MCP bridge helper — `from tools.td_mcp import td_call` |
| `reference/` | Canonical catalog, cluster frames, generation plan |
| `tests/` | 7 test modules, 234 tests |
| `docs/` | Archived specs and reports (see banners) |

## Conventions

- GLSL shaders use `uAudio` (time, rms, bass, sub_bass) and `uAudio2`
  (sub_bass, mids, highs, beat) uniforms
- Python effects export `EFFECT_META` dict + `fx_function` callable
- Effect validation: syntax check, export check, test run, shape match
- TD build scripts use `tools/td_mcp.py` for MCP bridge calls
- The 8 original hand-coded effects in `effects/` are pre-canonical-analysis
  prototypes; the 43 GLSL shaders in TD reflect the corrected visual grammar

## Archived Documents

Files in `docs/` with "ARCHIVED" banners describe the earlier 8-effect
system. They are kept for historical reference. The current system is
documented in `README.md` and `ARCHITECTURE.md`.

- `docs/PRODUCT_DOC.md` — Original product spec (pre-expansion)
- `docs/HERMES_PROMPT.md` — Initial Hermes kickoff prompt
- `docs/PHASE_D_PLAN.md` — Initial 8-effect TD build plan
- `docs/SUMMIT_README.md` — April 30 day-of-show runbook
- `touchdesigner/README_FOR_HERMES.md` — Manual Hermes build prompts
