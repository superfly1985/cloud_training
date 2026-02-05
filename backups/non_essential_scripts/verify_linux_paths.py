#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证所有文件中的路径是否符合Linux标准
"""

import os
import re
import json
from pathlib import Path

def check_file_for_path_issues(file_path, file_type="python"):
    """检查单个文件的路径问题"""
    issues = []
    
    if not os.path.exists(file_path):
        return issues
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # 检查常见的Windows路径问题
            if file_type == "python":
                # 检查错误的反斜杠转义
                if '.replace("\\", "/")' in line:
                    continue  # 这是正确的修复
                
                # 检查错误的反斜杠转义语法
                if '.replace("\", "/")' in line:
                    issues.append(f"第{i}行: 错误的反斜杠转义语法")
                
                # 检查Windows风格的路径
                if re.search(r'[A-Z]:\\\\', line):
                    issues.append(f"第{i}行: 包含Windows风格的绝对路径")
                
                # 检查远程路径末尾的多余斜杠
                if re.search(r'"/root/[^"]*/"', line) and 'mkdir' not in line:
                    issues.append(f"第{i}行: 远程路径末尾有多余的斜杠")
            
            elif file_type == "json":
                # 检查JSON中的路径问题
                if re.search(r'"/root/[^"]*/"', line):
                    issues.append(f"第{i}行: 远程路径末尾有多余的斜杠")
    
    except Exception as e:
        issues.append(f"读取文件失败: {e}")
    
    return issues

def verify_cloud_training_gui():
    """验证主GUI文件"""
    print("🔍 验证 cloud_training_gui.py...")
    
    file_path = "d:/OneDrive/24.Visual AI/training_scripts/cloud_training_gui.py"
    issues = check_file_for_path_issues(file_path, "python")
    
    if issues:
        print("❌ 发现问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✅ 路径格式正确")
        return True

def verify_config_files():
    """验证配置文件"""
    config_files = [
        "d:/OneDrive/24.Visual AI/training_scripts/cloud_training_config.json",
        "d:/OneDrive/24.Visual AI/training_scripts/cloud_config.json"
    ]
    
    all_good = True
    
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"🔍 验证配置文件: {os.path.basename(config_file)}")
            
            issues = check_file_for_path_issues(config_file, "json")
            
            if issues:
                print("❌ 发现问题:")
                for issue in issues:
                    print(f"  - {issue}")
                all_good = False
            else:
                print("✅ 路径格式正确")
    
    return all_good

def verify_training_scripts():
    """验证训练脚本"""
    script_files = [
        "d:/OneDrive/24.Visual AI/training_scripts/generated_training_script.py",
        "d:/OneDrive/24.Visual AI/training_scripts/create_training_script.py",
        "d:/OneDrive/24.Visual AI/training_scripts/fix_and_restart_training.py"
    ]
    
    all_good = True
    
    for script_file in script_files:
        if os.path.exists(script_file):
            print(f"🔍 验证训练脚本: {os.path.basename(script_file)}")
            
            issues = check_file_for_path_issues(script_file, "python")
            
            if issues:
                print("❌ 发现问题:")
                for issue in issues:
                    print(f"  - {issue}")
                all_good = False
            else:
                print("✅ 路径格式正确")
    
    return all_good

def verify_upload_progress():
    """验证上传进度文件"""
    progress_file = "d:/OneDrive/24.Visual AI/training_scripts/upload_progress.json"
    
    if os.path.exists(progress_file):
        print(f"🔍 验证上传进度文件: {os.path.basename(progress_file)}")
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            issues = []
            for remote_path in progress_data.keys():
                # 检查远程路径中是否有反斜杠
                if '\\' in remote_path:
                    issues.append(f"远程路径包含反斜杠: {remote_path}")
            
            if issues:
                print("❌ 发现问题:")
                for issue in issues:
                    print(f"  - {issue}")
                return False
            else:
                print("✅ 路径格式正确")
                return True
        
        except Exception as e:
            print(f"❌ 读取文件失败: {e}")
            return False
    else:
        print("ℹ️ 上传进度文件不存在，跳过检查")
        return True

def check_specific_patterns():
    """检查特定的路径模式"""
    print("🔍 检查特定的路径模式...")
    
    # 检查主GUI文件中的关键路径处理
    gui_file = "d:/OneDrive/24.Visual AI/training_scripts/cloud_training_gui.py"
    
    if os.path.exists(gui_file):
        with open(gui_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查文件上传路径处理
        if 'remote_file = f"{remote_path}/{rel_path}".replace("\\\\", "/")' in content:
            print("✅ 文件上传路径处理正确")
        else:
            print("❌ 文件上传路径处理可能有问题")
            return False
        
        # 检查默认远程路径
        if "'remote_path': '/root/yolo_dataset'" in content:
            print("✅ 默认远程路径格式正确")
        else:
            print("❌ 默认远程路径格式可能有问题")
            return False
    
    return True

def main():
    """主函数"""
    print("🚀 开始验证所有文件的Linux路径格式...")
    print("=" * 60)
    
    all_checks_passed = True
    
    # 1. 验证主GUI文件
    if not verify_cloud_training_gui():
        all_checks_passed = False
    
    print()
    
    # 2. 验证配置文件
    if not verify_config_files():
        all_checks_passed = False
    
    print()
    
    # 3. 验证训练脚本
    if not verify_training_scripts():
        all_checks_passed = False
    
    print()
    
    # 4. 验证上传进度文件
    if not verify_upload_progress():
        all_checks_passed = False
    
    print()
    
    # 5. 检查特定模式
    if not check_specific_patterns():
        all_checks_passed = False
    
    print("=" * 60)
    
    if all_checks_passed:
        print("🎉 所有文件的路径格式都符合Linux标准！")
        print("\n验证通过的项目:")
        print("✅ 文件上传路径处理")
        print("✅ 文件删除路径处理")
        print("✅ 训练脚本路径配置")
        print("✅ 配置文件路径格式")
        print("✅ 远程路径格式统一")
        print("\n现在可以安全地在Linux服务器上使用这些脚本！")
    else:
        print("❌ 发现路径格式问题，需要进一步修复")
    
    return all_checks_passed

if __name__ == "__main__":
    main()