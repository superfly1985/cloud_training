#!/usr/bin/env python3
import paramiko
import logging
import time
import os
import json
import sys
import argparse
from pathlib import Path
from scp import SCPClient
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime
import hashlib

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cloud_gpu_training_final.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 云服务器配置
CLOUD_CONFIG = {
    'hostname': '152.136.245.138',
    'port': 22,
    'username': 'root',
    'password': 'Vonzeus01'
}

# 训练配置参数 - T4 16GB GPU优化版本
TRAINING_CONFIG = {
    'epochs': 300,
    'batch_size': 20,  # 恢复V3成功配置的批次大小
    'learning_rate': 0.01,  # 保持正常学习率
    'image_size': 1024,  # 保持原始分辨率 1024*1024
    'base_model': 'yolov8s.pt',  # 使用YOLOv8s模型
    'dataset_path': '/root/yolo_dataset_4classes',
    'workers': 0,  # 数据加载线程数 (0=单进程，避免云端多进程问题)
    'mixed_precision': True,  # 保持混合精度训练
    'save_period': 10,  # 保持正常保存频率
    'patience': 50,  # 保持正常耐心值
    'project_name': 'multi_class_industrial_detection',
    'experiment_name': 'v4_ruler_4classes_origin_10_20_30_yolov8s',  # V4配置版本 - 4类ruler检测
    'object_keywords': '原点 10 20 30',
    'object_description': '4-class ruler detection with YOLOv8s - origin point and scale marks',
    'num_classes': 4,
    'class_names': ['原点', '10', '20', '30'],
    'class_config': {
        0: {'name': '原点', 'description': 'Origin point on ruler'},
        1: {'name': '10', 'description': '10mm scale mark'},
        2: {'name': '20', 'description': '20mm scale mark'},
        3: {'name': '30', 'description': '30mm scale mark'}
    },
    # 简化配置，移除可能导致内存问题的额外参数
    'cache_images': False,  # 禁用图像缓存（与V3一致）
}

# 上传配置
UPLOAD_CONFIG = {
    'max_workers': 20,  # 20线程上传
    'chunk_size': 8192,
    'retry_count': 3
}

# 状态管理配置
STATUS_FILE = 'training_progress_status.json'
TRAINING_STEPS = [
    'gpu_check',
    'server_time_check', 
    'cloud_cleanup',
    'environment_setup',
    'dataset_upload',
    'script_creation',
    'training_start'
]

# 线程安全的计数器
class ThreadSafeCounter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()
    
    def increment(self):
        with self._lock:
            self._value += 1
            return self._value
    
    def get_value(self):
        with self._lock:
            return self._value

# 上传统计
upload_stats = {
    'total': 0,
    'success': ThreadSafeCounter(),
    'failed': ThreadSafeCounter(),
    'start_time': None,
    'last_update_time': None,
    'last_progress_display': 0
}

# 上传进度记录文件路径
UPLOAD_PROGRESS_FILE = "upload_progress.json"

def get_file_hash(file_path):
    """计算文件的MD5哈希值，用于验证文件完整性"""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logging.error(f"计算文件哈希失败 {file_path}: {e}")
        return None

def load_upload_progress():
    """加载上传进度记录"""
    try:
        if os.path.exists(UPLOAD_PROGRESS_FILE):
            with open(UPLOAD_PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"加载上传进度记录失败: {e}")
    return {}

def save_upload_progress(progress_data):
    """保存上传进度记录"""
    try:
        with open(UPLOAD_PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"保存上传进度记录失败: {e}")

def mark_file_uploaded(local_file, remote_file, file_hash):
    """标记文件为已上传"""
    progress_data = load_upload_progress()
    progress_data[remote_file] = {
        'local_file': local_file,
        'hash': file_hash,
        'upload_time': datetime.now().isoformat(),
        'status': 'completed'
    }
    save_upload_progress(progress_data)

def is_file_uploaded(local_file, remote_file):
    """检查文件是否已经上传且完整"""
    progress_data = load_upload_progress()
    
    if remote_file not in progress_data:
        return False
    
    record = progress_data[remote_file]
    
    # 检查本地文件是否存在
    if not os.path.exists(local_file):
        return False
    
    # 检查文件哈希是否匹配
    current_hash = get_file_hash(local_file)
    if current_hash != record.get('hash'):
        return False
    
    # 检查状态是否为已完成
    return record.get('status') == 'completed'

def clear_upload_progress():
    """清空上传进度记录"""
    try:
        if os.path.exists(UPLOAD_PROGRESS_FILE):
            os.remove(UPLOAD_PROGRESS_FILE)
            logging.info("已清空上传进度记录")
    except Exception as e:
        logging.error(f"清空上传进度记录失败: {e}")

# 状态管理函数
def load_training_status():
    """加载训练进度状态"""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r', encoding='utf-8') as f:
                status = json.load(f)
                logging.info(f"📋 加载训练状态: {len([k for k, v in status.get('steps', {}).items() if v])} 个步骤已完成")
                return status
        else:
            logging.info("📋 未找到状态文件，将从头开始执行")
            return create_new_status()
    except Exception as e:
        logging.warning(f"加载状态文件失败: {e}，将从头开始执行")
        return create_new_status()

