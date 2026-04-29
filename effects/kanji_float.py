"""Effect 8: Kanji Float — CJK characters drift upward on sub-bass."""
import os
import random
from typing import Optional

import cv2
import numpy as np

EFFECT_META = {
    "name":        "Kanji Float",
    "description": "CJK glyphs drift upward in red/gold; spawn rate + speed driven by sub-bass",
    "key_audio":   ["sub_bass", "beat"],
    "tags":        ["kanji", "cjk", "text", "atmospheric", "sub_bass"],
    "order":       8,
}

try:
    from PIL import Image, ImageDraw, ImageFont as PILFont
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

_KANJI_LIST   = list("電音波光火夢狂神血宇虚空界霊")
_KANJI_COLORS = [(0, 0, 200), (0, 140, 255), (0, 50, 255)]   # BGR: red/gold


def _load_kanji_font() -> Optional[str]:
    """Find a CJK-capable font file on the system."""
    candidates = [
        # macOS
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/Library/Fonts/Osaka.ttf",
        # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        # Windows
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def fx_function(frame: np.ndarray, af, state: dict) -> np.ndarray:
    """Effect 8: Kanji Float — CJK characters drift upward on sub-bass."""
    H, W = frame.shape[:2]

    if "floats" not in state:
        state["floats"] = []
        state["font"]   = _load_kanji_font()

    floats = state["floats"]
    font   = state["font"]

    # Spawn on sub-bass
    if af.sub_bass > 0.35:
        n_spawn = int(af.sub_bass * 3)
        for _ in range(n_spawn):
            floats.append({
                "char":    random.choice(_KANJI_LIST),
                "x":       random.randint(30, W - 60),
                "y":       float(H + 20),
                "vy":      -(1.5 + af.sub_bass * 5),
                "opacity": 1.0,
                "decay":   random.uniform(0.004, 0.01),
                "size":    random.randint(28, 80),
                "color":   random.choice(_KANJI_COLORS),
            })

    canvas = (frame.astype(np.float32) * 0.5).astype(np.uint8)

    if _HAS_PIL and font:
        img_pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        draw    = ImageDraw.Draw(img_pil, "RGBA")

        alive = []
        for k in floats:
            beat_pulse = 0.7 + 0.3 * (1.0 if af.beat else 0.0)
            alpha = int(255 * k["opacity"] * beat_pulse)
            if alpha > 0:
                try:
                    try:
                        f = PILFont.truetype(font, k["size"])
                    except Exception:
                        f = PILFont.load_default()
                    r, g, b = k["color"][2], k["color"][1], k["color"][0]  # BGR→RGB
                    draw.text((k["x"], int(k["y"])), k["char"],
                              font=f, fill=(r, g, b, alpha))
                except Exception:
                    pass
            k["y"]       += k["vy"]
            k["opacity"] -= k["decay"]
            if k["opacity"] > 0:
                alive.append(k)

        state["floats"] = alive[-100:]
        canvas = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    else:
        alive = []
        for k in floats:
            alpha = k["opacity"]
            c = tuple(int(ch * alpha) for ch in k["color"])
            cv2.putText(canvas, k["char"],
                        (int(k["x"]), int(k["y"])),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        k["size"] / 30.0, c, 2, cv2.LINE_AA)
            k["y"]       += k["vy"]
            k["opacity"] -= k["decay"]
            if k["opacity"] > 0:
                alive.append(k)
        state["floats"] = alive[-100:]

    return canvas
