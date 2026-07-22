#!/usr/bin/env python3
"""
¥ØUSUK€ Visual Extender — AI Effect Generator
Uses Claude API to write new runnable effect functions.

Usage:
    python pipeline/generate_effect.py --from-frame reference/canonical_effects_frames/cluster_05.jpg --name "Plasma Web"
    python pipeline/generate_effect.py --describe "glitchy RGB channel separation with scan lines"
    python pipeline/generate_effect.py --extend neon_contour
    python pipeline/generate_effect.py --from-canonical reference/canonical_effects.json --id 7
    python pipeline/generate_effect.py --describe "..." --model claude-sonnet-4-5

Requires:
    export ANTHROPIC_API_KEY=sk-ant-...

Output:
    effects/ai_generated/effect_YYYYMMDD_HHMMSS_slug.py
"""

import argparse
import ast
import base64
import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

# ── Setup instructions ────────────────────────────────────────────────────────

_SETUP_INSTRUCTIONS = """
  ANTHROPIC_API_KEY is not set.

  To use the AI effect generator:
    1. Get your API key from https://console.anthropic.com/
    2. Set it in your shell:
         export ANTHROPIC_API_KEY=sk-ant-api03-...
    3. Re-run this script.

  Without the key, you can still:
    - Browse existing effects in effects/
    - Browse AI-generated effects in effects/ai_generated/
    - Run visuals.py with all loaded effects
"""

_SYSTEM_PROMPT = """\
You are an expert Python/OpenCV audio-reactive visual effects programmer.
Your task: write a single Python module that implements one audio-reactive visual effect.

## Plugin contract (REQUIRED)

The file must define exactly two names at module level:

    EFFECT_META = {
        "name":        str,          # Short display name
        "description": str,          # One-line description
        "key_audio":   list[str],    # e.g. ["bass", "onset"]
        "tags":        list[str],    # e.g. ["glitch", "rgb", "scanlines"]
        "order":       int,          # Use 99 for AI-generated effects
    }

    def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
        ...

## fx_function signature

    frame : np.ndarray  — BGR uint8, shape (H, W, 3)
    af                  — AudioFeatures object with these attributes:
        af.energy       float 0-1   overall RMS energy
        af.bass         float 0-1   80-300 Hz band
        af.mids         float 0-1   300-3000 Hz band
        af.highs        float 0-1   3000+ Hz band
        af.sub_bass     float 0-1   20-80 Hz band
        af.beat         bool        beat detected this frame
        af.onset        bool        transient onset this frame
        af.onset_energy float 0-1   onset strength
        af.kick         float 0-1   kick/low combined
    state : dict        — mutable dict persisted across frames (use for particles, rings, etc.)
    Returns: np.ndarray — BGR uint8, same shape as input (H, W, 3)

## Rules

1. Import only: cv2, numpy (as np), math, random, time, os. No other stdlib or third-party.
2. Do NOT import anthropic, requests, or any network library.
3. Output must be same shape as input: (H, W, 3) uint8.
4. Guard state initialization with `if "key" not in state:` patterns.
5. Keep all helper functions inside the file (no external dependencies).
6. The function MUST work when called with np.zeros((480, 640, 3), dtype=np.uint8).
7. Include EFFECT_META and fx_function — nothing else is required at module level.
8. Do NOT add `if __name__ == "__main__"` blocks.

## Output format

Respond with ONLY the Python code. No explanation, no markdown fences, no extra text.
Start with the module docstring, then imports, then EFFECT_META, then fx_function.
"""


# ── Pre-flight checks ─────────────────────────────────────────────────────────

def preflight_check(args) -> bool:
    errors = []

    if not os.environ.get("ANTHROPIC_API_KEY"):
        errors.append("ANTHROPIC_API_KEY not set")

    if args.from_frame and not Path(args.from_frame).exists():
        errors.append(f"Frame not found: {args.from_frame}")

    if args.extend:
        p = Path(__file__).parent.parent / "effects" / f"{args.extend}.py"
        if not p.exists():
            errors.append(f"Effect to extend not found: {p}")

    if args.from_canonical:
        if not Path(args.from_canonical).exists():
            errors.append(f"Canonical effects file not found: {args.from_canonical}")

    if errors:
        print("\n  ERROR(s):")
        for e in errors:
            print(f"    ✗ {e}")
        if "ANTHROPIC_API_KEY not set" in errors:
            print(_SETUP_INSTRUCTIONS)
        return False
    return True


# ── Prompt builder ────────────────────────────────────────────────────────────

