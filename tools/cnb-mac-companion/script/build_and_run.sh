#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="CNBMacCompanion"
BUNDLE_ID="dev.cnb.maccompanion"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(cat "$ROOT_DIR/VERSION" | tr -d '[:space:]')"
BUILD_NUMBER="$(git -C "$ROOT_DIR" rev-list --count HEAD 2>/dev/null || echo 1)"
BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
GIT_SHA="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_CACHE="$HOME/.cnb/build-cache/cnb-mac-companion"
INSTALL_DIR="$HOME/Applications"
APP_BUNDLE="$INSTALL_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
MODULE_CACHE="$BUILD_CACHE/module-cache"
RESOURCE_BUNDLE_NAME="CNBMacCompanion_CNBMacCompanion.bundle"

cd "$ROOT_DIR"

pkill -x "$APP_NAME" >/dev/null 2>&1 || true

mkdir -p "$MODULE_CACHE" "$INSTALL_DIR"
swift build \
  --product "$APP_NAME" \
  --scratch-path "$BUILD_CACHE" \
  -Xcc "-fmodules-cache-path=$MODULE_CACHE"

BUILD_BINARY="$(swift build --show-bin-path --scratch-path "$BUILD_CACHE")/$APP_NAME"
BUILD_PRODUCTS_DIR="$(swift build --show-bin-path --scratch-path "$BUILD_CACHE")"
BUILD_RESOURCE_BUNDLE="$BUILD_PRODUCTS_DIR/$RESOURCE_BUNDLE_NAME"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"

if [[ -d "$BUILD_RESOURCE_BUNDLE" ]]; then
  cp -R "$BUILD_RESOURCE_BUNDLE" "$APP_BUNDLE/$RESOURCE_BUNDLE_NAME"
fi

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>CNB Companion</string>
  <key>CFBundleDisplayName</key>
  <string>CNB Companion</string>
  <key>CFBundleDevelopmentRegion</key>
  <string>zh-Hans</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>$VERSION</string>
  <key>CFBundleVersion</key>
  <string>$BUILD_NUMBER</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
  </dict>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
PLIST

cat >"$APP_CONTENTS/build_meta.json" <<META
{"version":"$VERSION","build":"$BUILD_NUMBER","date":"$BUILD_DATE","git":"$GIT_SHA"}
META

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    open_app
    sleep 1
    pgrep -x "$APP_NAME" >/dev/null
    ;;
  --no-launch|no-launch)
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify|--no-launch]" >&2
    exit 2
    ;;
esac
