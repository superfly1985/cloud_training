@echo off
chcp 65001 >nul
echo ========================================
echo 自动化云端训练启动脚本
echo ========================================
echo 服务器: 152.136.245.138
echo 用户: root
echo 密码: Vonzeus01
echo 训练脚本: cloud_train_20250922_114614.py
echo ========================================

echo.
echo 步骤 1: 连接服务器并启动训练...
echo.

REM 创建临时SSH脚本
echo cd /root > temp_commands.txt
echo python cloud_train_20250922_114614.py >> temp_commands.txt

echo 正在连接服务器并执行训练...
echo 请在SSH连接后手动执行以下命令:
echo.
echo cd /root
echo python cloud_train_20250922_114614.py
echo.
echo 按任意键连接到服务器...
pause >nul

REM 尝试SSH连接
ssh root@152.136.245.138

echo.
echo 如果SSH连接失败，请手动执行以下步骤:
echo 1. 使用SSH客户端连接: ssh root@152.136.245.138
echo 2. 输入密码: Vonzeus01
echo 3. 执行命令: cd /root
echo 4. 执行命令: python cloud_train_20250922_114614.py
echo.
echo 训练完成后，模型将保存为: pin_detector_20250922_114614.pt
echo.

REM 清理临时文件
if exist temp_commands.txt del temp_commands.txt

pause