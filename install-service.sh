#!/usr/bin/env bash
# Install SunSquint Guard monitor as a macOS LaunchAgent (runs at login, stays in background).
# Requires: venv at PROJECT_ROOT/.venv and dependencies installed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR" && pwd)"
PYTHON="$ROOT/.venv/bin/python"
PLIST_NAME="com.sunsquintguard.monitor"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

if [[ ! -x "$PYTHON" ]]; then
  echo "Error: Python not found at $PYTHON"
  echo "Create a venv and install deps first:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$ROOT/data"

# Escape for plist: replace \ with \\ and replace " with \"
escape_plist() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'
}
ROOT_ESC=$(escape_plist "$ROOT")
PYTHON_ESC=$(escape_plist "$PYTHON")

cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$PLIST_NAME</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_ESC</string>
    <string>-m</string>
    <string>monitor</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$ROOT_ESC</string>
  <key>RunAtLoad</key>
  <true/>
  <key>StandardOutPath</key>
  <string>$ROOT_ESC/data/sunsquintguard-stdout.log</string>
  <key>StandardErrorPath</key>
  <string>$ROOT_ESC/data/sunsquintguard-stderr.log</string>
</dict>
</plist>
PLIST

# Unload first if already loaded (idempotent install)
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Installed and started: $PLIST_PATH"
echo "  Check: launchctl list | grep sunsquintguard"
echo "  Logs:  $ROOT/data/squint.log and data/sunsquintguard-stdout.log"
