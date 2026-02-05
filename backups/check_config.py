# -*- coding: utf-8 -*-
"""
配置检查脚本 - 验证YOLOv8s + 1024分辨率训练配置
"""

# 训练配置
TRAINING_CONFIG = {
    'epochs': 300,
    'batch_size': 1,  # 保持批次大小=1 以适应YOLOv8s + 1024分辨率
    'learning_rate': 0.01,  # 恢复正常学习率
    'image_size': 1024,  # 恢复原始分辨率 1024*1024
    'base_model': 'yolov8s.pt',  # 使用YOLOv8s模型
    'dataset_path': '/root/yolo_dataset/',
    'workers': 2,  # 适当增加工作线程
    'mixed_precision': True,  # 保持混合精度训练
    'save_period': 10,  # 恢复正常保存频率
    'patience': 50,  # 恢复正常耐心值
    'project_name': 'multi_class_industrial_detection',
    'experiment_name': 'v3_multiclass_kading_bracket_doublepin_yolov8s_1024',  # YOLOv8s + 1024版本
    'object_keywords': '卡丁 支架 双飞卡钉',
    'object_description': 'Multi-class detection with YOLOv8s model at 1024x1024 resolution for T4 GPU',
    'num_classes': 3,
    'class_names': ['卡丁', '支架', '双飞卡钉'],
    'class_config': {
        0: {'name': '卡丁', 'description': 'Standard industrial pins'},
        1: {'name': '支架', 'description': 'Support brackets'},
        2: {'name': '双飞卡钉', 'description': 'Double-wing pins'}
    },
    # YOLOv8s + 1024分辨率优化参数
    'gradient_accumulation_steps': 16,  # 增加梯度累积以模拟更大批次
    'cache_images': False,  # 禁用图像缓存以节省内存
    'device_batch_size': 1,  # 设备批次大小=1
    'max_memory_usage': 0.85,  # 提高内存使用率
    'cpu_fallback': True,  # 启用CPU回退模式
    'memory_fraction': 0.9,  # GPU内存分配比例90%
    'empty_cache_freq': 2,  # 每2步清空缓存
    'pin_memory': False,  # 禁用内存锁定
    'persistent_workers': False,  # 禁用持久化工作进程
    'prefetch_factor': 2,  # 适当的预取因子
    'drop_last': True,  # 丢弃最后不完整的批次
    'shuffle_buffer_size': 200  # 适当的随机缓冲区
}

def main():
    print('=== YOLOv8s + 1024分辨率 训练配置 ===')
    print('基础模型:', TRAINING_CONFIG['base_model'])
    print('图片尺寸:', str(TRAINING_CONFIG['image_size']) + 'x' + str(TRAINING_CONFIG['image_size']))
    print('批次大小:', TRAINING_CONFIG['batch_size'])
    print('梯度累积步数:', TRAINING_CONFIG['gradient_accumulation_steps'])
    print('有效批次大小:', TRAINING_CONFIG['batch_size'], '×', TRAINING_CONFIG['gradient_accumulation_steps'], '=', TRAINING_CONFIG['batch_size'] * TRAINING_CONFIG['gradient_accumulation_steps'])
    print('学习率:', TRAINING_CONFIG['learning_rate'])
    print('工作线程:', TRAINING_CONFIG['workers'])
    print('混合精度:', TRAINING_CONFIG['mixed_precision'])
    print('内存使用率:', str(TRAINING_CONFIG['max_memory_usage']*100) + '%')
    print('GPU内存分配:', str(TRAINING_CONFIG['memory_fraction']*100) + '%')
    print('实验名称:', TRAINING_CONFIG['experiment_name'])
    print()
    
    print('=== 内存优化策略 ===')
    print('图像缓存:', '禁用' if not TRAINING_CONFIG['cache_images'] else '启用')
    print('CPU回退:', '启用' if TRAINING_CONFIG['cpu_fallback'] else '禁用')
    print('缓存清理频率: 每' + str(TRAINING_CONFIG['empty_cache_freq']) + '步')
    print('内存锁定:', '禁用' if not TRAINING_CONFIG['pin_memory'] else '启用')
    print()
    
    print('=== 预估内存需求 ===')
    # YOLOv8s模型参数约11M，1024分辨率下的内存需求
    model_params = 11.2  # Million parameters
    image_memory = (1024 * 1024 * 3 * 4) / (1024**3)  # GB per image (float32)
    batch_memory = image_memory * TRAINING_CONFIG['batch_size']
    gradient_memory = batch_memory * TRAINING_CONFIG['gradient_accumulation_steps']
    model_memory = model_params * 4 / 1024  # MB to GB
    total_estimated = batch_memory + gradient_memory + model_memory + 2  # +2GB for overhead

    print('模型内存: ~' + str(round(model_memory, 2)) + ' GB')
    print('单张图片内存: ~' + str(round(image_memory, 3)) + ' GB')
    print('批次内存: ~' + str(round(batch_memory, 3)) + ' GB')
    print('梯度累积内存: ~' + str(round(gradient_memory, 3)) + ' GB')
    print('预估总内存: ~' + str(round(total_estimated, 2)) + ' GB')
    print('T4 GPU显存: 16 GB')
    print('内存余量:', str(round(16 - total_estimated, 2)) + ' GB')
    print()
    
    if total_estimated <= 16:
        print('✅ 配置应该可以在T4 GPU上运行')
        print('✅ 内存预估合理，可以开始训练')
    else:
        print('⚠️  配置可能超出T4 GPU显存限制')
        print('⚠️  建议进一步优化配置')
    
    print()
    print('=== 配置对比 ===')
    print('相比之前的超级激进配置:')
    print('- 模型: yolov8n.pt → yolov8s.pt (更强的模型)')
    print('- 分辨率: 320x320 → 1024x1024 (保持原始分辨率)')
    print('- 梯度累积: 8步 → 16步 (更大的有效批次)')
    print('- 学习率: 0.005 → 0.01 (恢复正常学习率)')
    print('- 工作线程: 1 → 2 (适当增加并行度)')

if __name__ == '__main__':
    main()