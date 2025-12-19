###############################################################################
# Enable Real Phi-2 Model for PHILAB (Windows)
#
# This script switches PHILAB from using the mock model to the real Phi-2 model.
# The real model will be downloaded on first use (~2.7GB).
#
# Usage: .\enable-phi2.ps1
###############################################################################

$ErrorActionPreference = "Stop"

$configFile = "$env:USERPROFILE\PHILAB\phi2_lab\config\app.yaml"

Write-Host "Enabling real Phi-2 model in PHILAB..."
Write-Host "This will download ~2.7GB of model weights on first use."
Write-Host ""

# Check if config file exists
if (-not (Test-Path $configFile)) {
    Write-Host "Error: Config file not found at $configFile" -ForegroundColor Red
    exit 1
}

# Backup original config
$backupFile = "$configFile.backup"
Copy-Item $configFile $backupFile

# Replace use_mock: true with use_mock: false
$content = Get-Content $configFile -Raw
$content = $content -replace 'use_mock: true', 'use_mock: false'
Set-Content -Path $configFile -Value $content

Write-Host "Phi-2 model enabled!" -ForegroundColor Green
Write-Host "Config updated: $configFile" -ForegroundColor Cyan
Write-Host "Backup saved: $backupFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next time you run PHILAB, it will download the real Phi-2 model."
Write-Host "This may take several minutes depending on your internet connection."
