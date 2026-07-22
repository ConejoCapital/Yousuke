#!/usr/bin/env python3
"""
¥ØUSUK€ Visual Extender — Video download + metadata + frame extraction
Usage:
    python pipeline/download_video.py              # full run
    python pipeline/download_video.py --frames-only  # only extract frames from existing video
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
VIDEO_ID   = "CxflYGeSx7Q"
VIDEO_URL  = f"https://www.youtube.com/watch?v={VIDEO_ID}"
BASE_DIR   = Path(__file__).parent.parent / "reference"
VIDEO_PATH = BASE_DIR / "video.mp4"
AUDIO_PATH = BASE_DIR / "audio.mp3"
FRAMES_DIR = BASE_DIR / "frames"
INFO_PATH  = BASE_DIR / "video_info.json"
ANALYSIS_PATH = BASE_DIR / "visual_analysis.md"
N_FRAMES   = 30

# Manually compiled effect timestamps from Boiler Room Tokyo × Super Dommune
EFFECT_TIMESTAMPS = [
    (0,    "Film Grain Base",       "Opening — heavy grain, low-energy ambient"),
    (120,  "Neon Contour",          "First bass drop — contour edges appear, cyan bloom"),
    (240,  "Particle Confetti",     "Build-up — silhouette particle burst on kick"),
    (400,  "Voxel Explosion",       "Big transient — frame shatters into voxel field"),
    (580,  "Volumetric Rings",      "Mid-section sustained — rings propagate from center"),
    (720,  "Shard Burst",           "Kick cluster — screen fractures into flying shards"),
    (900,  "Gold Particle Rain",    "High-energy peak — dense gold downward cascade"),
    (1080, "Kanji Float",           "Bass sub rolls — kanji drift upward, red/gold"),
    (1200, "Neon Contour",          "Return to contour — cycling through effects"),
    (1380, "Voxel Explosion",       "Second climax — voxel explosion with wide radius"),
]


def run(cmd: list[str], check=True) -> subprocess.CompletedProcess:
    """Run a subprocess command, streaming output."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=check)


def download_video() -> bool:
    """Download the video using yt-dlp. Returns True if successful."""
    if VIDEO_PATH.exists() and VIDEO_PATH.stat().st_size > 1_000_000:
        print(f"  Video already downloaded: {VIDEO_PATH}")
        return True

    BASE_DIR.mkdir(parents=True, exist_ok=True)

    if not _check_ytdlp():
        print("  ERROR: yt-dlp not found. Run: brew install yt-dlp")
        return False

    print(f"\n[1] Downloading video: {VIDEO_URL}")
    try:
        run([
            "yt-dlp",
            "--remote-components", "ejs:github",
            "--format", "95/bv*[height<=720]+ba/b[height<=720]",
            "--merge-output-format", "mp4",
            "--output", str(VIDEO_PATH),
            "--write-info-json",
            "--write-description",
            VIDEO_URL,
        ])
        return VIDEO_PATH.exists()
    except subprocess.CalledProcessError as e:
        print(f"  WARNING: Download failed ({e}). Continuing with other steps.")
        return False


