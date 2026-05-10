#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_NAME="${CNB_VISION_SIMULATOR_DEVICE:-Apple Vision Pro}"
BUNDLE_ID="dev.cnb.CNBVision"
APP_BUNDLE="$ROOT_DIR/build/Debug-xrsimulator/CNBVision.app"
FEISHU_CHAT_CONFIG_FILE="$HOME/.cnb/feishu_chat.json"

cd "$ROOT_DIR"

DEVICE_ID="$(
  CNB_VISION_SIMULATOR_DEVICE_NAME="$DEVICE_NAME" python3 - <<'PY'
import json
import os
import subprocess

name = os.environ["CNB_VISION_SIMULATOR_DEVICE_NAME"]
data = json.loads(subprocess.check_output(["xcrun", "simctl", "list", "devices", "available", "-j"]))
matches = []
for runtime, devices in data.get("devices", {}).items():
    if "visionOS" not in runtime and "xrOS" not in runtime:
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
  echo "Could not find an available visionOS simulator named '$DEVICE_NAME'." >&2
  exit 1
fi

"$ROOT_DIR/script/export_feishu_chat_config.py" || true

xcrun simctl boot "$DEVICE_ID" >/dev/null 2>&1 || true
xcrun simctl bootstatus "$DEVICE_ID" -b
/usr/bin/open -a Simulator --args -CurrentDeviceUDID "$DEVICE_ID"

xcodebuild \
  -project CNBIsland.xcodeproj \
  -target CNBVision \
  -configuration Debug \
  -sdk xrsimulator \
  SYMROOT="$ROOT_DIR/build" \
  OBJROOT="$ROOT_DIR/build/Intermediates" \
  CODE_SIGNING_ALLOWED=NO \
  build

xcrun simctl install "$DEVICE_ID" "$APP_BUNDLE"

APP_DATA="$(xcrun simctl get_app_container "$DEVICE_ID" "$BUNDLE_ID" data)"
mkdir -p "$APP_DATA/Documents" "$APP_DATA/.cnb"
if [[ -f "$FEISHU_CHAT_CONFIG_FILE" ]]; then
  cp "$FEISHU_CHAT_CONFIG_FILE" "$APP_DATA/Documents/feishu_chat.json"
  cp "$FEISHU_CHAT_CONFIG_FILE" "$APP_DATA/.cnb/feishu_chat.json"
fi

xcrun simctl launch \
  --terminate-running-process \
  "$DEVICE_ID" \
  "$BUNDLE_ID"

echo "OK launched $BUNDLE_ID on $DEVICE_NAME ($DEVICE_ID)"
if [[ -f "$APP_DATA/Documents/feishu_chat.json" ]]; then
  echo "Feishu chat settings copied to $APP_DATA/Documents/feishu_chat.json"
else
  echo "No ~/.cnb/feishu_chat.json found; the app will show the missing-config state."
fi
