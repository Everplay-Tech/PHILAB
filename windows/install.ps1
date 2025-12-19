###############################################################################
# PHILAB Easy Installer for Windows
#
# This script provides a one-click installation for PHILAB on Windows.
# It handles dependency installation, virtual environment setup, and shortcut creation.
#
# Usage:
#   Right-click and "Run with PowerShell"
#   Or from terminal: powershell -ExecutionPolicy Bypass -File install.ps1 [options]
#
# Options:
#   -WithPhi2    Download and enable real Phi-2 model (~2.7GB)
#   -Help        Show help message
###############################################################################

param(
    [switch]$WithPhi2,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# Colors for output
function Write-Color {
    param(
        [string]$Text,
        [string]$Color = "White"
    )
    Write-Host $Text -ForegroundColor $Color
}

if ($Help) {
    Write-Host "PHILAB Installer for Windows"
    Write-Host ""
    Write-Host "Usage: install.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -WithPhi2    Download and enable real Phi-2 model (~2.7GB)"
    Write-Host "  -Help        Show this help message"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\install.ps1                    # Install with mock model"
    Write-Host "  .\install.ps1 -WithPhi2          # Install with real Phi-2 model"
    exit 0
}

Write-Color "Starting PHILAB installation for Windows..." "Green"

# Check Windows version
$osVersion = [Environment]::OSVersion.Version
if ($osVersion.Major -lt 10) {
    Write-Color "Warning: Windows $($osVersion.Major) detected. PHILAB requires Windows 10+ for best performance." "Yellow"
}

# Check for Python
$pythonCmd = $null
$pythonPaths = @(
    "python",
    "python3",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe"
)

foreach ($path in $pythonPaths) {
    try {
        $version = & $path --version 2>&1
        if ($version -match "Python 3\.(\d+)") {
            $minorVersion = [int]$Matches[1]
            if ($minorVersion -ge 10) {
                $pythonCmd = $path
                Write-Color "Found Python: $version" "Blue"
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Color "Python 3.10+ not found. Please install Python from https://www.python.org/downloads/" "Red"
    Write-Color "Make sure to check 'Add Python to PATH' during installation." "Yellow"
    Write-Host ""
    Write-Host "Press any key to open Python download page..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Start-Process "https://www.python.org/downloads/"
    exit 1
}

# Set installation directories
$philabHome = "$env:USERPROFILE\PHILAB"
$venvDir = "$env:USERPROFILE\.philab"

# Create virtual environment
Write-Color "Setting up virtual environment..." "Blue"
if (Test-Path $venvDir) {
    Write-Color "Removing existing virtual environment..." "Yellow"
    Remove-Item -Recurse -Force $venvDir
}
& $pythonCmd -m venv $venvDir

# Activate virtual environment
$activateScript = "$venvDir\Scripts\Activate.ps1"
. $activateScript

# Upgrade pip
Write-Color "Upgrading pip..." "Blue"
python -m pip install --upgrade pip

# Clone or update PHILAB
if (-not (Test-Path $philabHome)) {
    Write-Color "Downloading PHILAB..." "Blue"

    # Check for git
    try {
        $null = git --version
        git clone https://github.com/Everplay-Tech/PHILAB.git $philabHome
    } catch {
        Write-Color "Git not found. Downloading as ZIP..." "Yellow"
        $zipPath = "$env:TEMP\PHILAB.zip"
        Invoke-WebRequest -Uri "https://github.com/Everplay-Tech/PHILAB/archive/refs/heads/main.zip" -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath $env:TEMP -Force
        Move-Item "$env:TEMP\PHILAB-main" $philabHome
        Remove-Item $zipPath
    }
} else {
    Write-Color "Updating PHILAB..." "Blue"
    Set-Location $philabHome
    try {
        git pull
    } catch {
        Write-Color "Could not update via git. Continuing with existing files." "Yellow"
    }
}

Set-Location $philabHome

# Install dependencies
Write-Color "Installing dependencies..." "Blue"
pip install -e .

# Install ML dependencies
Write-Color "Installing ML dependencies (this may take a while)..." "Yellow"
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install transformers accelerate

# Create desktop shortcut
Write-Color "Creating desktop shortcut..." "Blue"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = "$desktopPath\PHILAB.lnk"

# Create launcher batch file
$launcherPath = "$philabHome\launch_philab.bat"
@"
@echo off
call "$venvDir\Scripts\activate.bat"
cd /d "$philabHome"
python -m phi2_lab.geometry_viz.api
"@ | Out-File -FilePath $launcherPath -Encoding ASCII

# Create shortcut using COM
$WScriptShell = New-Object -ComObject WScript.Shell
$shortcut = $WScriptShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $launcherPath
$shortcut.WorkingDirectory = $philabHome
$shortcut.Description = "Launch PHILAB Geometry Visualization"
$shortcut.Save()

# Create browser launcher
$browserLauncherPath = "$philabHome\open_philab.bat"
@"
@echo off
start http://127.0.0.1:8000
call "$venvDir\Scripts\activate.bat"
cd /d "$philabHome"
python -m phi2_lab.geometry_viz.api
"@ | Out-File -FilePath $browserLauncherPath -Encoding ASCII

# Enable Phi-2 if requested
if ($WithPhi2) {
    Write-Color "Enabling Phi-2 model..." "Blue"
    & "$philabHome\enable-phi2.ps1"
    Write-Host ""
}

Write-Color "Installation complete!" "Green"
Write-Host ""
Write-Color "To run PHILAB:" "Blue"
Write-Host "1. Double-click PHILAB shortcut on your Desktop"
Write-Host "2. Or run from PowerShell:"
Write-Host "   & `"$venvDir\Scripts\Activate.ps1`""
Write-Host "   cd `"$philabHome`""
Write-Host "   python -m phi2_lab.geometry_viz.api"
Write-Host ""
Write-Host "Then open http://127.0.0.1:8000 in your browser."
Write-Host ""
Write-Color "Note: First run may download model weights." "Yellow"

Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
