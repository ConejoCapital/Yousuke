"""Phase B3 — AudioFeatures unit tests.

Verifies frequency band extraction, beat/onset detection, and simulate()
determinism with synthesized sine waves at known frequencies.
"""
from __future__ import annotations

import math

import numpy as np
import pytest


# ── 1. Default state ──────────────────────────────────────────────────────────

def test_default_state_all_zero(audio_features):
    af = audio_features
    for ch in ("energy", "bass", "sub_bass", "mids", "highs", "onset_energy", "kick"):
        assert getattr(af, ch) == 0.0, f"{ch} should default to 0.0"
    assert af.beat is False
    assert af.onset is False


# ── 2. update_from_block: silence ─────────────────────────────────────────────

def test_silence_yields_zero_energy(audio_features):
    af = audio_features
    silence = np.zeros(2048, dtype=np.float32)
    af.update_from_block(silence)
    assert af.energy < 0.01
    assert af.bass < 0.05
    assert af.mids < 0.05
    assert af.highs < 0.05


# ── 3. Sine wave at known freq lights the right band ─────────────────────────

@pytest.mark.parametrize("freq,band", [
    (50,    "sub_bass"),
    (200,   "bass"),
    (1000,  "mids"),
    (5000,  "highs"),
])
def test_sine_lights_correct_band(audio_features, sine_block_factory, freq, band):
    """A pure tone at a band's center freq should light that band more than the
    other 3 frequency bands. We don't require a specific magnitude — just that
    the target band is the dominant one."""
    af = audio_features
    block = sine_block_factory(freq, sr=22050, duration_s=0.5, amplitude=0.7)
    af.update_from_block(block, sr=22050)

    bands = {
        "sub_bass": af.sub_bass,
        "bass":     af.bass,
        "mids":     af.mids,
        "highs":    af.highs,
    }
    target = bands[band]
    others = [v for k, v in bands.items() if k != band]
    # NOTE: a *pure* sine tone fires ~1 FFT bin; mean across a wide band
    # (e.g. 3-20kHz) dilutes it heavily. We require: (a) some signal,
    # (b) target band wins relative to the other 3 bands. Real broadband
    # music does not have this dilution issue.
    assert target > 0.0, f"Target band {band} silent for {freq}Hz"
    assert target >= max(others), (
        f"{freq}Hz should peak in {band} but bands={bands}"
    )


# ── 4. All values clamped to [0, 1] ──────────────────────────────────────────

def test_loud_signal_does_not_overflow(audio_features, sine_block_factory):
    af = audio_features
    # Very loud signal across full range
    block = sine_block_factory(440, sr=22050, duration_s=0.5, amplitude=4.0)
    af.update_from_block(block, sr=22050)
    for ch in ("energy", "bass", "sub_bass", "mids", "highs", "kick"):
        v = getattr(af, ch)
        assert 0.0 <= v <= 1.0, f"{ch} = {v} out of [0, 1]"


# ── 5. Beat / onset detection: energy step triggers ──────────────────────────

def test_energy_step_triggers_beat_and_onset(audio_features, sine_block_factory):
    af = audio_features
    quiet = np.zeros(2048, dtype=np.float32)
    af.update_from_block(quiet)
    assert af.beat is False

    loud = sine_block_factory(150, sr=22050, duration_s=0.1, amplitude=0.9)
    af.update_from_block(loud, sr=22050)
    # Energy went from ~0 to high — should fire both beat and onset
    assert af.beat is True
    assert af.onset is True
    assert af.onset_energy > 0


def test_steady_signal_does_not_trigger_repeatedly(audio_features, sine_block_factory):
    af = audio_features
    block = sine_block_factory(150, sr=22050, duration_s=0.1, amplitude=0.7)
    af.update_from_block(block, sr=22050)
    # Same block again — no energy delta → no beat
    af.update_from_block(block, sr=22050)
    assert af.beat is False
    assert af.onset is False


# ── 6. simulate() determinism + shape ────────────────────────────────────────

def test_simulate_is_deterministic(audio_features):
    af1 = audio_features
    af1.simulate(1.0)
    snapshot1 = (af1.energy, af1.bass, af1.mids, af1.highs, af1.beat)
    af1.simulate(2.0)
    af1.simulate(1.0)
    snapshot2 = (af1.energy, af1.bass, af1.mids, af1.highs, af1.beat)
    assert snapshot1 == snapshot2


def test_simulate_produces_in_range_values(audio_features):
    af = audio_features
    for t in np.linspace(0, 60, 100):
        af.simulate(float(t))
        for ch in ("energy", "bass", "sub_bass", "mids", "highs", "kick"):
            v = getattr(af, ch)
            assert 0.0 <= v <= 1.0, f"t={t} {ch}={v}"


def test_simulate_fires_beats_at_128bpm(audio_features):
    """At 128 BPM, beat period = 0.469s — across 5s we should see ~10 beat triggers."""
    af = audio_features
    beats = 0
    last_beat = False
    for t in np.linspace(0, 5, 600):
        af.simulate(float(t))
        if af.beat and not last_beat:
            beats += 1
        last_beat = af.beat
    assert 5 <= beats <= 15, f"Expected ~10 beats in 5s @128bpm, got {beats}"
