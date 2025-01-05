# -*- mode: python ; coding: utf-8 -*-

import sys
import os
from pathlib import Path
import structlog
import uuid

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ]
)

# Initialize logger
logger = structlog.get_logger().bind(
    module="NeoWorldBuilder.spec",
    trace_id=str(uuid.uuid4())
)

logger.info("spec_file_processing_started")

# Important: SPECPATH is already the project root
project_root = SPECPATH
src_dir = os.path.join(project_root, 'src')
main_script = os.path.join(src_dir, 'main.py')

logger.info("paths_determined",
            project_root=project_root,
            src_dir=src_dir,
            main_script=main_script)

# Verify paths exist
if not os.path.exists(src_dir):
    logger.error("source_directory_missing", path=src_dir)
    raise FileNotFoundError(
        f"Source directory not found at {src_dir}. Please ensure the 'src' directory "
        f"exists in {project_root} and contains main.py"
    )
if not os.path.exists(main_script):
    logger.error("main_script_missing", path=main_script)
    raise FileNotFoundError(
        f"Main script not found at {main_script}. Please ensure main.py exists in the src directory"
    )

# Determine which config directory to use
deploy_config = os.environ.get('NEOWORLDBUILDER_DEPLOY_CONFIG')
config_dir = deploy_config if deploy_config else os.path.join(src_dir, 'config')

# Additional data files to include
additional_datas = [
    (config_dir, 'config'),
    (os.path.join(config_dir, 'styles'), 'config/styles'),
    (os.path.join(src_dir, 'resources'), 'resources'),
]

# Additional hidden imports
hidden_imports = [
    'config',
    'config.config',
    'core',
    'models',
    'services',
    'ui',
    'utils',
    'PyQt6.sip',
    'neo4j',
    'structlog',
    'reportlab',
    'shapely',
    'pandas',
    'networkx',
]

# Create the Analysis object
a = Analysis(
    [main_script],
    pathex=[project_root, src_dir],
    binaries=[],
    datas=additional_datas,
    hiddenimports=hidden_imports,
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
        'black',
        'ipython',
        'jupyter',
    ],
    noarchive=False,
)

# Create the PYZ archive
pyz = PYZ(a.pure, a.zipped_data)

# Simple executable properties without version info
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeoWorldBuilder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# Collect all files
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NeoWorldBuilder'
)

logger.info("spec_file_processing_completed")