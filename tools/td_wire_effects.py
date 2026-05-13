#!/usr/bin/env python3
"""Wire all 21 new effects to the effect_router in TouchDesigner."""

import json
import urllib.request

MCP_URL = "http://localhost:40404/mcp"
_REQ_ID = 0


def td_exec(code):
    global _REQ_ID
    _REQ_ID += 1
    payload = {
        "jsonrpc": "2.0",
        "id": _REQ_ID,
        "method": "tools/call",
        "params": {"name": "td_execute_python", "arguments": {"code": code}},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(MCP_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    content = result.get("result", {}).get("content", [])
    return "\n".join(c["text"] for c in content if c.get("type") == "text")


EFFECTS = [
    "fx_confetti_storm", "fx_thermal_posterize", "fx_fire_scanlines",
    "fx_echo_trail", "fx_rainbow_echo", "fx_liquify_wave", "fx_pixel_glitch",
    "fx_datamosh", "fx_rgb_explode", "fx_kaleidoscope",
    "fx_plasma_tentacles", "fx_strobe_invert", "fx_pixelate_cascade",
    "fx_glitch_tear", "fx_radial_zoom", "fx_neon_skeleton",
    "fx_solarize_pulse", "fx_triangle_shatter", "fx_feedback_spiral",
    "fx_matrix_rain", "fx_chromatic_double",
]


def main():
    # Wire each effect using outputConnectors method (which auto-expands switch inputs)
    for i, name in enumerate(EFFECTS):
        idx = 7 + i
        code = (
            f"router = op('/project1/effect_router')\n"
            f"fx = op('/project1/{name}')\n"
            f"if fx is None:\n"
            f"    print('MISSING: {name}')\n"
            f"else:\n"
            f"    try:\n"
            f"        fx.outputConnectors[0].connect(router.inputConnectors[{idx}])\n"
            f"        print('[{idx}] {name} -> effect_router OK')\n"
            f"    except Exception as e:\n"
            f"        print(f'[{idx}] {name} FAILED: {{e}}')\n"
        )
        result = td_exec(code)
        print(result.strip().split("\n")[0])

    # Verify final state
    result = td_exec(
        "router = op('/project1/effect_router')\n"
        "connected = 0\n"
        "for i, conn in enumerate(router.inputConnectors):\n"
        "    if conn.connections:\n"
        "        connected += 1\n"
        "        names = [c.owner.path.split('/')[-1] for c in conn.connections]\n"
        "        print(f'  [{i:2d}] {names[0]}')\n"
        "print(f'\\nTotal: {connected} inputs connected')\n"
    )
    print(result)


if __name__ == "__main__":
    main()
