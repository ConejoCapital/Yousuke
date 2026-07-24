#!/usr/bin/env bash
# ============================================================
# YOUSUKE Visual Extender — Summit Launch Script
# AI Psychosis Summit NYC | April 30, 2026
# ============================================================
# Run this script from the project root:
#   bash scripts/launch_summit.sh
#
# Options:
#   --mode td        Launch TouchDesigner .toe (GPU, presentation grade)
#   --mode python    Launch Python standalone (fallback, webcam+mic)
#   --mode showcase  Launch live showcase (fullscreen, quiet, all effects rotating)
#   --mode both      Launch both simultaneously
# ============================================================

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$SCRIPT_DIR/.venv/bin"
TOE="$SCRIPT_DIR/touchdesigner/AIPSummitYousuke.36.toe"
TD_APP="/Applications/TouchDesigner.app/Contents/MacOS/TouchDesigner"

MODE="${1:-td}"
if [[ "$1" == "--mode" ]]; then MODE="$2"; fi

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║   ¥ØUSUK€ Visual Extender — AI Psychosis Summit NYC  ║"
echo "║   April 30, 2026                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

check_deps() {
    echo "→ Checking dependencies..."
    if [ ! -x "$VENV/python" ]; then
        echo "  No .venv found, running setup..."
        bash "$SCRIPT_DIR/scripts/setup.sh"
    fi
    if ! "$VENV/python" -c "import cv2, sounddevice, librosa" 2>/dev/null; then
        echo "  Installing Python deps..."
        "$VENV/python" -m pip install -q -r "$SCRIPT_DIR/standalone/requirements.txt"
    fi
    echo "  ✓ Python deps OK"
}

launch_td() {
    echo "→ Launching TouchDesigner..."
    if [ ! -f "$TOE" ]; then
        echo "  ERROR: touchdesigner/AIPSummitYousuke.36.toe not found at $TOE"
        exit 1
    fi
    if [ ! -f "$TD_APP" ]; then
        echo "  ERROR: TouchDesigner not found at $TD_APP"
        echo "  Download from: https://derivative.ca/download"
        exit 1
    fi
    open -a TouchDesigner "$TOE"
    echo "  ✓ TouchDesigner launched with AIPSummitYousuke.36.toe"
    echo ""
    echo "  Controls (once window opens):"
    echo "    1-9      → Lock to effect"
    echo "    0        → Toggle auto-rotate"
    echo "    Space/→  → Next effect"
    echo "    ←        → Previous effect"
    echo "    B        → Toggle blend mode"
    echo "    Esc      → Close output window"
    echo ""
    echo "  To open fullscreen output:"
    echo "    In TD: locate main_output → right-click → Open as Window"
    echo "    Or: effect_router → Open as Floating Window"
}

launch_python() {
    echo "→ Launching Python standalone (webcam + mic)..."
    check_deps
    "$VENV/python" "$SCRIPT_DIR/standalone/visuals.py" --mode webcam --audio mic
}

launch_showcase() {
    echo "→ Launching Live Showcase (fullscreen + quiet)..."
    check_deps
    "$VENV/python" "$SCRIPT_DIR/tools/live_showcase.py" --fullscreen --quiet
}

case "$MODE" in
    td)
        launch_td
        ;;
    python)
        launch_python
        ;;
    showcase)
        launch_showcase
        ;;
    both)
        launch_td
        sleep 3
        echo ""
        echo "→ Also launching Python standalone as backup monitor..."
        check_deps
        "$VENV/python" "$SCRIPT_DIR/standalone/visuals.py" --mode webcam --audio mic &
        ;;
    help|--help|-h)
        echo "Usage: bash launch_summit.sh [--mode td|python|showcase|both]"
        echo ""
        echo "  td       → Launch TouchDesigner .toe (default, GPU-accelerated)"
        echo "  python   → Launch Python standalone (cv2 + sounddevice fallback)"
        echo "  showcase → Launch live showcase (fullscreen, all effects, quiet)"
        echo "  both     → Launch TD + Python simultaneously"
        ;;
    *)
        echo "Unknown mode: $MODE. Use --mode td|python|showcase|both"
        exit 1
        ;;
esac
