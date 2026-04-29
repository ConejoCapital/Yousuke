#!/usr/bin/env python3
"""
¥ØUSUK€ Visual Extender — Canonical Effects Analyzer
Samples frames from the reference video, extracts visual features,
clusters them with k-means, and writes canonical_effects.json.

Usage:
    python analyze_video.py [--video PATH] [--interval N] [--clusters N] [--output PATH]

Defaults:
    --video     reference/video.mp4
    --interval  10   (seconds between sampled frames)
    --clusters  20
    --output    reference/canonical_effects.json
"""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# ── Optional deps ─────────────────────────────────────────────────────────────
try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False

    class tqdm:  # minimal stub
        def __init__(self, iterable=None, desc="", total=None, **kw):
            self._it = iter(iterable) if iterable is not None else None
            self._n  = 0
            self._total = total or (len(iterable) if iterable is not None else 0)
            print(f"{desc}...")
        def __iter__(self): return self
        def __next__(self):
            val = next(self._it)
            self._n += 1
            if self._n % max(1, self._total // 10) == 0:
                print(f"  {self._n}/{self._total}")
            return val
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def set_postfix_str(self, s): pass


N_FEATURES = 19  # 15 dominant color + 4 structural features


# ── Pre-flight checks ─────────────────────────────────────────────────────────

def preflight_check(video_path: Path, clusters: int) -> dict:
    errors    = []
    estimates = {}

    # Check sklearn
    if not HAS_SKLEARN:
        errors.append("scikit-learn not installed  →  pip install scikit-learn>=1.4.0")

    # Check video exists
    if not video_path.exists():
        errors.append(f"Video not found: {video_path}")
        return {"ok": False, "errors": errors, "estimates": estimates}

    # Read video metadata
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        errors.append(f"Cannot open video: {video_path}")
        cap.release()
        return {"ok": False, "errors": errors, "estimates": estimates}

    fps         = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration    = total_frames / fps
    cap.release()

    # Estimate n frames to sample
    n_sampled = max(1, int(duration / 10))  # using default interval=10; will be recomputed
    estimates["fps"]          = fps
    estimates["total_frames"] = total_frames
    estimates["duration_s"]   = duration
    estimates["duration_str"] = f"{int(duration//60)}m {int(duration%60)}s"

    # Disk space: ~50MB for frames
    free_bytes = shutil.disk_usage(video_path.parent).free
    if free_bytes < 50 * 1024 * 1024:
        errors.append(f"Low disk space: {free_bytes // 1024 // 1024} MB free (need ~50 MB)")

    return {"ok": len(errors) == 0, "errors": errors, "estimates": estimates}


def print_preflight(result: dict, video_path: Path, interval: int, clusters: int):
    est = result["estimates"]
    print("=== Pre-flight Check ===")
    print(f"  Video:       {video_path}")
    if "duration_str" in est:
        dur     = est["duration_s"]
        n_frames = max(1, int(dur / interval))
        print(f"  Duration:    {est['duration_str']}  ({est['total_frames']} frames @ {est['fps']:.1f} fps)")
        print(f"  Will sample: ~{n_frames} frames  (every {interval}s)")
        print(f"  Clusters:    {clusters}")
        print(f"  Est. sample: ~{n_frames * 0.02:.0f}s  |  features: ~{n_frames * 0.05:.0f}s  |  kmeans: ~{n_frames * 0.003:.0f}s")
    if result["errors"]:
        print("\n  ERRORS:")
        for e in result["errors"]:
            print(f"    ✗ {e}")
    else:
        print("  ✓ All checks passed")
    print()


# ── Feature extraction ────────────────────────────────────────────────────────

def extract_features(frame: np.ndarray) -> np.ndarray:
    """
    Extract 19-float feature vector from a BGR frame:
      [0:15]  dominant colors (k=5 kmeans on 64×64 resized, normalized 0-1 RGB)
      [15]    edge density (Canny nonzero / (64*64))
      [16]    overall brightness (mean gray / 255)
      [17]    saturation mean (HSV S / 255)
      [18]    color variance (std dev of pixels / 255)
    """
    small = cv2.resize(frame, (64, 64))
    pixels = small.reshape(-1, 3).astype(np.float32)

    # Dominant colors via k-means (k=5)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, _, centers = cv2.kmeans(pixels, 5, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
    # centers shape: (5, 3) BGR, normalize to 0-1
    dom_colors = (centers.flatten() / 255.0)[:15]

    # Edge density
    gray        = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    edges       = cv2.Canny(gray, 50, 150)
    edge_density = float(np.count_nonzero(edges)) / (64 * 64)

    # Brightness
    brightness = float(np.mean(gray)) / 255.0

    # Saturation
    hsv        = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    saturation = float(np.mean(hsv[:, :, 1])) / 255.0

    # Color variance
    color_var  = float(np.std(pixels)) / 255.0

    return np.array([*dom_colors, edge_density, brightness, saturation, color_var],
                    dtype=np.float32)


# ── Category inference ────────────────────────────────────────────────────────

def infer_category(visual_sig: dict) -> tuple:
    """
    Infer category name and audio mapping from visual signature heuristics.
    Returns (category_name: str, audio_mapping: str)
    """
    edge     = visual_sig["edge_density_raw"]
    bright   = visual_sig["brightness_raw"]
    sat      = visual_sig["saturation_raw"]
    variance = visual_sig["color_variance_raw"]

    high_edge   = edge     > 0.15
    dark        = bright   < 0.3
    colorful    = sat      > 0.3
    monochrome  = sat      < 0.15
    complex_    = variance > 0.3

    if high_edge and colorful and dark:
        return ("Neon Edge",            "edge_density → bass; hue → energy")
    if high_edge and dark and monochrome:
        return ("Monochrome Contour",   "edge_density → mids; brightness → energy")
    if bright > 0.6 and colorful and complex_:
        return ("High-Energy Color Burst", "variance → onset_energy; saturation → highs")
    if dark and not complex_ and colorful:
        return ("Dark Atmospheric",     "saturation → sub_bass; brightness → beat")
    if monochrome and dark:
        return ("Film Grain / Noise",   "brightness → energy; variance → grain_scale")
    if bright > 0.5 and not colorful:
        return ("Washed Out / Overexposed", "brightness → energy; edge → bass")
    if edge < 0.05 and colorful:
        return ("Smooth Color Flow",    "saturation → sub_bass; hue → mids")
    if high_edge and bright > 0.4:
        return ("Energetic Edge Burst", "edge_density → onset; brightness → energy")
    return ("Complex Scene",            "energy → overall; onset → burst")


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="¥ØUSUK€ Canonical Effects Analyzer"
    )
    parser.add_argument("--video",    default="reference/video.mp4",
                        help="Path to source video (default: reference/video.mp4)")
    parser.add_argument("--interval", type=int, default=10,
                        help="Seconds between sampled frames (default: 10)")
    parser.add_argument("--clusters", type=int, default=20,
                        help="Number of k-means clusters (default: 20)")
    parser.add_argument("--output",   default="reference/canonical_effects.json",
                        help="Output JSON path (default: reference/canonical_effects.json)")
    args = parser.parse_args()

    video_path  = Path(args.video)
    output_path = Path(args.output)
    frames_dir  = output_path.parent / "canonical_effects_frames"
    error_log_path = output_path.parent / "analyze_errors.json"

    # ── Pre-flight ──────────────────────────────────────────────────────────
    pf = preflight_check(video_path, args.clusters)
    print_preflight(pf, video_path, args.interval, args.clusters)
    if not pf["ok"]:
        print("Pre-flight failed. Aborting.")
        sys.exit(1)

    est      = pf["estimates"]
    fps      = est["fps"]
    duration = est["duration_s"]

    # ── Stage 1: Frame sampling ─────────────────────────────────────────────
    n_sampled_est = max(1, int(duration / args.interval))
    print(f"[1/5] Sampling frames (est. ~{n_sampled_est * 0.02:.0f}s for {est['duration_str']} video at {args.interval}s interval)...")

    cap          = cv2.VideoCapture(str(video_path))
    frame_data   = []   # list of (timestamp, frame)
    stage1_start = time.time()

    timestamps = [i * args.interval for i in range(int(duration / args.interval) + 1)
                  if i * args.interval < duration]

    with tqdm(timestamps, desc="Sampling", total=len(timestamps)) as pbar:
        for ts in pbar:
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ret, frame = cap.read()
            if ret and frame is not None:
                frame_data.append((ts, frame))
            pbar.set_postfix_str(f"{ts:.0f}s")

    cap.release()
    stage1_time = time.time() - stage1_start
    n_frames    = len(frame_data)
    print(f"  Sampled {n_frames} frames in {stage1_time:.1f}s\n")

    if n_frames == 0:
        print("ERROR: No frames sampled. Aborting.")
        sys.exit(1)

    # ── Stage 2: Feature extraction ─────────────────────────────────────────
    print(f"[2/5] Extracting features from {n_frames} frames (est. ~{n_frames * 0.05:.0f}s)...")
    features   = np.zeros((n_frames, N_FEATURES), dtype=np.float32)
    error_log  = []
    stage2_start = time.time()

    with tqdm(list(enumerate(frame_data)), desc="Features", total=n_frames) as pbar:
        for i, (ts, frame) in pbar:
            try:
                features[i] = extract_features(frame)
            except Exception as e:
                print(f"\n  WARNING: frame {i} (t={ts:.1f}s) failed: {e} — using zero vector")
                features[i] = np.zeros(N_FEATURES)
                error_log.append({"frame": i, "ts": ts, "error": str(e)})
            pbar.set_postfix_str(f"t={ts:.0f}s")

    stage2_time = time.time() - stage2_start
    print(f"  Features extracted in {stage2_time:.1f}s\n")

    if error_log:
        error_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(error_log_path, "w") as f:
            json.dump(error_log, f, indent=2)
        print(f"  Error log saved: {error_log_path}  ({len(error_log)} errors)")

    # ── Stage 3: K-means clustering ─────────────────────────────────────────
    n_clusters = min(args.clusters, n_frames)
    print(f"[3/5] K-means: fitting {n_frames} frames × {N_FEATURES} features (n_clusters={n_clusters})...")
    stage3_start = time.time()

    scaler        = StandardScaler()
    features_norm = scaler.fit_transform(features)

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(features_norm)

    stage3_time = time.time() - stage3_start
    print(f"  Clustering complete in {stage3_time:.1f}s\n")

    # Warn on small clusters
    for cid in range(km.n_clusters):
        size = int((labels == cid).sum())
        if size < 2:
            print(f"  WARNING: Cluster {cid} has only {size} frame(s) — "
                  f"consider reducing --clusters")

    # ── Stage 4: Find representative frames ─────────────────────────────────
    print(f"[4/5] Finding representative frames for {n_clusters} clusters...")
    representatives = {}  # cid → frame_index
    for cid in range(n_clusters):
        member_indices = np.where(labels == cid)[0]
        if len(member_indices) == 0:
            continue
        centroid = km.cluster_centers_[cid]
        dists    = np.linalg.norm(features_norm[member_indices] - centroid, axis=1)
        best_idx = member_indices[np.argmin(dists)]
        representatives[cid] = best_idx

    # ── Stage 5: Build catalog + save ───────────────────────────────────────
    print(f"[5/5] Building catalog and saving outputs...")
    stage5_start = time.time()
    frames_dir.mkdir(parents=True, exist_ok=True)

    catalog_effects = []
    for cid in range(n_clusters):
        rep_idx = representatives.get(cid)
        if rep_idx is None:
            continue

        rep_ts, rep_frame = frame_data[rep_idx]

        # Collect all timestamps in this cluster
        cluster_indices = np.where(labels == cid)[0]
        cluster_ts      = sorted([frame_data[i][0] for i in cluster_indices])

        # Visual signature from representative frame's features
        feat = features[rep_idx]
        # Dominant hex: use first dominant color (BGR → RGB → hex)
        bgr_dom = (feat[:3] * 255).astype(int)
        dom_hex = "#{:02x}{:02x}{:02x}".format(int(bgr_dom[2]), int(bgr_dom[1]), int(bgr_dom[0]))

        edge_raw   = float(feat[15])
        bright_raw = float(feat[16])
        sat_raw    = float(feat[17])
        var_raw    = float(feat[18])

        edge_label   = "high"   if edge_raw > 0.15  else ("medium" if edge_raw > 0.06 else "low")
        bright_label = "bright" if bright_raw > 0.6 else ("medium" if bright_raw > 0.3 else "dark")
        sat_label    = "colorful" if sat_raw > 0.3  else ("neutral" if sat_raw > 0.15 else "monochrome")

        visual_sig = {
            "dominant_hex":       dom_hex,
            "edge_density":       edge_label,
            "edge_density_raw":   round(edge_raw, 4),
            "brightness":         bright_label,
            "brightness_raw":     round(bright_raw, 4),
            "saturation":         sat_label,
            "saturation_raw":     round(sat_raw, 4),
            "color_variance_raw": round(var_raw, 4),
        }

        category, audio_map = infer_category(visual_sig)

        # Save representative frame
        frame_filename = f"cluster_{cid:02d}.jpg"
        frame_save_path = frames_dir / frame_filename
        cv2.imwrite(str(frame_save_path), rep_frame)

        catalog_effects.append({
            "id":                        cid,
            "name":                      f"{category} #{cid:02d}",
            "category":                  category,
            "timestamps":                [round(t, 1) for t in cluster_ts[:10]],  # first 10
            "representative_timestamp":  round(rep_ts, 1),
            "representative_frame_path": str(frames_dir / frame_filename),
            "visual_signature":          visual_sig,
            "inferred_audio_mapping":    audio_map,
            "cluster_size":              int(len(cluster_indices)),
        })

    # Sort by id
    catalog_effects.sort(key=lambda x: x["id"])

    catalog = {
        "source_video":      "https://youtu.be/CxflYGeSx7Q",
        "n_clusters":        n_clusters,
        "n_frames_sampled":  n_frames,
        "interval_seconds":  args.interval,
        "canonical_effects": catalog_effects,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)

    json_size_kb = output_path.stat().st_size / 1024
    frames_size  = sum(p.stat().st_size for p in frames_dir.glob("*.jpg"))
    frames_mb    = frames_size / 1024 / 1024
    stage5_time  = time.time() - stage5_start

    total_time = stage1_time + stage2_time + stage3_time + stage5_time

    print()
    print("=== Analysis Complete ===")
    print(f"  Video:         {video_path}  ({est['duration_str']}, {est['total_frames']} frames)")
    print(f"  Sampled:       {n_frames} frames (every {args.interval}s)")
    print(f"  Clusters:      {n_clusters}")
    print(f"  Errors:        {len(error_log)} frames failed feature extraction")
    print(f"  Stage times:   sampling={stage1_time:.1f}s  features={stage2_time:.1f}s  "
          f"kmeans={stage3_time:.1f}s  catalog={stage5_time:.1f}s")
    print(f"  Total time:    {total_time:.1f}s")
    print(f"  Output:        {output_path}  ({len(catalog_effects)} effects, {json_size_kb:.1f} KB)")
    print(f"  Frames saved:  {frames_dir}  ({len(catalog_effects)} JPEGs, {frames_mb:.1f} MB)")
    print()
    print(f"  Use with:  python generate_effect.py --from-canonical {output_path} --id 0")


if __name__ == "__main__":
    main()
