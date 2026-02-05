#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的调试测试脚本 - 精确定位package_name错误
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_script_generation():
    """测试训练脚本生成功能"""
    try:
        print("开始测试训练脚本生成...")
        
        # 导入GUI类
        from cloud_training_gui import CloudTrainingGUI
        import tkinter as tk
        
        # 创建根窗口（但不显示）
        root = tk.Tk()
        root.withdraw()  # 隐藏窗口
        
        # 创建GUI实例
        gui = CloudTrainingGUI(root)
        
        print("GUI实例创建成功")
        
        # 尝试调用create_training_script_content方法
        print("调用create_training_script_content方法...")
        script_content = gui.create_training_script_content()
        
        print("✓ 训练脚本生成成功")
        print(f"脚本长度: {len(script_content)} 字符")
        
        # 检查脚本内容中是否有语法错误
        print("检查生成的脚本语法...")
        try:
            compile(script_content, '<generated_script>', 'exec')
            print("✓ 生成的脚本语法正确")
        except SyntaxError as syntax_error:
            print(f"✗ 生成的脚本语法错误: {syntax_error}")
            print(f"错误行号: {syntax_error.lineno}")
            print(f"错误文本: {syntax_error.text}")
            
            # 显示错误附近的代码
            lines = script_content.split('\n')
            start_line = max(0, syntax_error.lineno - 3)
            end_line = min(len(lines), syntax_error.lineno + 2)
            
            print("错误附近的代码:")
            for i in range(start_line, end_line):
                marker = ">>> " if i == syntax_error.lineno - 1 else "    "
                print(f"{marker}{i+1:3d}: {lines[i]}")
        
        # 检查是否包含package_name变量的孤立引用
        print("检查package_name引用...")
        lines = script_content.split('\n')
        for i, line in enumerate(lines):
            if 'package_name' in line and 'def ' not in line and 'import_name = package_name' not in line:
                # 检查这行是否在函数内部
                # 简单的检查：向上查找最近的函数定义
                in_function = False
                for j in range(i-1, -1, -1):
                    if lines[j].strip().startswith('def '):
                        in_function = True
                        break
                    elif lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                        # 遇到了顶级代码，说明不在函数内
                        break
                
                if not in_function:
                    print(f"⚠ 发现可能的孤立package_name引用在第{i+1}行: {line.strip()}")
        
        root.destroy()
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_script_generation()
    if success:
        print("\n✓ 所有测试通过")
    else:
        print("\n✗ 测试失败")