#!/bin/bash
# Launch the canonical plugin preview in a new Terminal window.
# Bypasses any TCC/permission weirdness from the Hermes agent's subprocess.
#
# Usage: bash tools/preview_in_terminal.sh effects/canonical/chiaroscuro_magenta.py [duration]

set -e

PLUGIN="${1:-effects/canonical/chiaroscuro_magenta.py}"
DURATION="${2:-12}"
PROJECT_DIR="$HOME/Desktop/Yousuke"

if [ ! -f "$PROJECT_DIR/$PLUGIN" ]; then
    echo "ERROR: plugin not found at $PROJECT_DIR/$PLUGIN"
    exit 1
fi

# Compose a shell command that cd's, activates venv, and runs the preview
CMD="cd '$PROJECT_DIR' && source .venv/bin/activate && python tools/preview_canonical.py '$PLUGIN' --duration $DURATION; echo; echo 'Preview ended. Close this window or press any key...'; read -n 1"

# Tell Terminal.app to open a new window and run the command
osascript <<EOF
tell application "Terminal"
    activate
    do script "$CMD"
end tell
EOF
