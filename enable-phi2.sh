#!/bin/bash
###############################################################################
# Enable Real Phi-2 Model for PHILAB
#
# This script switches PHILAB from using the mock model to the real Phi-2 model.
# The real model will be downloaded on first use (~2.7GB).
#
# Usage: ./enable-phi2.sh
###############################################################################

set -e

CONFIG_FILE="$HOME/PHILAB/phi2_lab/config/app.yaml"

echo "Enabling real Phi-2 model in PHILAB..."
echo "This will download ~2.7GB of model weights on first use."
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Backup original config
cp "$CONFIG_FILE" "$CONFIG_FILE.backup"

# Replace use_mock: true with use_mock: false
sed -i '' 's/use_mock: true/use_mock: false/' "$CONFIG_FILE"

echo "✅ Phi-2 model enabled!"
echo "📁 Config updated: $CONFIG_FILE"
echo "💾 Backup saved: $CONFIG_FILE.backup"
echo ""
echo "Next time you run PHILAB, it will download the real Phi-2 model."
echo "This may take several minutes depending on your internet connection."
