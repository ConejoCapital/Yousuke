import random

# ========================================
# YOUSUKE CHAOS ENGINE — AUDIO-DRIVEN
# ========================================
# Switches ONLY on audio events (beat pulse, bass hit, onset).
# Time fallback only if audio goes silent for 3+ seconds.
# No rotation. Horizontal only. High contrast, no whiteout.

# Minimum gap between switches
MIN_SWITCH_GAP = 0.15
# Fallback ONLY if audio is dead silent
SILENT_FALLBACK = 3.0


DARK_KEYWORDS = ("contour", "silhouette", "sil_", "edge", "outline", "wire")


def get_num_effects():
    router = op("/project1/effect_router")
    return sum(1 for c in router.inputConnectors if c.connections)


def get_dark_indices():
    """Discover which router slots contain dark/contour effects. Cached in storage."""
    storage = me.storage
    if "dark_indices" in storage:
        return storage["dark_indices"]

    router = op("/project1/effect_router")
    dark = []
    for i, conn in enumerate(router.inputConnectors):
        if conn.connections:
            src = conn.connections[0].owner
            name = src.name.lower()
            if any(kw in name for kw in DARK_KEYWORDS):
                dark.append(i)
    storage["dark_indices"] = dark
    return dark


def pick_weighted_indices(N, dark_indices):
    """Pick 3 distinct indices with 85% bright, 15% contour weighting."""
    bright_indices = [i for i in range(N) if i not in dark_indices]
    if not bright_indices:
        bright_indices = list(range(N))

    chosen = []
    for _ in range(3):
        if random.random() < 0.15 and dark_indices:
            pool = [i for i in dark_indices if i not in chosen]
        else:
            pool = [i for i in bright_indices if i not in chosen]
        if not pool:
            pool = [i for i in range(N) if i not in chosen]
        if not pool:
            break
        chosen.append(random.choice(pool))
    return chosen


def chaos_randomize(intensity=1.0):
    N = get_num_effects()
    if N < 3:
        return

    dark_indices = get_dark_indices()
    indices = pick_weighted_indices(N, dark_indices)

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
        None,
        op("/project1/layer2_opacity"),
        op("/project1/layer3_opacity"),
    ]

    for i in range(3):
        routers[i].par.index = indices[i]

        # Horizontal only — no rotation, just flips and scale
        if xforms[i]:
            xforms[i].par.rotate = 0
            flip_x = random.choice([-1, 1])
            s = random.uniform(0.85, 1.15)
            xforms[i].par.sx = s * flip_x
            xforms[i].par.sy = s
            xforms[i].par.tx = random.uniform(-0.05, 0.05)
            xforms[i].par.ty = 0

        # BRIGHT VIBRANT — full value, high saturation, happy colors
        if hsvs[i]:
            hsvs[i].par.hueoffset = random.uniform(0, 360)
            hsvs[i].par.saturationmult = random.uniform(1.3, 2.0)
            hsvs[i].par.valuemult = random.uniform(0.85, 1.1)

        # Layers 2/3 opacity — balanced contribution
        if opacities[i]:
            opacities[i].par.opacity = random.uniform(0.3, 0.5)


def onOffToOn(channel, sampleIndex, val, prev):
    return


def whileOff(channel, sampleIndex, val, prev):
    return


def onOnToOff(channel, sampleIndex, val, prev):
    return


def whileOn(channel, sampleIndex, val, prev):
    if channel.name != "bass":
        return

    ae = op("/project1/active_effect")
    if ae is None:
        return
    try:
        if int(ae.par.value1.eval()) == 0:
            return
    except:
        return

    t = absTime.seconds
    storage = me.storage

    if "last_switch" not in storage:
        storage["last_switch"] = t
        storage["prev_pulse"] = 0.0

    last_switch = storage["last_switch"]
    prev_pulse = storage["prev_pulse"]

    if t - last_switch < MIN_SWITCH_GAP:
        return

    do_switch = False
    intensity = 1.0

    # 1. Beat pulse — switch on every beat
    beat_detect = op("/project1/audio_analysis/beat_detect")
    if beat_detect is not None:
        try:
            pulse = beat_detect.chan("pulse").eval()
            if pulse > 0.5 and prev_pulse <= 0.5:
                do_switch = True
                intensity = 1.5
            storage["prev_pulse"] = float(pulse)
        except:
            pass

    # 2. Bass energy — strong bass triggers switch
    audio = op("/project1/audio_analysis/out1")
    if audio is not None and not do_switch:
        try:
            bass = audio.chan("bass").eval()
            if bass > 0.3 and (t - last_switch) > 0.25:
                do_switch = True
                intensity = 0.8 + bass
        except:
            pass

    # 3. Mids/highs spike — any strong transient triggers
    if audio is not None and not do_switch:
        try:
            mids = audio.chan("mids").eval()
            highs = audio.chan("highs").eval()
            if (mids > 0.5 or highs > 0.6) and (t - last_switch) > 0.3:
                do_switch = True
                intensity = 1.0
        except:
            pass

    # 4. Silent fallback only
    if not do_switch and (t - last_switch) >= SILENT_FALLBACK:
        do_switch = True

    if do_switch:
        storage["last_switch"] = t
        chaos_randomize(intensity)


def onValueChange(channel, sampleIndex, val, prev):
    return
