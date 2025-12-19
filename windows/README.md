# PHILAB Windows Installation

## A Note From the Developer

Hey Windows friends - I'll be honest with you: I don't have a proper Windows machine to test this on. These scripts were written with care and *should* work, but they haven't been battle-tested on real Windows hardware.

If you run into issues, please:
1. Open a GitHub issue with the error message
2. Let me know your Windows version and Python version
3. I'll do my best to fix it remotely

Pull requests from Windows users are especially welcome. You know your platform better than I do.

Sorry about that, and thanks for your patience.

---

## Quick Install

### Option 1: Double-Click (Easiest)

1. Double-click `install.bat`
2. Follow the prompts
3. A desktop shortcut will be created

### Option 2: PowerShell

```powershell
cd windows
powershell -ExecutionPolicy Bypass -File install.ps1
```

### Option 3: With Real Phi-2 Model (~2.7GB)

```powershell
powershell -ExecutionPolicy Bypass -File install.ps1 -WithPhi2
```

---

## Requirements

- Windows 10 or 11
- Python 3.10+ (download from https://python.org)
- ~5GB disk space

**Important**: When installing Python, check "Add Python to PATH"

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `install.bat` | Double-click installer (runs PowerShell script) |
| `install.ps1` | Main PowerShell installer |
| `enable-phi2.ps1` | Switch from mock data to real Phi-2 model |
| `WINDOWS_SETUP.md` | Detailed setup guide and troubleshooting |

---

## After Installation

1. Double-click the **PHILAB** shortcut on your Desktop
2. Open http://127.0.0.1:8000 in your browser
3. The GUI should load with mock data by default

---

## Troubleshooting

See `WINDOWS_SETUP.md` for detailed troubleshooting steps.

Common issues:
- **"Python not found"** - Install Python and check "Add to PATH"
- **"Execution policy"** - Run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- **Port 8000 in use** - Close other apps or change the port in the code

---

## Contributing

If you're a Windows user and want to help improve these scripts:
1. Fork the repo
2. Test the installation
3. Submit fixes via PR

Your contributions help make PHILAB accessible to everyone.
