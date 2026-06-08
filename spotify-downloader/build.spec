# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Spotify Downloader.
Build command: pyinstaller build.spec
"""

import os
import importlib

# Find customtkinter installation path
ctk_path = os.path.dirname(importlib.import_module("customtkinter").__file__)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (ctk_path, 'customtkinter/'),
    ],
    hiddenimports=[
        'spotdl',
        'spotdl.download',
        'spotdl.providers',
        'spotdl.utils',
        'yt_dlp',
        'customtkinter',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SpotifyDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed mode (no terminal)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment when you have an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SpotifyDownloader',
)
