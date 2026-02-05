#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复设备配置并重新启动训练
"""

import paramiko
import time
from datetime import datetime

def fix_and_restart_training():
    """修复设备配置并重新启动训练"""
    
    # 服务器配置
    server_config = {
        'hostname': '152.136.245.138',
        'port': 22,
        'username': 'root',
        'password': 'Vonzeus01'
    }
    
    # 生成新的训练脚本内容（修复设备配置）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    training_script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO训练脚本 - 修复版本
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
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
            logger.error(f"数据集配置文件不存在: {{yaml_path}}")
            return
        
        # 检查CUDA环境
        logger.info(f"PyTorch版本: {{torch.__version__}}")
        logger.info(f"CUDA可用: {{torch.cuda.is_available()}}")
        logger.info(f"CUDA设备数量: {{torch.cuda.device_count()}}")
        if torch.cuda.is_available():
            logger.info(f"当前CUDA设备: {{torch.cuda.current_device()}}")
            logger.info(f"GPU名称: {{torch.cuda.get_device_name(0)}}")
        
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
            device='0',  # 明确指定使用GPU 0
            project='runs/train',
            name='yolo_training_{timestamp}',
            save=True,
            save_period=10,
            val=True,
            plots=True
        )
        
        logger.info("训练完成！")
        logger.info(f"最佳模型保存在: {{results.save_dir}}")
        
    except Exception as e:
        logger.error(f"训练失败: {{e}}")
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
        
        # 停止当前训练进程（如果有的话）
        print("\n🛑 停止当前训练进程...")
        cmd = "pkill -f training_script.py || true"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 备份旧的训练脚本
        print("📄 备份旧的训练脚本...")
        cmd = "cp /root/training_script.py /root/training_script_backup.py 2>/dev/null || true"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 上传新的训练脚本
        print("📝 上传修复后的训练脚本...")
        cmd = f"cat > /root/training_script.py << 'EOF'\\n{training_script_content}EOF"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 验证脚本内容
        print("✅ 验证新脚本内容...")
        cmd = "grep -n device /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"设备配置: {output}")
        
        # 启动新的训练
        print("🚀 启动新的训练...")
        cmd = "cd /root && nohup python3 training_script.py > training.log 2>&1 &"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 等待一下让训练开始
        print("⏳ 等待训练启动...")
        time.sleep(5)
        
        # 检查训练状态
        print("📊 检查训练状态...")
        cmd = "ps aux | grep training_script.py | grep -v grep"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        
        if output:
            print(f"✅ 训练进程已启动: {output}")
        else:
            print("❌ 训练进程未找到")
        
        # 显示最新的训练日志
        print("\n📋 最新训练日志:")
        cmd = "tail -20 /root/training.log 2>/dev/null || echo '日志文件不存在'"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(output)
        
        ssh.close()
        print("\n🎉 训练重启完成！")
        print("💡 提示：可以通过GUI监控训练进度")
        return True
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        return False

if __name__ == "__main__":
    print("🔧 开始修复设备配置并重新启动训练...")
    fix_and_restart_training()