#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复cloud_training_gui.py中的f-string语法错误
问题：第2028行开始的f-string没有正确关闭，导致整个文件结构混乱
"""

def fix_fstring_issue():
    file_path = "cloud_training_gui.py"
    
    print("正在读取文件...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"原始文件共有 {len(lines)} 行")
    
    # 找到create_training_script_content方法的开始和结束
    method_start = None
    for i, line in enumerate(lines):
        if "def create_training_script_content(self):" in line:
            method_start = i
            break
    
    if method_start is None:
        print("错误：找不到create_training_script_content方法")
        return
    
    print(f"找到create_training_script_content方法开始于第 {method_start + 1} 行")
    
    # 找到下一个方法的开始位置（upload_dataset）
    next_method_start = None
    for i in range(method_start + 1, len(lines)):
        line = lines[i].strip()
        if line.startswith("def ") and "upload_dataset" in line:
            next_method_start = i
            break
    
    if next_method_start is None:
        print("错误：找不到upload_dataset方法")
        return
    
    print(f"找到upload_dataset方法开始于第 {next_method_start + 1} 行")
    
    # 创建新的create_training_script_content方法内容
    new_method_content = '''    def create_training_script_content(self):
        """创建训练脚本内容"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_name = self.dataset_config['dataset_name']
        num_classes = self.dataset_config['num_classes']
        remote_path = self.dataset_config['remote_path']
        epochs = self.training_config['epochs']
        batch_size = self.training_config['batch_size']
        learning_rate = self.training_config['learning_rate']
        image_size = self.training_config['image_size']
        base_model = self.training_config['base_model']
        
        return f"""#!/usr/bin/env python3
# -*- coding: utf-8 -*-
\"\"\"
自动生成的YOLO训练脚本
数据集: {dataset_name}
类别数: {num_classes}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
训练参数: epochs={epochs}, batch={batch_size}, lr={learning_rate}
\"\"\"

import os
import sys
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
        dataset_path = "{remote_path}"
        yaml_path = os.path.join(dataset_path, "data.yaml")
        
        # 检查数据集
        if not os.path.exists(yaml_path):
            logger.error(f"数据集配置文件不存在: {{yaml_path}}")
            return
        
        # 加载YOLO模型
        model = YOLO("{base_model}")
        
        # 开始训练
        logger.info("开始训练...")
        results = model.train(
            data=yaml_path,
            epochs={epochs},
            batch={batch_size},
            lr0={learning_rate},
            imgsz={image_size},
            device='auto',
            project='runs/train',
            name='yolo_training_{{timestamp}}',
            save=True,
            save_period=10,
            val=True,
            plots=True
        )
        
        logger.info("训练完成！")
        return results
        
    except Exception as e:
        logger.error(f"训练失败: {{e}}")
        raise

if __name__ == "__main__":
    main()
"""

'''
    
    # 构建新的文件内容
    new_lines = []
    
    # 添加方法开始之前的内容
    new_lines.extend(lines[:method_start])
    
    # 添加新的方法内容
    new_lines.append(new_method_content)
    
    # 添加upload_dataset方法及之后的内容（确保正确的缩进）
    upload_method_line = lines[next_method_start].strip()
    new_lines.append(f"    {upload_method_line}\n")  # 确保正确的缩进
    
    # 添加upload_dataset方法的其余内容
    new_lines.extend(lines[next_method_start + 1:])
    
    # 写入修复后的文件
    print("正在写入修复后的文件...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"修复完成！")
    print(f"删除了第 {method_start + 1} 到第 {next_method_start} 行的孤立代码")
    print(f"新文件共有 {len(new_lines)} 行")
    print(f"减少了 {len(lines) - len(new_lines)} 行")

if __name__ == "__main__":
    fix_fstring_issue()