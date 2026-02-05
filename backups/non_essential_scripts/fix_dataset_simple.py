#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单修复云端数据集目录结构
"""

import paramiko

def fix_cloud_dataset_simple():
    """简单修复云端数据集目录结构"""
    
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
            stdout.channel.recv_exit_status()
        
        # 2. 复制文件到正确位置
        print("\n🚚 复制文件到正确位置...")
        copy_commands = [
            # 复制训练集图片
            "cp /root/yolo_dataset/train/images/*.jpg /root/yolo_dataset/images/train/ 2>/dev/null || true",
            # 复制训练集标签
            "cp /root/yolo_dataset/train/labels/*.txt /root/yolo_dataset/labels/train/ 2>/dev/null || true",
            # 复制验证集图片
            "cp /root/yolo_dataset/val/images/*.jpg /root/yolo_dataset/images/val/ 2>/dev/null || true",
            # 复制验证集标签
            "cp /root/yolo_dataset/val/labels/*.txt /root/yolo_dataset/labels/val/ 2>/dev/null || true",
            # 复制测试集图片
            "cp /root/yolo_dataset/test/images/*.jpg /root/yolo_dataset/images/test/ 2>/dev/null || true",
            # 复制测试集标签
            "cp /root/yolo_dataset/test/labels/*.txt /root/yolo_dataset/labels/test/ 2>/dev/null || true"
        ]
        
        for cmd in copy_commands:
            print(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                error = stderr.read().decode('utf-8')
                if error.strip():
                    print(f"⚠️ 警告: {error}")
        
        # 3. 验证复制结果
        print("\n✅ 验证复制结果...")
        verify_commands = [
            "find /root/yolo_dataset/images/train -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/images/val -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/labels/train -name '*.txt' | wc -l",
            "find /root/yolo_dataset/labels/val -name '*.txt' | wc -l",
            "ls -la /root/yolo_dataset/images/",
            "ls -la /root/yolo_dataset/labels/"
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
    print("🔧 开始简单修复云端数据集目录结构...")
    fix_cloud_dataset_simple()