def build_prompt(args, prior_error: Optional[str] = None,
                 prior_code: Optional[str] = None) -> list:
    """
    Build the messages list for the Claude API call.
    Returns list of {"role": ..., "content": ...} dicts.
    """
    messages = []

    # ── Determine mode and build user content ──
    if args.from_frame:
        t0 = time.time()
        print(f"  Reading image: {args.from_frame}")
        with open(args.from_frame, "rb") as f:
            img_bytes = f.read()
        frame_b64 = base64.b64encode(img_bytes).decode()
        ext       = Path(args.from_frame).suffix.lower().lstrip(".")
        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                      "png": "image/png"}.get(ext, "image/jpeg")

        name_hint = f" Call the effect \"{args.name}\"." if args.name else ""
        user_content = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": frame_b64},
            },
            {
                "type": "text",
                "text": (
                    f"Write an audio-reactive visual effect inspired by the visual style "
                    f"in this frame. Capture the mood, colors, and energy — but make it "
                    f"dynamic and responsive to music.{name_hint}"
                ),
            },
        ]

    elif args.describe:
        frame_b64 = None
        user_content = (
            f"Write an audio-reactive visual effect that does: {args.describe}"
            + (f'\n\nCall the effect "{args.name}".' if args.name else "")
        )

    elif args.extend:
        effect_path = Path(__file__).parent.parent / "effects" / f"{args.extend}.py"
        existing_code = effect_path.read_text()
        frame_b64 = None
        user_content = (
            f"Here is an existing effect:\n\n```python\n{existing_code}\n```\n\n"
            f"Write a new, distinct variation that extends or remixes this effect. "
            f"Change at least 3 visual aspects while keeping the same general concept. "
            + (f'Call the new effect "{args.name}".' if args.name else
               "Give it a creative new name in EFFECT_META.")
        )

    elif args.from_canonical:
        with open(args.from_canonical) as f:
            catalog = json.load(f)
        effects_list = catalog.get("canonical_effects", [])
        target = None
        for e in effects_list:
            if e["id"] == args.id:
                target = e
                break
        if target is None:
            print(f"  ERROR: Effect ID {args.id} not found in {args.from_canonical}")
            sys.exit(1)

        # Load the representative frame image so Claude sees the actual look,
        # not just the numeric signature. This is critical for visual parity.
        frame_path = target.get("representative_frame_path")
        frame_b64 = None
        if frame_path and Path(frame_path).exists():
            with open(frame_path, "rb") as f:
                img_bytes = f.read()
            frame_b64 = base64.b64encode(img_bytes).decode()
            ext = Path(frame_path).suffix.lower().lstrip(".")
            media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                          "png": "image/png"}.get(ext, "image/jpeg")

        text_block = (
            f"Write an audio-reactive visual effect that recreates the look "
            f"shown in the attached reference frame from a live visual set by "
            f"\u00a5\u00d8USUK\u20ac \u00a5UK1MAT$U (Boiler Room Tokyo \u00d7 Super Dommune).\n\n"
            f"This frame is cluster #{target['id']} of the canonical-effects analysis.\n"
            f"Category hint: {target['category']}.\n"
            f"Visual signature (from k-means on 1,440+ sampled frames):\n"
            f"```json\n{json.dumps(target['visual_signature'], indent=2)}\n```\n\n"
            f"Audio mapping: {target['inferred_audio_mapping']}.\n"
            f"This look recurs at timestamps: "
            f"{target['timestamps'][:5]}s (first 5 of {target['cluster_size']}).\n\n"
            f"Match the frame's palette, edge character, contrast and motion feel as "
            f"closely as possible. Treat the numeric signature as ground truth \u2014 "
            f"the dominant colors, edge density and saturation of your output on a "
            f"mid-energy frame should land within \u00b110% of those values.\n\n"
            + (f'Call the effect "{args.name}".' if args.name else
               'Call the effect "' + target["name"] + '".')
        )

        if frame_b64 is not None:
            user_content = [
                {"type": "image",
                 "source": {"type": "base64", "media_type": media_type, "data": frame_b64}},
                {"type": "text", "text": text_block},
            ]
        else:
            user_content = text_block

    else:
        print("  ERROR: Must specify one of --from-frame, --describe, --extend, --from-canonical")
        sys.exit(1)

    messages.append({"role": "user", "content": user_content})

    # ── Append correction turn on retry ──
    if prior_error and prior_code:
        messages.append({"role": "assistant", "content": prior_code})
        messages.append({
            "role": "user",
            "content": (
                f"The code you generated failed validation with this error:\n\n"
                f"  {prior_error}\n\n"
                f"Fix the issue and return the complete corrected code. "
                f"Ensure fx_function returns an ndarray with shape (H, W, 3) uint8 "
                f"that matches the input frame's dimensions."
            ),
        })

    return messages, frame_b64


