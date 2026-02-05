#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复反斜杠路径的文件
"""

import paramiko

def fix_backslash_files():
    """修复反斜杠路径的文件"""
    
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
            print(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()  # 等待命令完成
        
        # 移动文件到正确位置
        print("\n🚚 移动文件到正确位置...")
        
        # 处理训练集图片
        print("处理训练集图片...")
        cmd = 'cd /root/yolo_dataset && find . -name "*train\\\\images\\\\*.jpg" -exec sh -c \'mv "$1" "images/train/$(basename "$1")";\' _ {} \\;'
        print(f"执行: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if error:
            print(f"错误: {error}")
        
        # 处理训练集标签
        print("处理训练集标签...")
        cmd = 'cd /root/yolo_dataset && find . -name "*train\\\\labels\\\\*.txt" -exec sh -c \'mv "$1" "labels/train/$(basename "$1")";\' _ {} \\;'
        print(f"执行: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if error:
            print(f"错误: {error}")
        
        # 处理验证集图片
        print("处理验证集图片...")
        cmd = 'cd /root/yolo_dataset && find . -name "*val\\\\images\\\\*.jpg" -exec sh -c \'mv "$1" "images/val/$(basename "$1")";\' _ {} \\;'
        print(f"执行: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if error:
            print(f"错误: {error}")
        
        # 处理验证集标签
        print("处理验证集标签...")
        cmd = 'cd /root/yolo_dataset && find . -name "*val\\\\labels\\\\*.txt" -exec sh -c \'mv "$1" "labels/val/$(basename "$1")";\' _ {} \\;'
        print(f"执行: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        if error:
            print(f"错误: {error}")
        
        # 验证结果
        print("\n✅ 验证修复结果...")
        
        verify_commands = [
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
        
        # 检查dataset.yaml文件
        print("\n📄 检查dataset.yaml文件...")
        cmd = "cat /root/yolo_dataset/dataset.yaml"
        print(f"执行: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        if error:
            print(f"❌ 错误: {error}")
        else:
            print(f"✅ dataset.yaml内容:\n{output}")
        
        ssh.close()
        print("\n🎉 文件修复完成！")
        return True
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

if __name__ == "__main__":
    print("🔧 开始修复反斜杠路径的文件...")
    fix_backslash_files()