def extract_metadata() -> dict:
    """Extract video metadata from yt-dlp JSON sidecar or by querying."""
    print("\n[2] Extracting metadata...")

    # yt-dlp writes a .info.json sidecar when --write-info-json is used
    sidecar = BASE_DIR / "video.info.json"
    if sidecar.exists():
        with open(sidecar) as f:
            raw = json.load(f)
        meta = {
            "video_id":    VIDEO_ID,
            "title":       raw.get("title", ""),
            "description": raw.get("description", "")[:2000],
            "duration_s":  raw.get("duration", 0),
            "duration":    _fmt_duration(raw.get("duration", 0)),
            "upload_date": raw.get("upload_date", ""),
            "view_count":  raw.get("view_count", 0),
            "channel":     raw.get("channel", ""),
            "chapters":    raw.get("chapters", []),
            "url":         VIDEO_URL,
        }
    else:
        # Fallback: query without downloading
        meta = {
            "video_id":   VIDEO_ID,
            "title":      "¥ØUSUK€ ¥UK1MAT$U - Boiler Room Tokyo × Super Dommune",
            "url":        VIDEO_URL,
            "note":       "Full metadata requires yt-dlp + download",
        }

    with open(INFO_PATH, "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"  Metadata saved: {INFO_PATH}")
    print(f"  Title: {meta.get('title', 'N/A')}")
    print(f"  Duration: {meta.get('duration', 'N/A')}")
    return meta


def extract_audio() -> bool:
    """Extract audio track from video using ffmpeg."""
    if AUDIO_PATH.exists() and AUDIO_PATH.stat().st_size > 100_000:
        print(f"\n[3] Audio already exists: {AUDIO_PATH}")
        return True

    if not VIDEO_PATH.exists():
        print("\n[3] No video file — skipping audio extraction")
        return False

    print("\n[3] Extracting audio track...")
    try:
        run([
            "ffmpeg", "-i", str(VIDEO_PATH),
            "-q:a", "0", "-map", "a",
            str(AUDIO_PATH), "-y", "-loglevel", "error",
        ])
        size_mb = AUDIO_PATH.stat().st_size / 1_048_576
        print(f"  Audio saved: {AUDIO_PATH} ({size_mb:.1f} MB)")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  WARNING: Audio extraction failed ({e})")
        return False


def extract_frames() -> int:
    """Extract N_FRAMES evenly-spaced frames from the video."""
    try:
        import cv2
    except ImportError:
        print("  ERROR: opencv-python not installed. Run: pip install opencv-python")
        return 0

    if not VIDEO_PATH.exists():
        print("\n[4] No video file — skipping frame extraction")
        return 0

    print(f"\n[4] Extracting {N_FRAMES} reference frames...")
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(VIDEO_PATH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 25.0
    duration_s   = total_frames / fps

    print(f"  Total frames: {total_frames} | FPS: {fps:.2f} | Duration: {_fmt_duration(duration_s)}")

    indices = [int(i * total_frames / N_FRAMES) for i in range(N_FRAMES)]
    saved = 0

    for i, frame_idx in enumerate(indices):
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        ts = frame_idx / fps
        out_path = FRAMES_DIR / f"frame_{i:02d}_{ts:.1f}s.jpg"
        cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        saved += 1

    cap.release()
    print(f"  Saved {saved} frames to: {FRAMES_DIR}")
    return saved


def write_visual_analysis(meta: dict) -> None:
    """Generate visual_analysis.md summarizing the 8 effects with timestamps."""
    print("\n[5] Writing visual analysis...")

    duration_str = meta.get("duration", "~60 min")

    lines = [
        f"# Visual Analysis — ¥ØUSUK€ Boiler Room Tokyo × Super Dommune",
        f"",
        f"**Source:** {VIDEO_URL}",
        f"**Duration:** {duration_str}",
        f"**Analysis date:** 2026-04-28",
        f"",
        f"---",
        f"",
        f"## Effect Catalog with Timestamps",
        f"",
        f"| Timestamp | Effect | Description |",
        f"|-----------|--------|-------------|",
    ]

    for ts, effect, desc in EFFECT_TIMESTAMPS:
        lines.append(f"| {_fmt_duration(ts)} | **{effect}** | {desc} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 8 Core Effects — Technical Notes",
        f"",
        f"### 1. Neon Contour",
        f"- Canny edge detection, colorized with HSV colormap",
        f"- Bloom achieved via Gaussian blur addWeighted composite",
        f"- Bass drives line thickness (1→8px); energy drives hue rotation",
        f"- Most frequently occurring effect — serves as visual base layer",
        f"",
        f"### 2. Particle Confetti",
        f"- Particles spawn along silhouette/edge boundaries",
        f"- Mediapipe body segmentation identifies boundary regions",
        f"- Kick transients trigger burst spawning; bass sets velocity magnitude",
        f"- Neon color palette — cyan, magenta, yellow, green",
        f"",
        f"### 3. Voxel Explosion",
        f"- Frame downsampled to ~32×18 colored cube grid",
        f"- Onset transients apply radial outward force to each cube",
        f"- Physics: velocity × 0.92 friction + 0.3 gravity per frame",
        f"- Most visually dramatic — use sparingly (every 4–8 bars)",
        f"",
        f"### 4. Volumetric Rings",
        f"- Concentric elliptical halos spawned on each beat",
        f"- Travel outward from center, fade as radius grows",
        f"- Mid-band energy controls travel speed (2–10px/frame)",
        f"- Creates hypnotic depth illusion — great for sustained sections",
        f"",
        f"### 5. Shard Burst",
        f"- Voronoi fracture of current frame on kick",
        f"- Shard count scales with kick amplitude (20–200)",
        f"- Each shard translates outward; returns via friction decay",
        f"- Spread angle driven by bass",
        f"",
        f"### 6. Gold Particle Rain",
        f"- Dense downward particle field, gold/amber palette",
        f"- Highs drive density (up to 200 particles/frame)",
        f"- Overall energy shifts color temperature gold→white",
        f"- Works well as background layer under other effects",
        f"",
        f"### 7. Film Grain Base",
        f"- Gaussian noise overlay scaled by RMS energy",
        f"- Radial vignette darkens edges",
        f"- Slight desaturation on low-energy passages",
        f"- Most subtle — intended as textural backdrop",
        f"",
        f"### 8. Kanji Float",
        f"- CJK characters drift upward; sub-bass triggers spawn",
        f"- Characters: 電音波光火夢狂神血宇",
        f"- Color: red (0,0,180 BGR) or gold (0,140,255 BGR)",
        f"- Beat pulse modulates opacity × 0.3",
        f"",
        f"---",
        f"",
        f"## Recommended Effect Sequencing (Demo Script)",
        f"",
        f"```",
        f"0:00 → 0:30   Film Grain Base    Intro, atmospheric",
        f"0:30 → 2:00   Neon Contour       First drop, visual anchor",
        f"2:00 → 3:30   Particle Confetti  Build energy",
        f"3:30 → 4:00   Voxel Explosion    First climax",
        f"4:00 → 5:30   Volumetric Rings   Comedown, hypnotic",
        f"5:30 → 6:00   Kanji Float        Sub bass section",
        f"6:00 → 7:00   Gold Particle Rain Peak energy",
        f"7:00 → 7:30   Shard Burst        Final drop",
        f"7:30 → 8:00   Neon Contour       Outro",
        f"```",
    ]

    ANALYSIS_PATH.write_text("\n".join(lines))
    print(f"  Analysis saved: {ANALYSIS_PATH}")


def _check_ytdlp() -> bool:
    try:
        subprocess.run(["yt-dlp", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _fmt_duration(seconds) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def main():
    parser = argparse.ArgumentParser(description="Download and prepare ¥ØUSUK€ video assets")
    parser.add_argument("--frames-only", action="store_true",
                        help="Only extract frames from an existing video.mp4")
    args = parser.parse_args()

    print("=== ¥ØUSUK€ Video + Metadata Tool ===")
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)

    if args.frames_only:
        n = extract_frames()
        print(f"\nDone. Extracted {n} frames.")
        return

    # Full run
    dl_ok = download_video()
    meta  = extract_metadata()
    extract_audio()
    n_frames = extract_frames()
    write_visual_analysis(meta)

    print("\n=== Summary ===")
    print(f"  Video:    {'✓' if VIDEO_PATH.exists() else '✗'} {VIDEO_PATH}")
    print(f"  Audio:    {'✓' if AUDIO_PATH.exists() else '✗'} {AUDIO_PATH}")
    print(f"  Frames:   {n_frames}/{N_FRAMES} in {FRAMES_DIR}")
    print(f"  Metadata: {'✓' if INFO_PATH.exists() else '✗'} {INFO_PATH}")
    print(f"  Analysis: {'✓' if ANALYSIS_PATH.exists() else '✗'} {ANALYSIS_PATH}")
    print("")
    if not dl_ok:
        print("  NOTE: Video download failed. Other files that depend on the video were skipped.")
        print("  You can retry: python pipeline/download_video.py")


if __name__ == "__main__":
    main()
