#!/bin/bash
###############################################################################
# PHILAB Code Signing and Notarization Script
#
# This script handles code signing and Apple notarization for macOS applications.
# Notarization is required for apps distributed outside the App Store on macOS 10.15+.
#
# Developer mode: set PHILAB_DEVELOPER_MODE=local or pass --allow-missing-identity
# to skip signing/notarization when no Developer ID Application identity is present.
# Production signing requires a paid Apple Developer account and a Developer ID
# Application certificate.
###############################################################################

set -euo pipefail

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

# Configuration
APP_NAME="PHILAB"
VERSION="1.0.0"
BUNDLE_ID="com.e-tech-playtech.philab"

# Environment flags
DEV_MODE_ENV=false
if [[ "${PHILAB_DEVELOPER_MODE:-}" =~ ^[Ll][Oo][Cc][Aa][Ll]$ ]]; then
    DEV_MODE_ENV=true
fi

# Parse command-line arguments
APP_IDENTITY=""
INSTALLER_IDENTITY=""
APPLE_ID=""
TEAM_ID=""
PASSWORD=""
DO_NOTARIZE=false
DO_STAPLE=false
ALLOW_MISSING_IDENTITY=false

print_usage() {
    cat << EOF
Usage: $0 [options]

Required for signing (when a Developer ID Application identity is present):
  --app-identity ID          Developer ID Application certificate

Required for notarization:
  --apple-id EMAIL           Apple ID for notarization
  --team-id TEAM             Apple Developer Team ID
  --password PASS            App-specific password (optional if using keychain)

Optional:
  --bundle-id ID             Application bundle identifier (optional override)
  --installer-identity ID    Developer ID Installer certificate (for pkg signing)
  --notary-password PASS     App-specific password for notarization (alias for --password)
  --notarize                 Perform notarization
  --staple                   Staple notarization ticket
  --allow-missing-identity   Developer mode: skip signing/notarization if no Developer ID Application identity is found
  -h, --help                 Show this help message

Developer mode can also be enabled with PHILAB_DEVELOPER_MODE=local. Signing and
notarization require a paid Apple Developer account and a Developer ID Application certificate.

Examples:
  PHILAB_DEVELOPER_MODE=local $0
  $0 --allow-missing-identity
  $0 \\
    --app-identity "Developer ID Application: Company Name (TEAM_ID)" \\
    --installer-identity "Developer ID Installer: Company Name (TEAM_ID)" \\
    --apple-id "developer@example.com" \\
    --team-id "ABCD123456" \\
    --password "@keychain:APP_SPECIFIC_PASSWORD" \\
    --notarize --staple
EOF
}

while [[ $# -gt 0 ]]; do
    case $1 in
        --app-identity)
            APP_IDENTITY="$2"
            shift 2
            ;;
        --installer-identity)
            INSTALLER_IDENTITY="$2"
            shift 2
            ;;
        --apple-id)
            APPLE_ID="$2"
            shift 2
            ;;
        --team-id)
            TEAM_ID="$2"
            shift 2
            ;;
        --bundle-id)
            BUNDLE_ID="$2"
            shift 2
            ;;
        --password)
            PASSWORD="$2"
            shift 2
            ;;
        --notary-password)
            PASSWORD="$2"
            shift 2
            ;;
        --notarize)
            DO_NOTARIZE=true
            shift
            ;;
        --staple)
            DO_STAPLE=true
            shift
            ;;
        --allow-missing-identity)
            ALLOW_MISSING_IDENTITY=true
            shift
            ;;
        -h|--help)
            print_usage
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}\n"
            print_usage
            exit 1
            ;;
    esac
done

DEV_MODE=false
if [[ "$DEV_MODE_ENV" == true || "$ALLOW_MISSING_IDENTITY" == true ]]; then
    DEV_MODE=true
fi

HAS_DEVELOPER_IDENTITY=false

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

has_developer_id_application_identity() {
    if ! command -v security &> /dev/null; then
        log_error "security not found. Please install Xcode Command Line Tools."
        return 2
    fi

    local identity_output
    identity_output=$(security find-identity -v -p codesigning 2>/dev/null | grep "Developer ID Application" || true)

    if [[ -n "$identity_output" ]]; then
        echo "$identity_output"
        return 0
    fi

    return 1
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check for required tools
    if ! command -v codesign &> /dev/null; then
        log_error "codesign not found. Please install Xcode Command Line Tools."
        exit 1
    fi

    if [ "$DO_NOTARIZE" = true ]; then
        if ! command -v xcrun &> /dev/null; then
            log_error "xcrun not found. Please install Xcode Command Line Tools."
            exit 1
        fi
    fi

    # Check if app exists
    if [ ! -d "$DIST_DIR/${APP_NAME}.app" ]; then
        log_error "Application bundle not found. Please run build-app.sh first."
        exit 1
    fi

    log_success "Prerequisites verified"
}

