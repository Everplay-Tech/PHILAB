# PHILAB Installation Guide

## Easiest Method (macOS DMG)

1. Download the installer from our [Releases page](https://github.com/E-TECH-PLAYTECH/PHILAB/releases).
   - **Standard Installer**: `PHILAB-1.0.0-Installer.dmg` (Fast, Mock Model)
   - **Full Installer**: `PHILAB-1.0.0-with-Phi2-Installer.dmg` (Includes Phi-2 Model)
2. Open the DMG file.
3. Double-click the installer script inside.
4. Follow the prompts.

## Quick Install (Terminal)

### With Mock Model (Fast, ~500MB)
```bash
curl -fsSL https://raw.githubusercontent.com/E-TECH-PLAYTECH/PHILAB/main/install.sh | bash
```

### With Real Phi-2 Model (Complete, ~3.2GB total)
```bash
curl -fsSL https://raw.githubusercontent.com/E-TECH-PLAYTECH/PHILAB/main/install.sh | bash -s -- --with-phi2
```

## Manual Installation

### Option 1: Mock Model Only
```bash
git clone https://github.com/E-TECH-PLAYTECH/PHILAB.git
cd PHILAB
./install.sh
```

### Option 2: With Real Phi-2
```bash
git clone https://github.com/E-TECH-PLAYTECH/PHILAB.git
cd PHILAB
./install.sh --with-phi2
```

## What Gets Installed

### Mock Model Version:
- ✅ PHILAB framework and tools
- ✅ Mock Phi-2 model (for testing/demos)
- ✅ Web interface and CLI
- ❌ Real Phi-2 model (2.7GB)

### Real Phi-2 Version:
- ✅ Everything above
- ✅ Real Microsoft Phi-2 model
- ✅ Full AI capabilities
- ⚠️  Requires ~3.2GB total space

## Switching Between Mock/Real Models

After installation, you can switch at any time:

```bash
cd ~/PHILAB
./enable-phi2.sh    # Switch to real Phi-2
# OR
# Edit phi2_lab/config/app.yaml and set use_mock: false
```

## Running PHILAB

After installation:

1. **Double-click** `PHILAB.command` on your Desktop
2. **Or run:** `source ~/.philab/bin/activate && cd ~/PHILAB && python -m phi2_lab.geometry_viz.api`
3. **Open:** http://127.0.0.1:8000 in your browser

## Troubleshooting

- **Permission denied:** Run `chmod +x ~/PHILAB/*.sh`
- **Model download fails:** Check internet connection, may take 10-30 minutes
- **Port 8000 in use:** Change port in the launch command
