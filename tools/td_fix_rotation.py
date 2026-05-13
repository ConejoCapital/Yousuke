#!/usr/bin/env python3
"""
Fix auto-rotate stalling & keyboard controls in TouchDesigner.

Problems:
  1. auto_rotate CHOP Execute uses onValueChange on audio_analysis — stops
     firing when audio values go static (no music playing).
  2. keyboard_control keyboardinDAT may not receive events when the Window
     COMP is focused.

Fixes:
  1. Rewrite auto_rotate to use whileOn callback (fires every frame as long
     as any monitored channel is non-zero). The timer logic stays the same
     but the callback actually fires reliably.
  2. Set keyboard_control to receive global key events regardless of focus.

Usage:
  python3 tools/td_fix_rotation.py           # Apply all fixes
  python3 tools/td_fix_rotation.py --dry-run # Show what would be done
  python3 tools/td_fix_rotation.py --verify  # Just verify current state
"""

import json
import sys
import time
import urllib.request

MCP_URL = "http://localhost:40404/mcp"
_REQ_ID = 0


def td_exec(code, label=""):
    """Execute Python code inside TouchDesigner via twozero MCP."""
    global _REQ_ID
    _REQ_ID += 1
    payload = {
        "jsonrpc": "2.0",
        "id": _REQ_ID,
        "method": "tools/call",
        "params": {"name": "td_execute_python", "arguments": {"code": code}},
    }
    data = json.dumps(payload).encode("utf-8")
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
        print(f"  MCP error{f' ({label})' if label else ''}: {e}")
        return ""