create_entitlements() {
    log_info "Creating entitlements file..."

    cat > "$MACOS_DIR/PHILAB.entitlements" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Allow network access -->
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.network.server</key>
    <true/>

    <!-- File access -->
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>

    <!-- Disable library validation for Python modules -->
    <key>com.apple.security.cs.disable-library-validation</key>
    <true/>

    <!-- Allow loading of unsigned executable memory -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <true/>

    <!-- JIT entitlement (needed for PyTorch) -->
    <key>com.apple.security.cs.allow-jit</key>
    <true/>

    <!-- Disable runtime hardening for compatibility -->
    <key>com.apple.security.cs.disable-executable-page-protection</key>
    <true/>
</dict>
</plist>
EOF

    log_success "Entitlements file created"
}

sign_frameworks_and_binaries() {
    local app_path="$DIST_DIR/${APP_NAME}.app"

    log_info "Signing frameworks and binaries..."

    # Sign all dylibs and frameworks first
    find "$app_path/Contents" -name "*.dylib" -o -name "*.so" | while read -r lib; do
        log_info "Signing: $(basename "$lib")"
        codesign --force --sign "$APP_IDENTITY" \
            --options runtime \
            --timestamp \
            "$lib" 2>/dev/null || log_warning "Failed to sign: $lib"
    done

    # Sign frameworks
    find "$app_path/Contents/Frameworks" -name "*.framework" 2>/dev/null | while read -r framework; do
        log_info "Signing framework: $(basename "$framework")"
        codesign --force --sign "$APP_IDENTITY" \
            --options runtime \
            --timestamp \
            "$framework" 2>/dev/null || log_warning "Failed to sign: $framework"
    done

    log_success "Frameworks and binaries signed"
}

sign_application() {
    local app_path="$DIST_DIR/${APP_NAME}.app"

    log_info "Signing application bundle..."

    # Sign the main executable
    codesign --force --sign "$APP_IDENTITY" \
        --entitlements "$MACOS_DIR/PHILAB.entitlements" \
        --options runtime \
        --timestamp \
        --deep \
        "$app_path"

    log_success "Application bundle signed"
}

verify_signature() {
    local app_path="$DIST_DIR/${APP_NAME}.app"

    log_info "Verifying code signature..."

    # Verify signature
    codesign --verify --deep --strict --verbose=2 "$app_path" 2>&1

    if [ $? -eq 0 ]; then
        log_success "Code signature verified"
    else
        log_error "Code signature verification failed"
        exit 1
    fi

    # Display signature info
    log_info "Signature information:"
    codesign -dv --verbose=4 "$app_path" 2>&1 | grep -E "Authority|Identifier|TeamIdentifier"
}

create_archive_for_notarization() {
    log_info "Creating archive for notarization..."

    local app_path="$DIST_DIR/${APP_NAME}.app"
    local zip_path="$DIST_DIR/${APP_NAME}-${VERSION}.zip"

    # Remove old archive
    rm -f "$zip_path"

    # Create zip archive
    cd "$DIST_DIR"
    ditto -c -k --keepParent "${APP_NAME}.app" "$(basename "$zip_path")"
    cd - > /dev/null

    if [ ! -f "$zip_path" ]; then
        log_error "Failed to create archive for notarization"
        exit 1
    fi

    log_success "Archive created: $zip_path"
    echo "$zip_path"
}

submit_for_notarization() {
    local zip_path="$1"

    log_info "Submitting for notarization..."
    log_warning "This may take several minutes..."

    # Build notarytool command
    local notary_cmd=(
        xcrun notarytool submit "$zip_path"
        --apple-id "$APPLE_ID"
        --team-id "$TEAM_ID"
        --wait
    )

    # Add password argument
    if [ -n "$PASSWORD" ]; then
        notary_cmd+=(--password "$PASSWORD")
    else
        # Try to use keychain profile
        notary_cmd+=(--keychain-profile "PHILAB-Notarization")
    fi

    # Submit
    "${notary_cmd[@]}" > /tmp/notarization_output.txt 2>&1

    if [ $? -eq 0 ]; then
        log_success "Notarization successful!"
        cat /tmp/notarization_output.txt
        return 0
    else
        log_error "Notarization failed!"
        cat /tmp/notarization_output.txt
        exit 1
    fi
}

