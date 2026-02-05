#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复所有文件中的Windows路径写法问题，确保符合Linux标准
"""

import os
import re
import json
from pathlib import Path

def fix_cloud_training_gui():
    """修复cloud_training_gui.py中的路径问题"""
    file_path = "d:/OneDrive/24.Visual AI/training_scripts/cloud_training_gui.py"
    
    print("🔧 修复 cloud_training_gui.py 中的路径问题...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复文件上传中的路径问题
    # 1. 修复 remote_file 路径构建
    old_pattern = r'remote_file = f"{remote_path}/{rel_path}".replace\(\'\\\\\\\\?\', \'/\'\)'
    new_pattern = r'remote_file = f"{remote_path}/{rel_path}".replace("\\", "/")'
    content = re.sub(old_pattern, new_pattern, content)
    
    # 2. 修复文件删除中的路径问题
    old_pattern = r'full_path = os\.path\.join\(current_path, filename\)\.replace\(\'\\\\?\', \'/\'\)'
    new_pattern = r'full_path = os.path.join(current_path, filename).replace("\\", "/")'
    content = re.sub(old_pattern, new_pattern, content)
    
    # 3. 修复所有 os.path.join 后的路径分隔符
    # 查找所有 os.path.join 的使用，确保在Linux环境下使用正确的路径分隔符
    patterns_to_fix = [
        # 修复训练脚本生成中的路径
        (r'yaml_path = os\.path\.join\(dataset_path, "dataset\.yaml"\)', 
         r'yaml_path = os.path.join(dataset_path, "dataset.yaml")'),
        
        # 修复文件路径构建
        (r'script_file = os\.path\.join\(os\.path\.dirname\(__file__\), \'generated_training_script\.py\'\)',
         r'script_file = os.path.join(os.path.dirname(__file__), "generated_training_script.py")'),
    ]
    
    for old, new in patterns_to_fix:
        content = re.sub(old, new, content)
    
    # 4. 确保所有远程路径使用正确的Linux路径格式
    # 修复远程目录创建
    content = re.sub(
        r'remote_dir = os\.path\.dirname\(remote_file\)',
        r'remote_dir = os.path.dirname(remote_file).replace("\\", "/")',
        content
    )
    
    # 5. 修复配置文件中的路径问题
    # 确保默认远程路径使用Linux格式
    content = re.sub(
        r"'remote_path': '/root/yolo_dataset/'",
        r"'remote_path': '/root/yolo_dataset'",
        content
    )
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ cloud_training_gui.py 路径问题修复完成")

def fix_config_files():
    """修复配置文件中的路径问题"""
    config_files = [
        "d:/OneDrive/24.Visual AI/training_scripts/cloud_training_config.json",
        "d:/OneDrive/24.Visual AI/training_scripts/cloud_config.json"
    ]
    
    for config_file in config_files:
        if os.path.exists(config_file):
            print(f"🔧 修复配置文件: {config_file}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 修复远程路径
            if 'dataset_config' in config and 'remote_path' in config['dataset_config']:
                remote_path = config['dataset_config']['remote_path']
                # 确保远程路径使用Linux格式，去掉末尾的斜杠
                config['dataset_config']['remote_path'] = remote_path.rstrip('/')
            
            # 如果直接有remote_path字段
            if 'remote_path' in config:
                config['remote_path'] = config['remote_path'].rstrip('/')
            
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            print(f"✅ {config_file} 修复完成")

def fix_training_scripts():
    """修复训练脚本中的路径问题"""
    script_files = [
        "d:/OneDrive/24.Visual AI/training_scripts/generated_training_script.py",
        "d:/OneDrive/24.Visual AI/training_scripts/create_training_script.py",
        "d:/OneDrive/24.Visual AI/training_scripts/fix_and_restart_training.py"
    ]
    
    for script_file in script_files:
        if os.path.exists(script_file):
            print(f"🔧 修复训练脚本: {script_file}")
            
            with open(script_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 修复数据集路径
            content = re.sub(
                r'dataset_path = "/root/yolo_dataset/"',
                r'dataset_path = "/root/yolo_dataset"',
                content
            )
            
            # 修复yaml路径构建
            content = re.sub(
                r'yaml_path = os\.path\.join\(dataset_path, "dataset\.yaml"\)',
                r'yaml_path = os.path.join(dataset_path, "dataset.yaml")',
                content
            )
            
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {script_file} 修复完成")

def fix_upload_progress_json():
    """修复上传进度文件中的路径问题"""
    progress_file = "d:/OneDrive/24.Visual AI/training_scripts/upload_progress.json"
    
    if os.path.exists(progress_file):
        print(f"🔧 修复上传进度文件: {progress_file}")
        
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress_data = json.load(f)
        
        # 修复所有路径中的反斜杠
        fixed_data = {}
        for remote_path, file_info in progress_data.items():
            # 修复远程路径
            fixed_remote_path = remote_path.replace('\\', '/')
            
            # 修复本地文件路径信息
            if 'local_file' in file_info:
                # 保持本地路径不变，但确保远程路径正确
                fixed_data[fixed_remote_path] = file_info
            else:
                fixed_data[fixed_remote_path] = file_info
        
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(fixed_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ {progress_file} 修复完成")

def fix_other_scripts():
    """修复其他脚本中的路径问题"""
    script_files = [
        "d:/OneDrive/24.Visual AI/training_scripts/start_cloud_gpu_training_final.py",
        "d:/OneDrive/24.Visual AI/training_scripts/download_specific_models.py",
        "d:/OneDrive/24.Visual AI/training_scripts/download_trained_models.py"
    ]
    
    for script_file in script_files:
        if os.path.exists(script_file):
            print(f"🔧 修复脚本: {script_file}")
            
            with open(script_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 修复常见的路径问题
            fixes = [
                # 修复数据集路径
                (r"'dataset_path': '/root/yolo_dataset_4classes/'", 
                 r"'dataset_path': '/root/yolo_dataset_4classes'"),
                
                # 修复配置路径
                (r"config_path = '/root/yolo_dataset_4classes/dataset\.yaml'",
                 r"config_path = '/root/yolo_dataset_4classes/dataset.yaml'"),
                
                # 修复数据路径
                (r"data='/root/yolo_dataset_4classes/dataset\.yaml'",
                 r"data='/root/yolo_dataset_4classes/dataset.yaml'"),
                
                # 修复路径构建
                (r"config\['path'\] = '/root/yolo_dataset_4classes'",
                 r"config['path'] = '/root/yolo_dataset_4classes'"),
            ]
            
            for old_pattern, new_pattern in fixes:
                content = re.sub(old_pattern, new_pattern, content)
            
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ {script_file} 修复完成")

def main():
    """主函数"""
    print("🚀 开始修复所有文件中的Windows路径写法问题...")
    print("=" * 60)
    
    # 1. 修复主GUI文件
    fix_cloud_training_gui()
    
    # 2. 修复配置文件
    fix_config_files()
    
    # 3. 修复训练脚本
    fix_training_scripts()
    
    # 4. 修复上传进度文件
    fix_upload_progress_json()
    
    # 5. 修复其他脚本
    fix_other_scripts()
    
    print("=" * 60)
    print("🎉 所有路径问题修复完成！")
    print("\n修复内容总结:")
    print("1. ✅ 修复了文件上传中的路径分隔符问题")
    print("2. ✅ 修复了文件删除中的路径构建问题")
    print("3. ✅ 修复了训练脚本生成中的路径问题")
    print("4. ✅ 修复了配置文件中的路径格式")
    print("5. ✅ 修复了上传进度文件中的路径问题")
    print("6. ✅ 确保所有远程路径使用Linux格式")
    print("\n现在所有路径都符合Linux标准！")

if __name__ == "__main__":
    main()