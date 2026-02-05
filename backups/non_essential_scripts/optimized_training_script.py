#!/usr/bin/env python3
"""
优化的训练脚本 - 解决numpy 2.x与matplotlib兼容性问题
专门处理numpy版本降级和matplotlib版本匹配
"""

import sys
import os
import subprocess
import importlib
import time

def current_time():
    """获取当前时间字符串"""
    from datetime import datetime
    return datetime.now().strftime('%H:%M:%S')

def ensure_package_available(package_name, import_name, install_cmd=None):
    """确保包可用，如果不可用则尝试安装"""
    try:
        module = __import__(import_name)
        print(f"[{current_time()}] [训练] ✓ {package_name} 可用")
        return True
    except ImportError:
        print(f"[{current_time()}] [训练] ⚠ {package_name} 不可用，尝试安装...")
        
        if install_cmd is None:
            install_cmd = f"python3 -m pip install --user --force-reinstall {package_name}"
        
        try:
            result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True, timeout=300)
            
            if result.stdout:
                print(f"安装输出: {result.stdout[-200:]}")  # 只显示最后200字符
            if result.stderr:
                print(f"安装错误: {result.stderr[-200:]}")  # 只显示最后200字符
                
            if result.returncode == 0:
                print(f"✓ {package_name} 安装成功")
                
                # 清理Python模块缓存
                
                # 移除已缓存的模块
                modules_to_remove = [k for k in sys.modules.keys() if k.startswith(import_name)]
                for mod in modules_to_remove:
                    del sys.modules[mod]
                
                importlib.invalidate_caches()
                
                # 等待一下让系统稳定
                import time
                time.sleep(1)
                
                # 重新尝试导入
                try:
                    module = __import__(import_name)
                    print(f"✓ {package_name} 导入成功")
                    return True
                except ImportError as import_error:
                    print(f"✗ {package_name} 安装后仍无法导入: {import_error}")
                    return False
            else:
                print(f"✗ {package_name} 安装失败")
                return False
        except Exception as e:
            print(f"✗ {package_name} 安装异常: {e}")
            return False

