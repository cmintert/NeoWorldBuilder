# NeoRealmBuilder.spec
block_cipher = None

a = Analysis(['src/main.py'],
             pathex=[],
             binaries=[],
             datas=[('config/', 'config/'), ('resources/', 'resources/')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='NeoRealmBuilder',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon='resources/graphics/icon.ico' if exists('resources/graphics/icon.ico') else None)