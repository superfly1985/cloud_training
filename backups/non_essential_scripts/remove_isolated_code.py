#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
删除cloud_training_gui.py中的孤立代码
"""

def remove_isolated_code():
    """删除第2055行到第2400行的孤立代码"""
    file_path = 'd:\\OneDrive\\24.Visual AI\\training_scripts\\cloud_training_gui.py'
    
    print("正在读取文件...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    print(f"文件总行数: {len(lines)}")
    print(f"删除前第2055行内容: {lines[2054].strip()}")  # 第2055行（索引2054）
    print(f"删除前第2400行内容: {lines[2399].strip()}")  # 第2400行（索引2399）
    
    # 删除第2055行到第2400行（包含）
    # 索引是从0开始的，所以第2055行是索引2054，第2400行是索引2399
    start_index = 2054  # 第2055行
    end_index = 2400    # 第2401行（不包含）
    
    print(f"删除行范围: {start_index + 1} 到 {end_index}")
    
    # 保留第2055行之前和第2401行之后的内容
    new_lines = lines[:start_index] + lines[end_index:]
    
    print(f"删除后文件行数: {len(new_lines)}")
    print(f"删除后第{start_index + 1}行内容: {new_lines[start_index].strip()}")
    
    # 写回文件
    print("正在写回文件...")
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("✓ 孤立代码删除完成")

if __name__ == "__main__":
    remove_isolated_code()