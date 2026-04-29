"""Phase B4 — Plugin loader tests.

Verifies dynamic loading of effects/, malformed plugin handling, and
ai_generated/ extension hook.
"""
from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest


def _load(effects_dir: Path):
    from visuals import _load_effects_from_dir
    return _load_effects_from_dir(effects_dir)


def test_loads_all_eight_builtins(effects_dir):
    fns, names, report, elapsed = _load(effects_dir)
    assert len(fns) >= 8
    assert len(fns) == len(names)
    assert all(callable(fn) for fn in fns)
    assert elapsed >= 0


def test_returns_distinct_effect_names(effects_dir):
    _, names, _, _ = _load(effects_dir)
    # No two effects with the same name
    assert len(set(names)) == len(names), f"Duplicate names in: {names}"


def test_effects_sorted_by_meta_order(effects_dir):
    """The plugin loader sorts builtins by EFFECT_META['order'] — confirm via
    direct module read.  Canonical effects (order < 0) are prepended to the
    front of the list; built-ins (order >= 1) follow in ascending order."""
    import importlib.util as iu
    fns, names, _, _ = _load(effects_dir)

    # Reconstruct expected order from ALL source directories the loader scans
    all_orders = []

    # Built-ins from effects/*.py
    for py in sorted(effects_dir.glob("*.py")):
        if py.name.startswith("_") or py.name == "__init__.py":
            continue
        spec = iu.spec_from_file_location(py.stem, py)
        m = iu.module_from_spec(spec)
        spec.loader.exec_module(m)
        if hasattr(m, "EFFECT_META") and hasattr(m, "fx_function"):
            all_orders.append((m.EFFECT_META.get("order", 99), m.EFFECT_META.get("name", py.stem)))

    # Canonical effects from effects/canonical/*.py
    canonical_dir = effects_dir / "canonical"
    canonical_orders = []
    if canonical_dir.exists():
        for py in sorted(canonical_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            spec = iu.spec_from_file_location(py.stem, py)
            m = iu.module_from_spec(spec)
            spec.loader.exec_module(m)
            if hasattr(m, "EFFECT_META") and hasattr(m, "fx_function"):
                canonical_orders.append((m.EFFECT_META.get("order", -1), m.EFFECT_META.get("name", py.stem)))

    # Canonical effects are sorted by order and prepended to the front
    canonical_names = [n for _, n in sorted(canonical_orders)]
    builtin_names = [n for _, n in sorted(all_orders)]
    expected_names = canonical_names + builtin_names

    assert names[: len(expected_names)] == expected_names


def test_malformed_plugin_does_not_break_loader(tmp_path, effects_dir):
    """A broken plugin in ai_generated/ must NOT prevent built-ins from loading."""
    sandbox_effects = tmp_path / "effects"
    sandbox_effects.mkdir()
    # Copy real builtins
    for py in effects_dir.glob("*.py"):
        shutil.copy(py, sandbox_effects / py.name)
    # Make ai_generated/ with one broken file
    ai = sandbox_effects / "ai_generated"
    ai.mkdir()
    (ai / "broken.py").write_text("this is not valid python !!!\n")

    fns, names, report, _ = _load(sandbox_effects)
    assert len(fns) >= 8, "Builtins must still load despite broken AI plugin"
    # Report should mention the failure
    joined = "\n".join(report)
    assert "broken.py" in joined and "WARNING" in joined.upper()


def test_ai_generated_plugin_loads_and_extends(tmp_path, effects_dir):
    """A valid plugin in ai_generated/ should be appended to the effect list."""
    sandbox_effects = tmp_path / "effects"
    sandbox_effects.mkdir()
    for py in effects_dir.glob("*.py"):
        shutil.copy(py, sandbox_effects / py.name)
    ai = sandbox_effects / "ai_generated"
    ai.mkdir()
    (ai / "test_plugin.py").write_text(textwrap.dedent("""
        import numpy as np
        EFFECT_META = {"name": "Test AI FX", "order": 100}
        def fx_function(frame, af, state):
            return frame.copy()
    """))

    fns, names, _, _ = _load(sandbox_effects)
    assert "Test AI FX" in names
    assert names.index("Test AI FX") >= 8  # appended after builtins


def test_empty_effects_dir_returns_empty(tmp_path):
    empty = tmp_path / "effects_empty"
    empty.mkdir()
    fns, names, report, _ = _load(empty)
    assert fns == []
    assert names == []


def test_load_report_lines_are_strings(effects_dir):
    _, _, report, _ = _load(effects_dir)
    assert all(isinstance(line, str) for line in report)
