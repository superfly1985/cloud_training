#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复云端数据集目录结构脚本
将Windows格式的路径文件重新组织为标准的YOLO数据集结构
"""

import paramiko
import json
import os
from datetime import datetime

def load_config():
    """加载云端训练配置"""
    config_file = 'cloud_training_config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"配置文件 {config_file} 不存在")
        return None

def connect_to_server(config):
    """连接到云端服务器"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh.connect(
            hostname=config['server']['hostname'],
            port=config['server']['port'],
            username=config['server']['username'],
            password=config['server']['password'],
            timeout=30
        )
        
        print(f"✅ 成功连接到服务器 {config['server']['hostname']}")
        return ssh
    except Exception as e:
        print(f"❌ 连接服务器失败: {e}")
        return None

def backup_current_structure(ssh):
    """备份当前的数据集结构"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"/root/yolo_dataset_backup_{timestamp}"
    
    print(f"📦 备份当前结构到: {backup_dir}")
    
    commands = [
        f"cp -r /root/yolo_dataset {backup_dir}",
        f"echo 'Backup created at {timestamp}' > {backup_dir}/backup_info.txt"
    ]
    
    for cmd in commands:
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            if exit_code != 0:
                error = stderr.read().decode('utf-8')
                print(f"❌ 备份命令失败: {cmd} - {error}")
                return False
        except Exception as e:
            print(f"❌ 备份异常: {cmd} - {e}")
            return False
    
    print(f"✅ 备份完成: {backup_dir}")
    return backup_dir

def create_proper_directory_structure(ssh):
    """创建正确的目录结构"""
    print("📁 创建标准YOLO目录结构...")
    
    directories = [
        "/root/yolo_dataset/train",
        "/root/yolo_dataset/train/images", 
        "/root/yolo_dataset/train/labels",
        "/root/yolo_dataset/val",
        "/root/yolo_dataset/val/images",
        "/root/yolo_dataset/val/labels", 
        "/root/yolo_dataset/test",
        "/root/yolo_dataset/test/images",
        "/root/yolo_dataset/test/labels"
    ]
    
    for directory in directories:
        try:
            stdin, stdout, stderr = ssh.exec_command(f"mkdir -p {directory}")
            exit_code = stdout.channel.recv_exit_status()
            if exit_code == 0:
                print(f"✅ 创建目录: {directory}")
            else:
                error = stderr.read().decode('utf-8')
                print(f"❌ 创建目录失败: {directory} - {error}")
                return False
        except Exception as e:
            print(f"❌ 创建目录异常: {directory} - {e}")
            return False
    
    return True

def move_files_to_proper_structure(ssh):
    """将文件移动到正确的目录结构"""
    print("🔄 重新组织文件结构...")
    
    # 移动文件的命令
    move_commands = [
        # 移动训练集图片
        "find /root/yolo_dataset -name 'train\\\\images\\\\*' -type f -exec mv {} /root/yolo_dataset/train/images/ \\;",
        # 移动训练集标签
        "find /root/yolo_dataset -name 'train\\\\labels\\\\*' -type f -exec mv {} /root/yolo_dataset/train/labels/ \\;",
        # 移动验证集图片
        "find /root/yolo_dataset -name 'val\\\\images\\\\*' -type f -exec mv {} /root/yolo_dataset/val/images/ \\;",
        # 移动验证集标签
        "find /root/yolo_dataset -name 'val\\\\labels\\\\*' -type f -exec mv {} /root/yolo_dataset/val/labels/ \\;",
        # 移动测试集图片
        "find /root/yolo_dataset -name 'test\\\\images\\\\*' -type f -exec mv {} /root/yolo_dataset/test/images/ \\;",
        # 移动测试集标签
        "find /root/yolo_dataset -name 'test\\\\labels\\\\*' -type f -exec mv {} /root/yolo_dataset/test/labels/ \\;"
    ]
    
    # 由于find命令可能有问题，我们使用更直接的方法
    direct_move_commands = [
        # 移动训练集
        "if [ -d '/root/yolo_dataset' ]; then find /root/yolo_dataset -maxdepth 1 -name 'train*images*' -type f -exec mv {} /root/yolo_dataset/train/images/ \\; 2>/dev/null || true; fi",
        "if [ -d '/root/yolo_dataset' ]; then find /root/yolo_dataset -maxdepth 1 -name 'train*labels*' -type f -exec mv {} /root/yolo_dataset/train/labels/ \\; 2>/dev/null || true; fi",
        # 移动验证集
        "if [ -d '/root/yolo_dataset' ]; then find /root/yolo_dataset -maxdepth 1 -name 'val*images*' -type f -exec mv {} /root/yolo_dataset/val/images/ \\; 2>/dev/null || true; fi",
        "if [ -d '/root/yolo_dataset' ]; then find /root/yolo_dataset -maxdepth 1 -name 'val*labels*' -type f -exec mv {} /root/yolo_dataset/val/labels/ \\; 2>/dev/null || true; fi",
        # 移动测试集
        "if [ -d '/root/yolo_dataset' ]; then find /root/yolo_dataset -maxdepth 1 -name 'test*images*' -type f -exec mv {} /root/yolo_dataset/test/images/ \\; 2>/dev/null || true; fi",
        "if [ -d '/root/yolo_dataset' ]; then find /root/yolo_dataset -maxdepth 1 -name 'test*labels*' -type f -exec mv {} /root/yolo_dataset/test/labels/ \\; 2>/dev/null || true; fi"
    ]
    
    for cmd in direct_move_commands:
        try:
            print(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if output:
                print(f"输出: {output}")
            if error and "No such file" not in error:
                print(f"警告: {error}")
                
        except Exception as e:
            print(f"❌ 移动文件异常: {cmd} - {e}")
    
    return True

def clean_old_structure(ssh):
    """清理旧的目录结构"""
    print("🧹 清理旧的目录结构...")
    
    # 删除旧的空目录
    cleanup_commands = [
        "rmdir /root/yolo_dataset/trainimages 2>/dev/null || true",
        "rmdir /root/yolo_dataset/trainlabels 2>/dev/null || true", 
        "rmdir /root/yolo_dataset/valimages 2>/dev/null || true",
        "rmdir /root/yolo_dataset/vallabels 2>/dev/null || true",
        "rmdir /root/yolo_dataset/testimages 2>/dev/null || true",
        "rmdir /root/yolo_dataset/testlabels 2>/dev/null || true"
    ]
    
    for cmd in cleanup_commands:
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            exit_code = stdout.channel.recv_exit_status()
            # 忽略错误，因为目录可能不存在或不为空
        except Exception as e:
            pass  # 忽略清理错误
    
    print("✅ 清理完成")

def verify_new_structure(ssh):
    """验证新的目录结构"""
    print("🔍 验证新的目录结构...")
    
    directories_to_check = [
        "/root/yolo_dataset/train/images",
        "/root/yolo_dataset/train/labels", 
        "/root/yolo_dataset/val/images",
        "/root/yolo_dataset/val/labels",
        "/root/yolo_dataset/test/images",
        "/root/yolo_dataset/test/labels"
    ]
    
    structure_ok = True
    
    for directory in directories_to_check:
        try:
            stdin, stdout, stderr = ssh.exec_command(f"ls -la {directory} | wc -l")
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                count = int(stdout.read().decode('utf-8').strip()) - 1  # 减去总计行
                print(f"✅ {directory}: {count} 个文件")
                if count == 0:
                    print(f"⚠️  警告: {directory} 为空")
            else:
                print(f"❌ {directory}: 不存在或无法访问")
                structure_ok = False
                
        except Exception as e:
            print(f"❌ 检查目录异常: {directory} - {e}")
            structure_ok = False
    
    return structure_ok

def update_dataset_yaml(ssh):
    """更新dataset.yaml文件确保路径正确"""
    print("📝 更新dataset.yaml配置...")
    
    yaml_content = """names:
