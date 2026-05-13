#!/usr/bin/env python3
"""
Build 33 Body Contour / Silhouette GLSL effects in TouchDesigner via twozero MCP bridge.

These effects emphasize the performer's body contour, silhouette, and outline
using Sobel edge detection, luma-based body masking, and outline extraction.

Each effect becomes a baseCOMP with:
  in1 (inTOP) -> glslTOP (pixel shader) -> out1 (outTOP)

GLSL receives uAudio  = (time, rms, bass, sub_bass)
              uAudio2 = (sub_bass, mids, highs, beat)

Usage:
  python3 tools/td_build_contour.py           # Build all effects
  python3 tools/td_build_contour.py --dry-run # Print what would be done
  python3 tools/td_build_contour.py --effect 0 # Build only effect #0
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

# Common GLSL header for all Body Contour effects
GLSL_HEADER = """// YOUSUKE Body Contour Effect
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

# ─── NEON CONTOUR EFFECTS (0-10) ─────────────────────────────────────────────

CONTOUR_EFFECTS = [
    # ── 0: Neon Outline ──
    {
        "name": "fx_g3_body_neon_outline",
        "label": "Neon Outline",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb,
                         vec3(0.299, 0.587, 0.114));
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            sobelX += s * kx;
            sobelY += s * ky;
        }
    }
    float edge = sqrt(sobelX * sobelX + sobelY * sobelY);
    float edgeMask = smoothstep(0.08, 0.3, edge);
    // Rainbow neon color cycling with position and time
    float hueShift = uv.x * 2.0 + uv.y * 1.5 + iTime * 1.2;
    vec3 neon = 0.5 + 0.5 * cos(6.2832 * (hueShift + vec3(0.0, 0.33, 0.67)));
    neon *= 1.0 + bass * 0.5;
    vec3 result = edgeMask * neon * (1.5 + energy);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 1: Pulse Edge ──
    {
        "name": "fx_g3_body_pulse_edge",
        "label": "Pulse Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float radius = (2.0 + bass * 6.0) * texel.x;
    float edgeSum = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * radius).rgb,
                         vec3(0.299, 0.587, 0.114));
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            edgeSum += abs(s * kx) + abs(s * ky);
        }
    }
    float edge = smoothstep(0.1, 0.5, edgeSum * 0.25);
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    vec3 bodyFill = vec3(0.02, 0.03, 0.12) * bodyMask;
    vec3 edgeColor = vec3(1.0, 1.0, 1.0) * edge * (1.0 + beat * 0.5);
    vec3 result = bodyFill + edgeColor;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 2: Double Edge ──
    {
        "name": "fx_g3_body_double_edge",
        "label": "Double Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float innerX = 0.0, innerY = 0.0, outerX = 0.0, outerY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 off = vec2(float(x), float(y));
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            float sInner = dot(texture(sTD2DInputs[0], uv + off * texel).rgb, vec3(0.299, 0.587, 0.114));
            float sOuter = dot(texture(sTD2DInputs[0], uv + off * texel * 3.0).rgb, vec3(0.299, 0.587, 0.114));
            innerX += sInner * kx; innerY += sInner * ky;
            outerX += sOuter * kx; outerY += sOuter * ky;
        }
    }
    float innerEdge = smoothstep(0.08, 0.3, sqrt(innerX*innerX + innerY*innerY));
    float outerEdge = smoothstep(0.05, 0.2, sqrt(outerX*outerX + outerY*outerY));
    vec3 cyan = vec3(0.0, 1.0, 1.0) * innerEdge * 1.5;
    vec3 magenta = vec3(1.0, 0.0, 1.0) * outerEdge * 1.2;
    vec3 result = cyan + magenta * (1.0 - innerEdge * 0.5);
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 3: Electric Wire ──
    {
        "name": "fx_g3_body_electric_wire",
        "label": "Electric Wire",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb,
                         vec3(0.299, 0.587, 0.114));
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            sobelX += s * kx;
            sobelY += s * ky;
        }
    }
    float edge = sqrt(sobelX * sobelX + sobelY * sobelY);
    float thinEdge = smoothstep(0.15, 0.35, edge);
    // Electric flicker using noise
    float flicker = hash(uv * 200.0 + vec2(iTime * 30.0, iTime * 17.0));
    flicker = step(0.3, flicker);
    float wire = thinEdge * flicker;
    // Occasional bright flash on beat
    wire *= 1.0 + beat * 2.0;
    vec3 result = vec3(wire) * vec3(0.9, 0.95, 1.0);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 4: Heat Contour ──
    {
        "name": "fx_g3_body_heat_contour",
        "label": "Heat Contour",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.05, 0.2, luma);
    // Multiple contour thresholds
    float contour = 0.0;
    for (int i = 1; i < 10; i++) {
        float threshold = float(i) * 0.1;
        float line = abs(luma - threshold);
        contour += smoothstep(0.02, 0.005, line);
    }
    contour = clamp(contour, 0.0, 1.0);
    // Thermal palette: blue -> cyan -> green -> yellow -> red
    vec3 thermal;
    if (luma < 0.25) thermal = mix(vec3(0.0, 0.0, 0.8), vec3(0.0, 0.8, 1.0), luma * 4.0);
    else if (luma < 0.5) thermal = mix(vec3(0.0, 0.8, 1.0), vec3(0.0, 1.0, 0.2), (luma - 0.25) * 4.0);
    else if (luma < 0.75) thermal = mix(vec3(0.0, 1.0, 0.2), vec3(1.0, 1.0, 0.0), (luma - 0.5) * 4.0);
    else thermal = mix(vec3(1.0, 1.0, 0.0), vec3(1.0, 0.1, 0.0), (luma - 0.75) * 4.0);
    vec3 result = thermal * bodyMask + vec3(1.0) * contour * bodyMask * 0.8;
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 5: Laser Scan ──
    {
        "name": "fx_g3_body_laser_scan",
        "label": "Laser Scan",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Scan line position sweeping vertically
    float scanY = sin(iTime * 1.5) * 0.5 + 0.5;
    float scanDist = abs(uv.y - scanY);
    float scanBand = smoothstep(0.06, 0.0, scanDist);
    // Sobel edges
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb,
                         vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Neon edges visible near scan line, dark silhouette elsewhere
    vec3 neonEdge = vec3(0.0, 1.0, 0.8) * edge * scanBand * 2.5;
    vec3 darkSil = vec3(0.02) * bodyMask * (1.0 - scanBand);
    vec3 scanLine = vec3(0.0, 0.4, 0.3) * scanBand * 0.3;
    vec3 result = neonEdge + darkSil + scanLine;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 6: Glitch Edge ──
    {
        "name": "fx_g3_body_glitch_edge",
        "label": "Glitch Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    // Horizontal band displacement
    float bandHash = hash(vec2(floor(uv.y * 40.0), floor(iTime * 8.0)));
    float displace = (bandHash - 0.5) * 0.03 * step(0.85, bandHash + bass * 0.3);
    vec2 uvR = uv + vec2(displace, 0.0);
    vec2 uvG = uv;
    vec2 uvB = uv - vec2(displace, 0.0);
    // Sobel on each channel separately
    float edgeR = 0.0, edgeG = 0.0, edgeB = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 off = vec2(float(x), float(y)) * texel;
            float kx = float(x) * (y == 0 ? 2.0 : 1.0);
            float ky = float(y) * (x == 0 ? 2.0 : 1.0);
            float k = abs(kx) + abs(ky);
            edgeR += dot(texture(sTD2DInputs[0], uvR + off).rgb, vec3(0.299, 0.587, 0.114)) * k;
            edgeG += dot(texture(sTD2DInputs[0], uvG + off).rgb, vec3(0.299, 0.587, 0.114)) * k;
            edgeB += dot(texture(sTD2DInputs[0], uvB + off).rgb, vec3(0.299, 0.587, 0.114)) * k;
        }
    }
    float eR = smoothstep(0.3, 0.8, edgeR * 0.25);
    float eG = smoothstep(0.3, 0.8, edgeG * 0.25);
    float eB = smoothstep(0.3, 0.8, edgeB * 0.25);
    vec3 result = vec3(eR * 1.3, eG * 1.1, eB * 1.3);
    result *= 1.0 + beat * 0.5;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 7: Fire Outline ──
    {
        "name": "fx_g3_body_fire_outline",
        "label": "Fire Outline",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb,
                         vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = sqrt(sobelX * sobelX + sobelY * sobelY);
    // Glow radius grows with energy
    float glowR = (3.0 + energy * 8.0) * texel.x;
    float glow = 0.0;
    for (int i = 0; i < 8; i++) {
        float a = float(i) * 0.785;
        float s = dot(texture(sTD2DInputs[0], uv + vec2(cos(a), sin(a)) * glowR).rgb, vec3(0.299, 0.587, 0.114));
        glow += smoothstep(0.08, 0.3, abs(s - dot(texture(sTD2DInputs[0], uv).rgb, vec3(0.299, 0.587, 0.114))));
    }
    glow /= 8.0;
    float intensity = max(edge, glow * 0.7);
    // Fire palette: red -> orange -> yellow
    vec3 fire;
    if (intensity < 0.33) fire = mix(vec3(0.5, 0.0, 0.0), vec3(1.0, 0.3, 0.0), intensity * 3.0);
    else if (intensity < 0.66) fire = mix(vec3(1.0, 0.3, 0.0), vec3(1.0, 0.7, 0.0), (intensity - 0.33) * 3.0);
    else fire = mix(vec3(1.0, 0.7, 0.0), vec3(1.0, 1.0, 0.5), (intensity - 0.66) * 3.0);
    vec3 result = fire * smoothstep(0.05, 0.2, intensity) * (1.5 + bass * 0.5);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 8: Matrix Edge ──
    {
        "name": "fx_g3_body_matrix_edge",
        "label": "Matrix Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Sobel edge
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Matrix rain on body region
    vec2 cell = floor(uv * vec2(60.0, 30.0));
    float charSpeed = hash(vec2(cell.x, 0.0)) * 3.0 + 1.0;
    float charPhase = hash(vec2(cell.x, 1.0));
    float rain = fract(-iTime * charSpeed + charPhase + cell.y * 0.1);
    float charBright = step(0.7, rain) * hash(cell + floor(iTime * 5.0));
    float matrixChar = charBright * bodyMask * 0.6;
    vec3 greenEdge = vec3(0.0, 1.0, 0.2) * edge * 2.0;
    vec3 greenRain = vec3(0.0, 0.8, 0.1) * matrixChar;
    vec3 result = greenEdge + greenRain;
    result *= 1.0 + beat * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 9: Plasma Edge ──
    {
        "name": "fx_g3_body_plasma_edge",
        "label": "Plasma Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel * 2.0).rgb,
                         vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = sqrt(sobelX * sobelX + sobelY * sobelY);
    float edgeMask = smoothstep(0.05, 0.25, edge);
    // Thick glow via multi-sample
    float glow = 0.0;
    for (int i = 0; i < 8; i++) {
        float a = float(i) * 0.785;
        vec2 off = vec2(cos(a), sin(a)) * texel * 5.0;
        float s = dot(texture(sTD2DInputs[0], uv + off).rgb, vec3(0.299, 0.587, 0.114));
        float c = dot(texture(sTD2DInputs[0], uv).rgb, vec3(0.299, 0.587, 0.114));
        glow += smoothstep(0.05, 0.2, abs(s - c));
    }
    glow /= 8.0;
    float combined = max(edgeMask, glow * 0.8);
    // Plasma color from sin waves
    float p1 = sin(uv.x * 8.0 + iTime * 2.0);
    float p2 = sin(uv.y * 6.0 - iTime * 1.5);
    float p3 = sin((uv.x + uv.y) * 10.0 + iTime * 3.0);
    float plasma = (p1 + p2 + p3) / 3.0 * 0.5 + 0.5;
    vec3 color = 0.5 + 0.5 * cos(6.2832 * (plasma + vec3(0.0, 0.33, 0.67)));
    vec3 result = color * combined * (1.5 + energy * 0.5);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 10: Strobe Edge ──
    {
        "name": "fx_g3_body_strobe_edge",
        "label": "Strobe Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb,
                         vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Beat-synced strobe: visible or ghost
    float strobe = step(0.5, fract(iTime * 4.0 + beat * 2.0));
    float bright = edge * strobe * 1.8;
    float ghost = edge * (1.0 - strobe) * 0.1;
    float combined = bright + ghost;
    vec3 result = vec3(combined);
    result *= 1.0 + beat * 0.5;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ─── SILHOUETTE EFFECTS (11-21) ──────────────────────────────────────────────

    # ── 11: Solid Silhouette ──
    {
        "name": "fx_g3_body_solid_silhouette",
        "label": "Solid Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.12, 0.18, luma);
    vec3 result = vec3(bodyMask);
    result *= 1.0 + beat * 0.2;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 12: Gradient Silhouette ──
    {
        "name": "fx_g3_body_gradient_sil",
        "label": "Gradient Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Vertical gradient: deep blue bottom -> hot pink top
    vec3 bottomColor = vec3(0.05, 0.02, 0.3);
    vec3 topColor = vec3(1.0, 0.1, 0.6);
    float gradT = uv.y + sin(iTime * 0.5) * 0.1;
    vec3 gradient = mix(bottomColor, topColor, clamp(gradT, 0.0, 1.0));
    vec3 result = gradient * bodyMask;
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 13: Starfield Silhouette ──
    {
        "name": "fx_g3_body_starfield_sil",
        "label": "Starfield Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Dense twinkling starfield
    float stars = 0.0;
    for (int layer = 0; layer < 3; layer++) {
        float scale = 80.0 + float(layer) * 40.0;
        vec2 cell = floor(uv * scale);
        float starHash = hash(cell + float(layer) * 100.0);
        float isStar = step(0.92, starHash);
        float twinkle = sin(iTime * (3.0 + starHash * 5.0) + starHash * 6.28) * 0.5 + 0.5;
        vec2 starPos = (cell + 0.5) / scale;
        float dist = length(uv - starPos) * scale;
        float brightness = isStar * smoothstep(1.5, 0.0, dist) * twinkle;
        stars += brightness;
    }
    stars = clamp(stars, 0.0, 1.0);
    // Stars inside body, dark bg outside
    vec3 starColor = vec3(0.8, 0.9, 1.0) * stars * bodyMask;
    vec3 darkBg = vec3(0.01) * (1.0 - bodyMask);
    vec3 result = starColor + darkBg;
    result *= 1.0 + beat * 0.4;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 14: Fire Silhouette ──
    {
        "name": "fx_g3_body_fire_sil",
        "label": "Fire Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Animated fire noise (fbm rising upward)
    float speed = 1.5 + energy * 3.0;
    vec2 fireUV = uv * vec2(3.0, 4.0) + vec2(0.0, -iTime * speed);
    float f = fbm(fireUV);
    float f2 = fbm(fireUV * 2.0 + 10.0);
    float fireIntensity = f * 0.7 + f2 * 0.3;
    fireIntensity *= (1.0 - uv.y * 0.5); // brighter at bottom
    // Fire palette
    vec3 fire;
    if (fireIntensity < 0.3) fire = mix(vec3(0.1, 0.0, 0.0), vec3(0.8, 0.1, 0.0), fireIntensity / 0.3);
    else if (fireIntensity < 0.6) fire = mix(vec3(0.8, 0.1, 0.0), vec3(1.0, 0.6, 0.0), (fireIntensity - 0.3) / 0.3);
    else fire = mix(vec3(1.0, 0.6, 0.0), vec3(1.0, 1.0, 0.5), (fireIntensity - 0.6) / 0.4);
    vec3 result = fire * bodyMask * 1.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 15: Ocean Silhouette ──
    {
        "name": "fx_g3_body_ocean_sil",
        "label": "Ocean Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Animated ocean wave noise with horizontal bias
    vec2 oceanUV = uv * vec2(5.0, 2.0) + vec2(iTime * 0.8, iTime * 0.3);
    float w1 = fbm(oceanUV);
    float w2 = fbm(oceanUV * 1.5 + vec2(50.0, 0.0));
    float wave = w1 * 0.6 + w2 * 0.4;
    // Ocean palette: dark blue -> teal -> cyan foam
    vec3 ocean;
    if (wave < 0.4) ocean = mix(vec3(0.0, 0.05, 0.2), vec3(0.0, 0.2, 0.4), wave / 0.4);
    else if (wave < 0.7) ocean = mix(vec3(0.0, 0.2, 0.4), vec3(0.0, 0.6, 0.6), (wave - 0.4) / 0.3);
    else ocean = mix(vec3(0.0, 0.6, 0.6), vec3(0.5, 0.9, 1.0), (wave - 0.7) / 0.3);
    vec3 result = ocean * bodyMask * (1.2 + bass * 0.4);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 16: Rainbow Silhouette ──
    {
        "name": "fx_g3_body_rainbow_sil",
        "label": "Rainbow Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Animated rainbow horizontal bands moving upward
    float bandSpeed = iTime * 0.8 + energy * 0.5;
    float hue = fract(uv.y * 3.0 - bandSpeed);
    vec3 rainbow = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
    rainbow *= 1.2; // boost saturation
    vec3 result = rainbow * bodyMask;
    result *= 1.0 + beat * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 17: Glitch Silhouette ──
    {
        "name": "fx_g3_body_glitch_sil",
        "label": "Glitch Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Horizontal glitch tears
    float band = floor(uv.y * 30.0);
    float bandSeed = hash(vec2(band, floor(iTime * 6.0)));
    float tearActive = step(0.8 - bass * 0.3, bandSeed);
    float displacement = (bandSeed - 0.5) * 0.08 * tearActive;
    // Re-sample body mask with displacement
    vec2 glitchUV = uv + vec2(displacement, 0.0);
    glitchUV = clamp(glitchUV, 0.0, 1.0);
    float glitchLuma = dot(texture(sTD2DInputs[0], glitchUV).rgb, vec3(0.299, 0.587, 0.114));
    float glitchMask = smoothstep(0.1, 0.25, glitchLuma);
    // White body on black, with glitch
    vec3 result = vec3(glitchMask);
    // Color fringe on tear bands
    result.r = tearActive > 0.5 ? smoothstep(0.1, 0.25, dot(texture(sTD2DInputs[0], uv + vec2(displacement * 1.2, 0.0)).rgb, vec3(0.299, 0.587, 0.114))) : result.r;
    result *= 1.0 + beat * 0.4;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 18: Pixel Silhouette ──
    {
        "name": "fx_g3_body_pixel_sil",
        "label": "Pixel Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 res = uTD2DInfos[0].res.zw;
    // Pixelate to 16px blocks
    float blockSize = 16.0;
    vec2 pixelUV = floor(uv * res / blockSize) * blockSize / res;
    pixelUV += (blockSize * 0.5) / res; // center of block
    vec4 src = texture(sTD2DInputs[0], pixelUV);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.12, 0.2, luma);
    // Solid color fill with slight hue shift over time
    float hue = fract(iTime * 0.1);
    vec3 color = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
    vec3 result = color * bodyMask;
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 19: Ghost Silhouette ──
    {
        "name": "fx_g3_body_ghost_sil",
        "label": "Ghost Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec3 result = vec3(0.0);
    // Multiple offset body masks for ghost trail
    for (int i = 0; i < 5; i++) {
        float fi = float(i);
        float t = fi * 0.02 * (1.0 + energy);
        vec2 offset = vec2(t * sin(iTime * 2.0 + fi), t * cos(iTime * 1.5 + fi * 1.3));
        vec2 sampleUV = clamp(uv + offset, 0.0, 1.0);
        vec4 src = texture(sTD2DInputs[0], sampleUV);
        float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
        float mask = smoothstep(0.1, 0.25, luma);
        float opacity = 1.0 - fi * 0.18;
        result += vec3(mask * opacity);
    }
    result /= 3.0; // normalize but keep layered brightness
    result = clamp(result, 0.0, 1.0);
    result *= 1.0 + beat * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 20: Kaleidoscope Silhouette ──
    {
        "name": "fx_g3_body_kaleidoscope_sil",
        "label": "Kaleidoscope Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 center = vec2(0.5);
    vec2 p = uv - center;
    // 4-fold kaleidoscope
    float r = length(p);
    float theta = atan(p.y, p.x) + iTime * 0.3;
    float sliceAngle = 6.2832 / 4.0;
    float thetaMod = mod(theta, sliceAngle);
    float foldIdx = floor(theta / sliceAngle);
    if (mod(foldIdx, 2.0) > 0.5) thetaMod = sliceAngle - thetaMod;
    vec2 kUV = center + r * vec2(cos(thetaMod), sin(thetaMod));
    kUV = clamp(kUV, 0.0, 1.0);
    // Sample body mask from folded coords
    vec4 src = texture(sTD2DInputs[0], kUV);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    vec3 result = vec3(bodyMask);
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 21: Inverted Silhouette ──
    {
        "name": "fx_g3_body_invert_sil",
        "label": "Inverted Silhouette",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Body = black void, bg = original camera image
    vec3 original = src.rgb;
    vec3 result = original * (1.0 - bodyMask);
    result *= 1.0 + energy * 0.2;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ─── COMBINED CONTOUR+FILL EFFECTS (22-32) ──────────────────────────────────

    # ── 22: Neon Fill ──
    {
        "name": "fx_g3_body_neon_fill",
        "label": "Neon Fill",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Sobel edge
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Cyan edges + translucent blue body fill
    vec3 edgeColor = vec3(0.0, 1.0, 1.0) * edge * 2.0;
    vec3 bodyFill = src.rgb * vec3(0.3, 0.4, 0.8) * bodyMask * 0.3;
    vec3 result = edgeColor + bodyFill;
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 23: X-Ray Contour ──
    {
        "name": "fx_g3_body_xray_contour",
        "label": "X-Ray Contour",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Inverted grayscale for x-ray body interior
    float invertedLuma = 1.0 - luma;
    vec3 xray = vec3(invertedLuma) * bodyMask;
    // Green Sobel edge outlines
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    vec3 greenEdge = vec3(0.1, 1.0, 0.2) * edge * 1.5;
    vec3 result = xray * 0.6 + greenEdge;
    result *= 1.0 + energy * 0.2;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 24: Thermal Contour ──
    {
        "name": "fx_g3_body_thermal_contour",
        "label": "Thermal Contour",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // 4-color thermal palette on body
    vec3 thermal;
    if (luma < 0.2) thermal = mix(vec3(0.0), vec3(0.3, 0.0, 0.5), luma * 5.0);
    else if (luma < 0.5) thermal = mix(vec3(0.3, 0.0, 0.5), vec3(1.0, 0.4, 0.0), (luma - 0.2) / 0.3);
    else thermal = mix(vec3(1.0, 0.4, 0.0), vec3(1.0, 1.0, 1.0), (luma - 0.5) / 0.5);
    thermal *= bodyMask;
    // White Sobel edge outlines on top
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    vec3 result = thermal + vec3(edge) * 1.2;
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 25: Cyberpunk Contour ──
    {
        "name": "fx_g3_body_cyberpunk_contour",
        "label": "Cyberpunk Contour",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Hot pink Sobel edges
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    vec3 pinkEdge = vec3(1.0, 0.1, 0.5) * edge * 2.0;
    // Scan lines on body interior (4px spacing)
    float scanLine = step(0.5, fract(uv.y * res.y / 4.0));
    vec3 bodyInterior = vec3(0.15, 0.05, 0.2) * bodyMask * scanLine;
    // Dark purple bg
    vec3 bg = vec3(0.05, 0.01, 0.08) * (1.0 - bodyMask);
    vec3 result = pinkEdge + bodyInterior + bg;
    result *= 1.0 + beat * 0.4;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 26: Hologram ──
    {
        "name": "fx_g3_body_hologram",
        "label": "Hologram",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 res = uTD2DInfos[0].res.zw;
    // Slight vertical wobble
    vec2 wobbleUV = uv + vec2(0.0, sin(uv.y * 30.0 + iTime * 5.0) * 0.003);
    vec4 src = texture(sTD2DInputs[0], wobbleUV);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Horizontal scan lines every 3px
    float scanLine = step(0.5, fract(uv.y * res.y / 3.0));
    float holoBody = bodyMask * scanLine * 0.5;
    vec3 bodyColor = vec3(0.0, 0.8, 1.0) * holoBody;
    // White edge glow
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], wobbleUV + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    vec3 edgeGlow = vec3(0.9, 1.0, 1.0) * edge * 1.5;
    vec3 result = bodyColor + edgeGlow;
    result *= 1.0 + energy * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 27: Blueprint ──
    {
        "name": "fx_g3_body_blueprint",
        "label": "Blueprint",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec2 res = uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Dark blue background
    vec3 bg = vec3(0.02, 0.04, 0.15);
    // Faint blue grid pattern on body
    float gridSpacing = 20.0; // pixels
    float gridX = smoothstep(0.4, 0.5, abs(fract(uv.x * res.x / gridSpacing) - 0.5) * 2.0);
    float gridY = smoothstep(0.4, 0.5, abs(fract(uv.y * res.y / gridSpacing) - 0.5) * 2.0);
    float grid = 1.0 - max(gridX, gridY);
    vec3 bodyGrid = vec3(0.1, 0.2, 0.5) * grid * bodyMask * 0.4;
    // White Sobel edges on top
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    vec3 result = bg * (1.0 - bodyMask) + bodyGrid + vec3(0.8, 0.9, 1.0) * edge * 1.5;
    result *= 1.0 + energy * 0.2;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 28: Shadow Play ──
    {
        "name": "fx_g3_body_shadow_play",
        "label": "Shadow Play",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.12, 0.2, luma);
    // Warm amber/orange gradient background
    vec3 bgTop = vec3(0.9, 0.6, 0.2);
    vec3 bgBottom = vec3(0.8, 0.35, 0.05);
    vec3 bg = mix(bgBottom, bgTop, uv.y);
    // Slight warm flicker from audio
    bg *= 0.9 + energy * 0.2;
    // Solid black body silhouette (shadow puppet)
    vec3 body = vec3(0.0);
    vec3 result = mix(bg, body, bodyMask);
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 29: Particle Edge ──
    {
        "name": "fx_g3_body_particle_edge",
        "label": "Particle Edge",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel).rgb,
                         vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Scatter bright dots along edges
    float particleHash = hash(floor(uv * 100.0) + vec2(floor(iTime * 8.0)));
    float particle = step(0.88, particleHash);
    float sparkle = edge * particle;
    // Slight color variation per particle
    vec3 particleColor = 0.5 + 0.5 * cos(6.2832 * (particleHash + vec3(0.0, 0.15, 0.3)));
    vec3 result = particleColor * sparkle * 3.0;
    result *= 1.0 + beat * 0.5;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 30: Aura Glow ──
    {
        "name": "fx_g3_body_aura_glow",
        "label": "Aura Glow",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Multi-sample blur for soft glow extending beyond body
    float glow = 0.0;
    float glowRadius = 12.0 + energy * 8.0;
    for (int i = 0; i < 12; i++) {
        float angle = float(i) * 0.5236; // PI/6
        vec2 off = vec2(cos(angle), sin(angle)) * texel * glowRadius;
        float s = dot(texture(sTD2DInputs[0], uv + off).rgb, vec3(0.299, 0.587, 0.114));
        glow += smoothstep(0.1, 0.25, s);
    }
    glow /= 12.0;
    // Aura color cycles with time
    float hue = fract(iTime * 0.15);
    vec3 auraColor = 0.5 + 0.5 * cos(6.2832 * (hue + vec3(0.0, 0.33, 0.67)));
    // Aura visible outside body (glow - bodyMask), body shows original
    float auraOnly = clamp(glow - bodyMask * 0.5, 0.0, 1.0);
    vec3 aura = auraColor * auraOnly * 1.5;
    vec3 body = src.rgb * bodyMask;
    vec3 result = body + aura;
    result *= 1.0 + beat * 0.3;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 31: Comic Contour ──
    {
        "name": "fx_g3_body_comic_contour",
        "label": "Comic Contour",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    vec4 src = texture(sTD2DInputs[0], uv);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Posterize to 3 colors (shadows, midtones, highlights)
    float posterized;
    vec3 posterColor;
    if (luma < 0.33) {
        posterized = 0.15;
        posterColor = vec3(0.1, 0.05, 0.15); // dark shadow
    } else if (luma < 0.66) {
        posterized = 0.5;
        posterColor = vec3(0.4, 0.3, 0.5); // midtone
    } else {
        posterized = 0.85;
        posterColor = vec3(0.9, 0.85, 0.95); // highlight
    }
    // Thick black Sobel outlines
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], uv + vec2(float(x), float(y)) * texel * 1.5).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.06, 0.2, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Comic result: posterized body with black edges
    vec3 result = posterColor * bodyMask * (1.0 - edge);
    result *= 1.0 + energy * 0.2;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },

    # ── 32: Mirror Contour ──
    {
        "name": "fx_g3_body_mirror_contour",
        "label": "Mirror Contour",
        "shader": GLSL_HEADER + """
void main() {
    vec2 uv = vUV.st;
    vec2 texel = 1.0 / uTD2DInfos[0].res.zw;
    // Mirror: left half reflected to right
    vec2 mirrorUV = vec2(uv.x < 0.5 ? uv.x : 1.0 - uv.x, uv.y);
    vec4 src = texture(sTD2DInputs[0], mirrorUV);
    float luma = dot(src.rgb, vec3(0.299, 0.587, 0.114));
    float bodyMask = smoothstep(0.1, 0.25, luma);
    // Sobel edges on mirrored image
    float sobelX = 0.0, sobelY = 0.0;
    for (int x = -1; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            float s = dot(texture(sTD2DInputs[0], mirrorUV + vec2(float(x), float(y)) * texel).rgb, vec3(0.299, 0.587, 0.114));
            sobelX += s * float(x) * (y == 0 ? 2.0 : 1.0);
            sobelY += s * float(y) * (x == 0 ? 2.0 : 1.0);
        }
    }
    float edge = smoothstep(0.08, 0.3, sqrt(sobelX*sobelX + sobelY*sobelY));
    // Alternating hot pink / electric blue by vertical position
    float bandPhase = fract(uv.y * 8.0 + iTime * 0.5);
    vec3 edgeColor = bandPhase < 0.5 ? vec3(1.0, 0.1, 0.5) : vec3(0.1, 0.4, 1.0);
    vec3 neonEdge = edgeColor * edge * 2.0;
    // Dark body fill
    vec3 bodyFill = vec3(0.03) * bodyMask;
    vec3 result = neonEdge + bodyFill;
    result *= 1.0 + beat * 0.4;
    fragColor = TDOutputSwizzle(vec4(result, 1.0));
}
""",
    },
]

ALL_CONTOUR = CONTOUR_EFFECTS


# ─── BUILD FUNCTION ──────────────────────────────────────────────────────────

def build_effect(idx, effect, dry_run=False):
    """Build one Body Contour effect in TouchDesigner."""
    name = effect["name"]
    label = effect["label"]
    shader = effect["shader"]
    parent = "/project1"
    comp_path = f"{parent}/{name}"

    print(f"\n[{idx+1:2d}/33] Building {label} ({name})...")

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

    # Position below gen3 effects
    node_x = -400 + (idx % 7) * 170
    node_y = -2500 - (idx // 7) * 200
    td_exec(f"op('{comp_path}').nodeX = {node_x}; op('{comp_path}').nodeY = {node_y}")

    # 2. Create in1 (inTOP)
    td_create_op(comp_path, "inTOP", "in1")
    td_exec(f"op('{comp_path}/in1').nodeX = -300; op('{comp_path}/in1').nodeY = 0")

    # 3. Create GLSL TOP
    glsl_name = "glsl_" + name.replace("fx_g3_body_", "body_")
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
    parser = argparse.ArgumentParser(description="Build 33 Body Contour effects in TouchDesigner")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--effect", type=int, default=-1, help="Build only effect N (0-indexed)")
    args = parser.parse_args()

    print("=" * 60)
    print("YOUSUKE Body Contour Effect Builder")
    print(f"Building 33 body contour effects via twozero MCP")
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
        if args.effect < len(ALL_CONTOUR):
            if build_effect(args.effect, ALL_CONTOUR[args.effect], args.dry_run):
                built += 1
        else:
            print(f"Effect index {args.effect} out of range (0-{len(ALL_CONTOUR)-1})")
    else:
        for idx, effect in enumerate(ALL_CONTOUR):
            try:
                if build_effect(idx, effect, args.dry_run):
                    built += 1
            except Exception as e:
                print(f"  FAILED: {e}")

    print(f"\n{'=' * 60}")
    print(f"Built {built}/{len(ALL_CONTOUR)} Body Contour effects")
    print("=" * 60)


if __name__ == "__main__":
    main()
