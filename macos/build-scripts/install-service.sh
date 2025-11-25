#!/bin/bash
###############################################################################
# PHILAB Service Installation Script
#
# This script installs PHILAB as a macOS LaunchDaemon service.
# The service will automatically start on boot and restart if it crashes.
#
# Usage:
#   sudo ./install-service.sh [--uninstall]
#
# Options:
#   --uninstall    Remove the service
#
# Requirements:
#   - Must be run with sudo
#   - PHILAB.app must be installed in /Applications
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="com.e-tech-playtech.philab"
PLIST_SRC="$(dirname "$0")/../templates/${SERVICE_NAME}.plist"
PLIST_DEST="/Library/LaunchDaemons/${SERVICE_NAME}.plist"
APP_PATH="/Applications/PHILAB.app"
DATA_DIR="/usr/local/var/philab"
LOG_DIR="/usr/local/var/log/philab"

# Parse arguments
UNINSTALL=false
if [[ "${1:-}" == "--uninstall" ]]; then
    UNINSTALL=true
fi

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

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "This script must be run with sudo"
        exit 1
    fi
}

check_app_exists() {
    if [ ! -d "$APP_PATH" ]; then
        log_error "PHILAB.app not found at $APP_PATH"
        log_error "Please install PHILAB first"
        exit 1
    fi
}

create_user() {
    log_info "Creating service user..."

    # Check if user already exists
    if dscl . -read /Users/_philab &>/dev/null; then
        log_info "Service user _philab already exists"
        return
    fi

    # Find available UID
    local uid=300
    while dscl . -read /Users/_philab_${uid} &>/dev/null; do
        uid=$((uid + 1))
    done

    # Create user
    dscl . -create /Users/_philab
    dscl . -create /Users/_philab UserShell /usr/bin/false
    dscl . -create /Users/_philab RealName "PHILAB Service User"
    dscl . -create /Users/_philab UniqueID "$uid"
    dscl . -create /Users/_philab PrimaryGroupID 20
    dscl . -create /Users/_philab NFSHomeDirectory /var/empty
    dscl . -create /Users/_philab IsHidden 1

    # Create group
    dscl . -create /Groups/_philab
    dscl . -create /Groups/_philab RealName "PHILAB Service Group"
    dscl . -create /Groups/_philab PrimaryGroupID "$uid"

    log_success "Service user created"
}

create_directories() {
    log_info "Creating service directories..."

    # Create data directory
    mkdir -p "$DATA_DIR"
    chown _philab:_philab "$DATA_DIR"
    chmod 755 "$DATA_DIR"

    # Create log directory
    mkdir -p "$LOG_DIR"
    chown _philab:_philab "$LOG_DIR"
    chmod 755 "$LOG_DIR"

    log_success "Directories created"
}

install_service() {
    log_info "Installing LaunchDaemon..."

    # Stop existing service if running
    if launchctl list | grep -q "$SERVICE_NAME"; then
        log_info "Stopping existing service..."
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
    fi

    # Copy plist
    cp "$PLIST_SRC" "$PLIST_DEST"
    chown root:wheel "$PLIST_DEST"
    chmod 644 "$PLIST_DEST"

    # Load service
    launchctl load -w "$PLIST_DEST"

    log_success "Service installed and started"
}

uninstall_service() {
    log_info "Uninstalling service..."

    # Stop service
    if [ -f "$PLIST_DEST" ]; then
        launchctl unload -w "$PLIST_DEST" 2>/dev/null || true
        rm -f "$PLIST_DEST"
        log_success "Service uninstalled"
    else
        log_warning "Service not found"
    fi

    # Ask about data removal
    read -p "Remove data directory $DATA_DIR? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$DATA_DIR"
        log_success "Data directory removed"
    fi

    # Ask about log removal
    read -p "Remove log directory $LOG_DIR? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$LOG_DIR"
        log_success "Log directory removed"
    fi
}

print_status() {
    echo ""
    echo -e "${BLUE}Service Status:${NC}"
    if launchctl list | grep -q "$SERVICE_NAME"; then
        log_success "Service is running"
        launchctl list | grep "$SERVICE_NAME"
    else
        log_warning "Service is not running"
    fi
    echo ""
}

print_usage() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║              PHILAB Service Management                         ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${YELLOW}Service Control:${NC}"
    echo "  Start:   sudo launchctl load -w $PLIST_DEST"
    echo "  Stop:    sudo launchctl unload -w $PLIST_DEST"
    echo "  Restart: sudo launchctl unload $PLIST_DEST && sudo launchctl load $PLIST_DEST"
    echo "  Status:  sudo launchctl list | grep $SERVICE_NAME"
    echo ""
    echo -e "${YELLOW}Logs:${NC}"
    echo "  Output:  tail -f $LOG_DIR/stdout.log"
    echo "  Errors:  tail -f $LOG_DIR/stderr.log"
    echo ""
    echo -e "${YELLOW}Data:${NC}"
    echo "  Location: $DATA_DIR"
    echo ""
}

###############################################################################
# Main Script
###############################################################################

main() {
    check_root

    if [ "$UNINSTALL" = true ]; then
        log_info "Uninstalling PHILAB service..."
        uninstall_service
    else
        log_info "Installing PHILAB service..."
        check_app_exists
        create_user
        create_directories
        install_service
        print_status
        print_usage
    fi
}

# Run main function
main
