#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_SELECTOR="${CNB_AVP_DEVICE:-Apollo’s Huawei Vision Pro}"
TEAM_ID="${CNB_DEVELOPMENT_TEAM:-N2PMDDULMW}"
BUNDLE_ID="dev.cnb.CNBVision"
BUILD_ROOT="${CNB_AVP_BUILD_ROOT:-/private/tmp/cnb-vision-xros-build}"
OBJ_ROOT="${CNB_AVP_OBJ_ROOT:-/private/tmp/cnb-vision-xros-obj}"
APP_BUNDLE="$BUILD_ROOT/Debug-xros/CNBVision.app"
SKIP_BUILD="${CNB_SKIP_BUILD:-0}"
FEISHU_CHAT_CONFIG_FILE="$HOME/.cnb/feishu_chat.json"
DEVICE_JSON="$ROOT_DIR/build/physical-avp-devices.json"
INSTALL_JSON="$ROOT_DIR/build/physical-avp-install.json"
INSTALL_LOG="$ROOT_DIR/build/physical-avp-install.log"
LAUNCH_JSON="$ROOT_DIR/build/physical-avp-launch.json"
LAUNCH_LOG="$ROOT_DIR/build/physical-avp-launch.log"
STAGING_DIR="/private/tmp/cnb-vision-device-state"

cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/build"
: >"$INSTALL_LOG"
: >"$LAUNCH_LOG"

"$ROOT_DIR/script/export_feishu_chat_config.py" || true

xcrun devicectl list devices --json-output "$DEVICE_JSON" >/dev/null

DEVICE_INFO="$(
  CNB_AVP_DEVICE_SELECTOR="$DEVICE_SELECTOR" CNB_AVP_DEVICE_JSON="$DEVICE_JSON" python3 - <<'PY'
import json
import os
import sys

selector = os.environ["CNB_AVP_DEVICE_SELECTOR"]
path = os.environ["CNB_AVP_DEVICE_JSON"]
data = json.load(open(path))
devices = data.get("result", {}).get("devices", [])

def value(device, *keys):
    cur = device
    for key in keys:
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(key)
    return cur if cur is not None else ""

matches = []
for device in devices:
    if value(device, "hardwareProperties", "platform") != "visionOS":
        continue
    names = {
        value(device, "identifier"),
        value(device, "deviceProperties", "name"),
        value(device, "hardwareProperties", "udid"),
        value(device, "hardwareProperties", "serialNumber"),
    }
    names.update(value(device, "connectionProperties", "potentialHostnames") or [])
    if selector in names:
        matches.append(device)

if not matches:
    print(f"Could not find AVP device '{selector}'.", file=sys.stderr)
    sys.exit(2)

device = matches[0]
print("|".join(map(str, [
    value(device, "identifier"),
    value(device, "deviceProperties", "name"),
    value(device, "hardwareProperties", "udid"),
    value(device, "connectionProperties", "pairingState"),
    value(device, "connectionProperties", "tunnelState"),
    value(device, "deviceProperties", "developerModeStatus"),
    value(device, "deviceProperties", "ddiServicesAvailable"),
])))
PY
)"

IFS='|' read -r DEVICE_ID DEVICE_NAME DEVICE_UDID PAIRING_STATE TUNNEL_STATE DEVELOPER_MODE DDI_AVAILABLE <<<"$DEVICE_INFO"

echo "Target device: $DEVICE_NAME"
echo "Identifier: $DEVICE_ID"
echo "UDID: $DEVICE_UDID"
echo "Pairing: $PAIRING_STATE, Developer Mode: $DEVELOPER_MODE, tunnel: $TUNNEL_STATE, DDI: $DDI_AVAILABLE"

if [[ "$DEVELOPER_MODE" == "disabled" ]]; then
  cat >&2 <<EOF
Developer Mode is disabled on '$DEVICE_NAME'.
Enable it on AVP, keep it awake, then rerun:
  CNB_AVP_DEVICE="$DEVICE_SELECTOR" ./script/run_physical_avp.sh
EOF
  exit 4
fi

if [[ "$SKIP_BUILD" == "1" ]]; then
  if [[ ! -d "$APP_BUNDLE" ]]; then
    echo "CNB_SKIP_BUILD=1 was set, but app bundle does not exist: $APP_BUNDLE" >&2
    exit 6
  fi
else
  rm -rf "$BUILD_ROOT" "$OBJ_ROOT"
  xcodebuild \
    -project CNBIsland.xcodeproj \
    -scheme CNBVision \
    -configuration Debug \
    -sdk xros \
    -destination "platform=visionOS,id=$DEVICE_UDID" \
    -allowProvisioningUpdates \
    -allowProvisioningDeviceRegistration \
    DEVELOPMENT_TEAM="$TEAM_ID" \
    SYMROOT="$BUILD_ROOT" \
    OBJROOT="$OBJ_ROOT" \
    build
fi

xcrun devicectl device install app \
  --device "$DEVICE_ID" \
  "$APP_BUNDLE" \
  --timeout 90 \
  --json-output "$INSTALL_JSON" \
  --log-output "$INSTALL_LOG"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
if [[ -f "$FEISHU_CHAT_CONFIG_FILE" ]]; then
  cp "$FEISHU_CHAT_CONFIG_FILE" "$STAGING_DIR/feishu_chat.json"
fi

if [[ -n "$(find "$STAGING_DIR" -type f -maxdepth 1 -print -quit)" ]]; then
  xcrun devicectl device copy to \
    --device "$DEVICE_ID" \
    --source "$STAGING_DIR" \
    --destination "Documents" \
    --domain-type appDataContainer \
    --domain-identifier "$BUNDLE_ID" \
    --timeout 90
fi

if ! xcrun devicectl device process launch \
  --device "$DEVICE_ID" \
  --terminate-existing \
  "$BUNDLE_ID" \
  --timeout 90 \
  --json-output "$LAUNCH_JSON" \
  --log-output "$LAUNCH_LOG"; then
  if grep -q "profile has not been explicitly trusted\\|invalid code signature" "$LAUNCH_LOG"; then
    cat >&2 <<EOF
CNBVision is installed, but AVP has not trusted this development profile yet.
On AVP, trust the developer profile for this Mac/account, then rerun:
  CNB_SKIP_BUILD=1 CNB_AVP_DEVICE="$DEVICE_SELECTOR" ./script/run_physical_avp.sh
EOF
    exit 8
  fi
  exit 1
fi

echo "OK installed and launched $BUNDLE_ID on $DEVICE_NAME."
echo "App: $APP_BUNDLE"
echo "Install log: $INSTALL_LOG"
echo "Launch log: $LAUNCH_LOG"
