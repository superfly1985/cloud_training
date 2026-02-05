#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成的YOLO训练脚本
数据集: yolo_dataset
类别数: 5
生成时间: 2025-09-28 18:54:59
训练参数: epochs=50, batch=20, lr=0.01
"""

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
        dataset_path = "/root/yolo_dataset"
        yaml_path = os.path.join(dataset_path, "dataset.yaml")
        
        # 检查数据集
        if not os.path.exists(yaml_path):
            logger.error(f"数据集配置文件不存在: {yaml_path}")
            return
        
        # 检查并下载YOLO模型
        model_name = "yolov11s.pt"
        logger.info(f"准备加载模型: {model_name}")
        
        def download_model_with_retry(model_name, max_retries=3):
            """带重试机制的模型下载函数"""
            import urllib.request
            import urllib.error
            import time
            import ssl
            
            # 创建SSL上下文，忽略证书验证（用于网络问题）
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"第 {attempt + 1} 次尝试加载模型: {model_name}")
                    
                    # 首先尝试直接加载（可能已存在）
                    if os.path.exists(model_name):
                        model = YOLO(model_name)
                        logger.info(f"模型 {model_name} 从本地加载成功")
                        return model
                    
                    # 尝试让YOLO自动下载
                    model = YOLO(model_name)
                    logger.info(f"模型 {model_name} 自动下载并加载成功")
                    return model
                    
                except Exception as e:
                    logger.warning(f"第 {attempt + 1} 次尝试失败: {e}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10  # 递增等待时间
                        logger.info(f"等待 {wait_time} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"所有 {max_retries} 次尝试都失败了")
                        raise e
            
            return None
        
        # 使用改进的下载函数
        try:
            model = download_model_with_retry(model_name)
            if model is None:
                raise Exception("模型下载失败")
        except Exception as e:
            logger.error(f"模型下载最终失败: {e}")
            logger.info("尝试使用备用方案...")
            
            # 备用方案：尝试使用其他可用的模型
            backup_models = ["yolov8s.pt", "yolov8n.pt", "yolov11s.pt", "yolov11n.pt"]
            model = None
            
            for backup_model in backup_models:
                if backup_model != model_name:
                    try:
                        logger.info(f"尝试备用模型: {backup_model}")
                        model = YOLO(backup_model)
                        logger.info(f"备用模型 {backup_model} 加载成功")
                        break
                    except Exception as backup_error:
                        logger.warning(f"备用模型 {backup_model} 也失败: {backup_error}")
                        continue
            
            if model is None:
                logger.error("所有模型下载尝试都失败，无法继续训练")
                raise Exception("无法下载任何可用的YOLO模型")
        
        # 开始训练
        logger.info("开始训练...")
        results = model.train(
            data=yaml_path,
            epochs=50,
            batch=20,
            lr0=0.01,
            imgsz=1024,
            device='0',
            project='runs/train',
            name='yolo_training_20250928_185459',
            save=True,
            save_period=10,
            val=True,
            plots=True
        )
        
        logger.info("训练完成！")
        return results
        
    except Exception as e:
        logger.error(f"训练失败: {e}")
        raise

if __name__ == "__main__":
    main()
