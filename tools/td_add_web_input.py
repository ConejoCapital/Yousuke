#!/usr/bin/env python3
"""Add a webrenderTOP as a new effect input in TouchDesigner via MCP."""

import json
import urllib.request
import time

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


WEB_URL = "https://spitballs.karynnakamura.com/?id=10"
NODE_NAME = "fx_spitballs_web"


def main():
    # Step 1: Create the webrenderTOP
    print("=== Creating webrenderTOP ===")
    code = (
        "p = op('/project1')\n"
        "existing = op('/project1/" + NODE_NAME + "')\n"
        "if existing:\n"
        "    existing.destroy()\n"
        "    print('Destroyed old node')\n"
        "web = p.create(td.webrenderTOP, '" + NODE_NAME + "')\n"
        "web.par.url = '" + WEB_URL + "'\n"
        "web.par.outputresolution = 'custom'\n"
        "web.par.resolutionw = 1280\n"
        "web.par.resolutionh = 720\n"
        "web.par.resmult = False\n"
        "web.par.active = True\n"
        "web.par.maxrenderrate = 60\n"
        "web.par.alwayscook = True\n"
        "web.nodeX = 800\n"
        "web.nodeY = -600\n"
        "print('Created: ' + web.path)\n"
        "print('URL: ' + str(web.par.url))\n"
        "print('Resolution: ' + str(web.par.resolutionw) + 'x' + str(web.par.resolutionh))\n"
        "print('Active: ' + str(web.par.active.val))\n"
    )
    result = td_exec(code)
    print(result)

    time.sleep(2)

    # Step 2: Create a prominence levelTOP (matching the pattern of other effects)
    print("\n=== Creating prominence levelTOP ===")
    level_name = NODE_NAME + "_level"
    code = (
        "p = op('/project1')\n"
        "existing = op('/project1/" + level_name + "')\n"
        "if existing:\n"
        "    existing.destroy()\n"
        "lvl = p.create(levelTOP, '" + level_name + "')\n"
        "lvl.par.opacity = 0.85\n"
        "lvl.nodeX = 950\n"
        "lvl.nodeY = -600\n"
        "web = op('/project1/" + NODE_NAME + "')\n"
        "web.outputConnectors[0].connect(lvl.inputConnectors[0])\n"
        "print('Created level: ' + lvl.path)\n"
        "print('Wired: ' + web.path + ' -> ' + lvl.path)\n"
    )
    result = td_exec(code)
    print(result)

    # Step 3: Wire to all 3 routers (find first empty slot)
    print("\n=== Wiring to routers ===")
    routers = ["effect_router", "layer2_router", "layer3_router"]
    for router_name in routers:
        code = (
            "router = op('/project1/" + router_name + "')\n"
            "lvl = op('/project1/" + level_name + "')\n"
            "if router is None:\n"
            "    print('MISSING: " + router_name + "')\n"
            "elif lvl is None:\n"
            "    print('MISSING: " + level_name + "')\n"
            "else:\n"
            "    target = -1\n"
            "    for i, c in enumerate(router.inputConnectors):\n"
            "        if not c.connections:\n"
            "            target = i\n"
            "            break\n"
            "    if target < 0:\n"
            "        target = len(router.inputConnectors)\n"
            "    lvl.outputConnectors[0].connect(router.inputConnectors[target])\n"
            "    print('" + router_name + " slot [' + str(target) + '] <- " + level_name + " OK')\n"
        )
        result = td_exec(code)
        print(result)

    # Step 4: Verify (auto_rotate dynamically counts connected inputs)
    print("\n=== Verifying ===")
    code = (
        "web = op('/project1/" + NODE_NAME + "')\n"
        "print('Web size: ' + str(web.width) + 'x' + str(web.height))\n"
        "r = op('/project1/effect_router')\n"
        "total = sum(1 for c in r.inputConnectors if c.connections)\n"
        "print('Total effects in rotation: ' + str(total))\n"
    )
    result = td_exec(code)
    print(result)

    print("\n=== Done! ===")
    print("Spitballs web art is now an effect in all 3 routers.")
    print("Auto-rotate dynamically includes it via get_num_effects().")


if __name__ == "__main__":
    main()
