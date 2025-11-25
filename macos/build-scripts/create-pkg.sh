#!/bin/bash
###############################################################################
# PHILAB macOS .pkg Installer Creator
#
# This script creates a production-ready macOS .pkg installer that can be
# distributed through enterprise MDM systems or direct download.
#
# The installer includes:
#   - Application bundle installation
#   - Pre-install and post-install scripts
#   - LaunchDaemon setup (optional)
#   - Proper permissions and ownership
#
# Usage:
#   ./create-pkg.sh [--sign IDENTITY] [--no-service]
#
# Options:
#   --sign IDENTITY    Sign the package with the specified Developer ID
#   --no-service       Don't install the LaunchDaemon service
#
# Requirements:
#   - pkgbuild and productbuild command-line tools
#   - PHILAB.app already built (run build-app.sh first)
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
INSTALLERS_DIR="$MACOS_DIR/installers"

# Configuration
APP_NAME="PHILAB"
VERSION="1.0.0"
BUNDLE_ID="com.e-tech-playtech.philab"
APP_PATH="$DIST_DIR/${APP_NAME}.app"
PKG_NAME="PHILAB-${VERSION}.pkg"
PKG_PATH="$DIST_DIR/$PKG_NAME"

# Parse command-line arguments
SIGN_IDENTITY=""
INSTALL_SERVICE=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --sign)
            SIGN_IDENTITY="$2"
            shift 2
            ;;
        --no-service)
            INSTALL_SERVICE=false
            shift
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Usage: $0 [--sign IDENTITY] [--no-service]"
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

    # Check if app bundle exists
    if [ ! -d "$APP_PATH" ]; then
        log_error "Application bundle not found at $APP_PATH"
        log_error "Please run build-app.sh first"
        exit 1
    fi

    # Check if pkgbuild exists
    if ! command -v pkgbuild &> /dev/null; then
        log_error "pkgbuild command not found. Please install Xcode Command Line Tools."
        exit 1
    fi

    # Check if productbuild exists
    if ! command -v productbuild &> /dev/null; then
        log_error "productbuild command not found. Please install Xcode Command Line Tools."
        exit 1
    fi

    log_success "Prerequisites verified"
}

create_installer_scripts() {
    log_info "Creating installer scripts..."

    mkdir -p "$INSTALLERS_DIR/scripts"

    # Pre-install script
    cat > "$INSTALLERS_DIR/scripts/preinstall" << 'EOF'
#!/bin/bash
# Pre-install script for PHILAB

set -e

echo "Preparing to install PHILAB..."

# Stop the service if running
if launchctl list | grep -q "com.e-tech-playtech.philab"; then
    echo "Stopping existing PHILAB service..."
    launchctl unload /Library/LaunchDaemons/com.e-tech-playtech.philab.plist 2>/dev/null || true
fi

# Remove old installation if exists
if [ -d "/Applications/PHILAB.app" ]; then
    echo "Removing previous installation..."
    rm -rf "/Applications/PHILAB.app"
fi

exit 0
EOF

    # Post-install script
    cat > "$INSTALLERS_DIR/scripts/postinstall" << EOF
#!/bin/bash
# Post-install script for PHILAB

set -e

echo "Configuring PHILAB installation..."

# Set correct permissions
chmod -R 755 "/Applications/PHILAB.app"
chown -R root:wheel "/Applications/PHILAB.app"

# Create directories for data
mkdir -p "/usr/local/var/philab"
mkdir -p "/usr/local/var/log/philab"
chmod 755 "/usr/local/var/philab"
chmod 755 "/usr/local/var/log/philab"

# Install LaunchDaemon if requested
if [ "$INSTALL_SERVICE" = true ] && [ -f "/Applications/PHILAB.app/Contents/Resources/com.e-tech-playtech.philab.plist" ]; then
    echo "Installing PHILAB service..."
    cp "/Applications/PHILAB.app/Contents/Resources/com.e-tech-playtech.philab.plist" "/Library/LaunchDaemons/"
    chmod 644 "/Library/LaunchDaemons/com.e-tech-playtech.philab.plist"
    chown root:wheel "/Library/LaunchDaemons/com.e-tech-playtech.philab.plist"

    # Start the service
    launchctl load "/Library/LaunchDaemons/com.e-tech-playtech.philab.plist"
    echo "PHILAB service started"
fi

# Create symlink for CLI access
ln -sf "/Applications/PHILAB.app/Contents/MacOS/philab" "/usr/local/bin/philab" || true

echo "PHILAB installation completed successfully!"
echo ""
echo "To start using PHILAB:"
echo "  1. Run 'philab' from the command line"
echo "  2. Or open the PHILAB application from /Applications"
echo ""

exit 0
EOF

    chmod +x "$INSTALLERS_DIR/scripts/preinstall"
    chmod +x "$INSTALLERS_DIR/scripts/postinstall"

    log_success "Installer scripts created"
}

