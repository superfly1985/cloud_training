#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实用的numpy兼容性修复方案
通过安装兼容的matplotlib版本来解决numpy 2.x兼容性问题
"""

import os
import sys
import subprocess
import importlib
import time
from datetime import datetime

def current_time():
    return datetime.now().strftime("%H:%M:%S")

def run_command(cmd, timeout=300):
    """运行命令并返回结果"""
    try:
        print(f"[{current_time()}] 执行命令: {cmd}")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        print(f"[{current_time()}] 返回码: {result.returncode}")
        if result.stdout:
            print(f"输出: {result.stdout.strip()}")
        if result.stderr and result.returncode != 0:
            print(f"错误: {result.stderr.strip()}")
        return result
    except Exception as e:
        print(f"[{current_time()}] 命令执行异常: {e}")
        return None

def clear_matplotlib_modules():
    """清理matplotlib相关模块"""
    print(f"[{current_time()}] 清理matplotlib模块缓存...")
    
    modules_to_remove = [k for k in sys.modules.keys() if 'matplotlib' in k.lower()]
    for mod in modules_to_remove:
        try:
            del sys.modules[mod]
            print(f"[{current_time()}] 移除模块: {mod}")
        except:
            pass
    
    importlib.invalidate_caches()
    print(f"[{current_time()}] matplotlib模块缓存已清理")

def get_numpy_version():
    """获取当前numpy版本"""
    try:
        import numpy
        return numpy.__version__
    except ImportError:
        return None

def install_compatible_matplotlib():
    """安装与numpy 2.x兼容的matplotlib版本"""
    print(f"[{current_time()}] === 安装兼容的matplotlib版本 ===")
    
    # 检查当前numpy版本
    numpy_version = get_numpy_version()
    if not numpy_version:
        print(f"[{current_time()}] ✗ numpy未安装")
        return False
    
    print(f"[{current_time()}] 当前numpy版本: {numpy_version}")
    
    # 根据numpy版本选择兼容的matplotlib版本
    if numpy_version.startswith('2.'):
        # numpy 2.x需要较新的matplotlib版本
        compatible_matplotlib_versions = [
            "matplotlib>=3.8.0",
            "matplotlib==3.8.4",
            "matplotlib==3.9.0",
            "matplotlib>=3.7.0"
        ]
        print(f"[{current_time()}] 检测到numpy 2.x，选择兼容的matplotlib版本...")
    else:
        # numpy 1.x可以使用较旧的matplotlib版本
        compatible_matplotlib_versions = [
            "matplotlib==3.5.3",
            "matplotlib==3.6.3",
            "matplotlib==3.7.1"
        ]
        print(f"[{current_time()}] 检测到numpy 1.x，选择标准matplotlib版本...")
    
    # 尝试安装兼容的matplotlib版本
    for version in compatible_matplotlib_versions:
        print(f"[{current_time()}] 尝试安装: {version}")
        
        # 先卸载现有的matplotlib
        uninstall_cmd = "python -m pip uninstall -y matplotlib"
        run_command(uninstall_cmd)
        
        # 清理模块缓存
        clear_matplotlib_modules()
        
        # 安装新版本
        install_cmd = f"python -m pip install --user --no-cache-dir {version}"
        result = run_command(install_cmd)
        
        if result and result.returncode == 0:
            # 验证安装
            clear_matplotlib_modules()
            time.sleep(2)
            
            try:
                import matplotlib
                import matplotlib.pyplot as plt
                installed_version = matplotlib.__version__
                print(f"[{current_time()}] ✓ {version} 安装成功，实际版本: {installed_version}")
                
                # 测试基本功能
                fig, ax = plt.subplots()
                ax.plot([1, 2, 3], [1, 4, 2])
                print(f"[{current_time()}] ✓ matplotlib基本功能测试通过")
                
                return True
                
            except Exception as e:
                print(f"[{current_time()}] ✗ {version} 验证失败: {e}")
                clear_matplotlib_modules()
                continue
        else:
            print(f"[{current_time()}] ✗ {version} 安装失败")
    
    print(f"[{current_time()}] ✗ 所有matplotlib版本都安装失败")
    return False

def test_complete_compatibility():
    """测试完整的包兼容性"""
    print(f"[{current_time()}] === 测试完整包兼容性 ===")
    
    try:
        # 测试numpy
        import numpy
        print(f"[{current_time()}] ✓ numpy {numpy.__version__} 导入成功")
        
        # 测试numpy.core.multiarray
        import numpy.core.multiarray
        print(f"[{current_time()}] ✓ numpy.core.multiarray 导入成功")
        
        # 测试matplotlib
        import matplotlib
        print(f"[{current_time()}] ✓ matplotlib {matplotlib.__version__} 导入成功")
        
        # 测试matplotlib.pyplot
        import matplotlib.pyplot as plt
        print(f"[{current_time()}] ✓ matplotlib.pyplot 导入成功")
        
        # 测试torch
        try:
            import torch
            print(f"[{current_time()}] ✓ torch {torch.__version__} 导入成功")
        except ImportError:
            print(f"[{current_time()}] ⚠ torch 未安装")
        
        # 测试ultralytics
        try:
            import ultralytics
            print(f"[{current_time()}] ✓ ultralytics 导入成功")
        except ImportError:
            print(f"[{current_time()}] ⚠ ultralytics 未安装")
        
        # 测试基本绘图功能
        fig, ax = plt.subplots(figsize=(6, 4))
        x = numpy.linspace(0, 10, 100)
        y = numpy.sin(x)
        ax.plot(x, y, label='sin(x)')
        ax.legend()
        ax.set_title('Numpy + Matplotlib 兼容性测试')
        print(f"[{current_time()}] ✓ numpy + matplotlib 综合功能测试通过")
        
        return True
        
    except Exception as e:
        print(f"[{current_time()}] ✗ 包兼容性测试失败: {e}")
        return False

def main():
    print(f"[{current_time()}] === 实用numpy兼容性修复方案启动 ===")
    print(f"[{current_time()}] Python版本: {sys.version}")
    print(f"[{current_time()}] 工作目录: {os.getcwd()}")
    
    # 步骤1: 安装兼容的matplotlib
    matplotlib_success = install_compatible_matplotlib()
    
    if matplotlib_success:
        print(f"[{current_time()}] ✓ matplotlib兼容性修复成功")
        
        # 步骤2: 测试完整兼容性
        compatibility_success = test_complete_compatibility()
        
        if compatibility_success:
            print(f"[{current_time()}] 🎉 所有包兼容性测试通过！")
            print(f"[{current_time()}] 解决方案总结:")
            print(f"[{current_time()}] 1. ✓ 保持numpy 2.x版本不变")
            print(f"[{current_time()}] 2. ✓ 安装与numpy 2.x兼容的matplotlib版本")
            print(f"[{current_time()}] 3. ✓ 验证所有关键包的兼容性")
            print(f"[{current_time()}] 4. ✓ 测试基本功能正常工作")
        else:
            print(f"[{current_time()}] ⚠ matplotlib安装成功，但兼容性测试失败")
    else:
        print(f"[{current_time()}] ✗ matplotlib兼容性修复失败")
    
    print(f"[{current_time()}] === 实用numpy兼容性修复方案完成 ===")

if __name__ == "__main__":
    main()