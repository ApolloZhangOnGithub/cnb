#!/usr/bin/env bash
# Archive and export CNB Island for TestFlight upload.
# Prerequisites: Xcode, valid Apple Developer signing identity.
#
# Usage:
#   ./script/archive_for_testflight.sh           # iPhone
#   ./script/archive_for_testflight.sh vision     # Vision Pro
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TARGET="${1:-iphone}"
ARCHIVE_DIR="$HOME/.cnb/build-cache/cnb-island-archives"
mkdir -p "$ARCHIVE_DIR"

if [ "$TARGET" = "vision" ]; then
  SCHEME="CNBVision"
  DEST="generic/platform=xrOS"
  ARCHIVE="$ARCHIVE_DIR/CNBVision.xcarchive"
  echo "=== Archiving CNBVision for visionOS ==="
else
  SCHEME="CNBIsland"
  DEST="generic/platform=iOS"
  ARCHIVE="$ARCHIVE_DIR/CNBIsland.xcarchive"
  echo "=== Archiving CNBIsland for iOS ==="
fi

xcodebuild archive \
  -project CNBIsland.xcodeproj \
  -scheme "$SCHEME" \
  -destination "$DEST" \
  -archivePath "$ARCHIVE" \
  -configuration Release \
  SKIP_INSTALL=NO \
  BUILD_LIBRARY_FOR_DISTRIBUTION=YES

echo ""
echo "=== Archive created at $ARCHIVE ==="
echo ""
echo "Next steps:"
echo "  1. Open Xcode Organizer: xed $ARCHIVE"
echo "  2. Click 'Distribute App' → App Store Connect → Upload"
echo "  3. Or use: xcrun altool --upload-app -f <path-to-ipa> -u <apple-id> -p <app-specific-password>"
echo ""
echo "After upload, go to App Store Connect → TestFlight to manage testers."