def create_new_status():
    """创建新的状态记录"""
    return {
        'session_id': datetime.now().strftime('%Y%m%d_%H%M%S'),
        'created_at': datetime.now().isoformat(),
        'last_updated': datetime.now().isoformat(),
        'steps': {step: False for step in TRAINING_STEPS},
        'current_step': None,
        'total_steps': len(TRAINING_STEPS)
    }

def save_training_status(status):
    """保存训练进度状态"""
    try:
        status['last_updated'] = datetime.now().isoformat()
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(status, f, indent=2, ensure_ascii=False)
        logging.debug(f"状态已保存: {STATUS_FILE}")
    except Exception as e:
        logging.error(f"保存状态文件失败: {e}")

def mark_step_completed(status, step_name):
    """标记步骤为已完成"""
    if step_name in status['steps']:
        status['steps'][step_name] = True
        status['current_step'] = step_name
        save_training_status(status)
        completed_count = sum(status['steps'].values())
        logging.info(f"✅ 步骤完成: {step_name} ({completed_count}/{status['total_steps']})")
    else:
        logging.warning(f"未知步骤: {step_name}")

def is_step_completed(status, step_name):
    """检查步骤是否已完成"""
    return status.get('steps', {}).get(step_name, False)

def reset_training_status():
    """重置训练状态"""
    try:
        if os.path.exists(STATUS_FILE):
            backup_file = f"{STATUS_FILE}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(STATUS_FILE, backup_file)
            logging.info(f"原状态文件已备份为: {backup_file}")
        
        new_status = create_new_status()
        save_training_status(new_status)
        logging.info("🔄 训练状态已重置")
        return new_status
    except Exception as e:
        logging.error(f"重置状态失败: {e}")
        return create_new_status()

def show_training_status(status):
    """显示当前训练状态"""
    print("\n" + "="*50)
    print("📊 当前训练进度状态")
    print("="*50)
    print(f"会话ID: {status.get('session_id', 'N/A')}")
    print(f"创建时间: {status.get('created_at', 'N/A')}")
    print(f"最后更新: {status.get('last_updated', 'N/A')}")
    print("\n步骤完成情况:")
    
    step_names = {
        'gpu_check': '1. GPU状态检查',
        'server_time_check': '2. 服务器时间检查',
        'cloud_cleanup': '3. 清理云端数据',
        'environment_setup': '4. 环境设置',
        'dataset_upload': '5. 数据集上传',
        'script_creation': '6. 训练脚本创建',
        'training_start': '7. 训练启动'
    }
    
    for step in TRAINING_STEPS:
        status_icon = "✅" if status['steps'].get(step, False) else "⏳"
        step_name = step_names.get(step, step)
        print(f"  {status_icon} {step_name}")
    
    completed = sum(status['steps'].values())
    total = len(TRAINING_STEPS)
    print(f"\n总进度: {completed}/{total} ({completed/total*100:.1f}%)")
    print("="*50)

