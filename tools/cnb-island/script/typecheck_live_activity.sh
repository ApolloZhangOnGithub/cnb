#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SDK_PATH="$(xcrun --sdk iphonesimulator --show-sdk-path)"
TARGET="arm64-apple-ios26.0-simulator"

cd "$ROOT_DIR"

xcrun swiftc \
  -sdk "$SDK_PATH" \
  -target "$TARGET" \
  -swift-version 6 \
  -strict-concurrency=complete \
  -typecheck \
  Sources/CNBIslandShared/*.swift \
  Sources/CNBIslandApp/*.swift

xcrun swiftc \
  -sdk "$SDK_PATH" \
  -target "$TARGET" \
  -swift-version 6 \
  -strict-concurrency=complete \
  -typecheck \
  Sources/CNBIslandShared/*.swift \
  Sources/CNBIslandWidget/*.swift

echo "OK ActivityKit app and WidgetKit Live Activity sources type-check for $TARGET"
