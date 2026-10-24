# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['rubric_local\\app.py'],
    pathex=[],
    binaries=[],
    datas=[('bin', 'bin'), ('rubric.ico', '.')],
    hiddenimports=[
        'pystray',
        'pystray._win32',
        'PIL._tkinter_finder',
        'win32gui',
        'win32con',
        'win32api',
        'win32event',
        'winerror',
        'pywintypes'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Rubric-Local',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='test_build\\version_info.txt',
    icon=['rubric.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='Rubric-Local',
)
