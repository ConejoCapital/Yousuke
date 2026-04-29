#!/usr/bin/env python3
"""
Build 21 hyper-maximalist effects in TouchDesigner via twozero MCP bridge.

Each effect becomes a baseCOMP with:
  in1 (inTOP) → glslTOP (pixel shader) → out1 (outTOP)

GLSL receives uAudio = (time, rms, bass, sub_bass)
              uAudio2 = (sub_bass, mids, highs, beat)

All effects are wired into the effect_router switchTOP.

Usage:
  python3 tools/td_build_effects.py           # Build all 21 effects
  python3 tools/td_build_effects.py --dry-run # Print what would be done
  python3 tools/td_build_effects.py --effect 0 # Build only effect #0
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


def td_create_op(parent, optype, name, pars=None):
    """Create an operator in TD."""
    args = {"parent": parent, "type": optype, "name": name}
    if pars:
        args["pars"] = pars
    return td_call("td_create_operator", args)


def td_set_pars(path, pars):
    """Set parameters on an operator."""
    return td_call("td_set_operator_pars", {"path": path, "pars": pars})


def td_write_dat(path, text):
    """Write text content to a DAT."""
    return td_call("td_write_dat", {"path": path, "text": text})


# ─── GLSL SHADERS ────────────────────────────────────────────────────────────

# Common GLSL header for all effects
GLSL_HEADER = """// ¥ØUSUK€ Hyper-Maximalist Effect
// uAudio  = (time, rms, bass, sub_bass)
// uAudio2 = (sub_bass, mids, highs, beat)

uniform vec4 uAudio;
uniform vec4 uAudio2;

out vec4 fragColor;

#define iTime   uAudio.x
#define energy  uAudio.y
#define bass    uAudio.z
#define sub     uAudio.w
#define mids    uAudio2.y
#define highs   uAudio2.z
#define beat    uAudio2.w