def create_ssh_client():
    """创建SSH客户端"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(**CLOUD_CONFIG)
    return ssh

def check_gpu_status(status=None):
    """检查GPU状态"""
    ssh = create_ssh_client()
    try:
        logging.info("检查GPU状态...")
        
        # 检查NVIDIA驱动
        stdin, stdout, stderr = ssh.exec_command('nvidia-smi')
        gpu_info = stdout.read().decode()
        
        if 'NVIDIA-SMI' in gpu_info:
            logging.info("✅ GPU可用")
            logging.info("GPU信息:")
            for line in gpu_info.split('\n')[:10]:  # 显示前10行
                if line.strip():
                    logging.info(f"  {line}")
            
            # 标记步骤完成
            if status:
                mark_step_completed(status, 'gpu_check')
                save_training_status(status)
                logging.info("✅ GPU检查步骤已完成并保存")
            
            return True
        else:
            logging.error("❌ GPU不可用")
            return False
            
    except Exception as e:
        logging.error(f"检查GPU失败: {e}")
        return False
    finally:
        ssh.close()

def check_server_time(status=None):
    """检查服务器时间设置"""
    ssh = create_ssh_client()
    try:
        logging.info("检查服务器时间设置...")
        
        # 检查当前时间
        stdin, stdout, stderr = ssh.exec_command('date')
        current_time = stdout.read().decode().strip()
        
        # 检查时区设置
        stdin, stdout, stderr = ssh.exec_command('timedatectl show --property=Timezone --value')
        timezone = stdout.read().decode().strip()
        
        # 检查是否为北京时间
        stdin, stdout, stderr = ssh.exec_command('date "+%Y-%m-%d %H:%M:%S %Z"')
        formatted_time = stdout.read().decode().strip()
        
        logging.info("🕐 服务器时间信息:")
        logging.info(f"  当前时间: {current_time}")
        logging.info(f"  时区设置: {timezone}")
        logging.info(f"  格式化时间: {formatted_time}")
        
        # 判断是否为北京时间
        if 'Asia/Shanghai' in timezone or 'CST' in formatted_time:
            logging.info("✅ 服务器已设置为北京时间")
            
            # 标记步骤完成
            if status:
                mark_step_completed(status, 'server_time_check')
                save_training_status(status)
                logging.info("✅ 服务器时间检查步骤已完成并保存")
            
            return True
        else:
            logging.warning("⚠️ 服务器可能未设置为北京时间")
            logging.info("建议设置为北京时间: sudo timedatectl set-timezone Asia/Shanghai")
            return False
            
    except Exception as e:
        logging.error(f"检查服务器时间失败: {e}")
        return False
    finally:
        ssh.close()

def setup_training_environment(status=None):
    """设置训练环境"""
    ssh = create_ssh_client()
    try:
        logging.info("设置训练环境...")
        
        # 检查并安装必要的包
        commands = [
            'pip install ultralytics',
            'pip install torch torchvision torchaudio',
            'pip install opencv-python',
            'pip install pillow',
            'pip install matplotlib',
            'pip install tensorboard'
        ]
        
        for cmd in commands:
            logging.info(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()  # 等待命令完成
        
        logging.info("✅ 训练环境设置完成")
        
        # 标记步骤完成
        if status:
            mark_step_completed(status, 'environment_setup')
            save_training_status(status)
            logging.info("✅ 环境设置步骤已完成并保存")
        
        return True
        
    except Exception as e:
        logging.error(f"设置环境失败: {e}")
        return False
    finally:
        ssh.close()

def create_training_script(status=None):
    """创建优化的YOLO8多类别训练脚本"""
    # 提取配置值避免f-string中的嵌套引号问题
    object_keywords = TRAINING_CONFIG['object_keywords']
    object_description = TRAINING_CONFIG['object_description']
    project_name = TRAINING_CONFIG['project_name']
    experiment_name = TRAINING_CONFIG['experiment_name']
    base_model = TRAINING_CONFIG['base_model']
    epochs = TRAINING_CONFIG['epochs']
    batch_size = TRAINING_CONFIG['batch_size']
    image_size = TRAINING_CONFIG['image_size']
    workers = TRAINING_CONFIG['workers']
    mixed_precision = TRAINING_CONFIG['mixed_precision']
    save_period = TRAINING_CONFIG['save_period']
    patience = TRAINING_CONFIG['patience']
    num_classes = TRAINING_CONFIG['num_classes']
    class_names = TRAINING_CONFIG['class_names']
    
    training_script = f'''#!/usr/bin/env python3
import torch
from ultralytics import YOLO
import os
import logging
from datetime import datetime
import yaml

# 配置日志
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/yolo8_training.log'),
        logging.StreamHandler()
    ]
)

def check_dataset_config():
    """检查并修复数据集配置"""
    config_path = '/root/yolo_dataset_4classes/dataset.yaml'
    
    if not os.path.exists(config_path):
        logging.error(f"数据集配置文件不存在: {config_path}")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        logging.info(f"原始配置: {config}")
        
        # 设置基本路径
        config['path'] = '/root/yolo_dataset_4classes'
        config['train'] = 'train/images'
        config['val'] = 'val/images'
        
        # 设置类别信息
        config['nc'] = {num_classes}  # 类别数量
        config['names'] = {class_names}  # 类别名称列表
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        logging.info(f"修复后配置: {config}")
        logging.info(f"类别数量: {config['nc']}")
        logging.info(f"类别名称: {config['names']}")
        
        # 验证配置
        if not validate_dataset_config(config):
            return False
            
        return True
    except Exception as e:
        logging.error(f"处理数据集配置失败: {e}")
        return False

def validate_dataset_config(config):
    """验证数据集配置是否正确"""
    try:
        # 检查类别数量
        if config.get('nc') != {num_classes}:
            logging.error(f"类别数量不匹配: 期望 {num_classes}, 实际 {config.get('nc')}")
            return False
        
        # 检查类别名称
        expected_names = {class_names}
        actual_names = config.get('names', [])
        if actual_names != expected_names:
            logging.error(f"类别名称不匹配: 期望 {expected_names}, 实际 {actual_names}")
            return False
        
        # 检查路径配置
        required_paths = ['path', 'train', 'val']
        for path_key in required_paths:
            if path_key not in config:
                logging.error(f"缺少必需的路径配置: {path_key}")
                return False
        
        logging.info("✅ 数据集配置验证通过")
        return True
        
    except Exception as e:
        logging.error(f"验证数据集配置失败: {e}")
        return False

def optimize_for_t4_gpu():
    """针对T4 16GB GPU进行基础优化（使用V3成功配置）"""
    try:
        import torch
        import gc
        
        # 基础GPU缓存清理
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            gc.collect()
            
            # 获取GPU信息
            gpu_name = torch.cuda.get_device_name(0)
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            
            logging.info(f"🔧 GPU基础优化设置:")
            logging.info(f"   GPU型号: {gpu_name}")
            logging.info(f"   GPU内存: {gpu_memory:.1f} GB")
            
            # 基础CUDA优化（与V3一致）
            torch.backends.cudnn.benchmark = True
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
            
            logging.info("✅ 使用V3成功配置参数:")
            logging.info("   - 批次大小: {batch_size}")
            logging.info("   - 图片尺寸: {image_size}")
            logging.info("   - 模型: {base_model}")
            logging.info("   - 工作线程: {workers}")
            logging.info("   - 混合精度: {mixed_precision}")
            logging.info("   - 图像缓存: 禁用")
            logging.info("✅ GPU基础优化设置完成")
            return True
                
    except Exception as e:
        logging.warning(f"⚠️ GPU优化设置失败: {e}")
        return False

def log_training_info():
    """记录训练信息"""
    logging.info("=" * 60)
    logging.info("🎯 YOLO8 多类别工业检测训练")
    logging.info("=" * 60)
    logging.info("📋 训练目标信息:")
    logging.info("   物体关键词: {object_keywords}")
    logging.info("   训练描述: {object_description}")
    logging.info("   项目名称: {project_name}")
    logging.info("   实验版本: {experiment_name}")
    logging.info("   类别数量: {num_classes}")
    logging.info("   类别名称: {class_names}")
    logging.info("📊 优化配置信息:")
    logging.info("   批次大小: {batch_size} (T4优化)")
    logging.info("   图片尺寸: {image_size} (内存优化)")
    logging.info("   基础模型: {base_model} (轻量化)")
    logging.info("   工作线程: {workers} (内存优化)")
    logging.info("   混合精度: {mixed_precision} (内存节省)")
    logging.info("=" * 60)

def main():
    """主训练函数"""
    try:
        log_training_info()
        
        if not check_dataset_config():
            logging.error("数据集配置检查失败，训练中止")
            return

        # T4 GPU内存优化
        logging.info("🔧 正在进行GPU优化设置...")
        optimize_for_t4_gpu()

        logging.info("🤖 开始加载YOLOv8模型...")
        model = YOLO("{base_model}")
        
        logging.info("🚀 开始模型训练...")
        model.train(
            data='/root/yolo_dataset_4classes/dataset.yaml',
            epochs={epochs},
            batch={batch_size},
            imgsz={image_size},
            workers={workers},
            amp={mixed_precision},
            save_period={save_period},
            patience={patience},
            project='{project_name}',
            name='{experiment_name}',
            cache=False,  # 禁用图像缓存以节省内存
            device=0,  # 指定GPU设备
            single_cls=False,  # 多类别检测
            optimizer='AdamW',  # 使用内存友好的优化器
            lr0=0.01,  # 学习率
            lrf=0.01,  # 最终学习率
            momentum=0.937,  # 动量
            weight_decay=0.0005,  # 权重衰减
            warmup_epochs=3,  # 预热轮数
            warmup_momentum=0.8,  # 预热动量
            warmup_bias_lr=0.1,  # 预热偏置学习率
            box=7.5,  # 边界框损失权重
            cls=0.5,  # 分类损失权重
            dfl=1.5,  # 分布焦点损失权重
            pose=12.0,  # 姿态损失权重
            kobj=2.0,  # 关键点对象损失权重
            label_smoothing=0.0,  # 标签平滑
            nbs=64,  # 名义批次大小
            overlap_mask=True,  # 重叠掩码
            mask_ratio=4,  # 掩码比率
            dropout=0.0,  # 丢弃率
            val=True,  # 验证
            plots=True,  # 保存训练图表
            exist_ok=True,  # 允许覆盖现有项目
            pretrained=True,  # 使用预训练权重
            verbose=True,  # 详细输出
            seed=0,  # 随机种子
            deterministic=True,  # 确定性训练
            rect=False,  # 矩形训练
            cos_lr=False,  # 余弦学习率调度
            close_mosaic=10,  # 关闭马赛克增强的轮数
            resume=False,  # 不恢复训练
            fraction=1.0,  # 数据集分数
            profile=False,  # 性能分析
            freeze=None,  # 冻结层
            multi_scale=False,  # 多尺度训练
            copy_paste=0.0,  # 复制粘贴增强
            auto_augment='randaugment',  # 自动增强
            erasing=0.4,  # 随机擦除
            crop_fraction=1.0  # 裁剪分数
        )
        
        logging.info("🎉 训练完成！")
        
    except Exception as e:
        logging.error(f"❌ 训练过程中发生严重错误: {e}", exc_info=True)

if __name__ == '__main__':
    main()
'''
    
    ssh = create_ssh_client()
    try:
        # 创建训练脚本文件
        with open('temp_training_script.py', 'w', encoding='utf-8') as f:
            f.write(training_script)
        
        # 上传训练脚本
        sftp = ssh.open_sftp()
        sftp.put('temp_training_script.py', '/root/train_multiclass_industrial_detection.py')
        sftp.close()
        
        # 删除临时文件
        os.remove('temp_training_script.py')
        
        # 设置执行权限
        stdin, stdout, stderr = ssh.exec_command('chmod +x /root/train_multiclass_industrial_detection.py')
        stdout.read()
        
        logging.info("✅ 训练脚本创建完成")
        
        # 如果提供了状态对象，标记步骤完成
        if status is not None:
            mark_step_completed(status, 'script_creation')
            save_training_status(status)
            logging.info("✅ 脚本创建步骤已标记为完成")
        
        return True
        
    except Exception as e:
        logging.error(f"创建训练脚本失败: {e}")
        return False
    finally:
        ssh.close()

def start_training(status=None):
    """启动训练"""
    ssh = create_ssh_client()
    try:
        logging.info("启动GPU训练...")
        
        # 首先检查训练脚本是否存在
        stdin, stdout, stderr = ssh.exec_command('ls -la /root/train_multiclass_industrial_detection.py')
        script_check = stdout.read().decode().strip()
        error_output = stderr.read().decode().strip()
        
        if error_output or not script_check:
            logging.error("❌ 训练脚本不存在")
            logging.error(f"错误信息: {error_output}")
            logging.info("🔄 尝试重新创建训练脚本...")
            
            # 尝试重新创建训练脚本
            if create_training_script(status):
                logging.info("✅ 训练脚本重新创建成功")
            else:
                logging.error("❌ 训练脚本重新创建失败")
                return False
        else:
            logging.info(f"✅ 训练脚本存在: {script_check}")
        
        # 检查Python版本
        stdin, stdout, stderr = ssh.exec_command('python3 --version')
        python_version = stdout.read().decode().strip()
        logging.info(f"Python版本: {python_version}")
        
        # 使用nohup在后台运行训练，使用python3
        cmd = 'cd /root && nohup python3 train_multiclass_industrial_detection.py > training.log 2>&1 &'
        logging.info(f"执行命令: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        stdout.read()
        
        # 等待更长时间让训练开始
        logging.info("等待训练启动...")
        time.sleep(10)
        
        # 检查训练是否开始
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep train_multiclass_industrial_detection.py | grep -v grep')
        process_info = stdout.read().decode().strip()
        
        if process_info:
            logging.info("✅ 训练已启动")
            logging.info(f"进程信息: {process_info}")
            
            # 显示训练日志的开始部分
            stdin, stdout, stderr = ssh.exec_command('head -30 /root/training.log')
            log_content = stdout.read().decode().strip()
            if log_content:
                logging.info("训练日志:")
                for line in log_content.split('\n'):
                    logging.info(f"  {line}")
            
            # 如果提供了状态对象，标记步骤完成
            if status is not None:
                mark_step_completed(status, 'training_start')
                save_training_status(status)
                logging.info("✅ 训练启动步骤已标记为完成")
            
            return True
        else:
            logging.error("❌ 训练启动失败")
            
            # 检查错误日志
            stdin, stdout, stderr = ssh.exec_command('cat /root/training.log')
            error_log = stdout.read().decode().strip()
            if error_log:
                logging.error(f"错误日志: {error_log}")
            else:
                logging.error("没有找到训练日志文件")
            
            # 检查是否有其他Python进程
            stdin, stdout, stderr = ssh.exec_command('ps aux | grep python')
            python_processes = stdout.read().decode().strip()
            if python_processes:
                logging.info(f"当前Python进程: {python_processes}")
            
            return False
            
    except Exception as e:
        logging.error(f"启动训练失败: {e}")
        return False
    finally:
        ssh.close()

def monitor_training():
    """监控训练进度"""
    ssh = create_ssh_client()
    try:
        logging.info("监控训练进度...")
        
        # 检查训练进程
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep train_black_automotive_clip_detection.py | grep -v grep')
        process_info = stdout.read().decode().strip()
        
        if process_info:
            logging.info("训练正在进行中...")
            
            # 显示最新的训练日志
            stdin, stdout, stderr = ssh.exec_command('tail -10 /root/training.log')
            log_content = stdout.read().decode().strip()
            if log_content:
                logging.info("最新训练日志:")
                for line in log_content.split('\n'):
                    logging.info(f"  {line}")
        else:
            logging.info("训练进程未运行")
            
            # 检查是否有完成的训练结果
            stdin, stdout, stderr = ssh.exec_command('ls -la /root/runs/detect/')
            results = stdout.read().decode().strip()
            if results:
                logging.info("训练结果目录:")
                logging.info(results)
        
    except Exception as e:
        logging.error(f"监控失败: {e}")
    finally:
        ssh.close()

def clean_cloud_dataset(status=None):
    """删除云端现有的训练数据集"""
    ssh = create_ssh_client()
    try:
        logging.info("🗑️ 删除云端现有数据集...")
        
        # 删除旧的数据集目录
        commands = [
            'rm -rf /root/yolo_dataset*',  # 删除所有yolo_dataset相关目录
            'rm -rf /root/pin_detection_data', 
            'rm -rf /root/runs/train/*',
            'rm -f /root/cloud_train*.py',
            'rm -f /root/best_pin_detector*.pt'
        ]
        
        for cmd in commands:
            logging.info(f"执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()  # 等待命令完成
            
        logging.info("✅ 云端数据清理完成")
        
        # 标记步骤完成
        if status:
            mark_step_completed(status, 'cloud_cleanup')
            save_training_status(status)
            logging.info("✅ 云端清理步骤已完成并保存")
        
        return True
        
    except Exception as e:
        logging.error(f"清理云端数据失败: {e}")
        return False
    finally:
        ssh.close()

def upload_file_worker(file_info):
    """单个文件上传工作线程"""
    local_file, remote_file = file_info
    max_retries = 3
    
    # 计算文件哈希用于验证
    file_hash = get_file_hash(local_file)
    if not file_hash:
        logging.error(f"无法计算文件哈希: {local_file}")
        upload_stats['failed'].increment()
        return
    
    for attempt in range(max_retries):
        ssh = None
        sftp = None
        try:
            # 每个线程创建独立的SSH连接
            ssh = create_ssh_client()
            sftp = ssh.open_sftp()
            
            # 上传文件（覆盖模式）
            sftp.put(local_file, remote_file)
            
            # 标记文件为已上传
            mark_file_uploaded(local_file, remote_file, file_hash)
            
            upload_stats['success'].increment()
            success_count = upload_stats['success'].get_value()
            failed_count = upload_stats['failed'].get_value()
            current_time = time.time()
            
            # 更频繁的进度显示（每10个文件或每5秒）
            time_since_last = current_time - (upload_stats['last_update_time'] or upload_stats['start_time'])
            progress_diff = success_count - upload_stats['last_progress_display']
            
            if progress_diff >= 10 or time_since_last >= 5:
                upload_stats['last_update_time'] = current_time
                upload_stats['last_progress_display'] = success_count
                
                # 计算进度百分比
                total_processed = success_count + failed_count
                progress_percent = (total_processed / upload_stats['total']) * 100 if upload_stats['total'] > 0 else 0
                
                # 计算上传速度
                elapsed_time = current_time - upload_stats['start_time']
                upload_speed = success_count / elapsed_time if elapsed_time > 0 else 0
                
                # 估算剩余时间
                remaining_files = upload_stats['total'] - total_processed
                eta_seconds = remaining_files / upload_speed if upload_speed > 0 else 0
                eta_minutes = eta_seconds / 60
                
                # 创建进度条
                bar_length = 30
                filled_length = int(bar_length * progress_percent / 100)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                logging.info(f"📊 上传进度: [{bar}] {progress_percent:.1f}% ({total_processed}/{upload_stats['total']})")
                logging.info(f"   ✅ 成功: {success_count} | ❌ 失败: {failed_count} | 🚀 速度: {upload_speed:.1f} 文件/秒")
                if eta_minutes > 0:
                    if eta_minutes < 1:
                        logging.info(f"   ⏱️  预计剩余时间: {eta_seconds:.0f} 秒")
                    else:
                        logging.info(f"   ⏱️  预计剩余时间: {eta_minutes:.1f} 分钟")
            
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"上传失败，重试 {attempt + 1}/{max_retries}: {os.path.basename(local_file)} - {e}")
                time.sleep(1)  # 等待1秒后重试
            else:
                logging.error(f"上传失败（已重试{max_retries}次）: {os.path.basename(local_file)} - {e}")
                upload_stats['failed'].increment()
                return False
        finally:
            if sftp:
                sftp.close()
            if ssh:
                ssh.close()

def collect_files_to_upload(resume_mode=True):
    """收集需要上传的文件列表
    
    Args:
        resume_mode (bool): 是否启用断点续传模式，True时只收集未上传的文件
    """
    files_to_upload = []
    skipped_files = []
    local_dataset = r"D:\OneDrive\24.Visual AI\data\yolo_dataset_4classes"
    
    # 收集所有文件
    dataset_dirs = [
        ('train/images', '/root/yolo_dataset_4classes/train/images'),
        ('train/labels', '/root/yolo_dataset_4classes/train/labels'),
        ('val/images', '/root/yolo_dataset_4classes/val/images'),
        ('val/labels', '/root/yolo_dataset_4classes/val/labels'),
        ('test/images', '/root/yolo_dataset_4classes/test/images'),
        ('test/labels', '/root/yolo_dataset_4classes/test/labels')
    ]
    
    total_files = 0
    for local_subdir, remote_subdir in dataset_dirs:
        local_path = os.path.join(local_dataset, local_subdir)
        if os.path.exists(local_path):
            for file in os.listdir(local_path):
                if file.endswith(('.jpg', '.jpeg', '.png', '.txt')):
                    total_files += 1
                    local_file = os.path.join(local_path, file)
                    remote_file = f"{remote_subdir}/{file}"
                    
                    # 检查是否启用断点续传且文件已上传
                    if resume_mode and is_file_uploaded(local_file, remote_file):
                        skipped_files.append((local_file, remote_file))
                        continue
                    
                    files_to_upload.append((local_file, remote_file))
    
    if resume_mode and skipped_files:
        logging.info(f"🔄 断点续传模式: 发现 {len(skipped_files)} 个已上传文件，将跳过")
        logging.info(f"📁 总文件数: {total_files}, 需要上传: {len(files_to_upload)}, 已完成: {len(skipped_files)}")
    
    return files_to_upload

def create_remote_directories():
    """创建远程目录结构"""
    ssh = create_ssh_client()
    try:
        commands = [
            'mkdir -p /root/yolo_dataset_4classes/train/images',
            'mkdir -p /root/yolo_dataset_4classes/train/labels', 
            'mkdir -p /root/yolo_dataset_4classes/val/images',
            'mkdir -p /root/yolo_dataset_4classes/val/labels',
            'mkdir -p /root/yolo_dataset_4classes/test/images',
            'mkdir -p /root/yolo_dataset_4classes/test/labels'
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            stdout.read()
            
        return True
    except Exception as e:
        logging.error(f"创建远程目录失败: {e}")
        return False
    finally:
        ssh.close()

def upload_new_dataset(status=None, resume_mode=True):
    """使用20线程批量上传修改后的YOLO数据集"""
    logging.info("🚀 开始20线程批量上传新的YOLO数据集...")
    
    try:
        # 1. 创建远程目录
        if not create_remote_directories():
            logging.error("创建远程目录失败")
            return False
        
        # 2. 上传配置文件
        local_dataset = r"D:\OneDrive\24.Visual AI\data\yolo_dataset_4classes"
        config_file = f"{local_dataset}/dataset.yaml"
        if os.path.exists(config_file):
            ssh = create_ssh_client()
            try:
                sftp = ssh.open_sftp()
                sftp.put(config_file, "/root/yolo_dataset_4classes/dataset.yaml")
                sftp.close()
                logging.info("✅ 配置文件上传完成")
            finally:
                ssh.close()
        
        # 3. 收集文件（根据参数决定是否启用断点续传）
        files_to_upload = collect_files_to_upload(resume_mode=resume_mode)
        if not files_to_upload:
            logging.info("✅ 所有文件都已上传完成，无需重新上传")
            return True
        
        upload_stats['total'] = len(files_to_upload)
        upload_stats['start_time'] = time.time()
        upload_stats['last_update_time'] = upload_stats['start_time']
        upload_stats['last_progress_display'] = 0
        
        # 重置计数器
        upload_stats['success'] = ThreadSafeCounter()
        upload_stats['failed'] = ThreadSafeCounter()
        
        logging.info(f"🚀 开始使用20线程上传 {len(files_to_upload)} 个文件")
        logging.info(f"📊 上传进度: [░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 0.0% (0/{len(files_to_upload)})")
        logging.info(f"   ✅ 成功: 0 | ❌ 失败: 0 | 🚀 速度: 0.0 文件/秒")
        
        # 4. 多线程上传
        with ThreadPoolExecutor(max_workers=20) as executor:
            # 提交所有上传任务
            future_to_file = {executor.submit(upload_file_worker, file_info): file_info for file_info in files_to_upload}
            
            # 等待所有任务完成
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    result = future.result()
                except Exception as e:
                    logging.error(f"任务执行异常: {file_info[0]} - {e}")
                    upload_stats['failed'].increment()
        
        # 5. 最终统计结果
        total_time = time.time() - upload_stats['start_time']
        success_count = upload_stats['success'].get_value()
        failed_count = upload_stats['failed'].get_value()
        total_processed = success_count + failed_count
        
        # 最终进度条（100%）
        bar = '█' * 30
        logging.info(f"\n🎉 上传完成!")
        logging.info(f"📊 最终进度: [{bar}] 100.0% ({total_processed}/{upload_stats['total']})")
        
        logging.info(f"\n📈 详细统计报告:")
        logging.info(f"   📁 总文件数: {upload_stats['total']}")
        logging.info(f"   ✅ 成功上传: {success_count} ({success_count/upload_stats['total']*100:.1f}%)")
        logging.info(f"   ❌ 失败数量: {failed_count} ({failed_count/upload_stats['total']*100:.1f}%)")
        logging.info(f"   ⏱️  总耗时: {total_time:.2f} 秒 ({total_time/60:.1f} 分钟)")
        if total_time > 0:
            logging.info(f"   🚀 平均速度: {success_count/total_time:.2f} 文件/秒")
            logging.info(f"   📊 数据传输效率: {(success_count/upload_stats['total'])*100:.1f}%")
        
        # 如果上传成功且提供了状态对象，标记步骤完成
        if failed_count == 0 and status is not None:
            mark_step_completed(status, 'dataset_upload')
            save_training_status(status)
            logging.info("✅ 数据集上传步骤已标记为完成")
        
        return failed_count == 0
        
    except Exception as e:
        logging.error(f"上传数据集失败: {e}")
        return False

def main():
    """主函数 - 支持断点续传的云端GPU训练流程"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='云端GPU训练脚本 - 支持断点续传')
    parser.add_argument('--reset', action='store_true', help='重置训练状态，从头开始')
    parser.add_argument('--status', action='store_true', help='仅显示当前状态，不执行训练')
    args = parser.parse_args()
    
    logging.info("=== 开始云端GPU训练流程（支持断点续传） ===")
    
    # 加载训练状态
    if args.reset:
        logging.info("🔄 命令行参数指定重置状态...")
        status = reset_training_status()
    else:
        status = load_training_status()
    
    # 显示当前状态
    show_training_status(status)
    
    # 如果只是查看状态，则退出
    if args.status:
        logging.info("📋 状态查看完成，退出程序")
        return True
    
    # 检查是否有未完成的步骤
    completed_steps = sum(status['steps'].values())
    total_steps = len(TRAINING_STEPS)
    
    if completed_steps > 0:
        print(f"\n🔄 检测到之前的训练进度: {completed_steps}/{total_steps} 步骤已完成")
        print("选择操作:")
        print("1. 继续未完成的步骤 (推荐)")
        print("2. 重新开始所有步骤")
        print("3. 查看详细状态后决定")
        print("4. 退出")
        
        while True:
            choice = input("\n请选择 (1-4): ").strip()
            if choice == '1':
                logging.info("🚀 继续执行未完成的步骤...")
                break
            elif choice == '2':
                logging.info("🔄 重置训练状态，重新开始...")
                status = reset_training_status()
                break
            elif choice == '3':
                show_training_status(status)
                continue
            elif choice == '4':
                logging.info("👋 用户选择退出")
                return True
            else:
                print("❌ 无效选择，请输入 1-4")
    else:
        logging.info("🆕 开始新的训练流程...")
    
    # 重置上传统计
    upload_stats['total'] = 0
    upload_stats['success'] = ThreadSafeCounter()
    upload_stats['failed'] = ThreadSafeCounter()
    upload_stats['start_time'] = None
    
    try:
        # 执行训练步骤（支持跳过已完成的步骤）
        
        # 1. 检查GPU状态
        if not is_step_completed(status, 'gpu_check'):
            logging.info("🔍 执行步骤 1/7: GPU状态检查")
            if not check_gpu_status(status):
                logging.error("GPU检查失败，无法继续")
                return False
        else:
            logging.info("✅ 跳过步骤 1/7: GPU状态检查 (已完成)")
        
        # 2. 检查服务器时间
        if not is_step_completed(status, 'server_time_check'):
            logging.info("🔍 执行步骤 2/7: 服务器时间检查")
            check_server_time(status)  # 不强制要求成功，仅作为信息检查
        else:
            logging.info("✅ 跳过步骤 2/7: 服务器时间检查 (已完成)")
        
        # 3. 清理云端旧数据
        if not is_step_completed(status, 'cloud_cleanup'):
            logging.info("🔍 执行步骤 3/7: 清理云端数据")
            if not clean_cloud_dataset(status):
                logging.error("清理云端数据失败，无法继续")
                return False
        else:
            logging.info("✅ 跳过步骤 3/7: 清理云端数据 (已完成)")
        
        # 4. 设置训练环境
        if not is_step_completed(status, 'environment_setup'):
            logging.info("🔍 执行步骤 4/7: 环境设置")
            if not setup_training_environment(status):
                logging.error("环境设置失败，无法继续")
                return False
        else:
            logging.info("✅ 跳过步骤 4/7: 环境设置 (已完成)")
        
        # 5. 上传新数据集
        if not is_step_completed(status, 'dataset_upload'):
            logging.info("🔍 执行步骤 5/7: 数据集上传")
            if not upload_new_dataset(status, resume_enabled):
                logging.error("上传新数据集失败，无法继续")
                return False
        else:
            logging.info("✅ 跳过步骤 5/7: 数据集上传 (已完成)")
        
        # 6. 创建训练脚本
        if not is_step_completed(status, 'script_creation'):
            logging.info("🔍 执行步骤 6/7: 训练脚本创建")
            if not create_training_script(status):
                logging.error("创建训练脚本失败，无法继续")
                return False
        else:
            logging.info("✅ 跳过步骤 6/7: 训练脚本创建 (已完成)")
        
        # 7. 启动训练
        if not is_step_completed(status, 'training_start'):
            logging.info("🔍 执行步骤 7/7: 启动训练")
            if not start_training(status):
                logging.error("启动训练失败")
                return False
        else:
            logging.info("✅ 跳过步骤 7/7: 启动训练 (已完成)")
        
        logging.info("🎉 云端训练流程完成！")
        
        # 显示最终状态
        show_training_status(status)
        
        # 8. 监控训练（可选）
        monitor_choice = input("\n是否开始监控训练进度？(y/n): ")
        if monitor_choice.lower() == 'y':
            monitor_training()
        
        return True
        
    except Exception as e:
        logging.error(f"训练流程出现错误: {e}")
        return False