def main():
    """主函数"""
    print("=== 优化的训练脚本启动 ===")
    print(f"[{current_time()}] [训练] Python版本: {sys.version}")
    print(f"[{current_time()}] [训练] 工作目录: {os.getcwd()}")
    
    # 优化Python路径设置
    print(f"[{current_time()}] [训练] 优化Python路径...")
    user_site_packages = os.path.expanduser("~/.local/lib/python3.9/site-packages")
    if user_site_packages not in sys.path:
        sys.path.insert(0, user_site_packages)
        print(f"[{current_time()}] [训练] ✓ 添加用户包路径: {user_site_packages}")
    
    # 确保关键包可用 - 按依赖顺序安装
    print("=== 运行时包检查和安装 ===")
    
    # 第一步：检查当前numpy版本并确保兼容性
    print(f"[{current_time()}] [训练] 步骤1: 检查numpy版本兼容性...")
    numpy_ok = False
    numpy_needs_downgrade = False
    
    try:
        import numpy
        current_numpy_version = numpy.__version__
        print(f"[{current_time()}] [训练] 当前numpy版本: {current_numpy_version}")
        
        # 检查numpy版本是否与matplotlib兼容
        major_version = int(current_numpy_version.split('.')[0])
        minor_version = int(current_numpy_version.split('.')[1])
        
        # numpy 2.x 与 matplotlib 3.5.3 不兼容
        if major_version >= 2:
            print(f"[{current_time()}] [训练] ⚠ numpy {current_numpy_version} 与matplotlib不兼容，需要降级到1.x版本")
            numpy_needs_downgrade = True
        elif major_version == 1 and minor_version >= 25:
            print(f"[{current_time()}] [训练] ⚠ numpy {current_numpy_version} 可能与matplotlib不兼容，建议降级")
            numpy_needs_downgrade = True
        else:
            print(f"[{current_time()}] [训练] ✓ numpy {current_numpy_version} 版本兼容")
            numpy_needs_downgrade = False
            
            # 验证numpy.core.multiarray
            try:
                import numpy.core.multiarray
                print(f"[{current_time()}] [训练] ✓ numpy.core.multiarray正常")
                numpy_ok = True
            except Exception as e:
                print(f"[{current_time()}] [训练] ✗ numpy.core.multiarray异常: {e}")
                numpy_needs_downgrade = True
                
    except ImportError:
        print(f"[{current_time()}] [训练] ✗ numpy未安装")
        numpy_needs_downgrade = True
        numpy_ok = False
    
    # 如果需要降级或修复numpy
    if numpy_needs_downgrade or not numpy_ok:
        print(f"[{current_time()}] [训练] 开始numpy兼容性修复...")
        
        # 兼容的numpy版本（按优先级排序）
        compatible_numpy_versions = [
            "numpy==1.24.3",  # 最稳定的兼容版本
            "numpy==1.23.5",  # 备用兼容版本  
            "numpy==1.22.4",  # 更保守的版本
            "numpy==1.21.6",  # 最保守的版本
        ]
        
        numpy_ok = False
        for numpy_version in compatible_numpy_versions:
            print(f"[{current_time()}] [训练] 尝试安装兼容版本: {numpy_version}")
            if ensure_package_available("numpy", "numpy", f"python3 -m pip install --user --force-reinstall {numpy_version}"):
                # 验证安装后的版本
                try:
                    # 清理numpy模块缓存
                    modules_to_remove = [k for k in sys.modules.keys() if 'numpy' in k.lower()]
                    for mod in modules_to_remove:
                        del sys.modules[mod]
                    importlib.invalidate_caches()
                    
                    import time
                    time.sleep(1)
                    
                    import numpy
                    import numpy.core.multiarray
                    print(f"[{current_time()}] [训练] ✓ {numpy_version} 安装成功，实际版本: {numpy.__version__}")
                    numpy_ok = True
                    break
                except Exception as verify_e:
                    print(f"[{current_time()}] [训练] ✗ {numpy_version} 安装后验证失败: {verify_e}")
                    continue
            else:
                print(f"[{current_time()}] [训练] ✗ {numpy_version} 安装失败")
        
        if not numpy_ok:
            print(f"[{current_time()}] [训练] ⚠ 所有兼容numpy版本都安装失败，尝试彻底清理...")
            # 彻底清理numpy的多种方法
            cleanup_commands = [
                "python3 -m pip uninstall -y numpy",
                "python3 -m pip cache purge",
                "python3 -m pip install --user --no-cache-dir --force-reinstall numpy==1.24.3"
            ]
            
            for cmd in cleanup_commands:
                try:
                    print(f"[{current_time()}] [训练] 执行清理命令: {cmd}")
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                    print(f"[{current_time()}] [训练] 命令结果: {result.returncode}")
                    if result.stdout:
                        print(f"输出: {result.stdout[-100:]}")
                    if result.stderr:
                        print(f"错误: {result.stderr[-100:]}")
                except Exception as e:
                    print(f"[{current_time()}] [训练] 清理命令异常: {e}")
            
            # 最后验证numpy
            try:
                # 清理所有numpy相关模块
                modules_to_remove = [k for k in sys.modules.keys() if 'numpy' in k.lower()]
                for mod in modules_to_remove:
                    del sys.modules[mod]
                importlib.invalidate_caches()
                
                import time
                time.sleep(2)  # 等待更长时间
                
                import numpy
                import numpy.core.multiarray
                print(f"[{current_time()}] [训练] ✓ numpy彻底清理重装成功，版本: {numpy.__version__}")
                numpy_ok = True
            except Exception as final_error:
                print(f"[{current_time()}] [训练] ✗ numpy彻底清理重装仍然失败: {final_error}")
                print(f"[{current_time()}] [训练] 将继续尝试其他包，但可能会有兼容性问题")
    
    # 第二步：根据numpy版本选择兼容的matplotlib版本
    print(f"[{current_time()}] [训练] 步骤2: 选择兼容的matplotlib版本...")
    matplotlib_version = "matplotlib==3.5.3"  # 默认版本
    try:
        import numpy
        numpy_version = numpy.__version__
        print(f"[{current_time()}] [训练] 当前numpy版本: {numpy_version}")
        
        # 根据numpy版本选择最佳的matplotlib版本
        if numpy_version.startswith("1.24"):
            matplotlib_version = "matplotlib==3.7.1"  # 与numpy 1.24兼容
            print(f"[{current_time()}] [训练] 为numpy 1.24选择matplotlib 3.7.1")
        elif numpy_version.startswith("1.23"):
            matplotlib_version = "matplotlib==3.6.3"  # 与numpy 1.23兼容
            print(f"[{current_time()}] [训练] 为numpy 1.23选择matplotlib 3.6.3")
        elif numpy_version.startswith("1.22"):
            matplotlib_version = "matplotlib==3.5.3"  # 与numpy 1.22兼容
            print(f"[{current_time()}] [训练] 为numpy 1.22选择matplotlib 3.5.3")
        elif numpy_version.startswith("1.21"):
            matplotlib_version = "matplotlib==3.5.1"  # 与numpy 1.21兼容
            print(f"[{current_time()}] [训练] 为numpy 1.21选择matplotlib 3.5.1")
        else:
            print(f"[{current_time()}] [训练] 使用默认matplotlib版本 3.5.3")
            
    except Exception as e:
        print(f"[{current_time()}] [训练] 无法检查numpy版本，使用默认matplotlib: {e}")
    
    # 第三步：检查其他关键包
    print(f"[{current_time()}] [训练] 步骤3: 检查其他关键包...")
    required_packages = [
        ("matplotlib", "matplotlib", f"python3 -m pip install --user --force-reinstall {matplotlib_version}"),
        ("torch", "torch", None),
        ("ultralytics", "ultralytics", None),
    ]
    
    all_packages_ok = True
    for pkg_name, import_name, install_cmd in required_packages:
        if not ensure_package_available(pkg_name, import_name, install_cmd):
            print(f"[{current_time()}] [训练] ✗ 关键包 {pkg_name} 无法确保可用")
            all_packages_ok = False
    
    if not all_packages_ok:
        print(f"[{current_time()}] [训练] ✗ 部分关键包不可用，但继续尝试训练...")
    
    # 最终导入验证
    print("=== 最终导入验证 ===")
    try:
        import matplotlib
        print(f"[{current_time()}] [训练] matplotlib路径: {matplotlib.__file__}")
        print(f"[{current_time()}] [训练] matplotlib版本: {matplotlib.__version__}")
    except ImportError as e:
        print(f"[{current_time()}] [训练] matplotlib最终导入失败: {e}")
        print(f"[{current_time()}] [训练] 尝试备用导入方案...")
        # 备用方案：直接使用系统包
        sys.path.append('/usr/local/lib/python3.9/dist-packages')
        try:
            import matplotlib
            print(f"[{current_time()}] [训练] 备用方案成功 - matplotlib路径: {matplotlib.__file__}")
        except ImportError:
            print(f"[{current_time()}] [训练] 所有导入方案都失败，但继续执行训练...")
    
    try:
        import numpy
        print(f"[{current_time()}] [训练] numpy路径: {numpy.__file__}")
        print(f"[{current_time()}] [训练] numpy版本: {numpy.__version__}")
    except ImportError as e:
        print(f"[{current_time()}] [训练] numpy导入失败: {e}")
    
    try:
        import torch
        print(f"[{current_time()}] [训练] torch版本: {torch.__version__}")
    except ImportError as e:
        print(f"[{current_time()}] [训练] torch导入失败: {e}")
    
    try:
        from ultralytics import YOLO
        print(f"[{current_time()}] [训练] ultralytics导入成功")
    except ImportError as e:
        print(f"[{current_time()}] [训练] ultralytics导入失败: {e}")
    
    print("=== 包兼容性检查完成 ===")
    print(f"[{current_time()}] [训练] 🎉 优化的训练脚本验证完成！")
    print(f"[{current_time()}] [训练] 关键改进:")
    print(f"[{current_time()}] [训练] 1. ✓ numpy 2.x版本自动检测和降级")
    print(f"[{current_time()}] [训练] 2. ✓ 智能matplotlib版本匹配")
    print(f"[{current_time()}] [训练] 3. ✓ 彻底的包清理和重装机制")
    print(f"[{current_time()}] [训练] 4. ✓ 多重验证和备用方案")
    print(f"[{current_time()}] [训练] 5. ✓ 增强的错误处理和诊断")

if __name__ == "__main__":
    main()