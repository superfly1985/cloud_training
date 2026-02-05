#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精准清理脚本 - 基于cloud_training_gui.py实际依赖分析
仅移动非必需文件，保留核心功能文件
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

class PreciseCleanupManager:
    def __init__(self):
        self.base_dir = Path(r"d:\OneDrive\24.Visual AI\training_scripts")
        self.backup_dir = self.base_dir / "backups" / "non_essential_scripts"
        self.report_file = self.base_dir / "precise_cleanup_report.json"
        
        # cloud_training_gui.py 核心必需文件
        self.core_files = {
            "cloud_training_gui.py",
            "cloud_training_config.json",
            "generated_training_script.py",  # 由GUI生成
            "start_cloud_gpu_training_final.py"  # 云端训练启动脚本
        }
        
        # 依赖的检查工具（建议保留）
        self.essential_checkers = {
            "check_config.py",
            "check_python_packages.py", 
            "check_server_status.py",
            "check_dataset_structure.py",
            "check_matplotlib_installation.py",
            "check_python_compatibility.py",
            "check_package_locations.py",
            "check_training_logs.py"
        }
        
        # 保留的核心文件（必需+建议保留）
        self.keep_files = self.core_files.union(self.essential_checkers)
        
        # 需要清理的文件模式
        self.cleanup_patterns = [
            "fix_*.py",
            "auto_*.py", 
            "download_*.py",
            "create_*.py",
            "remove_*.py",
            "update_*.py",
            "reinstall_*.py",
            "practical_*.py",
            "simple_*.py",
            "real_time_*.py",
            "optimized_*.py",
            "move_*.py",
            "verify_*.py",
            "find_*.py",
            "force_*.py",
            "comprehensive_*.py",
            "quick_*.py",
            "dataset_config_gui.py",
            "cloud_cleanup.py",
            "final_compatibility_verification.py",
            "generate_package_download_csv.py",
            "fix_*.py",
            "create_training_script.py",
            "fix_and_restart_training.py",
            "*.txt",
            "*.md",
            "*.json"
        ]
        
        self.cleanup_report = {
            "cleanup_date": datetime.now().isoformat(),
            "base_directory": str(self.base_dir),
            "backup_directory": str(self.backup_dir),
            "files_to_move": [],
            "files_to_keep": [],
            "statistics": {}
        }
    
    def scan_files(self):
        """扫描目录并分类文件"""
        python_files = []
        other_files = []
        
        # 获取所有Python文件和其他文件
        for item in self.base_dir.glob("*"):
            if item.is_file():
                if item.suffix == ".py":
                    python_files.append(item.name)
                elif item.suffix in [".txt", ".md", ".json"]:
                    other_files.append(item.name)
        
        # 分类处理
        files_to_move = []
        files_to_keep = []
        
        # 处理Python文件
        for py_file in python_files:
            if py_file in self.keep_files:
                files_to_keep.append(py_file)
            else:
                # 检查是否匹配清理模式
                should_cleanup = False
                for pattern in self.cleanup_patterns:
                    if pattern.startswith("*."):
                        # 扩展名模式
                        if py_file.endswith(pattern[1:]):
                            should_cleanup = True
                            break
                    else:
                        # 通配符模式
                        import fnmatch
                        if fnmatch.fnmatch(py_file, pattern):
                            should_cleanup = True
                            break
                
                if should_cleanup:
                    files_to_move.append(py_file)
                else:
                    files_to_keep.append(py_file)
        
        # 处理其他文件
        for other_file in other_files:
            # 保留cloud_training_config.json
            if other_file == "cloud_training_config.json":
                files_to_keep.append(other_file)
            else:
                files_to_move.append(other_file)
        
        self.cleanup_report["files_to_move"] = sorted(files_to_move)
        self.cleanup_report["files_to_keep"] = sorted(files_to_keep)
        self.cleanup_report["statistics"] = {
            "total_python_files": len(python_files),
            "total_other_files": len(other_files),
            "files_to_move_count": len(files_to_move),
            "files_to_keep_count": len(files_to_keep)
        }
        
        return files_to_move, files_to_keep
    
    def create_backup_script(self, files_to_move):
        """创建备份脚本"""
        batch_content = f"""@echo off
REM 精准清理备份脚本
REM 创建时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

set BACKUP_DIR={self.backup_dir}

REM 创建备份目录
if not exist "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    echo 创建备份目录: %BACKUP_DIR%
)

"""
        
        # 添加移动命令
        for file_name in files_to_move:
            source_path = self.base_dir / file_name
            batch_content += f'echo 移动文件: {file_name}\n'
            batch_content += f'move /Y "{source_path}" "%BACKUP_DIR%"\n'
            batch_content += f'if errorlevel 1 echo 移动失败: {file_name}\n'
            batch_content += f'if errorlevel 0 echo 移动成功: {file_name}\n'
            batch_content += "\n"
        
        batch_content += f"""
echo.
echo 清理完成！
echo 共移动 {len(files_to_move)} 个文件到 %BACKUP_DIR%
echo 报告文件: {self.report_file}
echo.
pause
"""
        
        batch_file = self.base_dir / "precise_cleanup.bat"
        with open(batch_file, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        
        return batch_file
    
    def save_report(self):
        """保存清理报告"""
        with open(self.report_file, 'w', encoding='utf-8') as f:
            json.dump(self.cleanup_report, f, ensure_ascii=False, indent=2)
    
    def print_analysis(self):
        """打印分析结果"""
        print("=" * 60)
        print("精准清理分析结果")
        print("=" * 60)
        print(f"基础目录: {self.base_dir}")
        print(f"备份目录: {self.backup_dir}")
        print()
        
        stats = self.cleanup_report["statistics"]
        print(f"Python文件总数: {stats['total_python_files']}")
        print(f"其他文件总数: {stats['total_other_files']}")
        print(f"待移动文件数: {stats['files_to_move_count']}")
        print(f"保留文件数: {stats['files_to_keep_count']}")
        print()
        
        print("核心必需文件:")
        for file in sorted(self.core_files):
            print(f"  ✓ {file}")
        print()
        
        print("建议保留的检查工具:")
        for file in sorted(self.essential_checkers):
            print(f"  ○ {file}")
        print()
        
        print("待移动文件:")
        for file in self.cleanup_report["files_to_move"]:
            print(f"  → {file}")
        print()
        
        print("保留文件:")
        for file in self.cleanup_report["files_to_keep"]:
            print(f"  ★ {file}")

def main():
    """主函数"""
    print("开始执行精准清理分析...")
    
    manager = PreciseCleanupManager()
    
    # 扫描文件
    files_to_move, files_to_keep = manager.scan_files()
    
    # 打印分析结果
    manager.print_analysis()
    
    # 创建备份脚本
    batch_file = manager.create_backup_script(files_to_move)
    print(f"\n批处理脚本已创建: {batch_file}")
    
    # 保存报告
    manager.save_report()
    print(f"清理报告已保存: {manager.report_file}")
    
    print("\n分析完成！")
    print("请查看precise_cleanup.bat文件，确认无误后执行清理操作")
    print("执行命令: .\\precise_cleanup.bat")

if __name__ == "__main__":
    main()