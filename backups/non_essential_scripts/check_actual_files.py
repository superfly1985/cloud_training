#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细检查数据集文件的实际位置
"""

import paramiko

def check_actual_files():
    """详细检查数据集文件的实际位置"""
    
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
        
        # 详细列出所有文件
        print("\n📁 详细列出所有文件...")
        cmd = """
        echo "=== 完整目录结构 ==="
        find /root/yolo_dataset -type f | sort
        echo ""
        echo "=== 目录列表 ==="
        find /root/yolo_dataset -type d | sort
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"完整结构:\n{output}")
        
        # 使用ls -la查看详细信息
        print("\n📋 使用ls -la查看详细信息...")
        cmd = "ls -la /root/yolo_dataset/"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"根目录内容:\n{output}")
        
        # 检查特殊字符文件
        print("\n🔍 检查特殊字符文件...")
        cmd = """
        echo "=== 使用不同方法查找文件 ==="
        # 方法1: 直接find
        echo "方法1 - 直接find:"
        find /root/yolo_dataset -name "*.jpg" -o -name "*.png" -o -name "*.txt" | wc -l
        
        # 方法2: 使用ls递归
        echo "方法2 - ls递归:"
        ls -laR /root/yolo_dataset/ | grep -E "\\.(jpg|png|txt)$" | wc -l
        
        # 方法3: 查找包含特殊字符的目录
        echo "方法3 - 特殊字符目录:"
        find /root/yolo_dataset -type d -name "*[\\\\]*" 2>/dev/null || echo "无特殊字符目录"
        
        # 方法4: 查找所有非标准ASCII文件名
        echo "方法4 - 非标准文件名:"
        find /root/yolo_dataset -type f | grep -v "^[[:print:]]*$" | head -5 || echo "无非标准文件名"
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"特殊字符检查:\n{output}")
        
        # 检查具体的目录内容
        print("\n📂 检查具体目录内容...")
        directories = [
            "trainimages", "trainlabels", "valimages", "vallabels", 
            "testimages", "testlabels", "images/train", "images/val", 
            "labels/train", "labels/val"
        ]
        
        for dir_name in directories:
            cmd = f"ls -la /root/yolo_dataset/{dir_name}/ 2>/dev/null | head -5 || echo '目录不存在或为空: {dir_name}'"
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            print(f"{dir_name}: {output}")
        
        # 尝试手动移动文件
        print("\n🔧 尝试手动移动文件...")
        cmd = """
        # 检查trainimages目录
        if [ -d "/root/yolo_dataset/trainimages" ]; then
            echo "trainimages目录存在，内容:"
            ls -la /root/yolo_dataset/trainimages/ | head -5
            echo "移动trainimages中的文件..."
            find /root/yolo_dataset/trainimages -type f \\( -name "*.jpg" -o -name "*.png" \\) -exec mv {} /root/yolo_dataset/images/train/ \\;
        fi
        
        # 检查trainlabels目录
        if [ -d "/root/yolo_dataset/trainlabels" ]; then
            echo "trainlabels目录存在，内容:"
            ls -la /root/yolo_dataset/trainlabels/ | head -5
            echo "移动trainlabels中的文件..."
            find /root/yolo_dataset/trainlabels -type f -name "*.txt" -exec mv {} /root/yolo_dataset/labels/train/ \\;
        fi
        
        # 检查valimages目录
        if [ -d "/root/yolo_dataset/valimages" ]; then
            echo "valimages目录存在，内容:"
            ls -la /root/yolo_dataset/valimages/ | head -5
            echo "移动valimages中的文件..."
            find /root/yolo_dataset/valimages -type f \\( -name "*.jpg" -o -name "*.png" \\) -exec mv {} /root/yolo_dataset/images/val/ \\;
        fi
        
        # 检查vallabels目录
        if [ -d "/root/yolo_dataset/vallabels" ]; then
            echo "vallabels目录存在，内容:"
            ls -la /root/yolo_dataset/vallabels/ | head -5
            echo "移动vallabels中的文件..."
            find /root/yolo_dataset/vallabels -type f -name "*.txt" -exec mv {} /root/yolo_dataset/labels/val/ \\;
        fi
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"手动移动结果:\n{output}")
        
        # 最终验证
        print("\n✅ 最终验证...")
        cmd = """
        echo "=== 最终文件统计 ==="
        echo "训练图片: $(find /root/yolo_dataset/images/train -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)"
        echo "训练标签: $(find /root/yolo_dataset/labels/train -name "*.txt" 2>/dev/null | wc -l)"
        echo "验证图片: $(find /root/yolo_dataset/images/val -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)"
        echo "验证标签: $(find /root/yolo_dataset/labels/val -name "*.txt" 2>/dev/null | wc -l)"
        echo "总图片数: $(find /root/yolo_dataset -name "*.jpg" -o -name "*.png" 2>/dev/null | wc -l)"
        echo "总标签数: $(find /root/yolo_dataset -name "*.txt" 2>/dev/null | grep -v export_stats | wc -l)"
        """
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"最终验证:\n{output}")
        
        ssh.close()
        print("\n🎉 检查完成！")
        return True
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    print("🔍 开始详细检查数据集文件...")
    check_actual_files()