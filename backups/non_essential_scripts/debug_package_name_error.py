#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试package_name错误的脚本
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from cloud_training_gui import CloudTrainingGUI
    import tkinter as tk
    
    print("开始调试package_name错误...")
    
    # 创建GUI实例
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    gui = CloudTrainingGUI(root)
    
    print("GUI实例创建成功")
    
    # 尝试生成训练脚本内容
    print("开始生成训练脚本内容...")
    try:
        script_content = gui.create_training_script_content()
        print("✓ 训练脚本内容生成成功")
        
        # 检查脚本内容中是否有语法错误
        print("检查脚本语法...")
        try:
            compile(script_content, '<string>', 'exec')
            print("✓ 脚本语法检查通过")
        except SyntaxError as syntax_error:
            print(f"✗ 脚本语法错误: {syntax_error}")
            print(f"错误位置: 行 {syntax_error.lineno}")
            
            # 显示错误附近的代码
            lines = script_content.split('\n')
            start = max(0, syntax_error.lineno - 3)
            end = min(len(lines), syntax_error.lineno + 3)
            print("错误附近的代码:")
            for i in range(start, end):
                marker = ">>> " if i == syntax_error.lineno - 1 else "    "
                print(f"{marker}{i+1:3d}: {lines[i]}")
                
    except Exception as e:
        print(f"✗ 生成训练脚本时出错: {e}")
        import traceback
        print("详细错误信息:")
        traceback.print_exc()
        
        # 尝试找到具体的错误行
        tb = traceback.extract_tb(e.__traceback__)
        for frame in tb:
            if 'cloud_training_gui.py' in frame.filename:
                print(f"错误发生在文件: {frame.filename}")
                print(f"错误发生在行: {frame.lineno}")
                print(f"错误发生在函数: {frame.name}")
                print(f"错误代码: {frame.line}")
                break
    
    root.destroy()
    
except Exception as e:
    print(f"导入或初始化失败: {e}")
    import traceback
    traceback.print_exc()

print("调试完成")