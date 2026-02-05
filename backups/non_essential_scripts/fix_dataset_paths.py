#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复数据集路径配置问题
"""

import paramiko
import yaml

def fix_dataset_paths():
    """修复数据集路径配置问题"""
    
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
        
        # 检查当前数据集结构
        print("\n📁 检查当前数据集结构...")
        cmd = "find /root/yolo_dataset -type d | sort"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"目录结构:\n{output}")
        
        # 检查文件分布
        print("\n📊 检查文件分布...")
        cmd = """
        echo "=== 图片文件 ==="
        find /root/yolo_dataset -name "*.jpg" -o -name "*.png" | head -10
        echo "=== 标签文件 ==="
        find /root/yolo_dataset -name "*.txt" | head -10
        echo "=== 文件统计 ==="
        echo "图片总数: $(find /root/yolo_dataset -name "*.jpg" -o -name "*.png" | wc -l)"
        echo "标签总数: $(find /root/yolo_dataset -name "*.txt" | wc -l)"
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"文件分布:\n{output}")
        
        # 检查dataset.yaml内容
        print("\n📋 检查dataset.yaml内容...")
        cmd = "cat /root/yolo_dataset/dataset.yaml"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"当前配置:\n{output}")
        
        # 创建正确的目录结构
        print("\n🔧 创建正确的目录结构...")
        cmd = """
        mkdir -p /root/yolo_dataset/images/train
        mkdir -p /root/yolo_dataset/images/val
        mkdir -p /root/yolo_dataset/labels/train
        mkdir -p /root/yolo_dataset/labels/val
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 移动文件到正确位置（如果需要）
        print("\n📦 检查并移动文件...")
        cmd = """
        # 检查train目录下是否有文件
        train_images=$(find /root/yolo_dataset/train -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)
        train_labels=$(find /root/yolo_dataset/train -name "*.txt" 2>/dev/null | wc -l)
        
        # 检查val目录下是否有文件
        val_images=$(find /root/yolo_dataset/val -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)
        val_labels=$(find /root/yolo_dataset/val -name "*.txt" 2>/dev/null | wc -l)
        
        echo "train目录图片: $train_images"
        echo "train目录标签: $train_labels"
        echo "val目录图片: $val_images"
        echo "val目录标签: $val_labels"
        
        # 如果train目录有文件，移动到images/train
        if [ $train_images -gt 0 ]; then
            echo "移动train图片文件..."
            find /root/yolo_dataset/train -name "*.jpg" -o -name "*.png" | while read file; do
                mv "$file" /root/yolo_dataset/images/train/
            done
        fi
        
        if [ $train_labels -gt 0 ]; then
            echo "移动train标签文件..."
            find /root/yolo_dataset/train -name "*.txt" | while read file; do
                mv "$file" /root/yolo_dataset/labels/train/
            done
        fi
        
        # 如果val目录有文件，移动到images/val
        if [ $val_images -gt 0 ]; then
            echo "移动val图片文件..."
            find /root/yolo_dataset/val -name "*.jpg" -o -name "*.png" | while read file; do
                mv "$file" /root/yolo_dataset/images/val/
            done
        fi
        
        if [ $val_labels -gt 0 ]; then
            echo "移动val标签文件..."
            find /root/yolo_dataset/val -name "*.txt" | while read file; do
                mv "$file" /root/yolo_dataset/labels/val/
            done
        fi
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"移动结果:\n{output}")
        
        # 更新dataset.yaml配置
        print("\n📝 更新dataset.yaml配置...")
        new_yaml_content = """# YOLO数据集配置文件
path: /root/yolo_dataset  # 数据集根目录
train: images/train  # 训练图片目录（相对于path）
val: images/val      # 验证图片目录（相对于path）

# 类别数量
nc: 1

# 类别名称
names:
  0: object
"""
        
        # 使用SFTP更新配置文件
        sftp = ssh.open_sftp()
        with sftp.open('/root/yolo_dataset/dataset.yaml', 'w') as f:
            f.write(new_yaml_content)
        sftp.close()
        
        # 验证新的目录结构
        print("\n✅ 验证新的目录结构...")
        cmd = """
        echo "=== 目录结构 ==="
        find /root/yolo_dataset -type d | sort
        echo "=== 文件统计 ==="
        echo "训练图片: $(find /root/yolo_dataset/images/train -name "*.jpg" -o -name "*.png" | wc -l)"
        echo "训练标签: $(find /root/yolo_dataset/labels/train -name "*.txt" | wc -l)"
        echo "验证图片: $(find /root/yolo_dataset/images/val -name "*.jpg" -o -name "*.png" | wc -l)"
        echo "验证标签: $(find /root/yolo_dataset/labels/val -name "*.txt" | wc -l)"
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"验证结果:\n{output}")
        
        # 显示更新后的配置
        print("\n📋 显示更新后的配置...")
        cmd = "cat /root/yolo_dataset/dataset.yaml"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"新配置:\n{output}")
        
        ssh.close()
        print("\n🎉 数据集路径修复完成！")
        return True
        
    except Exception as e:
        print(f"❌ 修复失败: {e}")
        return False

if __name__ == "__main__":
    print("🔧 开始修复数据集路径配置...")
    fix_dataset_paths()