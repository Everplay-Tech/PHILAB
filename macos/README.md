# PHILAB macOS Packaging

This directory contains comprehensive macOS packaging and distribution infrastructure for PHILAB.

## Overview

PHILAB provides multiple installation methods for macOS:

1. **Direct App Bundle** - Standalone `.app` for drag-and-drop installation
2. **PKG Installer** - Enterprise-ready installer for MDM deployment
3. **DMG Disk Image** - Professional distribution format
4. **Homebrew** - Command-line installation via Homebrew

## Directory Structure

```
macos/
├── build-scripts/          # Build automation scripts
│   ├── build-app.sh       # Creates .app bundle using PyInstaller
│   ├── create-pkg.sh      # Creates .pkg installer
│   ├── create-dmg.sh      # Creates distributable DMG
│   ├── sign-and-notarize.sh  # Code signing and notarization
│   └── install-service.sh # Service installation
├── resources/             # Icons, backgrounds, and assets
├── templates/             # LaunchDaemon and configuration templates
├── installers/           # Generated installer files (temporary)
├── homebrew/             # Homebrew formula
└── philab.spec           # PyInstaller configuration

## Build Requirements

### System Requirements
- macOS 10.14 (Mojave) or later
- Xcode Command Line Tools
- Python 3.10 or later

### Installation Tools
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install PyInstaller
pip3 install pyinstaller

# Install create-dmg (optional, for professional DMGs)
brew install create-dmg
```

### Minimal local build (fresh clone)

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
make macos-app
```

### For Code Signing (Enterprise Only)
- Apple Developer Program membership
- Developer ID Application certificate
- Developer ID Installer certificate
- App-specific password for notarization

## Quick Start

### 1. Build Application Bundle

Create a standalone macOS .app:

```bash
cd /path/to/PHILAB
./macos/build-scripts/build-app.sh
```

Output: `dist/PHILAB.app`

Options:
- `--clean` - Clean previous builds
- `--dev` - Build with debug symbols

### 2. Create PKG Installer

Build an enterprise-ready .pkg installer:

```bash
./macos/build-scripts/create-pkg.sh
```

Output: `dist/PHILAB-1.0.0.pkg`

For signed installer:
```bash
./macos/build-scripts/create-pkg.sh --sign "Developer ID Installer: Your Name (TEAM_ID)"
```

### 3. Create DMG Disk Image

Create a distributable DMG:

```bash
./macos/build-scripts/create-dmg.sh
```

Output: `dist/PHILAB-1.0.0.dmg`

For signed DMG:
```bash
./macos/build-scripts/create-dmg.sh --sign "Developer ID Application: Your Name (TEAM_ID)"
```

### 4. Code Signing & Notarization

For public distribution on macOS 10.15+:

```bash
./macos/build-scripts/sign-and-notarize.sh \
  --app-identity "Developer ID Application: Your Name (TEAM_ID)" \
  --installer-identity "Developer ID Installer: Your Name (TEAM_ID)" \
  --apple-id "your@email.com" \
  --team-id "TEAM_ID" \
  --notarize --staple
```

For local development without a Developer ID Application certificate, enable developer mode to skip signing/notarization while still completing the build: `PHILAB_DEVELOPER_MODE=local ./macos/build-scripts/sign-and-notarize.sh`. For a fully signed and notarized build once you have the certificate, run: `./macos/build-scripts/sign-and-notarize.sh --app-identity "Developer ID Application: Your Name (TEAMID1234)" --bundle-id "com.yourcompany.philab" --apple-id "your-apple-id@example.com" --team-id "TEAMID1234" --notary-password "@keychain:APP_SPECIFIC_PASSWORD" --notarize --staple`.

## Complete Build Workflow

For a full production release:

```bash
# 1. Build app bundle
./macos/build-scripts/build-app.sh --clean

# 2. Sign and notarize the app
./macos/build-scripts/sign-and-notarize.sh \
  --app-identity "Developer ID Application: ..." \
  --apple-id "your@email.com" \
  --team-id "TEAM_ID" \
  --notarize --staple

# 3. Create PKG installer
./macos/build-scripts/create-pkg.sh \
  --sign "Developer ID Installer: ..."

# 4. Create DMG for download
./macos/build-scripts/create-dmg.sh \
  --sign "Developer ID Application: ..."
```

## Service Mode

PHILAB can run as a background service using LaunchDaemon.

### Install Service

```bash
sudo ./macos/build-scripts/install-service.sh
```

This will:
- Create service user `_philab`
- Install LaunchDaemon plist
- Create data and log directories
- Start the service automatically

### Manage Service

```bash
# Check status
sudo launchctl list | grep philab

