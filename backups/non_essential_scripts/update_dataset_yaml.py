#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
更新dataset.yaml文件以使用正确的路径格式
"""

import paramiko

def update_dataset_yaml():
    """更新dataset.yaml文件"""
    
    # 服务器配置
    server_config = {
        'hostname': '152.136.245.138',
        'port': 22,
        'username': 'root',
        'password': 'Vonzeus01'
    }
    
    # 正确的dataset.yaml内容
    yaml_content = """names:
- 卡车
- 飞机
- 轮船
- 房屋
- 公路
nc: 5
path: /root/yolo_dataset
test: images/test
train: images/train
val: images/val
"""
    
    try:
        # 连接服务器
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**server_config, timeout=30)
        
        print("✓ 已连接到服务器")
        
        # 备份原始文件
        print("\n📄 备份原始dataset.yaml文件...")
        cmd = "cp /root/yolo_dataset/dataset.yaml /root/yolo_dataset/dataset.yaml.backup"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 写入新的dataset.yaml内容
        print("📝 更新dataset.yaml文件...")
        cmd = f"cat > /root/yolo_dataset/dataset.yaml << 'EOF'\n{yaml_content}EOF"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 验证新文件内容
        print("✅ 验证新的dataset.yaml内容...")
        cmd = "cat /root/yolo_dataset/dataset.yaml"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"新的dataset.yaml内容:\n{output}")
        
        # 最终验证数据集结构
        print("\n🔍 最终验证数据集结构...")
        verify_commands = [
            "find /root/yolo_dataset/images/train -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/images/val -name '*.jpg' | wc -l",
            "find /root/yolo_dataset/labels/train -name '*.txt' | wc -l",
            "find /root/yolo_dataset/labels/val -name '*.txt' | wc -l"
        ]
        
        for cmd in verify_commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            print(f"{cmd}: {output}")
        
        ssh.close()
        print("\n🎉 dataset.yaml文件更新完成！")
        print("✅ 数据集结构修复完成，现在可以正常训练了！")
        return True
        
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False

if __name__ == "__main__":
    print("📝 开始更新dataset.yaml文件...")
    update_dataset_yaml()