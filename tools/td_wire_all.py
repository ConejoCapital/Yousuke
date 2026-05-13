#!/usr/bin/env python3
"""
Wire all 43 effects (21 original + 21 mutations + fx_canon_shards) to the
effect_router switchTOP in TouchDesigner.

Disconnects all current inputs first, then wires in order:
  Slots 0-20:  Original 21 effects
  Slots 21-41: 21 mutation effects
  Slot 42:     fx_canon_shards

Also wires cam_in to each mutation's input connector.

Usage:
  python3 tools/td_wire_all.py           # Wire everything
  python3 tools/td_wire_all.py --dry-run # Print plan without executing
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


# --- Effect lists ---

ORIGINALS = [
    "fx_confetti_storm", "fx_thermal_posterize", "fx_fire_scanlines",
    "fx_echo_trail", "fx_rainbow_echo", "fx_liquify_wave", "fx_pixel_glitch",
    "fx_datamosh", "fx_rgb_explode", "fx_kaleidoscope",
    "fx_plasma_tentacles", "fx_strobe_invert", "fx_pixelate_cascade",
    "fx_glitch_tear", "fx_radial_zoom", "fx_neon_skeleton",
    "fx_solarize_pulse", "fx_triangle_shatter", "fx_feedback_spiral",
    "fx_matrix_rain", "fx_chromatic_double",
]

MUTATIONS = [
    "fx_mut_acid_confetti", "fx_mut_xray_thermal", "fx_mut_ice_scanlines",
    "fx_mut_echo_kaleidoscope", "fx_mut_rainbow_shatter", "fx_mut_liquify_vortex",
    "fx_mut_pixel_rain", "fx_mut_datamosh_strobe", "fx_mut_rgb_spiral",
    "fx_mut_hyper_kaleidoscope", "fx_mut_plasma_web", "fx_mut_strobe_posterize",
    "fx_mut_cascade_mirror", "fx_mut_glitch_feedback", "fx_mut_radial_neon",
    "fx_mut_skeleton_fire", "fx_mut_negative_solarize", "fx_mut_voronoi_feedback",
    "fx_mut_double_spiral", "fx_mut_kanji_matrix", "fx_mut_chromatic_prism",
]

ALL_EFFECTS = ORIGINALS + MUTATIONS + ["fx_canon_shards"]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Wire all 43 effects to effect_router")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    print("=" * 60)
    print("YOUSUKE Full Effect Wiring")
    print(f"Wiring {len(ALL_EFFECTS)} effects to effect_router")
    print("=" * 60)

    if args.dry_run:
        for i, name in enumerate(ALL_EFFECTS):
            print(f"  [{i:2d}] {name}")
        print("\nDRY RUN: no changes made")
        return

    # Verify MCP connection
    try:
        result = td_call("td_get_focus")
        print(f"TD connected: {result.split(chr(10))[0]}")
    except Exception as e:
        print(f"ERROR: Cannot connect to TouchDesigner MCP: {e}")
        sys.exit(1)

    # Step 1: Disconnect all current router inputs
    print("\n[1/3] Disconnecting all current router inputs...")
    td_exec("""
router = op('/project1/effect_router')
if router is None:
    print('ERROR: effect_router not found')
else:
    for conn in router.inputConnectors:
        for c in conn.connections:
            c.disconnect()
    print('All inputs disconnected')
""")
    time.sleep(0.3)

    # Step 2: Wire cam_in to each mutation's input connector
    print("\n[2/3] Wiring cam_in to mutation inputs...")
    for name in MUTATIONS:
        result = td_exec(f"""
comp = op('/project1/{name}')
cam = op('/project1/cam_in')
if comp is None:
    print('MISSING: {name}')
elif cam is None:
    print('MISSING: cam_in')
else:
    try:
        comp.inputConnectors[0].connect(cam)
        print('OK: cam_in -> {name}')
    except Exception as e:
        print(f'FAIL: {{e}}')
""")
        status = result.strip().split("\n")[0] if result.strip() else "no response"
        print(f"  {status}")
        time.sleep(0.05)

    # Step 3: Wire all effects to router in order
    print("\n[3/3] Wiring all effects to router...")
    wired = 0
    for i, name in enumerate(ALL_EFFECTS):
        result = td_exec(f"""
router = op('/project1/effect_router')
fx = op('/project1/{name}')
if fx is None:
    print('MISSING: {name}')
else:
    try:
        fx.outputConnectors[0].connect(router.inputConnectors[{i}])
        print('[{i:2d}] {name} -> effect_router OK')
    except Exception as e:
        print(f'[{i:2d}] {name} FAIL: {{e}}')
""")
        status = result.strip().split("\n")[0] if result.strip() else "no response"
        print(f"  {status}")
        if "OK" in status:
            wired += 1
        time.sleep(0.05)

    # Verify final state
    print(f"\n{'=' * 60}")
    print(f"Wired {wired}/{len(ALL_EFFECTS)} effects")
    print()

    result = td_exec("""
router = op('/project1/effect_router')
connected = 0
for i, conn in enumerate(router.inputConnectors):
    if conn.connections:
        connected += 1
        names = [c.owner.path.split('/')[-1] for c in conn.connections]
        print(f'  [{i:2d}] {names[0]}')
print(f'\\nTotal: {connected} inputs connected')
""")
    print(result)

    # Update active_effect range info
    td_exec("""
ae = op('/project1/active_effect')
if ae is not None:
    print('active_effect: idx=' + str(ae.par.value0.eval()) + ', auto=' + str(ae.par.value1.eval()))
""")

    print("=" * 60)
    print("Done! Press 0 to auto-rotate through all effects.")


if __name__ == "__main__":
    main()
