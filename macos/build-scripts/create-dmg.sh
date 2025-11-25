#!/bin/bash
###############################################################################
# PHILAB macOS DMG Creator
#
# This script creates a professional DMG disk image for macOS distribution.
# The DMG includes a custom background, application shortcut, and proper layout.
#
# Usage:
#   ./create-dmg.sh [--pkg] [--sign IDENTITY]
#
# Options:
#   --pkg              Include the .pkg installer instead of .app
#   --sign IDENTITY    Sign the DMG with the specified Developer ID
#
# Requirements:
#   - create-dmg tool (installed via Homebrew: brew install create-dmg)
#   - OR manual DMG creation using hdiutil (fallback)
###############################################################################

set -e  # Exit on error
set -u  # Exit on undefined variable

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MACOS_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$MACOS_DIR")"
DIST_DIR="$PROJECT_ROOT/dist"
RESOURCES_DIR="$MACOS_DIR/resources"

# Configuration
APP_NAME="PHILAB"
VERSION="1.0.0"
DMG_NAME="PHILAB-${VERSION}"
VOLUME_NAME="PHILAB ${VERSION}"

# Parse command-line arguments
USE_PKG=false
SIGN_IDENTITY=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --pkg)
            USE_PKG=true
            shift
            ;;
        --sign)
            SIGN_IDENTITY="$2"
            shift 2
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Usage: $0 [--pkg] [--sign IDENTITY]"
            exit 1
            ;;
    esac
done

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    if [ "$USE_PKG" = true ]; then
        if [ ! -f "$DIST_DIR/PHILAB-${VERSION}.pkg" ]; then
            log_error ".pkg installer not found. Please run create-pkg.sh first"
            exit 1
        fi
    else
        if [ ! -d "$DIST_DIR/${APP_NAME}.app" ]; then
            log_error "Application bundle not found. Please run build-app.sh first"
            exit 1
        fi
    fi

    log_success "Prerequisites verified"
}

create_dmg_background() {
    log_info "Creating DMG background image..."

    mkdir -p "$RESOURCES_DIR"

    # Create a simple text-based background (placeholder for actual design)
    # In production, use a professionally designed background image
    cat > "$RESOURCES_DIR/dmg-background.png.info" << 'EOF'
# DMG Background Image Placeholder
#
# For production use, place a 600x400px PNG image here:
#   macos/resources/dmg-background.png
#
# Recommended design:
#   - Brand colors and logo
#   - Arrow pointing from app to Applications folder
#   - Professional appearance
#   - 72 DPI resolution
EOF

    # Check if create-dmg is installed
    if command -v create-dmg &> /dev/null; then
        log_success "create-dmg tool found"
        return 0
    else
        log_warning "create-dmg tool not found (will use fallback method)"
        log_info "Install with: brew install create-dmg"
        return 1
    fi
}

create_dmg_with_tool() {
    log_info "Creating DMG using create-dmg tool..."

    local source_dir="$DIST_DIR/dmg_source"
    local dmg_path="$DIST_DIR/${DMG_NAME}.dmg"

    # Clean up
    rm -rf "$source_dir" "$dmg_path"

    # Create source directory
    mkdir -p "$source_dir"

    if [ "$USE_PKG" = true ]; then
        cp "$DIST_DIR/PHILAB-${VERSION}.pkg" "$source_dir/"
    else
        cp -R "$DIST_DIR/${APP_NAME}.app" "$source_dir/"
    fi

    # Create DMG
    create-dmg \
        --volname "$VOLUME_NAME" \
        --volicon "$RESOURCES_DIR/app-icon.icns" \
        --window-pos 200 120 \
        --window-size 600 400 \
        --icon-size 100 \
        --icon "${APP_NAME}.app" 150 190 \
        --hide-extension "${APP_NAME}.app" \
        --app-drop-link 450 190 \
        --eula "$PROJECT_ROOT/LICENSE" \
        --format UDZO \
        --no-internet-enable \
        "$dmg_path" \
        "$source_dir"

    # Clean up
    rm -rf "$source_dir"

    log_success "DMG created: $dmg_path"
}