staple_notarization() {
    local app_path="$DIST_DIR/${APP_NAME}.app"

    log_info "Stapling notarization ticket..."

    xcrun stapler staple "$app_path"

    if [ $? -eq 0 ]; then
        log_success "Notarization ticket stapled"

        # Verify stapling
        xcrun stapler validate "$app_path"
        log_success "Staple validated"
    else
        log_error "Stapling failed"
        exit 1
    fi
}

sign_installer() {
    if [ -z "$INSTALLER_IDENTITY" ]; then
        log_warning "Installer identity not provided, skipping pkg signing"
        return
    fi

    local pkg_path="$DIST_DIR/PHILAB-${VERSION}.pkg"

    if [ ! -f "$pkg_path" ]; then
        log_warning "Installer package not found, skipping"
        return
    fi

    log_info "Signing installer package..."

    productsign --sign "$INSTALLER_IDENTITY" \
        --timestamp \
        "$pkg_path" \
        "$pkg_path.signed"

    mv "$pkg_path.signed" "$pkg_path"

    log_success "Installer package signed"
}

print_summary() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              Signing & Notarization Complete! ✅                ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Signed Application:${NC} $DIST_DIR/${APP_NAME}.app"

    if [ "$DO_NOTARIZE" = true ]; then
        echo -e "${BLUE}Status:${NC} Signed and Notarized ✓"
    else
        echo -e "${BLUE}Status:${NC} Signed (not notarized)"
    fi

    echo ""
    echo -e "${YELLOW}Distribution Options:${NC}"
    echo "  1. Create DMG for distribution:"
    echo "     ./macos/build-scripts/create-dmg.sh --sign \"$APP_IDENTITY\""
    echo ""
    echo "  2. The app is now ready for distribution and will pass Gatekeeper"
    echo ""

    if [ "$DO_NOTARIZE" = false ]; then
        echo -e "${YELLOW}⚠️  Note:${NC} For public distribution on macOS 10.15+, notarization is required:"
        echo "     $0 --app-identity \"$APP_IDENTITY\" \\"
        echo "        --apple-id \"your@email.com\" \\"
        echo "        --team-id \"YOUR_TEAM\" \\"
        echo "        --notarize --staple"
        echo ""
    fi
}

###############################################################################
# Main Script
###############################################################################

main() {
    log_info "Starting code signing and notarization process..."
    echo ""

    local identity_output=""
    if identity_output=$(has_developer_id_application_identity); then
        HAS_DEVELOPER_IDENTITY=true
        log_info "Developer ID Application identities detected. Proceeding with signing."
    else
        HAS_DEVELOPER_IDENTITY=false
    fi

    if [[ "$HAS_DEVELOPER_IDENTITY" == false ]]; then
        if [[ "$DEV_MODE" == true ]]; then
            log_warning "No valid Developer ID Application identity found."
            log_warning "PHILAB_DEVELOPER_MODE=local or --allow-missing-identity set; skipping signing and notarization."
            exit 0
        else
            log_error "No valid Developer ID Application identity found. Set PHILAB_DEVELOPER_MODE=local or pass --allow-missing-identity to skip signing."
            exit 1
        fi
    fi

    # Validate required arguments for signing/notarization when an identity exists
    if [ -z "$APP_IDENTITY" ]; then
        log_error "App identity required for signing. Use --app-identity"
        exit 1
    fi

    if [ "$DO_NOTARIZE" = true ]; then
        if [ -z "$APPLE_ID" ] || [ -z "$TEAM_ID" ]; then
            log_error "Apple ID and Team ID required for notarization"
            exit 1
        fi
    fi

    check_prerequisites
    create_entitlements
    sign_frameworks_and_binaries
    sign_application
    verify_signature

    if [ -n "$INSTALLER_IDENTITY" ]; then
        sign_installer
    fi

    if [ "$DO_NOTARIZE" = true ]; then
        local archive_path
        archive_path=$(create_archive_for_notarization)
        submit_for_notarization "$archive_path"

        if [ "$DO_STAPLE" = true ]; then
            staple_notarization
        fi
    fi

    print_summary
}

# Run main function
main
