#!/usr/bin/env python3
"""
批量修复双花括号格式化错误的脚本
将 {{variable}} 替换为 {variable}
"""

import re
import os

def fix_double_braces_in_file(file_path):
    """修复文件中的双花括号错误"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用正则表达式查找并替换双花括号
        # 匹配 {{variable}} 模式，但不匹配 {{{variable}}} 这种三重花括号
        pattern = r'\{\{([^{}]+)\}\}'
        
        # 计算替换次数
        matches = re.findall(pattern, content)
        if not matches:
            print(f"✓ {file_path}: 没有发现双花括号错误")
            return 0
        
        # 执行替换
        fixed_content = re.sub(pattern, r'{\1}', content)
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        
        print(f"✓ {file_path}: 修复了 {len(matches)} 个双花括号错误")
        for i, match in enumerate(matches[:5], 1):  # 只显示前5个
            print(f"   {i}. {{{{{{match}}}}}} -> {{{match}}}")
        if len(matches) > 5:
            print(f"   ... 还有 {len(matches) - 5} 个")
        
        return len(matches)
        
    except Exception as e:
        print(f"✗ 修复 {file_path} 时出错: {e}")
        return 0

def main():
    """主函数"""
    print("开始批量修复双花括号格式化错误...")
    print("=" * 50)
    
    # 要修复的文件列表
    files_to_fix = [
        "cloud_training_gui.py",
        "start_cloud_gpu_training_final.py"
    ]
    
    total_fixes = 0
    
    for file_name in files_to_fix:
        file_path = os.path.join(os.path.dirname(__file__), file_name)
        if os.path.exists(file_path):
            fixes = fix_double_braces_in_file(file_path)
            total_fixes += fixes
        else:
            print(f"⚠ 文件不存在: {file_path}")
    
    print("=" * 50)
    print(f"修复完成！总共修复了 {total_fixes} 个双花括号错误")
    
    if total_fixes > 0:
        print("\n建议现在测试修复后的功能:")
        print("1. 尝试生成训练脚本")
        print("2. 检查所有字符串格式化是否正常")

if __name__ == "__main__":
    main()