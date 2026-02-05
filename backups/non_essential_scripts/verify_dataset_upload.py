#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证云端数据集上传状态
"""

import paramiko
import json
from datetime import datetime

def verify_cloud_dataset():
    """验证云端数据集结构和配置文件"""
    
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
        
        # 检查数据集目录结构
        print("\n📁 检查数据集目录结构...")
        commands = [
            "ls -la /root/yolo_dataset/",
            "find /root/yolo_dataset/images -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/labels -name '*.txt' | wc -l",
            "ls -la /root/yolo_dataset/dataset.yaml",
            "cat /root/yolo_dataset/dataset.yaml"
        ]
        
        results = {}
        for cmd in commands:
            print(f"\n执行命令: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                print(f"❌ 错误: {error}")
                results[cmd] = {'error': error}
            else:
                print(f"✅ 输出: {output}")
                results[cmd] = {'output': output}
        
        # 检查训练和验证集
        print("\n📊 检查训练和验证集...")
        train_val_commands = [
            "find /root/yolo_dataset/images/train -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/images/val -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/labels/train -name '*.txt' | wc -l",
            "find /root/yolo_dataset/labels/val -name '*.txt' | wc -l"
        ]
        
        for cmd in train_val_commands:
            print(f"\n执行命令: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                print(f"❌ 错误: {error}")
                results[cmd] = {'error': error}
            else:
                print(f"✅ 输出: {output}")
                results[cmd] = {'output': output}
        
        # 生成报告
        report = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'server': server_config['hostname'],
            'verification_results': results
        }
        
        # 保存报告
        report_file = f"dataset_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"\n📄 验证报告已保存: {report_file}")
        
        ssh.close()
        return True
        
    except Exception as e:
        print(f"❌ 验证失败: {e}")
        return False

if __name__ == "__main__":
    print("🔍 开始验证云端数据集...")
    verify_cloud_dataset()