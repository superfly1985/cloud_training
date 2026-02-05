@echo off
echo 启动云端训练脚本优化GUI界面...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 切换到脚本目录
cd /d "%~dp0"

REM 检查并安装依赖
echo 检查依赖包...
pip install -r requirements_gui.txt

REM 启动GUI应用
echo 启动GUI应用...
python cloud_training_gui.py

pause