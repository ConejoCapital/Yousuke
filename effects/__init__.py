"""
¥ØUSUK€ Visual Extender — Effects Plugin Package

Plugin Contract
===============
Every .py file in this directory (and effects/ai_generated/) must export exactly two names:

    EFFECT_META = {
        "name":        str,          # Display name, e.g. "Neon Contour"
        "description": str,          # One-line description
        "key_audio":   list[str],    # e.g. ["bass", "onset"]
        "tags":        list[str],    # e.g. ["edges", "neon", "colormap"]
        "order":       int,          # 1-8 for built-ins, 99 for AI-generated
    }

    def fx_function(frame: np.ndarray, af: AudioFeatures, state: dict) -> np.ndarray:
        \"\"\"
        Args:
            frame: BGR uint8 frame, shape (H, W, 3)
            af:    AudioFeatures instance with attributes:
                     energy, bass, mids, highs, sub_bass  — float 0-1
                     beat, onset                           — bool
                     onset_energy, kick                    — float 0-1
            state: mutable dict persisted across frames for this effect
        Returns:
            BGR uint8 frame, same shape as input
        \"\"\"
        ...

Loading order
=============
The plugin loader in standalone/visuals.py loads built-in effects sorted by
EFFECT_META["order"], then loads ai_generated/ effects after.

Files starting with "_" or named "__init__.py" are skipped.
"""
