# Canonical Effects — Vision-Verified Catalog
## Source: ¥ØUSUK€ ¥UK1MAT$U — Boiler Room Tokyo × Super Dommune (93.5 min)

**Analysis date:** 2026-04-28
**Method:** Download 720p25 → k-means(k=40, 19-feature, 3s interval) on 1,871 frames → supertype dedup → vision audit of representative frames → manual canonical consolidation

**Key finding:** The original hand-guessed 8-effect catalog (Neon Contour, Particle Confetti, Voxel Explosion, Volumetric Rings, Shard Burst, Gold Particle Rain, Film Grain, Kanji Float) is substantially wrong. The actual ¥ØUSUK€ visual grammar is **not** sharp-edge GLSL TRON-cyberpunk. It is a chiaroscuro-bloom-chromatic-motion-blur aesthetic with narrow palettes and soft, indistinct light-boundary edges — NOT traced contour outlines. K-means `edge_density: high` was detecting light/dark contrast boundaries, not edges.

**Logo note:** Every cluster frame has `BOILER ROOM` (bottom-left, white circle) and `¥ØU$UK€ ¥UK1MAT$U` leetspeak text (bottom-right) burned into the broadcast. These are NOT part of the artistic effect vocabulary and must be ignored when translating to fx_function plugins.

---

## Canonical effect set (7 distinct techniques)

### 1. Chiaroscuro magenta bloom  [dominant — ~45% of set]
- Crushed blacks, blown-out highlights, heavy bloom/diffusion
- Subtle red/blue chromatic aberration (RGB fringe) at luminance edges
- Motion blur / slow-shutter ghosting on moving subjects
- Digital noise / organic grain overlay
- Palette: deep magenta + hot pink + pure white + near-total black
- Rep cluster: 13 (size=63, t=252s), 30, 27, 31, 38, 39, 6, 8, 15
- Audio mapping: `bloom_radius ← energy`, `aberration_strength ← onset_energy`, `motion_blur_frames ← 1 + bass*4`, `hue_shift 0..15° ← mids`
- Cluster total reach: ~700 frames (37% of samples)

### 2. Chiaroscuro cyan/cool bloom  [variant]
- Same technique as #1 but cool palette (cyan/white highlights, deep blue shadows)
- Skin reads flesh/pink; equipment reads cyan
- Rep cluster: 21 (size=74, t=18s), 5, 14, 34
- Audio mapping: `bloom_radius ← energy`, `temperature -30..0 K ← sub_bass`, `cyan_dominance 0..1 ← highs`
- Cluster total reach: ~226 frames

### 3. Very-dark crushed-black silhouette  [low-light variant]
- Extreme black point crush — figure barely emerges from pure black
- Highlights still bloomed (magenta or warm)
- Much more negative space than #1/#2
- Rep cluster: 32 (size=58, t=93s), 4, 19, 22, 16, 36
- Audio mapping: `black_point_lift ← -1 * energy` (darker at silence, figure emerges on kick)
- Cluster total reach: ~290 frames

### 4. Hazy low-contrast dream haze  [subdued variant]
- Raised blacks, reduced saturation, uniform fog overlay
- Dusty rose / desaturated flesh-pink palette
- Soft bokeh from lighting rigs visible top-right
- Unlike #1 which is high-contrast, this is low-contrast but same bloom DNA
- Rep cluster: 23 (size=26, t=57s), 33
- Audio mapping: `haze_opacity 0.3..0.8 ← 1 - energy` (haziest on quiet sections)
- Cluster total reach: ~64 frames

### 5. Dark atmospheric B-roll / macro  [compositional variant]
- Shallow DoF macro shot of equipment, bottles, hands, knobs
- Chiaroscuro lighting but through heavy bloom/diffusion (NOT sharp)
- Mixer screen / button LEDs as blown-out pink or green light sources
- Red/orange filled shadows (not pure black)
- Rep cluster: 17 (size=55, t=3s), 0
- Audio mapping: `macro_zoom 1.0..1.4 ← energy`, `bokeh_size ← mids`
- Cluster total reach: ~66 frames

