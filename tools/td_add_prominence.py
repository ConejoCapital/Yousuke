#!/usr/bin/env python3
"""
Add audio-driven dynamic opacity (prominence pulsing) to all effects.

For each of the 43 effect baseCOMPs, inserts a levelTOP between the last
effect node and out1:
  - Opacity: 0.6 + <audio_band> * 0.4
    - Effects 0-13:  bass-driven
    - Effects 14-28: mids-driven
    - Effects 29-42: highs-driven
  - Brightness: 1.0 + beat * 0.3 (30% beat flash)

This makes each effect breathe with the music.

Usage:
  python3 tools/td_add_prominence.py           # Add to all effects
  python3 tools/td_add_prominence.py --dry-run # Print plan
"""

import json
import sys
import time
import urllib.request

MCP_URL = "http://localhost:40404/mcp"
_REQ_ID = 0


def td_call(method, arguments=None, retries=2):
    """Call a twozero MCP tool and return text content."""
    global _REQ_ID
    _REQ_ID += 1
    payload = {
        "jsonrpc": "2.0",
        "id": _REQ_ID,
        "method": "tools/call",
        "params": {"name": method, "arguments": arguments or {}},
    }
    data = json.dumps(payload).encode("utf-8")
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                MCP_URL, data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            content = result.get("result", {}).get("content", [])
            texts = [c["text"] for c in content if c.get("type") == "text"]
            return "\n".join(texts)
        except Exception as e:
            if attempt == retries:
                raise
            time.sleep(1)


def td_exec(code):
    """Execute Python code inside TouchDesigner."""
    return td_call("td_execute_python", {"code": code})


# All 43 effects in router order
ALL_EFFECTS = [
    # Originals (0-20)
    "fx_confetti_storm", "fx_thermal_posterize", "fx_fire_scanlines",
    "fx_echo_trail", "fx_rainbow_echo", "fx_liquify_wave", "fx_pixel_glitch",
    "fx_datamosh", "fx_rgb_explode", "fx_kaleidoscope",
    "fx_plasma_tentacles", "fx_strobe_invert", "fx_pixelate_cascade",
    "fx_glitch_tear", "fx_radial_zoom", "fx_neon_skeleton",
    "fx_solarize_pulse", "fx_triangle_shatter", "fx_feedback_spiral",
    "fx_matrix_rain", "fx_chromatic_double",
    # Mutations (21-41)
    "fx_mut_acid_confetti", "fx_mut_xray_thermal", "fx_mut_ice_scanlines",
    "fx_mut_echo_kaleidoscope", "fx_mut_rainbow_shatter", "fx_mut_liquify_vortex",
    "fx_mut_pixel_rain", "fx_mut_datamosh_strobe", "fx_mut_rgb_spiral",
    "fx_mut_hyper_kaleidoscope", "fx_mut_plasma_web", "fx_mut_strobe_posterize",
    "fx_mut_cascade_mirror", "fx_mut_glitch_feedback", "fx_mut_radial_neon",
    "fx_mut_skeleton_fire", "fx_mut_negative_solarize", "fx_mut_voronoi_feedback",
    "fx_mut_double_spiral", "fx_mut_kanji_matrix", "fx_mut_chromatic_prism",
    # Canon shards (42)
    "fx_canon_shards",
]


def get_audio_band(idx):
    """Return audio band expression for the given effect index."""
    if idx <= 13:
        return "bass"
    elif idx <= 28:
        return "mids"
    else:
        return "highs"


def add_prominence(idx, name, dry_run=False):
    """Insert a levelTOP with audio-driven opacity into an effect baseCOMP."""
    comp_path = f"/project1/{name}"
    band = get_audio_band(idx)
    band_expr = f"op('/project1/audio_analysis/out1')['{band}']"

    print(f"  [{idx:2d}] {name} ({band}-driven)...", end=" ")

    if dry_run:
        print("DRY RUN")
        return True

    # Check if comp exists and find the node connected to out1
    result = td_exec(f"""
comp = op('{comp_path}')
if comp is None:
    print('MISSING')
else:
    out1 = op('{comp_path}/out1')
    if out1 is None:
        print('NO_OUT1')
    else:
        # Check if levelTOP already exists
        existing = op('{comp_path}/prominence')
        if existing is not None:
            print('ALREADY_EXISTS')
        else:
            # Find what's connected to out1's input
            conns = out1.inputConnectors[0].connections
            if conns:
                source = conns[0].owner.path
                print(f'SOURCE:{{source}}')
            else:
                print('NO_SOURCE')
""")

    status = result.strip().split("\n")[-1] if result.strip() else "no response"

    if "MISSING" in status or "NO_OUT1" in status:
        print(f"SKIP ({status})")
        return False

    if "ALREADY_EXISTS" in status:
        print("SKIP (already has prominence)")
        return True

    if "NO_SOURCE" in status:
        print("SKIP (out1 has no input)")
        return False

    # Extract source path
    source_path = status.replace("SOURCE:", "")

    # Insert levelTOP between source and out1
    td_exec(f"""
comp = op('{comp_path}')
out1 = op('{comp_path}/out1')
source = op('{source_path}')

# Create levelTOP
level = comp.create(levelTOP, 'prominence')
level.nodeX = 200
level.nodeY = 0

# Disconnect out1 from its current source
out1.inputConnectors[0].disconnect()

# Wire: source -> levelTOP -> out1
level.inputConnectors[0].connect(source)
out1.inputConnectors[0].connect(level)

# Set opacity expression: 0.6 + band * 0.4
level.par.opacity.mode = ParMode.EXPRESSION
level.par.opacity.expr = "0.6 + {band_expr} * 0.4"

# Set brightness beat flash: 1.0 + beat * 0.3
level.par.brightness1.mode = ParMode.EXPRESSION
level.par.brightness1.expr = "1.0 + op('/project1/audio_analysis/out1')['beat'] * 0.3"

print('OK')
""")
    time.sleep(0.05)

    print("OK")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Add audio-driven prominence to all effects")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    print("=" * 60)
    print("YOUSUKE Audio Prominence Pulsing")
    print(f"Adding levelTOPs to {len(ALL_EFFECTS)} effects")
    print("  Effects  0-13: bass-driven opacity")
    print("  Effects 14-28: mids-driven opacity")
    print("  Effects 29-42: highs-driven opacity")
    print("  All: beat flash on brightness (+30%)")
    print("=" * 60)

    if not args.dry_run:
        try:
            result = td_call("td_get_focus")
            print(f"\nTD connected: {result.split(chr(10))[0]}")
        except Exception as e:
            print(f"ERROR: Cannot connect to TouchDesigner MCP: {e}")
            sys.exit(1)

    print()
    added = 0
    for idx, name in enumerate(ALL_EFFECTS):
        try:
            if add_prominence(idx, name, args.dry_run):
                added += 1
        except Exception as e:
            print(f"FAIL: {e}")

    print(f"\n{'=' * 60}")
    print(f"Prominence added to {added}/{len(ALL_EFFECTS)} effects")
    print("=" * 60)


if __name__ == "__main__":
    main()