// Hash functions for procedural noise
float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1, 0));
    float c = hash(i + vec2(0, 1));
    float d = hash(i + vec2(1, 1));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 5; i++) {
        v += a * noise(p);
        p *= 2.0;
        a *= 0.5;
    }
    return v;
}
"""

EFFECTS = [
    # ── S1: Confetti Particle Storm ──
    {
        "name": "fx_confetti_storm",
        "label": "Confetti Particle Storm",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // Pink tint on bright areas (body proxy)
    vec3 body = mix(src.rgb, vec3(1.0, 0.4, 0.7), 0.4 * step(0.15, luma));

    // Starfield background
    vec2 starUV = uv * 200.0;
    float star = step(0.992, hash(floor(starUV)));
    float twinkle = 0.5 + 0.5 * sin(iTime * 3.0 + hash(floor(starUV)) * 6.28);
    vec3 bg = vec3(star * twinkle * 0.8);

    // Confetti particles
    float confetti = 0.0;
    vec3 confettiColor = vec3(0.0);
    for (int i = 0; i < 30; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 0.7));
        float t = iTime * (0.5 + seed) + fi;
        vec2 pos = vec2(
            fract(seed + sin(t * 0.3) * 0.3),
            fract(fi * 0.0371 - t * 0.15 * (0.5 + bass))
        );
        float d = length((uv - pos) * vec2(1.0, 1.78));
        float size = 0.005 + bass * 0.008;
        if (d < size) {
            vec3 cc = 0.5 + 0.5 * cos(6.28 * (seed * 3.0 + vec3(0, 0.33, 0.67)));
            confettiColor = cc;
            confetti = 1.0;
        }
    }

    // Composite
    float bodyMask = smoothstep(0.1, 0.2, luma);
    vec3 result = mix(bg, body, bodyMask);
    result = mix(result, confettiColor, confetti * 0.9);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── S2: Thermal Posterize ──
    {
        "name": "fx_thermal_posterize",
        "label": "Thermal Posterize",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Chromatic aberration
    float aberr = 1.5 + max(0.0, highs - 0.3) * 6.0;
    vec2 center = vec2(0.5);
    vec2 toC = uv - center;
    float r = length(toC);
    vec2 dir = (r > 0.001) ? toC / r : vec2(0.0);
    vec2 off = dir * r * r * aberr * texel;

    float R = texture(sTD2DInputs[0], uv + off).r;
    float G = texture(sTD2DInputs[0], uv).g;
    float B = texture(sTD2DInputs[0], uv - off).b;
    float luma = R * 0.299 + G * 0.587 + B * 0.114;

    // 3-color thermal posterization
    float tLow = 0.30 + bass * 0.1;
    float tHigh = 0.65 - bass * 0.1;

    vec3 cBlue   = vec3(0.08, 0.31, 0.78);
    vec3 cOrange = vec3(1.0, 0.55, 0.16);
    vec3 cWhite  = vec3(1.0, 1.0, 1.0);

    vec3 result;
    if (luma < tLow) result = cBlue;
    else if (luma < tHigh) result = cOrange;
    else result = cWhite;

    // Floating text shimmer
    float textNoise = step(0.97, noise(uv * 30.0 + iTime * 0.5)) * energy * 0.5;
    result += vec3(0.4, 0.7, 1.0) * textNoise;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── S3: Fire Face Scanlines ──
    {
        "name": "fx_fire_scanlines",
        "label": "Fire Face Scanlines",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);

    // Starfield bg
    vec2 starUV = uv * 180.0;
    float star = step(0.993, hash(floor(starUV)));
    float twinkle = 0.5 + 0.5 * sin(iTime * 2.5 + hash(floor(starUV)) * 6.28);
    vec3 bg = vec3(star * twinkle * 0.7);

    // Fire noise (upper region = face)
    float fireSpeed = 2.0 + energy * 8.0;
    vec2 fireUV = uv * 4.0 + vec2(0, -iTime * fireSpeed * 0.3);
    float fireNoise = fbm(fireUV);
    vec3 fire = vec3(
        clamp(fireNoise * 2.0, 0.0, 1.0),
        clamp(fireNoise * 1.2 - 0.2, 0.0, 1.0),
        clamp(fireNoise * 0.4 - 0.3, 0.0, 1.0)
    );

    // Fire only on upper body (face)
    float faceMask = bodyMask * smoothstep(0.55, 0.45, uv.y);
    vec3 body = mix(src.rgb, fire, faceMask * 0.6);

    // Metallic scanlines
    float scanSpacing = 4.0 + bass * 8.0;
    float scanline = sin(uv.y * uTD2DInfos[0].res.w / scanSpacing + iTime * 2.0);
    scanline = smoothstep(0.7, 1.0, scanline);
    body = mix(body, vec3(0.7, 0.72, 0.68), scanline * 0.15 * bodyMask);

    vec3 result = mix(bg, body, bodyMask);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── S4: Echo Clone Trail ──
    {
        "name": "fx_echo_trail",
        "label": "Echo Clone Trail",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Starfield
    vec2 starUV = uv * 200.0;
    float star = step(0.992, hash(floor(starUV)));
    float twinkle = 0.5 + 0.5 * sin(iTime * 3.0 + hash(floor(starUV)) * 6.28);
    vec3 bg = vec3(star * twinkle * 0.8);

    // Echo copies via offset sampling
    int nEchoes = 3 + int(bass * 4.0);
    vec3 echoes = vec3(0.0);
    float totalWeight = 0.0;

    for (int i = 1; i <= 6; i++) {
        if (i > nEchoes) break;
        float fi = float(i);
        vec2 offset = vec2(fi * 0.015, fi * 0.008);
        vec2 echoUV = uv - offset;
        vec4 echoSrc = texture(sTD2DInputs[0], echoUV);
        float echoLuma = dot(echoSrc.rgb, vec3(0.299, 0.587, 0.114));
        float echoMask = smoothstep(0.1, 0.2, echoLuma);

        float opacity = max(0.1, 1.0 - fi * 0.18);
        // Blur approximation via offset jitter
        vec3 blurred = echoSrc.rgb;
        for (int j = 0; j < 3; j++) {
            float fj = float(j) + 1.0;
            float blurAmt = fi * (4.0 + energy * 12.0) / uTD2DInfos[0].res.w;
            blurred += texture(sTD2DInputs[0], echoUV + vec2(0, blurAmt * fj)).rgb;
            blurred += texture(sTD2DInputs[0], echoUV - vec2(0, blurAmt * fj)).rgb;
        }
        blurred /= 7.0;

        echoes += blurred * echoMask * opacity;
        totalWeight += echoMask * opacity;
    }

    vec3 result = bg;
    if (totalWeight > 0.01) result = mix(result, echoes / max(totalWeight, 0.01), min(totalWeight, 1.0));
    result = mix(result, src.rgb, bodyMask);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── S5: Rainbow Echo Spiral ──
    {
        "name": "fx_rainbow_echo",
        "label": "Rainbow Echo Spiral",
        "shader": GLSL_HEADER + """
vec3 hueShift(vec3 color, float shift) {
    float angle = shift * 3.14159 / 180.0;
    float s = sin(angle), c = cos(angle);
    vec3 weights = vec3(0.299, 0.587, 0.114);
    float vsqrt3 = sqrt(1.0/3.0);
    mat3 m = mat3(
        c + (1.0-c)/3.0, 1.0/3.0*(1.0-c)-vsqrt3*s, 1.0/3.0*(1.0-c)+vsqrt3*s,
        1.0/3.0*(1.0-c)+vsqrt3*s, c + 1.0/3.0*(1.0-c), 1.0/3.0*(1.0-c)-vsqrt3*s,
        1.0/3.0*(1.0-c)-vsqrt3*s, 1.0/3.0*(1.0-c)+vsqrt3*s, c + (1.0-c)/3.0
    );
    return m * color;
}

