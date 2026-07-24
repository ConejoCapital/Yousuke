> **HISTORICAL SNAPSHOT (April 28, 2026).** This report describes the
> test suite as it stood during Phase B, before the effect bank grew.
> The suite now holds 234 tests. Current documentation: [README.md](../README.md).

# Phase B Report — Test Scaffold + Engine Hardening
**Apr 28, 2026**

## Summary

96 / 96 tests passing. Two perf-critical effects optimized in-flight, both
well under budget. Standalone Python engine is now production-grade and
ready to serve as the backstage fallback for the April 30 show.

## Test breakdown

| File | Tests | Status |
|---|---|---|
| `tests/test_smoke.py` | 12 | ✓ |
| `tests/test_audio_features.py` | 11 | ✓ |
| `tests/test_plugin_loader.py` | 7 | ✓ |
| `tests/test_effects_render.py` | 40 | ✓ |
| `tests/test_perf.py` | 9 | ✓ |
| `tests/test_analyze_video.py` | 7 | ✓ |
| `tests/test_generate_effect.py` | 10 | ✓ |
| **Total** | **96** | **✓** |

## Performance baseline (1280×720, single-threaded)

| Effect | Median | p95 | Status |
|---|---:|---:|---|
| Volumetric Rings | 1.70 ms | 1.79 ms | ✓ |
| Shard Burst | 1.36 ms | 1.45 ms | ✓ optimized −97% |
| Voxel Explosion | 2.53 ms | 2.70 ms | ✓ |
| Gold Particle Rain | 2.99 ms | 3.72 ms | ✓ |
| Neon Contour | 5.24 ms | 5.71 ms | ✓ |
| Particle Confetti | 5.67 ms | 6.23 ms | ✓ |
| Film Grain Base | 7.82 ms | 8.05 ms | ✓ optimized −78% |
| Kanji Float | 11.72 ms | 17.84 ms | ✓ |

**Single-effect headroom**: slowest = 11.72ms vs 33.3ms 30fps budget.
Theoretical fps for slowest effect alone: **85 fps**.

## Bugs found and fixed during testing

1. **Shard Burst — O(n²) full-frame mask allocation** (effects/shard_burst.py)
   - Before: 42.5ms/frame (would drop us below 30fps)
   - Fix: vectorized rotation, single fillPoly + single bitwise_and instead of
     per-shard mask
   - After: 1.4ms/frame
2. **Film Grain Base — full-resolution Gaussian RNG + HSV roundtrip**
   - Before: 35ms/frame
   - Fix: half-res uniform RNG + cv2.resize + cv2-native gray conversion +
     addWeighted desaturation (no HSV)
   - After: 7.8ms/frame

## Test coverage by behavior

- AudioFeatures band extraction validated against pure sines at 50/200/1k/5k Hz
- Beat/onset detection: rising edge fires, steady state does not retrigger
- simulate() determinism + 128 BPM beat count verified
- All 8 effects render across 30 frames under quiet AND beat conditions
- All 8 effects produce visible output (not all-black)
- All 8 effects DO NOT mutate input frame
- All 8 effects keep state size bounded under 200 continuous beat frames
- Plugin loader handles malformed plugins without crashing built-ins
- AI-generated plugins extend the catalog correctly
- analyze_video feature extraction is deterministic in shape, in [0,1] range
- generate_effect validation rejects: syntax errors, missing meta, missing
  fx_function, incomplete meta keys

## Files added

```
tests/
  __init__.py
  conftest.py
  test_smoke.py
  test_audio_features.py
  test_plugin_loader.py
  test_effects_render.py
  test_perf.py
  test_analyze_video.py
  test_generate_effect.py
pytest.ini
reports/
  perf_baseline.json
  PHASE_B_REPORT.md
```

## Next phase

Phase C — render a 60-second synthetic-audio test reel headlessly so we can
visually QA all 8 effects. Then Phase D — TouchDesigner network via twozero MCP.
