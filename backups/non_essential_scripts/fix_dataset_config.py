#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复云端数据集配置文件
"""

import paramiko
import json
import os
from datetime import datetime

def fix_cloud_dataset_config():
    """修复云端的dataset.yaml配置文件"""
    
    # 服务器配置
    server_config = {
        'hostname': '43.139.107.206',
        'port': 22,
        'username': 'root',
        'password': 'vonzeus01'
    }
    
    try:
        # 连接服务器
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**server_config, timeout=30)
        
        print("✓ 已连接到服务器")
        
        # 检查当前的dataset.yaml内容
        print("\n检查当前dataset.yaml内容...")
        stdin, stdout, stderr = ssh.exec_command('cat /root/yolo_dataset/dataset.yaml')
        current_content = stdout.read().decode('utf-8')
        error_content = stderr.read().decode('utf-8')
        
        if error_content:
            print(f"读取错误: {error_content}")
        
        print("当前dataset.yaml内容:")
        print("-" * 50)
        print(current_content)
        print("-" * 50)
        
        # 创建正确的dataset.yaml内容
        correct_yaml_content = """# YOLO数据集配置文件
# 自动生成时间: {timestamp}

# 数据集路径 (相对于此配置文件)
path: /root/yolo_dataset  # 数据集根目录
train: train/images       # 训练图片路径 (相对于path)
val: val/images          # 验证图片路径 (相对于path)
test: test/images        # 测试图片路径 (相对于path, 可选)

# 类别数量
nc: 5

# 类别名称
names:
  0: class_0
  1: class_1  
  2: class_2
  3: class_3
  4: class_4
""".format(timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        # 备份原文件
        print("\n备份原dataset.yaml文件...")
        backup_cmd = f'cp /root/yolo_dataset/dataset.yaml /root/yolo_dataset/dataset.yaml.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        stdin, stdout, stderr = ssh.exec_command(backup_cmd)
        stdout.read()  # 等待命令完成
        
        # 写入新的配置文件
        print("写入修复后的dataset.yaml...")
        
        # 使用echo命令写入文件
        escaped_content = correct_yaml_content.replace("'", "'\"'\"'")  # 转义单引号
        write_cmd = f"echo '{escaped_content}' > /root/yolo_dataset/dataset.yaml"
        stdin, stdout, stderr = ssh.exec_command(write_cmd)
        stdout.read()  # 等待命令完成
        
        # 验证写入结果
        print("\n验证修复后的dataset.yaml内容...")
        stdin, stdout, stderr = ssh.exec_command('cat /root/yolo_dataset/dataset.yaml')
        new_content = stdout.read().decode('utf-8')
        
        print("修复后的dataset.yaml内容:")
        print("-" * 50)
        print(new_content)
        print("-" * 50)
        
        # 检查数据集目录结构
        print("\n检查数据集目录结构...")
        stdin, stdout, stderr = ssh.exec_command('find /root/yolo_dataset -type d | head -20')
        dir_structure = stdout.read().decode('utf-8')
        print("目录结构:")
        print(dir_structure)
        
        # 检查图片文件数量
        print("\n检查图片文件数量...")
        stdin, stdout, stderr = ssh.exec_command('find /root/yolo_dataset -name "*.jpg" -o -name "*.png" | wc -l')
        image_count = stdout.read().decode('utf-8').strip()
        print(f"图片文件总数: {image_count}")
        
        # 检查标签文件数量
        stdin, stdout, stderr = ssh.exec_command('find /root/yolo_dataset -name "*.txt" | wc -l')
        label_count = stdout.read().decode('utf-8').strip()
        print(f"标签文件总数: {label_count}")
        
        ssh.close()
        print("\n✓ 数据集配置修复完成!")
        return True
        
    except Exception as e:
        print(f"修复失败: {e}")
        return False

if __name__ == "__main__":
    print("开始修复云端数据集配置...")
    success = fix_cloud_dataset_config()
    
    if success:
        print("\n修复完成！现在可以重新开始训练。")
    else:
        print("\n修复失败，请检查服务器连接和权限。")