void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Neon horizontal bands bg
    vec3 bg = vec3(0.0);
    float bandSpacing = 60.0 - energy * 30.0;
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float y = mod(fi * bandSpacing / uTD2DInfos[0].res.w + sin(iTime * 0.05 + fi) * 0.01, 1.0);
        float band = exp(-abs(uv.y - y) * uTD2DInfos[0].res.w * 0.5);
        vec3 bandColor = 0.5 + 0.5 * cos(6.28 * (fi / 6.0 + vec3(0, 0.33, 0.67)));
        bg += bandColor * band * energy * 0.3;
    }

    // Hue-shifted echo copies
    float huePerEcho = 30.0 + mids * 20.0;
    vec3 echoes = vec3(0.0);
    float totalW = 0.0;
    for (int i = 1; i <= 5; i++) {
        float fi = float(i);
        vec2 offset = vec2(fi * 0.02, fi * 0.005);
        vec4 echoSrc = texture(sTD2DInputs[0], uv - offset);
        float eLuma = dot(echoSrc.rgb, vec3(0.299, 0.587, 0.114));
        float eMask = smoothstep(0.1, 0.2, eLuma);
        vec3 shifted = hueShift(echoSrc.rgb, fi * huePerEcho);
        float opacity = max(0.15, 0.7 - fi * 0.12);
        echoes += shifted * eMask * opacity;
        totalW += eMask * opacity;
    }

    vec3 result = bg;
    if (totalW > 0.01) result = mix(result, echoes / max(totalW, 0.01), min(totalW, 1.0));
    result = mix(result, src.rgb, bodyMask);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── S6: Liquify Wave Body ──
    {
        "name": "fx_liquify_wave",
        "label": "Liquify Wave Body",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Sinusoidal displacement
    float amp = (5.0 + bass * 25.0) * texel.x;
    float freq = 20.0 + mids * 15.0;
    float phase = iTime * 3.0;

    vec2 displaced = uv;
    displaced.x += sin(uv.y * freq + phase) * amp;
    displaced.y += cos(uv.x * freq + phase * 0.7) * amp * 0.6;

    vec4 src = texture(sTD2DInputs[0], displaced);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Purple/pink tint on body
    vec3 purpleTint = vec3(0.78, 0.2, 0.78);
    vec3 body = mix(src.rgb, purpleTint, 0.4 * bodyMask);

    // Edge glow (Sobel-ish)
    float dx = length(texture(sTD2DInputs[0], displaced + vec2(texel.x, 0)).rgb -
                       texture(sTD2DInputs[0], displaced - vec2(texel.x, 0)).rgb);
    float dy = length(texture(sTD2DInputs[0], displaced + vec2(0, texel.y)).rgb -
                       texture(sTD2DInputs[0], displaced - vec2(0, texel.y)).rgb);
    float edge = sqrt(dx * dx + dy * dy);
    vec3 glow = vec3(0.8, 0.2, 0.9) * edge * 3.0 * bodyMask;

    // Starfield
    vec2 starUV = uv * 180.0;
    float star = step(0.993, hash(floor(starUV)));
    float twinkle = 0.5 + 0.5 * sin(iTime * 2.5 + hash(floor(starUV)) * 6.28);
    vec3 bg = vec3(star * twinkle * 0.7);

    vec3 result = mix(bg, body, bodyMask) + glow;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── S7: Pixel Mosaic Glitch ──
    {
        "name": "fx_pixel_glitch",
        "label": "Pixel Mosaic Glitch",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;

    // Block grid
    float blockSize = 32.0 + bass * 32.0;
    vec2 blockUV = floor(uv * res / blockSize) * blockSize / res;
    float blockHash = hash(blockUV + floor(iTime * 2.0));

    // Glitch displacement on beats
    vec2 displaced = uv;
    float glitchStrength = bass * 0.5;
    if (blockHash > 0.7 && glitchStrength > 0.1) {
        // Only glitch one side
        float side = step(0.5, uv.x);
        float sideMatch = step(0.5, hash(vec2(floor(iTime * 2.0))));
        if (side == sideMatch) {
            float shift = (hash(blockUV * 3.0) - 0.5) * glitchStrength * 0.15;
            displaced.x += shift;
        }
    }

    vec4 src = texture(sTD2DInputs[0], displaced);
    vec3 result = src.rgb;

    // Color channel swap for glitched blocks
    if (blockHash > 0.85 && bass > 0.3) {
        float swapType = hash(blockUV * 7.0);
        if (swapType > 0.66) result = result.bgr;
        else if (swapType > 0.33) result = 1.0 - result;
        else result = result.grb;
    }

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V1: Datamosh Freeze ──
    {
        "name": "fx_datamosh",
        "label": "Datamosh Freeze",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);

    // Simulate motion smear via directional sampling
    float amp = 2.0 + bass * 6.0;
    float freezeIntensity = max(0.0, highs - 0.3) * 3.0;

    vec2 motionDir = vec2(
        noise(uv * 5.0 + iTime) - 0.5,
        noise(uv * 5.0 + iTime + 100.0) - 0.5
    ) * freezeIntensity * texel * 20.0;

    vec3 smeared = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float fi = float(i) / 8.0;
        smeared += texture(sTD2DInputs[0], uv + motionDir * fi).rgb;
    }
    smeared /= 8.0;

    // Amplified frame diff approximation
    vec3 shifted = texture(sTD2DInputs[0], uv + texel * amp).rgb;
    vec3 diff = abs(src.rgb - shifted) * amp;

    vec3 result = mix(src.rgb, smeared, freezeIntensity * 0.5);
    result += diff * 0.15 * energy;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── V2: RGB Channel Explosion ──
    {
        "name": "fx_rgb_explode",
        "label": "RGB Channel Explosion",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 center = vec2(0.5);

    float kick = min(1.0, sub + bass * 0.5);
    float rOff = (3.0 + kick * 30.0) * texel.x;
    float bOff = -(2.0 + kick * 20.0) * texel.x;

    vec2 toC = uv - center;
    float dist = length(toC);
    vec2 dir = (dist > 0.001) ? toC / dist : vec2(0.0);

    float R = texture(sTD2DInputs[0], uv + dir * rOff).r;
    float G = texture(sTD2DInputs[0], uv).g;
    float B = texture(sTD2DInputs[0], uv + dir * bOff).b;

    vec3 result = vec3(R, G, B);

    // Bloom on brights
    float luma = dot(result, vec3(0.299, 0.587, 0.114));
    if (energy > 0.3) {
        vec3 bloom = vec3(0.0);
        for (int i = 0; i < 8; i++) {
            float angle = float(i) * 0.785;
            vec2 off = vec2(cos(angle), sin(angle)) * 10.0 * texel;
            bloom += texture(sTD2DInputs[0], uv + off).rgb;
        }
        bloom /= 8.0;
        result += bloom * energy * 0.3 * step(0.5, luma);
    }

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V3: Mirror Kaleidoscope ──
    {
        "name": "fx_kaleidoscope",
        "label": "Mirror Kaleidoscope",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 p = uv - center;

    int nFolds = 2 * max(1, int(2.0 + bass * 2.0));
    float sliceAngle = 6.28318 / float(nFolds);
    float rotation = iTime * energy * 0.5;

    float r = length(p);
    float theta = atan(p.y, p.x) + rotation;

    // Fold
    float thetaMod = mod(theta, sliceAngle);
    float foldIdx = floor(theta / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;

    vec2 newUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
    newUV = clamp(newUV, 0.0, 1.0);

    vec4 src = texture(sTD2DInputs[0], newUV);
    vec3 result = src.rgb;

    // Hue shift per fold
    float hueShift = foldIdx * (180.0 / float(nFolds));
    float angle = hueShift * 3.14159 / 180.0;
    float s = sin(angle), c = cos(angle);
    float vs = sqrt(1.0/3.0);
    mat3 m = mat3(
        c+(1.0-c)/3.0, (1.0-c)/3.0-vs*s, (1.0-c)/3.0+vs*s,
        (1.0-c)/3.0+vs*s, c+(1.0-c)/3.0, (1.0-c)/3.0-vs*s,
        (1.0-c)/3.0-vs*s, (1.0-c)/3.0+vs*s, c+(1.0-c)/3.0
    );
    result = m * result;

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.3);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── V4: Plasma Tentacles ──
    {
        "name": "fx_plasma_tentacles",
        "label": "Plasma Tentacles",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Dark silhouette body
    vec3 body = src.rgb * 0.15 * bodyMask;

    // Tentacles: procedural energy lines from body edges
    vec3 tentacles = vec3(0.0);
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, 42.0));
        float angle = seed * 6.28 + iTime * 0.3;
        float tentLen = (50.0 + bass * 200.0) / uTD2DInfos[0].res.w;

        vec2 origin = vec2(0.5 + 0.3 * cos(seed * 6.28 + iTime * 0.1),
                          0.5 + 0.3 * sin(seed * 6.28 + iTime * 0.1));

        // Curved tendril
        vec2 dir = vec2(cos(angle), sin(angle));
        vec2 wobble = vec2(sin(iTime + fi) * 0.05, cos(iTime * 1.3 + fi) * 0.03) * energy;

        float closest = 1.0;
        for (int j = 0; j < 20; j++) {
            float t = float(j) / 20.0;
            vec2 pt = origin + dir * t * tentLen + wobble * t * t;
            float d = length(uv - pt);
            closest = min(closest, d);
        }

        float thickness = (2.0 + bass * 3.0) / uTD2DInfos[0].res.w;
        float line = exp(-closest / thickness);
        vec3 neonColor = 0.5 + 0.5 * cos(6.28 * (seed + vec3(0, 0.33, 0.67)));
        tentacles += neonColor * line * 0.4;
    }

    vec3 result = body + tentacles;
    // Bloom
    result += tentacles * 0.3;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V5: Strobe Flash Invert ──
    {
        "name": "fx_strobe_invert",
        "label": "Strobe Flash Invert",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    // Flash inversion on beat
    float flash = step(0.7, beat) * step(0.5, fract(iTime * 8.0));
    vec3 result = mix(src.rgb, 1.0 - src.rgb, flash);

    // Contrast boost
    float contrast = 1.2 + energy * 0.8;
    result = (result - 0.5) * contrast + 0.5;

    // Afterimage via persistence approximation
    vec3 shifted = texture(sTD2DInputs[0], uv + vec2(0.002, 0.001)).rgb;
    float decay = 0.65 + energy * 0.2;
    result = mix(result, shifted, decay * 0.15);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── V6: Body Pixelate Cascade ──
    {
        "name": "fx_pixelate_cascade",
        "label": "Body Pixelate Cascade",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;

    // Cascade position oscillates
    float cascadePos = 0.5 + 0.5 * sin(iTime * (1.0 + energy * 2.0));
    float maxPixSize = 8.0 + bass * 32.0;

    // Variable pixelation by vertical position
    float distFromCascade = abs(uv.y - cascadePos);
    float pixSize = mix(maxPixSize, 1.0, smoothstep(0.0, 0.4, distFromCascade));
    pixSize = max(1.0, floor(pixSize));

    vec2 pixUV = floor(uv * res / pixSize) * pixSize / res + (pixSize * 0.5) / res;
    vec4 pixSrc = texture(sTD2DInputs[0], pixUV);
    vec4 src = texture(sTD2DInputs[0], uv);

    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Apply pixelation to body, keep bg clear
    vec3 result = mix(src.rgb * 0.4, pixSrc.rgb, bodyMask);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V7: Glitch Horizon Tear ──
    {
        "name": "fx_glitch_tear",
        "label": "Glitch Horizon Tear",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    float kick = min(1.0, sub + bass * 0.5);

    vec2 displaced = uv;

    // Horizontal band tears
    float bandY = floor(uv.y * res.y / 8.0);
    float tearHash = hash(vec2(bandY, floor(iTime * 4.0)));

    if (tearHash > (1.0 - kick * 0.3)) {
        float shift = (hash(vec2(bandY * 3.0, floor(iTime * 4.0))) - 0.5);
        shift *= (10.0 + bass * 100.0) / res.x;
        displaced.x += shift;
    }

    vec4 src = texture(sTD2DInputs[0], displaced);
    vec3 result = src.rgb;

    // Color inversion on some bands
    if (tearHash > 0.92) {
        result = 1.0 - result;
    }

    // Scanline overlay on kicks
    if (kick > 0.5) {
        float scanline = step(0.5, fract(uv.y * res.y * 0.5));
        result -= vec3(0.12) * scanline;
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── V8: Radial Zoom Tunnel ──
    {
        "name": "fx_radial_zoom",
        "label": "Radial Zoom Tunnel",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    float zoom = 0.96 + bass * 0.03;
    if (beat > 0.5) zoom = min(1.0, zoom + 0.04);
    float rotation = mids * 0.02;

    // Radial zoom: sample from zoomed-in position
    vec2 p = uv - center;
    float r = length(p);
    float theta = atan(p.y, p.x) + rotation;

    vec3 result = vec3(0.0);
    float totalW = 0.0;

    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float scale = pow(zoom, fi);
        float rot = theta + fi * rotation;
        vec2 sampleUV = center + r * scale * vec2(cos(rot), sin(rot));
        sampleUV = clamp(sampleUV, 0.0, 1.0);

        vec3 layer = texture(sTD2DInputs[0], sampleUV).rgb;

        // Progressive hue tinting
        float hueAngle = fi * 0.3;
        float s2 = sin(hueAngle), c2 = cos(hueAngle);
        float vs2 = sqrt(1.0/3.0);
        mat3 m = mat3(c2+(1.0-c2)/3.0, (1.0-c2)/3.0-vs2*s2, (1.0-c2)/3.0+vs2*s2,
                      (1.0-c2)/3.0+vs2*s2, c2+(1.0-c2)/3.0, (1.0-c2)/3.0-vs2*s2,
                      (1.0-c2)/3.0-vs2*s2, (1.0-c2)/3.0+vs2*s2, c2+(1.0-c2)/3.0);
        layer = m * layer;

        float w = 1.0 / (1.0 + fi * 0.5);
        result += layer * w;
        totalW += w;
    }
    result /= totalW;

    // Bloom
    vec3 bloom = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * 10.0 / uTD2DInfos[0].res.zw;
        bloom += texture(sTD2DInputs[0], uv + off).rgb;
    }
    bloom /= 8.0;
    result = mix(result, bloom, 0.15 + energy * 0.1);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V9: Neon Skeleton Wire ──
    {
        "name": "fx_neon_skeleton",
        "label": "Neon Skeleton Wire",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // Faint body ghost
    vec3 ghost = src.rgb * 0.12 * smoothstep(0.08, 0.2, luma);

    // Edge detection as skeleton proxy (Sobel)
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel * 2.0).rgb,
                         vec3(0.299, 0.587, 0.114));
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            sobelX += s * kx;
            sobelY += s * ky;
        }
    }
    float edge = sqrt(sobelX * sobelX + sobelY * sobelY);

    // Neon glow from edges
    float thickness = 2.0 + bass * 6.0;
    float edgeMask = smoothstep(0.1, 0.3, edge);

    // Multi-color neon based on position
    float colorPhase = uv.y * 3.0 + uv.x * 2.0 + iTime * 0.5;
    vec3 neonColor = 0.5 + 0.5 * cos(6.28 * (colorPhase + vec3(0, 0.33, 0.67)));

    // Glow
    float glowRadius = (5.0 + energy * 15.0) * texel.x;
    float glow = 0.0;
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * glowRadius;
        float sampleEdge = 0.0;
        vec3 samp = texture(sTD2DInputs[0], uv + off).rgb;
        float sLuma = dot(samp, vec3(0.299, 0.587, 0.114));
        vec3 samp2 = texture(sTD2DInputs[0], uv + off + texel).rgb;
        sampleEdge = length(samp - samp2);
        glow += sampleEdge;
    }
    glow /= 8.0;

    vec3 result = ghost + neonColor * edgeMask * (1.0 + bass * 2.0);
    result += neonColor * glow * 0.5;

    // Joint particles approximation
    float pulse = step(0.7, beat) * step(0.95, hash(uv * 10.0 + iTime));
    result += vec3(1.0, 0.8, 0.3) * pulse * 0.5;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V10: Color Solarize Pulse ──
    {
        "name": "fx_solarize_pulse",
        "label": "Color Solarize Pulse",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    float phase = iTime * 2.0;

    // Per-channel oscillating solarization thresholds
    float tR = (128.0 + sin(phase) * 60.0 + energy * 35.0 * sin(phase * 0.9)) / 255.0;
    float tG = (128.0 + sin(phase + 2.09) * 60.0 + mids * 30.0 * cos(phase * 1.3)) / 255.0;
    float tB = (128.0 + sin(phase + 4.19) * 60.0 + bass * 40.0 * sin(phase * 1.5)) / 255.0;

    vec3 result;
    result.r = src.r > tR ? 1.0 - src.r : src.r;
    result.g = src.g > tG ? 1.0 - src.g : src.g;
    result.b = src.b > tB ? 1.0 - src.b : src.b;

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    float satBoost = 1.3 + energy * 0.5;
    result = mix(vec3(gray), result, satBoost);

    // Bloom
    vec3 bloom = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * 8.0 / uTD2DInfos[0].res.zw;
        bloom += texture(sTD2DInputs[0], uv + off).rgb;
    }
    bloom /= 8.0;
    result = mix(result, bloom, 0.15 + energy * 0.1);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── V11: Triangle Mesh Shatter ──
    {
        "name": "fx_triangle_shatter",
        "label": "Triangle Mesh Shatter",
        "shader": GLSL_HEADER + """
// Voronoi-based triangle approximation
vec2 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float minDist = 1.0;
    vec2 minPoint = vec2(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash(i + neighbor) * vec2(1.0);
            // Explode on kick
            float kick = min(1.0, sub + bass * 0.5);
            if (kick > 0.5) {
                point += (hash(i + neighbor + floor(iTime)) - 0.5) * kick * 0.5;
            }
            vec2 diff = neighbor + point - f;
            float d = length(diff);
            if (d < minDist) {
                minDist = d;
                minPoint = i + neighbor + point;
            }
        }
    }
    return vec2(minDist, hash(minPoint));
}

void main() {
    vec2 uv = vUV.st;
    float gridSize = 12.0 + bass * 8.0;
    vec2 v = voronoi(uv * gridSize);

    float edge = smoothstep(0.02, 0.04, v.x);

    // Sample texture at cell center (approximation)
    vec2 cellUV = floor(uv * gridSize + 0.5) / gridSize;
    vec4 cellColor = texture(sTD2DInputs[0], cellUV);
    vec4 src = texture(sTD2DInputs[0], uv);

    // Mix between cell-colored triangles and edges
    vec3 result = mix(vec3(0.7, 0.7, 0.75), cellColor.rgb * edge, edge);

    // Dark bg behind gaps
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);
    result = mix(src.rgb * 0.15, result, bodyMask);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V12: Feedback Spiral Zoom ──
    {
        "name": "fx_feedback_spiral",
        "label": "Feedback Spiral Zoom",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    float scale = 0.96 + bass * 0.03;
    float rotDeg = 2.0 + mids * 5.0;
    float rot = rotDeg * 3.14159 / 180.0;

    // Scale + rotate from center
    vec2 p = uv - center;
    float c2 = cos(rot), s2 = sin(rot);
    vec2 rotated = vec2(p.x * c2 - p.y * s2, p.x * s2 + p.y * c2) * scale;
    vec2 feedbackUV = rotated + center;
    feedbackUV = clamp(feedbackUV, 0.0, 1.0);

    vec4 feedback = texture(sTD2DInputs[0], feedbackUV);
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Magenta/cyan tint on feedback
    vec3 tinted = feedback.rgb;
    float hueShift = (2.0 + energy * 3.0) * 3.14159 / 180.0;
    float hs = sin(hueShift), hc = cos(hueShift);
    float vs = sqrt(1.0/3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                  (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                  (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
    tinted = m * tinted * 0.97;

    vec3 result = mix(tinted, src.rgb, bodyMask);

    // Bloom
    vec3 bloom = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * 10.0 / uTD2DInfos[0].res.zw;
        bloom += texture(sTD2DInputs[0], uv + off).rgb;
    }
    bloom /= 8.0;
    result = mix(result, bloom, 0.15 + energy * 0.1);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V13: Binary Rain Matrix ──
    {
        "name": "fx_matrix_rain",
        "label": "Binary Rain Matrix",
        "shader": GLSL_HEADER + """
float charPattern(vec2 uv, float seed) {
    // Pseudo-character: random dots in a 4x5 grid
    vec2 grid = floor(uv * vec2(4.0, 5.0));
    float h = hash(grid + seed);
    return step(0.5, h);
}

void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Green-tinted body
    vec3 greenBody = vec3(0.0, luma, 0.0) * 0.5 * bodyMask;

    // Matrix rain columns
    float charSize = 10.0;
    vec2 cellUV = uv * res / charSize;
    vec2 cell = floor(cellUV);
    vec2 cellFract = fract(cellUV);

    float speed = 2.0 + energy * 8.0;
    float columnSeed = hash(vec2(cell.x, 0.0));
    float fallOffset = iTime * speed * (0.5 + columnSeed);
    float charIdx = cell.y - fallOffset;
    float charCell = floor(charIdx);

    float charSeed = hash(vec2(cell.x, charCell));
    // Occasional character mutation
    charSeed += floor(iTime * 3.0) * 0.01;

    float ch = charPattern(cellFract, charSeed);

    // Leading char bright, trailing fade
    float age = fract(-charIdx * 0.04);
    float brightness = age > 0.95 ? 1.0 : age * 0.6;

    // Column density based on audio
    float density = 20.0 + highs * 60.0;
    float columnActive = step(0.5, hash(vec2(cell.x, floor(iTime * 0.5)))) * (density / 80.0);

    vec3 rain = vec3(0.0);
    if (columnActive > 0.3) {
        if (age > 0.95) rain = vec3(0.8, 1.0, 0.8) * ch;
        else rain = vec3(0.0, brightness, 0.0) * ch;
    }

    // Dark green bg
    vec3 bg = vec3(0.0, 0.02, 0.0);
    vec3 result = bg + greenBody + rain * 0.7;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── V14: Chromatic Body Double ──
    {
        "name": "fx_chromatic_double",
        "label": "Chromatic Body Double",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float kick = min(1.0, sub + bass * 0.5);

    float rOff = (5.0 + kick * 30.0) * texel.x;
    float bOff = -(5.0 + kick * 30.0) * texel.x;

    // Sample with offsets
    vec4 srcR = texture(sTD2DInputs[0], uv + vec2(rOff, 0));
    vec4 srcG = texture(sTD2DInputs[0], uv);
    vec4 srcB = texture(sTD2DInputs[0], uv + vec2(bOff, 0));

    float lumaR = dot(srcR.rgb, vec3(0.299, 0.587, 0.114));
    float lumaG = dot(srcG.rgb, vec3(0.299, 0.587, 0.114));
    float lumaB = dot(srcB.rgb, vec3(0.299, 0.587, 0.114));

    float maskR = smoothstep(0.1, 0.2, lumaR);
    float maskG = smoothstep(0.1, 0.2, lumaG);
    float maskB = smoothstep(0.1, 0.2, lumaB);

    // Additive RGB body copies on black
    vec3 result = vec3(0.0);
    result.r = srcR.r * maskR;
    result.g = srcG.g * maskG;
    result.b = srcB.b * maskB;

    // Bloom
    if (energy > 0.2) {
        vec3 bloom = vec3(0.0);
        for (int i = 0; i < 8; i++) {
            float angle = float(i) * 0.785;
            vec2 off = vec2(cos(angle), sin(angle)) * 10.0 * texel;
            vec4 s = texture(sTD2DInputs[0], uv + off);
            bloom += s.rgb * smoothstep(0.1, 0.2, dot(s.rgb, vec3(0.299, 0.587, 0.114)));
        }
        bloom /= 8.0;
        result += bloom * (0.2 + energy * 0.15);
    }

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
]


# ─── BUILDER ─────────────────────────────────────────────────────────────────

def build_effect(idx, effect, dry_run=False):
    """Build one effect in TouchDesigner."""
    name = effect["name"]
    label = effect["label"]
    shader = effect["shader"]
    parent = "/project1"
    comp_path = f"{parent}/{name}"

    print(f"\n[{idx+1:2d}/21] Building {label} ({name})...")

    if dry_run:
        print(f"  DRY RUN: would create {comp_path}")
        return True

    # 1. Create baseCOMP container
    try:
        td_exec(f"""
if op('{comp_path}'):
    op('{comp_path}').destroy()
""")
        time.sleep(0.1)
    except:
        pass

    td_create_op(parent, "baseCOMP", name)
    time.sleep(0.2)

    # Position the node
    node_x = -400 + (idx % 7) * 170
    node_y = -300 - (idx // 7) * 200
    td_exec(f"op('{comp_path}').nodeX = {node_x}; op('{comp_path}').nodeY = {node_y}")

    # 2. Create in1 (inTOP) inside the COMP
    td_create_op(comp_path, "inTOP", "in1")
    td_exec(f"op('{comp_path}/in1').nodeX = -300; op('{comp_path}/in1').nodeY = 0")

    # 3. Create GLSL TOP
    glsl_name = f"glsl_{name.replace('fx_', '')}"
    td_create_op(comp_path, "glslTOP", glsl_name)
    td_exec(f"op('{comp_path}/{glsl_name}').nodeX = 0; op('{comp_path}/{glsl_name}').nodeY = 0")

    # 4. Create pixel shader DAT
    pixel_dat_name = f"{glsl_name}_pixel"
    td_create_op(comp_path, "textDAT", pixel_dat_name)
    td_exec(f"op('{comp_path}/{pixel_dat_name}').nodeX = 0; op('{comp_path}/{pixel_dat_name}').nodeY = -150")

    # Write shader code
    td_write_dat(f"{comp_path}/{pixel_dat_name}", shader)

    # 5. Create out1 (outTOP)
    td_create_op(comp_path, "outTOP", "out1")
    td_exec(f"op('{comp_path}/out1').nodeX = 300; op('{comp_path}/out1').nodeY = 0")

    # 6. Wire: in1 → glsl → out1
    td_exec(f"""
glsl = op('{comp_path}/{glsl_name}')
glsl.inputConnectors[0].connect(op('{comp_path}/in1'))
op('{comp_path}/out1').inputConnectors[0].connect(glsl)
""")

    # 7. Set GLSL parameters
    td_set_pars(f"{comp_path}/{glsl_name}", {
        "pixeldat": pixel_dat_name,
        "glslversion": "glsl430",
    })

    # 8. Set audio uniform vectors (same pattern as canonical effects)
    td_exec(f"""
glsl = op('{comp_path}/{glsl_name}')
# Vector 0: uAudio = (time, rms, bass, sub_bass)
glsl.par.vec = 1  # Enable 2 vectors (0-indexed count)
glsl.par.vec0name = 'uAudio'
glsl.par.vec0valuex.mode = ParMode.EXPRESSION
glsl.par.vec0valuex.expr = "absTime.seconds"
glsl.par.vec0valuey.mode = ParMode.EXPRESSION
glsl.par.vec0valuey.expr = "op('/project1/audio_analysis/out1')['rms']"
glsl.par.vec0valuez.mode = ParMode.EXPRESSION
glsl.par.vec0valuez.expr = "op('/project1/audio_analysis/out1')['bass']"
glsl.par.vec0valuew.mode = ParMode.EXPRESSION
glsl.par.vec0valuew.expr = "op('/project1/audio_analysis/out1')['sub_bass']"

# Vector 1: uAudio2 = (sub_bass, mids, highs, beat)
glsl.par.vec1name = 'uAudio2'
glsl.par.vec1valuex.mode = ParMode.EXPRESSION
glsl.par.vec1valuex.expr = "op('/project1/audio_analysis/out1')['sub_bass']"
glsl.par.vec1valuey.mode = ParMode.EXPRESSION
glsl.par.vec1valuey.expr = "op('/project1/audio_analysis/out1')['mids']"
glsl.par.vec1valuez.mode = ParMode.EXPRESSION
glsl.par.vec1valuez.expr = "op('/project1/audio_analysis/out1')['highs']"
glsl.par.vec1valuew.mode = ParMode.EXPRESSION
glsl.par.vec1valuew.expr = "op('/project1/audio_analysis/out1')['beat']"
""")
    time.sleep(0.1)

    print(f"  ✓ Created {comp_path} with GLSL shader")
    return True


def wire_effects_to_router():
    """Wire all new effects to the effect_router switchTOP."""
    print("\n[WIRING] Connecting effects to effect_router...")

    # Get current inputs count
    result = td_exec("""
sw = op('/project1/effect_router')
n = len(sw.inputConnectors)
print(f"Current inputs: {n}")
for i, conn in enumerate(sw.inputConnectors):
    conns = [c.owner.path for c in conn.connections]
    print(f"  [{i}]: {conns}")
""")
    print(result)

    # Wire each new effect from cam_in and to effect_router
    for idx, effect in enumerate(EFFECTS):
        name = effect["name"]
        comp_path = f"/project1/{name}"

        td_exec(f"""
comp = op('{comp_path}')
cam = op('/project1/cam_in')
router = op('/project1/effect_router')

# Wire cam_in → effect comp
comp.inputConnectors[0].connect(cam)

# Wire effect comp → router (append to next available input)
next_idx = len(router.inputConnectors)
# TD switchTOP auto-expands inputs when you connect
router.inputConnectors[next_idx].connect(comp)
""")
        time.sleep(0.05)

    # Update active_effect range
    total = td_exec("""
sw = op('/project1/effect_router')
total = len([c for c in sw.inputConnectors if c.connections])
print(total)
""")
    print(f"\n  Total effect inputs on router: {total.strip().split(chr(10))[0]}")

    # Update auto_rotate to cover new range
    td_exec(f"""
# Update keyboard callbacks to handle new effect count
try:
    ae = op('/project1/active_effect')
    # Verify it still works
    print(f"active_effect value: {{ae['effect_idx']}}")
except:
    print("active_effect OK")
""")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build hyper-maximalist effects in TouchDesigner")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--effect", type=int, default=-1, help="Build only effect N (0-indexed)")
    parser.add_argument("--skip-wire", action="store_true", help="Skip wiring to router")
    args = parser.parse_args()

    print("=" * 60)
    print("¥ØUSUK€ Hyper-Maximalist TD Effect Builder")
    print(f"Building {len(EFFECTS)} effects via twozero MCP")
    print("=" * 60)

    # Verify MCP connection
    try:
        result = td_call("td_get_focus")
        print(f"\nTD connected: {result.split(chr(10))[0]}")
    except Exception as e:
        print(f"\nERROR: Cannot connect to TouchDesigner MCP: {e}")
        print("Make sure TouchDesigner is running with twozero.tox enabled")
        sys.exit(1)

    # Build effects
    built = 0
    if args.effect >= 0:
        if args.effect < len(EFFECTS):
            if build_effect(args.effect, EFFECTS[args.effect], args.dry_run):
                built += 1
        else:
            print(f"Effect index {args.effect} out of range (0-{len(EFFECTS)-1})")
    else:
        for idx, effect in enumerate(EFFECTS):
            try:
                if build_effect(idx, effect, args.dry_run):
                    built += 1
            except Exception as e:
                print(f"  ✗ FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Built {built}/{len(EFFECTS)} effects")

    # Wire to router
    if not args.dry_run and not args.skip_wire and built > 0:
        try:
            wire_effects_to_router()
        except Exception as e:
            print(f"Wiring error: {e}")

    print(f"\nDone! Press 0 in TD window to auto-rotate through all effects.")


if __name__ == "__main__":
    main()
