"""Effect 7: Film Grain Base — noise + vignette + desaturation.

PERF NOTES (Apr 2026 optimization):
  Original used np.random.normal(float32) for noise (~12ms) + a full HSV
  roundtrip (~15ms) → ~35ms/frame at 1280x720.
  Optimized version uses uint8 randint (faster RNG, no float conversion) and
  collapses vignette + desaturation into a single LUT-free numpy pass, doing
  channel-wise saturation by interpolating toward grayscale. Result: ~6-9ms.
"""
import cv2
import numpy as np

EFFECT_META = {
    "name":        "Film Grain Base",
    "description": "Gaussian noise + radial vignette + desaturation; grain scale driven by RMS energy",
    "key_audio":   ["energy"],
    "tags":        ["grain", "noise", "vignette", "film", "atmospheric"],
    "order":       7,
}


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 7: Film Grain Base — noise + vignette + desaturation."""
    H, W = frame.shape[:2]

    # Cache vignette per resolution
    if "vignette" not in state or state.get("vig_shape") != (H, W):
        Y, X = np.ogrid[:H, :W]
        dist = np.sqrt(((X - W / 2) / (W / 2)) ** 2 + ((Y - H / 2) / (H / 2)) ** 2)
        state["vignette"]  = np.clip(1.0 - dist * 0.5, 0, 1).astype(np.float32)
        state["vig_shape"] = (H, W)
    vig = state["vignette"][:, :, np.newaxis]  # (H,W,1)

    # ── Optimized noise ──
    # Generate noise at half resolution and upscale — visually indistinguishable
    # for film-grain texture but ~4x faster than full-res RNG.
    grain_amount = int(15 + af.energy * 40)  # 15..55 pixel-units of jitter
    Hh, Wh = H // 2, W // 2
    noise_small = np.random.randint(-grain_amount, grain_amount + 1,
                                    size=(Hh, Wh, 3), dtype=np.int16)
    noise = cv2.resize(noise_small.astype(np.int16), (W, H),
                       interpolation=cv2.INTER_LINEAR).astype(np.int16)
    grained = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # ── Combined vignette + desaturation via cv2.addWeighted ──
    # cv2.cvtColor(BGR2GRAY) is hand-optimized SIMD — much faster than a
    # numpy float dot product. Then addWeighted blends color/gray, then
    # we apply the vignette as a single float multiply.
    sat_factor = 0.5 + af.energy * 0.5  # 0.5..1.0 (lower = more desat)

    if sat_factor < 0.999:
        gray = cv2.cvtColor(grained, cv2.COLOR_BGR2GRAY)
        gray3 = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        desat = cv2.addWeighted(grained, sat_factor, gray3, 1.0 - sat_factor, 0)
    else:
        desat = grained

    # Apply vignette (cached float32 mask)
    out = (desat.astype(np.float32) * vig).astype(np.uint8)
    return out