### 6. Pixel-sort / radial shard burst  [true shard effect — correct version]
- Radial pixel extrusion in crystalline/needle shards from bright center
- Centrifugal motion, temporal smearing
- Magenta/pink dominant with pure white core, hints of cobalt blue
- Bokeh/particle overlay adds atmospheric noise
- Rep cluster: 20 (size=33, t=1113s)
- Audio mapping: `shard_length ← onset_energy`, `radial_velocity ← kick`, `particle_density ← highs`
- Cluster total reach: ~64 frames
- Note: This REPLACES the old voronoi `shard_burst.py` which was geometrically wrong

### 7. Feedback echo / recursive tunnel  [temporal effect]
- Previous frames scaled+offset and recomposited = "hall of mirrors" tunnel
- Silhouette repeated in concentric rings receding into frame
- Sparkle/bokeh overlay (digital dust)
- Luma-key isolates highlights → tints pink/red, kills midtones
- Rep cluster: 35 (size=35, t=147s), 9
- Audio mapping: `feedback_gain 0.85..0.97 ← sub_bass`, `zoom_step_per_frame 0.98..1.04 ← beat`, `highlight_tint_hue ← mids`
- Cluster total reach: ~136 frames
- Note: This REPLACES old `volumetric_rings.py` concept — the "rings" were actually feedback echoes, not drawn circles

---

## Effects to DELETE from the existing catalog

> **Implementation note:** The 8 original hand-coded Python effects remain
> in `effects/` for the Python standalone engine. The canonical analysis
> informed the GLSL shader generation phase, which produced 43 shaders
> (21 originals + 21 mutations + 1 canon) that reflect the actual visual
> grammar. The TouchDesigner production system uses the corrected effects;
> the Python standalone retains the originals alongside 21 AI-generated
> and 2 canonical plugins.

These do not exist in the reference video and should be removed or flagged as non-canonical:
- `kanji_float.py` — no kanji overlays present in ANY sampled frame. Text present is only the ¥ØUSUK€ leetspeak broadcast watermark.
- `gold_particle_rain.py` — no gold-rain effect found; gold/amber color temperature appears only in dark-atmospheric B-roll as LED reflections, not as particles.
- `voxel_explosion.py` — no pixelated grid look found anywhere.
- `film_grain.py` — grain is present as *texture layer* on the chiaroscuro bloom effects, not as a standalone look.
- `particle_confetti.py` — no confetti-style particle spawning found. Silhouette-based particles don't appear in the set.
- `volumetric_rings.py` — rings are actually feedback trails (#7 above), not drawn concentric shapes.
- `neon_contour.py` — the set does NOT use Canny/Sobel edge tracing. What we see is high-contrast chiaroscuro (#1/#2).
- `shard_burst.py` — voronoi cell fracture is not present. The actual shard effect is pixel-sort radial extrusion (#6).

Net: **7 of 8 existing effects should be deprecated**, only rough `film_grain.py` might survive as a texture sub-layer inside the new effects.

---

## Generation strategy

Generate 7 plugins in this order (most → least common):
1. `chiaroscuro_magenta.py` (from cluster 13)
2. `crushed_black_silhouette.py` (from cluster 32)
3. `chiaroscuro_cyan.py` (from cluster 21)
4. `dark_atmospheric_macro.py` (from cluster 17)
5. `feedback_echo_tunnel.py` (from cluster 35)
6. `pixel_sort_shards.py` (from cluster 20)
7. `hazy_dream_fog.py` (from cluster 23)

Each plugin will be generated via `generate_effect.py --from-canonical` with the patched code that now sends the representative frame image to Claude Opus 4.7 alongside the numeric signature.

After all 7 generate successfully, rebuild the TouchDesigner network and the standalone key-bindings to use the new catalog.
