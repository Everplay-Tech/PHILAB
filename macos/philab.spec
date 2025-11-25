# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification for building the PHILAB macOS bundle.

The spec packages the command line entry point ``philab.cli`` into a console
binary named ``philab`` and bundles lightweight resources required by the
installer (LaunchDaemon template and configuration files).
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files
from PyInstaller.utils.hooks import collect_submodules

# PyInstaller executes .spec files in contexts where ``__file__`` may be
# undefined (for example, during ``pyinstaller`` invocation on macOS), so guard
# the path calculation to keep builds resilient.
if "__file__" in globals():
    project_root = Path(__file__).resolve().parent.parent
else:
    project_root = Path.cwd()
cli_entrypoint = project_root / "philab" / "cli.py"

# Collect package data so PyInstaller can bundle configuration files
package_datas = collect_data_files("phi2_lab")
package_datas.append(
    (
        str(project_root / "macos" / "templates" / "com.e-tech-playtech.philab.plist"),
        ".",
    )
)

# Discover dynamic imports from phi2_lab to keep the binary aligned with runtime
hidden_imports = collect_submodules("phi2_lab")

block_cipher = None

a = Analysis(
    [str(cli_entrypoint)],
    pathex=[str(project_root)],
    binaries=[],
    datas=package_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="philab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="philab",
)
app = BUNDLE(
    coll,
    name="PHILAB.app",
    icon=None,
    bundle_identifier="com.e-tech-playtech.philab",
)
