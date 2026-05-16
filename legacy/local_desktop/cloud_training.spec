# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# 如果需要手动指定版本，可以在这里修改，或者通过环境变量传入
import os
version = os.environ.get('APP_VERSION', 'v3.0.8')
spec_dir = os.path.abspath(globals().get('SPECPATH', os.getcwd()))
main_script = os.path.join(spec_dir, 'main.py')
assets_dir = os.path.join(spec_dir, 'assets')

a = Analysis(
    [main_script],
    pathex=[spec_dir],
    binaries=[],
    datas=[(assets_dir, 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 本地 GUI 客户端不直接依赖这些重型推理库，排除可显著减小体积
        'torch',
        'torchvision',
        'torchaudio',
        'ultralytics',
        'cv2',
        'onnx',
        'onnxruntime',
        # 使用 TkAgg，不需要 Qt 相关后端
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'shiboken2',
        'shiboken6',
        'qtpy',
    ],
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
    name='云端训练',  # EXE 文件名不带版本号
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name=f'云端训练{version}',  # 文件夹名带版本号
)
