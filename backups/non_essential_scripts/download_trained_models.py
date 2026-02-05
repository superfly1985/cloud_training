#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLOv8训练模型自动下载脚本
功能：从云端服务器下载训练完成的模型到本地指定目录
作者：AI Assistant
创建时间：2025-09-22
"""

import os
import sys
import time
import logging
import paramiko
import hashlib
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_download.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

# 云服务器配置
CLOUD_CONFIG = {
    'hostname': '152.136.245.138',
    'username': 'root',
    'password': 'Vonzeus01',
    'port': 22
}

# 本地目录配置
LOCAL_DOWNLOAD_DIR = r'd:\OneDrive\24.Visual AI\runs\detect\cloud_trained'
CLOUD_TRAINING_DIR = '/root/multi_class_industrial_detection'

def ensure_local_directory():
    """确保本地下载目录存在"""
    try:
        os.makedirs(LOCAL_DOWNLOAD_DIR, exist_ok=True)
        logging.info(f"📁 本地下载目录已准备: {LOCAL_DOWNLOAD_DIR}")
        return True
    except Exception as e:
        logging.error(f"❌ 创建本地目录失败: {e}")
        return False

def connect_to_server():
    """连接到云服务器"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logging.info(f"🔗 正在连接云服务器 {CLOUD_CONFIG['hostname']}...")
        ssh.connect(
            hostname=CLOUD_CONFIG['hostname'],
            username=CLOUD_CONFIG['username'],
            password=CLOUD_CONFIG['password'],
            port=CLOUD_CONFIG['port'],
            timeout=30
        )
        
        logging.info("✅ 云服务器连接成功")
        return ssh
    except Exception as e:
        logging.error(f"❌ 连接云服务器失败: {e}")
        return None

def get_latest_training_run(ssh):
    """获取最新的训练运行目录"""
    try:
        # 查找最新的训练目录
        stdin, stdout, stderr = ssh.exec_command(f'ls -t {CLOUD_TRAINING_DIR}/ | head -1')
        latest_run = stdout.read().decode().strip()
        
        if latest_run:
            latest_run_path = f"{CLOUD_TRAINING_DIR}/{latest_run}"
            logging.info(f"🎯 找到最新训练运行: {latest_run_path}")
            
            # 检查weights目录是否存在
            stdin, stdout, stderr = ssh.exec_command(f'ls -la {latest_run_path}/weights/')
            weights_output = stdout.read().decode()
            
            if 'best.pt' in weights_output:
                logging.info("✅ 发现训练权重文件")
                return latest_run_path
            else:
                logging.warning("⚠️ 未找到训练权重文件")
                return None
        else:
            logging.error("❌ 未找到训练运行目录")
            return None
            
    except Exception as e:
        logging.error(f"❌ 获取训练目录失败: {e}")
        return None

