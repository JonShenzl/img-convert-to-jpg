# -*- mode: python ; coding: utf-8 -*-
# Copyright (c) 2026 Jon.Shen (Jon.Shen@Foxmail.com)
# 自由复制、修改；禁止商业使用；整合或再分发需注明出处。

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'secrets', 'xml', 'xmlrpc', 'asyncio',
        'concurrent', 'multiprocessing', 'sqlite3',
        'unittest', 'doctest', 'pydoc', 'distutils',
        'setuptools', 'pkg_resources', 'pip', 'lib2to3',
        'numpy', 'pandas', 'matplotlib', 'IPython', 'pytest',
        'turtle', 'pystray',
        'PIL.ImageTk', 'PIL.ImageFont', 'PIL.ImageDraw',
        'PIL.ImageShow', 'PIL.ImageCms',
        'PIL.ImageQt', 'PIL.ImageEnhance',
        'PIL.AvifImagePlugin', 'PIL._avif',
    ],
    noarchive=False,
    optimize=2,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ImgConvertToJpg',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
    icon=['assets/app.ico'],
)
