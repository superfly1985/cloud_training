#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接移动文件到正确位置
"""

import paramiko

def move_files_direct():
    """直接移动文件到正确位置"""
    
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
        
        # 创建正确的目录结构
        print("\n📁 确保目录结构存在...")
        mkdir_commands = [
            "mkdir -p /root/yolo_dataset/images/train",
            "mkdir -p /root/yolo_dataset/images/val",
            "mkdir -p /root/yolo_dataset/images/test",
            "mkdir -p /root/yolo_dataset/labels/train",
            "mkdir -p /root/yolo_dataset/labels/val",
            "mkdir -p /root/yolo_dataset/labels/test"
        ]
        
        for cmd in mkdir_commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()  # 等待命令完成
        
        # 使用ls命令列出所有文件，然后逐个移动
        print("\n🔍 列出所有文件...")
        cmd = "cd /root/yolo_dataset && ls -la"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"目录内容:\n{output}")
        
        # 移动训练集图片
        print("\n🚚 移动训练集图片...")
        cmd = 'cd /root/yolo_dataset && for file in train\\\\images\\\\*.jpg; do if [ -f "$file" ]; then mv "$file" "images/train/$(basename "$file")"; echo "移动: $file"; fi; done'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if output:
            print(f"输出: {output}")
        if error:
            print(f"错误: {error}")
        
        # 移动训练集标签
        print("\n🚚 移动训练集标签...")
        cmd = 'cd /root/yolo_dataset && for file in train\\\\labels\\\\*.txt; do if [ -f "$file" ]; then mv "$file" "labels/train/$(basename "$file")"; echo "移动: $file"; fi; done'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if output:
            print(f"输出: {output}")
        if error:
            print(f"错误: {error}")
        
        # 移动验证集图片
        print("\n🚚 移动验证集图片...")
        cmd = 'cd /root/yolo_dataset && for file in val\\\\images\\\\*.jpg; do if [ -f "$file" ]; then mv "$file" "images/val/$(basename "$file")"; echo "移动: $file"; fi; done'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if output:
            print(f"输出: {output}")
        if error:
            print(f"错误: {error}")
        
        # 移动验证集标签
        print("\n🚚 移动验证集标签...")
        cmd = 'cd /root/yolo_dataset && for file in val\\\\labels\\\\*.txt; do if [ -f "$file" ]; then mv "$file" "labels/val/$(basename "$file")"; echo "移动: $file"; fi; done'
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if output:
            print(f"输出: {output}")
        if error:
            print(f"错误: {error}")
        
        # 验证结果
        print("\n✅ 验证修复结果...")
        
        verify_commands = [
            "find /root/yolo_dataset/images/train -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/images/val -name '*.jpg' | wc -l", 
            "find /root/yolo_dataset/labels/train -name '*.txt' | wc -l",
            "find /root/yolo_dataset/labels/val -name '*.txt' | wc -l",
            "ls -la /root/yolo_dataset/images/train/ | head -5",
            "ls -la /root/yolo_dataset/images/val/ | head -5"
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
        print("\n🎉 文件移动完成！")
        return True
        
    except Exception as e:
        print(f"❌ 移动失败: {e}")
        return False

if __name__ == "__main__":
    print("🔧 开始直接移动文件...")
    move_files_direct()