create_dmg_fallback() {
    log_info "Creating DMG using hdiutil (fallback method)..."

    local source_dir="$DIST_DIR/dmg_source"
    local dmg_path="$DIST_DIR/${DMG_NAME}.dmg"
    local temp_dmg="$DIST_DIR/${DMG_NAME}-temp.dmg"

    # Clean up
    rm -rf "$source_dir" "$dmg_path" "$temp_dmg"

    # Create source directory
    mkdir -p "$source_dir"

    if [ "$USE_PKG" = true ]; then
        cp "$DIST_DIR/PHILAB-${VERSION}.pkg" "$source_dir/"
    else
        cp -R "$DIST_DIR/${APP_NAME}.app" "$source_dir/"
        ln -s /Applications "$source_dir/Applications"
    fi

    # Copy README
    if [ -f "$PROJECT_ROOT/README.md" ]; then
        cp "$PROJECT_ROOT/README.md" "$source_dir/README.txt"
    fi

    # Calculate size needed
    local size_mb=$(du -sm "$source_dir" | cut -f1)
    size_mb=$((size_mb + 50))  # Add 50MB padding

    # Create temporary DMG
    hdiutil create -srcfolder "$source_dir" \
        -volname "$VOLUME_NAME" \
        -fs HFS+ \
        -fsargs "-c c=64,a=16,e=16" \
        -format UDRW \
        -size ${size_mb}m \
        "$temp_dmg"

    # Mount the DMG
    local device=$(hdiutil attach -readwrite -noverify -noautoopen "$temp_dmg" | grep -E '^/dev/' | sed 1q | awk '{print $1}')
    local mount_point="/Volumes/$VOLUME_NAME"

    # Wait for mount
    sleep 2

    # Customize appearance
    if [ -d "$mount_point" ]; then
        # Set background if available
        if [ -f "$RESOURCES_DIR/dmg-background.png" ]; then
            mkdir -p "$mount_point/.background"
            cp "$RESOURCES_DIR/dmg-background.png" "$mount_point/.background/"
        fi

        # Apply custom settings with AppleScript
        osascript > /dev/null << EOF
tell application "Finder"
    tell disk "$VOLUME_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {400, 100, 1000, 500}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        if exists file ".background:dmg-background.png" then
            set background picture of viewOptions to file ".background:dmg-background.png"
        end if
        if exists file "$APP_NAME.app" then
            set position of item "$APP_NAME.app" to {150, 190}
        end if
        if exists file "Applications" then
            set position of item "Applications" to {450, 190}
        end if
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
EOF

        # Unmount
        hdiutil detach "$device" -quiet -force
    fi

    # Convert to compressed DMG
    hdiutil convert "$temp_dmg" \
        -format UDZO \
        -imagekey zlib-level=9 \
        -o "$dmg_path"

    # Clean up
    rm -f "$temp_dmg"
    rm -rf "$source_dir"

    log_success "DMG created: $dmg_path"
}

sign_dmg() {
    local dmg_path="$DIST_DIR/${DMG_NAME}.dmg"

    if [ -n "$SIGN_IDENTITY" ]; then
        log_info "Signing DMG with: $SIGN_IDENTITY"
        codesign --sign "$SIGN_IDENTITY" --timestamp "$dmg_path"
        log_success "DMG signed"
    else
        log_warning "DMG is not code signed"
    fi
}

verify_dmg() {
    log_info "Verifying DMG..."

    local dmg_path="$DIST_DIR/${DMG_NAME}.dmg"

    if [ ! -f "$dmg_path" ]; then
        log_error "DMG file not found"
        exit 1
    fi

    # Verify DMG integrity
    hdiutil verify "$dmg_path" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        log_success "DMG integrity verified"
    else
        log_error "DMG verification failed"
        exit 1
    fi

    # Get DMG size
    local dmg_size=$(du -sh "$dmg_path" | cut -f1)
    log_info "DMG size: $dmg_size"

    # Verify signature if signed
    if [ -n "$SIGN_IDENTITY" ]; then
        codesign -v "$dmg_path" 2>&1
        if [ $? -eq 0 ]; then
            log_success "DMG signature verified"
        else
            log_warning "DMG signature verification failed"
        fi
    fi

    log_success "DMG verified"
}

print_next_steps() {
    local dmg_path="$DIST_DIR/${DMG_NAME}.dmg"

    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  DMG Created Successfully! 💿                   ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}DMG:${NC} $dmg_path"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Test the DMG:"
    echo "     open \"$dmg_path\""
    echo ""
    echo "  2. Distribute to users via download link"
    echo ""

    if [ -z "$SIGN_IDENTITY" ]; then
        echo -e "${YELLOW}⚠️  Note:${NC} DMG is not signed or notarized"
        echo "     For public distribution, sign and notarize with:"
        echo "     ./macos/build-scripts/sign-and-notarize.sh"
        echo ""
    else
        echo "  3. Notarize for Gatekeeper:"
        echo "     ./macos/build-scripts/sign-and-notarize.sh --notarize"
        echo ""
    fi
}

###############################################################################
# Main Script
###############################################################################

main() {
    log_info "Starting PHILAB DMG creation..."
    echo ""

    check_prerequisites
    create_dmg_background

    # Use create-dmg tool if available, otherwise fallback
    if command -v create-dmg &> /dev/null && [ "$USE_PKG" = false ]; then
        create_dmg_with_tool
    else
        create_dmg_fallback
    fi

    sign_dmg
    verify_dmg
    print_next_steps
}

# Run main function
main
