# -*- mode: python ; coding: utf-8 -*-

import json
import os
from pathlib import Path

# Create clean configuration files while preserving other settings
def create_clean_configs():
    # Read and update system.json
    system_config_path = Path('src/config/system.json')
    with open(system_config_path, 'r') as f:
        system_config = json.load(f)

    # Remove KEY for clean installation
    if "KEY" in system_config:
        del system_config["KEY"]

    # Read and update database.json
    database_config_path = Path('src/config/database.json')
    with open(database_config_path, 'r') as f:
        database_config = json.load(f)

    # Set empty password while preserving other settings
    database_config["PASSWORD"] = ""

    # Write updated configs
    with open(system_config_path, 'w') as f:
        json.dump(system_config, f, indent=4)

    with open(database_config_path, 'w') as f:
        json.dump(database_config, f, indent=4)

# Create clean configs before building
create_clean_configs()

block_cipher = None

# Separate our data files that we want to keep external
a = Analysis(
    ['src/main.py'],
    pathex=['.', 'src'],
    binaries=[],
    datas=[
        ('src/config', 'config'),
        ('src/resources', 'resources'),
    ],
    hiddenimports=[
        'config',
        'config.config',
        'core',
        'models',
        'services',
        'ui',
        'utils',
        'PyQt6.sip',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        '_tkinter',
        'sphinx',
        'test',
        'matplotlib',
        'notebook',
        'black'
    ],
)

pyz = PYZ(a.pure, a.zipped_data)

# Create only the collected version
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,    # Keep binaries separate
    name='NeoRealmBuilder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect everything in one directory
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NeoRealmBuilder'
)