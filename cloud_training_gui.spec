# -*- mode: python ; coding: utf-8 -*-

import os
import sys

# 获取当前脚本目录
current_dir = os.getcwd()

# 分析主程序
a = Analysis(
    ['cloud_training_gui.py'],
    pathex=[current_dir],
    binaries=[],
    datas=[
        # 包含配置文件模板
        ('cloud_training_config.json', '.') if os.path.exists('cloud_training_config.json') else None,
    ],
    hiddenimports=[
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'paramiko',
        'json',
        'threading',
        'datetime',
        'os',
        'sys',
        're',
        'time',
        'subprocess',
        'pathlib',
        'matplotlib',
        'matplotlib.pyplot',
        'matplotlib.backends.backend_tkagg',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'numpy',
        'cv2',
        'yaml',
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'cryptography',
        'bcrypt',
        'nacl',
        'six',
        'cffi',
        'pycparser',
        'pyasn1',
        'pyasn1_modules',
        'rsa',
        'ecdsa',
        'ed25519',
        'invoke',
        'fabric',
        'patchwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# 过滤掉None值
a.datas = [item for item in a.datas if item is not None]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='云端训练GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 设置为False隐藏控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='云端训练GUI'
)
