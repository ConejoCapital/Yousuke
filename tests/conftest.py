"""Shared pytest fixtures for the Yousuke Visual Extender test suite."""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STANDALONE_DIR = PROJECT_ROOT / "standalone"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
EFFECTS_DIR = PROJECT_ROOT / "effects"

# Make standalone/ + effects/ importable
for p in (str(PROJECT_ROOT), str(STANDALONE_DIR), str(PIPELINE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def effects_dir() -> Path:
    return EFFECTS_DIR


@pytest.fixture
def synthetic_frame() -> np.ndarray:
    """A 1280x720 BGR frame with structure (gradient + circle + edges)."""
    H, W = 720, 1280
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    # Vertical gradient
    grad = np.linspace(20, 200, H, dtype=np.uint8)
    frame[:] = grad[:, None, None]
    # Bright circle (gives edges for Canny / silhouette effects)
    import cv2
    cv2.circle(frame, (W // 2, H // 2), 200, (50, 220, 255), -1)
    cv2.rectangle(frame, (100, 100), (400, 400), (200, 50, 200), -1)
    # Add some noise so RNG-seeded effects have texture
    noise = np.random.RandomState(42).randint(0, 40, frame.shape, dtype=np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return frame


@pytest.fixture
def small_frame() -> np.ndarray:
    """A 320x180 BGR frame for fast perf-insensitive tests."""
    import cv2
    H, W = 180, 320
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    cv2.circle(frame, (W // 2, H // 2), 50, (255, 200, 100), -1)
    cv2.rectangle(frame, (20, 20), (80, 80), (100, 255, 200), -1)
    return frame


@pytest.fixture
def audio_features():
    """Fresh AudioFeatures instance (lazy-imported to keep fixture cheap)."""
    from visuals import AudioFeatures
    return AudioFeatures()


@pytest.fixture
def beat_features():
    """AudioFeatures simulated mid-beat (high energy, all bands lit)."""
    from visuals import AudioFeatures
    af = AudioFeatures()
    af.energy = 0.8
    af.bass = 0.7
    af.sub_bass = 0.6
    af.mids = 0.5
    af.highs = 0.4
    af.beat = True
    af.onset = True
    af.onset_energy = 0.6
    af.kick = 0.9
    return af


@pytest.fixture
def quiet_features():
    """AudioFeatures with all channels near zero."""
    from visuals import AudioFeatures
    return AudioFeatures()  # defaults are all 0.0/False


def make_sine_block(freq_hz: float, sr: int = 22050, duration_s: float = 0.5,
                    amplitude: float = 0.5) -> np.ndarray:
    """Generate a mono sine wave at a known frequency."""
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    return (amplitude * np.sin(2 * math.pi * freq_hz * t)).astype(np.float32)


@pytest.fixture
def sine_block_factory():
    """Factory that builds sine waves at any frequency."""
    return make_sine_block