create_distribution_xml() {
    log_info "Creating distribution definition..."

    cat > "$INSTALLERS_DIR/distribution.xml" << EOF
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>PHILAB - AI Interpretability Lab</title>
    <organization>com.e-tech-playtech</organization>
    <domains enable_localSystem="true"/>
    <options customize="never" require-scripts="true" rootVolumeOnly="true" />

    <!-- Define documents displayed at various steps -->
    <welcome file="welcome.html" mime-type="text/html" />
    <license file="license.html" mime-type="text/html" />
    <readme file="readme.html" mime-type="text/html" />
    <conclusion file="conclusion.html" mime-type="text/html" />

    <!-- Define product information -->
    <product id="${BUNDLE_ID}" version="${VERSION}" />

    <!-- Installation check -->
    <installation-check script="pm_install_check();"/>
    <script>
    <![CDATA[
    function pm_install_check() {
        if (system.compareVersions(system.version.ProductVersion, '10.14.0') < 0) {
            my.result.title = 'Unable to install';
            my.result.message = 'PHILAB requires macOS 10.14 (Mojave) or later.';
            my.result.type = 'Fatal';
            return false;
        }
        return true;
    }
    ]]>
    </script>

    <!-- List all component packages -->
    <pkg-ref id="${BUNDLE_ID}">
        <bundle-version>
            <bundle id="${BUNDLE_ID}" CFBundleVersion="${VERSION}" path="/Applications/PHILAB.app" />
        </bundle-version>
    </pkg-ref>

    <!-- Define the installation order -->
    <choices-outline>
        <line choice="default">
            <line choice="${BUNDLE_ID}" />
        </line>
    </choices-outline>

    <choice id="default"/>
    <choice id="${BUNDLE_ID}" visible="false">
        <pkg-ref id="${BUNDLE_ID}"/>
    </choice>

    <pkg-ref id="${BUNDLE_ID}" version="${VERSION}" onConclusion="none">philab-component.pkg</pkg-ref>

</installer-gui-script>
EOF

    log_success "Distribution definition created"
}

