#!/usr/bin/env python3
"""
Update auto-rotate to aggressive random rotation for 43 effects.

Changes from old rotation:
  - SWITCH_INTERVAL: 4.0s -> 1.5s
  - BEAT_SWITCH_THRESHOLD: 16 -> 5
  - Onset threshold: 0.4 -> 0.2
  - Min onset time: 2.0s -> 0.8s
  - Order: sequential -> random (no-repeat)

Usage:
  python3 tools/td_update_rotation.py           # Apply
  python3 tools/td_update_rotation.py --dry-run # Print plan
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


# --- Aggressive random auto-rotate script ---

AGGRESSIVE_ROTATE_SCRIPT = r'''# YOUSUKE Aggressive Auto-Rotate — random order, fast switching
# Monitored CHOP: /project1/audio_analysis/out1
# Fires every frame via whileOn callback.
#
# active_effect is a constantCHOP:
#   par.value0 = effect_idx
#   par.value1 = auto_rotate

import random

# Aggressive timing parameters
SWITCH_INTERVAL = 1.5       # Was 4.0s — now 1.5s
BEAT_SWITCH_THRESHOLD = 5   # Was 16 — now 5 beats
ONSET_THRESHOLD = 0.2       # Was 0.4 — now 0.2
MIN_ONSET_TIME = 0.8        # Was 2.0s — now 0.8s


def onOffToOn(channel, sampleIndex, val, prev):
    return

def whileOff(channel, sampleIndex, val, prev):
    return

def onOnToOff(channel, sampleIndex, val, prev):
    return

def whileOn(channel, sampleIndex, val, prev):
    """Fires every frame while any channel value is non-zero."""
    if channel.name != 'bass':
        return

    ae = op('/project1/active_effect')
    if ae is None:
        return

    try:
        effect_idx = int(ae.par.value0.eval())
        auto_mode = int(ae.par.value1.eval())
    except:
        return
    if auto_mode == 0:
        return

    router = op('/project1/effect_router')
    if router is None:
        return
    total_effects = len([c for c in router.inputConnectors if c.connections])
    if total_effects < 2:
        return

    now = absTime.seconds
    storage = op('/project1/auto_rotate').storage

    if 'last_switch_time' not in storage:
        storage['last_switch_time'] = now
        storage['beat_count'] = 0

    last_switch = storage['last_switch_time']
    beat_count = storage.get('beat_count', 0)
    elapsed = now - last_switch

    # Count beats
    audio = op('/project1/audio_analysis/out1')
    if audio is not None:
        try:
            beat_chan = audio.chan('beat')
            if beat_chan is not None and beat_chan.eval() > 0.5:
                beat_count += 1
                storage['beat_count'] = beat_count
        except:
            pass

    # Switch conditions (aggressive)
    should_switch = False

    if elapsed >= SWITCH_INTERVAL:
        should_switch = True
    elif beat_count >= BEAT_SWITCH_THRESHOLD:
        should_switch = True
    elif elapsed >= MIN_ONSET_TIME:
        try:
            onset_chan = audio.chan('onset') if audio is not None else None
            if onset_chan is not None and onset_chan.eval() > ONSET_THRESHOLD:
                should_switch = True
        except:
            pass

    if should_switch:
        # Random selection: pick any effect except the current one
        candidates = [i for i in range(total_effects) if i != effect_idx]
        new_idx = random.choice(candidates)

        ae.par.value0 = new_idx
        router.par.index = new_idx
        storage['last_switch_time'] = now
        storage['beat_count'] = 0


def onValueChange(channel, sampleIndex, val, prev):
    return
'''


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Update auto-rotate to aggressive random mode")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    print("=" * 60)
    print("YOUSUKE Aggressive Random Auto-Rotate")
    print("=" * 60)
    print()
    print("  SWITCH_INTERVAL:       4.0s -> 1.5s")
    print("  BEAT_SWITCH_THRESHOLD: 16   -> 5")
    print("  ONSET_THRESHOLD:       0.4  -> 0.2")
    print("  MIN_ONSET_TIME:        2.0s -> 0.8s")
    print("  ORDER:                 sequential -> random (no-repeat)")
    print()

    if args.dry_run:
        print("DRY RUN: would rewrite /project1/auto_rotate")
        return

    # Verify MCP connection
    try:
        result = td_call("td_get_focus")
        print(f"TD connected: {result.split(chr(10))[0]}")
    except Exception as e:
        print(f"ERROR: Cannot connect to TouchDesigner MCP: {e}")
        sys.exit(1)

    # Verify auto_rotate exists
    result = td_exec("""
ar = op('/project1/auto_rotate')
if ar is None:
    print('MISSING')
else:
    print(f'EXISTS whileon={ar.par.whileon} active={ar.par.active}')
""")
    print(f"Current state: {result.strip()}")

    if "MISSING" in result:
        print("Creating auto_rotate chopexecuteDAT...")
        td_exec("""
parent = op('/project1')
ar = parent.create(chopexecuteDAT, 'auto_rotate')
ar.nodeX = 400
ar.nodeY = -600
ar.par.chop = '/project1/audio_analysis/out1'
ar.par.active = True
ar.par.whileon = True
ar.par.onvaluechange = False
print('Created auto_rotate')
""")

    # Ensure whileOn is enabled
    td_exec("""
ar = op('/project1/auto_rotate')
ar.par.whileon = True
ar.par.active = True
ar.par.chop = '/project1/audio_analysis/out1'
print(f'Params set: whileon={ar.par.whileon} active={ar.par.active}')
""")

    # Write the new aggressive rotation script
    print("\nWriting aggressive rotation script...")
    td_write_dat("/project1/auto_rotate", AGGRESSIVE_ROTATE_SCRIPT)

    # Initialize storage
    td_exec("""
ar = op('/project1/auto_rotate')
ar.storage['last_switch_time'] = absTime.seconds
ar.storage['beat_count'] = 0
print(f'Storage initialized at t={absTime.seconds:.1f}')
""")

    # Verify
    result = td_exec("""
ar = op('/project1/auto_rotate')
print(f'whileon={ar.par.whileon}')
print(f'active={ar.par.active}')
has_random = 'random.choice' in ar.text
has_1_5 = 'SWITCH_INTERVAL = 1.5' in ar.text
has_5_beat = 'BEAT_SWITCH_THRESHOLD = 5' in ar.text
print(f'has random.choice: {has_random}')
print(f'has 1.5s interval: {has_1_5}')
print(f'has 5-beat threshold: {has_5_beat}')
""")
    print(f"\nVerification:\n{result.strip()}")

    # Enable auto-rotate
    td_exec("""
ae = op('/project1/active_effect')
if ae is not None:
    ae['auto_rotate'] = 1
    print(f'auto_rotate enabled: {ae["auto_rotate"]}')
""")

    print(f"\n{'=' * 60}")
    print("Aggressive random auto-rotate installed!")
    print("Press 0 in TD to toggle auto-rotate on/off.")
    print("=" * 60)


if __name__ == "__main__":
    main()
