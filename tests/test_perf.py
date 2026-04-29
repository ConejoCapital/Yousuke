"""Phase B6 — Per-effect performance benchmarks.

Measures average ms/frame at 1280x720 for each effect. Logs results to
reports/perf_baseline.json. Targets:
  - 30 FPS budget = 33.3 ms/frame total → individual effect must be < 25ms
  - WARN at >20ms, FAIL at >50ms (we want headroom for capture + display)
"""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

PERF_REPORT = Path(__file__).resolve().parent.parent / "reports" / "perf_baseline.json"
WARN_MS = 20.0
FAIL_MS = 50.0


def _all_effects():
    from visuals import EFFECTS, EFFECT_NAMES
    return list(zip(EFFECT_NAMES, EFFECTS))


def _measure(fn, frame, af, n_warmup=5, n_measure=30):
    state = {}
    # Warmup so first-frame state allocation doesn't skew the median
    for _ in range(n_warmup):
        fn(frame, af, state)
    times = []
    for i in range(n_measure):
        # Toggle audio so spawn paths are exercised
        af.beat = (i % 4 == 0)
        af.onset = (i % 6 == 0)
        t0 = time.perf_counter()
        fn(frame, af, state)
        times.append((time.perf_counter() - t0) * 1000.0)
    arr = np.array(times)
    return {
        "median_ms": float(np.median(arr)),
        "mean_ms":   float(np.mean(arr)),
        "p95_ms":    float(np.percentile(arr, 95)),
        "max_ms":    float(np.max(arr)),
        "min_ms":    float(np.min(arr)),
        "n_samples": int(n_measure),
    }


@pytest.mark.perf
def test_perf_baseline(synthetic_frame, beat_features):
    """Run the full effect catalog and write a perf report.

    This test always passes — it's a measurement, not a gate. The gate is the
    individual `test_perf_under_*ms` tests below.
    """
    results = {}
    print()  # newline so the first effect prints on its own line under pytest
    for name, fn in _all_effects():
        from visuals import AudioFeatures
        af = AudioFeatures()
        af.energy = 0.7; af.bass = 0.6; af.sub_bass = 0.5
        af.mids = 0.5;   af.highs = 0.4; af.kick = 0.8
        stats = _measure(fn, synthetic_frame, af)
        stats["status"] = (
            "FAIL" if stats["median_ms"] > FAIL_MS else
            "WARN" if stats["median_ms"] > WARN_MS else
            "OK"
        )
        results[name] = stats
        marker = {"OK": "✓", "WARN": "⚠", "FAIL": "✗"}[stats["status"]]
        print(f"  {marker} {name:<22} median={stats['median_ms']:6.2f}ms  "
              f"p95={stats['p95_ms']:6.2f}ms  max={stats['max_ms']:6.2f}ms")

    # Aggregate
    medians = [r["median_ms"] for r in results.values()]
    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "frame_size": list(synthetic_frame.shape[:2][::-1]),  # (W, H)
        "warn_threshold_ms": WARN_MS,
        "fail_threshold_ms": FAIL_MS,
        "effects": results,
        "totals": {
            "sum_median_ms": float(sum(medians)),
            "max_median_ms": float(max(medians)),
            "slowest_effect": max(results, key=lambda k: results[k]["median_ms"]),
        },
    }
    PERF_REPORT.parent.mkdir(parents=True, exist_ok=True)
    PERF_REPORT.write_text(json.dumps(summary, indent=2))
    print(f"\n  perf report → {PERF_REPORT}")
    print(f"  slowest = {summary['totals']['slowest_effect']} "
          f"@ {summary['totals']['max_median_ms']:.2f}ms")


@pytest.mark.perf
@pytest.mark.parametrize("name,fn", _all_effects(), ids=lambda x: x if isinstance(x, str) else "fn")
def test_perf_per_effect_under_50ms(name, fn, synthetic_frame):
    """Hard gate: every effect must finish in under 50ms median at 1280x720."""
    from visuals import AudioFeatures
    af = AudioFeatures()
    af.energy = 0.7; af.bass = 0.6; af.kick = 0.8; af.beat = True
    stats = _measure(fn, synthetic_frame, af, n_warmup=3, n_measure=15)
    assert stats["median_ms"] < FAIL_MS, (
        f"{name} median {stats['median_ms']:.1f}ms exceeds {FAIL_MS}ms hard gate"
    )
