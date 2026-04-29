"""
Canonical Effect #1 — Chiaroscuro Magenta Bloom  (v2, diffusion-forward)

Dominant visual in ¥ØUSUK€ Boiler Room Tokyo × Super Dommune (~45% of frames).
Cluster 13 @ 252s is the reference.

v1 was "crunchy digital glitch". Vision audit said target is "dreamy diffused glow"
— like a Pro-Mist filter, not a glitch filter. This v2 rewrites the stack:

  - Bloom is now the DOMINANT layer, not an additive on top
  - Black-point much gentler (lifted by bloom wrap, not crushed to zero)
  - Two-pass diffusion: wide soft halation + narrow specular glow
  - Motion blur is frame-accumulator with decay (persistent ghost trail)
  - Grain is subtle and magenta-tinted (not white TV noise)
  - Chromatic aberration is radial from centre + soft-masked to edges only

Audio reactivity:
  bloom_radius    ← energy            9..40 px sigma on wide halation
  halation_mix    ← 0.6 + energy*0.3  diffusion is always 60%+ of the output
  motion_decay    ← 0.70 + bass*0.18  bass = longer ghost trails
  aberration_px   ← 1 + onset*5       subtle, not digital-hard
  tint_warmth     ← mids vs sub       sub→red, mids→pink
  grain_amount    ← 0.015..0.035      always subtle
"""

import cv2
import math
import numpy as np

EFFECT_META = {
    "name":        "Chiaroscuro Magenta",
    "description": "Dreamy magenta Pro-Mist diffusion with halation wrap and motion ghost",
    "key_audio":   ["energy", "onset_energy", "bass", "mids", "sub_bass"],
    "tags":        ["canonical", "chiaroscuro", "bloom", "halation", "magenta", "diffusion"],
    "order":       -1,
}


