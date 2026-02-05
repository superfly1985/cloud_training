@echo off
REM 精准清理备份脚本
REM 创建时间: 2025-12-02 15:02:24

set BACKUP_DIR=d:\OneDrive\24.Visual AI\training_scripts\backups\non_essential_scripts

REM 创建备份目录
if not exist "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    echo 创建备份目录: %BACKUP_DIR%
)

echo 移动文件: cloud_cleanup.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\cloud_cleanup.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: cloud_cleanup.py
if errorlevel 0 echo 移动成功: cloud_cleanup.py

echo 移动文件: comprehensive_server_check.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\comprehensive_server_check.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: comprehensive_server_check.py
if errorlevel 0 echo 移动成功: comprehensive_server_check.py

echo 移动文件: create_training_script.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\create_training_script.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: create_training_script.py
if errorlevel 0 echo 移动成功: create_training_script.py

echo 移动文件: dataset_config_gui.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\dataset_config_gui.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: dataset_config_gui.py
if errorlevel 0 echo 移动成功: dataset_config_gui.py

echo 移动文件: final_compatibility_verification.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\final_compatibility_verification.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: final_compatibility_verification.py
if errorlevel 0 echo 移动成功: final_compatibility_verification.py

echo 移动文件: find_models.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\find_models.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: find_models.py
if errorlevel 0 echo 移动成功: find_models.py

echo 移动文件: fix_and_restart_training.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_and_restart_training.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_and_restart_training.py
if errorlevel 0 echo 移动成功: fix_and_restart_training.py

echo 移动文件: fix_backslash_files.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_backslash_files.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_backslash_files.py
if errorlevel 0 echo 移动成功: fix_backslash_files.py

echo 移动文件: fix_create_training_script_method.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_create_training_script_method.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_create_training_script_method.py
if errorlevel 0 echo 移动成功: fix_create_training_script_method.py

echo 移动文件: fix_dataset_structure.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_dataset_structure.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_dataset_structure.py
if errorlevel 0 echo 移动成功: fix_dataset_structure.py

echo 移动文件: fix_double_braces.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_double_braces.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_double_braces.py
if errorlevel 0 echo 移动成功: fix_double_braces.py

echo 移动文件: fix_dpkg_and_verify.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_dpkg_and_verify.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_dpkg_and_verify.py
if errorlevel 0 echo 移动成功: fix_dpkg_and_verify.py

echo 移动文件: fix_fstring_issue.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\fix_fstring_issue.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: fix_fstring_issue.py
if errorlevel 0 echo 移动成功: fix_fstring_issue.py

echo 移动文件: force_numpy_downgrade.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\force_numpy_downgrade.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: force_numpy_downgrade.py
if errorlevel 0 echo 移动成功: force_numpy_downgrade.py

echo 移动文件: generate_package_download_csv.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\generate_package_download_csv.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: generate_package_download_csv.py
if errorlevel 0 echo 移动成功: generate_package_download_csv.py

echo 移动文件: quick_server_check.py
move /Y "d:\OneDrive\24.Visual AI\training_scripts\quick_server_check.py" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: quick_server_check.py
if errorlevel 0 echo 移动成功: quick_server_check.py

echo 移动文件: cloud_cleanup_report_20250924_123815.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\cloud_cleanup_report_20250924_123815.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: cloud_cleanup_report_20250924_123815.json
if errorlevel 0 echo 移动成功: cloud_cleanup_report_20250924_123815.json

echo 移动文件: cloud_config.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\cloud_config.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: cloud_config.json
if errorlevel 0 echo 移动成功: cloud_config.json

echo 移动文件: compatibility_report_20250928_161044.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\compatibility_report_20250928_161044.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: compatibility_report_20250928_161044.json
if errorlevel 0 echo 移动成功: compatibility_report_20250928_161044.json

echo 移动文件: compatibility_report_20250928_161108.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\compatibility_report_20250928_161108.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: compatibility_report_20250928_161108.json
if errorlevel 0 echo 移动成功: compatibility_report_20250928_161108.json

echo 移动文件: dataset_structure_report_20250928_083008.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\dataset_structure_report_20250928_083008.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: dataset_structure_report_20250928_083008.json
if errorlevel 0 echo 移动成功: dataset_structure_report_20250928_083008.json

echo 移动文件: dataset_verification_report_20250928_163535.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\dataset_verification_report_20250928_163535.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: dataset_verification_report_20250928_163535.json
if errorlevel 0 echo 移动成功: dataset_verification_report_20250928_163535.json

echo 移动文件: python_compatibility_report.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\python_compatibility_report.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: python_compatibility_report.json
if errorlevel 0 echo 移动成功: python_compatibility_report.json

echo 移动文件: status_report.md
move /Y "d:\OneDrive\24.Visual AI\training_scripts\status_report.md" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: status_report.md
if errorlevel 0 echo 移动成功: status_report.md

echo 移动文件: training_progress_status.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\training_progress_status.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: training_progress_status.json
if errorlevel 0 echo 移动成功: training_progress_status.json

echo 移动文件: upload_progress.json
move /Y "d:\OneDrive\24.Visual AI\training_scripts\upload_progress.json" "%BACKUP_DIR%"
if errorlevel 1 echo 移动失败: upload_progress.json
if errorlevel 0 echo 移动成功: upload_progress.json


echo.
echo 清理完成！
echo 共移动 26 个文件到 %BACKUP_DIR%
echo 报告文件: d:\OneDrive\24.Visual AI\training_scripts\precise_cleanup_report.json
echo.
pause
