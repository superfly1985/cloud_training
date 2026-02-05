#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动化训练监控和模型下载脚本
功能：持续监控训练进度，训练完成后自动下载模型
"""

import os
import sys
import time
import logging
import subprocess
import paramiko
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_monitor.log', encoding='utf-8'),
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

def check_training_status():
    """检查训练状态"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=CLOUD_CONFIG['hostname'],
            username=CLOUD_CONFIG['username'],
            password=CLOUD_CONFIG['password'],
            port=CLOUD_CONFIG['port'],
            timeout=30
        )
        
        # 检查训练进程
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep 'python.*train' | grep -v grep")
        processes = stdout.read().decode().strip()
        
        # 检查最新的训练日志
        stdin, stdout, stderr = ssh.exec_command("ls -t /root/runs/train/ | head -1")
        latest_run = stdout.read().decode().strip()
        
        if latest_run:
            # 检查训练是否完成（查看是否有best.pt文件）
            stdin, stdout, stderr = ssh.exec_command(f"ls -la /root/runs/train/{latest_run}/weights/best.pt 2>/dev/null")
            best_pt_exists = stdout.read().decode().strip()
            
            # 检查训练日志的最后几行
            stdin, stdout, stderr = ssh.exec_command(f"tail -10 /root/runs/train/{latest_run}/train_batch*.jpg 2>/dev/null || echo 'No batch files'")
            
        ssh.close()
        
        if not processes and best_pt_exists:
            logging.info("🎉 训练已完成！发现best.pt文件")
            return True, latest_run
        elif processes:
            logging.info(f"🔄 训练仍在进行中... 进程: {len(processes.split())} 个")
            return False, latest_run
        else:
            logging.info("⚠️ 未检测到训练进程，但可能刚刚完成")
            return best_pt_exists != "", latest_run
            
    except Exception as e:
        logging.error(f"❌ 检查训练状态失败: {e}")
        return False, None

def download_models():
    """调用下载脚本"""
    try:
        logging.info("🚀 开始下载训练模型...")
        
        # 调用下载脚本
        result = subprocess.run([
            sys.executable, 
            'download_trained_models.py'
        ], 
        cwd=os.path.dirname(os.path.abspath(__file__)),
        capture_output=True, 
        text=True, 
        encoding='utf-8'
        )
        
        if result.returncode == 0:
            logging.info("✅ 模型下载成功！")
            logging.info(f"下载输出: {result.stdout}")
            return True
        else:
            logging.error(f"❌ 模型下载失败: {result.stderr}")
            return False
            
    except Exception as e:
        logging.error(f"❌ 调用下载脚本失败: {e}")
        return False

def main():
    """主监控循环"""
    logging.info("🤖 启动自动化训练监控和下载程序")
    logging.info("📋 监控策略：每5分钟检查一次训练状态")
    
    check_interval = 300  # 5分钟
    last_epoch_check = None
    
    while True:
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            logging.info(f"⏰ [{current_time}] 检查训练状态...")
            
            is_completed, latest_run = check_training_status()
            
            if is_completed:
                logging.info("🎯 训练已完成！开始下载模型...")
                
                if download_models():
                    logging.info("🎉 自动化任务完成！训练模型已成功下载到本地")
                    break
                else:
                    logging.error("❌ 模型下载失败，5分钟后重试...")
                    time.sleep(300)
            else:
                if latest_run:
                    logging.info(f"📊 当前训练运行: {latest_run}")
                
                logging.info(f"⏳ 训练仍在进行中，{check_interval//60}分钟后再次检查...")
                time.sleep(check_interval)
                
        except KeyboardInterrupt:
            logging.info("⏹️ 用户中断监控程序")
            break
        except Exception as e:
            logging.error(f"❌ 监控过程中出现错误: {e}")
            logging.info("🔄 30秒后重试...")
            time.sleep(30)

if __name__ == "__main__":
    main()