def calculate_file_hash(file_path):
    """计算文件MD5哈希值"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"❌ 计算文件哈希失败: {e}")
        return None

def download_model_files(ssh, cloud_run_path):
    """下载模型文件"""
    try:
        # 创建SFTP连接
        sftp = ssh.open_sftp()
        
        # 创建本地子目录（以时间戳命名）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_run_dir = os.path.join(LOCAL_DOWNLOAD_DIR, f"training_{timestamp}")
        os.makedirs(local_run_dir, exist_ok=True)
        
        weights_dir = f"{cloud_run_path}/weights"
        local_weights_dir = os.path.join(local_run_dir, "weights")
        os.makedirs(local_weights_dir, exist_ok=True)
        
        # 获取权重文件列表
        stdin, stdout, stderr = ssh.exec_command(f'ls {weights_dir}/*.pt')
        weight_files = stdout.read().decode().strip().split('\n')
        
        downloaded_files = []
        
        for weight_file in weight_files:
            if weight_file.strip():
                filename = os.path.basename(weight_file.strip())
                local_file_path = os.path.join(local_weights_dir, filename)
                
                logging.info(f"📥 正在下载: {filename}")
                
                try:
                    # 下载文件
                    sftp.get(weight_file.strip(), local_file_path)
                    
                    # 验证文件大小
                    cloud_stat = sftp.stat(weight_file.strip())
                    local_stat = os.stat(local_file_path)
                    
                    if cloud_stat.st_size == local_stat.st_size:
                        logging.info(f"✅ {filename} 下载成功 ({local_stat.st_size} bytes)")
                        downloaded_files.append({
                            'filename': filename,
                            'local_path': local_file_path,
                            'size': local_stat.st_size,
                            'hash': calculate_file_hash(local_file_path)
                        })
                    else:
                        logging.error(f"❌ {filename} 文件大小不匹配")
                        
                except Exception as e:
                    logging.error(f"❌ 下载 {filename} 失败: {e}")
        
        # 下载训练配置和结果文件
        config_files = ['args.yaml', 'results.csv', 'results.png']
        for config_file in config_files:
            cloud_config_path = f"{cloud_run_path}/{config_file}"
            local_config_path = os.path.join(local_run_dir, config_file)
            
            try:
                sftp.get(cloud_config_path, local_config_path)
                logging.info(f"✅ 配置文件下载成功: {config_file}")
            except Exception as e:
                logging.warning(f"⚠️ 配置文件下载失败 {config_file}: {e}")
        
        sftp.close()
        
        # 生成下载报告
        generate_download_report(local_run_dir, downloaded_files, cloud_run_path)
        
        return local_run_dir, downloaded_files
        
    except Exception as e:
        logging.error(f"❌ 下载模型文件失败: {e}")
        return None, []

def generate_download_report(local_dir, downloaded_files, cloud_path):
    """生成下载报告"""
    report_path = os.path.join(local_dir, "download_report.md")
    
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# YOLOv8训练模型下载报告\n\n")
            f.write(f"**下载时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**云端路径**: {cloud_path}\n")
            f.write(f"**本地路径**: {local_dir}\n\n")
            
            f.write("## 下载文件列表\n\n")
            f.write("| 文件名 | 大小 | MD5哈希 |\n")
            f.write("|--------|------|--------|\n")
            
            for file_info in downloaded_files:
                size_mb = file_info['size'] / (1024 * 1024)
                f.write(f"| {file_info['filename']} | {size_mb:.2f}MB | {file_info['hash'][:16]}... |\n")
            
            f.write(f"\n**总计下载文件**: {len(downloaded_files)} 个\n")
            
        logging.info(f"📋 下载报告已生成: {report_path}")
        
    except Exception as e:
        logging.error(f"❌ 生成下载报告失败: {e}")

def wait_for_training_completion(ssh):
    """等待训练完成"""
    logging.info("⏳ 正在等待训练完成...")
    
    while True:
        try:
            # 检查训练进程
            stdin, stdout, stderr = ssh.exec_command("ps aux | grep 'python.*train' | grep -v grep")
            processes = stdout.read().decode().strip()
            
            if not processes:
                logging.info("🎉 训练已完成！")
                return True
            else:
                logging.info("🔄 训练仍在进行中，等待60秒后再次检查...")
                time.sleep(60)
                
        except Exception as e:
            logging.error(f"❌ 检查训练状态失败: {e}")
            time.sleep(60)

def download_latest_models_now(ssh):
    """立即下载最新的best和last模型"""
    try:
        # 获取最新训练运行
        latest_run_path = get_latest_training_run(ssh)
        if not latest_run_path:
            return False, None, []
        
        # 创建SFTP连接
        sftp = ssh.open_sftp()
        
        # 创建本地子目录（以时间戳命名）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_run_dir = os.path.join(LOCAL_DOWNLOAD_DIR, f"latest_models_{timestamp}")
        os.makedirs(local_run_dir, exist_ok=True)
        
        weights_dir = f"{latest_run_path}/weights"
        
        # 检查best.pt和last.pt是否存在
        target_files = ['best.pt', 'last.pt']
        downloaded_files = []
        
        for model_file in target_files:
            cloud_file_path = f"{weights_dir}/{model_file}"
            local_file_path = os.path.join(local_run_dir, model_file)
            
            try:
                # 检查文件是否存在
                sftp.stat(cloud_file_path)
                
                logging.info(f"📥 正在下载: {model_file}")
                
                # 下载文件
                sftp.get(cloud_file_path, local_file_path)
                
                # 验证文件大小
                cloud_stat = sftp.stat(cloud_file_path)
                local_stat = os.stat(local_file_path)
                
                if cloud_stat.st_size == local_stat.st_size:
                    logging.info(f"✅ {model_file} 下载成功 ({local_stat.st_size} bytes)")
                    downloaded_files.append({
                        'filename': model_file,
                        'local_path': local_file_path,
                        'size': local_stat.st_size,
                        'hash': calculate_file_hash(local_file_path)
                    })
                else:
                    logging.error(f"❌ {model_file} 文件大小不匹配")
                    
            except FileNotFoundError:
                logging.warning(f"⚠️ {model_file} 文件不存在，可能训练尚未生成此文件")
            except Exception as e:
                logging.error(f"❌ 下载 {model_file} 失败: {e}")
        
        # 下载训练配置和结果文件（如果存在）
        config_files = ['args.yaml', 'results.csv']
        for config_file in config_files:
            cloud_config_path = f"{latest_run_path}/{config_file}"
            local_config_path = os.path.join(local_run_dir, config_file)
            
            try:
                sftp.get(cloud_config_path, local_config_path)
                logging.info(f"✅ 配置文件下载成功: {config_file}")
            except Exception as e:
                logging.warning(f"⚠️ 配置文件下载失败 {config_file}: {e}")
        
        sftp.close()
        
        # 生成下载报告
        if downloaded_files:
            generate_download_report(local_run_dir, downloaded_files, latest_run_path)
        
        return True, local_run_dir, downloaded_files
        
    except Exception as e:
        logging.error(f"❌ 下载最新模型失败: {e}")
        return False, None, []

def main():
    """主函数"""
    logging.info("🚀 启动YOLOv8训练模型下载程序")
    
    # 确保本地目录存在
    if not ensure_local_directory():
        return False
    
    # 连接云服务器
    ssh = connect_to_server()
    if not ssh:
        return False
    
    try:
        # 提供选择模式
        print("\n📋 选择下载模式:")
        print("1. 立即下载最新的best和last模型")
        print("2. 等待训练完成后下载所有模型")
        
        choice = input("\n请选择 (1-2): ").strip()
        
        if choice == "1":
            logging.info("🎯 立即下载模式：下载最新的best和last模型")
            success, local_dir, downloaded_files = download_latest_models_now(ssh)
            
            if success and downloaded_files:
                logging.info(f"🎉 最新模型下载完成！")
                logging.info(f"📁 本地目录: {local_dir}")
                logging.info(f"📊 下载文件数: {len(downloaded_files)}")
                
                # 显示下载的模型文件
                for file_info in downloaded_files:
                    if file_info['filename'] == 'best.pt':
                        logging.info(f"🏆 最佳模型: {file_info['local_path']}")
                    elif file_info['filename'] == 'last.pt':
                        logging.info(f"📝 最新模型: {file_info['local_path']}")
                
                return True
            else:
                logging.error("❌ 最新模型下载失败或无可用模型")
                return False
                
        elif choice == "2":
            # 自动等待训练完成
            logging.info("🤖 自动模式：等待训练完成后下载模型")
            if not wait_for_training_completion(ssh):
                return False
            
            # 获取最新训练运行
            latest_run_path = get_latest_training_run(ssh)
            if not latest_run_path:
                return False
            
            # 下载模型文件
            local_dir, downloaded_files = download_model_files(ssh, latest_run_path)
            
            if local_dir and downloaded_files:
                logging.info(f"🎉 模型下载完成！")
                logging.info(f"📁 本地目录: {local_dir}")
                logging.info(f"📊 下载文件数: {len(downloaded_files)}")
                
                # 显示最重要的模型文件
                best_model = next((f for f in downloaded_files if f['filename'] == 'best.pt'), None)
                if best_model:
                    logging.info(f"🏆 最佳模型: {best_model['local_path']}")
                
                return True
            else:
                logging.error("❌ 模型下载失败")
                return False
        else:
            logging.error("❌ 无效选择")
            return False
            
    finally:
        ssh.close()
        logging.info("🔐 云服务器连接已关闭")

if __name__ == "__main__":
    success = main()
    if success:
        print("\n✅ 模型下载任务完成！")
        print(f"📁 模型已保存到: {LOCAL_DOWNLOAD_DIR}")
    else:
        print("\n❌ 模型下载任务失败！")
        sys.exit(1)