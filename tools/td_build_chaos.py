#!/usr/bin/env python3
"""
Build the YOUSUKE Chaos Engine in TouchDesigner.

Inserts per-layer transform + HSV adjust nodes into the compositing chain,
then writes a chaos randomization script to auto_rotate.

State space: ~10^95 unique visual combinations.
Time to exhaust at 1.5s/switch: ~10^77 universe lifetimes.

Usage:
  python3 tools/td_build_chaos.py
"""

import json
import os
import sys
import time
import urllib.request

MCP_URL = "http://localhost:40404/mcp"
_REQ_ID = 0


def td_call(method, arguments=None, retries=2):
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
    return td_call("td_execute_python", {"code": code})


def td_create_op(parent, optype, name):
    return td_call("td_create_operator", {"parent": parent, "type": optype, "name": name})


def td_set_pars(path, pars):
    return td_call("td_set_operator_pars", {"path": path, "pars": pars})


def td_write_dat(path, text):
    return td_call("td_write_dat", {"path": path, "text": text})


def main():
    print("=" * 60)
    print("YOUSUKE CHAOS ENGINE BUILDER")
    print("=" * 60)

    # Verify connection
    try:
        result = td_call("td_get_focus")
        print("TD connected:", result.split("\n")[0])
    except Exception as e:
        print("ERROR: Cannot connect to TouchDesigner MCP:", e)
        sys.exit(1)

    # ── Step 1: Create per-layer transform nodes ──
    print("\n[1/5] Creating per-layer transform nodes...")
    for i in range(1, 4):
        name = "chaos_xform" + str(i)
        td_exec("x = op('/project1/" + name + "'); x.destroy() if x else None")
        time.sleep(0.1)
        td_create_op("/project1", "transformTOP", name)
        td_set_pars("/project1/" + name, {"resolutionw": "1280", "resolutionh": "720"})
        print("  Created", name)
        time.sleep(0.1)

    # ── Step 2: Create per-layer HSV adjust nodes ──
    print("\n[2/5] Creating per-layer HSV adjust nodes...")
    for i in range(1, 4):
        name = "chaos_hsv" + str(i)
        td_exec("x = op('/project1/" + name + "'); x.destroy() if x else None")
        time.sleep(0.1)
        td_create_op("/project1", "hsvadjustTOP", name)
        print("  Created", name)
        time.sleep(0.1)

    # ── Step 3: Wire chaos nodes into compositing chain ──
    print("\n[3/5] Wiring chaos nodes into compositing chain...")

    # Layer 1: effect_router -> chaos_xform1 -> chaos_hsv1 -> blend_add1[0]
    td_exec("""
er = op("/project1/effect_router")
xf1 = op("/project1/chaos_xform1")
hsv1 = op("/project1/chaos_hsv1")
blend1 = op("/project1/blend_add1")

# Disconnect effect_router from blend_add1
for ic in blend1.inputConnectors:
    for c in ic.connections:
        if c.owner.name == "effect_router":
            c.disconnect()

# Wire chain
xf1.inputConnectors[0].connect(er)
hsv1.inputConnectors[0].connect(xf1)
blend1.inputConnectors[0].connect(hsv1)

xf1.nodeX = 400; xf1.nodeY = 200
hsv1.nodeX = 600; hsv1.nodeY = 200
print("Layer 1: effect_router -> chaos_xform1 -> chaos_hsv1 -> blend_add1")
""")
    time.sleep(0.2)

    # Layer 2: layer2_opacity -> chaos_xform2 -> chaos_hsv2 -> blend_add1[1]
    td_exec("""
l2op = op("/project1/layer2_opacity")
xf2 = op("/project1/chaos_xform2")
hsv2 = op("/project1/chaos_hsv2")
blend1 = op("/project1/blend_add1")

for ic in blend1.inputConnectors:
    for c in ic.connections:
        if c.owner.name == "layer2_opacity":
            c.disconnect()

xf2.inputConnectors[0].connect(l2op)
hsv2.inputConnectors[0].connect(xf2)
blend1.inputConnectors[1].connect(hsv2)

xf2.nodeX = 400; xf2.nodeY = 0
hsv2.nodeX = 600; hsv2.nodeY = 0
print("Layer 2: layer2_opacity -> chaos_xform2 -> chaos_hsv2 -> blend_add1")
""")
    time.sleep(0.2)

    # Layer 3: layer3_opacity -> chaos_xform3 -> chaos_hsv3 -> blend_add2[1]
    td_exec("""
l3op = op("/project1/layer3_opacity")
xf3 = op("/project1/chaos_xform3")
hsv3 = op("/project1/chaos_hsv3")
blend2 = op("/project1/blend_add2")

for ic in blend2.inputConnectors:
    for c in ic.connections:
        if c.owner.name == "layer3_opacity":
            c.disconnect()

xf3.inputConnectors[0].connect(l3op)
hsv3.inputConnectors[0].connect(xf3)
blend2.inputConnectors[1].connect(hsv3)

xf3.nodeX = 400; xf3.nodeY = -200
hsv3.nodeX = 600; hsv3.nodeY = -200
print("Layer 3: layer3_opacity -> chaos_xform3 -> chaos_hsv3 -> blend_add2")
""")
    time.sleep(0.2)

    # ── Step 4: Write chaos engine script to auto_rotate ──
    print("\n[4/5] Writing chaos engine script to auto_rotate...")
    script_path = os.path.join(os.path.dirname(__file__), "chaos_engine_script.py")
    with open(script_path, "r") as f:
        chaos_script = f.read()
    td_write_dat("/project1/auto_rotate", chaos_script)
    print("  Chaos script written to /project1/auto_rotate")

    # ── Step 5: Verify ──
    print("\n[5/5] Verifying chain...")
    result = td_exec("""
checks = [
    ("chaos_xform1", "effect_router"),
    ("chaos_hsv1", "chaos_xform1"),
    ("chaos_xform2", "layer2_opacity"),
    ("chaos_hsv2", "chaos_xform2"),
    ("chaos_xform3", "layer3_opacity"),
    ("chaos_hsv3", "chaos_xform3"),
]
ok = 0
for node_name, expected_src in checks:
    node = op("/project1/" + node_name)
    if node and node.inputConnectors[0].connections:
        actual = node.inputConnectors[0].connections[0].owner.name
        if actual == expected_src:
            ok += 1
            print("  OK: " + node_name + " <- " + actual)
        else:
            print("  WRONG: " + node_name + " <- " + actual + " (expected " + expected_src + ")")
    else:
        print("  DISCONNECTED: " + node_name)

b1 = op("/project1/blend_add1")
b1_ins = []
for ic in b1.inputConnectors:
    if ic.connections:
        b1_ins.append(ic.connections[0].owner.name)
print("  blend_add1 inputs: " + str(b1_ins))

b2 = op("/project1/blend_add2")
b2_ins = []
for ic in b2.inputConnectors:
    if ic.connections:
        b2_ins.append(ic.connections[0].owner.name)
print("  blend_add2 inputs: " + str(b2_ins))

print("  FPS: " + str(me.time.rate))
print("  Chain checks: " + str(ok) + "/6 OK")
""")
    print(result)

    # Save
    td_exec("project.save(); print('Project saved')")

    print("\n" + "=" * 60)
    print("CHAOS ENGINE ONLINE")
    print()
    print("Per-switch randomization:")
    print("  - 3 layers x 100 effects (discrete)")
    print("  - 3 layers x rotation 0-360 (continuous)")
    print("  - 3 layers x flip X/Y (binary)")
    print("  - 3 layers x scale 0.85-1.15 (continuous)")
    print("  - 3 layers x hue offset 0-360 (continuous)")
    print("  - 3 layers x saturation 0.5-1.5 (continuous)")
    print("  - 2 layers x opacity 0.3-1.0 (continuous)")
    print()
    print("Total state space: ~10^95 unique combinations")
    print("Time to exhaust: ~10^77 universe lifetimes")
    print("=" * 60)


if __name__ == "__main__":
    main()
