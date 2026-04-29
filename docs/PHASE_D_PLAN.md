# Phase D — TouchDesigner Build Plan (executed via twozero MCP)

## Status: AWAITING TD MCP CONNECTION

Prerequisites once you've completed the manual steps in the chat:
- [ ] TouchDesigner installed (✓ done — `/Applications/TouchDesigner.app`)
- [ ] twozero.tox in ~/Downloads (✓ done)
- [ ] mcp_servers.twozero_td in ~/.hermes/config.yaml (✓ done)
- [ ] TD running with twozero installed + MCP toggle on
- [ ] Hermes session restarted (so MCP tools load)
- [ ] `nc -z 127.0.0.1 40404` returns success

## Build sequence (each step = one MCP transaction batch)

Per the touchdesigner-mcp skill rules:
- Always call `td_get_par_info` before setting params on a new op type
- Always call `td_get_errors` after each phase
- Take a screenshot via `td_get_screenshot` after every fx_ container

### D0 — Network sanity
1. `td_list_instances` — confirm exactly one TD instance reachable
2. `td_get_focus` — see active project path, selected op
3. `td_get_network(path="/project1")` — inspect baseline
4. `td_clear_textport()` — clean console
5. `td_get_perf` — baseline FPS

### D1 — Audio + camera input (PROMPT 1+2)
- Create `cam_in` (videodeviceinTOP) at /project1
- Create `audio_in` (audiodeviceinCHOP)
- Create container `audio_analysis` with:
  - audiospectrumCHOP (FFT=512, outputmenu=setmanually, outlength=256, timeslice=ON)
  - mathCHOP (gain=10) for spectrum
  - analyzeCHOP for RMS
  - beatCHOP for beat trigger
  - separate channels for sub_bass/bass/mids/highs via selectCHOP + range filters
  - mergeCHOP combining all 7 channels
  - outCHOP exposing them
- VERIFY: read each channel via `td_read_chop`, screenshot the network

### D2-D9 — Eight fx_ containers
For each effect (one MCP batch per container):
- Create container `fx_<name>` with explicit input/output
- Build the operator graph per touchdesigner/README_FOR_HERMES.md
- Wire camera + relevant audio_out channels
- VERIFY: `td_get_errors`, `td_get_screenshot`

Effect order (matches README):
- D2: fx_neon_contour (Edge → Blur → HSV → Level → Composite)
- D3: fx_particles (Threshold → Edge → GPU Particles → Point Sprite → Composite)
- D4: fx_voxel (Reorder → Instanced Geometry → Render)
- D5: fx_rings (Beat → Trigger → Feedback → Circle SOP → Composite)
- D6: fx_shards (GLSL TOP voronoi shader, kick uniform)
- D7: fx_gold_rain (Particle SOP → Point Sprite → Composite)
- D8: fx_grain (Noise → Composite → GLSL vignette → HSV)
- D9: fx_kanji (Text TOP array → Feedback → Composite, NotoSansCJK font)

### D10 — Effect router (PROMPT 11)
- switchTOP `effect_router` with 8 inputs
- constantCHOP `active_effect` (int 0-7) → switch index
- chopExecuteDAT `auto_rotate` for auto-advance logic
- keyboardinDAT for manual lock (1-8 keys)

### D11 — Output (PROMPT 12)
- windowCOMP `main_output` (1280x720, fullscreen toggle)
- performCOMP for FPS overlay
- infoDAT showing active effect name + audio levels
- annotation explaining signal flow
- Save as ~/Desktop/Yousuke/visuals.toe

### D12 — Verification gauntlet
- `td_get_errors(recursive=true)` — must return empty
- `td_get_perf` — FPS should be ≥30
- For each fx_: lock the switch to that effect → screenshot → unlock
- Generate a 30s recording via moviefileoutTOP at prores codec → reports/td_reel.mov

## Why this is safe to script in advance

twozero MCP tools are deterministic — same call same result. The skill guidance is clear:
1. Discover params before setting them (td_get_par_info)
2. Bulk creation via td_execute_python is safer than 50 individual calls
3. Always verify after each phase

## What I'll show you between phases

After D1: screenshot of audio_analysis container with channel values
After D2-D9 (each): screenshot + 1-line "looks like X" description
After D10: video of switching between 2-3 effects manually
After D11: full-screen output running with simulated audio
After D12: pass/fail report on each verification gate

## Estimated time
- D0: 30s
- D1: 2 min
- D2-D9: 4-6 min each = 30-50 min total
- D10: 5 min
- D11: 3 min
- D12: 5 min
TOTAL: 45-65 min once MCP connected
