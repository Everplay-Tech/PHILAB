# PHILAB Windows Setup Guide

This guide covers installing and running PHILAB on Windows 10/11.

## Prerequisites

- **Windows 10** or **Windows 11**
- **Python 3.10+** (3.11 recommended)
- ~5GB free disk space (more if downloading Phi-2 model)

## Quick Install

### Option 1: Double-click installer (Easiest)

1. Download the repository as ZIP from GitHub
2. Extract to a folder
3. Double-click `install.bat`
4. Follow the prompts

### Option 2: PowerShell (Recommended)

```powershell
# Open PowerShell as Administrator (optional but recommended)
# Navigate to the PHILAB folder, then run:
powershell -ExecutionPolicy Bypass -File install.ps1

# To include real Phi-2 model (~2.7GB download):
powershell -ExecutionPolicy Bypass -File install.ps1 -WithPhi2
```

### Option 3: Manual Setup

```powershell
# 1. Clone or download PHILAB
git clone https://github.com/Everplay-Tech/PHILAB.git
cd PHILAB

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install --upgrade pip
pip install -e .
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate

# 4. Run the geometry visualization
python -m phi2_lab.geometry_viz.api

# 5. Open browser to http://127.0.0.1:8000
```

## Running PHILAB

After installation, you have several options:

### Desktop Shortcut
Double-click the **PHILAB** shortcut on your Desktop.

### Command Line
```powershell
# Activate the virtual environment
& "$env:USERPROFILE\.philab\Scripts\Activate.ps1"

# Navigate to PHILAB
cd "$env:USERPROFILE\PHILAB"

# Run the geometry visualization server
python -m phi2_lab.geometry_viz.api
```

Then open http://127.0.0.1:8000 in your browser.

## Enabling Real Phi-2 Model

By default, PHILAB runs with mock data. To enable the real Phi-2 model:

```powershell
# From the PHILAB directory:
.\enable-phi2.ps1
```

This will:
- Update the config to use real Phi-2
- Download ~2.7GB of model weights on first run
- Provide full activation capture capabilities

## Troubleshooting

### Python not found

1. Download Python from https://www.python.org/downloads/
2. **Important**: Check "Add Python to PATH" during installation
3. Restart your terminal and try again

### PowerShell execution policy error

Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### pip install fails with SSL error

Try:
```powershell
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org <package>
```

### torch installation fails

For older GPUs or CPU-only systems:
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

For NVIDIA GPU with CUDA:
```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### Port 8000 already in use

Either stop the other service using port 8000, or modify the API to use a different port:
```powershell
# In phi2_lab/geometry_viz/api.py, change the port:
uvicorn.run(app, host="127.0.0.1", port=8001)
```

### Browser doesn't open automatically

Manually navigate to http://127.0.0.1:8000 in your browser.

## Directory Structure

After installation:
```
%USERPROFILE%\
├── .philab\              # Virtual environment
│   └── Scripts\
│       └── activate.bat
└── PHILAB\               # Main repository
    ├── phi2_lab\
    │   ├── geometry_viz\ # Dashboard code
    │   └── config\       # Configuration files
    ├── install.ps1       # PowerShell installer
    ├── install.bat       # Batch wrapper
    └── enable-phi2.ps1   # Enable real model
```

## Differences from macOS

| Feature | macOS | Windows |
|---------|-------|---------|
| Installer | `./install.sh` | `install.bat` or `install.ps1` |
| Enable Phi-2 | `./enable-phi2.sh` | `.\enable-phi2.ps1` |
| Venv location | `~/.philab` | `%USERPROFILE%\.philab` |
| Desktop shortcut | `.command` file | `.lnk` shortcut |
| Activate venv | `source .../activate` | `.../Activate.ps1` |

## Need Help?

- Check the main [README.md](README.md) for general documentation
- File issues on GitHub for bugs or questions
- The mock mode works without any model downloads - great for testing