- 卡车
- 飞机
- 轮船
- 房屋
- 公路
nc: 5
path: /root/yolo_dataset
test: test/images
train: train/images
val: val/images
"""
    
    try:
        # 备份原文件
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        stdin, stdout, stderr = ssh.exec_command(f"cp /root/yolo_dataset/dataset.yaml /root/yolo_dataset/dataset.yaml.backup_{timestamp}")
        
        # 写入新配置
        stdin, stdout, stderr = ssh.exec_command(f"cat > /root/yolo_dataset/dataset.yaml << 'EOF'\n{yaml_content}EOF")
        exit_code = stdout.channel.recv_exit_status()
        
        if exit_code == 0:
            print("✅ dataset.yaml 更新成功")
            return True
        else:
            error = stderr.read().decode('utf-8')
            print(f"❌ 更新dataset.yaml失败: {error}")
            return False
            
    except Exception as e:
        print(f"❌ 更新dataset.yaml异常: {e}")
        return False

def main():
    """主函数"""
    print("🚀 开始修复云端数据集结构...")
    
    # 加载配置
    config = load_config()
    if not config:
        return
    
    # 连接服务器
    ssh = connect_to_server(config)
    if not ssh:
        return
    
    try:
        # 1. 备份当前结构
        backup_dir = backup_current_structure(ssh)
        if not backup_dir:
            print("❌ 备份失败，停止修复")
            return
        
        # 2. 创建正确的目录结构
        if not create_proper_directory_structure(ssh):
            print("❌ 创建目录结构失败")
            return
        
        # 3. 移动文件到正确位置
        if not move_files_to_proper_structure(ssh):
            print("❌ 移动文件失败")
            return
        
        # 4. 清理旧结构
        clean_old_structure(ssh)
        
        # 5. 验证新结构
        if verify_new_structure(ssh):
            print("✅ 新目录结构验证成功")
        else:
            print("⚠️  新目录结构验证有问题")
        
        # 6. 更新dataset.yaml
        if update_dataset_yaml(ssh):
            print("✅ 配置文件更新成功")
        else:
            print("❌ 配置文件更新失败")
        
        print("\n" + "="*60)
        print("🎉 数据集结构修复完成！")
        print(f"📦 备份位置: {backup_dir}")
        print("💡 现在可以重新启动训练了")
        
    except Exception as e:
        print(f"❌ 修复过程中发生错误: {e}")
    
    finally:
        ssh.close()
        print("\n🔚 修复完成")

if __name__ == "__main__":
    main()