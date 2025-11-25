#!/bin/bash
###############################################################################
# PHILAB macOS App Builder
#
# This script builds a production-ready macOS .app bundle using PyInstaller.
# It handles dependency installation, building, and basic validation.
#
# Usage:
#   ./build-app.sh [--clean] [--dev]
#
# Options:
#   --clean    Clean previous builds before building
#   --dev      Build in development mode (includes debug symbols)
#
# Requirements:
#   - Python 3.10 or later
#   - PyInstaller (installed automatically if missing)
#   - macOS 10.14 (Mojave) or later
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
BUILD_DIR="$PROJECT_ROOT/build"
DIST_DIR="$PROJECT_ROOT/dist"
SPEC_FILE="$MACOS_DIR/philab.spec"

# Configuration
PYTHON_MIN_VERSION="3.10"
APP_NAME="PHILAB"
VERSION="1.0.0"

# Parse command-line arguments
CLEAN=false
DEV_MODE=false

for arg in "$@"; do
    case $arg in
        --clean)
            CLEAN=true
            shift
            ;;
        --dev)
            DEV_MODE=true
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $arg${NC}"
            echo "Usage: $0 [--clean] [--dev]"
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

check_python_version() {
    log_info "Checking Python version..."

    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed"
        exit 1
    fi

    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')

    if [ "$(printf '%s\n' "$PYTHON_MIN_VERSION" "$python_version" | sort -V | head -n1)" != "$PYTHON_MIN_VERSION" ]; then
        log_error "Python $PYTHON_MIN_VERSION or later is required (found $python_version)"
        exit 1
    fi

    log_success "Python $python_version found"
}

check_macos_version() {
    log_info "Checking macOS version..."

    if [[ "$OSTYPE" != "darwin"* ]]; then
        log_error "This script must be run on macOS"
        exit 1
    fi

    macos_version=$(sw_vers -productVersion)
    log_success "macOS $macos_version detected"
}

install_pyinstaller() {
    log_info "Checking PyInstaller installation..."

    if ! python3 -c "import PyInstaller" &> /dev/null; then
        log_warning "PyInstaller not found. Installing..."
        python3 -m pip install pyinstaller
        log_success "PyInstaller installed"
    else
        pyinstaller_version=$(python3 -c "import PyInstaller; print(PyInstaller.__version__)")
        log_success "PyInstaller $pyinstaller_version found"
    fi
}

install_dependencies() {
    log_info "Installing project dependencies..."

    cd "$PROJECT_ROOT"

    if [ -f "requirements.txt" ]; then
        python3 -m pip install -r requirements.txt
    fi

    # Install the project itself so PyInstaller can resolve imports from the
    # packaged ``philab`` module during analysis.
    python3 -m pip install -e .

    log_success "Dependencies installed"
}

clean_build() {
    log_info "Cleaning previous builds..."

    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        log_success "Removed build directory"
    fi

    if [ -d "$DIST_DIR" ]; then
        rm -rf "$DIST_DIR"
        log_success "Removed dist directory"
    fi
}

build_app() {
    log_info "Building macOS application bundle..."

    cd "$PROJECT_ROOT"

    # Build with PyInstaller
    if [ "$DEV_MODE" = true ]; then
        log_info "Building in development mode (with debug symbols)..."
        python3 -m PyInstaller --noconfirm --log-level=DEBUG "$SPEC_FILE"
    else
        log_info "Building in production mode..."
        python3 -m PyInstaller --noconfirm "$SPEC_FILE"
    fi

    log_success "Build completed"
}

validate_app() {
    log_info "Validating application bundle..."

    APP_PATH="$DIST_DIR/${APP_NAME}.app"

    if [ ! -d "$APP_PATH" ]; then
        log_error "Application bundle not found at $APP_PATH"
        exit 1
    fi

    # Check bundle structure
    if [ ! -f "$APP_PATH/Contents/Info.plist" ]; then
        log_error "Info.plist not found in bundle"
        exit 1
    fi

    if [ ! -f "$APP_PATH/Contents/MacOS/philab" ]; then
        log_error "Executable not found in bundle"
        exit 1
    fi

    # Verify code signature (if exists)
    if codesign -v "$APP_PATH" 2>/dev/null; then
        log_success "Code signature verified"
    else
        log_warning "Application is not code signed (this is normal for unsigned builds)"
    fi

    # Get bundle size
    bundle_size=$(du -sh "$APP_PATH" | cut -f1)
    log_info "Bundle size: $bundle_size"

    log_success "Application bundle validated: $APP_PATH"
}

print_next_steps() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    Build Successful! 🎉                        ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Application:${NC} $DIST_DIR/${APP_NAME}.app"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Test the application:"
    echo "     open \"$DIST_DIR/${APP_NAME}.app\""
    echo ""
    echo "  2. Create a DMG for distribution:"
    echo "     ./macos/build-scripts/create-dmg.sh"
    echo ""
    echo "  3. Sign and notarize for App Store / Gatekeeper:"
    echo "     ./macos/build-scripts/sign-and-notarize.sh"
    echo ""
    echo "  4. Create a .pkg installer:"
    echo "     ./macos/build-scripts/create-pkg.sh"
    echo ""
}

###############################################################################
# Main Script
###############################################################################

main() {
    log_info "Starting PHILAB macOS build process..."
    echo ""

    # Pre-flight checks
    check_macos_version
    check_python_version

    # Clean if requested
    if [ "$CLEAN" = true ]; then
        clean_build
    fi

    # Setup
    install_pyinstaller
    install_dependencies

    # Build
    build_app

    # Validate
    validate_app

    # Done
    print_next_steps
}

# Run main function
main
