"""Phase B1 smoke tests — every module imports cleanly and core types exist."""
from __future__ import annotations

import importlib

import pytest


def test_import_visuals():
    import visuals
    assert hasattr(visuals, "AudioFeatures")
    assert hasattr(visuals, "EFFECTS")
    assert hasattr(visuals, "EFFECT_NAMES")
    assert len(visuals.EFFECTS) == len(visuals.EFFECT_NAMES)
    assert len(visuals.EFFECTS) >= 8, "Expected at least 8 effects (got %d)" % len(visuals.EFFECTS)


def test_import_analyze_video():
    mod = importlib.import_module("analyze_video")
    assert mod is not None


def test_import_generate_effect():
    mod = importlib.import_module("generate_effect")
    assert mod is not None


@pytest.mark.parametrize("name", [
    "neon_contour",
    "particle_confetti",
    "voxel_explosion",
    "volumetric_rings",
    "shard_burst",
    "gold_particle_rain",
    "film_grain",
    "kanji_float",
])
def test_effect_module_loads(name):
    mod = importlib.import_module(f"effects.{name}")
    assert hasattr(mod, "fx_function"), f"{name} missing fx_function"
    assert hasattr(mod, "EFFECT_META"), f"{name} missing EFFECT_META"
    meta = mod.EFFECT_META
    assert "name" in meta
    assert "order" in meta


def test_effects_dir_listing(effects_dir):
    assert effects_dir.exists()
    py_files = sorted(p.name for p in effects_dir.glob("*.py") if not p.name.startswith("_"))
    assert len(py_files) >= 8
