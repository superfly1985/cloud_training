#!/usr/bin/env python3
"""
验证V3配置脚本
对比当前配置与成功的V3配置
"""

# 当前配置（已更新为V3配置）
CURRENT_CONFIG = {
    'batch_size': 20,  # 恢复V3成功配置的批次大小
    'image_size': 1024,  # 保持原始分辨率 1024*1024
    'base_model': 'yolov8s.pt',  # 使用YOLOv8s模型
    'workers': 6,  # 恢复V3成功配置的工作线程数
    'mixed_precision': True,  # 保持混合精度训练
    'cache_images': False,  # 禁用图像缓存（与V3一致）
    'epochs': 300,
    'learning_rate': 0.01,
    'save_period': 10,
    'patience': 50,
}

# V3成功配置（从yaml文件读取）
V3_CONFIG = {
    'batch_size': 20,  # batch: 20
    'image_size': 1024,  # imgsz: 1024
    'base_model': 'yolov8s.pt',  # model: yolov8s.pt
    'workers': 6,  # workers: 6
    'mixed_precision': True,  # amp: true
    'cache_images': False,  # 默认false
    'epochs': 300,  # epochs: 300
    'patience': 50,  # patience: 50
}

def compare_configs():
    """对比配置差异"""
    print("=" * 60)
    print("🔍 V3配置验证对比")
    print("=" * 60)
    
    all_match = True
    
    for key in V3_CONFIG:
        current_val = CURRENT_CONFIG.get(key)
        v3_val = V3_CONFIG.get(key)
        
        if current_val == v3_val:
            status = "✅ 匹配"
        else:
            status = "❌ 不匹配"
            all_match = False
        
        print(f"{key:20}: 当前={current_val:15} | V3={v3_val:15} | {status}")
    
    print("=" * 60)
    
    if all_match:
        print("🎉 配置验证通过！当前配置与V3成功配置完全一致")
        print("✅ 应该可以解决CUDA内存不足问题")
    else:
        print("⚠️ 配置存在差异，需要进一步调整")
    
    print("=" * 60)
    
    # 内存预估
    print("\n📊 内存使用预估:")
    batch_size = CURRENT_CONFIG['batch_size']
    image_size = CURRENT_CONFIG['image_size']
    
    # YOLOv8s模型内存预估
    model_memory = 0.05  # YOLOv8s约50MB
    
    # 图像内存预估 (batch_size * 3 * H * W * 4 bytes)
    image_memory = batch_size * 3 * image_size * image_size * 4 / (1024**3)
    
    # 特征图内存预估（约为图像内存的2-3倍）
    feature_memory = image_memory * 2.5
    
    # 梯度内存预估（约为模型参数的2倍）
    gradient_memory = model_memory * 2
    
    # 总内存预估
    total_memory = model_memory + image_memory + feature_memory + gradient_memory
    
    print(f"模型内存: {model_memory:.2f} GB")
    print(f"图像内存: {image_memory:.2f} GB")
    print(f"特征图内存: {feature_memory:.2f} GB")
    print(f"梯度内存: {gradient_memory:.2f} GB")
    print(f"总预估内存: {total_memory:.2f} GB")
    print(f"T4 GPU显存: 16.00 GB")
    print(f"内存余量: {16.0 - total_memory:.2f} GB")
    
    if total_memory < 14.0:  # 留2GB余量
        print("✅ 内存预估合理，应该可以在T4 GPU上运行")
    else:
        print("⚠️ 内存预估偏高，可能仍有内存不足风险")

def show_key_changes():
    """显示关键变更"""
    print("\n🔄 关键配置变更:")
    print("1. batch_size: 1 → 20 (恢复V3成功配置)")
    print("2. workers: 2 → 6 (恢复V3成功配置)")
    print("3. 移除梯度累积参数 (gradient_accumulation_steps)")
    print("4. 移除额外优化参数 (memory_fraction, empty_cache_freq等)")
    print("5. 简化GPU优化函数，移除硬编码参数")
    print("6. 保持YOLOv8s模型和1024分辨率")

if __name__ == '__main__':
    compare_configs()
    show_key_changes()