def handle_upload_progress_options():
    """处理上传进度相关的命令行选项"""
    parser = argparse.ArgumentParser(description='云端GPU训练脚本 - 支持断点续传')
    parser.add_argument('--clear-upload-progress', action='store_true', 
                       help='清空上传进度记录，强制重新上传所有文件')
    parser.add_argument('--show-upload-progress', action='store_true',
                       help='显示当前上传进度记录')
    parser.add_argument('--no-resume', action='store_true',
                       help='禁用断点续传，重新上传所有文件')
    
    args = parser.parse_args()
    
    if args.show_upload_progress:
        show_upload_progress_info()
        return False
    
    if args.clear_upload_progress:
        clear_upload_progress()
        print("✅ 已清空上传进度记录")
        return False
    
    # 返回是否禁用断点续传
    return not args.no_resume

def show_upload_progress_info():
    """显示上传进度信息"""
    progress_data = load_upload_progress()
    
    if not progress_data:
        print("📝 没有找到上传进度记录")
        return
    
    print(f"📊 上传进度记录 (共 {len(progress_data)} 个文件):")
    print("-" * 80)
    
    completed_count = 0
    for remote_file, record in progress_data.items():
        status = record.get('status', 'unknown')
        upload_time = record.get('upload_time', 'unknown')
        local_file = record.get('local_file', 'unknown')
        
        if status == 'completed':
            completed_count += 1
            print(f"✅ {remote_file}")
            print(f"   本地文件: {local_file}")
            print(f"   上传时间: {upload_time}")
        else:
            print(f"❌ {remote_file} (状态: {status})")
        print()
    
    print(f"📈 统计: {completed_count}/{len(progress_data)} 个文件已完成上传")

if __name__ == "__main__":
    # 处理命令行参数
    resume_enabled = handle_upload_progress_options()
    if resume_enabled is False:
        # 如果返回False，说明执行了查看或清空操作，直接退出
        sys.exit(0)
    
    main()