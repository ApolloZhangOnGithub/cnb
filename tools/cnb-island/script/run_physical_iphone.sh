#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEVICE_SELECTOR="${CNB_IOS_DEVICE:-Kezhen 的 iPhone 深蓝色}"
TEAM_ID="${CNB_DEVELOPMENT_TEAM:-N2PMDDULMW}"
BUNDLE_ID="dev.cnb.CNBIsland"
BUILD_ROOT="${CNB_IOS_BUILD_ROOT:-/private/tmp/cnb-island-iphoneos-build}"
OBJ_ROOT="${CNB_IOS_OBJ_ROOT:-/private/tmp/cnb-island-iphoneos-obj}"
APP_BUNDLE="$BUILD_ROOT/Debug-iphoneos/CNBIsland.app"
SKIP_BUILD="${CNB_SKIP_BUILD:-0}"
STATE_FILE="$HOME/.cnb/live_state.json"
FEISHU_CHAT_CONFIG_FILE="$HOME/.cnb/feishu_chat.json"
ADMIN_TODO_FILE="${CNB_ADMIN_TODO_FILE:-$ROOT_DIR/../../ADMIN_TO_DO.md}"
DEVICE_JSON="$ROOT_DIR/build/physical-devices.json"
INSTALL_JSON="$ROOT_DIR/build/physical-install.json"
INSTALL_LOG="$ROOT_DIR/build/physical-install.log"
LAUNCH_JSON="$ROOT_DIR/build/physical-launch.json"
LAUNCH_LOG="$ROOT_DIR/build/physical-launch.log"
DEVICE_DETAILS_LOG="$ROOT_DIR/build/physical-device-details.log"
STAGING_DIR="/private/tmp/cnb-island-device-state"

cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/build"
: >"$INSTALL_LOG"
: >"$LAUNCH_LOG"

"$ROOT_DIR/script/export_live_state.py"
"$ROOT_DIR/script/export_feishu_chat_config.py" || true

xcrun devicectl list devices --json-output "$DEVICE_JSON" >/dev/null

DEVICE_INFO="$(
  CNB_IOS_DEVICE_SELECTOR="$DEVICE_SELECTOR" CNB_IOS_DEVICE_JSON="$DEVICE_JSON" python3 - <<'PY'
import json
import os
import sys

selector = os.environ["CNB_IOS_DEVICE_SELECTOR"]
path = os.environ["CNB_IOS_DEVICE_JSON"]
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
    print(f"Could not find device '{selector}'.", file=sys.stderr)
    sys.exit(2)

device = matches[0]
name = value(device, "deviceProperties", "name")
identifier = value(device, "identifier")
udid = value(device, "hardwareProperties", "udid")
tunnel = value(device, "connectionProperties", "tunnelState")
ddi = value(device, "deviceProperties", "ddiServicesAvailable")
developer = value(device, "deviceProperties", "developerModeStatus")
pairing = value(device, "connectionProperties", "pairingState")

print("|".join(map(str, [identifier, name, udid, tunnel, ddi, developer, pairing])))
PY
)"

IFS='|' read -r DEVICE_ID DEVICE_NAME DEVICE_UDID TUNNEL_STATE DDI_AVAILABLE DEVELOPER_MODE PAIRING_STATE <<<"$DEVICE_INFO"

echo "Target device: $DEVICE_NAME"
echo "Identifier: $DEVICE_ID"
echo "UDID: $DEVICE_UDID"
echo "Pairing: $PAIRING_STATE, Developer Mode: $DEVELOPER_MODE, tunnel: $TUNNEL_STATE, DDI: $DDI_AVAILABLE"

if [[ "$DEVELOPER_MODE" != "enabled" ]]; then
  if xcrun devicectl device info details --device "$DEVICE_ID" >"$DEVICE_DETAILS_LOG" 2>&1 &&
     grep -q "developerModeStatus: enabled" "$DEVICE_DETAILS_LOG"; then
    DEVELOPER_MODE="enabled"
    echo "Developer Mode rechecked from device details: enabled"
  fi
fi

if [[ "$TUNNEL_STATE" == "unavailable" ]]; then
  cat >&2 <<EOF
