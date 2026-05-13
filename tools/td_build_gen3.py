#!/usr/bin/env python3
"""
Build 57 Gen 3 GLSL effects in TouchDesigner via twozero MCP bridge.

Gen 3 effects are crossbreeds, palette swaps, and intensity mutations
of the original 21 + 21 mutation effects.

Each effect becomes a baseCOMP with:
  in1 (inTOP) -> glslTOP (pixel shader) -> out1 (outTOP)

GLSL receives uAudio  = (time, rms, bass, sub_bass)
              uAudio2 = (sub_bass, mids, highs, beat)

Usage:
  python3 tools/td_build_gen3.py           # Build all effects
  python3 tools/td_build_gen3.py --dry-run # Print what would be done
  python3 tools/td_build_gen3.py --effect 0 # Build only effect #0
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

# Common GLSL header for all Gen 3 effects
GLSL_HEADER = """// YOUSUKE Gen 3 Effect
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

# ─── CROSSBREED EFFECTS (0-19) ───────────────────────────────────────────────

EFFECTS = [
    # ── 0: Kaleidoscope + Datamosh ──
    {
        "name": "fx_g3_kaleido_mosh",
        "label": "Kaleido Mosh",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 p = uv - center;

    // 6-fold kaleidoscope
    float r = length(p);
    float theta = atan(p.y, p.x) + iTime * energy * 0.3;
    float sliceAngle = 6.28318 / 6.0;
    float thetaMod = mod(theta, sliceAngle);
    float foldIdx = floor(theta / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;
    vec2 kUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
    kUV = clamp(kUV, 0.0, 1.0);

    // Noise-driven UV displacement (datamosh smear)
    float moshAmp = (3.0 + bass * 12.0) / uTD2DInfos[0].res.zw.x;
    vec2 motionDir = vec2(
        noise(kUV * 6.0 + iTime * 1.5) - 0.5,
        noise(kUV * 6.0 + iTime * 1.5 + 50.0) - 0.5
    ) * moshAmp;

    vec3 smeared = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float fi = float(i) / 8.0;
        smeared += texture(sTD2DInputs[0], kUV + motionDir * fi).rgb;
    }
    smeared /= 8.0;

    vec4 src = texture(sTD2DInputs[0], kUV);
    float freeze = max(0.0, highs - 0.2) * 2.0;
    vec3 result = mix(src.rgb, smeared, freeze * 0.6);

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.4);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 1: Plasma Skeleton ──
    {
        "name": "fx_g3_plasma_skeleton",
        "label": "Plasma Skeleton",
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
    float edgeMask = smoothstep(0.08, 0.25, edge);

    // Edge angle for color mapping
    float edgeAngle = atan(sobelY, sobelX);

    // Multi-color neon based on edge angle + plasma oscillation
    float plasma = sin(edgeAngle * 3.0 + iTime * 2.0) * 0.5 + 0.5;
    vec3 neonColor = 0.5 + 0.5 * cos(6.28 * (plasma + vec3(0.0, 0.33, 0.67)));

    // Glow spread
    float glowR = (4.0 + energy * 10.0) * texel.x;
    float glow = 0.0;
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * glowR;
        vec3 samp = texture(sTD2DInputs[0], uv + off).rgb;
        vec3 samp2 = texture(sTD2DInputs[0], uv + off + texel).rgb;
        glow += length(samp - samp2);
    }
    glow /= 8.0;

    // Faint ghost body
    vec3 ghost = src.rgb * 0.1 * smoothstep(0.08, 0.2, luma);
    vec3 result = ghost + neonColor * edgeMask * (1.5 + bass * 2.0);
    result += neonColor * glow * 0.6;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 2: Fire Kaleidoscope ──
    {
        "name": "fx_g3_fire_kaleido",
        "label": "Fire Kaleidoscope",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 p = uv - center;

    // 8-fold kaleidoscope
    float r = length(p);
    float theta = atan(p.y, p.x) + iTime * 0.4;
    float sliceAngle = 6.28318 / 8.0;
    float thetaMod = mod(theta, sliceAngle);
    float foldIdx = floor(theta / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;
    vec2 kUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
    kUV = clamp(kUV, 0.0, 1.0);

    vec4 src = texture(sTD2DInputs[0], kUV);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // FBM fire noise
    float fireSpeed = 2.5 + energy * 6.0;
    vec2 fireUV = kUV * 5.0 + vec2(0.0, -iTime * fireSpeed * 0.25);
    float fireNoise = fbm(fireUV);

    vec3 fire = vec3(
        clamp(fireNoise * 2.2, 0.0, 1.0),
        clamp(fireNoise * 1.3 - 0.15, 0.0, 1.0),
        clamp(fireNoise * 0.5 - 0.35, 0.0, 1.0)
    );

    // Composite fire onto image through kaleidoscope
    float fireMix = 0.5 + bass * 0.3;
    vec3 result = mix(src.rgb, fire, fireMix * smoothstep(0.05, 0.3, luma));

    // Beat flash brightening
    result += vec3(0.15) * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 3: Echo Plasma ──
    {
        "name": "fx_g3_echo_plasma",
        "label": "Echo Plasma",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    // 4 echo copies at offset positions
    vec3 echoes = src.rgb;
    float totalW = 1.0;
    for (int i = 1; i <= 4; i++) {
        float fi = float(i);
        vec2 offset = vec2(
            sin(iTime * 0.5 + fi * 1.7) * 0.03 * fi,
            cos(iTime * 0.4 + fi * 2.3) * 0.02 * fi
        );
        vec4 echoSrc = texture(sTD2DInputs[0], uv + offset);
        float w = 1.0 / (1.0 + fi * 0.4);
        // Hue shift per echo
        float hAngle = fi * 0.5 + iTime * 0.3;
        float hs = sin(hAngle), hc = cos(hAngle);
        float vs = sqrt(1.0 / 3.0);
        mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                      (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                      (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
        echoes += m * echoSrc.rgb * w;
        totalW += w;
    }
    echoes /= totalW;

    // 8 neon line segments connecting random points
    vec3 neons = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        vec2 a = vec2(hash(vec2(fi, 1.0 + floor(iTime * 0.5))),
                      hash(vec2(fi, 2.0 + floor(iTime * 0.5))));
        vec2 b = vec2(hash(vec2(fi, 3.0 + floor(iTime * 0.5))),
                      hash(vec2(fi, 4.0 + floor(iTime * 0.5))));
        vec2 ab = b - a;
        float t = clamp(dot(uv - a, ab) / dot(ab, ab), 0.0, 1.0);
        vec2 closest = a + t * ab;
        float d = length(uv - closest);
        float lineW = (1.5 + bass * 2.0) / uTD2DInfos[0].res.zw.x;
        float line = exp(-d / lineW);
        vec3 lc = 0.5 + 0.5 * cos(6.28 * (fi / 8.0 + vec3(0, 0.33, 0.67)));
        neons += lc * line * 0.35;
    }

    vec3 result = echoes + neons;
    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 4: Matrix RGB ──
    {
        "name": "fx_g3_matrix_rgb",
        "label": "Matrix RGB",
        "shader": GLSL_HEADER + """
float charPattern(vec2 uv, float seed) {
    vec2 grid = floor(uv * vec2(4.0, 5.0));
    return step(0.5, hash(grid + seed));
}

void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 texel = 1.0 / res;

    // RGB chromatic aberration on camera
    float kick = min(1.0, sub + bass * 0.5);
    float rOff = (4.0 + kick * 25.0) * texel.x;
    float bOff = -(3.0 + kick * 18.0) * texel.x;
    float R = texture(sTD2DInputs[0], uv + vec2(rOff, 0.0)).r;
    float G = texture(sTD2DInputs[0], uv).g;
    float B = texture(sTD2DInputs[0], uv + vec2(bOff, 0.0)).b;
    vec3 cam = vec3(R, G, B) * 0.4;

    // Matrix rain overlay
    float charSize = 10.0;
    vec2 cellUV = uv * res / charSize;
    vec2 cell = floor(cellUV);
    vec2 cellFract = fract(cellUV);

    float speed = 3.0 + energy * 6.0;
    float columnSeed = hash(vec2(cell.x, 0.0));
    float fallOffset = iTime * speed * (0.5 + columnSeed);
    float charIdx = cell.y - fallOffset;
    float charCell = floor(charIdx);

    float charSeed = hash(vec2(cell.x, charCell)) + floor(iTime * 2.0) * 0.01;
    float ch = charPattern(cellFract, charSeed);

    float age = fract(-charIdx * 0.04);
    float brightness = age > 0.95 ? 1.0 : age * 0.5;
    float density = 25.0 + highs * 50.0;
    float columnActive = step(0.5, hash(vec2(cell.x, floor(iTime * 0.5)))) * (density / 75.0);

    vec3 rain = vec3(0.0);
    if (columnActive > 0.3) {
        if (age > 0.95) rain = vec3(0.8, 1.0, 0.8) * ch;
        else rain = vec3(0.0, brightness, 0.0) * ch;
    }

    vec3 result = cam + rain * 0.7;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 5: Confetti Spiral ──
    {
        "name": "fx_g3_confetti_spiral",
        "label": "Confetti Spiral",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    // Spiral zoom transform on camera
    vec2 p = uv - center;
    float scale = 0.97;
    float rotAngle = 0.05 + mids * 0.03;
    float cs = cos(rotAngle), sn = sin(rotAngle);
    vec2 spiralUV = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs) * scale + center;
    spiralUV = clamp(spiralUV, 0.0, 1.0);

    vec4 src = texture(sTD2DInputs[0], spiralUV);
    vec3 result = src.rgb;

    // 40 confetti particles
    for (int i = 0; i < 40; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 0.7));
        float t = iTime * (0.4 + seed * 0.6) + fi;
        vec2 pos = vec2(
            fract(seed + sin(t * 0.25) * 0.4),
            fract(fi * 0.0251 - t * 0.12 * (0.4 + bass * 0.6))
        );

        // Apply same spiral transform to particle positions
        vec2 pp = pos - center;
        pp = vec2(pp.x * cs - pp.y * sn, pp.x * sn + pp.y * cs) * scale;
        pos = pp + center;

        float d = length((uv - pos) * vec2(1.0, 1.78));
        float size = 0.004 + bass * 0.006;
        if (d < size) {
            vec3 cc = 0.5 + 0.5 * cos(6.28 * (seed * 4.0 + vec3(0.0, 0.33, 0.67)));
            result = mix(result, cc, 0.9);
        }
    }

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 6: Glitch Solar ──
    {
        "name": "fx_g3_glitch_solar",
        "label": "Glitch Solar",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    float kick = min(1.0, sub + bass * 0.5);

    // Horizontal band displacement
    vec2 displaced = uv;
    float bandY = floor(uv.y * res.y / 6.0);
    float tearHash = hash(vec2(bandY, floor(iTime * 5.0)));
    if (tearHash > (1.0 - kick * 0.35)) {
        float shift = (hash(vec2(bandY * 3.0, floor(iTime * 5.0))) - 0.5);
        shift *= (8.0 + bass * 80.0) / res.x;
        displaced.x += shift;
    }

    vec4 src = texture(sTD2DInputs[0], displaced);

    // Per-channel solarization with oscillating thresholds
    float phase = iTime * 2.5;
    float tR = (128.0 + sin(phase) * 55.0 + energy * 30.0) / 255.0;
    float tG = (128.0 + sin(phase + 2.09) * 55.0 + mids * 25.0) / 255.0;
    float tB = (128.0 + sin(phase + 4.19) * 55.0 + bass * 35.0) / 255.0;

    vec3 result;
    result.r = src.r > tR ? 1.0 - src.r : src.r;
    result.g = src.g > tG ? 1.0 - src.g : src.g;
    result.b = src.b > tB ? 1.0 - src.b : src.b;

    // Color inversion on some torn bands
    if (tearHash > 0.93) {
        result = 1.0 - result;
    }

    // Scanline overlay on kicks
    if (kick > 0.5) {
        float scanline = step(0.5, fract(uv.y * res.y * 0.5));
        result -= vec3(0.1) * scanline;
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 7: Radial Shatter ──
    {
        "name": "fx_g3_radial_shatter",
        "label": "Radial Shatter",
        "shader": GLSL_HEADER + """
vec2 voronoi(vec2 p, float kick) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float minDist = 1.0;
    vec2 minPoint = vec2(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = vec2(hash(i + neighbor));
            if (kick > 0.4) {
                point += (hash(i + neighbor + floor(iTime)) - 0.5) * kick * 0.4;
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
    vec2 center = vec2(0.5);
    float kick = min(1.0, sub + bass * 0.5);

    float gridSize = 10.0 + bass * 6.0;
    vec2 v = voronoi(uv * gridSize, kick);
    float edge = smoothstep(0.02, 0.05, v.x);

    // Each cell samples from radially-zoomed position
    float cellSeed = v.y;
    float zoomFactor = 0.85 + cellSeed * 0.3;
    vec2 toC = uv - center;
    vec2 radialUV = center + toC * zoomFactor;
    radialUV = clamp(radialUV, 0.0, 1.0);

    vec4 cellColor = texture(sTD2DInputs[0], radialUV);
    vec3 result = cellColor.rgb * edge;

    // White edge lines
    result += vec3(0.8) * (1.0 - edge) * 0.5;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 8: Liquid Matrix ──
    {
        "name": "fx_g3_liquid_matrix",
        "label": "Liquid Matrix",
        "shader": GLSL_HEADER + """
float charPattern(vec2 uv, float seed) {
    vec2 grid = floor(uv * vec2(4.0, 5.0));
    return step(0.5, hash(grid + seed));
}

void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 texel = 1.0 / res;

    // Sinusoidal UV displacement on camera
    float amp = (4.0 + bass * 20.0) * texel.x;
    float freq = 18.0 + mids * 12.0;
    float phase = iTime * 2.5;
    vec2 displaced = uv;
    displaced.x += sin(uv.y * freq + phase) * amp;
    displaced.y += cos(uv.x * freq + phase * 0.8) * amp * 0.5;
    vec4 src = texture(sTD2DInputs[0], displaced);
    vec3 cam = src.rgb * 0.5;

    // Matrix rain overlay in green
    float charSize = 9.0;
    vec2 cellUV = uv * res / charSize;
    vec2 cell = floor(cellUV);
    vec2 cellFract = fract(cellUV);

    float speed = 2.5 + energy * 5.0;
    float columnSeed = hash(vec2(cell.x, 0.0));
    float fallOffset = iTime * speed * (0.5 + columnSeed);
    float charIdx = cell.y - fallOffset;
    float charCell = floor(charIdx);
    float charSeed = hash(vec2(cell.x, charCell)) + floor(iTime * 3.0) * 0.01;
    float ch = charPattern(cellFract, charSeed);

    float age = fract(-charIdx * 0.04);
    float brightness = age > 0.95 ? 1.0 : age * 0.55;
    float columnActive = step(0.45, hash(vec2(cell.x, floor(iTime * 0.4))));

    vec3 rain = vec3(0.0);
    if (columnActive > 0.3) {
        if (age > 0.95) rain = vec3(0.7, 1.0, 0.7) * ch;
        else rain = vec3(0.0, brightness, 0.0) * ch;
    }

    vec3 result = cam + rain * 0.65;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 9: Pixel Neon ──
    {
        "name": "fx_g3_pixel_neon",
        "label": "Pixel Neon",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 texel = 1.0 / res;

    // 16px block pixelation
    float blockSize = 16.0 + bass * 8.0;
    vec2 blockUV = floor(uv * res / blockSize) * blockSize / res + (blockSize * 0.5) / res;
    vec4 pixSrc = texture(sTD2DInputs[0], blockUV);

    // Sobel edge detection between blocks
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 sampleUV = blockUV + vec2(float(x), float(y)) * blockSize / res;
            float s = dot(texture(sTD2DInputs[0], sampleUV).rgb, vec3(0.299, 0.587, 0.114));
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            sobelX += s * kx;
            sobelY += s * ky;
        }
    }
    float edge = sqrt(sobelX * sobelX + sobelY * sobelY);
    float edgeMask = smoothstep(0.05, 0.2, edge);

    // Neon color based on block position
    float colorPhase = blockUV.y * 4.0 + blockUV.x * 3.0 + iTime * 0.8;
    vec3 neonColor = 0.5 + 0.5 * cos(6.28 * (colorPhase + vec3(0.0, 0.33, 0.67)));

    // Neon glow on edges
    vec3 result = pixSrc.rgb;
    result += neonColor * edgeMask * (1.5 + energy * 2.0);

    // Beat flash
    result += vec3(0.1) * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 10: Thermal Spiral ──
    {
        "name": "fx_g3_thermal_spiral",
        "label": "Thermal Spiral",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    // Feedback spiral zoom transform
    vec2 p = uv - center;
    float scale = 0.96 + bass * 0.03;
    float rotDeg = 3.0 + mids * 4.0;
    float rot = rotDeg * 3.14159 / 180.0;
    float cs = cos(rot), sn = sin(rot);
    vec2 spiralUV = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs) * scale + center;
    spiralUV = clamp(spiralUV, 0.0, 1.0);

    vec4 feedSrc = texture(sTD2DInputs[0], spiralUV);
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Mix spiral feedback with direct
    vec3 mixed = mix(feedSrc.rgb * 0.95, src.rgb, bodyMask);
    float mixLuma = dot(mixed, vec3(0.299, 0.587, 0.114));

    // Blue/orange/white thermal posterize palette
    float tLow = 0.30 + bass * 0.1;
    float tHigh = 0.65 - bass * 0.1;
    vec3 cBlue   = vec3(0.08, 0.31, 0.78);
    vec3 cOrange = vec3(1.0, 0.55, 0.16);
    vec3 cWhite  = vec3(1.0, 1.0, 1.0);

    vec3 result;
    if (mixLuma < tLow) result = cBlue;
    else if (mixLuma < tHigh) result = cOrange;
    else result = cWhite;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 11: Datamosh Confetti ──
    {
        "name": "fx_g3_datamosh_confetti",
        "label": "Datamosh Confetti",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // 8-sample motion smear with noise-based direction
    float moshAmp = (2.0 + bass * 8.0) * texel.x;
    vec2 motionDir = vec2(
        noise(uv * 5.0 + iTime * 1.2) - 0.5,
        noise(uv * 5.0 + iTime * 1.2 + 80.0) - 0.5
    ) * moshAmp;

    vec3 smeared = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float fi = float(i) / 8.0;
        smeared += texture(sTD2DInputs[0], uv + motionDir * fi).rgb;
    }
    smeared /= 8.0;

    vec4 src = texture(sTD2DInputs[0], uv);
    float freeze = max(0.0, highs - 0.2) * 2.5;
    vec3 result = mix(src.rgb, smeared, freeze * 0.5);

    // 25 confetti particles on top
    for (int i = 0; i < 25; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 0.63));
        float t = iTime * (0.5 + seed * 0.5) + fi;
        vec2 pos = vec2(
            fract(seed + sin(t * 0.3) * 0.35),
            fract(fi * 0.0401 - t * 0.14 * (0.5 + bass))
        );
        float d = length((uv - pos) * vec2(1.0, 1.78));
        float size = 0.005 + bass * 0.007;
        if (d < size) {
            vec3 cc = 0.5 + 0.5 * cos(6.28 * (seed * 3.5 + vec3(0.0, 0.33, 0.67)));
            result = mix(result, cc, 0.9);
        }
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 12: Chromatic Kaleidoscope ──
    {
        "name": "fx_g3_chromatic_kaleido",
        "label": "Chromatic Kaleido",
        "shader": GLSL_HEADER + """
vec2 kaleidoUV(vec2 uv, float baseAngle, float extraRot) {
    vec2 center = vec2(0.5);
    vec2 p = uv - center;
    float r = length(p);
    float theta = atan(p.y, p.x) + extraRot;
    float sliceAngle = 6.28318 / 6.0;
    float thetaMod = mod(theta + baseAngle, sliceAngle);
    float foldIdx = floor((theta + baseAngle) / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;
    vec2 kUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
    return clamp(kUV, 0.0, 1.0);
}

void main() {
    vec2 uv = vUV.st;
    float rot = iTime * energy * 0.4;

    // R/G/B through slightly different kaleido fold angles
    vec2 uvR = kaleidoUV(uv, 0.0, rot);
    vec2 uvG = kaleidoUV(uv, 0.1, rot);
    vec2 uvB = kaleidoUV(uv, 0.2, rot);

    float R = texture(sTD2DInputs[0], uvR).r;
    float G = texture(sTD2DInputs[0], uvG).g;
    float B = texture(sTD2DInputs[0], uvB).b;

    vec3 result = vec3(R, G, B);

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.5 + bass * 0.5);

    // Bloom
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec3 bloom = vec3(0.0);
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * 8.0 * texel;
        bloom += texture(sTD2DInputs[0], uv + off).rgb;
    }
    bloom /= 8.0;
    result = mix(result, bloom, 0.12 + energy * 0.08);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 13: Strobe Liquid ──
    {
        "name": "fx_g3_strobe_liquid",
        "label": "Strobe Liquid",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Sin/cos UV warping (liquid)
    float amp = (5.0 + bass * 22.0) * texel.x;
    float freq = 16.0 + mids * 10.0;
    float phase = iTime * 3.0;
    vec2 displaced = uv;
    displaced.x += sin(uv.y * freq + phase) * amp;
    displaced.y += cos(uv.x * freq * 0.8 + phase * 0.6) * amp * 0.7;

    vec4 src = texture(sTD2DInputs[0], displaced);
    vec3 result = src.rgb;

    // Beat-triggered inversion
    float strobe = step(0.7, beat);
    result = mix(result, 1.0 - result, strobe);

    // Contrast boost during strobe
    float contrast = 1.2 + strobe * 0.6 + energy * 0.3;
    result = (result - 0.5) * contrast + 0.5;

    // Afterimage persistence
    vec3 shifted = texture(sTD2DInputs[0], displaced + vec2(0.003, 0.001)).rgb;
    result = mix(result, shifted, 0.12);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 14: Echo Shatter ──
    {
        "name": "fx_g3_echo_shatter",
        "label": "Echo Shatter",
        "shader": GLSL_HEADER + """
vec2 voronoi(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float minDist = 1.0;
    vec2 minPoint = vec2(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = vec2(hash(i + neighbor));
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

    // Voronoi grid with 12 cells
    float gridSize = 12.0 + bass * 5.0;
    vec2 v = voronoi(uv * gridSize);
    float edge = smoothstep(0.02, 0.05, v.x);

    // Each cell shows a different echo-offset sample
    float cellSeed = v.y;
    vec2 echoOffset = vec2(
        (cellSeed - 0.5) * 0.06,
        (hash(vec2(cellSeed * 100.0, 7.0)) - 0.5) * 0.04
    );
    echoOffset *= (1.0 + bass * 2.0);

    vec4 cellSrc = texture(sTD2DInputs[0], uv + echoOffset);

    // Hue shift per cell
    float hAngle = cellSeed * 3.0;
    float hs = sin(hAngle), hc = cos(hAngle);
    float vs = sqrt(1.0 / 3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                  (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                  (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
    vec3 tinted = m * cellSrc.rgb;

    vec3 result = tinted * edge;
    // Bright edge lines
    result += vec3(0.6, 0.7, 0.9) * (1.0 - edge) * 0.4;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 15: Fire RGB ──
    {
        "name": "fx_g3_fire_rgb",
        "label": "Fire RGB",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Radial chromatic aberration
    float kick = min(1.0, sub + bass * 0.5);
    vec2 toC = uv - center;
    float dist = length(toC);
    vec2 dir = (dist > 0.001) ? toC / dist : vec2(0.0);
    float rOff = (3.0 + kick * 20.0) * texel.x * dist * 4.0;
    float bOff = -(2.0 + kick * 15.0) * texel.x * dist * 4.0;

    float R = texture(sTD2DInputs[0], uv + dir * rOff).r;
    float G = texture(sTD2DInputs[0], uv).g;
    float B = texture(sTD2DInputs[0], uv + dir * bOff).b;
    vec3 cam = vec3(R, G, B);

    // FBM fire noise composited over image
    float fireSpeed = 2.0 + energy * 7.0;
    vec2 fireUV = uv * 4.5 + vec2(0.0, -iTime * fireSpeed * 0.25);
    float fireNoise = fbm(fireUV);
    vec3 fire = vec3(
        clamp(fireNoise * 2.0, 0.0, 1.0),
        clamp(fireNoise * 1.2 - 0.2, 0.0, 1.0),
        clamp(fireNoise * 0.4 - 0.3, 0.0, 1.0)
    );

    float luma = dot(cam, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    float fireMix = 0.45 + bass * 0.25;
    vec3 result = mix(cam, cam + fire, fireMix * bodyMask);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 16: Pixel Radial ──
    {
        "name": "fx_g3_pixel_radial",
        "label": "Pixel Radial",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 center = vec2(0.5);

    // Pixelation size varies by distance from center
    float dist = length(uv - center) * 2.0; // 0..~1.4
    float minBlock = 2.0;
    float maxBlock = 32.0 + bass * 24.0;
    float blockSize = mix(minBlock, maxBlock, clamp(dist, 0.0, 1.0));
    blockSize = max(1.0, floor(blockSize));

    vec2 pixUV = floor(uv * res / blockSize) * blockSize / res + (blockSize * 0.5) / res;
    vec4 pixSrc = texture(sTD2DInputs[0], pixUV);

    vec3 result = pixSrc.rgb;

    // Subtle vignette darkening at edges
    float vignette = 1.0 - dist * 0.3;
    result *= vignette;

    // Color saturation boost near center (detail area)
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    float satBoost = mix(1.5, 1.0, clamp(dist, 0.0, 1.0));
    result = mix(vec3(gray), result, satBoost);

    // Beat flash
    result += vec3(0.08) * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 17: Rainbow Mosh ──
    {
        "name": "fx_g3_rainbow_mosh",
        "label": "Rainbow Mosh",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // 5 hue-shifted echo copies with motion noise displacement
    vec3 result = vec3(0.0);
    float totalW = 0.0;

    for (int i = 0; i < 5; i++) {
        float fi = float(i);

        // Motion noise displacement per copy
        float moshAmp = (1.5 + fi * 1.0 + bass * 5.0) * texel.x;
        vec2 motionDir = vec2(
            noise(uv * 4.0 + iTime + fi * 20.0) - 0.5,
            noise(uv * 4.0 + iTime + fi * 20.0 + 60.0) - 0.5
        ) * moshAmp;

        vec2 echoUV = uv + motionDir + vec2(fi * 0.012, fi * 0.006);
        echoUV = clamp(echoUV, 0.0, 1.0);
        vec3 samp = texture(sTD2DInputs[0], echoUV).rgb;

        // Hue shift per copy
        float hAngle = fi * 1.2 + iTime * 0.2;
        float hs = sin(hAngle), hc = cos(hAngle);
        float vs = sqrt(1.0 / 3.0);
        mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                      (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                      (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
        samp = m * samp;

        float w = 1.0 / (1.0 + fi * 0.35);
        result += samp * w;
        totalW += w;
    }
    result /= totalW;

    // Saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.6);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 18: Solar Skeleton ──
    {
        "name": "fx_g3_solar_skeleton",
        "label": "Solar Skeleton",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);

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
    float edgeMask = smoothstep(0.08, 0.25, edge);

    // Edge color from source
    vec3 edgeColor = src.rgb * edgeMask * 2.0;

    // Oscillating solarize palette on edge color (per-channel thresholds)
    float phase = iTime * 2.0;
    float tR = (128.0 + sin(phase) * 60.0 + energy * 30.0) / 255.0;
    float tG = (128.0 + sin(phase + 2.09) * 60.0 + mids * 25.0) / 255.0;
    float tB = (128.0 + sin(phase + 4.19) * 60.0 + bass * 35.0) / 255.0;

    vec3 solarEdge;
    solarEdge.r = edgeColor.r > tR ? 1.0 - edgeColor.r : edgeColor.r;
    solarEdge.g = edgeColor.g > tG ? 1.0 - edgeColor.g : edgeColor.g;
    solarEdge.b = edgeColor.b > tB ? 1.0 - edgeColor.b : edgeColor.b;

    // Faint body ghost behind edges
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    vec3 ghost = src.rgb * 0.08 * smoothstep(0.08, 0.2, luma);

    vec3 result = ghost + solarEdge * (1.5 + bass * 1.5);

    // Beat pulse brightness
    result += vec3(0.1) * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 19: Spiral Glitch ──
    {
        "name": "fx_g3_spiral_glitch",
        "label": "Spiral Glitch",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 res = uTD2DInfos[0].res.zw;

    // Feedback spiral zoom (scale 0.96, rotation ~3deg)
    vec2 p = uv - center;
    float scale = 0.96 + bass * 0.02;
    float rot = (3.0 + mids * 3.0) * 3.14159 / 180.0;
    float cs = cos(rot), sn = sin(rot);
    vec2 spiralUV = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs) * scale + center;
    spiralUV = clamp(spiralUV, 0.0, 1.0);

    vec4 feedSrc = texture(sTD2DInputs[0], spiralUV);
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Mix spiral feedback with direct camera
    vec3 result = mix(feedSrc.rgb * 0.95, src.rgb, bodyMask);

    // Horizontal band tears on beats
    float kick = min(1.0, sub + bass * 0.5);
    float bandY = floor(uv.y * res.y / 8.0);
    float tearHash = hash(vec2(bandY, floor(iTime * 4.0)));

    if (tearHash > (1.0 - kick * 0.3) && beat > 0.5) {
        float shift = (hash(vec2(bandY * 3.0, floor(iTime * 4.0))) - 0.5);
        shift *= (12.0 + bass * 90.0) / res.x;
        vec2 tornUV = vec2(uv.x + shift, uv.y);
        vec3 torn = texture(sTD2DInputs[0], clamp(tornUV, 0.0, 1.0)).rgb;
        result = torn;
    }

    // Color inversion on extreme tears
    if (tearHash > 0.94 && beat > 0.7) {
        result = 1.0 - result;
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },
]

# ─── PALETTE SWAP EFFECTS (20-39) ─────────────────────────────────────────────

PALETTE_SWAPS = [
    # ── 20: Cyberpunk Confetti ──
    {
        "name": "fx_g3_cyber_confetti",
        "label": "Cyberpunk Confetti",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    vec3 body = mix(src.rgb, vec3(0.0, 0.8, 1.0), 0.4 * step(0.15, luma));
    // Dark blue bg
    vec3 bg = vec3(0.02, 0.02, 0.12);
    // 30 cyberpunk confetti
    float confetti = 0.0;
    vec3 confettiColor = vec3(0.0);
    for (int i = 0; i < 30; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 0.7));
        float t = iTime * (0.5 + seed) + fi;
        vec2 pos = vec2(fract(seed + sin(t * 0.3) * 0.3), fract(fi * 0.0371 - t * 0.15 * (0.5 + bass)));
        float d = length((uv - pos) * vec2(1.0, 1.78));
        float size = 0.005 + bass * 0.008;
        if (d < size) {
            float sel = fract(seed * 5.0);
            if (sel < 0.33) confettiColor = vec3(1.0, 0.2, 0.6);      // hot pink
            else if (sel < 0.66) confettiColor = vec3(0.0, 0.6, 1.0);  // electric blue
            else confettiColor = vec3(1.0, 1.0, 0.0);                   // neon yellow
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

    # ── 21: Ocean Thermal ──
    {
        "name": "fx_g3_ocean_thermal",
        "label": "Ocean Thermal",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Bass-driven chromatic aberration
    float kick = min(1.0, sub + bass * 0.5);
    vec2 toC = uv - center;
    float dist = length(toC);
    vec2 dir = (dist > 0.001) ? toC / dist : vec2(0.0);
    float rOff = (3.0 + kick * 18.0) * texel.x * dist * 3.0;
    float bOff = -(2.0 + kick * 12.0) * texel.x * dist * 3.0;

    float R = texture(sTD2DInputs[0], uv + dir * rOff).r;
    float G = texture(sTD2DInputs[0], uv).g;
    float B = texture(sTD2DInputs[0], uv + dir * bOff).b;
    vec3 cam = vec3(R, G, B);
    float luma = dot(cam, vec3(0.299, 0.587, 0.114));

    // Ocean thermal posterize: navy / teal / seafoam white
    vec3 cNavy    = vec3(0.05, 0.1, 0.3);
    vec3 cTeal    = vec3(0.0, 0.6, 0.6);
    vec3 cSeafoam = vec3(0.8, 1.0, 0.95);

    float tLow  = 0.28 + bass * 0.1;
    float tHigh = 0.60 - bass * 0.1;

    vec3 result;
    if (luma < tLow) result = cNavy;
    else if (luma < tHigh) result = cTeal;
    else result = cSeafoam;

    // Slight energy glow
    result += vec3(0.0, 0.1, 0.1) * energy * 0.3;

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 22: Blood Fire ──
    {
        "name": "fx_g3_blood_fire",
        "label": "Blood Fire",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // Crimson body tint
    vec3 body = src.rgb * vec3(0.7, 0.05, 0.1);

    // FBM fire noise in blood palette
    float fireSpeed = 2.5 + energy * 6.0;
    vec2 fireUV = uv * 5.0 + vec2(0.0, -iTime * fireSpeed * 0.25);
    float fn = fbm(fireUV);

    vec3 fire = vec3(
        clamp(fn * 2.2, 0.0, 1.0),                    // deep red
        clamp(fn * 0.4 - 0.1, 0.0, 1.0),              // minimal green
        clamp(fn * 0.15 - 0.2, 0.0, 1.0)              // almost no blue
    );
    // Pale yellow tips on brightest fire
    fire = mix(fire, vec3(1.0, 0.9, 0.5), smoothstep(0.7, 0.95, fn));

    float bodyMask = smoothstep(0.08, 0.25, luma);
    float fireMix = 0.55 + bass * 0.3;
    vec3 result = mix(body, body + fire * vec3(1.0, 0.15, 0.05), fireMix * bodyMask);

    // Blood scanlines
    float scanline = step(0.5, fract(uv.y * res.y * 0.5));
    result -= vec3(0.06, 0.0, 0.0) * scanline * energy;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 23: Arctic Echo ──
    {
        "name": "fx_g3_arctic_echo",
        "label": "Arctic Echo",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // White body tint
    vec3 body = mix(vec3(1.0), src.rgb, 0.3);

    // Pale cyan starfield background
    vec3 bg = vec3(0.7, 0.95, 1.0) * 0.15;
    float starHash = hash(floor(uv * 120.0));
    if (starHash > 0.985) bg += vec3(0.5, 0.7, 0.8) * (0.5 + 0.5 * sin(iTime * 3.0 + starHash * 50.0));

    // 5 echo copies with ice-blue tint
    vec3 echoes = vec3(0.0);
    float totalW = 0.0;
    for (int i = 0; i < 5; i++) {
        float fi = float(i + 1);
        vec2 offset = vec2(
            sin(iTime * 0.4 + fi * 1.5) * 0.025 * fi,
            cos(iTime * 0.3 + fi * 2.1) * 0.018 * fi
        );
        vec3 echoSamp = texture(sTD2DInputs[0], clamp(uv + offset, 0.0, 1.0)).rgb;
        // Ice blue tint on echoes
        echoSamp = mix(echoSamp, vec3(0.6, 0.85, 1.0), 0.5);
        float w = 1.0 / (1.0 + fi * 0.5);
        echoes += echoSamp * w;
        totalW += w;
    }
    echoes /= totalW;

    float bodyMask = smoothstep(0.08, 0.2, luma);
    vec3 result = mix(bg, mix(echoes * 0.5, body, 0.6), bodyMask);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 24: Pastel Rainbow ──
    {
        "name": "fx_g3_pastel_rainbow",
        "label": "Pastel Rainbow",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    // 5 echo copies with 60-degree pastel hue shifts
    vec3 result = vec3(0.0);
    float totalW = 0.0;

    // Pastel palette: pink, mint, lavender, peach, sky
    vec3 pastels[5];
    pastels[0] = vec3(1.0, 0.7, 0.8);   // pink
    pastels[1] = vec3(0.6, 1.0, 0.8);   // mint
    pastels[2] = vec3(0.7, 0.6, 1.0);   // lavender
    pastels[3] = vec3(1.0, 0.85, 0.7);  // peach
    pastels[4] = vec3(0.7, 0.85, 1.0);  // sky

    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        vec2 offset = vec2(
            sin(iTime * 0.5 + fi * 1.3) * 0.03 * (fi + 1.0),
            cos(iTime * 0.4 + fi * 1.9) * 0.02 * (fi + 1.0)
        );
        vec3 echoSamp = texture(sTD2DInputs[0], clamp(uv + offset, 0.0, 1.0)).rgb;

        // Hue shift by 60 degrees per copy
        float hAngle = fi * 1.047; // 60 degrees in radians
        float hs = sin(hAngle), hc = cos(hAngle);
        float vs = sqrt(1.0 / 3.0);
        mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                      (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                      (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
        echoSamp = m * echoSamp;

        // Pastel overlay blend
        echoSamp = mix(echoSamp, pastels[i], 0.35);

        float w = 1.0 / (1.0 + fi * 0.4);
        result += echoSamp * w;
        totalW += w;
    }
    result /= totalW;

    // Soften contrast for pastel feel
    result = mix(vec3(0.5), result, 0.85);
    result = clamp(result + vec3(0.08), 0.0, 1.0);

    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 25: Cyber Kaleido ──
    {
        "name": "fx_g3_cyber_kaleido",
        "label": "Cyber Kaleido",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 p = uv - center;

    // 8-fold kaleidoscope with fast energy-driven rotation
    float r = length(p);
    float theta = atan(p.y, p.x) + iTime * energy * 2.0;
    float sliceAngle = 6.28318 / 8.0;
    float thetaMod = mod(theta, sliceAngle);
    float foldIdx = floor(theta / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;
    vec2 kUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
    kUV = clamp(kUV, 0.0, 1.0);

    vec4 src = texture(sTD2DInputs[0], kUV);
    vec3 result = src.rgb;

    // Cyberpunk saturation boost to 1.8
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.8);

    // Hot pink / cyan edge tint based on edge detection
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], kUV + vec2(float(x), float(y)) * texel * 2.0).rgb,
                         vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.06, 0.2, sqrt(sobelX * sobelX + sobelY * sobelY));
    float edgeAngle = atan(sobelY, sobelX);

    // Alternate hot pink and cyan on edges
    vec3 edgeColor = mix(vec3(1.0, 0.2, 0.5), vec3(0.0, 1.0, 1.0), sin(edgeAngle * 2.0) * 0.5 + 0.5);
    result += edgeColor * edge * (1.0 + bass * 1.5);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 26: Ocean Plasma ──
    {
        "name": "fx_g3_ocean_plasma",
        "label": "Ocean Plasma",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));

    // Dark teal background
    vec3 bg = vec3(0.0, 0.3, 0.4);

    // 10 bioluminescent tentacles
    vec3 tentacles = vec3(0.0);
    for (int i = 0; i < 10; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 1.3));
        float baseX = seed;
        float waveAmp = 0.08 + seed * 0.06;
        float waveFreq = 4.0 + fi * 0.7;
        float speed = 0.8 + seed * 0.6;

        // Tentacle center line
        float tentX = baseX + sin(uv.y * waveFreq + iTime * speed + fi * 2.0) * waveAmp;
        tentX += sin(uv.y * waveFreq * 2.3 + iTime * speed * 1.4) * waveAmp * 0.3;
        float d = abs(uv.x - tentX);

        float width = (0.008 + bass * 0.012) * (1.0 + sin(uv.y * 10.0 + iTime) * 0.3);
        float glow = exp(-d * d / (width * width));

        // Alternate bioluminescent cyan and deep blue
        vec3 tColor = mix(vec3(0.0, 0.8, 1.0), vec3(0.1, 0.2, 0.6), step(0.5, fract(seed * 3.7)));
        tentacles += tColor * glow * (0.6 + energy * 0.4);
    }

    float bodyMask = smoothstep(0.08, 0.2, luma);
    vec3 body = src.rgb * vec3(0.2, 0.5, 0.6);
    vec3 result = mix(bg, body, bodyMask);
    result += tentacles;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 27: Blood Strobe ──
    {
        "name": "fx_g3_blood_strobe",
        "label": "Blood Strobe",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb;

    // Dark crimson body tint
    result *= vec3(0.9, 0.4, 0.35);

    // High contrast 2.0
    float contrast = 2.0;
    result = (result - 0.5) * contrast + 0.5;

    // Beat-triggered blood red flash (instead of white)
    float strobe = step(0.7, beat);
    vec3 bloodFlash = vec3(0.8, 0.1, 0.05);
    result = mix(result, bloodFlash, strobe * 0.7);

    // Beat-triggered inversion with crimson tint
    if (beat > 0.85) {
        result = 1.0 - result;
        result *= vec3(1.0, 0.3, 0.2);
    }

    // Afterimage persistence
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec3 shifted = texture(sTD2DInputs[0], uv + vec2(0.003, 0.001)).rgb;
    shifted *= vec3(0.8, 0.1, 0.05);
    result = mix(result, shifted, 0.1);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 28: Arctic Pixel ──
    {
        "name": "fx_g3_arctic_pixel",
        "label": "Arctic Pixel",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    float kick = min(1.0, sub + bass * 0.5);

    // Pixelation with bass-driven block size
    float blockSize = 12.0 + bass * 16.0;
    vec2 blockUV = floor(uv * res / blockSize) * blockSize / res + (blockSize * 0.5) / res;
    vec4 pixSrc = texture(sTD2DInputs[0], blockUV);

    // Ice palette: shift colors to blue-white tones
    vec3 result = pixSrc.rgb * vec3(0.7, 0.85, 1.0);

    // Frost blue inversions on random blocks
    float blockHash = hash(floor(uv * res / blockSize));
    float glitchTrigger = step(1.0 - kick * 0.25, blockHash);
    if (glitchTrigger > 0.5) {
        result = vec3(1.0) - result;
        result *= vec3(0.6, 0.8, 1.0); // keep frost-blue on inversion
    }

    // Random block color shift (arctic palette)
    float shiftHash = hash(floor(uv * res / blockSize) + floor(iTime * 3.0));
    if (shiftHash > 0.92 && kick > 0.3) {
        result = vec3(0.8, 0.92, 1.0); // frost white block
    }

    // Scanline overlay
    float scanline = step(0.5, fract(uv.y * res.y * 0.5));
    result -= vec3(0.03) * scanline;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 29: Pastel Matrix ──
    {
        "name": "fx_g3_pastel_matrix",
        "label": "Pastel Matrix",
        "shader": GLSL_HEADER + """
float charPattern(vec2 uv, float seed) {
    vec2 grid = floor(uv * vec2(4.0, 5.0));
    return step(0.5, hash(grid + seed));
}

void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);

    // Cream background
    vec3 bg = vec3(0.95, 0.93, 0.88);

    // Pastel matrix rain
    float charSize = 10.0;
    vec2 cellUV = uv * res / charSize;
    vec2 cell = floor(cellUV);
    vec2 cellFract = fract(cellUV);

    float speed = 2.5 + energy * 4.0;
    float columnSeed = hash(vec2(cell.x, 0.0));
    float fallOffset = iTime * speed * (0.5 + columnSeed);
    float charIdx = cell.y - fallOffset;
    float charCell = floor(charIdx);
    float charSeed = hash(vec2(cell.x, charCell)) + floor(iTime * 2.0) * 0.01;
    float ch = charPattern(cellFract, charSeed);

    float age = fract(-charIdx * 0.04);
    float brightness = age > 0.95 ? 1.0 : age * 0.6;
    float columnActive = step(0.45, hash(vec2(cell.x, floor(iTime * 0.5))));

    vec3 rain = vec3(0.0);
    if (columnActive > 0.3) {
        if (age > 0.95) rain = vec3(1.0, 0.6, 0.7) * ch;       // soft pink leading
        else rain = vec3(0.6, 0.4, 0.8) * brightness * ch;      // lavender trail
    }

    // Blend camera faintly into background
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    vec3 result = mix(bg, src.rgb * 0.4 + bg * 0.6, bodyMask);
    result += rain * 0.7;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 30: Cyber Skeleton ──
    {
        "name": "fx_g3_cyber_skeleton",
        "label": "Cyber Skeleton",
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
    float edgeMask = smoothstep(0.08, 0.25, edge);
    float edgeAngle = atan(sobelY, sobelX);

    // Alternate hot pink and electric blue based on edge angle
    vec3 hotPink = vec3(1.0, 0.2, 0.5);
    vec3 electricBlue = vec3(0.0, 0.5, 1.0);
    float angleMix = sin(edgeAngle * 3.0 + iTime * 1.5) * 0.5 + 0.5;
    vec3 neonColor = mix(hotPink, electricBlue, angleMix);

    // Glow spread
    float glowR = (4.0 + energy * 10.0) * texel.x;
    float glow = 0.0;
    for (int i = 0; i < 8; i++) {
        float angle = float(i) * 0.785;
        vec2 off = vec2(cos(angle), sin(angle)) * glowR;
        vec3 samp = texture(sTD2DInputs[0], uv + off).rgb;
        vec3 samp2 = texture(sTD2DInputs[0], uv + off + texel).rgb;
        glow += length(samp - samp2);
    }
    glow /= 8.0;

    // Dark body ghost
    vec3 ghost = src.rgb * 0.08 * smoothstep(0.08, 0.2, luma);
    vec3 result = ghost + neonColor * edgeMask * (1.5 + bass * 2.0);
    result += neonColor * glow * 0.5;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 31: Ocean Solarize ──
    {
        "name": "fx_g3_ocean_solarize",
        "label": "Ocean Solarize",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);

    // Per-channel solarization with ocean palette weighting
    float phase = iTime * 2.0;
    float tR = (100.0 + sin(phase) * 40.0 + energy * 20.0) / 255.0;        // lower red threshold
    float tG = (130.0 + sin(phase + 2.09) * 50.0 + mids * 25.0) / 255.0;   // mid green
    float tB = (160.0 + sin(phase + 4.19) * 55.0 + bass * 35.0) / 255.0;   // higher blue threshold

    vec3 result;
    result.r = src.r > tR ? 1.0 - src.r : src.r;
    result.g = src.g > tG ? 1.0 - src.g : src.g;
    result.b = src.b > tB ? 1.0 - src.b : src.b;

    // Navy / teal / coral palette shift
    vec3 navy = vec3(0.05, 0.1, 0.3);
    vec3 teal = vec3(0.0, 0.6, 0.6);
    vec3 coral = vec3(1.0, 0.5, 0.4);

    float luma = dot(result, vec3(0.299, 0.587, 0.114));
    vec3 palette = mix(navy, teal, smoothstep(0.2, 0.45, luma));
    palette = mix(palette, coral, smoothstep(0.55, 0.8, luma));
    result = mix(result, palette, 0.5 + bass * 0.2);

    // Beat pulse
    result += vec3(0.0, 0.08, 0.1) * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 32: Blood Glitch ──
    {
        "name": "fx_g3_blood_glitch",
        "label": "Blood Glitch",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    float kick = min(1.0, sub + bass * 0.5);

    // Bass-heavy horizontal band displacement
    vec2 displaced = uv;
    float bandY = floor(uv.y * res.y / 6.0);
    float tearHash = hash(vec2(bandY, floor(iTime * 5.0)));
    if (tearHash > (1.0 - kick * 0.4)) {
        float shift = (hash(vec2(bandY * 3.0, floor(iTime * 5.0))) - 0.5);
        shift *= (10.0 + bass * 100.0) / res.x;
        displaced.x += shift;
    }

    vec4 src = texture(sTD2DInputs[0], clamp(displaced, 0.0, 1.0));
    vec3 result = src.rgb;

    // Deep red color on torn bands
    if (tearHash > (1.0 - kick * 0.4)) {
        result *= vec3(0.6, 0.0, 0.0);
    }

    // Crimson inversion on extreme tears
    if (tearHash > 0.92) {
        result = 1.0 - result;
        result *= vec3(0.9, 0.15, 0.1);
    }

    // Overall blood tint
    result = mix(result, result * vec3(1.0, 0.3, 0.2), 0.3);

    // Scanline overlay on kicks
    if (kick > 0.5) {
        float scanline = step(0.5, fract(uv.y * res.y * 0.5));
        result -= vec3(0.08, 0.0, 0.0) * scanline;
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 33: Arctic Radial ──
    {
        "name": "fx_g3_arctic_radial",
        "label": "Arctic Radial",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    // 6-layer radial zoom with progressive ice-blue tinting
    vec3 result = vec3(0.0);
    float totalW = 0.0;

    for (int i = 0; i < 6; i++) {
        float fi = float(i);
        float zoomFactor = 1.0 - fi * 0.06 * (1.0 + bass * 0.5);
        vec2 toC = uv - center;
        vec2 zoomedUV = center + toC * zoomFactor;
        zoomedUV = clamp(zoomedUV, 0.0, 1.0);

        vec3 samp = texture(sTD2DInputs[0], zoomedUV).rgb;

        // Progressive cooler temperature per layer
        float coolness = fi / 5.0;
        vec3 iceTint = vec3(0.7 - coolness * 0.1, 0.9 + coolness * 0.05, 1.0);
        samp = mix(samp, samp * iceTint, 0.3 + coolness * 0.4);

        float w = 1.0 / (1.0 + fi * 0.4);
        result += samp * w;
        totalW += w;
    }
    result /= totalW;

    // Overall ice-blue tint
    result = mix(result, result * vec3(0.7, 0.9, 1.0), 0.25);

    // Beat flash with cool white
    result += vec3(0.85, 0.92, 1.0) * 0.12 * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 34: Pastel Feedback ──
    {
        "name": "fx_g3_pastel_feedback",
        "label": "Pastel Feedback",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);

    // Gentle feedback spiral: scale 0.97, rotation 1.5 degrees
    vec2 p = uv - center;
    float scale = 0.97;
    float rot = 1.5 * 3.14159 / 180.0;
    float cs = cos(rot), sn = sin(rot);
    vec2 spiralUV = vec2(p.x * cs - p.y * sn, p.x * sn + p.y * cs) * scale + center;
    spiralUV = clamp(spiralUV, 0.0, 1.0);

    vec4 feedSrc = texture(sTD2DInputs[0], spiralUV);
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.2, luma);

    // Mix feedback with direct camera
    vec3 mixed = mix(feedSrc.rgb * 0.95, src.rgb, bodyMask);

    // Soft pastel hue rotation: 15 degrees per iteration step
    float hAngle = 15.0 * 3.14159 / 180.0 * (1.0 + sin(iTime * 0.3));
    float hs = sin(hAngle), hc = cos(hAngle);
    float vs = sqrt(1.0 / 3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                  (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                  (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
    mixed = m * mixed;

    // Pastel softening: reduce contrast, add warmth
    mixed = mix(vec3(0.5), mixed, 0.8);
    mixed += vec3(0.06, 0.04, 0.07); // slight pastel lift

    // Gentle saturation
    float gray = dot(mixed, vec3(0.299, 0.587, 0.114));
    mixed = mix(vec3(gray), mixed, 1.2);

    fragColor = TDOutputSwizzle(vec4(clamp(mixed, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 35: Cyber Datamosh ──
    {
        "name": "fx_g3_cyber_datamosh",
        "label": "Cyber Datamosh",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // 10-sample motion smear with noise-based direction
    float moshAmp = (3.0 + bass * 10.0) * texel.x;
    vec2 motionDir = vec2(
        noise(uv * 5.0 + iTime * 1.3) - 0.5,
        noise(uv * 5.0 + iTime * 1.3 + 70.0) - 0.5
    ) * moshAmp;

    vec3 smeared = vec3(0.0);
    for (int i = 0; i < 10; i++) {
        float fi = float(i) / 10.0;
        vec3 samp = texture(sTD2DInputs[0], clamp(uv + motionDir * fi, 0.0, 1.0)).rgb;

        // Alternate neon magenta and cyan tint per sample
        if (i % 2 == 0) {
            samp = mix(samp, samp * vec3(1.0, 0.0, 0.8), 0.4);   // magenta tint
        } else {
            samp = mix(samp, samp * vec3(0.0, 1.0, 1.0), 0.4);   // cyan tint
        }
        smeared += samp;
    }
    smeared /= 10.0;

    vec4 src = texture(sTD2DInputs[0], uv);
    float freeze = max(0.0, highs - 0.15) * 2.5;
    vec3 result = mix(src.rgb, smeared, freeze * 0.6);

    // Neon saturation boost
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, 1.6);

    // Magenta/cyan edge glow
    result += vec3(1.0, 0.0, 0.8) * energy * 0.08;
    result += vec3(0.0, 1.0, 1.0) * bass * 0.06;

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 36: Ocean Liquify ──
    {
        "name": "fx_g3_ocean_liquify",
        "label": "Ocean Liquify",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Sinusoidal UV displacement (liquid wave)
    float amp = (5.0 + bass * 25.0) * texel.x;
    float freq = 14.0 + mids * 10.0;
    float phase = iTime * 2.5;
    vec2 displaced = uv;
    displaced.x += sin(uv.y * freq + phase) * amp;
    displaced.y += cos(uv.x * freq * 0.8 + phase * 0.7) * amp * 0.6;

    vec4 src = texture(sTD2DInputs[0], clamp(displaced, 0.0, 1.0));

    // Deep ocean teal body tint
    vec3 result = src.rgb * vec3(0.3, 0.7, 0.7);
    result = mix(src.rgb, result, 0.6);

    // Bioluminescent edge glow via simple gradient detection
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float lumaR = dot(texture(sTD2DInputs[0], clamp(displaced + vec2(texel.x * 3.0, 0.0), 0.0, 1.0)).rgb,
                      vec3(0.299, 0.587, 0.114));
    float lumaU = dot(texture(sTD2DInputs[0], clamp(displaced + vec2(0.0, texel.y * 3.0), 0.0, 1.0)).rgb,
                      vec3(0.299, 0.587, 0.114));
    float edge = abs(luma - lumaR) + abs(luma - lumaU);
    float edgeMask = smoothstep(0.03, 0.15, edge);

    // Bioluminescent cyan glow on edges
    vec3 bioGlow = vec3(0.0, 0.8, 1.0);
    result += bioGlow * edgeMask * (1.2 + energy * 1.5);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 37: Blood Chromatic ──
    {
        "name": "fx_g3_blood_chromatic",
        "label": "Blood Chromatic",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;

    // Blood palette chromatic aberration: R big, G small, B medium
    float kick = min(1.0, sub + bass * 0.5);
    vec2 toC = uv - center;
    float dist = length(toC);
    vec2 dir = (dist > 0.001) ? toC / dist : vec2(0.0);

    float rOff = (6.0 + kick * 30.0) * texel.x * dist * 4.0;    // big red offset
    float gOff = (1.5 + kick * 6.0) * texel.x * dist * 4.0;     // small green offset
    float bOff = -(3.5 + kick * 18.0) * texel.x * dist * 4.0;   // medium blue offset

    float R = texture(sTD2DInputs[0], uv + dir * rOff).r;
    float G = texture(sTD2DInputs[0], uv + dir * gOff).g;
    float B = texture(sTD2DInputs[0], uv + dir * bOff).b;
    vec3 result = vec3(R, G, B);

    // Dark crimson body overlay
    vec3 crimson = vec3(0.5, 0.05, 0.08);
    float luma = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(result, result * crimson * 3.0, 0.4);

    // Boost red channel
    result.r = clamp(result.r * 1.4, 0.0, 1.0);
    result.g *= 0.5;
    result.b *= 0.6;

    // Beat flash
    result += vec3(0.3, 0.05, 0.02) * step(0.7, beat);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 38: Arctic Triangle ──
    {
        "name": "fx_g3_arctic_triangle",
        "label": "Arctic Triangle",
        "shader": GLSL_HEADER + """
vec2 voronoi_ice(vec2 p, float kick) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    float minDist = 1.0;
    vec2 minPoint = vec2(0.0);
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = vec2(hash(i + neighbor));
            if (kick > 0.4) {
                point += (hash(i + neighbor + floor(iTime)) - 0.5) * kick * 0.3;
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
    vec2 center = vec2(0.5);
    float kick = min(1.0, sub + bass * 0.5);

    float gridSize = 12.0 + bass * 6.0;
    vec2 v = voronoi_ice(uv * gridSize, kick);
    float edge = smoothstep(0.02, 0.05, v.x);

    // Each cell samples from offset position
    float cellSeed = v.y;
    float zoomFactor = 0.88 + cellSeed * 0.24;
    vec2 toC = uv - center;
    vec2 cellUV = center + toC * zoomFactor;
    cellUV = clamp(cellUV, 0.0, 1.0);

    vec4 cellColor = texture(sTD2DInputs[0], cellUV);

    // Frost-white cell fills
    vec3 fillColor = mix(cellColor.rgb, vec3(0.9, 0.95, 1.0), 0.35);
    vec3 result = fillColor * edge;

    // Ice-blue cell edges
    vec3 iceEdge = vec3(0.6, 0.8, 1.0);
    result += iceEdge * (1.0 - edge) * 0.7;

    // Dark blue in deepest gaps
    result = mix(vec3(0.05, 0.1, 0.25), result, 0.85 + edge * 0.15);

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },

    # ── 39: Pastel Pixelate ──
    {
        "name": "fx_g3_pastel_pixelate",
        "label": "Pastel Pixelate",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;

    // Cascading pixelation: larger blocks at top, smaller at bottom
    float yFactor = 1.0 - uv.y;
    float blockSize = mix(4.0, 32.0 + bass * 16.0, yFactor * yFactor);
    blockSize = max(2.0, floor(blockSize));

    vec2 pixUV = floor(uv * res / blockSize) * blockSize / res + (blockSize * 0.5) / res;
    vec4 pixSrc = texture(sTD2DInputs[0], pixUV);

    vec3 result = pixSrc.rgb;

    // Pastel wash overlay
    vec3 pastelWash = vec3(0.9, 0.8, 0.85);
    result = mix(result, pastelWash, 0.3);

    // Subtle hue variation per block
    float blockHash = hash(floor(uv * res / blockSize));
    float hAngle = blockHash * 0.5 + iTime * 0.1;
    float hs = sin(hAngle), hc = cos(hAngle);
    float vs = sqrt(1.0 / 3.0);
    mat3 m = mat3(hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs,
                  (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0, (1.0-hc)/3.0-vs*hs,
                  (1.0-hc)/3.0-vs*hs, (1.0-hc)/3.0+vs*hs, hc+(1.0-hc)/3.0);
    result = m * result;

    // Soften for pastel look
    result = mix(vec3(0.5), result, 0.75);
    result = clamp(result + vec3(0.08, 0.06, 0.09), 0.0, 1.0);

    // Beat sparkle on random blocks
    if (blockHash > 0.93 && beat > 0.6) {
        result += vec3(0.15, 0.12, 0.18);
    }

    fragColor = TDOutputSwizzle(vec4(clamp(result, 0.0, 1.0), 1.0));
}
""",
    },
]

# ─── INTENSITY MUTATIONS (40-56) ─────────────────────────────────────────────

INTENSITY_MUTATIONS = [
    # ── 40: Hyper Confetti ──
    {
        "name": "fx_g3_hyper_confetti",
        "label": "Hyper Confetti",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb * 0.3;

    float t = iTime * 3.0;
    for (int i = 0; i < 100; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi, fi * 7.13));
        float x = fract(seed * 13.7 + t * (0.1 + seed * 0.15) * (mod(fi, 2.0) == 0.0 ? 1.0 : -1.0));
        float y = fract(seed * 9.3 - t * (0.3 + seed * 0.5));
        vec2 pos = vec2(x, y);
        float sz = (3.0 + bass * 8.0) / res.x;
        float d = max(abs(uv.x - pos.x), abs(uv.y - pos.y));
        if (d < sz) {
            float hue = fract(fi * 0.073 + iTime * 0.2);
            vec3 col = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
            result += col * (1.0 - d / sz) * 0.6;
        }
    }

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 41: Ultra Fire ──
    {
        "name": "fx_g3_ultra_fire",
        "label": "Ultra Fire",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.4, luma);

    float fireSpeed = 10.0 + energy * 40.0;
    vec2 fireUV = uv * 12.0;
    fireUV.y -= iTime * fireSpeed;

    float f = fbm(fireUV);
    f += fbm(fireUV * 2.1 + iTime * 3.0) * 0.5;
    f = f * 0.7 + bass * 0.6;

    vec3 fireCol = mix(vec3(1.0, 0.1, 0.0), vec3(1.0, 0.9, 0.2), f);
    fireCol = mix(fireCol, vec3(0.2, 0.5, 1.0), highs * 0.3);

    vec3 result = mix(src.rgb, fireCol, bodyMask * f);
    result += fireCol * (1.0 - bodyMask) * f * 0.4;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 42: Mega Echo ──
    {
        "name": "fx_g3_mega_echo",
        "label": "Mega Echo",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec3 result = vec3(0.0);
    float totalW = 0.0;

    for (int i = 0; i < 10; i++) {
        float fi = float(i);
        vec2 off = vec2(fi * 0.01, fi * 0.005);
        off *= 1.0 + energy * 2.0;
        vec4 s = texture(sTD2DInputs[0], uv - off);
        float w = 1.0 / (1.0 + fi * 0.4);
        float hueShift = fi * 36.0 / 360.0;
        vec3 col = s.rgb;
        float h = fract(atan(col.g - col.b, col.r - col.g) / 6.2832 + hueShift);
        float sat = length(col - vec3(dot(col, vec3(0.333))));
        col = 0.5 + 0.5 * cos(6.2832 * (h + vec3(0.0, 0.33, 0.67)));
        col = mix(s.rgb, col, 0.6);
        result += col * w;
        totalW += w;
    }

    result /= totalW;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 43: Micro Pixel ──
    {
        "name": "fx_g3_micro_pixel",
        "label": "Micro Pixel",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    float blockSize = 4.0 + bass * 4.0;
    vec2 blockUV = floor(uv * res / blockSize) * blockSize / res;
    vec4 src = texture(sTD2DInputs[0], blockUV);
    vec3 result = src.rgb;

    float blockHash = hash(blockUV * 100.0);
    if (beat > 0.6 && blockHash > 0.5) {
        result.rgb = result.bgr;
    }

    float contrast = 1.2 + energy * 0.8;
    result = (result - 0.5) * contrast + 0.5;
    result += vec3(0.02, 0.01, 0.03) * blockHash;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 44: Antigrav Confetti ──
    {
        "name": "fx_g3_antigrav_confetti",
        "label": "Antigrav Confetti",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb * 0.35;

    float t = iTime * 2.0;
    for (int i = 0; i < 50; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi * 3.17, fi * 11.13));
        float x = fract(seed * 17.3 + cos(t * (0.5 + seed)) * 0.3);
        float y = fract(seed * 7.9 + t * 0.2 * (0.5 + seed));
        vec2 pos = vec2(x, y);
        float sz = (3.0 + mids * 6.0) / res.x;
        float angle = t * (1.0 + seed * 3.0);
        pos.x += sin(angle) * 0.02;
        pos.y += cos(angle * 0.7) * 0.015;
        float d = length(uv - pos);
        if (d < sz) {
            float hue = fract(fi * 0.061 + iTime * 0.15);
            vec3 col = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
            result += col * (1.0 - d / sz) * 0.7;
        }
    }

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 45: Extreme Kaleido ──
    {
        "name": "fx_g3_extreme_kaleido",
        "label": "Extreme Kaleido",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 p = uv - 0.5;
    float r = length(p);
    float a = atan(p.y, p.x);

    float rot = iTime * energy * 5.0;
    a += rot;

    float nFolds = 32.0;
    float sector = 6.2832 / nFolds;
    a = mod(a, sector);
    if (a > sector * 0.5) a = sector - a;

    vec2 kUV = vec2(cos(a), sin(a)) * r + 0.5;
    vec4 src = texture(sTD2DInputs[0], kUV);
    vec3 result = src.rgb;

    float sat = 2.0;
    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    result = mix(vec3(gray), result, sat);

    result += vec3(0.05, 0.02, 0.08) * bass;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 46: Turbo Spiral ──
    {
        "name": "fx_g3_turbo_spiral",
        "label": "Turbo Spiral",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec3 result = vec3(0.0);
    float totalW = 0.0;

    float rotDeg = 50.0 + mids * 50.0;
    float rotRad = rotDeg * 3.14159 / 180.0;
    float sc = 0.93;

    vec2 p = uv;
    for (int i = 0; i < 8; i++) {
        float fi = float(i);
        p -= center;
        float cs = cos(rotRad * 0.15);
        float sn = sin(rotRad * 0.15);
        p = mat2(cs, -sn, sn, cs) * p * sc;
        p += center;
        vec4 s = texture(sTD2DInputs[0], clamp(p, 0.0, 1.0));
        float hueShift = fi * 0.08 + iTime * 0.05;
        vec3 col = 0.5 + 0.5 * cos(6.2832 * (hueShift + vec3(0.0, 0.33, 0.67)));
        float w = 1.0 / (1.0 + fi * 0.5);
        result += mix(s.rgb, col, 0.3) * w;
        totalW += w;
    }

    result /= totalW;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 47: Super Datamosh ──
    {
        "name": "fx_g3_super_datamosh",
        "label": "Super Datamosh",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 texel = 1.0 / res;
    vec3 result = vec3(0.0);

    float freezeIntensity = energy * 8.0;
    for (int i = 0; i < 24; i++) {
        float fi = float(i);
        float seed = hash(vec2(fi * 3.7, fi * 11.1 + floor(iTime * 2.0)));
        vec2 noiseOff = (vec2(seed, hash(vec2(seed, fi))) - 0.5) * freezeIntensity * texel * 20.0;
        vec2 motionOff = vec2(fi * 0.003, 0.0) * (1.0 + bass * 3.0);
        vec4 s = texture(sTD2DInputs[0], uv + noiseOff + motionOff);
        result += s.rgb;
    }

    result /= 24.0;
    float contrast = 1.3 + beat * 0.5;
    result = (result - 0.5) * contrast + 0.5;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 48: Mega Tentacles ──
    {
        "name": "fx_g3_mega_tentacles",
        "label": "Mega Tentacles",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.15, 0.5, luma);

    vec3 result = src.rgb * (1.0 - bodyMask * 0.7);
    float t = iTime * 1.5;

    for (int i = 0; i < 30; i++) {
        float fi = float(i);
        float angle = fi * 6.2832 / 30.0 + t * 0.3;
        float wobble = sin(t * 2.0 + fi * 0.7) * 0.15;
        vec2 dir = vec2(cos(angle), sin(angle));
        vec2 tentPos = vec2(0.5) + dir * (0.1 + wobble);
        float d = length(uv - tentPos);
        float thickness = 0.008 + bass * 0.005;
        float glow = thickness / (d + 0.001);
        glow = clamp(glow, 0.0, 1.0);
        float hue = fract(fi / 30.0 + iTime * 0.1);
        vec3 col = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
        result += col * glow * 0.15;
    }

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 49: Ultra Strobe ──
    {
        "name": "fx_g3_ultra_strobe",
        "label": "Ultra Strobe",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb;

    float strobe = step(0.5, fract(iTime * 16.0));
    float contrast = 3.0;
    result = (result - 0.5) * contrast + 0.5;

    if (beat > 0.5) {
        result = vec3(1.0) - result;
    }

    result *= 0.3 + strobe * 0.7;
    float flash = step(0.85, beat) * 0.6;
    result += vec3(flash);

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 50: Extreme RGB ──
    {
        "name": "fx_g3_extreme_rgb",
        "label": "Extreme RGB",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 texel = 1.0 / res;

    float kick = min(1.0, sub + bass * 0.5);
    float baseOff = (40.0 + kick * 200.0) * texel.x;
    float angle = iTime * 0.5;
    vec2 dir = vec2(cos(angle), sin(angle));

    float r = texture(sTD2DInputs[0], uv + dir * baseOff).r;
    float g = texture(sTD2DInputs[0], uv).g;
    float b = texture(sTD2DInputs[0], uv - dir * baseOff).b;
    vec3 result = vec3(r, g, b);

    float luma = dot(result, vec3(0.299, 0.587, 0.114));
    float bloom = smoothstep(0.6, 1.0, luma) * 0.4;
    result += vec3(bloom);

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 51: Turbo Matrix ──
    {
        "name": "fx_g3_turbo_matrix",
        "label": "Turbo Matrix",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb * 0.15;

    float speed = 20.0 + energy * 60.0;
    float density = 60.0 + highs * 120.0;
    float colW = res.x / density;
    float col = floor(uv.x * density);
    float colSeed = hash(vec2(col, 0.0));
    float drop = fract(colSeed * 10.0 - iTime * speed / density * (0.5 + colSeed));
    float dist = abs(uv.y - drop);
    float trail = exp(-dist * density * 0.3);

    float charFlicker = step(0.4, hash(vec2(col, floor(iTime * 15.0 + uv.y * density))));
    vec3 matrixCol = vec3(0.1, 1.0, 0.3) * trail * charFlicker;
    matrixCol += vec3(0.0, 0.3, 0.1) * trail * 0.3;

    result += matrixCol;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 52: Hyper Glitch ──
    {
        "name": "fx_g3_hyper_glitch",
        "label": "Hyper Glitch",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;

    float bandH = 4.0;
    float band = floor(uv.y * res.y / bandH);
    float bandSeed = hash(vec2(band, floor(iTime * 8.0)));
    float shiftMag = (40.0 + bass * 400.0) / res.x;

    float shift = 0.0;
    if (bandSeed > 0.5) {
        shift = (bandSeed - 0.5) * 2.0 * shiftMag;
        if (mod(band, 2.0) == 0.0) shift = -shift;
    }

    vec2 glitchUV = vec2(fract(uv.x + shift), uv.y);
    vec4 src = texture(sTD2DInputs[0], glitchUV);
    vec3 result = src.rgb;

    if (beat > 0.7 && bandSeed > 0.7) {
        result = vec3(1.0) - result;
    }

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 53: Mega Shatter ──
    {
        "name": "fx_g3_mega_shatter",
        "label": "Mega Shatter",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    float gridSize = 30.0 + bass * 20.0;
    vec2 p = uv * gridSize;
    vec2 cell = floor(p);
    float minDist = 10.0;
    float minDist2 = 10.0;

    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 neighbor = vec2(float(x), float(y));
            vec2 point = hash(cell + neighbor) * vec2(1.0);
            point = 0.5 + 0.5 * sin(iTime * 0.5 + 6.2832 * vec2(hash(cell + neighbor), hash(cell + neighbor + 99.0)));
            float d = length(p - cell - neighbor - point);
            if (d < minDist) {
                minDist2 = minDist;
                minDist = d;
            } else if (d < minDist2) {
                minDist2 = d;
            }
        }
    }

    float edge = minDist2 - minDist;
    float edgeGlow = smoothstep(0.05, 0.0, edge) * (0.5 + energy);
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb * (0.5 + minDist * 0.5);
    result += vec3(0.3, 0.6, 1.0) * edgeGlow;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 54: Ultra Solarize ──
    {
        "name": "fx_g3_ultra_solarize",
        "label": "Ultra Solarize",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    vec3 result = src.rgb;

    float phase = iTime * 10.0;
    result.r = abs(sin(result.r * 3.14159 * 5.0 + phase));
    result.g = abs(sin(result.g * 3.14159 * 5.0 + phase + 2.094));
    result.b = abs(sin(result.b * 3.14159 * 5.0 + phase + 4.189));

    float gray = dot(result, vec3(0.299, 0.587, 0.114));
    float sat = 2.5;
    result = mix(vec3(gray), result, sat);

    result += vec3(bass * 0.1, mids * 0.05, highs * 0.1);
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 55: Extreme Zoom ──
    {
        "name": "fx_g3_extreme_zoom",
        "label": "Extreme Zoom",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec3 result = vec3(0.0);
    float totalW = 0.0;

    for (int i = 0; i < 12; i++) {
        float fi = float(i);
        float scale = 1.0 - fi * 0.06;
        float rot = fi * 0.3 + iTime * 0.15;
        vec2 p = uv - center;
        float cs = cos(rot);
        float sn = sin(rot);
        p = mat2(cs, -sn, sn, cs) * p;
        p *= scale;
        p += center;
        vec4 s = texture(sTD2DInputs[0], clamp(p, 0.0, 1.0));
        float hue = fract(fi * 0.07 + iTime * 0.04);
        vec3 tint = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
        float w = 1.0 / (1.0 + fi * 0.3);
        result += mix(s.rgb, tint, 0.25) * w;
        totalW += w;
    }

    result /= totalW;
    result *= 1.0 + energy * 0.3;
    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
    # ── 56: Turbo Neon ──
    {
        "name": "fx_g3_turbo_neon",
        "label": "Turbo Neon",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    vec2 texel = 4.0 / res;

    float tl = dot(texture(sTD2DInputs[0], uv + vec2(-texel.x, texel.y)).rgb, vec3(0.333));
    float t  = dot(texture(sTD2DInputs[0], uv + vec2(0.0, texel.y)).rgb, vec3(0.333));
    float tr = dot(texture(sTD2DInputs[0], uv + vec2(texel.x, texel.y)).rgb, vec3(0.333));
    float l  = dot(texture(sTD2DInputs[0], uv + vec2(-texel.x, 0.0)).rgb, vec3(0.333));
    float r  = dot(texture(sTD2DInputs[0], uv + vec2(texel.x, 0.0)).rgb, vec3(0.333));
    float bl = dot(texture(sTD2DInputs[0], uv + vec2(-texel.x, -texel.y)).rgb, vec3(0.333));
    float b  = dot(texture(sTD2DInputs[0], uv + vec2(0.0, -texel.y)).rgb, vec3(0.333));
    float br = dot(texture(sTD2DInputs[0], uv + vec2(texel.x, -texel.y)).rgb, vec3(0.333));

    float edgeX = -tl - 2.0*l - bl + tr + 2.0*r + br;
    float edgeY = -tl - 2.0*t - tr + bl + 2.0*b + br;
    float edge = sqrt(edgeX * edgeX + edgeY * edgeY);

    float glowRadius = (20.0 + energy * 40.0) / res.x;
    float glow = edge * (1.0 + smoothstep(0.0, glowRadius, edge) * 3.0);
    float hue = fract(edge * 2.0 + iTime * 0.2 + uv.x * 0.3);
    vec3 neonCol = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
    vec3 result = neonCol * glow * 2.0;

    if (beat > 0.7) {
        float jointHash = hash(floor(uv * res / 8.0));
        if (jointHash > 0.92) {
            result += vec3(0.8, 0.9, 1.0) * (beat - 0.7) * 3.0;
        }
    }

    result = clamp(result, 0.0, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
]

# Combined list of all Gen 3 effects
ALL_GEN3 = EFFECTS + PALETTE_SWAPS + INTENSITY_MUTATIONS


# --- BUILDER ---

def build_effect(idx, effect, dry_run=False):
    """Build one Gen 3 effect in TouchDesigner."""
    name = effect["name"]
    label = effect["label"]
    shader = effect["shader"]
    parent = "/project1"
    comp_path = f"{parent}/{name}"

    print(f"\n[{idx+1:2d}/57] Building {label} ({name})...")

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

    # Position below existing effects
    node_x = -400 + (idx % 7) * 170
    node_y = -1500 - (idx // 7) * 200
    td_exec(f"op('{comp_path}').nodeX = {node_x}; op('{comp_path}').nodeY = {node_y}")

    # 2. Create in1 (inTOP)
    td_create_op(comp_path, "inTOP", "in1")
    td_exec(f"op('{comp_path}/in1').nodeX = -300; op('{comp_path}/in1').nodeY = 0")

    # 3. Create GLSL TOP
    glsl_name = f"glsl_{name.replace('fx_g3_', '')}"
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
    parser = argparse.ArgumentParser(description="Build 57 Gen 3 effects in TouchDesigner")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--effect", type=int, default=-1, help="Build only effect N (0-indexed)")
    args = parser.parse_args()

    print("=" * 60)
    print("YOUSUKE Gen 3 Effect Builder")
    print(f"Building {len(ALL_GEN3)} Gen 3 effects via twozero MCP")
    print("=" * 60)

    if not args.dry_run:
        try:
            result = td_call("td_get_focus")
            print(f"\nTD connected: {result.split(chr(10))[0]}")
        except Exception as e:
            print(f"\nERROR: Cannot connect to TouchDesigner MCP: {e}")
            print("Make sure TouchDesigner is running with twozero.tox enabled")
            sys.exit(1)

    built = 0
    if args.effect >= 0:
        if args.effect < len(ALL_GEN3):
            if build_effect(args.effect, ALL_GEN3[args.effect], args.dry_run):
                built += 1
        else:
            print(f"Effect index {args.effect} out of range (0-{len(ALL_GEN3)-1})")
    else:
        for idx, effect in enumerate(ALL_GEN3):
            try:
                if build_effect(idx, effect, args.dry_run):
                    built += 1
            except Exception as e:
                print(f"  FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Built {built}/{len(ALL_GEN3)} Gen 3 effects")
    print("=" * 60)


if __name__ == "__main__":
    main()
