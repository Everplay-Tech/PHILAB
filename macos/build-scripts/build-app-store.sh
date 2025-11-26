#!/bin/bash
###############################################################################
# PHILAB App Store Build Script
#
# This script builds, signs, and packages PHILAB for the Mac App Store.
#
# Usage:
#   ./build-app-store.sh --identity "Apple Distribution: Your Name (TEAMID)"
#
###############################################################################

set -e

# Configuration
APP_NAME="PHILAB"
VERSION="1.0.0"
BUNDLE_ID="com.e-tech-playtech.philab"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DIST_DIR="$PROJECT_ROOT/dist"
ENTITLEMENTS="$PROJECT_ROOT/macos/templates/AppStore.entitlements"
INFO_PLIST="$PROJECT_ROOT/macos/templates/Info.plist"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Parse Args
SIGNING_IDENTITY=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --identity)
            SIGNING_IDENTITY="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

if [ -z "$SIGNING_IDENTITY" ]; then
    echo -e "${RED}Error: You must provide a signing identity with --identity${NC}"
    echo "Example: --identity \"Apple Distribution: Everplay-Tech (ABC12345)\""
    exit 1
fi

echo -e "${GREEN}Building for App Store...${NC}"

# 1. Build the App using existing script
"$SCRIPT_DIR/build-app.sh" --clean

APP_PATH="$DIST_DIR/$APP_NAME.app"

# 2. Replace Info.plist with App Store compatible one
echo "Updating Info.plist..."
cp "$INFO_PLIST" "$APP_PATH/Contents/Info.plist"

# 3. Remove incompatible binaries (if any)
# Sometimes PyInstaller bundles things that fail validation.
# For now, we assume the build is clean.

# 4. Sign Frameworks and Dylibs (Inner Signing)
echo "Signing libraries..."
find "$APP_PATH/Contents" -name "*.dylib" -o -name "*.so" | while read -r lib; do
    codesign --force --sign "$SIGNING_IDENTITY" \
        --entitlements "$ENTITLEMENTS" \
        --options runtime \
        --timestamp \
        "$lib"
done

# 5. Sign the Main Application (Outer Signing)
echo "Signing application bundle..."
codesign --force --verify --verbose --sign "$SIGNING_IDENTITY" \
    --entitlements "$ENTITLEMENTS" \
    --options runtime \
    --timestamp \
    --deep \
    "$APP_PATH"

# 6. Build the Installer Package (.pkg)
# This is what you actually upload to App Store Connect
echo "Building Installer Package (.pkg)..."
PKG_PATH="$DIST_DIR/$APP_NAME-$VERSION.pkg"

productbuild --component "$APP_PATH" /Applications \
    --sign "3rd Party Mac Developer Installer" \
    "$PKG_PATH"

echo -e "${GREEN}Done!${NC}"
echo "Installer ready for upload: $PKG_PATH"
