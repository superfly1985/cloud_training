#!/usr/bin/env python3
"""
检查matplotlib安装位置和可访问性
"""

import sys
import os
import subprocess

def check_matplotlib_installation():
    """检查matplotlib的安装情况"""
    print("=== matplotlib安装检查 ===")
    
    # 1. 检查当前Python路径
    print(f"当前Python路径: {sys.executable}")
    print(f"Python版本: {sys.version}")
    print()
    
    # 2. 检查sys.path
    print("当前sys.path:")
    for i, path in enumerate(sys.path):
        print(f"  {i}: {path}")
    print()
    
    # 3. 尝试导入matplotlib
    try:
        import matplotlib
        print(f"✓ matplotlib导入成功")
        print(f"  版本: {matplotlib.__version__}")
        print(f"  安装路径: {matplotlib.__file__}")
        print(f"  包目录: {os.path.dirname(matplotlib.__file__)}")
    except ImportError as e:
        print(f"✗ matplotlib导入失败: {e}")
    print()
    
    # 4. 使用pip检查matplotlib安装
    try:
        result = subprocess.run([sys.executable, '-m', 'pip', 'show', 'matplotlib'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("✓ pip show matplotlib:")
            print(result.stdout)
        else:
            print("✗ pip show matplotlib失败:")
            print(result.stderr)
    except Exception as e:
        print(f"✗ pip检查失败: {e}")
    print()
    
    # 5. 检查可能的matplotlib安装位置
    possible_paths = [
        '/root/.local/lib/python3.9/site-packages/matplotlib',
        '/usr/local/lib/python3.9/dist-packages/matplotlib',
        '/usr/lib/python3/dist-packages/matplotlib',
        '/usr/lib/python3.9/site-packages/matplotlib'
    ]
    
    print("检查可能的matplotlib安装位置:")
    for path in possible_paths:
        if os.path.exists(path):
            print(f"  ✓ 存在: {path}")
            # 检查__init__.py文件
            init_file = os.path.join(path, '__init__.py')
            if os.path.exists(init_file):
                print(f"    ✓ __init__.py存在")
            else:
                print(f"    ✗ __init__.py不存在")
        else:
            print(f"  ✗ 不存在: {path}")
    print()
    
    # 6. 检查环境变量
    print("相关环境变量:")
    env_vars = ['PYTHONPATH', 'PYTHONNOUSERSITE', 'PYTHONDONTWRITEBYTECODE']
    for var in env_vars:
        value = os.environ.get(var, '未设置')
        print(f"  {var}: {value}")
    print()
    
    # 7. 检查用户站点包目录
    try:
        import site
        print("用户站点包信息:")
        print(f"  用户站点包目录: {site.getusersitepackages()}")
        print(f"  用户站点包启用: {site.ENABLE_USER_SITE}")
        print(f"  用户基础目录: {site.getuserbase()}")
    except Exception as e:
        print(f"✗ 用户站点包检查失败: {e}")

if __name__ == "__main__":
    check_matplotlib_installation()