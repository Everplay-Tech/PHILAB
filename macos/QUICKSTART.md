# macOS Packaging - Quick Start Guide

Get started with PHILAB macOS packaging in 5 minutes!

## Easy Installation (Recommended)

For end users, use the one-click installer:

```bash
# Download and run the installer
curl -fsSL https://raw.githubusercontent.com/E-TECH-PLAYTECH/PHILAB/main/install.sh | bash
```

This automatically:
- Detects Apple Silicon (M1/M2/M3) or Intel Macs
- Installs Python 3.11+ if needed
- Sets up virtual environment
- Installs all dependencies
- Creates desktop shortcuts
- Downloads the latest PHILAB code

## For Developers: Build from Source

### Prerequisites

```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install PyInstaller
pip3 install pyinstaller

# Optional: Install create-dmg
brew install create-dmg
```

### Build Your First macOS App

#### Option 1: Using Makefile (Recommended)

```bash
# Build everything (app, pkg, dmg)
make macos-release

# Outputs in dist/:
# - PHILAB.app         (Application bundle)
# - PHILAB-1.0.0.pkg  (Installer package)
# - PHILAB-1.0.0.dmg  (Disk image)
```

#### Option 2: Step by Step

```bash
# 1. Build .app bundle
./macos/build-scripts/build-app.sh

# 2. Create .pkg installer
./macos/build-scripts/create-pkg.sh

# 3. Create .dmg disk image
./macos/build-scripts/create-dmg.sh
```

### Option 3: Easy Install Script

```bash
# Run the installer locally
make macos-install
```

## Test Your Build

```bash
# Test the app bundle
open dist/PHILAB.app

# Test the PKG installer
sudo installer -pkg dist/PHILAB-1.0.0.pkg -target /

# Test the CLI
philab --help
```

## For Production (Signed & Notarized)

```bash
# 1. Set up credentials
export APP_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"
export INSTALLER_IDENTITY="Developer ID Installer: Your Name (TEAM_ID)"
export APPLE_ID="your@email.com"
export TEAM_ID="YOUR_TEAM_ID"

# 2. Store notarization password (one-time)
xcrun notarytool store-credentials "PHILAB-Notarization" \
  --apple-id "$APPLE_ID" \
  --team-id "$TEAM_ID" \
  --password "xxxx-xxxx-xxxx-xxxx"

# 3. Build signed release
make macos-release-signed \
  APP_IDENTITY="$APP_IDENTITY" \
  INSTALLER_IDENTITY="$INSTALLER_IDENTITY" \
  APPLE_ID="$APPLE_ID" \
  TEAM_ID="$TEAM_ID"
```

## Common Commands

```bash
# Clean builds
make macos-clean

# Build just the app
make macos-app

# Build just the PKG
make macos-pkg

# Build just the DMG
make macos-dmg

# Install as service
make macos-install-service

# View all commands
make help | grep macos
```

## File Locations

After building:

```
dist/
├── PHILAB.app              # Standalone application
├── PHILAB-1.0.0.pkg       # Installer package
├── PHILAB-1.0.0.dmg       # Disk image
└── checksums.txt          # SHA-256 checksums

build/                      # Build artifacts (temporary)
macos/installers/          # Installer components (temporary)
```

## Distribution

### For Developers

Share the DMG:
```bash
# Upload dist/PHILAB-1.0.0.dmg to GitHub Releases
# Users download and drag to Applications
```

### For Enterprise

Deploy the PKG:
```bash
# Upload dist/PHILAB-1.0.0.pkg to your MDM
# Jamf, Kandji, Mosyle, Intune, etc.
```

### For Homebrew Users

Coming soon:
```bash
brew install --cask e-tech-playtech/philab/philab
```

## Troubleshooting

### Build fails

```bash
# Clean and retry
make macos-clean
pip3 install --upgrade pyinstaller
make macos-app-clean
```

### "App is damaged" error

```bash
# For testing only - remove quarantine
xattr -dr com.apple.quarantine /Applications/PHILAB.app

# Proper fix: Sign and notarize
make macos-sign ...
```

### Permission denied

```bash
# Make scripts executable
chmod +x macos/build-scripts/*.sh
```

## Next Steps

- **Read full documentation:** [macos/README.md](README.md)
- **Enterprise deployment:** [docs/MACOS_DEPLOYMENT.md](../docs/MACOS_DEPLOYMENT.md)
- **CI/CD setup:** [.github/workflows/macos-build.yml](../.github/workflows/macos-build.yml)

## Need Help?

- **Issues:** https://github.com/E-TECH-PLAYTECH/PHILAB/issues
- **Documentation:** https://github.com/E-TECH-PLAYTECH/PHILAB
- **Enterprise Support:** contact@e-tech-playtech.com

---

**Happy Building! 🚀**
