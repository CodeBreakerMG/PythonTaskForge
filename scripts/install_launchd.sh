#!/usr/bin/env bash
# Install TaskForge as a login LaunchAgent (run AFTER the .app is installed).
#
# Usage:
#   ./scripts/install_launchd.sh
#   ./scripts/install_launchd.sh /Applications/TaskForge.app
#   ./scripts/install_launchd.sh --uninstall

set -euo pipefail

LABEL="com.taskforge.runtime"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$HOME/Library/Logs/TaskForge"
UID_NUM="$(id -u)"
DOMAIN="gui/${UID_NUM}"

resolve_app() {
  local candidate="${1:-}"

  if [[ -n "$candidate" ]]; then
    echo "$candidate"
    return
  fi

  local options=(
    "/Applications/TaskForge.app"
    "$HOME/Applications/TaskForge.app"
    "$(cd "$(dirname "$0")/.." && pwd)/dist/TaskForge.app"
  )

  for path in "${options[@]}"; do
    if [[ -d "$path" ]]; then
      echo "$path"
      return
    fi
  done

  echo ""
}

uninstall() {
  if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "${DOMAIN}/${LABEL}" || true
    echo "Stopped LaunchAgent ${LABEL}"
  fi

  if [[ -f "$PLIST" ]]; then
    rm -f "$PLIST"
    echo "Removed ${PLIST}"
  else
    echo "No plist found at ${PLIST}"
  fi
}

install_agent() {
  local app_path
  app_path="$(resolve_app "${1:-}")"

  if [[ -z "$app_path" || ! -d "$app_path" ]]; then
    echo "TaskForge.app not found."
    echo "Install/copy the app first, then run:"
    echo "  $0 /Applications/TaskForge.app"
    exit 1
  fi

  local binary="${app_path}/Contents/MacOS/TaskForge"
  if [[ ! -x "$binary" ]]; then
    # Fallback for unusual bundle layouts
    binary="$(/usr/bin/find "$app_path/Contents/MacOS" -type f -perm -111 | head -n 1 || true)"
  fi

  if [[ -z "${binary:-}" || ! -x "$binary" ]]; then
    echo "Could not find executable inside: $app_path"
    exit 1
  fi

  mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"

  cat >"$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>${binary}</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>StandardOutPath</key>
  <string>${LOG_DIR}/launchd.out.log</string>

  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/launchd.err.log</string>
</dict>
</plist>
EOF

  # Replace an existing agent if present
  if launchctl print "${DOMAIN}/${LABEL}" >/dev/null 2>&1; then
    launchctl bootout "${DOMAIN}/${LABEL}" || true
  fi

  launchctl bootstrap "$DOMAIN" "$PLIST"
  launchctl enable "${DOMAIN}/${LABEL}"
  launchctl kickstart -k "${DOMAIN}/${LABEL}"

  echo "Installed LaunchAgent: ${LABEL}"
  echo "App: ${app_path}"
  echo "Binary: ${binary}"
  echo "Plist: ${PLIST}"
  echo "Logs: ${LOG_DIR}/"
  echo
  echo "TaskForge should now start at login."
  echo "To remove later: $0 --uninstall"
}

case "${1:-}" in
  --uninstall|-u)
    uninstall
    ;;
  --help|-h)
    echo "Usage: $0 [/path/to/TaskForge.app]"
    echo "       $0 --uninstall"
    ;;
  *)
    install_agent "${1:-}"
    ;;
esac
