"""
Canonical Effect #2 — Crushed-Black Silhouette Bloom

Low-light variant of #1. Cluster 32 @ 93s is the reference.
~290 sampled frames matched this supertype (~15% of set).

What makes it distinct from chiaroscuro_magenta:
  - Much darker base — figure emerges from near-total-black
  - Much LESS of the frame is highlighted (thin rim of glow only)
  - Highlight is warm magenta-red, not hot pink
  - NO motion blur carry-over (dark frames don't ghost well)
  - Specular pops from highlight sources (LEDs, mixer screens) are sharper

Audio reactivity:
  rim_threshold   ← 1 - energy      quieter = higher threshold = figure disappears
  figure_lift     ← kick            kick momentarily brightens the silhouette
  bloom_spread    ← sub_bass        sub-bass expands the halation radius
  red_shift       ← bass            bass warms the tint toward red
"""

import cv2
import math
import numpy as np

EFFECT_META = {
    "name":        "Crushed Silhouette",
    "description": "Figure emerges from near-total black with warm magenta-red rim bloom",
    "key_audio":   ["energy", "sub_bass", "bass", "kick"],
    "tags":        ["canonical", "chiaroscuro", "silhouette", "crushed_black", "bloom"],
    "order":       -2,   # second in canonical rotation
}


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    H, W = frame.shape[:2]

    energy = float(getattr(af, "energy", 0.0))
    sub    = float(getattr(af, "sub_bass", 0.0))
    bass   = float(getattr(af, "bass", 0.0))
    kick   = float(getattr(af, "kick", 0.0))

    f = frame.astype(np.float32) / 255.0
    luma = 0.114 * f[..., 0] + 0.587 * f[..., 1] + 0.299 * f[..., 2]

    # ── 1. Aggressive highlight threshold — only the BRIGHTEST pixels glow ─
    # Dynamic threshold: high when quiet, lower on kicks (figure comes out)
    thresh = 0.55 + (1.0 - energy) * 0.15 - kick * 0.25
    thresh = max(0.30, min(0.85, thresh))
    # Smoothstep above threshold
    span = 0.15
    t = np.clip((luma - thresh) / span, 0.0, 1.0)
    hl_mask = (t * t * (3.0 - 2.0 * t)).astype(np.float32)

    # ── 2. Warm magenta-red tint (bass-shifted) ───────────────────────────
    # Base: B=0.50, G=0.20, R=1.00. bass pushes B down, mids would push G up.
    tint = np.array([
        0.55 - bass * 0.35,   # B (less blue = warmer)
        0.22 - bass * 0.08,   # G
        1.00,                 # R
    ], dtype=np.float32)
    # Mild desaturation so it doesn't read as a flat filter
    tint = tint * 0.75 + 0.25

    hl_intensity = (hl_mask * (0.5 + 0.5 * luma))[..., None]
    hl_rgb = hl_intensity * tint[None, None, :]

    # ── 3. Wide halation (big sigma, dominant weight) ─────────────────────
    wide_sigma = 28.0 + sub * 25.0                               # 28..53
    wide_k = int(wide_sigma * 2) | 1
    wide_k = min(wide_k, 121)
    wide_u8 = np.clip(hl_rgb * 255.0, 0, 255).astype(np.uint8)
    halation = cv2.GaussianBlur(wide_u8, (wide_k, wide_k), wide_sigma).astype(np.float32) / 255.0

    # Sharper specular for LED/screen highlights
    narrow_sigma = 4.0 + kick * 6.0
    narrow_k = int(narrow_sigma * 2) | 1
    narrow_k = min(narrow_k, 41)
    specular = cv2.GaussianBlur(wide_u8, (narrow_k, narrow_k), narrow_sigma).astype(np.float32) / 255.0

    # ── 4. Base layer — CRUSHED but preserve bright midtones (subject pop) ─
    # Target shows a brightly-lit subject emerging from black. We need to let
    # the source push through when there IS a bright subject — use a two-slope
    # curve: crush shadows hard, but let values above ~0.4 pass through.
    shadow_crush = np.power(np.clip(f, 0.0, 0.4) / 0.4, 2.4) * 0.4 * 0.25
    bright_pass = np.clip(f - 0.4, 0.0, 0.6) / 0.6 * 0.7   # linear for brights
    base = shadow_crush + bright_pass
    # Very faint warm tint in shadows from halation leak
    base = base + tint[None, None, :] * 0.015

    # ── 5. Composite with halation-dominant weighting ─────────────────────
    hal_weight = 2.2 + energy * 1.0
    spec_weight = 0.9 + kick * 0.8
    out = base + halation * hal_weight + specular * spec_weight

    # ── 6. Very subtle radial chromatic aberration ────────────────────────
    # This effect is darker so aberration would read as glitch-noise if strong.
    # Keep it to 1-3 px max, only at frame edges.
    aberr_strength = 0.8 + kick * 2.2
    if aberr_strength > 0.5:
        cx, cy = W * 0.5, H * 0.5
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        dx = xx - cx
        dy = yy - cy
        dist = np.sqrt(dx * dx + dy * dy)
        max_dist = math.sqrt(cx * cx + cy * cy)
        r_norm = (dist / max_dist).astype(np.float32)
        safe = np.maximum(dist, 1e-3)
        ux = dx / safe
        uy = dy / safe
        shift_mag = (r_norm ** 3) * aberr_strength          # cubic falloff, even softer
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

    # ── 7. Very subtle grain (less than plugin #1 — darker means more visible noise) ─
    rng = state.get("rng")
    if rng is None:
        rng = np.random.default_rng(0x51BEEF)
        state["rng"] = rng
    grain_amount = 0.010 + (1.0 - energy) * 0.012
    noise = rng.standard_normal((H, W, 1), dtype=np.float32) * grain_amount
    noise_tint = np.array([0.4, 0.3, 1.0], dtype=np.float32)[None, None, :]
    out = out + noise * noise_tint

    return np.clip(out * 255.0, 0, 255).astype(np.uint8)
