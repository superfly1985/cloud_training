#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重新创建正确的训练脚本
"""

import paramiko
from datetime import datetime

def create_training_script():
    """重新创建训练脚本"""
    
    # 服务器配置
    server_config = {
        'hostname': '152.136.245.138',
        'port': 22,
        'username': 'root',
        'password': 'Vonzeus01'
    }
    
    # 生成训练脚本内容
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    training_script_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO训练脚本 - 修复版本
"""

import os
import torch
import yaml
from ultralytics import YOLO
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        # 数据集配置
        dataset_path = "/root/yolo_dataset"
        yaml_path = os.path.join(dataset_path, "dataset.yaml")
        
        # 检查数据集
        if not os.path.exists(yaml_path):
            logger.error(f"数据集配置文件不存在: {yaml_path}")
            return
        
        # 检查CUDA环境
        logger.info(f"PyTorch版本: {torch.__version__}")
        logger.info(f"CUDA可用: {torch.cuda.is_available()}")
        logger.info(f"CUDA设备数量: {torch.cuda.device_count()}")
        if torch.cuda.is_available():
            logger.info(f"当前CUDA设备: {torch.cuda.current_device()}")
            logger.info(f"GPU名称: {torch.cuda.get_device_name(0)}")
        
        # 加载YOLO模型
        model = YOLO("yolov8s.pt")
        
        # 开始训练
        logger.info("开始训练...")
        results = model.train(
            data=yaml_path,
            epochs=300,
            batch=20,
            lr0=0.01,
            imgsz=1024,
            device='0',
            project='runs/train',
            name='yolo_training_''' + timestamp + '''',
            save=True,
            save_period=10,
            val=True,
            plots=True
        )
        
        logger.info("训练完成！")
        logger.info(f"最佳模型保存在: {results.save_dir}")
        
    except Exception as e:
        logger.error(f"训练失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
'''
    
    try:
        # 连接服务器
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**server_config, timeout=30)
        
        print("✓ 已连接到服务器")
        
        # 删除旧的脚本
        print("🗑️ 删除旧的训练脚本...")
        cmd = "rm -f /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 使用SFTP上传脚本
        print("📝 使用SFTP上传新的训练脚本...")
        sftp = ssh.open_sftp()
        
        # 创建临时文件
        with sftp.open('/root/training_script.py', 'w') as f:
            f.write(training_script_content)
        
        sftp.close()
        
        # 设置执行权限
        cmd = "chmod +x /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 验证脚本内容
        print("✅ 验证脚本内容...")
        cmd = "wc -l /root/training_script.py && head -10 /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"脚本信息:\n{output}")
        
        # 检查设备配置
        cmd = "grep -n device /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"设备配置: {output}")
        
        # 启动训练
        print("🚀 启动训练...")
        cmd = "cd /root && nohup python3 training_script.py > training.log 2>&1 &"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 等待训练启动
        import time
        print("⏳ 等待训练启动...")
        time.sleep(10)
        
        # 检查训练状态
        print("📊 检查训练状态...")
        cmd = "ps aux | grep training_script.py | grep -v grep"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        
        if output:
            print(f"✅ 训练进程已启动:\n{output}")
        else:
            print("❌ 训练进程未找到，检查日志...")
            
        # 显示训练日志
        cmd = "tail -30 /root/training.log 2>/dev/null || echo '日志文件不存在'"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"\n📋 训练日志:\n{output}")
        
        ssh.close()
        print("\n🎉 训练脚本创建完成！")
        return True
        
    except Exception as e:
        print(f"❌ 创建失败: {e}")
        return False

if __name__ == "__main__":
    print("📝 开始重新创建训练脚本...")
    create_training_script()