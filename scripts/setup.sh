#!/usr/bin/env bash
# ¥ØUSUK€ Visual Extender — One-shot environment setup
# Run: bash ~/Desktop/Yousuke/setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REF_DIR="$SCRIPT_DIR/reference"
FRAMES_DIR="$REF_DIR/frames"

echo "=== ¥ØUSUK€ Visual Extender Setup ==="
echo "Working directory: $SCRIPT_DIR"

# ── 1. Create reference folder structure ──────────────────────────────────────
mkdir -p "$REF_DIR" "$FRAMES_DIR"

# ── 2. Install yt-dlp via brew ────────────────────────────────────────────────
echo ""
echo "[1/4] Installing yt-dlp..."
if command -v yt-dlp &>/dev/null; then
    echo "  yt-dlp already installed: $(yt-dlp --version)"
else
    brew install yt-dlp
    echo "  yt-dlp installed: $(yt-dlp --version)"
fi

# ── 3. Install Python dependencies ───────────────────────────────────────────
echo ""
echo "[2/4] Installing Python packages..."
pip install --quiet --upgrade \
    librosa \
    sounddevice \
    opencv-python \
    mediapipe \
    moderngl \
    pygame \
    numpy \
    Pillow \
    yt-dlp \
    requests

echo "  Python packages installed."

# ── 4. Download video ────────────────────────────────────────────────────────
echo ""
echo "[3/4] Downloading ¥ØUSUK€ Boiler Room video..."
VIDEO_ID="CxflYGeSx7Q"
VIDEO_OUT="$REF_DIR/video.mp4"

if [ -f "$VIDEO_OUT" ] && [ -s "$VIDEO_OUT" ]; then
    echo "  Video already exists: $VIDEO_OUT"
else
    yt-dlp \
        --format "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" \
        --output "$VIDEO_OUT" \
        --write-info-json \
        --write-description \
        "https://www.youtube.com/watch?v=$VIDEO_ID" || {
            echo "  WARNING: Video download failed (may require age verification or be unavailable)."
            echo "  Skipping video download — standalone/visuals.py works without it."
        }
fi

# ── 5. Extract audio ──────────────────────────────────────────────────────────
AUDIO_OUT="$REF_DIR/audio.mp3"
if [ -f "$VIDEO_OUT" ] && [ -s "$VIDEO_OUT" ] && [ ! -f "$AUDIO_OUT" ]; then
    echo "  Extracting audio track..."
    ffmpeg -i "$VIDEO_OUT" -q:a 0 -map a "$AUDIO_OUT" -y -loglevel error
    echo "  Audio extracted: $AUDIO_OUT"
elif [ -f "$AUDIO_OUT" ]; then
    echo "  Audio already exists: $AUDIO_OUT"
fi

# ── 6. Extract 30 key frames ─────────────────────────────────────────────────
echo ""
echo "[4/4] Extracting reference frames..."
if [ -f "$VIDEO_OUT" ] && [ -s "$VIDEO_OUT" ]; then
    python3 "$SCRIPT_DIR/download_video.py" --frames-only 2>/dev/null || \
    python3 - <<'PYEOF'
import cv2, os, sys

video_path = os.path.expanduser("~/Desktop/Yousuke/reference/video.mp4")
frames_dir = os.path.expanduser("~/Desktop/Yousuke/reference/frames")
os.makedirs(frames_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
fps   = cap.get(cv2.CAP_PROP_FPS)
duration = total / fps if fps > 0 else 0

N = 30
indices = [int(i * total / N) for i in range(N)]
saved = 0
for idx in indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if ret:
        ts = idx / fps if fps > 0 else 0
        path = os.path.join(frames_dir, f"frame_{saved:02d}_{ts:.1f}s.jpg")
        cv2.imwrite(path, frame)
        saved += 1
cap.release()
print(f"  Extracted {saved} frames to {frames_dir}")
PYEOF
else
    echo "  No video file found — skipping frame extraction."
    echo "  Run 'python download_video.py' manually after video is available."
fi

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Setup complete ==="
echo ""
echo "Reference folder contents:"
ls -lh "$REF_DIR" 2>/dev/null || true
echo ""
echo "Next steps:"
echo "  1. Run the visual engine:"
echo "     python $SCRIPT_DIR/standalone/visuals.py --mode webcam --audio mic"
echo ""
echo "  2. Run with pre-recorded audio:"
echo "     python $SCRIPT_DIR/standalone/visuals.py --mode file --audio $AUDIO_OUT"
echo ""
echo "  3. Build TouchDesigner network:"
echo "     See $SCRIPT_DIR/touchdesigner/README_FOR_HERMES.md"
