#!/usr/bin/env python3
"""
Build 21 mutated GLSL effects in TouchDesigner via twozero MCP bridge.

Each mutation takes an existing effect and twists it into something new.
Same architecture as td_build_effects.py: baseCOMP with in1 -> glslTOP -> out1.

Usage:
  python3 tools/td_build_mutations.py           # Build all 21 mutations
  python3 tools/td_build_mutations.py --dry-run # Print what would be done
  python3 tools/td_build_mutations.py --effect 0 # Build only mutation #0
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


# --- GLSL SHADERS ---------------------------------------------------------------

GLSL_HEADER = """// YOUSUKE Mutation Effect
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

MUTATIONS = [
    # -- M1: Acid Confetti (confetti_storm mutation) --
    {
        "name": "fx_mut_acid_confetti",
        "label": "Acid Confetti",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // Cyan/lime body tint
    vec3 body = mix(src.rgb, vec3(0.0, 1.0, 0.7), 0.5 * step(0.15, luma));

    // Starfield bg
    vec2 starUV = uv * 250.0;
    float star = step(0.991, hash(floor(starUV)));
    float twinkle = 0.5 + 0.5 * sin(iTime * 4.0 + hash(floor(starUV)) * 6.28);
    vec3 bg = vec3(star * twinkle * 0.9);

    // 90 particles (3x), reversed gravity (upward), driven by highs
    float confetti = 0.0;
    vec3 confettiColor = vec3(0.0);
    for (int i = 0; i < 90; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 0.7));
        float t = iTime * (0.5 + seed) + fi;
        vec2 pos = vec2(
            fract(seed + sin(t * 0.3) * 0.4),
            fract(fi * 0.0111 + t * 0.2 * (0.5 + highs))  // upward
        );
        float d = length((uv - pos) * vec2(1.0, 1.78));
        float size = 0.004 + highs * 0.01;
        if (d < size) {
            // Cyan/lime/magenta palette
            vec3 cc = vec3(0.0);
            float sel = fract(seed * 7.0);
            if (sel < 0.33) cc = vec3(0.0, 1.0, 1.0);
            else if (sel < 0.66) cc = vec3(0.5, 1.0, 0.0);
            else cc = vec3(1.0, 0.0, 1.0);
            confettiColor = cc;
            confetti = 1.0;
        }
    }

    float bodyMask = smoothstep(0.1, 0.2, luma);
    vec3 result = mix(bg, body, bodyMask);
    result = mix(result, confettiColor, confetti * 0.9);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M2: X-Ray Thermal (thermal_posterize mutation) --
    {
        "name": "fx_mut_xray_thermal",
        "label": "X-Ray Thermal",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Aberration driven by bass
    float aberr = 2.0 + max(0.0, bass - 0.2) * 10.0;
    vec2 center = vec2(0.5);
    vec2 toC = uv - center;
    float r = length(toC);
    vec2 dir = (r > 0.001) ? toC / r : vec2(0.0);
    vec2 off = dir * r * r * aberr * texel;

    float R = texture(sTD2DInputs[0], uv + off).r;
    float G = texture(sTD2DInputs[0], uv).g;
    float B = texture(sTD2DInputs[0], uv - off).b;
    float luma = R * 0.299 + G * 0.587 + B * 0.114;

    // Inverted palette: white/purple/black
    float tLow = 0.30 + bass * 0.1;
    float tHigh = 0.65 - bass * 0.1;

    vec3 cBlack  = vec3(0.0, 0.0, 0.0);
    vec3 cPurple = vec3(0.6, 0.1, 0.8);
    vec3 cWhite  = vec3(1.0, 1.0, 1.0);

    vec3 result;
    if (luma < tLow) result = cWhite;        // inverted: bright areas dark
    else if (luma < tHigh) result = cPurple;
    else result = cBlack;

    // Bright body glow
    result += vec3(0.3, 0.1, 0.5) * smoothstep(0.3, 0.6, luma) * energy;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M3: Ice Scanlines (fire_scanlines mutation) --
    {
        "name": "fx_mut_ice_scanlines",
        "label": "Ice Scanlines",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);

    // Dark blue bg
    vec3 bg = vec3(0.02, 0.05, 0.12);
    bg += vec3(0.0, 0.02, 0.05) * step(0.993, hash(floor(uv * 200.0)));

    // Ice noise (blue/cyan palette)
    float iceSpeed = 1.0 + energy * 3.0;
    vec2 iceUV = uv * 5.0 + vec2(iTime * 0.1, -iTime * iceSpeed * 0.2);
    float iceNoise = fbm(iceUV);
    vec3 ice = vec3(
        clamp(iceNoise * 0.4, 0.0, 1.0),
        clamp(iceNoise * 1.5, 0.0, 1.0),
        clamp(iceNoise * 2.0, 0.0, 1.0)
    );

    // Crackle overlay
    float crackle = step(0.75, noise(uv * 40.0 + iTime * 0.3)) * 0.6;
    ice += vec3(0.5, 0.8, 1.0) * crackle * bodyMask;

    vec3 body = mix(src.rgb * vec3(0.5, 0.7, 1.0), ice, bodyMask * 0.5);

    // Diagonal scanlines
    float scanAngle = uv.x * 0.5 + uv.y;
    float scanSpacing = 3.0 + bass * 6.0;
    float scanline = sin(scanAngle * uTD2DInfos[0].res.w / scanSpacing + iTime * 1.5);
    scanline = smoothstep(0.7, 1.0, scanline);
    body = mix(body, vec3(0.6, 0.85, 1.0), scanline * 0.2 * bodyMask);

    vec3 result = mix(bg, body, bodyMask);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M4: Echo Kaleidoscope (echo_trail + kaleidoscope) --
    {
        "name": "fx_mut_echo_kaleidoscope",
        "label": "Echo Kaleidoscope",
        "shader": GLSL_HEADER + """
vec3 hueShift(vec3 color, float shift) {
    float angle = shift * 3.14159 / 180.0;
    float s = sin(angle), c = cos(angle);
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
    vec2 center = vec2(0.5);

    // 6-fold kaleidoscope
    int nFolds = 6;
    float sliceAngle = 6.28318 / float(nFolds);
    float rotation = iTime * energy * 0.3;

    vec3 result = vec3(0.0);
    float totalW = 0.0;

    // 4 echo copies, each through kaleidoscope
    for (int e = 0; e < 4; e++) {
        float fe = float(e);
        vec2 echoOffset = vec2(fe * 0.012, fe * 0.006);
        vec2 echoUV = uv - echoOffset;

        // Apply kaleidoscope
        vec2 p = echoUV - center;
        float r = length(p);
        float theta = atan(p.y, p.x) + rotation + fe * 0.2;
        float thetaMod = mod(theta, sliceAngle);
        float foldIdx = floor(theta / sliceAngle);
        if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;
        vec2 newUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
        newUV = clamp(newUV, 0.0, 1.0);

        vec4 s = texture(sTD2DInputs[0], newUV);
        // Hue shift per echo + fold
        float hue = fe * 40.0 + foldIdx * 30.0;
        vec3 shifted = hueShift(s.rgb, hue);

        float w = 1.0 / (1.0 + fe * 0.4);
        result += shifted * w;
        totalW += w;
    }
    result /= max(totalW, 0.01);

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.5);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M5: Rainbow Shatter (rainbow_echo + triangle_shatter) --
    {
        "name": "fx_mut_rainbow_shatter",
        "label": "Rainbow Shatter",
        "shader": GLSL_HEADER + """
vec2 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float minDist = 1.0;
    vec2 minPoint = vec2(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash(i + neighbor) * vec2(1.0);
            float kick = min(1.0, sub + bass * 0.5);
            if (kick > 0.4) {
                point += (hash(i + neighbor + floor(iTime * 2.0)) - 0.5) * kick * 0.7;
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
    float gridSize = 10.0 + bass * 10.0;
    vec2 v = voronoi(uv * gridSize);

    float edge = smoothstep(0.02, 0.05, v.x);

    vec2 cellUV = floor(uv * gridSize + 0.5) / gridSize;
    vec4 cellColor = texture(sTD2DInputs[0], cellUV);

    // Per-cell hue shift based on cell ID
    float hueAngle = v.y * 6.28 + iTime * 0.5;
    float hs = sin(hueAngle), hc = cos(hueAngle);
    float vs = sqrt(1.0/3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                  (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                  (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
    vec3 shifted = m * cellColor.rgb;

    vec3 result = mix(vec3(0.1), shifted * edge, edge);

    // Beat scatter: cells explode outward
    float scatter = step(0.6, beat) * 0.3;
    result *= (1.0 + scatter);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M6: Liquify Vortex (liquify_wave mutation) --
    {
        "name": "fx_mut_liquify_vortex",
        "label": "Liquify Vortex",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 center = vec2(0.5);

    // 4x displacement + spiral vortex
    float amp = (20.0 + bass * 100.0) * texel.x;
    float freq = 20.0 + mids * 15.0;
    float phase = iTime * 3.0;

    // Vortex rotation from center
    vec2 toC = uv - center;
    float dist = length(toC);
    float vortexAngle = dist * 10.0 * (1.0 + energy * 2.0) - iTime * 3.0;
    float cv = cos(vortexAngle), sv = sin(vortexAngle);
    float vortexStrength = smoothstep(0.5, 0.0, dist) * amp * 2.0;
    vec2 vortexDisp = vec2(cv * toC.x - sv * toC.y, sv * toC.x + cv * toC.y) - toC;
    vortexDisp *= vortexStrength;

    vec2 displaced = uv + vortexDisp;
    displaced.x += sin(uv.y * freq + phase) * amp;
    displaced.y += cos(uv.x * freq + phase * 0.7) * amp * 0.6;

    vec4 src = texture(sTD2DInputs[0], clamp(displaced, 0.0, 1.0));
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Gold/amber tint
    vec3 goldTint = vec3(1.0, 0.75, 0.2);
    vec3 body = mix(src.rgb, goldTint, 0.45 * bodyMask);

    // Edge glow (amber)
    float dx = length(texture(sTD2DInputs[0], clamp(displaced + vec2(texel.x, 0), 0.0, 1.0)).rgb -
                       texture(sTD2DInputs[0], clamp(displaced - vec2(texel.x, 0), 0.0, 1.0)).rgb);
    float dy = length(texture(sTD2DInputs[0], clamp(displaced + vec2(0, texel.y), 0.0, 1.0)).rgb -
                       texture(sTD2DInputs[0], clamp(displaced - vec2(0, texel.y), 0.0, 1.0)).rgb);
    float edge = sqrt(dx * dx + dy * dy);
    vec3 glow = vec3(1.0, 0.6, 0.1) * edge * 4.0 * bodyMask;

    vec3 bg = vec3(0.02, 0.01, 0.0);
    vec3 result = mix(bg, body, bodyMask) + glow;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M7: Pixel Rain (pixel_glitch + matrix_rain) --
    {
        "name": "fx_mut_pixel_rain",
        "label": "Pixel Rain",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;

    // Block grid cascading downward
    float blockSize = 16.0 + bass * 24.0;
    vec2 blockCoord = floor(uv * res / blockSize);
    float blockHash = hash(blockCoord);

    // Rain cascade: blocks fall downward over time
    float fallSpeed = 3.0 + energy * 6.0;
    float fallOffset = iTime * fallSpeed * (0.5 + hash(vec2(blockCoord.x, 0.0)));
    float rainY = mod(blockCoord.y + fallOffset, res.y / blockSize);
    float rainHash = hash(vec2(blockCoord.x, floor(rainY)));

    // Sample from offset position
    vec2 rainUV = vec2(uv.x, fract(uv.y + fallOffset * blockSize / res.y));
    vec2 blockUV = floor(rainUV * res / blockSize) * blockSize / res;
    vec4 src = texture(sTD2DInputs[0], blockUV);

    vec3 result = src.rgb;

    // Random color swap per block on beat
    if (rainHash > 0.6 && beat > 0.5) {
        float swapType = hash(vec2(blockCoord.x, floor(iTime * 4.0)));
        if (swapType > 0.66) result = result.bgr;
        else if (swapType > 0.33) result = result.grb;
        else result = vec3(0.0, result.g * 1.5, result.b * 0.5);
    }

    // Trailing fade (blocks above are dimmer)
    float trail = smoothstep(0.0, 0.3, fract(-rainY * 0.05));
    result *= 0.5 + trail * 0.5;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M8: Datamosh Strobe (datamosh + strobe_invert) --
    {
        "name": "fx_mut_datamosh_strobe",
        "label": "Datamosh Strobe",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);

    // 4x frame diff, high contrast motion smear
    float amp = 4.0 + bass * 12.0;
    float freezeIntensity = max(0.0, highs - 0.2) * 4.0;

    vec2 motionDir = vec2(
        noise(uv * 5.0 + iTime) - 0.5,
        noise(uv * 5.0 + iTime + 100.0) - 0.5
    ) * freezeIntensity * texel * 40.0;

    vec3 smeared = vec3(0.0);
    for (int i = 0; i < 12; i++) {
        float fi = float(i) / 12.0;
        smeared += texture(sTD2DInputs[0], uv + motionDir * fi).rgb;
    }
    smeared /= 12.0;

    // 4x amplified frame diff
    vec3 shifted = texture(sTD2DInputs[0], uv + texel * amp).rgb;
    vec3 diff = abs(src.rgb - shifted) * amp * 4.0;

    vec3 result = mix(src.rgb, smeared, freezeIntensity * 0.6);
    result += diff * 0.2 * energy;

    // Beat-sync inversion
    float flash = step(0.5, beat) * step(0.5, fract(iTime * 6.0));
    result = mix(result, 1.0 - result, flash);

    // High contrast push
    float contrast = 1.8 + energy * 1.0;
    result = (result - 0.5) * contrast + 0.5;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M9: RGB Spiral (rgb_explode mutation) --
    {
        "name": "fx_mut_rgb_spiral",
        "label": "RGB Spiral",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 center = vec2(0.5);

    float kick = min(1.0, mids * 1.5);  // mids-driven
    float baseOff = (9.0 + kick * 60.0) * texel.x;  // 3x offset

    vec2 toC = uv - center;
    float dist = length(toC);
    float angle = atan(toC.y, toC.x);

    // Spiral pattern: offset direction rotates with angle
    float spiralR = angle + dist * 8.0 - iTime * 2.0;
    float spiralG = angle + dist * 8.0 - iTime * 2.0 + 2.094;  // 120 deg
    float spiralB = angle + dist * 8.0 - iTime * 2.0 + 4.189;  // 240 deg

    vec2 offR = vec2(cos(spiralR), sin(spiralR)) * baseOff;
    vec2 offG = vec2(cos(spiralG), sin(spiralG)) * baseOff;
    vec2 offB = vec2(cos(spiralB), sin(spiralB)) * baseOff;

    float R = texture(sTD2DInputs[0], uv + offR).r;
    float G = texture(sTD2DInputs[0], uv + offG).g;
    float B = texture(sTD2DInputs[0], uv + offB).b;

    vec3 result = vec3(R, G, B);

    // Bloom on brights
    float luma = dot(result, vec3(0.299, 0.587, 0.114));
    if (energy > 0.2) {
        vec3 bloom = vec3(0.0);
        for (int i = 0; i < 8; i++) {
            float a = float(i) * 0.785;
            vec2 off = vec2(cos(a), sin(a)) * 12.0 * texel;
            bloom += texture(sTD2DInputs[0], uv + off).rgb;
        }
        bloom /= 8.0;
        result += bloom * energy * 0.4 * step(0.4, luma);
    }

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M10: Hyper Kaleidoscope (kaleidoscope mutation) --
    {
        "name": "fx_mut_hyper_kaleidoscope",
        "label": "Hyper Kaleidoscope",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 p = uv - center;

    // 12-24 folds (3x the original)
    int nFolds = 2 * max(1, int(6.0 + bass * 6.0));
    float sliceAngle = 6.28318 / float(nFolds);
    float rotation = iTime * energy * 1.5;  // 3x rotation

    float r = length(p);
    float theta = atan(p.y, p.x) + rotation;

    float thetaMod = mod(theta, sliceAngle);
    float foldIdx = floor(theta / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;

    // Per-fold scale zoom on beat
    float foldZoom = 1.0 + step(0.5, beat) * 0.15 * sin(foldIdx * 1.5);
    vec2 newUV = center + r * foldZoom * vec2(cos(thetaMod), sin(thetaMod));
    newUV = clamp(newUV, 0.0, 1.0);

    vec4 src = texture(sTD2DInputs[0], newUV);
    vec3 result = src.rgb;

    // Hue shift per fold
    float hueShift = foldIdx * (360.0 / float(nFolds));
    float angle2 = hueShift * 3.14159 / 180.0;
    float s = sin(angle2), c = cos(angle2);
    float vs = sqrt(1.0/3.0);
    mat3 m = mat3(
        c+(1.0-c)/3.0, (1.0-c)/3.0-vs*s, (1.0-c)/3.0+vs*s,
        (1.0-c)/3.0+vs*s, c+(1.0-c)/3.0, (1.0-c)/3.0-vs*s,
        (1.0-c)/3.0-vs*s, (1.0-c)/3.0+vs*s, c+(1.0-c)/3.0
    );
    result = m * result;

    // Extra saturation
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.6);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M11: Plasma Web (plasma_tentacles mutation) --
    {
        "name": "fx_mut_plasma_web",
        "label": "Plasma Web",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Bright white body
    vec3 body = vec3(luma * 1.2) * bodyMask;

    // Deep neon purple background
    vec3 bg = vec3(0.08, 0.0, 0.15);

    // Web: tentacles that connect to each other
    vec3 web = vec3(0.0);
    vec2 points[12];
    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, 42.0));
        points[i] = vec2(
            0.5 + 0.35 * cos(seed * 6.28 + iTime * 0.15 + fi * 0.5),
            0.5 + 0.35 * sin(seed * 6.28 + iTime * 0.12 + fi * 0.3)
        );
    }

    // Draw connections between nearby points
    for (int i = 0; i < 12; i++) {
        for (int j = i + 1; j < 12; j++) {
            vec2 a = points[i];
            vec2 b = points[j];
            float segLen = length(b - a);
            if (segLen > 0.5) continue;  // skip distant pairs

            // Distance from uv to line segment a-b
            vec2 ab = b - a;
            float t = clamp(dot(uv - a, ab) / dot(ab, ab), 0.0, 1.0);
            vec2 closest = a + t * ab;
            float d = length(uv - closest);

            float thickness = (1.5 + bass * 2.0) / uTD2DInfos[0].res.w;
            float line = exp(-d / thickness);

            float fi = float(i);
            vec3 neonColor = 0.5 + 0.5 * cos(6.28 * (fi / 12.0 + vec3(0, 0.33, 0.67)));
            web += neonColor * line * 0.3;
        }
    }

    // Also draw nodes
    for (int i = 0; i < 12; i++) {
        float d = length(uv - points[i]);
        float nodeGlow = exp(-d * uTD2DInfos[0].res.w * 0.15);
        web += vec3(1.0, 0.5, 1.0) * nodeGlow * 0.4;
    }

    vec3 result = mix(bg, body, bodyMask) + web;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M12: Strobe Posterize (strobe_invert + solarize_pulse) --
    {
        "name": "fx_mut_strobe_posterize",
        "label": "Strobe Posterize",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    // Beat inversion
    float flash = step(0.6, beat) * step(0.5, fract(iTime * 8.0));
    vec3 result = mix(src.rgb, 1.0 - src.rgb, flash);

    // Oscillating solarization
    float phase = iTime * 3.0;
    float tR = (128.0 + sin(phase) * 80.0) / 255.0;
    float tG = (128.0 + sin(phase + 2.09) * 80.0) / 255.0;
    float tB = (128.0 + sin(phase + 4.19) * 80.0) / 255.0;

    result.r = result.r > tR ? 1.0 - result.r : result.r;
    result.g = result.g > tG ? 1.0 - result.g : result.g;
    result.b = result.b > tB ? 1.0 - result.b : result.b;

    // 2x saturation
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 2.0);

    // Extreme contrast
    float contrast = 2.0 + energy * 1.0;
    result = (result - 0.5) * contrast + 0.5;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M13: Cascade Mirror (pixelate_cascade mutation) --
    {
        "name": "fx_mut_cascade_mirror",
        "label": "Cascade Mirror",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;

    // Horizontal cascade (left-right), driven by highs
    float cascadePos = 0.5 + 0.5 * sin(iTime * (1.5 + highs * 3.0));
    float maxPixSize = 8.0 + highs * 40.0;

    // Variable pixelation by horizontal position
    float distFromCascade = abs(uv.x - cascadePos);
    float pixSize = mix(maxPixSize, 1.0, smoothstep(0.0, 0.4, distFromCascade));
    pixSize = max(1.0, floor(pixSize));

    vec2 pixUV = floor(uv * res / pixSize) * pixSize / res + (pixSize * 0.5) / res;

    // Left-right mirror
    vec2 mirrorUV = pixUV;
    if (uv.x > 0.5) mirrorUV.x = 1.0 - mirrorUV.x;

    vec4 pixSrc = texture(sTD2DInputs[0], mirrorUV);
    vec4 src = texture(sTD2DInputs[0], uv);

    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    vec3 result = mix(src.rgb * 0.3, pixSrc.rgb, bodyMask);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M14: Glitch Feedback (glitch_tear + feedback_spiral) --
    {
        "name": "fx_mut_glitch_feedback",
        "label": "Glitch Feedback",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 center = vec2(0.5);
    float kick = min(1.0, sub + bass * 0.5);

    // 2x horizontal tears
    float bandY = floor(uv.y * res.y / 6.0);
    float tearHash = hash(vec2(bandY, floor(iTime * 6.0)));

    vec2 displaced = uv;
    if (tearHash > (1.0 - kick * 0.4)) {
        float shift = (hash(vec2(bandY * 3.0, floor(iTime * 6.0))) - 0.5);
        shift *= (20.0 + bass * 200.0) / res.x;  // 2x tear
        displaced.x += shift;
    }

    // Feedback spiral: scale + 2x rotate
    float scale = 0.95 + bass * 0.04;
    float rotDeg = 4.0 + mids * 10.0;  // 2x rotation
    float rot = rotDeg * 3.14159 / 180.0;

    vec2 p = displaced - center;
    float c2 = cos(rot), s2 = sin(rot);
    vec2 rotated = vec2(p.x * c2 - p.y * s2, p.x * s2 + p.y * c2) * scale;
    vec2 feedbackUV = clamp(rotated + center, 0.0, 1.0);

    vec4 feedback = texture(sTD2DInputs[0], feedbackUV);
    vec4 src = texture(sTD2DInputs[0], displaced);

    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    vec3 result = mix(feedback.rgb * 0.95, src.rgb, bodyMask);

    // Color inversion on some bands
    if (tearHash > 0.9) {
        result = 1.0 - result;
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M15: Radial Neon (radial_zoom + neon_skeleton) --
    {
        "name": "fx_mut_radial_neon",
        "label": "Radial Neon",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 center = vec2(0.5);

    vec3 result = vec3(0.0);
    float totalW = 0.0;

    // 6 radial zoom copies, each with Sobel edge detection
    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float scale = 1.0 - fi * 0.08;
        float rot = fi * 0.15 + iTime * 0.1;

        vec2 p = uv - center;
        float cr = cos(rot), sr = sin(rot);
        vec2 rp = vec2(p.x * cr - p.y * sr, p.x * sr + p.y * cr) * scale;
        vec2 sampleUV = clamp(rp + center, 0.0, 1.0);

        // Sobel edge detection
        float sobelX = 0.0, sobelY = 0.0;
        for (int x = -1; x <= 1; x++) {
            for (int y = -1; y <= 1; y++) {
                float s = dot(texture(sTD2DInputs[0], sampleUV + vec2(float(x), float(y)) * texel * 2.0).rgb,
                             vec3(0.299, 0.587, 0.114));
                float kx = float(x) * (y == 0 ? 2.0 : 1.0);
                float ky = float(y) * (x == 0 ? 2.0 : 1.0);
                sobelX += s * kx;
                sobelY += s * ky;
            }
        }
        float edge = sqrt(sobelX * sobelX + sobelY * sobelY);

        // Different neon color per layer
        vec3 neonColor = 0.5 + 0.5 * cos(6.28 * (fi / 6.0 + vec3(0, 0.33, 0.67)));
        float w = 1.0 / (1.0 + fi * 0.3);
        result += neonColor * edge * (2.0 + bass * 3.0) * w;
        totalW += w;
    }
    result /= max(totalW, 0.01);

    // Bloom
    result *= 1.5;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M16: Skeleton Fire (neon_skeleton + fire_scanlines) --
    {
        "name": "fx_mut_skeleton_fire",
        "label": "Skeleton Fire",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // Sobel edge detection
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
    float edgeMask = smoothstep(0.1, 0.3, edge);

    // Fire palette for edge glow
    vec3 fireColor = vec3(
        clamp(edge * 3.0, 0.0, 1.0),
        clamp(edge * 1.8 - 0.2, 0.0, 1.0),
        clamp(edge * 0.6 - 0.3, 0.0, 1.0)
    ) * (1.0 + bass * 2.0);

    // Scanlines on body
    float bodyMask = smoothstep(0.08, 0.2, luma);
    float scanSpacing = 4.0 + bass * 8.0;
    float scanline = sin(uv.y * uTD2DInfos[0].res.w / scanSpacing + iTime * 2.0);
    scanline = smoothstep(0.7, 1.0, scanline);
    vec3 bodyColor = src.rgb * 0.08 * bodyMask;
    bodyColor += vec3(0.15, 0.05, 0.0) * scanline * bodyMask;

    // Dark background
    vec3 bg = vec3(0.01, 0.0, 0.0);
    vec3 result = bg + bodyColor + fireColor * edgeMask;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M17: Negative Solarize (solarize_pulse mutation) --
    {
        "name": "fx_mut_negative_solarize",
        "label": "Negative Solarize",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    // Invert base image before solarization
    vec3 inverted = 1.0 - src.rgb;

    float phase = iTime * 2.0;

    // Sub_bass-driven solarization
    float drive = sub * 1.5;
    float tR = (128.0 + sin(phase) * 60.0 + drive * 50.0 * sin(phase * 0.9)) / 255.0;
    float tG = (128.0 + sin(phase + 2.09) * 60.0 + drive * 40.0 * cos(phase * 1.3)) / 255.0;
    float tB = (128.0 + sin(phase + 4.19) * 60.0 + drive * 35.0 * sin(phase * 1.5)) / 255.0;

    vec3 result;
    result.r = inverted.r > tR ? 1.0 - inverted.r : inverted.r;
    result.g = inverted.g > tG ? 1.0 - inverted.g : inverted.g;
    result.b = inverted.b > tB ? 1.0 - inverted.b : inverted.b;

    // Green/cyan shift
    result.g *= 1.3;
    result.b *= 1.15;
    result.r *= 0.7;

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    float satBoost = 1.4 + energy * 0.6;
    result = mix(vec3(gray), result, satBoost);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M18: Voronoi Feedback (triangle_shatter + feedback_spiral) --
    {
        "name": "fx_mut_voronoi_feedback",
        "label": "Voronoi Feedback",
        "shader": GLSL_HEADER + """
vec2 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float minDist = 1.0;
    vec2 minPoint = vec2(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash(i + neighbor) * vec2(1.0);
            // Bass-pulsing grid
            point += sin(iTime * 2.0 + hash(i + neighbor) * 6.28) * bass * 0.2;
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
    vec2 center = vec2(0.5);
    float gridSize = 10.0 + bass * 8.0;
    vec2 v = voronoi(uv * gridSize);

    float edge = smoothstep(0.02, 0.04, v.x);

    // Feedback-spiral transform per cell
    float cellSeed = v.y;
    float scale = 0.97 + cellSeed * 0.04;
    float rot = (cellSeed - 0.5) * 0.1 + mids * 0.05;
    vec2 p = uv - center;
    float c2 = cos(rot), s2 = sin(rot);
    vec2 rotated = vec2(p.x * c2 - p.y * s2, p.x * s2 + p.y * c2) * scale;
    vec2 feedbackUV = clamp(rotated + center, 0.0, 1.0);

    vec4 feedSrc = texture(sTD2DInputs[0], feedbackUV);
    vec2 cellUV = floor(uv * gridSize + 0.5) / gridSize;
    vec4 cellColor = texture(sTD2DInputs[0], cellUV);

    // Mix feedback and cell color
    vec3 result = mix(feedSrc.rgb * 0.9, cellColor.rgb, edge * 0.7);

    // Hue shift per cell
    float hueAngle = cellSeed * 3.14;
    float hs = sin(hueAngle), hc = cos(hueAngle);
    float vs2 = sqrt(1.0/3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs2*hs, (1.0-hc)/3.0+vs2*hs,
                  (1.0-hc)/3.0+vs2*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs2*hs,
                  (1.0-hc)/3.0-vs2*hs, (1.0-hc)/3.0+vs2*hs, hc+(1.0-hc)/3.0);
    result = m * result;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # -- M19: Double Spiral (feedback_spiral mutation) --
    {
        "name": "fx_mut_double_spiral",
        "label": "Double Spiral",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    // Spiral A: clockwise, 5x rotation speed
    float scaleA = 0.96 + bass * 0.03;
    float rotA = (10.0 + mids * 25.0) * 3.14159 / 180.0;  // 5x
    vec2 pA = uv - center;
    float cA = cos(rotA), sA = sin(rotA);
    vec2 spiralA_uv = vec2(pA.x * cA - pA.y * sA, pA.x * sA + pA.y * cA) * scaleA + center;
    spiralA_uv = clamp(spiralA_uv, 0.0, 1.0);

    // Spiral B: counter-clockwise
    float rotB = -(10.0 + mids * 25.0) * 3.14159 / 180.0;
    vec2 pB = uv - center;
    float cB = cos(rotB), sB = sin(rotB);
    vec2 spiralB_uv = vec2(pB.x * cB - pB.y * sB, pB.x * sB + pB.y * cB) * scaleA + center;
    spiralB_uv = clamp(spiralB_uv, 0.0, 1.0);

    vec4 srcA = texture(sTD2DInputs[0], spiralA_uv);
    vec4 srcB = texture(sTD2DInputs[0], spiralB_uv);
    vec4 src = texture(sTD2DInputs[0], uv);

    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Additive blend of both spirals
    vec3 spirals = srcA.rgb * 0.5 + srcB.rgb * 0.5;

    // Hue shift
    float hueAngle = energy * 5.0 * 3.14159 / 180.0;
    float hs = sin(hueAngle), hc = cos(hueAngle);
    float vs = sqrt(1.0/3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                  (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                  (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
    spirals = m * spirals * 0.97;

    vec3 result = mix(spirals, src.rgb, bodyMask);

    // Bloom
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec3 bloom = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * 12.0 * texel;
        bloom += texture(sTD2DInputs[0], uv + off).rgb;
    }
    bloom /= 8.0;
    result = mix(result, bloom, 0.2 + energy * 0.1);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M20: Kanji Matrix (matrix_rain mutation) --
    {
        "name": "fx_mut_kanji_matrix",
        "label": "Kanji Matrix",
        "shader": GLSL_HEADER + """
float charPattern(vec2 uv, float seed) {
    vec2 grid = floor(uv * vec2(5.0, 6.0));
    float h = hash(grid + seed);
    // Denser pattern for kanji-like look
    return step(0.35, h);
}

void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Red/gold body tint
    vec3 goldBody = vec3(luma * 0.8, luma * 0.5, luma * 0.1) * bodyMask;

    // 3x fall speed
    float charSize = 12.0;
    vec2 cellUV = uv * res / charSize;
    vec2 cell = floor(cellUV);
    vec2 cellFract = fract(cellUV);

    float speed = 6.0 + energy * 18.0;  // 3x speed
    float columnSeed = hash(vec2(cell.x, 0.0));
    float fallOffset = iTime * speed * (0.5 + columnSeed);
    float charIdx = cell.y - fallOffset;
    float charCell = floor(charIdx);

    float charSeed = hash(vec2(cell.x, charCell));
    // Beat-triggered character mutation
    charSeed += floor(iTime * 6.0 + beat * 3.0) * 0.02;

    float ch = charPattern(cellFract, charSeed);

    float age = fract(-charIdx * 0.04);
    float brightness = age > 0.95 ? 1.0 : age * 0.7;

    float density = 25.0 + highs * 70.0;
    float columnActive = step(0.4, hash(vec2(cell.x, floor(iTime * 0.5)))) * (density / 80.0);

    vec3 rain = vec3(0.0);
    if (columnActive > 0.3) {
        if (age > 0.95) rain = vec3(1.0, 0.9, 0.5) * ch;  // gold leading
        else rain = vec3(brightness * 0.8, brightness * 0.2, 0.0) * ch;  // red trail
    }

    // Dark red bg
    vec3 bg = vec3(0.04, 0.0, 0.0);
    vec3 result = bg + goldBody + rain * 0.8;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # -- M21: Chromatic Prism (chromatic_double mutation) --
    {
        "name": "fx_mut_chromatic_prism",
        "label": "Chromatic Prism",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float kick = min(1.0, sub + bass * 0.5);

    // 4x offset, pentagonal arrangement (5 channels: RGBCM)
    float baseOff = (20.0 + kick * 120.0) * texel.x;

    // 5 directions at 72-degree intervals
    vec2 dirs[5];
    for (int i = 0; i < 5; i++) {
        float a = float(i) * 1.2566 + iTime * 0.3;  // 72 deg = 2pi/5
        dirs[i] = vec2(cos(a), sin(a));
    }

    // Sample 5 channels
    vec4 sR = texture(sTD2DInputs[0], uv + dirs[0] * baseOff);
    vec4 sG = texture(sTD2DInputs[0], uv + dirs[1] * baseOff);
    vec4 sB = texture(sTD2DInputs[0], uv + dirs[2] * baseOff);
    vec4 sC = texture(sTD2DInputs[0], uv + dirs[3] * baseOff);
    vec4 sM = texture(sTD2DInputs[0], uv + dirs[4] * baseOff);

    float lumaR = dot(sR.rgb, vec3(0.299, 0.587, 0.114));
    float lumaG = dot(sG.rgb, vec3(0.299, 0.587, 0.114));
    float lumaB = dot(sB.rgb, vec3(0.299, 0.587, 0.114));
    float lumaC = dot(sC.rgb, vec3(0.299, 0.587, 0.114));
    float lumaM = dot(sM.rgb, vec3(0.299, 0.587, 0.114));

    float maskR = smoothstep(0.1, 0.2, lumaR);
    float maskG = smoothstep(0.1, 0.2, lumaG);
    float maskB = smoothstep(0.1, 0.2, lumaB);
    float maskC = smoothstep(0.1, 0.2, lumaC);
    float maskM = smoothstep(0.1, 0.2, lumaM);

    // RGBCM additive blend
    vec3 result = vec3(0.0);
    result += vec3(1.0, 0.0, 0.0) * sR.r * maskR;
    result += vec3(0.0, 1.0, 0.0) * sG.g * maskG;
    result += vec3(0.0, 0.0, 1.0) * sB.b * maskB;
    result += vec3(0.0, 1.0, 1.0) * dot(sC.rgb, vec3(0.333)) * maskC * 0.5;
    result += vec3(1.0, 0.0, 1.0) * dot(sM.rgb, vec3(0.333)) * maskM * 0.5;

    // Bloom
    if (energy > 0.2) {
        vec3 bloom = vec3(0.0);
        for (int i = 0; i < 8; i++) {
            float angle = float(i) * 0.785;
            vec2 off = vec2(cos(angle), sin(angle)) * 12.0 * texel;
            vec4 s = texture(sTD2DInputs[0], uv + off);
            bloom += s.rgb * smoothstep(0.1, 0.2, dot(s.rgb, vec3(0.299, 0.587, 0.114)));
        }
        bloom /= 8.0;
        result += bloom * (0.25 + energy * 0.2);
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },
]


# --- BUILDER -------------------------------------------------------------------

def build_effect(idx, effect, dry_run=False):
    """Build one mutation effect in TouchDesigner."""
    name = effect["name"]
    label = effect["label"]
    shader = effect["shader"]
    parent = "/project1"
    comp_path = f"{parent}/{name}"

    print(f"\n[{idx+1:2d}/21] Building {label} ({name})...")

    if dry_run:
        print(f"  DRY RUN: would create {comp_path}")
        return True

    # 1. Destroy existing if present
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

    # Position: row below existing effects
    node_x = -400 + (idx % 7) * 170
    node_y = -900 - (idx // 7) * 200
    td_exec(f"op('{comp_path}').nodeX = {node_x}; op('{comp_path}').nodeY = {node_y}")

    # 2. Create in1 (inTOP) inside the COMP
    td_create_op(comp_path, "inTOP", "in1")
    td_exec(f"op('{comp_path}/in1').nodeX = -300; op('{comp_path}/in1').nodeY = 0")

    # 3. Create GLSL TOP
    glsl_name = f"glsl_{name.replace('fx_mut_', '')}"
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

    # 6. Wire: in1 -> glsl -> out1
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

    # 8. Set audio uniform vectors
    td_exec(f"""
glsl = op('{comp_path}/{glsl_name}')
glsl.par.vec = 1
glsl.par.vec0name = 'uAudio'
glsl.par.vec0valuex.mode = ParMode.EXPRESSION
glsl.par.vec0valuex.expr = "absTime.seconds"
glsl.par.vec0valuey.mode = ParMode.EXPRESSION
glsl.par.vec0valuey.expr = "op('/project1/audio_analysis/out1')['rms']"
glsl.par.vec0valuez.mode = ParMode.EXPRESSION
glsl.par.vec0valuez.expr = "op('/project1/audio_analysis/out1')['bass']"
glsl.par.vec0valuew.mode = ParMode.EXPRESSION
glsl.par.vec0valuew.expr = "op('/project1/audio_analysis/out1')['sub_bass']"

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

    print(f"  OK {comp_path}")
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build 21 mutation effects in TouchDesigner")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--effect", type=int, default=-1, help="Build only mutation N (0-indexed)")
    args = parser.parse_args()

    print("=" * 60)
    print("YOUSUKE Mutation Effect Builder")
    print(f"Building {len(MUTATIONS)} mutation effects via twozero MCP")
    print("=" * 60)

    # Verify MCP connection
    if not args.dry_run:
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
        if args.effect < len(MUTATIONS):
            if build_effect(args.effect, MUTATIONS[args.effect], args.dry_run):
                built += 1
        else:
            print(f"Effect index {args.effect} out of range (0-{len(MUTATIONS)-1})")
    else:
        for idx, effect in enumerate(MUTATIONS):
            try:
                if build_effect(idx, effect, args.dry_run):
                    built += 1
            except Exception as e:
                print(f"  FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Built {built}/{len(MUTATIONS)} mutation effects")
    print("=" * 60)


if __name__ == "__main__":
    main()
