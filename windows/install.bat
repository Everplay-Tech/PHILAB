@echo off
REM PHILAB Easy Installer for Windows (Batch wrapper)
REM
REM This script launches the PowerShell installer with appropriate permissions.
REM Double-click this file to install PHILAB.

echo PHILAB Installer for Windows
echo ============================
echo.

REM Check for PowerShell
where powershell >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PowerShell is required but not found.
    echo Please install PowerShell or run the .ps1 script directly.
    pause
    exit /b 1
)

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Run the PowerShell installer
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Installation encountered an error.
    pause
)
