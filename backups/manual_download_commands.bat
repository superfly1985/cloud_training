@echo off
echo 开始下载项目所需的Python包...
echo.

REM 设置下载目录
set DOWNLOAD_DIR=D:\OneDrive\24.Visual AI\training_scripts\Environment_package
if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"
cd /d "%DOWNLOAD_DIR%"

echo 当前下载目录: %DOWNLOAD_DIR%
echo.

REM 升级pip
echo 升级pip...
python -m pip install --upgrade pip
echo.

REM 下载PyTorch包 (CPU版本)
echo 下载PyTorch包...
python -m pip download torch==2.0.1 torchvision==0.15.2 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cpu --dest "%DOWNLOAD_DIR%"
echo.

REM 下载Ultralytics
echo 下载Ultralytics...
python -m pip download ultralytics==8.0.196 --dest "%DOWNLOAD_DIR%"
python -m pip download ultralytics --dest "%DOWNLOAD_DIR%"
echo.

REM 下载NetworkX
echo 下载NetworkX...
python -m pip download networkx==2.8.8 --dest "%DOWNLOAD_DIR%"
python -m pip download networkx --dest "%DOWNLOAD_DIR%"
echo.

REM 下载核心依赖包
echo 下载核心依赖包...
python -m pip download numpy opencv-python pillow matplotlib scipy pandas --dest "%DOWNLOAD_DIR%"
echo.

REM 下载工具包
echo 下载工具包...
python -m pip download requests tqdm pyyaml seaborn psutil thop --dest "%DOWNLOAD_DIR%"
echo.

REM 下载PyTorch依赖包
echo 下载PyTorch依赖包...
python -m pip download filelock jinja2 sympy typing-extensions --dest "%DOWNLOAD_DIR%"
echo.

REM 下载机器学习包
echo 下载机器学习包...
python -m pip download scikit-learn scikit-image albumentations imgaug --dest "%DOWNLOAD_DIR%"
echo.

REM 下载实验跟踪包
echo 下载实验跟踪包...
python -m pip download tensorboard wandb clearml --dest "%DOWNLOAD_DIR%"
echo.

REM 下载基础包管理工具
echo 下载基础包管理工具...
python -m pip download setuptools wheel --dest "%DOWNLOAD_DIR%"
echo.

echo 所有包下载完成！
echo 下载位置: %DOWNLOAD_DIR%
echo.
echo 查看下载的文件:
dir "%DOWNLOAD_DIR%\*.whl" /b
echo.
pause