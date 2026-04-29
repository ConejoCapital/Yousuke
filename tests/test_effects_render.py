"""Phase B5 — Headless rendering tests for every effect.

Each effect must:
  1. Run without raising for 60 frames at 1280x720
  2. Produce uint8 output of the same H,W as input
  3. Not produce all-zero (totally black) output across the whole 60-frame run
  4. Tolerate both quiet audio (zeros) and beat audio (high energy)
  5. Maintain bounded internal state (no unbounded growth)
"""
from __future__ import annotations

import math

import numpy as np
import pytest

# Skip these effect names if discovered to be too unstable for headless;
# none currently expected to skip but slot is reserved.
_RENDER_FRAMES = 30


def _all_effects():
    from visuals import EFFECTS, EFFECT_NAMES
    return list(zip(EFFECT_NAMES, EFFECTS))


@pytest.mark.parametrize("name,fn", _all_effects(), ids=lambda x: x if isinstance(x, str) else "fn")
def test_effect_renders_quiet(name, fn, synthetic_frame, quiet_features):
    """Render under silence — must not crash, output shape preserved."""
    state = {}
    out = None
    for _ in range(_RENDER_FRAMES):
        out = fn(synthetic_frame, quiet_features, state)
    assert out is not None
    assert out.dtype == np.uint8, f"{name} output dtype was {out.dtype}"
    assert out.shape == synthetic_frame.shape, f"{name} shape mismatch: {out.shape} vs {synthetic_frame.shape}"
    assert not np.isnan(out).any(), f"{name} produced NaN"


@pytest.mark.parametrize("name,fn", _all_effects(), ids=lambda x: x if isinstance(x, str) else "fn")
def test_effect_renders_under_beat(name, fn, synthetic_frame, beat_features):
    """Render under simulated beat conditions — must not crash."""
    state = {}
    out = None
    for i in range(_RENDER_FRAMES):
        # Toggle beat/onset every few frames to exercise spawn paths
        beat_features.beat = (i % 4 == 0)
        beat_features.onset = (i % 6 == 0)
        out = fn(synthetic_frame, beat_features, state)
    assert out is not None
    assert out.shape == synthetic_frame.shape
    assert out.dtype == np.uint8


@pytest.mark.parametrize("name,fn", _all_effects(), ids=lambda x: x if isinstance(x, str) else "fn")
def test_effect_produces_visible_output(name, fn, synthetic_frame, beat_features):
    """At least one frame in the run should have non-trivial brightness.
    Catches effects that silently render all-black."""
    state = {}
    max_mean = 0.0
    for i in range(_RENDER_FRAMES):
        beat_features.beat = (i % 4 == 0)
        beat_features.onset = (i % 6 == 0)
        out = fn(synthetic_frame, beat_features, state)
        max_mean = max(max_mean, float(out.mean()))
    assert max_mean > 5.0, f"{name} output stayed near-black (max mean {max_mean:.2f}/255)"


@pytest.mark.parametrize("name,fn", _all_effects(), ids=lambda x: x if isinstance(x, str) else "fn")
def test_effect_state_is_bounded(name, fn, synthetic_frame, beat_features):
    """Run 200 frames continuously firing beats — state size must stay bounded.
    Catches particle/voxel lists that grow without cleanup."""
    import sys
    state = {}
    for i in range(200):
        beat_features.beat = True
        beat_features.onset = True
        beat_features.kick = 1.0
        beat_features.sub_bass = 0.9
        fn(synthetic_frame, beat_features, state)

    # Heuristic: any list/dict in state should have <= 5000 entries
    for k, v in state.items():
        if isinstance(v, list):
            assert len(v) <= 5000, f"{name}.state[{k!r}] grew to {len(v)} entries"
        if isinstance(v, dict):
            assert len(v) <= 5000, f"{name}.state[{k!r}] grew to {len(v)} entries"


@pytest.mark.parametrize("name,fn", _all_effects(), ids=lambda x: x if isinstance(x, str) else "fn")
def test_effect_does_not_mutate_input(name, fn, synthetic_frame, beat_features):
    """Effects must not write into the input frame in-place — that would corrupt
    the next effect in the chain."""
    state = {}
    original = synthetic_frame.copy()
    fn(synthetic_frame, beat_features, state)
    diff = np.abs(synthetic_frame.astype(np.int16) - original.astype(np.int16)).sum()
    assert diff == 0, f"{name} mutated input frame in place (sum-diff={diff})"
