#!/usr/bin/env python3
"""
Python 3.9+ 包下载脚本
下载适用于Python 3.9及更高版本的机器学习包
"""

import os
import subprocess
import sys
import csv
from pathlib import Path

def log_message(message):
    """记录日志消息"""
    print(f"[INFO] {message}")

def run_command(command, description=""):
    """运行命令并返回结果"""
    log_message(f"执行命令: {command}")
    if description:
        log_message(f"描述: {description}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            log_message(f"命令执行成功")
            if result.stdout:
                log_message(f"输出: {result.stdout.strip()}")
            return True, result.stdout
        else:
            log_message(f"命令执行失败 (返回码: {result.returncode})")
            if result.stderr:
                log_message(f"错误: {result.stderr.strip()}")
            return False, result.stderr
    except subprocess.TimeoutExpired:
        log_message(f"命令执行超时")
        return False, "命令执行超时"
    except Exception as e:
        log_message(f"命令执行异常: {str(e)}")
        return False, str(e)

def download_packages():
    """下载Python 3.9+兼容的包"""
    
    # 设置下载目录
    download_dir = Path("Environment_package_python39")
    download_dir.mkdir(exist_ok=True)
    
    log_message(f"开始下载Python 3.9+兼容包到目录: {download_dir.absolute()}")
    
    # 读取包清单
    csv_file = "python39_packages_download_list.csv"
    if not os.path.exists(csv_file):
        log_message(f"错误: 找不到包清单文件 {csv_file}")
        return False
    
    packages_downloaded = 0
    packages_failed = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            package_name = row['包名']
            version = row['版本']
            platform = row['平台']
            abi = row['ABI']
            priority = row['优先级']
            compatibility = row['兼容性']
            download_command = row['下载命令']
            
            log_message(f"\n处理包: {package_name} v{version} ({compatibility})")
            log_message(f"优先级: {priority}")
            
            # 构建下载命令
            if download_command:
                # 添加目标目录到下载命令
                full_command = f"{download_command} --dest {download_dir}"
            else:
                # 备用下载命令
                if platform == "any":
                    full_command = f"pip download --platform any --python-version 3.9 --no-deps {package_name}=={version} --dest {download_dir}"
                else:
                    full_command = f"pip download --platform {platform} --python-version 3.9 --abi {abi} --no-deps {package_name}=={version} --dest {download_dir}"
            
            # 执行下载
            success, output = run_command(full_command, f"下载 {package_name}")
            
            if success:
                packages_downloaded += 1
                log_message(f"✓ {package_name} 下载成功")
            else:
                packages_failed += 1
                log_message(f"✗ {package_name} 下载失败")
                
                # 对于高优先级包，尝试备用下载方法
                if priority == "高":
                    log_message(f"尝试备用下载方法...")
                    backup_command = f"pip download --no-deps {package_name}=={version} --dest {download_dir}"
                    backup_success, backup_output = run_command(backup_command, f"备用下载 {package_name}")
                    
                    if backup_success:
                        packages_downloaded += 1
                        packages_failed -= 1
                        log_message(f"✓ {package_name} 备用下载成功")
                    else:
                        log_message(f"✗ {package_name} 备用下载也失败")
    
    # 下载总结
    log_message(f"\n=== 下载总结 ===")
    log_message(f"成功下载: {packages_downloaded} 个包")
    log_message(f"下载失败: {packages_failed} 个包")
    log_message(f"下载目录: {download_dir.absolute()}")
    
    # 检查下载的文件
    downloaded_files = list(download_dir.glob("*"))
    log_message(f"下载目录中的文件数量: {len(downloaded_files)}")
    
    if downloaded_files:
        log_message(f"下载的文件:")
        for file in downloaded_files:
            file_size = file.stat().st_size / (1024 * 1024)  # MB
            log_message(f"  - {file.name} ({file_size:.1f} MB)")
    
    return packages_failed == 0

def main():
    """主函数"""
    log_message("Python 3.9+ 包下载脚本启动")
    
    # 检查pip版本
    success, pip_version = run_command("pip --version", "检查pip版本")
    if not success:
        log_message("错误: 无法找到pip")
        return False
    
    # 升级pip
    log_message("升级pip到最新版本...")
    run_command("python -m pip install --upgrade pip", "升级pip")
    
    # 开始下载包
    success = download_packages()
    
    if success:
        log_message("\n✓ 所有包下载完成!")
        log_message("现在可以在GUI中测试Python 3.9+的包安装功能")
    else:
        log_message("\n✗ 部分包下载失败，请检查网络连接和包版本")
    
    return success

if __name__ == "__main__":
    main()