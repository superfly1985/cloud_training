#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
正确移动带反斜杠的文件到正确目录
"""

import paramiko

def move_backslash_files():
    """移动带反斜杠的文件到正确目录"""
    
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
        
        # 检查当前文件分布
        print("\n📊 检查当前文件分布...")
        cmd = """
        echo "=== 带反斜杠的图片文件 ==="
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "\\.(jpg|png)$" | head -10
        echo "=== 带反斜杠的标签文件 ==="
        find /root/yolo_dataset -name "*\\\\*" -type f | grep "\\.txt$" | head -10
        echo "=== 文件统计 ==="
        echo "带反斜杠的图片: $(find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "\\.(jpg|png)$" | wc -l)"
        echo "带反斜杠的标签: $(find /root/yolo_dataset -name "*\\\\*" -type f | grep "\\.txt$" | wc -l)"
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"文件分布:\n{output}")
        
        # 移动训练图片
        print("\n📦 移动训练图片...")
        cmd = """
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "train.*\\.(jpg|png)$" | while read file; do
            if [ -f "$file" ]; then
                echo "移动: $file -> /root/yolo_dataset/images/train/"
                mv "$file" /root/yolo_dataset/images/train/
            fi
        done
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"训练图片移动结果:\n{output}")
        
        # 移动验证图片
        print("\n📦 移动验证图片...")
        cmd = """
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "val.*\\.(jpg|png)$" | while read file; do
            if [ -f "$file" ]; then
                echo "移动: $file -> /root/yolo_dataset/images/val/"
                mv "$file" /root/yolo_dataset/images/val/
            fi
        done
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"验证图片移动结果:\n{output}")
        
        # 移动训练标签
        print("\n📦 移动训练标签...")
        cmd = """
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "train.*\\.txt$" | while read file; do
            if [ -f "$file" ]; then
                echo "移动: $file -> /root/yolo_dataset/labels/train/"
                mv "$file" /root/yolo_dataset/labels/train/
            fi
        done
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"训练标签移动结果:\n{output}")
        
        # 移动验证标签
        print("\n📦 移动验证标签...")
        cmd = """
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "val.*\\.txt$" | while read file; do
            if [ -f "$file" ]; then
                echo "移动: $file -> /root/yolo_dataset/labels/val/"
                mv "$file" /root/yolo_dataset/labels/val/
            fi
        done
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"验证标签移动结果:\n{output}")
        
        # 移动测试文件（如果有的话）
        print("\n📦 移动测试文件...")
        cmd = """
        # 创建test目录
        mkdir -p /root/yolo_dataset/images/test
        mkdir -p /root/yolo_dataset/labels/test
        
        # 移动测试图片
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "test.*\\.(jpg|png)$" | while read file; do
            if [ -f "$file" ]; then
                echo "移动测试图片: $file -> /root/yolo_dataset/images/test/"
                mv "$file" /root/yolo_dataset/images/test/
            fi
        done
        
        # 移动测试标签
        find /root/yolo_dataset -name "*\\\\*" -type f | grep -E "test.*\\.txt$" | while read file; do
            if [ -f "$file" ]; then
                echo "移动测试标签: $file -> /root/yolo_dataset/labels/test/"
                mv "$file" /root/yolo_dataset/labels/test/
            fi
        done
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"测试文件移动结果:\n{output}")
        
        # 验证移动结果
        print("\n✅ 验证移动结果...")
        cmd = """
        echo "=== 最终文件统计 ==="
        echo "训练图片: $(find /root/yolo_dataset/images/train -name "*.jpg" -o -name "*.png" | wc -l)"
        echo "训练标签: $(find /root/yolo_dataset/labels/train -name "*.txt" | wc -l)"
        echo "验证图片: $(find /root/yolo_dataset/images/val -name "*.jpg" -o -name "*.png" | wc -l)"
        echo "验证标签: $(find /root/yolo_dataset/labels/val -name "*.txt" | wc -l)"
        echo "测试图片: $(find /root/yolo_dataset/images/test -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)"
        echo "测试标签: $(find /root/yolo_dataset/labels/test -name "*.txt" 2>/dev/null | wc -l)"
        echo "剩余带反斜杠文件: $(find /root/yolo_dataset -name "*\\\\*" -type f | wc -l)"
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"验证结果:\n{output}")
        
        # 更新dataset.yaml配置（包含测试集）
        print("\n📝 更新dataset.yaml配置...")
        new_yaml_content = """# YOLO数据集配置文件
path: /root/yolo_dataset  # 数据集根目录
train: images/train  # 训练图片目录（相对于path）
val: images/val      # 验证图片目录（相对于path）
test: images/test    # 测试图片目录（相对于path）

# 类别数量
nc: 5

# 类别名称
names:
  0: 卡车
  1: 飞机
  2: 轮船
  3: 房屋
  4: 公路
"""
        
        # 使用SFTP更新配置文件
        sftp = ssh.open_sftp()
        with sftp.open('/root/yolo_dataset/dataset.yaml', 'w') as f:
            f.write(new_yaml_content)
        sftp.close()
        
        # 显示最终配置
        print("\n📋 显示最终配置...")
        cmd = "cat /root/yolo_dataset/dataset.yaml"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"最终配置:\n{output}")
        
        ssh.close()
        print("\n🎉 文件移动完成！")
        return True
        
    except Exception as e:
        print(f"❌ 移动失败: {e}")
        return False

if __name__ == "__main__":
    print("📦 开始移动带反斜杠的文件...")
    move_backslash_files()