import os
import json

class ConfigManager:
    """配置管理模块"""
    
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.server_config = {
            'host': '127.0.0.1',
            'port': 22,
            'user': 'ubuntu',
            'password': '',
            'key_file': '',
            'remote_path': '/home/ubuntu/training'
        }
        self.dataset_config = {
            'dataset_path': '',
            'classes': [],
            'num_classes': 0,
            'yaml_file': ''
        }
        self.training_config = {
            'epochs': 100,
            'batch_size': 16,
            'learning_rate': 0.01,
            'image_size': 640,
            'base_model': 'yolov8n.pt',
            'model_name_suffix': '',
            'augmentation': {
                'scale': 0.5,
                'fliplr': 0.5,
                'hsv_h': 0.015,
                'hsv_s': 0.7,
                'hsv_v': 0.4,
                'augmentation_enabled': True
            }
        }
        self.config = {
            'server': self.server_config,
            'dataset': self.dataset_config,
            'training': self.training_config,
            'upload': {
                'max_workers': 8,
                'retry_times': 3
            }
        }
        self._load_config()
    
    def _load_config(self):
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
                    if 'upload' in cfg:
                        self.config['upload'].update(cfg['upload'])
        except Exception as e:
            print(f"加载配置失败: {e}")
    
    def save_config(self, cfg=None):
        """保存配置"""
        try:
            if isinstance(cfg, dict):
                if 'server' in cfg:
                    self.server_config.update(cfg['server'])
                if 'dataset' in cfg:
                    self.dataset_config.update(cfg['dataset'])
                if 'training' in cfg:
                    self.training_config.update(cfg['training'])
                if 'upload' in cfg:
                    self.config['upload'].update(cfg['upload'])
            
            out = {
                'server': self.server_config,
                'dataset': self.dataset_config,
                'training': self.training_config,
                'upload': self.config['upload']
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def get_config(self):
        """获取配置"""
        return {
            'server': dict(self.server_config),
            'dataset': dict(self.dataset_config),
            'training': dict(self.training_config),
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
        elif section == 'upload':
            self.config['upload'][key] = value
        return self.save_config()
