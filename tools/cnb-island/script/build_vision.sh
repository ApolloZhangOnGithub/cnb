#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

xcodebuild \
  -project CNBIsland.xcodeproj \
  -target CNBVision \
  -configuration Debug \
  -sdk xrsimulator \
  SYMROOT="$ROOT_DIR/build" \
  OBJROOT="$ROOT_DIR/build/Intermediates" \
  CODE_SIGNING_ALLOWED=NO \
  build
