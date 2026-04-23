import os
import time

class TrainingManager:
    """训练管理模块"""
    
    def __init__(self, config_manager, server_manager):
        self.config_manager = config_manager
        self.server_manager = server_manager
    
    def generate_training_script(self, dataset_path, model_name):
        """生成训练脚本"""
        try:
            training_config = self.config_manager.training_config
            
            script_content = f"""
# 训练脚本
import os
import sys

# 检查CUDA
try:
    import torch
    if torch.cuda.is_available():
        print('CUDA available:', torch.cuda.get_device_name(0))
    else:
        print('CUDA not available')
except Exception as e:
    print('CUDA check failed:', e)

# 安装依赖
print('Installing dependencies...')
os.system('pip install -q ultralytics')

# 开始训练
print('Starting training...')

# 训练命令
train_cmd = [
    'yolo', 'train',
    'data={dataset_path}/dataset.yaml',
    'model={base_model}',
    'epochs={epochs}',
    'batch={batch_size}',
    'lr0={learning_rate}',
    'imgsz={image_size}',
    'name={model_name}',
    'project=./runs/train'
]

# 添加增强参数
augmentation = {augmentation}
if augmentation.get('augmentation_enabled', True):
    train_cmd.extend([
        'scale={scale}',
        'fliplr={fliplr}',
        'hsv_h={hsv_h}',
        'hsv_s={hsv_s}',
        'hsv_v={hsv_v}'
    ])

print('Training command:', ' '.join(train_cmd))
os.system(' '.join(train_cmd))

print('Training completed!')
""".format(
    dataset_path=dataset_path,
    base_model=training_config['base_model'],
    epochs=training_config['epochs'],
    batch_size=training_config['batch_size'],
    learning_rate=training_config['learning_rate'],
    image_size=training_config['image_size'],
    model_name=model_name,
    augmentation=training_config['augmentation'],
    scale=training_config['augmentation'].get('scale', 0.5),
    fliplr=training_config['augmentation'].get('fliplr', 0.5),
    hsv_h=training_config['augmentation'].get('hsv_h', 0.015),
    hsv_s=training_config['augmentation'].get('hsv_s', 0.7),
    hsv_v=training_config['augmentation'].get('hsv_v', 0.4)
)
            
            return script_content
        except Exception as e:
            return f"生成脚本失败: {e}"
    
    def start_training(self, dataset_path):
        """开始训练"""
        try:
            # 生成模型名称
            training_config = self.config_manager.training_config
            base_model_name = os.path.splitext(os.path.basename(training_config['base_model']))[0]
            suffix = training_config['model_name_suffix']
            model_name = f"{base_model_name}{'_' + suffix if suffix else ''}"
            
            # 生成训练脚本
            script_content = self.generate_training_script(dataset_path, model_name)
            
            # 上传脚本到服务器
            remote_script_path = os.path.join(self.config_manager.server_config['remote_path'], 'train.py')
            local_script_path = 'train_temp.py'
            
            with open(local_script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            success, message = self.server_manager.upload_file(local_script_path, remote_script_path)
            if not success:
                return False, message
            
            # 执行训练脚本
            command = f'cd {self.config_manager.server_config["remote_path"]} && python train.py'
            success, output = self.server_manager.execute_command(command)
            
            # 清理临时文件
            if os.path.exists(local_script_path):
                os.remove(local_script_path)
            
            return success, output
        except Exception as e:
            return False, str(e)
    
    def get_training_status(self):
        """获取训练状态"""
        try:
            # 检查训练进程
            command = 'ps aux | grep train.py | grep -v grep'
            success, output = self.server_manager.execute_command(command)
            
            if success and output:
                return True, "训练中"
            return False, "未在训练"
        except Exception as e:
            return False, str(e)
