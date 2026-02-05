#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
强制numpy降级脚本
解决numpy 2.x与matplotlib兼容性问题
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
        if result.stderr:
            print(f"错误: {result.stderr.strip()}")
        return result
    except Exception as e:
        print(f"[{current_time()}] 命令执行异常: {e}")
        return None

def clear_numpy_modules():
    """清理所有numpy相关模块"""
    print(f"[{current_time()}] 清理numpy模块缓存...")
    
    # 清理sys.modules中的numpy相关模块
    modules_to_remove = [k for k in sys.modules.keys() if 'numpy' in k.lower()]
    for mod in modules_to_remove:
        try:
            del sys.modules[mod]
            print(f"[{current_time()}] 移除模块: {mod}")
        except:
            pass
    
    # 刷新importlib缓存
    importlib.invalidate_caches()
    print(f"[{current_time()}] 模块缓存已清理")

def force_numpy_downgrade():
    """强制numpy降级"""
    print(f"[{current_time()}] === 开始强制numpy降级 ===")
    
    # 步骤1: 检查当前numpy版本
    try:
        import numpy
        current_version = numpy.__version__
        print(f"[{current_time()}] 当前numpy版本: {current_version}")
        
        if current_version.startswith('1.'):
            print(f"[{current_time()}] ✓ numpy已经是1.x版本，无需降级")
            return True
    except ImportError:
        print(f"[{current_time()}] numpy未安装")
        current_version = None
    
    # 步骤2: 彻底卸载numpy
    print(f"[{current_time()}] 步骤1: 彻底卸载numpy...")
    
    uninstall_commands = [
        "python -m pip uninstall -y numpy",
        "python -m pip uninstall -y numpy-base",
        "python -m pip cache purge",
        "python -m pip list | findstr numpy"  # 检查是否还有numpy残留
    ]
    
    for cmd in uninstall_commands:
        run_command(cmd)
    
    # 清理模块缓存
    clear_numpy_modules()
    
    # 步骤3: 安装兼容的numpy版本
    print(f"[{current_time()}] 步骤2: 安装兼容的numpy版本...")
    
    # 尝试多个兼容版本
    compatible_versions = [
        "numpy==1.24.3",
        "numpy==1.23.5", 
        "numpy==1.22.4",
        "numpy==1.21.6"
    ]
    
    for version in compatible_versions:
        print(f"[{current_time()}] 尝试安装: {version}")
        
        # 使用强制安装参数
        install_cmd = f"python -m pip install --user --no-cache-dir --force-reinstall --no-deps {version}"
        result = run_command(install_cmd)
        
        if result and result.returncode == 0:
            # 清理模块缓存
            clear_numpy_modules()
            time.sleep(2)
            
            # 验证安装
            try:
                import numpy
                import numpy.core.multiarray
                installed_version = numpy.__version__
                print(f"[{current_time()}] ✓ {version} 安装成功，实际版本: {installed_version}")
                
                if installed_version.startswith('1.'):
                    print(f"[{current_time()}] ✓ numpy成功降级到1.x版本")
                    return True
                else:
                    print(f"[{current_time()}] ✗ 安装的版本仍然是 {installed_version}")
                    clear_numpy_modules()
                    continue
                    
            except Exception as e:
                print(f"[{current_time()}] ✗ {version} 验证失败: {e}")
                clear_numpy_modules()
                continue
        else:
            print(f"[{current_time()}] ✗ {version} 安装失败")
    
    # 步骤4: 如果所有版本都失败，尝试最后的方法
    print(f"[{current_time()}] 步骤3: 尝试最后的强制方法...")
    
    # 完全清理pip缓存和用户安装
    cleanup_commands = [
        "python -m pip cache purge",
        "python -m pip uninstall -y numpy numpy-base",
        "python -m pip install --user --no-cache-dir --force-reinstall --upgrade pip",
    ]
    
    for cmd in cleanup_commands:
        run_command(cmd)
    
    # 最后尝试安装numpy 1.24.3
    final_cmd = "python -m pip install --user --no-cache-dir --force-reinstall numpy==1.24.3"
    result = run_command(final_cmd)
    
    if result and result.returncode == 0:
        clear_numpy_modules()
        time.sleep(3)
        
        try:
            import numpy
            import numpy.core.multiarray
            final_version = numpy.__version__
            print(f"[{current_time()}] 最终numpy版本: {final_version}")
            
            if final_version.startswith('1.'):
                print(f"[{current_time()}] 🎉 numpy强制降级成功！")
                return True
            else:
                print(f"[{current_time()}] ⚠ numpy仍然是 {final_version}，可能需要手动处理")
                return False
                
        except Exception as e:
            print(f"[{current_time()}] ✗ 最终验证失败: {e}")
            return False
    
    print(f"[{current_time()}] ✗ 所有降级尝试都失败了")
    return False

def test_matplotlib_compatibility():
    """测试matplotlib兼容性"""
    print(f"[{current_time()}] === 测试matplotlib兼容性 ===")
    
    try:
        import numpy
        print(f"[{current_time()}] numpy版本: {numpy.__version__}")
        
        import matplotlib
        print(f"[{current_time()}] matplotlib版本: {matplotlib.__version__}")
        
        import matplotlib.pyplot as plt
        print(f"[{current_time()}] ✓ matplotlib.pyplot导入成功")
        
        # 测试基本绘图功能
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 2])
        print(f"[{current_time()}] ✓ matplotlib基本绘图功能正常")
        
        return True
        
    except Exception as e:
        print(f"[{current_time()}] ✗ matplotlib兼容性测试失败: {e}")
        return False

def main():
    print(f"[{current_time()}] === 强制numpy降级脚本启动 ===")
    print(f"[{current_time()}] Python版本: {sys.version}")
    print(f"[{current_time()}] 工作目录: {os.getcwd()}")
    
    # 执行强制降级
    success = force_numpy_downgrade()
    
    if success:
        # 测试matplotlib兼容性
        matplotlib_ok = test_matplotlib_compatibility()
        
        if matplotlib_ok:
            print(f"[{current_time()}] 🎉 numpy降级和matplotlib兼容性测试都成功！")
        else:
            print(f"[{current_time()}] ⚠ numpy降级成功，但matplotlib兼容性测试失败")
    else:
        print(f"[{current_time()}] ✗ numpy降级失败")
    
    print(f"[{current_time()}] === 强制numpy降级脚本完成 ===")

if __name__ == "__main__":
    main()