# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['src\\run_web.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src\\templates', 'templates'),
        ('src\\static', 'static'),
        ('src\\categories.json', '.'),
        ('src\\impact_types.json', '.'),
        ('src\\keywords.json', '.'),
        ('src\\.env', '.'),  # Include .env file in the build
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
