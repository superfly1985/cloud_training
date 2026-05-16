import os
import json

class ConfigManager:
    """配置管理模块"""
    
    def __init__(self, config_file=None):
        if config_file is None:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            config_file = os.path.join(base_dir, 'cloud_training_config.json')
        self.config_file = config_file
        
        # 使用与旧版完全一致的键名
        self.server_config = {
            'hostname': '127.0.0.1',
            'port': 22,
            'username': 'root',
            'password': ''
        }
        
        self.dataset_config = {
            'local_path': '',
            'remote_path': '/root/yolo_dataset',
            'dataset_name': '',
            'classes': [],
            'num_classes': 0
        }
        
        self.training_config = {
            'epochs': 300,
            'batch_size': 20,
            'learning_rate': 0.01,
            'image_size': 1024,
            'base_model': 'yolov8s.pt',
            'model_name_suffix': '',
            'augment_scale': 0.5,
            'augment_fliplr': 0.5,
            'augment_flipud': 0.0,
            'augment_perspective': 0.0,
            'augment_hsv_h': 0.015,
            'augment_hsv_s': 0.7,
            'augment_hsv_v': 0.4,
            'augment_scale_active': True,
            'augment_fliplr_active': True,
            'augment_flipud_active': True,
            'augment_perspective_active': True,
            'augment_hsv_h_active': True,
            'augment_hsv_s_active': True,
            'augment_hsv_v_active': True,
        }
        
        self.ui_config = {
            'window_width': 1240,
            'window_height': 900,
            'window_state': 'normal',  # 'normal' or 'zoomed'
            'window_x': -1,
            'window_y': -1
        }

        # 转换配置：与训练环境解耦，避免依赖冲突
        self.convert_config = {
            'python_export_cmd': '',
            'tflite_format': 'fp32'  # fp32 or fp16
        }
        
        self.config = {
            'server': self.server_config,
            'dataset': self.dataset_config,
            'training': self.training_config,
            'ui': self.ui_config,
            'convert': self.convert_config,
            'upload': {
                'max_workers': 8,
                'retry_times': 3
            }
        }
        # 供字段映射层直接访问上传配置
        self.upload_config = self.config['upload']
        self.load_config()
    
    def load_config(self):
        """加载配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                if isinstance(cfg, dict):
                    if 'server' in cfg:
                        self.server_config.update(cfg['server'])
                    if 'dataset' in cfg:
                        self.dataset_config.update(cfg['dataset'])
                    if 'training' in cfg:
                        self.training_config.update(cfg['training'])
                    if 'ui' in cfg:
                        self.ui_config.update(cfg['ui'])
                    if 'convert' in cfg:
                        self.convert_config.update(cfg['convert'])
                    if 'upload' in cfg:
                        self.config['upload'].update(cfg['upload'])
        except Exception as e:
            print(f"加载配置失败: {e}")
    
    def save_config(self):
        """保存配置"""
        try:
            out = {
                'server': self.server_config,
                'dataset': self.dataset_config,
                'training': self.training_config,
                'ui': self.ui_config,
                'convert': self.convert_config,
                'upload': self.config['upload']
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=4)
            return True, "配置保存成功"
        except Exception as e:
            error_msg = f"保存配置失败: {e}"
            print(error_msg)
            return False, error_msg
    
    def get_config(self):
        """获取配置"""
        return {
            'server': dict(self.server_config),
            'dataset': dict(self.dataset_config),
            'training': dict(self.training_config),
            'convert': dict(self.convert_config),
            'upload': dict(self.config['upload'])
        }
    
    def update_config(self, section, key, value):
        """更新配置"""
        if section == 'server':
            self.server_config[key] = value
        elif section == 'dataset':
            self.dataset_config[key] = value
        elif section == 'training':
            self.training_config[key] = value
        elif section == 'convert':
            self.convert_config[key] = value
        elif section == 'upload':
            self.config['upload'][key] = value
        return self.save_config()