# Stop service
sudo launchctl unload /Library/LaunchDaemons/com.e-tech-playtech.philab.plist

# Start service
sudo launchctl load /Library/LaunchDaemons/com.e-tech-playtech.philab.plist

# View logs
tail -f /usr/local/var/log/philab/stdout.log
tail -f /usr/local/var/log/philab/stderr.log
```

### Uninstall Service

```bash
sudo ./macos/build-scripts/install-service.sh --uninstall
```

## Homebrew Installation

### For End Users

Once published to a Homebrew tap:

```bash
# Add tap
brew tap e-tech-playtech/philab

# Install
brew install --cask philab

# Or install from main Homebrew (if accepted to homebrew-cask)
brew install --cask philab
```

### Publishing to Homebrew

1. Create a tap repository:
   ```bash
   # On GitHub, create: homebrew-philab
   ```

2. Add the formula:
   ```bash
   mkdir -p Casks
   cp macos/homebrew/philab.rb Casks/
   git add Casks/philab.rb
   git commit -m "Add PHILAB cask"
   git push
   ```

3. Calculate SHA256 for DMG:
   ```bash
   shasum -a 256 dist/PHILAB-1.0.0.dmg
   ```

4. Update the formula with the SHA256

5. Users can now install:
   ```bash
   brew install --cask e-tech-playtech/philab/philab
   ```

## Code Signing Setup

### 1. Get Developer ID Certificates

1. Join Apple Developer Program ($99/year)
2. In Xcode, go to Preferences → Accounts
3. Download certificates:
   - Developer ID Application (for .app and .dmg)
   - Developer ID Installer (for .pkg)

### 2. Create App-Specific Password

1. Go to https://appleid.apple.com/account/manage
2. Sign in
3. Under "Security" → "App-Specific Passwords"
4. Create new password

### 3. Store in Keychain

```bash
xcrun notarytool store-credentials "PHILAB-Notarization" \
  --apple-id "your@email.com" \
  --team-id "TEAM_ID" \
  --password "app-specific-password"
```

## Troubleshooting

### Build Fails - Missing Dependencies

```bash
# Install Python dependencies
pip3 install -r ../requirements.txt
pip3 install pyinstaller
```

### Code Signing Fails

```bash
# List available signing identities
security find-identity -v -p codesigning

# Verify certificate
security find-certificate -c "Developer ID Application"
```

### Notarization Fails

```bash
# Check notarization history
xcrun notarytool history --apple-id "your@email.com" --team-id "TEAM_ID"

# Get detailed log
xcrun notarytool log SUBMISSION_ID --apple-id "your@email.com" --team-id "TEAM_ID"
```

### App Won't Open - Gatekeeper

```bash
# Remove quarantine attribute (for testing only)
xattr -dr com.apple.quarantine /Applications/PHILAB.app

# Verify Gatekeeper status
spctl --assess -vv /Applications/PHILAB.app
```

## Distribution Checklist

Before releasing:

- [ ] App builds successfully
- [ ] All dependencies included
- [ ] Code signed with Developer ID
- [ ] Notarized by Apple
- [ ] DMG creates and mounts properly
- [ ] PKG installer works correctly
- [ ] Service mode installs and runs
- [ ] Uninstaller removes all files
- [ ] Tested on clean macOS installation
- [ ] Tested on minimum macOS version (10.14)
- [ ] Release notes written
- [ ] Documentation updated

## Enterprise Deployment

### Jamf Pro

1. Upload signed PKG to Jamf Pro
2. Create a policy for installation
3. Scope to target computers
4. Deploy

### Kandji

1. Add PKG to Library → Custom Apps
2. Configure auto-install
3. Assign to Blueprints

### Manual MDM

The signed PKG can be deployed via any MDM that supports:
- macOS package deployment
- LaunchDaemon configuration
- User/group creation

## CI/CD Integration

See `.github/workflows/macos-build.yml` for automated building:

```yaml
# Triggered on:
# - Push to main branch
# - Version tags (v*.*.*)
# - Manual workflow dispatch
```

The workflow:
1. Builds .app bundle
2. Signs with stored certificates
3. Creates PKG and DMG
4. Notarizes with Apple
5. Uploads artifacts to GitHub Releases

## Support

For issues with macOS packaging:
- GitHub Issues: https://github.com/E-TECH-PLAYTECH/PHILAB/issues
- Label: `macos`, `packaging`

## Resources

- [Apple Code Signing Guide](https://developer.apple.com/support/code-signing/)
- [Notarization Documentation](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [Homebrew Cask Cookbook](https://docs.brew.sh/Cask-Cookbook)
- [PyInstaller Manual](https://pyinstaller.org/en/stable/)

## License

MIT License - See LICENSE file in repository root
