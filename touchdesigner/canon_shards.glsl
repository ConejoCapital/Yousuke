// Canonical #6 — Pixel-Sort Radial Shards (distinct from old voronoi shard_burst!)
// Radial pixel extrusion in crystalline/needle shards from bright center,
// centrifugal motion, temporal smearing, magenta+white+cobalt palette.
// uAudio=(time,rms,bass,sub_bass), uAudio2=(sub,mids,highs,beat)

uniform vec4 uAudio;
uniform vec4 uAudio2;
out vec4 fragColor;

float hash1(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void main() {
    vec2 uv = vUV.st;
    float t = uAudio.x;
    float energy = uAudio.y;
    float bass = uAudio.z;
    float sub = uAudio.w;
    float highs = uAudio2.z;
    float onset = max(0.0, (highs + bass * 0.5) - 0.3);

    // Find angle+radius from centre
    vec2 d = uv - 0.5;
    d.x *= 1.778; // aspect
    float r = length(d);
    float ang = atan(d.y, d.x);

    // Angular "columns": divide circle into N wedges
    float numWedges = 48.0 + energy * 48.0;
    float wedgeIdx = floor((ang + 3.14159) / (6.2832 / numWedges));
    float wedgeRnd = hash1(vec2(wedgeIdx, floor(t * 0.3 + sub * 3.0)));

    // Each wedge extrudes outward — sample along radius at a PULLED-BACK point
    // The farther from centre, the more we pull back (creating a "smeared" streak)
    float pullback = 0.05 + onset * 0.30 * wedgeRnd;
    float newR = max(0.0, r - pullback);
    // Convert back to uv
    float cosA = cos(ang), sinA = sin(ang);
    vec2 sampleUV = 0.5 + vec2(cosA, sinA / 1.778) * newR;
    sampleUV = clamp(sampleUV, 0.001, 0.999);

    // Sample camera at pulled-back point
    vec3 src = texture(sTD2DInputs[0], sampleUV).rgb;

    // Luminance-keyed: only BRIGHT pixels get the shard treatment
    float luma = dot(src, vec3(0.299, 0.587, 0.114));
    float bright = smoothstep(0.35, 0.85, luma);

    // Add centrifugal streak: blend with a smeared sample further back
    vec2 smearUV = 0.5 + vec2(cosA, sinA / 1.778) * max(0.0, newR - 0.04);
    smearUV = clamp(smearUV, 0.001, 0.999);
    vec3 smear = texture(sTD2DInputs[0], smearUV).rgb;
    src = mix(src, smear, bright * 0.5);

    // Palette: magenta + cobalt + white
    vec3 magenta = vec3(1.0, 0.25, 0.85);
    vec3 cobalt  = vec3(0.15, 0.25, 0.95);
    vec3 white   = vec3(1.0);
    float palMix = fract(wedgeRnd * 3.0);
    vec3 paletteCol = mix(mix(magenta, cobalt, smoothstep(0.3, 0.7, palMix)),
                          white, smoothstep(0.7, 1.0, palMix));

    // Output = dark base + bright rim tinted by palette, pushed outward
    vec3 base = src * 0.15;
    float rim = smoothstep(0.55, 0.95, luma);
    vec3 shard = paletteCol * rim * (1.5 + bass * 1.2);

    // Core white pop near centre
    float core = smoothstep(0.25, 0.0, r) * (0.4 + energy * 0.6);

    // Particle dust (hash noise)
    float dust = hash1(uv * 800.0 + t * 5.0);
    dust = smoothstep(0.995 - highs * 0.04, 1.0, dust);

    vec3 outC = base + shard + vec3(core) + dust * vec3(1.0, 0.9, 0.8);

    fragColor = TDOutputSwizzle(vec4(clamp(outC, 0.0, 2.0), 1.0));
}


[fps 60.0/60] [0 err/0 warn]