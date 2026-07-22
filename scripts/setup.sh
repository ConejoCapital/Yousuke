#!/usr/bin/env bash
# YOUSUKE: one-shot environment setup.
# Run from anywhere: bash scripts/setup.sh
#
# Creates a local .venv and installs everything needed to run the Python
# standalone and the test suite. Downloading the reference video is
# optional and only needed if you want to re-run the analysis pipeline:
#   bash scripts/setup.sh --with-video

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$SCRIPT_DIR/.venv"

echo "=== YOUSUKE setup ==="
echo "Project root: $SCRIPT_DIR"

# 1. Python virtual environment
echo ""
echo "[1/2] Creating virtual environment..."
if [ -x "$VENV/bin/python" ]; then
    echo "  .venv already exists"
else
    python3 -m venv "$VENV"
    echo "  Created $VENV"
fi

# 2. Dependencies
echo ""
echo "[2/2] Installing Python packages..."
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$SCRIPT_DIR/standalone/requirements.txt"
echo "  Done."

# Optional: download the reference video for the analysis pipeline
if [[ "$1" == "--with-video" ]]; then
    echo ""
    echo "[optional] Downloading reference video..."
    mkdir -p "$SCRIPT_DIR/reference/frames"
    VIDEO_OUT="$SCRIPT_DIR/reference/video.mp4"
    if [ -s "$VIDEO_OUT" ]; then
        echo "  Video already exists: $VIDEO_OUT"
    else
        "$VENV/bin/python" -m yt_dlp \
            --format "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" \
            --output "$VIDEO_OUT" \
            "https://www.youtube.com/watch?v=CxflYGeSx7Q" || {
                echo "  WARNING: download failed. The standalone works without it."
            }
    fi
    if [ -s "$VIDEO_OUT" ] && [ ! -f "$SCRIPT_DIR/reference/audio.mp3" ]; then
        command -v ffmpeg >/dev/null && \
            ffmpeg -i "$VIDEO_OUT" -q:a 0 -map a "$SCRIPT_DIR/reference/audio.mp3" -y -loglevel error && \
            echo "  Audio extracted: reference/audio.mp3"
    fi
fi

echo ""
echo "=== Setup complete ==="
echo ""
echo "Run the visual engine (webcam + mic):"
echo "  $VENV/bin/python standalone/visuals.py --mode webcam --audio mic"
echo ""
echo "Run the tests:"
echo "  $VENV/bin/python -m pytest"
echo ""
echo "Open the TouchDesigner piece (needs TouchDesigner installed):"
echo "  open touchdesigner/AIPSummitYousuke.36.toe"
