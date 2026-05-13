#!/usr/bin/env python3
"""
YOUSUKE — Comprehensive wiring of ALL effects to ALL 3 routers.

Fixes critical issues from prior scripts:
  1. td_wire_all.py only wired to effect_router (layer2/layer3 were empty)
  2. Gen3 57 effects had NO wiring script at all
  3. Non-contiguous slots (0-42, 100-132) caused switchTOP black frames
  4. cam_in was not connected to Gen3 effects

After this script runs:
  Slots 0-20:   21 original effects
  Slots 21-41:  21 mutation effects
  Slot 42:      fx_canon_shards
  Slots 43-99:  57 Gen 3 effects
  Slots 100-132: 33 body contour effects
  Slot 133:     fx_spitballs_web (if present)

  ALL slots are contiguous and identical on all 3 routers.
  cam_in is wired to all effects that need camera input.

Usage:
  python3 tools/td_wire_everything.py           # Wire everything
  python3 tools/td_wire_everything.py --dry-run # Print plan only
  python3 tools/td_wire_everything.py --verify  # Only verify, don't rewire
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


def td_write_dat(path, text):
    """Write text content to a DAT."""
    return td_call("td_write_dat", {"path": path, "text": text})


# ═══════════════════════════════════════════════════════════════════════════════
# EFFECT LISTS — must match the build scripts exactly
# ═══════════════════════════════════════════════════════════════════════════════

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

GEN3 = [
    "fx_g3_kaleido_mosh", "fx_g3_plasma_skeleton", "fx_g3_fire_kaleido",
    "fx_g3_echo_plasma", "fx_g3_neon_datamosh", "fx_g3_glitch_kaleidoscope",
    "fx_g3_rgb_fire", "fx_g3_strobe_spiral", "fx_g3_pixel_plasma",
    "fx_g3_confetti_shatter", "fx_g3_thermal_echo", "fx_g3_skeleton_glitch",
    "fx_g3_zoom_matrix", "fx_g3_solarize_feedback", "fx_g3_liquify_neon",
    "fx_g3_chromatic_fire", "fx_g3_datamosh_rainbow", "fx_g3_pixelate_skeleton",
    "fx_g3_tentacle_strobe", "fx_g3_shatter_confetti",
    # Palette swaps (20)
    "fx_g3_confetti_neon", "fx_g3_thermal_ice", "fx_g3_fire_cyan",
    "fx_g3_echo_gold", "fx_g3_rainbow_mono", "fx_g3_liquify_blood",
    "fx_g3_pixel_pastel", "fx_g3_datamosh_toxic", "fx_g3_rgb_sunset",
    "fx_g3_kaleido_earth", "fx_g3_plasma_vapor", "fx_g3_strobe_warm",
    "fx_g3_pixelate_ocean", "fx_g3_glitch_rose", "fx_g3_zoom_magenta",
    "fx_g3_skeleton_gold", "fx_g3_solarize_green", "fx_g3_shatter_ice",
    "fx_g3_spiral_fire", "fx_g3_matrix_amber",
    # Intensity mutations (17)
    "fx_g3_confetti_overdrive", "fx_g3_thermal_extreme",
    "fx_g3_fire_inferno", "fx_g3_echo_infinite",
    "fx_g3_rainbow_supernova", "fx_g3_liquify_melt",
    "fx_g3_pixel_megablock", "fx_g3_datamosh_destroy",
    "fx_g3_rgb_nuclear", "fx_g3_kaleido_fractal",
    "fx_g3_plasma_storm", "fx_g3_strobe_seizure",
    "fx_g3_pixelate_mosaic", "fx_g3_glitch_corrupt",
    "fx_g3_zoom_warp", "fx_g3_skeleton_xray",
    "fx_g3_solarize_psychedelic",
]

CONTOUR = [
    "fx_g3_body_neon_outline", "fx_g3_body_pulse_edge",
    "fx_g3_body_double_edge", "fx_g3_body_electric_wire",
    "fx_g3_body_heat_contour", "fx_g3_body_laser_scan",
    "fx_g3_body_glitch_edge", "fx_g3_body_fire_outline",
    "fx_g3_body_matrix_edge", "fx_g3_body_plasma_edge",
    "fx_g3_body_strobe_edge", "fx_g3_body_solid_silhouette",
    "fx_g3_body_gradient_sil", "fx_g3_body_starfield_sil",
    "fx_g3_body_fire_sil", "fx_g3_body_ocean_sil",
    "fx_g3_body_rainbow_sil", "fx_g3_body_glitch_sil",
    "fx_g3_body_pixel_sil", "fx_g3_body_ghost_sil",
    "fx_g3_body_kaleidoscope_sil", "fx_g3_body_invert_sil",
    "fx_g3_body_neon_fill", "fx_g3_body_xray_contour",
    "fx_g3_body_thermal_contour", "fx_g3_body_cyberpunk_contour",
    "fx_g3_body_hologram", "fx_g3_body_blueprint",
    "fx_g3_body_shadow_play", "fx_g3_body_particle_edge",
    "fx_g3_body_aura_glow", "fx_g3_body_comic_contour",
    "fx_g3_body_mirror_contour",
]

WEB_EFFECTS = ["fx_spitballs_web"]

# Effects that need cam_in connected to their baseCOMP input
NEEDS_CAMERA = set(MUTATIONS + GEN3 + CONTOUR)

# Full ordered list
ALL_EFFECTS = ORIGINALS + MUTATIONS + ["fx_canon_shards"] + GEN3 + CONTOUR + WEB_EFFECTS

ROUTERS = ["effect_router", "layer2_router", "layer3_router"]


# ═══════════════════════════════════════════════════════════════════════════════
# CHAOS ENGINE SCRIPT (corrected version)
# ═══════════════════════════════════════════════════════════════════════════════

CHAOS_ENGINE_SCRIPT = r'''import random
import math

# ========================================
# YOUSUKE CHAOS ENGINE + AUTO-ROTATE
# ========================================
# On each switch: randomize effect selection + per-layer transform/color
# State space: ~10^95 combinations
#
# Per layer randomized on each switch:
#   - Effect index (0 to N-1, contiguous)
#   - Flip X (0 or 1)
#   - Flip Y (0 or 1)
#   - Scale (0.9 - 1.1, continuous)
#   - Hue offset (0-360 degrees, continuous)
#   - Saturation mult (0.8 - 1.4, continuous)
#   - Layer opacity (0.12 - 0.35, continuous)

SWITCH_INTERVAL = 1.5
BEAT_SWITCH_THRESHOLD = 5
ONSET_THRESHOLD = 0.2
MIN_ONSET_TIME = 0.8

_last_switch = 0
_beat_count = 0
_last_onset = 0

def get_num_effects():
    router = op("/project1/effect_router")
    return sum(1 for c in router.inputConnectors if c.connections)

def chaos_randomize():
    """Randomize all 3 layers: effect + transform + HSV."""
    N = get_num_effects()
    if N < 3:
        return

    # Pick 3 different effects
    indices = random.sample(range(N), 3)

    routers = [
        op("/project1/effect_router"),
        op("/project1/layer2_router"),
        op("/project1/layer3_router"),
    ]
    xforms = [
        op("/project1/chaos_xform1"),
        op("/project1/chaos_xform2"),
        op("/project1/chaos_xform3"),
    ]
    hsvs = [
        op("/project1/chaos_hsv1"),
        op("/project1/chaos_hsv2"),
        op("/project1/chaos_hsv3"),
    ]
    opacities = [
        None,  # Layer 1 has no separate opacity node
        op("/project1/layer2_opacity"),
        op("/project1/layer3_opacity"),
    ]

    # Map indices to actual connected slot numbers
    # (handles sparse arrays if any effects are missing)
    connected_slots = []
    for i, c in enumerate(routers[0].inputConnectors):
        if c.connections:
            connected_slots.append(i)

    for i in range(3):
        # Use the actual slot number, not the counting index
        if indices[i] < len(connected_slots):
            slot = connected_slots[indices[i]]
        else:
            slot = indices[i]

        # Set effect on all routers
        routers[i].par.index = slot

        # Scale with random flip (no rotation — distracting)
        if xforms[i]:
            xforms[i].par.rotate = 0
            flip_x = random.choice([-1, 1])
            flip_y = random.choice([-1, 1])
            s = random.uniform(0.9, 1.1)
            xforms[i].par.sx = s * flip_x
            xforms[i].par.sy = s * flip_y
            xforms[i].par.tx = random.uniform(-0.03, 0.03)
            xforms[i].par.ty = random.uniform(-0.03, 0.03)

        # Random hue offset and saturation
        if hsvs[i]:
            hsvs[i].par.hueoffset = random.uniform(0, 360)
            hsvs[i].par.saturationmult = random.uniform(0.8, 1.4)
            hsvs[i].par.valuemult = random.uniform(0.6, 0.95)

        # Low opacity for layers 2 and 3
        if opacities[i]:
            opacities[i].par.opacity = random.uniform(0.12, 0.35)


def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    global _last_switch, _beat_count, _last_onset

    t = absTime.seconds
    audio = op("/project1/audio_analysis/out1")

    do_switch = False

    # Time-based switch
    if t - _last_switch >= SWITCH_INTERVAL:
        do_switch = True

    # Beat-based switch
    try:
        beat_val = audio["beat"]
        if beat_val > 0.5 and prev <= 0.5:
            _beat_count += 1
            if _beat_count >= BEAT_SWITCH_THRESHOLD:
                do_switch = True
                _beat_count = 0
    except:
        pass

    # Onset-based switch
    try:
        onset_val = audio["onset"]
        if onset_val > ONSET_THRESHOLD and (t - _last_onset) > MIN_ONSET_TIME:
            _last_onset = t
            if random.random() > 0.7:
                do_switch = True
    except:
        pass

    if do_switch:
        _last_switch = t
        chaos_randomize()

def onValueChange(channel, sampleIndex, val, prev):
    return
'''


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def verify_only():
    """Run diagnostics without changing anything."""
    print("=" * 70)
    print("YOUSUKE WIRING DIAGNOSTIC (read-only)")
    print("=" * 70)

    # Check each effect exists
    print("\n[1/5] Checking effect existence...")
    missing = []
    present = []
    for name in ALL_EFFECTS:
        result = td_exec(
            "x = op('/project1/" + name + "')\n"
            "print('EXISTS' if x else 'MISSING')"
        )
        if "MISSING" in result:
            missing.append(name)
        else:
            present.append(name)
        time.sleep(0.02)

    print("  Present: " + str(len(present)) + "/" + str(len(ALL_EFFECTS)))
    if missing:
        print("  MISSING (" + str(len(missing)) + "):")
        for m in missing:
            print("    - " + m)

    # Check router input counts
    print("\n[2/5] Checking router wiring...")
    for router_name in ROUTERS:
        result = td_exec(
            "router = op('/project1/" + router_name + "')\n"
            "if router is None:\n"
            "    print('NOT FOUND')\n"
            "else:\n"
            "    connected = []\n"
            "    for i, c in enumerate(router.inputConnectors):\n"
            "        if c.connections:\n"
            "            connected.append(i)\n"
            "    print('Connected: ' + str(len(connected)))\n"
            "    if connected:\n"
            "        print('  Range: ' + str(min(connected)) + '-' + str(max(connected)))\n"
            "        gaps = [i for i in range(min(connected), max(connected)+1) if i not in connected]\n"
            "        if gaps:\n"
            "            print('  GAPS at: ' + str(gaps[:20]) + ('...' if len(gaps) > 20 else ''))\n"
            "        else:\n"
            "            print('  Contiguous: YES')\n"
        )
        print("  " + router_name + ": " + result.strip().replace("\n", "\n    "))

    # Check chaos engine nodes
    print("\n[3/5] Checking chaos engine chain...")
    chaos_checks = [
        ("chaos_xform1", "effect_router"),
        ("chaos_hsv1", "chaos_xform1"),
        ("chaos_xform2", "layer2_opacity"),
        ("chaos_hsv2", "chaos_xform2"),
        ("chaos_xform3", "layer3_opacity"),
        ("chaos_hsv3", "chaos_xform3"),
    ]
    for node_name, expected_src in chaos_checks:
        result = td_exec(
            "node = op('/project1/" + node_name + "')\n"
            "if node is None:\n"
            "    print('MISSING: " + node_name + "')\n"
            "elif not node.inputConnectors[0].connections:\n"
            "    print('DISCONNECTED: " + node_name + "')\n"
            "else:\n"
            "    src = node.inputConnectors[0].connections[0].owner.name\n"
            "    ok = 'OK' if src == '" + expected_src + "' else 'WRONG (got ' + src + ')'\n"
            "    print('" + node_name + " <- ' + src + ' ' + ok)\n"
        )
        print("  " + result.strip())

    # Check blend chain
    print("\n[4/5] Checking compositing chain...")
    for blend_name in ["blend_add1", "blend_add2", "blend_level"]:
        result = td_exec(
            "b = op('/project1/" + blend_name + "')\n"
            "if b is None:\n"
            "    print('" + blend_name + ": NOT FOUND')\n"
            "else:\n"
            "    ins = []\n"
            "    for ic in b.inputConnectors:\n"
            "        if ic.connections:\n"
            "            ins.append(ic.connections[0].owner.name)\n"
            "    print('" + blend_name + " inputs: ' + str(ins))\n"
        )
        print("  " + result.strip())

    # Check auto_rotate script
    print("\n[5/5] Checking auto_rotate script...")
    result = td_exec(
        "ar = op('/project1/auto_rotate')\n"
        "if ar is None:\n"
        "    print('auto_rotate: NOT FOUND')\n"
        "else:\n"
        "    has_chaos = 'chaos_randomize' in ar.text\n"
        "    has_whileon = 'whileOn' in ar.text\n"
        "    has_slot_map = 'connected_slots' in ar.text\n"
        "    print('auto_rotate:')\n"
        "    print('  whileon par: ' + str(ar.par.whileon))\n"
        "    print('  active par: ' + str(ar.par.active))\n"
        "    print('  has chaos_randomize: ' + str(has_chaos))\n"
        "    print('  has whileOn callback: ' + str(has_whileon))\n"
        "    print('  has slot mapping fix: ' + str(has_slot_map))\n"
        "    print('  script length: ' + str(len(ar.text)) + ' chars')\n"
    )
    print("  " + result.strip().replace("\n", "\n  "))

    # Check cam_in wiring
    print("\n[BONUS] Checking cam_in wiring to effects...")
    cam_wired = 0
    cam_missing = 0
    cam_missing_names = []
    for name in ALL_EFFECTS:
        if name not in NEEDS_CAMERA:
            continue
        result = td_exec(
            "comp = op('/project1/" + name + "')\n"
            "if comp is None:\n"
            "    print('EFFECT_MISSING')\n"
            "elif not comp.inputConnectors[0].connections:\n"
            "    print('NO_CAM')\n"
            "else:\n"
            "    src = comp.inputConnectors[0].connections[0].owner.name\n"
            "    print('cam=' + src)\n"
        )
        r = result.strip()
        if "cam_in" in r:
            cam_wired += 1
        elif "EFFECT_MISSING" not in r:
            cam_missing += 1
            cam_missing_names.append(name)
        time.sleep(0.02)

    print("  cam_in connected: " + str(cam_wired))
    print("  cam_in MISSING:   " + str(cam_missing))
    if cam_missing_names and len(cam_missing_names) <= 10:
        for n in cam_missing_names:
            print("    - " + n)
    elif cam_missing_names:
        print("    (first 10): " + str(cam_missing_names[:10]))

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


def wire_everything(dry_run=False):
    """Wire all effects to all 3 routers contiguously."""
    print("=" * 70)
    print("YOUSUKE COMPREHENSIVE WIRING")
    print("134 effects -> 3 routers (contiguous slots)")
    print("=" * 70)

    if dry_run:
        for i, name in enumerate(ALL_EFFECTS):
            cam = " (+ cam_in)" if name in NEEDS_CAMERA else ""
            print("  [" + str(i).rjust(3) + "] " + name + cam)
        print("\nDRY RUN: no changes made")
        return

    # ── Step 1: Disconnect all router inputs ──
    print("\n[1/6] Disconnecting all router inputs...")
    for router_name in ROUTERS:
        td_exec(
            "router = op('/project1/" + router_name + "')\n"
            "if router:\n"
            "    for conn in router.inputConnectors:\n"
            "        for c in conn.connections:\n"
            "            c.disconnect()\n"
            "    print('" + router_name + " cleared')\n"
            "else:\n"
            "    print('" + router_name + " NOT FOUND')\n"
        )
        time.sleep(0.2)

    # ── Step 2: Wire cam_in to effects that need it ──
    print("\n[2/6] Wiring cam_in to effects...")
    cam_ok = 0
    cam_fail = 0
    for name in ALL_EFFECTS:
        if name not in NEEDS_CAMERA:
            continue
        result = td_exec(
            "comp = op('/project1/" + name + "')\n"
            "cam = op('/project1/cam_in')\n"
            "if comp is None:\n"
            "    print('SKIP: " + name + " not found')\n"
            "elif cam is None:\n"
            "    print('SKIP: cam_in not found')\n"
            "else:\n"
            "    try:\n"
            "        comp.inputConnectors[0].connect(cam)\n"
            "        print('OK')\n"
            "    except Exception as e:\n"
            "        print('FAIL: ' + str(e))\n"
        )
        r = result.strip()
        if "OK" in r:
            cam_ok += 1
        elif "SKIP" not in r:
            cam_fail += 1
            print("  FAIL: " + name + " - " + r)
        time.sleep(0.02)
    print("  cam_in wired: " + str(cam_ok) + " effects (" + str(cam_fail) + " failures)")

    # ── Step 3: Wire all effects to all 3 routers ──
    print("\n[3/6] Wiring " + str(len(ALL_EFFECTS)) + " effects to 3 routers...")
    wire_counts = {r: 0 for r in ROUTERS}
    skipped = []

    for i, name in enumerate(ALL_EFFECTS):
        # Check if effect exists
        result = td_exec(
            "x = op('/project1/" + name + "')\n"
            "print('EXISTS' if x else 'MISSING')"
        )
        if "MISSING" in result:
            skipped.append(name)
            continue

        # Wire output to all 3 routers at slot i
        for router_name in ROUTERS:
            # For web effects, use the level node output if present
            out_node = name
            if name == "fx_spitballs_web":
                result_lvl = td_exec(
                    "x = op('/project1/fx_spitballs_web_level')\n"
                    "print('EXISTS' if x else 'MISSING')"
                )
                if "EXISTS" in result_lvl:
                    out_node = "fx_spitballs_web_level"

            result = td_exec(
                "router = op('/project1/" + router_name + "')\n"
                "fx = op('/project1/" + out_node + "')\n"
                "if fx is None or router is None:\n"
                "    print('SKIP')\n"
                "else:\n"
                "    try:\n"
                "        fx.outputConnectors[0].connect(router.inputConnectors[" + str(i) + "])\n"
                "        print('OK')\n"
                "    except Exception as e:\n"
                "        print('FAIL: ' + str(e))\n"
            )
            if "OK" in result:
                wire_counts[router_name] += 1
            time.sleep(0.02)

        # Progress every 10 effects
        if (i + 1) % 10 == 0:
            print("  ... " + str(i + 1) + "/" + str(len(ALL_EFFECTS)))

    print()
    for rname, count in wire_counts.items():
        print("  " + rname + ": " + str(count) + "/" + str(len(ALL_EFFECTS)) + " wired")
    if skipped:
        print("  Skipped (not found): " + str(skipped))

    # ── Step 4: Write corrected chaos engine script ──
    print("\n[4/6] Writing corrected chaos engine script...")
    result = td_exec(
        "ar = op('/project1/auto_rotate')\n"
        "print('EXISTS' if ar else 'MISSING')"
    )
    if "MISSING" in result:
        print("  Creating auto_rotate chopexecuteDAT...")
        td_exec(
            "parent = op('/project1')\n"
            "ar = parent.create(chopexecuteDAT, 'auto_rotate')\n"
            "ar.nodeX = 400\n"
            "ar.nodeY = -600\n"
            "ar.par.chop = '/project1/audio_analysis/out1'\n"
            "ar.par.active = True\n"
            "ar.par.whileon = True\n"
            "ar.par.onvaluechange = False\n"
            "print('Created auto_rotate')\n"
        )

    # Ensure correct params
    td_exec(
        "ar = op('/project1/auto_rotate')\n"
        "ar.par.whileon = True\n"
        "ar.par.active = True\n"
        "ar.par.chop = '/project1/audio_analysis/out1'\n"
        "print('Params set')\n"
    )

    td_write_dat("/project1/auto_rotate", CHAOS_ENGINE_SCRIPT)
    print("  Chaos engine script written with slot-mapping fix")

    # ── Step 5: Enable auto-rotate (fix constantCHOP bug) ──
    print("\n[5/6] Enabling auto-rotate (using par.value1, not bracket notation)...")
    td_exec(
        "ae = op('/project1/active_effect')\n"
        "if ae is not None:\n"
        "    ae.par.value1 = 1\n"
        "    print('auto_rotate enabled: par.value1 = ' + str(ae.par.value1.eval()))\n"
        "else:\n"
        "    print('active_effect not found')\n"
    )

    # ── Step 6: Verify ──
    print("\n[6/6] Running verification...")
    verify_only()

    # Save project
    td_exec("project.save(); print('Project saved')")

    print("\n" + "=" * 70)
    print("WIRING COMPLETE")
    total = sum(wire_counts.values())
    expected = len(ALL_EFFECTS) * 3
    print("  " + str(total) + "/" + str(expected) + " connections made")
    print("  " + str(len(ALL_EFFECTS)) + " effects x 3 routers = " + str(expected) + " expected")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Wire ALL effects to ALL 3 routers")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--verify", action="store_true", help="Only verify, don't rewire")
    args = parser.parse_args()

    if not args.dry_run:
        try:
            result = td_call("td_get_focus")
            print("TD connected: " + result.split("\n")[0])
        except Exception as e:
            print("ERROR: Cannot connect to TouchDesigner MCP: " + str(e))
            print("Make sure TouchDesigner is running with twozero.tox enabled")
            sys.exit(1)

    if args.verify:
        verify_only()
    elif args.dry_run:
        wire_everything(dry_run=True)
    else:
        wire_everything()


if __name__ == "__main__":
    main()
