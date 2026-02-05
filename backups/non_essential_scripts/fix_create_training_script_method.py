#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复create_training_script_content方法的结构问题
"""

import re

def fix_create_training_script_method():
    """修复create_training_script_content方法的结构问题"""
    
    file_path = "cloud_training_gui.py"
    
    print("读取文件...")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 找到create_training_script_content方法的开始和结束
    method_start = content.find("def create_training_script_content(self):")
    if method_start == -1:
        print("❌ 未找到create_training_script_content方法")
        return False
    
    # 找到下一个方法的开始（作为当前方法的结束）
    next_method_start = content.find("\n    def ", method_start + 1)
    if next_method_start == -1:
        print("❌ 未找到下一个方法")
        return False
    
    print(f"方法位置: {method_start} - {next_method_start}")
    
    # 提取方法内容
    method_content = content[method_start:next_method_start]
    
    print("分析方法结构...")
    
    # 检查是否有孤立的函数定义
    if "def ensure_package_available" in method_content and "return f'''" in method_content:
        print("✅ 发现结构问题：ensure_package_available函数定义在方法内部但不在f-string中")
        
        # 找到return f'''的位置
        return_pos = method_content.find("return f'''")
        if return_pos == -1:
            print("❌ 未找到return f'''")
            return False
        
        # 找到ensure_package_available函数定义的位置
        func_def_pos = method_content.find("def ensure_package_available")
        if func_def_pos == -1:
            print("❌ 未找到ensure_package_available函数定义")
            return False
        
        if func_def_pos > return_pos:
            print("✅ 确认问题：ensure_package_available函数定义在return语句之后")
            
            # 提取方法开始到return语句的部分
            method_header = method_content[:return_pos]
            
            # 提取return语句开始的部分（应该是完整的f-string）
            return_part = method_content[return_pos:]
            
            # 找到f-string的结束位置（第一个单独的'''）
            fstring_end = return_part.find("'''", 10)  # 跳过开始的'''
            if fstring_end == -1:
                print("❌ 未找到f-string结束")
                return False
            
            # 提取f-string内容
            fstring_content = return_part[:fstring_end + 3]
            
            # 提取f-string之后的内容（这些应该被删除）
            after_fstring = return_part[fstring_end + 3:]
            
            print(f"f-string长度: {len(fstring_content)}")
            print(f"f-string之后的内容长度: {len(after_fstring)}")
            
            # 重新构建方法
            new_method_content = method_header + fstring_content + "\n"
            
            # 替换原始内容
            new_content = content[:method_start] + new_method_content + content[next_method_start:]
            
            # 写回文件
            print("写回文件...")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print("✅ 修复完成")
            return True
        else:
            print("❌ 函数定义位置异常")
            return False
    else:
        print("❌ 未发现预期的结构问题")
        return False

if __name__ == "__main__":
    success = fix_create_training_script_method()
    if success:
        print("\n✅ 方法结构修复成功")
    else:
        print("\n❌ 方法结构修复失败")