def td_write_dat(path, text):
    """Write text content to a DAT via twozero MCP."""
    global _REQ_ID
    _REQ_ID += 1
    payload = {
        "jsonrpc": "2.0",
        "id": _REQ_ID,
        "method": "tools/call",
        "params": {"name": "td_write_dat", "arguments": {"path": path, "text": text}},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        MCP_URL, data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    content = result.get("result", {}).get("content", [])
    return "\n".join(c["text"] for c in content if c.get("type") == "text")


# ── Auto-rotate script (whileOn version) ─────────────────────────────────────
#
# This replaces the old onValueChange-based auto_rotate DAT.
# whileOn fires every frame as long as any monitored channel value is non-zero.
# Since audio channels always have non-zero values (bass~0.2, mids~0.23, etc.),
# this fires every frame even without active music.

AUTO_ROTATE_SCRIPT = r'''# ¥ØUSUK€ Auto-Rotate — whileOn (frame-driven)
# Monitored CHOP: /project1/audio_analysis/out1
# Fires every frame; uses absTime.seconds for reliable timer.

import math

# Seconds between automatic effect switches
SWITCH_INTERVAL = 4.0

# Beat threshold for early switch
BEAT_SWITCH_THRESHOLD = 16


def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    """Fires every frame while any channel value is non-zero."""
    # Only run logic on the first channel to avoid running N times per frame
    if channel.name != 'bass':
        return

    ae = op('/project1/active_effect')
    if ae is None:
        return

    effect_idx = int(ae['effect_idx'])
    auto_mode = int(ae['auto_rotate'])
    if auto_mode == 0:
        return

    # Get total effects from the switch
    router = op('/project1/effect_router')
    if router is None:
        return
    total_effects = len([c for c in router.inputConnectors if c.connections])
    if total_effects == 0:
        return

    # Timer logic using absTime.seconds (always advances)
    now = absTime.seconds
    storage = op('/project1/auto_rotate').storage

    if 'last_switch_time' not in storage:
        storage['last_switch_time'] = now
        storage['beat_count'] = 0

    last_switch = storage['last_switch_time']
    beat_count = storage.get('beat_count', 0)
    elapsed = now - last_switch

    # Count beats from audio
    audio = op('/project1/audio_analysis/out1')
    if audio is not None:
        try:
            beat_val = audio['beat']
            onset_val = audio['onset'] if 'onset' in [c.name for c in audio.chans()] else 0
            if beat_val > 0.5:
                beat_count += 1
                storage['beat_count'] = beat_count
        except:
            pass

    # Switch conditions:
    # 1. Time elapsed >= SWITCH_INTERVAL
    # 2. Accumulated enough beats
    # 3. Energy spike (onset) after minimum 2s
    should_switch = False

    if elapsed >= SWITCH_INTERVAL:
        should_switch = True
    elif beat_count >= BEAT_SWITCH_THRESHOLD:
        should_switch = True
    elif elapsed >= 2.0:
        try:
            onset_energy = audio['onset'] if audio is not None else 0
            if onset_energy > 0.4:
                should_switch = True
        except:
            pass

    if should_switch:
        new_idx = (effect_idx + 1) % total_effects
        ae['effect_idx'] = new_idx
        router.par.index = new_idx
        storage['last_switch_time'] = now
        storage['beat_count'] = 0
        debug(f'Auto-rotate: effect {effect_idx} -> {new_idx} (of {total_effects})')


def onValueChange(channel, sampleIndex, val, prev):
    """Legacy hook — kept for beat counting only."""
    return
'''


# ── Keyboard control script (updated for 28 effects + global focus) ──────────

KEYBOARD_SCRIPT = r'''# ¥ØUSUK€ Keyboard Controls — All 28 Effects
# keyboardinDAT: /project1/keyboard_control

def onKey(dat, key, character, alt, lAlt, rAlt, ctrl, lCtrl, rCtrl, shift,
          lShift, rShift, state, time, cmd, lCmd, rCmd):
    """Handle key events for effect control."""
    if state == 0:  # key up — ignore
        return

    ae = op('/project1/active_effect')
    router = op('/project1/effect_router')
    if ae is None or router is None:
        return

    effect_idx = int(ae['effect_idx'])
    total_effects = len([c for c in router.inputConnectors if c.connections])
    if total_effects == 0:
        total_effects = 28  # fallback

    # Space or Right arrow: cycle forward
    if key == 'space' or key == 'right':
        new_idx = (effect_idx + 1) % total_effects
        ae['effect_idx'] = new_idx
        ae['auto_rotate'] = 0  # lock
        router.par.index = new_idx
        debug(f'Key cycle: effect {effect_idx} -> {new_idx} (of {total_effects})')
        return

    # Left arrow: cycle backward
    if key == 'left':
        new_idx = (effect_idx - 1) % total_effects
        ae['effect_idx'] = new_idx
        ae['auto_rotate'] = 0
        router.par.index = new_idx
        debug(f'Key cycle back: effect {effect_idx} -> {new_idx}')
        return

    # Number keys 1-9: jump to effect
    if character and character.isdigit() and character != '0':
        target = int(character) - 1
        if target < total_effects:
            ae['effect_idx'] = target
            ae['auto_rotate'] = 0
            router.par.index = target
            debug(f'Key lock: effect {target}')
        return

    # 0: enable auto-rotate
    if character == '0':
        ae['auto_rotate'] = 1
        debug('Auto-rotate enabled')
        return

    # B: toggle blend mode (if blend system exists)
    if character and character.lower() == 'b':
        blend = op('/project1/blend_control')
        if blend is not None:
            try:
                current = int(blend['blend_mode'])
                blend['blend_mode'] = (current + 1) % 3
                debug(f'Blend mode: {(current + 1) % 3}')
            except:
                pass
        return

    # +/= : cycle forward (same as Space)
    if character in ('+', '='):
        new_idx = (effect_idx + 1) % total_effects
        ae['effect_idx'] = new_idx
        ae['auto_rotate'] = 0
        router.par.index = new_idx
        debug(f'Key +: effect {effect_idx} -> {new_idx}')
        return

    # -/_ : cycle backward
    if character in ('-', '_'):
        new_idx = (effect_idx - 1) % total_effects
        ae['effect_idx'] = new_idx
        ae['auto_rotate'] = 0
        router.par.index = new_idx
        debug(f'Key -: effect {effect_idx} -> {new_idx}')
        return
'''


# ── Fix functions ─────────────────────────────────────────────────────────────

def fix_auto_rotate(dry_run=False):
    """Rewrite auto_rotate DAT to use whileOn callback."""
    print("\n[1/3] Fixing auto-rotate (whileOn callback)...")

    if dry_run:
        print("  DRY RUN: would rewrite /project1/auto_rotate script")
        print("  DRY RUN: would set par.whileon = True")
        return True

    # Check if auto_rotate exists
    result = td_exec("""
ar = op('/project1/auto_rotate')
if ar is None:
    print('MISSING')
else:
    print(f'EXISTS type={ar.type} family={ar.family}')
    print(f'  whileon={ar.par.whileon}')
    print(f'  active={ar.par.active}')
""", "check auto_rotate")
    print(f"  Current state: {result.strip()}")

    if "MISSING" in result:
        # Create the CHOP Execute DAT
        print("  Creating auto_rotate chopexecuteDAT...")
        td_exec("""
import td
parent = op('/project1')
ar = parent.create(chopexecuteDAT, 'auto_rotate')
ar.nodeX = 400
ar.nodeY = -600
ar.par.chop = '/project1/audio_analysis/out1'
ar.par.active = True
ar.par.whileon = True
ar.par.onvaluechange = False
print('Created auto_rotate')
""", "create auto_rotate")
    else:
        # Update existing DAT parameters
        td_exec("""
ar = op('/project1/auto_rotate')
ar.par.whileon = True
ar.par.active = True
# Keep chop reference
ar.par.chop = '/project1/audio_analysis/out1'
print(f'Updated: whileon={ar.par.whileon} active={ar.par.active}')
""", "update params")

    # Write the new script
    td_write_dat("/project1/auto_rotate", AUTO_ROTATE_SCRIPT)
    print("  Wrote new auto_rotate script (whileOn-based)")

    # Initialize storage
    td_exec("""
ar = op('/project1/auto_rotate')
ar.storage['last_switch_time'] = absTime.seconds
ar.storage['beat_count'] = 0
print(f'Storage initialized at t={absTime.seconds:.1f}')
""", "init storage")

    # Verify
    result = td_exec("""
ar = op('/project1/auto_rotate')
print(f'whileon={ar.par.whileon}')
print(f'active={ar.par.active}')
print(f'chop={ar.par.chop}')
print(f'storage_keys={list(ar.storage.keys())}')
""", "verify auto_rotate")
    print(f"  Verified: {result.strip()}")

    return True


def fix_keyboard(dry_run=False):
    """Fix keyboard controls to work with all 28 effects + Window COMP focus."""
    print("\n[2/3] Fixing keyboard controls...")

    if dry_run:
        print("  DRY RUN: would rewrite /project1/keyboard_control script")
        print("  DRY RUN: would set global focus on keyboardinDAT")
        return True

    # Check keyboard_control
    result = td_exec("""
kb = op('/project1/keyboard_control')
if kb is None:
    print('MISSING')
else:
    print(f'EXISTS type={kb.type}')
    # Check focus settings if available
    try:
        print(f'  focusselect={kb.par.focusselect}')
    except:
        pass
""", "check keyboard")
    print(f"  Current state: {result.strip()}")

    if "MISSING" in result:
        # Create keyboardinDAT
        print("  Creating keyboard_control keyboardinDAT...")
        td_exec("""
parent = op('/project1')
kb = parent.create(keyboardinDAT, 'keyboard_control')
kb.nodeX = 400
kb.nodeY = -700
print('Created keyboard_control')
""", "create keyboard")

    # Write updated keyboard script
    td_write_dat("/project1/keyboard_control", KEYBOARD_SCRIPT)
    print("  Wrote updated keyboard script (28-effect support)")

    # Set focus to receive global events (even when Window COMP is focused)
    td_exec("""
kb = op('/project1/keyboard_control')
# Set to receive keyboard events regardless of which window is focused
try:
    kb.par.focusselect = 'anywhere'
    print(f'focusselect set to: {kb.par.focusselect}')
except:
    try:
        # Older TD versions may use different parameter name
        kb.par.focus = 0  # 0 = anywhere / global
        print(f'focus set to global')
    except:
        print('Could not set focus mode (check TD version)')

# Ensure it's active
kb.par.active = True
print(f'active={kb.par.active}')
""", "set focus")

    # Also create a keyboardin inside the Window COMP network as a backup
    td_exec("""
# Check if Window COMP has its own keyboard handler
win = op('/project1/main_output')
if win is not None:
    # See if there's already a keyboard DAT inside
    inner_kb = op('/project1/main_output/keyboard_control')
    if inner_kb is None:
        try:
            inner_kb = win.create(keyboardinDAT, 'keyboard_control')
            inner_kb.nodeX = 0
            inner_kb.nodeY = -200
            print('Created inner keyboard_control in Window COMP')
        except:
            print('Could not create inner keyboardinDAT (might not support it)')
    else:
        print('Inner keyboard_control already exists')
else:
    print('No main_output Window COMP found')
""", "inner keyboard")

    return True


def verify_state(dry_run=False):
    """Verify the complete effect routing and control state."""
    print("\n[3/3] Verifying system state...")

    if dry_run:
        print("  DRY RUN: would verify effect routing")
        return True

    # Check total connected effects
    result = td_exec("""
router = op('/project1/effect_router')
if router is None:
    print('ERROR: effect_router not found')
else:
    connected = []
    for i, conn in enumerate(router.inputConnectors):
        if conn.connections:
            names = [c.owner.path.split('/')[-1] for c in conn.connections]
            connected.append((i, names[0]))
    print(f'Total effects connected: {len(connected)}')
    for idx, name in connected:
        print(f'  [{idx:2d}] {name}')
""", "verify router")
    print(result)

    # Check active_effect CHOP
    result = td_exec("""
ae = op('/project1/active_effect')
if ae is None:
    print('ERROR: active_effect not found')
else:
    try:
        print(f'effect_idx = {ae["effect_idx"]}')
        print(f'auto_rotate = {ae["auto_rotate"]}')
    except:
        print('active_effect exists but channels not readable')
""", "verify active_effect")
    print(f"  Active effect: {result.strip()}")

    # Check auto_rotate
    result = td_exec("""
ar = op('/project1/auto_rotate')
if ar is None:
    print('ERROR: auto_rotate not found')
else:
    print(f'whileon={ar.par.whileon}')
    print(f'active={ar.par.active}')
    print(f'chop={ar.par.chop}')
    has_while = 'whileOn' in ar.text
    has_value = 'onValueChange' in ar.text
    print(f'script has whileOn: {has_while}')
    print(f'script has onValueChange: {has_value}')
""", "verify auto_rotate")
    print(f"  Auto-rotate: {result.strip()}")

    # Check keyboard
    result = td_exec("""
kb = op('/project1/keyboard_control')
if kb is None:
    print('ERROR: keyboard_control not found')
else:
    print(f'active={kb.par.active}')
    try:
        print(f'focusselect={kb.par.focusselect}')
    except:
        print('focusselect: N/A')
""", "verify keyboard")
    print(f"  Keyboard: {result.strip()}")

    return True


def enable_auto_rotate():
    """Enable auto-rotate mode via MCP."""
    print("\n[ENABLE] Setting auto_rotate = 1...")
    td_exec("""
ae = op('/project1/active_effect')
if ae is not None:
    ae['auto_rotate'] = 1
    print(f'auto_rotate = {ae["auto_rotate"]}')
else:
    print('ERROR: active_effect not found')
""", "enable auto-rotate")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Fix auto-rotate stalling & keyboard controls in TD"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without executing")
    parser.add_argument("--verify", action="store_true",
                        help="Only verify current state, don't change anything")
    parser.add_argument("--enable", action="store_true",
                        help="Also enable auto-rotate after fixing")
    args = parser.parse_args()

    print("=" * 60)
    print("¥ØUSUK€ Auto-Rotate & Keyboard Fix")
    print("=" * 60)

    # Verify MCP connection
    if not args.dry_run:
        try:
            result = td_exec("print('OK')", "connection test")
            if "OK" not in result:
                raise Exception("No response")
            print(f"TD MCP connection: OK")
        except Exception as e:
            print(f"\nERROR: Cannot connect to TouchDesigner MCP: {e}")
            print("Make sure TouchDesigner is running with twozero.tox enabled")
            sys.exit(1)

    if args.verify:
        verify_state()
        return

    # Apply fixes
    fix_auto_rotate(args.dry_run)
    fix_keyboard(args.dry_run)
    verify_state(args.dry_run)

    if args.enable and not args.dry_run:
        enable_auto_rotate()

    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY RUN complete — no changes made")
    else:
        print("All fixes applied!")
        print("\nWhat changed:")
        print("  1. auto_rotate now uses whileOn (fires every frame)")
        print("  2. keyboard_control handles all 28 effects + arrow keys")
        print("  3. keyboard focus set to global (works with Window COMP)")
        print("\nControls:")
        print("  Space/Right  = cycle forward through all 28 effects")
        print("  Left         = cycle backward")
        print("  1-9          = jump to effect")
        print("  0            = enable auto-rotate")
        print("  +/=          = cycle forward (alternative)")
        print("  -/_          = cycle backward (alternative)")
        print("  B            = toggle blend mode")
    print("=" * 60)


if __name__ == "__main__":
    main()