create_documentation_resources() {
    log_info "Creating installer documentation..."

    mkdir -p "$INSTALLERS_DIR/resources"

    # Welcome message
    cat > "$INSTALLERS_DIR/resources/welcome.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 20px; }
        h1 { color: #007AFF; }
        .highlight { background-color: #F0F8FF; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>Welcome to PHILAB</h1>
    <p>This installer will guide you through the installation of <strong>PHILAB - AI Interpretability Lab</strong>, an enterprise-ready multi-agent AI interpretability laboratory for Microsoft's Phi-2 model.</p>

    <div class="highlight">
        <h3>What is PHILAB?</h3>
        <p>PHILAB provides:</p>
        <ul>
            <li>Multi-agent AI orchestration and collaboration</li>
            <li>Advanced model interpretability research tools</li>
            <li>Knowledge base management (Atlas)</li>
            <li>Adaptive experiments and ablation studies</li>
            <li>Enterprise-grade production deployment</li>
        </ul>
    </div>

    <p><strong>Version:</strong> 1.0.0</p>
    <p><strong>Publisher:</strong> E-TECH-PLAYTECH</p>
</body>
</html>
EOF

    # License
    if [ -f "$PROJECT_ROOT/LICENSE" ]; then
        cat > "$INSTALLERS_DIR/resources/license.html" << EOF
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: monospace; padding: 20px; font-size: 12px; }
        pre { white-space: pre-wrap; }
    </style>
</head>
<body>
    <pre>$(cat "$PROJECT_ROOT/LICENSE")</pre>
</body>
</html>
EOF
    fi

    # Readme
    cat > "$INSTALLERS_DIR/resources/readme.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 20px; }
        h2 { color: #007AFF; }
        code { background-color: #F5F5F5; padding: 2px 5px; border-radius: 3px; }
        .warning { background-color: #FFF3CD; padding: 10px; border-left: 4px solid #FFC107; }
    </style>
</head>
<body>
    <h2>Installation Information</h2>

    <h3>What will be installed:</h3>
    <ul>
        <li><strong>Application:</strong> /Applications/PHILAB.app</li>
        <li><strong>CLI Tool:</strong> /usr/local/bin/philab (symlink)</li>
        <li><strong>Data Directory:</strong> /usr/local/var/philab</li>
        <li><strong>Log Directory:</strong> /usr/local/var/log/philab</li>
    </ul>

    <h3>System Requirements:</h3>
    <ul>
        <li>macOS 10.14 (Mojave) or later</li>
        <li>Python 3.10 or later (for development)</li>
        <li>4 GB RAM minimum (8 GB recommended)</li>
        <li>2 GB free disk space</li>
    </ul>

    <h3>After Installation:</h3>
    <p>You can run PHILAB using:</p>
    <ul>
        <li><code>philab</code> command in Terminal</li>
        <li>Open PHILAB.app from Applications folder</li>
    </ul>

    <div class="warning">
        <strong>⚠️ Note:</strong> If you're upgrading from a previous version, your configuration files will be preserved.
    </div>
</body>
</html>
EOF

    # Conclusion
    cat > "$INSTALLERS_DIR/resources/conclusion.html" << 'EOF'
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 20px; }
        h1 { color: #34C759; }
        .success { background-color: #E8F5E9; padding: 15px; border-radius: 5px; }
        code { background-color: #F5F5F5; padding: 2px 5px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="success">
        <h1>✅ Installation Complete!</h1>
        <p>PHILAB has been successfully installed on your system.</p>
    </div>

    <h2>Getting Started:</h2>
    <ol>
        <li>Open Terminal and run: <code>philab --help</code></li>
        <li>Configure your environment variables (optional)</li>
        <li>Start exploring AI interpretability!</li>
    </ol>

    <h2>Resources:</h2>
    <ul>
        <li><strong>Documentation:</strong> <a href="https://github.com/E-TECH-PLAYTECH/PHILAB">github.com/E-TECH-PLAYTECH/PHILAB</a></li>
        <li><strong>Issues:</strong> <a href="https://github.com/E-TECH-PLAYTECH/PHILAB/issues">Report issues on GitHub</a></li>
    </ul>

    <p>Thank you for installing PHILAB!</p>
</body>
</html>
EOF

    log_success "Documentation resources created"
}

build_package() {
    log_info "Building package..."

    # Clean up old builds
    rm -rf "$INSTALLERS_DIR/component.pkg" "$INSTALLERS_DIR/philab-component.pkg" "$PKG_PATH"

    # Create component package
    local pkg_args=(
        --root "$DIST_DIR"
        --identifier "$BUNDLE_ID"
        --version "$VERSION"
        --scripts "$INSTALLERS_DIR/scripts"
        --install-location "/Applications"
    )

    if [ -n "$SIGN_IDENTITY" ]; then
        pkg_args+=(--sign "$SIGN_IDENTITY")
        log_info "Signing component package with: $SIGN_IDENTITY"
    fi

    pkgbuild "${pkg_args[@]}" "$INSTALLERS_DIR/philab-component.pkg"

    log_success "Component package created"

    # Create product package with distribution
    local product_args=(
        --distribution "$INSTALLERS_DIR/distribution.xml"
        --resources "$INSTALLERS_DIR/resources"
        --package-path "$INSTALLERS_DIR"
    )

    if [ -n "$SIGN_IDENTITY" ]; then
        product_args+=(--sign "$SIGN_IDENTITY")
        log_info "Signing product package with: $SIGN_IDENTITY"
    fi

    productbuild "${product_args[@]}" "$PKG_PATH"

    log_success "Product package created: $PKG_PATH"
}

verify_package() {
    log_info "Verifying package..."

    # Check if package exists
    if [ ! -f "$PKG_PATH" ]; then
        log_error "Package file not found"
        exit 1
    fi

    # Get package info
    pkgutil --check-signature "$PKG_PATH" || log_warning "Package is not signed"

    # Get package size
    pkg_size=$(du -sh "$PKG_PATH" | cut -f1)
    log_info "Package size: $pkg_size"

    log_success "Package verified"
}

print_next_steps() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                Package Created Successfully! 📦                 ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Package:${NC} $PKG_PATH"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "  1. Test the installer:"
    echo "     sudo installer -pkg \"$PKG_PATH\" -target /"
    echo ""
    echo "  2. Distribute via MDM (Jamf, Kandji, etc.)"
    echo ""
    echo "  3. Or create a DMG for user download:"
    echo "     ./macos/build-scripts/create-dmg.sh --pkg"
    echo ""

    if [ -z "$SIGN_IDENTITY" ]; then
        echo -e "${YELLOW}⚠️  Note:${NC} Package is not signed. For enterprise distribution, sign with:"
        echo "     ./create-pkg.sh --sign \"Developer ID Installer: Your Name (TEAM_ID)\""
        echo ""
    fi
}

###############################################################################
# Main Script
###############################################################################

main() {
    log_info "Starting PHILAB .pkg installer creation..."
    echo ""

    check_prerequisites
    create_installer_scripts
    create_distribution_xml
    create_documentation_resources
    build_package
    verify_package
    print_next_steps
}

# Run main function
main