Device is paired but unavailable. Fix the phone connection first:
1. Connect 'Kezhen 的 iPhone 深蓝色' by USB, or put it on the same Wi-Fi with wireless debugging enabled.
2. Unlock the iPhone and keep it unlocked.
3. Tap Trust This Computer if prompted.
4. If Xcode shows it offline, open Xcode > Window > Devices and Simulators and wait for this iPhone to become available.

Then rerun:
  CNB_IOS_DEVICE="$DEVICE_SELECTOR" ./script/run_physical_iphone.sh
EOF
  exit 3
fi

if [[ "$DEVELOPER_MODE" == "disabled" ]]; then
  cat >&2 <<EOF
Device is connected and trusted, but iOS Developer Mode is disabled.

Enable it on the iPhone:
  Settings > Privacy & Security > Developer Mode > On

The iPhone will restart. After restart, unlock it and confirm "Turn On" for
Developer Mode, keep it connected by USB, then rerun:
  CNB_IOS_DEVICE="$DEVICE_SELECTOR" ./script/run_physical_iphone.sh
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
    -scheme CNBIsland \
    -configuration Debug \
    -sdk iphoneos \
    -destination "id=$DEVICE_UDID" \
    -allowProvisioningUpdates \
    -allowProvisioningDeviceRegistration \
    DEVELOPMENT_TEAM="$TEAM_ID" \
    SYMROOT="$BUILD_ROOT" \
    OBJROOT="$OBJ_ROOT" \
    build
fi

if ! xcrun devicectl device install app \
  --device "$DEVICE_ID" \
  "$APP_BUNDLE" \
  --timeout 60 \
  --json-output "$INSTALL_JSON" \
  --log-output "$INSTALL_LOG"; then
  if grep -q "kAMDMobileImageMounterDeviceLocked\\|The device is locked" "$INSTALL_LOG"; then
    cat >&2 <<EOF
Device is connected and Developer Mode is enabled, but the screen is locked.
Unlock '$DEVICE_NAME', keep the screen awake, then rerun:
  CNB_SKIP_BUILD=1 CNB_IOS_DEVICE="$DEVICE_SELECTOR" ./script/run_physical_iphone.sh
EOF
    exit 5
  fi
  if grep -q "This provisioning profile cannot be installed on this device\\|无法验证其完整性" "$INSTALL_LOG"; then
    cat >&2 <<EOF
The app is signed, but the provisioning profile does not include this iPhone.
Rerun without CNB_SKIP_BUILD so Xcode can register the device and refresh the
development profiles:
  CNB_IOS_DEVICE="$DEVICE_SELECTOR" ./script/run_physical_iphone.sh
EOF
    exit 7
  fi
  exit 1
fi

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp "$STATE_FILE" "$STAGING_DIR/live_state.json"
if [[ -f "$FEISHU_CHAT_CONFIG_FILE" ]]; then
  cp "$FEISHU_CHAT_CONFIG_FILE" "$STAGING_DIR/feishu_chat.json"
fi
if [[ -f "$ADMIN_TODO_FILE" ]]; then
  cp "$ADMIN_TODO_FILE" "$STAGING_DIR/ADMIN_TO_DO.md"
fi

xcrun devicectl device copy to \
  --device "$DEVICE_ID" \
  --source "$STAGING_DIR" \
  --destination "Documents" \
  --domain-type appDataContainer \
  --domain-identifier "$BUNDLE_ID" \
  --timeout 60

xcrun devicectl device process launch \
  --device "$DEVICE_ID" \
  --terminate-existing \
  --environment-variables '{"CNB_AUTOSTART_ACTIVITY":"1","CNB_RESET_ACTIVITY":"1"}' \
  "$BUNDLE_ID" \
  --timeout 60 \
  --json-output "$LAUNCH_JSON" \
  --log-output "$LAUNCH_LOG"

echo "OK installed and launched $BUNDLE_ID on $DEVICE_NAME."
echo "App: $APP_BUNDLE"
echo "Install log: $INSTALL_LOG"
echo "Launch log: $LAUNCH_LOG"
