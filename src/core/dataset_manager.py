import os
import json
import yaml

class DatasetManager:
    """数据集管理模块"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
    
    def check_dataset(self, dataset_path):
        """检查数据集"""
        try:
            # 检查必要的目录结构
            required_dirs = ['images', 'labels']
            for dir_name in required_dirs:
                dir_path = os.path.join(dataset_path, dir_name)
                if not os.path.exists(dir_path):
                    return False, f"缺少目录: {dir_path}"
            
            # 检查图像文件
            images_dir = os.path.join(dataset_path, 'images')
            image_files = [f for f in os.listdir(images_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
            if not image_files:
                return False, "未找到图像文件"
            
            # 检查标签文件
            labels_dir = os.path.join(dataset_path, 'labels')
            label_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
            if not label_files:
                return False, "未找到标签文件"
            
            return True, f"数据集检查通过，找到 {len(image_files)} 个图像和 {len(label_files)} 个标签"
        except Exception as e:
            return False, str(e)
    
    def create_yaml(self, dataset_path, classes):
        """创建数据集YAML文件"""
        try:
            yaml_content = {
                'path': dataset_path,
                'train': 'images',
                'val': 'images',
                'names': {i: cls for i, cls in enumerate(classes)}
            }
            
            yaml_file = os.path.join(dataset_path, 'dataset.yaml')
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(yaml_content, f, allow_unicode=True)
            
            return True, yaml_file
        except Exception as e:
            return False, str(e)
    
    def get_dataset_info(self, dataset_path):
        """获取数据集信息"""
        try:
            # 统计图像数量
            images_dir = os.path.join(dataset_path, 'images')
            image_files = [f for f in os.listdir(images_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
            
            # 统计标签数量
            labels_dir = os.path.join(dataset_path, 'labels')
            label_files = [f for f in os.listdir(labels_dir) if f.endswith('.txt')]
            
            # 读取类别信息
            yaml_file = os.path.join(dataset_path, 'dataset.yaml')
            classes = []
            if os.path.exists(yaml_file):
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    yaml_content = yaml.safe_load(f)
                    if yaml_content and 'names' in yaml_content:
                        classes = list(yaml_content['names'].values())
            
            return {
                'image_count': len(image_files),
                'label_count': len(label_files),
                'class_count': len(classes),
                'classes': classes
            }
        except Exception as e:
            return {'error': str(e)}
