#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import torch
import yaml
import pandas as pd
from PIL import Image
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def verify_models():
    model_dir = r'd:\OneDrive\24.Visual AI\runs\detect\cloud_trained'
    
    print("🔍 验证下载的模型文件...")
    print(f"📁 模型目录: {model_dir}")
    
    verification_results = {}
    
    # 1. 验证模型文件
    model_files = ['best_v3_multiclass_industrial.pt', 'last_v3_multiclass_industrial.pt']
    
    for model_file in model_files:
        model_path = os.path.join(model_dir, model_file)
        print(f"\n🔍 验证模型: {model_file}")
        
        try:
            if os.path.exists(model_path):
                file_size = os.path.getsize(model_path)
                print(f"  📄 文件大小: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
                
                # 尝试加载模型
                try:
                    model = torch.load(model_path, map_location='cpu')
                    print(f"  ✅ 模型加载成功")
                    
                    # 检查模型结构
                    if isinstance(model, dict):
                        if 'model' in model:
                            print(f"  📊 模型包含训练状态信息")
                            if 'epoch' in model:
                                print(f"     训练轮次: {model['epoch']}")
                            if 'best_fitness' in model:
                                print(f"     最佳适应度: {model['best_fitness']:.4f}")
                        else:
                            print(f"  📊 纯模型文件")
                    
                    verification_results[model_file] = "✅ 验证通过"
                    
                except Exception as e:
                    print(f"  ❌ 模型加载失败: {e}")
                    verification_results[model_file] = f"❌ 加载失败: {e}"
                    
            else:
                print(f"  ❌ 文件不存在")
                verification_results[model_file] = "❌ 文件不存在"
                
        except Exception as e:
            print(f"  ❌ 验证出错: {e}")
            verification_results[model_file] = f"❌ 验证出错: {e}"
    
    # 2. 验证配置文件
    config_files = ['training_args.yaml']
    
    for config_file in config_files:
        config_path = os.path.join(model_dir, config_file)
        print(f"\n🔍 验证配置: {config_file}")
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                print(f"  ✅ 配置文件加载成功")
                print(f"  📊 配置项数量: {len(config) if config else 0}")
                
                # 显示关键配置
                if config:
                    key_configs = ['model', 'data', 'epochs', 'batch', 'imgsz']
                    for key in key_configs:
                        if key in config:
                            print(f"     {key}: {config[key]}")
                
                verification_results[config_file] = "✅ 验证通过"
            else:
                print(f"  ❌ 文件不存在")
                verification_results[config_file] = "❌ 文件不存在"
                
        except Exception as e:
            print(f"  ❌ 验证出错: {e}")
            verification_results[config_file] = f"❌ 验证出错: {e}"
    
    # 3. 验证训练结果文件
    result_files = ['training_results.csv']
    
    for result_file in result_files:
        result_path = os.path.join(model_dir, result_file)
        print(f"\n🔍 验证结果: {result_file}")
        
        try:
            if os.path.exists(result_path):
                df = pd.read_csv(result_path)
                print(f"  ✅ 结果文件加载成功")
                print(f"  📊 训练记录数: {len(df)}")
                print(f"  📊 指标列数: {len(df.columns)}")
                
                # 显示最后几行的关键指标
                if len(df) > 0:
                    last_row = df.iloc[-1]
                    key_metrics = ['epoch', 'train/box_loss', 'train/cls_loss', 'val/box_loss', 'val/cls_loss']
                    print(f"  📈 最终训练指标:")
                    for metric in key_metrics:
                        if metric in df.columns:
                            print(f"     {metric}: {last_row[metric]:.4f}")
                
                verification_results[result_file] = "✅ 验证通过"
            else:
                print(f"  ❌ 文件不存在")
                verification_results[result_file] = "❌ 文件不存在"
                
        except Exception as e:
            print(f"  ❌ 验证出错: {e}")
            verification_results[result_file] = f"❌ 验证出错: {e}"
    
    # 4. 验证图像文件
    image_files = ['training_results.png', 'confusion_matrix.png']
    
    for image_file in image_files:
        image_path = os.path.join(model_dir, image_file)
        print(f"\n🔍 验证图像: {image_file}")
        
        try:
            if os.path.exists(image_path):
                img = Image.open(image_path)
                print(f"  ✅ 图像文件加载成功")
                print(f"  📊 图像尺寸: {img.size}")
                print(f"  📊 图像模式: {img.mode}")
                
                verification_results[image_file] = "✅ 验证通过"
            else:
                print(f"  ❌ 文件不存在")
                verification_results[image_file] = "❌ 文件不存在"
                
        except Exception as e:
            print(f"  ❌ 验证出错: {e}")
            verification_results[image_file] = f"❌ 验证出错: {e}"
    
    # 5. 生成验证报告
    print(f"\n📋 验证结果汇总:")
    passed = 0
    total = len(verification_results)
    
    for file, result in verification_results.items():
        print(f"  📄 {file}: {result}")
        if "✅" in result:
            passed += 1
    
    print(f"\n📊 验证统计:")
    print(f"  总文件数: {total}")
    print(f"  验证通过: {passed}")
    print(f"  验证失败: {total - passed}")
    print(f"  通过率: {passed/total*100:.1f}%")
    
    # 保存验证报告
    report_path = os.path.join(model_dir, 'verification_report.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("YOLOv8 多类工业检测模型验证报告\n")
        f.write(f"验证时间: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("验证结果:\n")
        for file, result in verification_results.items():
            f.write(f"  {file}: {result}\n")
        f.write(f"\n验证统计:\n")
        f.write(f"  总文件数: {total}\n")
        f.write(f"  验证通过: {passed}\n")
        f.write(f"  验证失败: {total - passed}\n")
        f.write(f"  通过率: {passed/total*100:.1f}%\n")
    
    print(f"\n📋 验证报告已保存: {report_path}")
    
    return passed == total

if __name__ == "__main__":
    success = verify_models()
    if success:
        print("\n✅ 所有文件验证通过！")
    else:
        print("\n⚠️ 部分文件验证失败，请检查验证报告。")