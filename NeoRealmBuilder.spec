# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

excluded_binaries = [
    'opengl32sw.dll',
    'd3dcompiler_47.dll',
]

a = Analysis(
    ['src/main.py'],
    pathex=[
        '.',
        'src',
    ],
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeoRealmBuilder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep True for debugging
    disable_windowed_traceback=False,
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
    name='NeoRealmBuilder'
)