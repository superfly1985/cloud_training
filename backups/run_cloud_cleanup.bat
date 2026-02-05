@echo off
echo ========================================
echo Cloud Server Cleanup Tool
echo ========================================
echo.

cd /d "%~dp0"

echo Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python not found
    echo Please install Python and add to PATH
    pause
    exit /b 1
)

echo Checking dependencies...
python -c "import paramiko" >nul 2>&1
if errorlevel 1 (
    echo Installing paramiko package...
    pip install paramiko
    if errorlevel 1 (
        echo Error: Failed to install paramiko
        echo Please run manually: pip install paramiko
        pause
        exit /b 1
    )
)

echo.
echo Important Notes:
echo 1. Edit cloud_config.json file first to configure server connection
echo 2. Confirm directories and file types to clean
echo 3. This operation will permanently delete cloud files
echo.

set /p confirm="Confirm configuration is ready and continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo Operation cancelled
    pause
    exit /b 0
)

echo.
echo Starting cloud cleanup tool...
python cloud_cleanup.py

echo.
echo Cleanup completed, press any key to exit...
pause >nul