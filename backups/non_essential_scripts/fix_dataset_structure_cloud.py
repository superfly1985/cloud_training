#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复云端数据集目录结构
"""

import paramiko
import time

def fix_cloud_dataset_structure():
    """修复云端数据集目录结构"""
    
    # 服务器配置
    server_config = {
        'hostname': '152.136.245.138',
        'port': 22,
        'username': 'root',
        'password': 'Vonzeus01'
    }
    
    try:
        # 连接服务器
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**server_config, timeout=30)
        
        print("✓ 已连接到服务器")
        
        # 1. 创建正确的目录结构
        print("\n📁 创建正确的目录结构...")
        create_dirs_commands = [
            "mkdir -p /root/yolo_dataset/images/train",
            "mkdir -p /root/yolo_dataset/images/val", 
            "mkdir -p /root/yolo_dataset/images/test",
            "mkdir -p /root/yolo_dataset/labels/train",
            "mkdir -p /root/yolo_dataset/labels/val",
            "mkdir -p /root/yolo_dataset/labels/test"
        ]
        
        for cmd in create_dirs_commands:
            print(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.channel.recv_exit_status()  # 等待命令完成
        
        # 2. 移动训练集图片
        print("\n🚚 移动训练集图片...")
        move_commands = [
            # 移动训练集图片
            "find /root/yolo_dataset -path '*/train\\images/*' -name '*.jpg' -exec mv {} /root/yolo_dataset/images/train/ \\;",
            # 移动训练集标签
            "find /root/yolo_dataset -path '*/train\\labels/*' -name '*.txt' -exec mv {} /root/yolo_dataset/labels/train/ \\;",
            # 移动验证集图片
            "find /root/yolo_dataset -path '*/val\\images/*' -name '*.jpg' -exec mv {} /root/yolo_dataset/images/val/ \\;",
            # 移动验证集标签
            "find /root/yolo_dataset -path '*/val\\labels/*' -name '*.txt' -exec mv {} /root/yolo_dataset/labels/val/ \\;",
            # 移动测试集图片
            "find /root/yolo_dataset -path '*/test\\images/*' -name '*.jpg' -exec mv {} /root/yolo_dataset/images/test/ \\;",
            # 移动测试集标签
            "find /root/yolo_dataset -path '*/test\\labels/*' -name '*.txt' -exec mv {} /root/yolo_dataset/labels/test/ \\;"
        ]
        
        for cmd in move_commands:
            print(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                error = stderr.read().decode('utf-8')
                print(f"⚠️ 命令执行警告: {error}")
        
        # 3. 清理旧的目录结构
        print("\n🧹 清理旧的目录结构...")
        cleanup_commands = [
            "rm -rf /root/yolo_dataset/train",
            "rm -rf /root/yolo_dataset/val", 
            "rm -rf /root/yolo_dataset/test",
            "rm -rf /root/yolo_dataset/trainimages",
            "rm -rf /root/yolo_dataset/trainlabels",
            "rm -rf /root/yolo_dataset/valimages",
            "rm -rf /root/yolo_dataset/vallabels",
            "rm -rf /root/yolo_dataset/testimages",
            "rm -rf /root/yolo_dataset/testlabels"
        ]
        
        for cmd in cleanup_commands:
            print(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.channel.recv_exit_status()
        
        # 4. 验证修复结果
        print("\n✅ 验证修复结果...")
        verify_commands = [
            "ls -la /root/yolo_dataset/",
            "find /root/yolo_dataset/images/train -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/images/val -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/labels/train -name '*.txt' | wc -l",
            "find /root/yolo_dataset/labels/val -name '*.txt' | wc -l"
        ]
        
        for cmd in verify_commands:
            print(f"\n执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                print(f"❌ 错误: {error}")
            else:
                print(f"✅ 输出: {output}")
        
        ssh.close()
        print("\n🎉 数据集目录结构修复完成！")
        return True
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

if __name__ == "__main__":
    print("🔧 开始修复云端数据集目录结构...")
    fix_cloud_dataset_structure()