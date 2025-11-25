#!/bin/bash
set -e

VERSION="1.0.0"
WITH_PHI2=false

for arg in "$@"; do
    case $arg in
        --with-phi2)
            WITH_PHI2=true
            ;;
    esac
done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
DIST_DIR="$PROJECT_ROOT/dist"

if [ "$WITH_PHI2" = true ]; then
    DMG_NAME="PHILAB-${VERSION}-with-Phi2-Installer"
    VOLUME_NAME="PHILAB ${VERSION} (with Phi-2)"
    INSTALLER_SCRIPT="install-with-phi2.sh"
else
    DMG_NAME="PHILAB-${VERSION}-Installer"
    VOLUME_NAME="PHILAB ${VERSION} Installer"
    INSTALLER_SCRIPT="install.sh"
fi

echo "Creating PHILAB installer DMG..."

mkdir -p "$DIST_DIR"
TEMP_DIR=$(mktemp -d)
echo "Preparing DMG contents in: $TEMP_DIR"

cp "$PROJECT_ROOT/install.sh" "$TEMP_DIR/$INSTALLER_SCRIPT"
chmod +x "$TEMP_DIR/$INSTALLER_SCRIPT"

cat > "$TEMP_DIR/README.txt" << 'EOL'
PHILAB 1.0.0 Installer
EOL

if [ "$WITH_PHI2" = true ]; then
    echo "Includes Microsoft Phi-2 Model" >> "$TEMP_DIR/README.txt"
fi

cat >> "$TEMP_DIR/README.txt" << 'EOL'

To install PHILAB:

1. Double-click install.sh
2. Follow the installation prompts
EOL

if [ "$WITH_PHI2" = true ]; then
    echo "3. Phi-2 model will be downloaded (~2.7GB)" >> "$TEMP_DIR/README.txt"
fi

cat >> "$TEMP_DIR/README.txt" << 'EOL'

After installation, double-click "PHILAB.command" on your Desktop to start PHILAB.

For help: https://github.com/Everplay-Tech/PHILAB

---
PHILAB - AI Interpretability Lab
EOL

ln -s /Applications "$TEMP_DIR/Applications"

echo "Creating DMG: $DMG_NAME.dmg"

hdiutil create \
    -volname "$VOLUME_NAME" \
    -srcfolder "$TEMP_DIR/" \
    -ov \
    -format UDZO \
    "$DIST_DIR/$DMG_NAME.dmg"

rm -rf "$TEMP_DIR"

echo "✅ Installer DMG created: $DIST_DIR/$DMG_NAME.dmg"
echo "Size: $(du -h "$DIST_DIR/$DMG_NAME.dmg" | cut -f1)"
echo ""
echo "Users can now:"
echo "1. Download $DMG_NAME.dmg"
echo "2. Open the DMG"
echo "3. Double-click $INSTALLER_SCRIPT"
echo "4. PHILAB installs automatically!"