def _magenta_tint(mids: float, sub: float) -> np.ndarray:
    """Return a per-channel multiplier (BGR) for the highlight tint.
    sub_bass pushes toward deep red; mids pushes toward hot pink."""
    # Base magenta: B=0.80 G=0.30 R=1.00
    b = 0.80 - sub * 0.55 + mids * 0.10
    g = 0.30 - sub * 0.20 + mids * 0.25
    r = 1.00 - sub * 0.02 + mids * 0.02
    return np.array([b, g, r], dtype=np.float32)


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]

    # Audio
    energy = float(getattr(af, "energy", 0.0))
    onset  = float(getattr(af, "onset_energy", 0.0))
    bass   = float(getattr(af, "bass", 0.0))
    mids   = float(getattr(af, "mids", 0.0))
    sub    = float(getattr(af, "sub_bass", 0.0))

    f = frame.astype(np.float32) / 255.0

    # ── 1. Highlight isolation (soft, not binary) ─────────────────────────
    # Use luma with a smooth shoulder — pixels above ~0.35 luma start
    # contributing to the highlight layer.
    luma = 0.114 * f[..., 0] + 0.587 * f[..., 1] + 0.299 * f[..., 2]
    # Smoothstep 0.30..0.95 → highlight weight 0..1
    t = np.clip((luma - 0.30) / 0.65, 0.0, 1.0)
    hl_mask = (t * t * (3.0 - 2.0 * t)).astype(np.float32)        # (H,W)

    # Tint the highlights magenta (apply multiplier to a white-ish source)
    tint = _magenta_tint(mids, sub)
    # De-saturate the tint slightly: mix 20% white into it so highlights
    # don't read as a flat magenta filter.
    tint = tint * 0.80 + 0.20
    # The highlight "source" is the highlight mask itself turned into a white field
    # modulated by the original luma (so brighter pixels still glow brighter).
    hl_intensity = (hl_mask * (0.4 + 0.6 * luma))[..., None]       # (H,W,1)
    hl_rgb = hl_intensity * tint[None, None, :]                    # tinted highlight

    # ── 2. Two-pass diffusion bloom ───────────────────────────────────────
    # Wide halation: huge blur that wraps light into shadow
    wide_sigma = 20.0 + energy * 35.0                              # 20..55
    wide_k = int(wide_sigma * 2) | 1
    wide_k = min(wide_k, 121)
    wide_u8 = np.clip(hl_rgb * 255.0, 0, 255).astype(np.uint8)
    halation = cv2.GaussianBlur(wide_u8, (wide_k, wide_k), wide_sigma).astype(np.float32) / 255.0

    # Narrow specular glow: tighter blur for sharp highlights
    narrow_sigma = 6.0 + energy * 10.0                             # 6..16
    narrow_k = int(narrow_sigma * 2) | 1
    narrow_k = min(narrow_k, 41)
    specular = cv2.GaussianBlur(wide_u8, (narrow_k, narrow_k), narrow_sigma).astype(np.float32) / 255.0

    # ── 3. Base layer — GENTLY darkened source with lifted blacks ─────────
    # Target has visible shadow detail, not a void. Keep more source through.
    base = np.power(f, 1.2)                                        # very mild contrast
    base *= 0.55                                                   # only mildly darkened
    # Faint magenta bleed in shadows (mostly from the halation pass anyway)
    shadow_tint = tint * 0.025
    base = base + shadow_tint[None, None, :]

    # ── 4. Composite: base + halation (dominant) + specular core ─────────
    # Halation is ADDITIVE and scaled up — it IS the look
    hal_weight = 1.6 + energy * 0.8                                # halation dominates
    spec_weight = 0.7 + onset * 0.6
    out = base + halation * hal_weight + specular * spec_weight

    # ── 5. Motion blur via frame accumulator ──────────────────────────────
    # Keep a decaying accumulator of previous outputs for temporal smear.
    decay = 0.70 + bass * 0.18                                     # 0.70..0.88
    prev = state.get("accum")
    if prev is None or prev.shape != out.shape:
        state["accum"] = out.copy()
    else:
        # Blend: output = current*(1-decay) + accum*decay  (ghost stays)
        out = out * (1.0 - decay * 0.55) + prev * (decay * 0.55)
        state["accum"] = out.copy()

    # ── 6. Radial chromatic aberration (subtle, soft-masked) ──────────────
    # Displacement grows with radius from centre, NOT a global shift.
    aberr_strength = 1.5 + onset * 4.5                             # 1.5..6 px at edges
    if aberr_strength > 0.5:
        cx, cy = W * 0.5, H * 0.5
        # Build R and B shift maps
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dx = xx - cx
        dy = yy - cy
        dist = np.sqrt(dx * dx + dy * dy)
        max_dist = math.sqrt(cx * cx + cy * cy)
        r_norm = (dist / max_dist).astype(np.float32)              # 0..1
        # Radial unit vector
        safe = np.maximum(dist, 1e-3)
        ux = dx / safe
        uy = dy / safe
        # R shifts OUTWARD, B shifts INWARD, magnitude ∝ r² (smooth toward edges)
        shift_mag = (r_norm * r_norm) * aberr_strength
        # Build remap grids
        map_R_x = (xx + ux * shift_mag).astype(np.float32)
        map_R_y = (yy + uy * shift_mag).astype(np.float32)
        map_B_x = (xx - ux * shift_mag).astype(np.float32)
        map_B_y = (yy - uy * shift_mag).astype(np.float32)
        out_u8 = np.clip(out * 255.0, 0, 255).astype(np.uint8)
        B, G, R = cv2.split(out_u8)
        R = cv2.remap(R, map_R_x, map_R_y, cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_REPLICATE)
        B = cv2.remap(B, map_B_x, map_B_y, cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_REPLICATE)
        out = cv2.merge([B, G, R]).astype(np.float32) / 255.0

    # ── 7. Subtle magenta-tinted grain ────────────────────────────────────
    rng = state.get("rng")
    if rng is None:
        rng = np.random.default_rng(0xC0FFEE)
        state["rng"] = rng
    grain_amount = 0.015 + (1.0 - energy) * 0.020                  # 0.015..0.035
    noise = rng.standard_normal((H, W, 1), dtype=np.float32) * grain_amount
    # Tint the noise: more red/pink than green, so it reads "film stock" not "TV static"
    noise_tint = np.array([0.6, 0.4, 1.0], dtype=np.float32)[None, None, :]
    out = out + noise * noise_tint

    # Final clip
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)
