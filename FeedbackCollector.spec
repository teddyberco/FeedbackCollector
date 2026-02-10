# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

import os
SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(SPEC_DIR, 'src', 'run_web.py')],
    pathex=[SPEC_DIR],
    binaries=[],
    datas=[
        (os.path.join(SPEC_DIR, 'src', 'templates'), 'templates'),
        (os.path.join(SPEC_DIR, 'src', 'static'), 'static'),
        (os.path.join(SPEC_DIR, 'src', 'categories.json'), '.'),
        (os.path.join(SPEC_DIR, 'src', 'impact_types.json'), '.'),
        (os.path.join(SPEC_DIR, 'src', 'keywords.json'), '.'),
        # .env is NOT bundled - place it next to FeedbackCollector.exe after build
    ],
    hiddenimports=[
        'praw',
        'requests',
        'pandas',
        'pyodbc',
        'flask',
        'jinja2',
        'waitress',
        'dotenv',
    ],
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
    name='FeedbackCollector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Show console for logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon path here if you have one
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FeedbackCollector',
)
