# CLAUDE.md — Project Context for Claude Code

## What This Is

Yousuke is a conceptual audio visual art piece built for (and performed at)
AI Psychosis Summit NYC (April 30, 2026). It takes live audio + camera
input and drives a bank of GLSL pixel shaders through a 3-layer additive
compositing system. The summit-night network had 43 effects (~6.4 x 10^37
states); the current production `.toe` has 133 wired effects (~2.0 x 10^39
states) after the post-summit Gen3 expansion.

## Architecture

- **TouchDesigner** (`AIPSummitYousuke.36.toe`) — Production GPU pipeline.
  133 GLSL shaders in baseCOMPs, 3-layer additive compositing via
  `effect_router` / `layer2_router` / `layer3_router`, frequency-band
  prominence, beat-driven auto-rotation.
- **Python standalone** (`standalone/visuals.py`) — Runs on any laptop.
  Plugin architecture loading effects from `effects/`, `effects/ai_generated/`,
  and `effects/canonical/`.

## Key Numbers

- 133 GLSL shaders wired in TouchDesigner (21 original + 21 mutations +
  1 canon shard = 43 summit-era, + 90 Gen3 added post-summit)
- 31 Python effects in standalone (8 hand-coded + 21 AI-generated + 2 canonical)
- 7 audio parameters in the Python standalone: rms, sub_bass, bass, mids,
  highs, beat, onset. The TD `audio_analysis/out1` CHOP exposes 6 (no
  onset) — the onset branch in `auto_rotate` is dormant by design.
- 3-layer additive compositing (commutative: C(133,3) = 383,306
  combinations; C(43,3) = 12,341 as performed at the summit)
- ~2.0 x 10^39 total visual states in the current network (~6.4 x 10^37 as
  performed)

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
python tools/td_build_gen3.py         # 90 Gen3 GLSL shaders
python tools/td_wire_all.py           # Wire to 3-router topology
python tools/td_add_prominence.py     # Audio-driven opacity
python tools/td_update_rotation.py    # Auto-rotate script
```

## How to Generate New Effects

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python generate_effect.py --from-frame reference/canonical_effects_frames/cluster_05.jpg --name "Effect Name"
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
| `effects/` | 8 hand-coded Python effect plugins |
| `effects/ai_generated/` | 21 AI-generated Python effects |
| `effects/canonical/` | 2 vision-verified canonical Python effects |
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
  prototypes; the GLSL shaders in TD reflect the corrected visual grammar

## Archived Documents

Files in `docs/` with "ARCHIVED" banners describe the earlier 8-effect
system. They are kept for historical reference. The current system is
documented in `README.md` and `ARCHITECTURE.md`.

Archived (have banners):
- `docs/PRODUCT_DOC.md` — Original product spec (pre-expansion)
- `docs/HERMES_PROMPT.md` — Initial Hermes kickoff prompt
- `docs/PHASE_D_PLAN.md` — Initial 8-effect TD build plan
- `docs/SUMMIT_README.md` — April 30 day-of-show runbook
- `touchdesigner/README_FOR_HERMES.md` — Manual Hermes build prompts

Historical reference (no banners, accurate for their era):
- `docs/PHASE_B_REPORT.md` — Phase B test report (96 tests at that time)
- `docs/EFFECTS_CATALOG.md` — Full effect catalog
