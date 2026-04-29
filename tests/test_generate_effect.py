"""Phase B8 — generate_effect.py unit tests.

NOTE: validate_generated_code returns (ok, rule, message) — a 3-tuple.
NOTE: estimate_cost returns (usd, in_tok, out_tok) — a 3-tuple.
"""
from __future__ import annotations

import pytest


def test_extract_code_from_fenced_block():
    from generate_effect import extract_code
    raw = """Here is your effect:

```python
import cv2
import numpy as np

EFFECT_META = {"name": "X", "description": "x", "key_audio": ["energy"], "tags": [], "order": 99}

def fx_function(frame, af, state):
    return frame
```

Hope this helps!"""
    code = extract_code(raw)
    assert "EFFECT_META" in code
    assert "def fx_function" in code
    assert "```" not in code


def test_validate_generated_code_passes_for_valid():
    from generate_effect import validate_generated_code
    code = """
import numpy as np

EFFECT_META = {
    "name": "Test",
    "description": "A test effect",
    "key_audio": ["energy"],
    "tags": ["test"],
    "order": 99,
}

def fx_function(frame, af, state):
    return frame.copy()
"""
    ok, rule, msg = validate_generated_code(code)
    assert ok, f"Validation should pass. rule={rule} msg={msg}"


def test_validate_generated_code_rejects_missing_meta():
    from generate_effect import validate_generated_code
    code = """
def fx_function(frame, af, state):
    return frame
"""
    ok, rule, msg = validate_generated_code(code)
    assert not ok
    assert "EFFECT_META" in (rule + msg)


def test_validate_generated_code_rejects_syntax_error():
    from generate_effect import validate_generated_code
    code = "this is not valid python !!!"
    ok, rule, msg = validate_generated_code(code)
    assert not ok
    assert "syntax" in (rule + msg).lower()


def test_validate_generated_code_rejects_missing_fx_function():
    from generate_effect import validate_generated_code
    code = """
EFFECT_META = {"name": "X", "description": "x", "key_audio": [], "tags": [], "order": 99}
def something_else(frame, af, state):
    return frame
"""
    ok, rule, msg = validate_generated_code(code)
    assert not ok
    assert "fx_function" in (rule + msg)


def test_validate_generated_code_rejects_missing_meta_keys():
    """EFFECT_META must have name/description/key_audio/tags/order."""
    from generate_effect import validate_generated_code
    code = """
EFFECT_META = {"name": "X"}
def fx_function(frame, af, state):
    return frame
"""
    ok, rule, msg = validate_generated_code(code)
    assert not ok


def test_estimate_cost_returns_tuple():
    from generate_effect import estimate_cost
    result = estimate_cost(
        system_text="x" * 1000,
        user_text="y" * 500,
        has_image=False,
        model="claude-sonnet-4-5",
    )
    assert len(result) == 3
    cost, in_tok, out_tok = result
    assert cost > 0
    assert in_tok > 0
    assert out_tok > 0


def test_estimate_cost_image_adds_more():
    from generate_effect import estimate_cost
    no_img, _, _ = estimate_cost("x" * 100, "y" * 100, has_image=False, model="claude-sonnet-4-5")
    with_img, _, _ = estimate_cost("x" * 100, "y" * 100, has_image=True, model="claude-sonnet-4-5")
    assert with_img > no_img


def test_estimate_cost_opus_more_than_sonnet():
    from generate_effect import estimate_cost
    sonnet, _, _ = estimate_cost("x" * 1000, "y" * 1000, False, "claude-sonnet-4-5")
    opus,   _, _ = estimate_cost("x" * 1000, "y" * 1000, False, "claude-opus-4-1")
    assert opus > sonnet
