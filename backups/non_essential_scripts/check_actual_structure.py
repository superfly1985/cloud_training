#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查云端实际目录结构
"""

import paramiko

def check_actual_structure():
    """检查云端实际目录结构"""
    
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
        
        # 检查所有可能的文件位置
        print("\n📁 检查所有可能的文件位置...")
        check_commands = [
            "find /root/yolo_dataset -name '*.jpg' | head -10",
            "find /root/yolo_dataset -name '*.txt' | head -10",
            "ls -la /root/yolo_dataset/",
            "ls -la /root/yolo_dataset/train/ 2>/dev/null || echo 'train目录不存在'",
            "ls -la /root/yolo_dataset/val/ 2>/dev/null || echo 'val目录不存在'",
            "ls -la /root/yolo_dataset/test/ 2>/dev/null || echo 'test目录不存在'",
            "find /root/yolo_dataset -type d | sort"
        ]
        
        for cmd in check_commands:
            print(f"\n执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                print(f"❌ 错误: {error}")
            else:
                print(f"✅ 输出: {output}")
        
        ssh.close()
        return True
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    print("🔍 开始检查云端实际目录结构...")
    check_actual_structure()