# ── Claude API call ───────────────────────────────────────────────────────────

def call_claude(messages: list, system: str, model: str) -> str:
    """Call Claude API and return the response text."""
    try:
        import anthropic
    except ImportError:
        print("  ERROR: anthropic package not installed  →  pip install anthropic>=0.30.0")
        sys.exit(1)

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=messages,
    )
    return response.content[0].text


# ── Code extraction ───────────────────────────────────────────────────────────

def extract_code(raw_response: str) -> str:
    """Strip markdown fences if present, return clean Python code."""
    # Try to extract from ```python ... ``` block
    match = re.search(r"```(?:python)?\n(.*?)```", raw_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Otherwise return as-is (system prompt says no fences, but just in case)
    return raw_response.strip()


# ── Code validation ───────────────────────────────────────────────────────────

class _MockAF:
    """Minimal AudioFeatures stub for validation test run."""
    energy       = 0.5
    bass         = 0.5
    mids         = 0.3
    highs        = 0.2
    sub_bass     = 0.4
    beat         = False
    onset        = False
    onset_energy = 0.0
    kick         = 0.3


def validate_generated_code(code: str) -> tuple:
    """
    Validate generated effect code.
    Returns (valid: bool, error_rule: str, error_message: str).
    """
    # Rule 1: Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, "Syntax check", str(e)

    # Rule 2: Write to temp file and load
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        spec   = importlib.util.spec_from_file_location("_validate_effect", tmp_path)
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            return False, "Module load", str(e)

        # Rule 3: Required exports
        if not hasattr(module, "EFFECT_META"):
            return False, "Required exports", "EFFECT_META not defined"
        if not hasattr(module, "fx_function"):
            return False, "Required exports", "fx_function not defined"
        if not callable(module.fx_function):
            return False, "Required exports", "fx_function is not callable"

        meta = module.EFFECT_META
        if not isinstance(meta, dict):
            return False, "Required exports", "EFFECT_META must be a dict"
        for key in ("name", "description", "key_audio", "tags", "order"):
            if key not in meta:
                return False, "Required exports", f"EFFECT_META missing key: '{key}'"

        # Rule 4: Test run on blank frame
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        state = {}
        try:
            result = module.fx_function(blank, _MockAF(), state)
        except Exception as e:
            return False, "Test run on blank frame", str(e)

        if not isinstance(result, np.ndarray):
            return False, "Test run on blank frame", f"fx_function returned {type(result)}, expected np.ndarray"

        if result.shape != (480, 640, 3):
            return False, "Test run on blank frame", \
                f"Output shape {result.shape} != expected (480, 640, 3)"

        if result.dtype != np.uint8:
            return False, "Test run on blank frame", \
                f"Output dtype {result.dtype} != uint8"

    finally:
        os.unlink(tmp_path)

    return True, "", ""


# ── Save effect ───────────────────────────────────────────────────────────────

def save_effect(code: str, name: str) -> Path:
    """Save generated code to effects/ai_generated/effect_YYYYMMDD_HHMMSS_slug.py"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug      = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")[:30]
    filename  = f"effect_{timestamp}_{slug}.py"

    out_dir = Path(__file__).parent.parent / "effects" / "ai_generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(code, encoding="utf-8")
    return out_path


# ── Cost estimator ────────────────────────────────────────────────────────────

def estimate_cost(system_text: str, user_text: str, has_image: bool, model: str) -> float:
    """Rough USD cost estimate (pre-call)."""
    prompt_tokens = len(system_text) // 4 + len(user_text) // 4
    image_tokens  = 1600 if has_image else 0
    total_in  = prompt_tokens + image_tokens
    total_out = 1200  # estimated output tokens

    # Pricing per million tokens (approximate, as of 2026)
    if "opus" in model:
        cost = (total_in * 15 + total_out * 75) / 1_000_000
    elif "sonnet" in model:
        cost = (total_in * 3 + total_out * 15) / 1_000_000
    else:
        cost = (total_in * 3 + total_out * 15) / 1_000_000

    return cost, total_in, total_out


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="¥ØUSUK€ AI Effect Generator — Uses Claude to write new visual effects"
    )

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--from-frame",     metavar="PATH",
                            help="Generate effect inspired by a video frame image")
    mode_group.add_argument("--describe",       metavar="TEXT",
                            help="Describe the effect in natural language")
    mode_group.add_argument("--extend",         metavar="EFFECT_NAME",
                            help="Extend an existing built-in effect (e.g. neon_contour)")
    mode_group.add_argument("--from-canonical", metavar="PATH",
                            help="Generate from canonical_effects.json entry")

    parser.add_argument("--id",    type=int, default=0,
                        help="Canonical effect ID to use (with --from-canonical, default: 0)")
    parser.add_argument("--name",  metavar="NAME",
                        help="Override effect name")
    parser.add_argument("--model", default="claude-opus-4-7",
                        help="Claude model (default: claude-opus-4-7)")

    args = parser.parse_args()

    print(f"\n=== ¥ØUSUK€ AI Effect Generator ===\n")

    # ── Pre-flight ──────────────────────────────────────────────────────────
    if not preflight_check(args):
        sys.exit(1)

    # Determine mode string
    if args.from_frame:    mode_str = f"from_frame ({args.from_frame})"
    elif args.describe:    mode_str = "describe"
    elif args.extend:      mode_str = f"extend ({args.extend})"
    else:                  mode_str = f"from_canonical (id={args.id})"

    # ── Retry loop ─────────────────────────────────────────────────────────
    max_retries  = 3
    prior_error  = None
    prior_code   = None
    generated_code = None

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"\n  Attempt {attempt}/{max_retries}: Feeding error back to Claude...")
            print(f"  Previous error: \"{prior_error}\"")

        # Step 1: Build prompt
        t0 = time.time()
        print(f"\n[1/4] Preparing prompt (mode: {mode_str})...", end="", flush=True)
        messages, frame_b64 = build_prompt(args, prior_error, prior_code)
        t1 = time.time()
        print(f"  {t1 - t0:.1f}s")

        # Step 2: Estimate cost + call Claude
        user_text_flat = (
            messages[0]["content"] if isinstance(messages[0]["content"], str)
            else " ".join(c.get("text", "") for c in messages[0]["content"]
                          if isinstance(c, dict))
        )
        cost_usd, total_in, total_out = estimate_cost(
            _SYSTEM_PROMPT, user_text_flat, frame_b64 is not None, args.model
        )
        print(f"[2/4] Calling Claude {args.model}...")
        print(f"  → Tokens sent: ~{total_in} (prompt)"
              + (" + 1 image" if frame_b64 else "")
              + f"  (est. ${cost_usd:.3f} USD)")
        print(f"  → Waiting for response", end="", flush=True)

        t2 = time.time()
        try:
            raw = call_claude(messages, _SYSTEM_PROMPT, args.model)
        except KeyboardInterrupt:
            print("\n  Interrupted.")
            sys.exit(1)
        except Exception as e:
            print(f"\n  ERROR calling Claude: {e}")
            sys.exit(1)

        t3 = time.time()
        print(f"  {t3 - t2:.1f}s")

        code = extract_code(raw)

        # Step 3: Validate
        print(f"[3/4] Validating generated code...")
        tv0 = time.time()

        valid, error_rule, error_message = validate_generated_code(code)

        tv1 = time.time()
        if valid:
            print(f"  → Syntax check:          PASS")
            print(f"  → Required exports:      PASS (EFFECT_META ✓, fx_function ✓)")
            print(f"  → Test run (blank frame): PASS (returned 640×480×3 uint8)")
            print(f"  → Validation total:      {tv1 - tv0:.1f}s")
            generated_code = code
            break
        else:
            print(f"\n  VALIDATION FAILED:")
            print(f"  Rule:  {error_rule}")
            print(f"  Error: {error_message}")
            print(f"  Retry: {attempt}/{max_retries}")
            prior_error = f"{error_rule}: {error_message}"
            prior_code  = code

    if generated_code is None:
        print(f"\n  FAILED after {max_retries} attempts. Last error: {prior_error}")
        sys.exit(1)

    # Step 4: Save
    print(f"[4/4] Saving effect...")
    # Extract name from EFFECT_META if not overridden
    effect_name = args.name
    if not effect_name:
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
                tmp.write(generated_code)
                tmp_path = tmp.name
            spec   = importlib.util.spec_from_file_location("_name_extract", tmp_path)
            m      = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            effect_name = m.EFFECT_META.get("name", "Generated Effect")
            os.unlink(tmp_path)
        except Exception:
            effect_name = "Generated Effect"

    out_path  = save_effect(generated_code, effect_name)
    file_size = out_path.stat().st_size / 1024
    print(f"  → {out_path}  ({file_size:.1f} KB)")

    print(f"\n  Done. Restart visuals.py to load the new effect:")
    print(f"    python standalone/visuals.py --mode webcam --audio mic")


if __name__ == "__main__":
    main()
