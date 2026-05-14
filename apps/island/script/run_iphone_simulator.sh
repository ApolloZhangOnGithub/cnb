#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_NAME="${CNB_IOS_SIMULATOR_DEVICE:-iPhone 17 Pro}"
APP_BUNDLE="$ROOT_DIR/build/Debug-iphonesimulator/CNBIsland.app"
BUNDLE_ID="dev.cnb.CNBIsland"
STATE_FILE="$HOME/.cnb/live_state.json"
FEISHU_CHAT_CONFIG_FILE="$HOME/.cnb/feishu_chat.json"
ADMIN_TODO_FILE="${CNB_ADMIN_TODO_FILE:-$ROOT_DIR/../../ADMIN_TO_DO.md}"
STDOUT_LOG="$ROOT_DIR/build/simulator-launch.stdout.log"
STDERR_LOG="$ROOT_DIR/build/simulator-launch.stderr.log"

cd "$ROOT_DIR"

DEVICE_ID="$(
  CNB_IOS_SIMULATOR_DEVICE_NAME="$DEVICE_NAME" python3 - <<'PY'
import json
import os
import subprocess

name = os.environ["CNB_IOS_SIMULATOR_DEVICE_NAME"]
data = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
matches = []
for runtime, devices in data.get("devices", {}).items():
    if "iOS" not in runtime:
        continue
    for device in devices:
        if device.get("name") == name:
            matches.append(device)

shutdown = next((device for device in matches if device.get("state") == "Shutdown"), None)
chosen = shutdown or (matches[0] if matches else None)
if chosen:
    print(chosen["udid"])
PY
)"

if [[ -z "$DEVICE_ID" ]]; then
  echo "Could not find an available iOS simulator named '$DEVICE_NAME'." >&2
  exit 1
fi

if python3 - <<'PY'
import json
import subprocess
import sys

data = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "booted", "-j"]))
for runtime, devices in data.get("devices", {}).items():
    if "visionOS" not in runtime:
        continue
    if any(device.get("state") == "Booted" for device in devices):
        sys.exit(0)
sys.exit(1)
PY
then
  echo "A visionOS simulator is booted. Refusing to continue." >&2
  exit 1
fi

"$ROOT_DIR/script/export_live_state.py"
"$ROOT_DIR/script/export_feishu_chat_config.py" || true

xcrun simctl boot "$DEVICE_ID" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$DEVICE_ID" -b
/usr/bin/open -a Simulator --args -CurrentDeviceUDID "$DEVICE_ID"

xcodebuild \
  -project CNBIsland.xcodeproj \
  -target CNBIsland \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination "platform=iOS Simulator,id=$DEVICE_ID" \
  CODE_SIGNING_ALLOWED=NO \
  build

xcrun simctl install "$DEVICE_ID" "$APP_BUNDLE"

APP_DATA="$(xcrun simctl get_app_container "$DEVICE_ID" "$BUNDLE_ID" data)"
mkdir -p "$APP_DATA/Documents"
cp "$STATE_FILE" "$APP_DATA/Documents/live_state.json"
if [[ -f "$FEISHU_CHAT_CONFIG_FILE" ]]; then
  cp "$FEISHU_CHAT_CONFIG_FILE" "$APP_DATA/Documents/feishu_chat.json"
fi
if [[ -f "$ADMIN_TODO_FILE" ]]; then
  cp "$ADMIN_TODO_FILE" "$APP_DATA/Documents/ADMIN_TO_DO.md"
fi
mkdir -p "$APP_DATA/.cnb"
cp "$STATE_FILE" "$APP_DATA/.cnb/live_state.json"
if [[ -f "$FEISHU_CHAT_CONFIG_FILE" ]]; then
  cp "$FEISHU_CHAT_CONFIG_FILE" "$APP_DATA/.cnb/feishu_chat.json"
fi
if [[ -f "$ADMIN_TODO_FILE" ]]; then
  cp "$ADMIN_TODO_FILE" "$APP_DATA/.cnb/ADMIN_TO_DO.md"
fi

mkdir -p "$ROOT_DIR/build"
: >"$STDOUT_LOG"
: >"$STDERR_LOG"

SIMCTL_CHILD_CNB_AUTOSTART_ACTIVITY=1 \
SIMCTL_CHILD_CNB_RESET_ACTIVITY=1 \
  xcrun simctl launch \
    --terminate-running-process \
    --stdout="$STDOUT_LOG" \
    --stderr="$STDERR_LOG" \
    "$DEVICE_ID" \
    "$BUNDLE_ID"

sleep 4
xcrun simctl terminate "$DEVICE_ID" "$BUNDLE_ID" >/dev/null 2>&1 || true

echo "OK launched $BUNDLE_ID on $DEVICE_NAME ($DEVICE_ID)"
echo "App was terminated after startup so the system Live Activity remains visible on the Home Screen."
echo "State copied to $APP_DATA/Documents/live_state.json"
if [[ -f "$APP_DATA/Documents/feishu_chat.json" ]]; then
  echo "Feishu chat settings copied to $APP_DATA/Documents/feishu_chat.json"
fi
if [[ -f "$APP_DATA/Documents/ADMIN_TO_DO.md" ]]; then
  echo "Admin to-do copied to $APP_DATA/Documents/ADMIN_TO_DO.md"
fi
echo "Launch stdout: $STDOUT_LOG"
echo "Launch stderr: $STDERR_LOG"
