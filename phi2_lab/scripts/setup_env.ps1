param(
    [string]$Python = "python",
    [string]$VenvDir = "$PSScriptRoot/../.venv"
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command $Python -ErrorAction SilentlyContinue)) {
    Write-Error "[setup_env] Python interpreter not found: $Python"
}

Write-Host "[setup_env] Creating virtual environment at $VenvDir"
& $Python -m venv $VenvDir

$activate = Join-Path $VenvDir "Scripts/Activate.ps1"
. $activate

python -m pip install --upgrade pip
python -m pip install --upgrade wheel setuptools

Write-Host "[setup_env] Installing phi2-lab in editable mode"
pip install -e (Join-Path $PSScriptRoot "..")

Write-Host "`n[setup_env] Environment ready."
Write-Host "To activate later: `"$activate`""
Write-Host "To run the smoke test: python $PSScriptRoot/self_check.py"
