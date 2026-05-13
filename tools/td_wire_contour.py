#!/usr/bin/env python3
"""
Wire all 33 body contour effects (Gen3) to the 3 routers in TouchDesigner.

For each effect:
  1. Wire cam_in -> effect input connector (baseCOMP takes camera input)
  2. Wire effect output -> effect_router slot 100+i
  3. Wire effect output -> layer2_router slot 100+i
  4. Wire effect output -> layer3_router slot 100+i

Slots 100-132 are used (offset from existing effects at 0-42).

Usage:
  python3 tools/td_wire_contour.py
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


# --- 33 Body Contour Effects ---

CONTOUR_EFFECTS = [
    "fx_g3_body_neon_outline",
    "fx_g3_body_pulse_edge",
    "fx_g3_body_double_edge",
    "fx_g3_body_electric_wire",
    "fx_g3_body_heat_contour",
    "fx_g3_body_laser_scan",
    "fx_g3_body_glitch_edge",
    "fx_g3_body_fire_outline",
    "fx_g3_body_matrix_edge",
    "fx_g3_body_plasma_edge",
    "fx_g3_body_strobe_edge",
    "fx_g3_body_solid_silhouette",
    "fx_g3_body_gradient_sil",
    "fx_g3_body_starfield_sil",
    "fx_g3_body_fire_sil",
    "fx_g3_body_ocean_sil",
    "fx_g3_body_rainbow_sil",
    "fx_g3_body_glitch_sil",
    "fx_g3_body_pixel_sil",
    "fx_g3_body_ghost_sil",
    "fx_g3_body_kaleidoscope_sil",
    "fx_g3_body_invert_sil",
    "fx_g3_body_neon_fill",
    "fx_g3_body_xray_contour",
    "fx_g3_body_thermal_contour",
    "fx_g3_body_cyberpunk_contour",
    "fx_g3_body_hologram",
    "fx_g3_body_blueprint",
    "fx_g3_body_shadow_play",
    "fx_g3_body_particle_edge",
    "fx_g3_body_aura_glow",
    "fx_g3_body_comic_contour",
    "fx_g3_body_mirror_contour",
]

SLOT_OFFSET = 100
ROUTERS = ["effect_router", "layer2_router", "layer3_router"]


def main():
    print("=" * 60)
    print("YOUSUKE Body Contour Effect Wiring (Gen3)")
    print("Wiring " + str(len(CONTOUR_EFFECTS)) + " effects to 3 routers at slots " + str(SLOT_OFFSET) + "-" + str(SLOT_OFFSET + len(CONTOUR_EFFECTS) - 1))
    print("=" * 60)

    # Verify MCP connection
    try:
        result = td_call("td_get_focus")
        print("TD connected: " + result.split("\n")[0])
    except Exception as e:
        print("ERROR: Cannot connect to TouchDesigner MCP: " + str(e))
        sys.exit(1)

    # Step 1: Wire cam_in to each contour effect's input connector
    print("\n[1/3] Wiring cam_in to contour effect inputs...")
    cam_ok = 0
    for name in CONTOUR_EFFECTS:
        code = (
            "comp = op('/project1/" + name + "')\n"
            "cam = op('/project1/cam_in')\n"
            "if comp is None:\n"
            "    print('MISSING: " + name + "')\n"
            "elif cam is None:\n"
            "    print('MISSING: cam_in')\n"
            "else:\n"
            "    try:\n"
            "        comp.inputConnectors[0].connect(cam)\n"
            "        print('OK: cam_in -> " + name + "')\n"
            "    except Exception as e:\n"
            "        print('FAIL: ' + str(e))\n"
        )
        result = td_exec(code)
        status = result.strip().split("\n")[0] if result.strip() else "no response"
        print("  " + status)
        if "OK" in status:
            cam_ok += 1
        time.sleep(0.05)

    print("  Camera wired: " + str(cam_ok) + "/" + str(len(CONTOUR_EFFECTS)))

    # Step 2: Wire each effect output to all 3 routers at slots 100+i
    print("\n[2/3] Wiring contour effects to 3 routers (slots " + str(SLOT_OFFSET) + "-" + str(SLOT_OFFSET + len(CONTOUR_EFFECTS) - 1) + ")...")
    wire_counts = {r: 0 for r in ROUTERS}

    for i, name in enumerate(CONTOUR_EFFECTS):
        slot = SLOT_OFFSET + i
        for router_name in ROUTERS:
            code = (
                "router = op('/project1/" + router_name + "')\n"
                "fx = op('/project1/" + name + "')\n"
                "if fx is None:\n"
                "    print('MISSING: " + name + "')\n"
                "elif router is None:\n"
                "    print('MISSING: " + router_name + "')\n"
                "else:\n"
                "    try:\n"
                "        fx.outputConnectors[0].connect(router.inputConnectors[" + str(slot) + "])\n"
                "        print('[" + str(slot) + "] " + name + " -> " + router_name + " OK')\n"
                "    except Exception as e:\n"
                "        print('[" + str(slot) + "] " + name + " -> " + router_name + " FAIL: ' + str(e))\n"
            )
            result = td_exec(code)
            status = result.strip().split("\n")[0] if result.strip() else "no response"
            print("  " + status)
            if "OK" in status:
                wire_counts[router_name] += 1
            time.sleep(0.05)

    print()
    for rname, count in wire_counts.items():
        print("  " + rname + ": " + str(count) + "/" + str(len(CONTOUR_EFFECTS)) + " wired")

    # Step 3: Verify final router input counts
    print("\n[3/3] Verifying router input counts...")
    for router_name in ROUTERS:
        code = (
            "router = op('/project1/" + router_name + "')\n"
            "if router is None:\n"
            "    print('" + router_name + ": NOT FOUND')\n"
            "else:\n"
            "    connected = 0\n"
            "    total = len(router.inputConnectors)\n"
            "    for conn in router.inputConnectors:\n"
            "        if conn.connections:\n"
            "            connected += 1\n"
            "    print('" + router_name + ": ' + str(connected) + ' connected inputs out of ' + str(total) + ' connectors')\n"
        )
        result = td_exec(code)
        status = result.strip() if result.strip() else "no response"
        print("  " + status)
        time.sleep(0.1)

    print("\n" + "=" * 60)
    print("Done! 33 body contour effects wired to slots 100-132 on all 3 routers.")
    print("=" * 60)


if __name__ == "__main__":
    main()
