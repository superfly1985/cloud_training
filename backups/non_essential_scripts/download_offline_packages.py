#!/usr/bin/env python3
"""
离线包下载工具
自动下载所有训练所需的Python包到本地Environment_package目录
支持不同Python版本的兼容性包下载
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def get_package_dir():
    """获取包存储目录"""
    script_dir = Path(__file__).parent
    package_dir = script_dir / "Environment_package"
    package_dir.mkdir(exist_ok=True)
    return package_dir

def run_pip_download(package_spec, target_dir, python_version=None, extra_args=None):
    """运行pip download命令"""
    cmd = [sys.executable, "-m", "pip", "download", "--dest", str(target_dir)]
    
    if extra_args:
        cmd.extend(extra_args)
    
    cmd.append(package_spec)
    
    print(f"执行命令: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"✓ 成功下载: {package_spec}")
            return True
        else:
            print(f"✗ 下载失败: {package_spec}")
            print(f"错误信息: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ 下载超时: {package_spec}")
        return False
    except Exception as e:
        print(f"✗ 下载异常: {package_spec}, 错误: {e}")
        return False

def download_pytorch_packages(package_dir):
    """下载PyTorch相关包"""
    print("\n=== 下载PyTorch相关包 ===")
    
    # PyTorch CPU版本 - 兼容Python 3.8
    pytorch_packages = [
        "torch==2.0.1",
        "torchvision==0.15.2", 
        "torchaudio==2.0.2"
    ]
    
    # PyTorch官方CPU源
    pytorch_args = ["--index-url", "https://download.pytorch.org/whl/cpu"]
    
    success_count = 0
    for package in pytorch_packages:
        if run_pip_download(package, package_dir, extra_args=pytorch_args):
            success_count += 1
    
    print(f"PyTorch包下载完成: {success_count}/{len(pytorch_packages)}")
    return success_count == len(pytorch_packages)

def download_ultralytics_packages(package_dir):
    """下载Ultralytics相关包"""
    print("\n=== 下载Ultralytics相关包 ===")
    
    # Ultralytics及其依赖
    ultralytics_packages = [
        "ultralytics==8.0.196",  # Python 3.8兼容版本
        "ultralytics",           # 最新版本
    ]
    
    success_count = 0
    for package in ultralytics_packages:
        if run_pip_download(package, package_dir):
            success_count += 1
    
    print(f"Ultralytics包下载完成: {success_count}/{len(ultralytics_packages)}")
    return success_count > 0

def download_common_dependencies(package_dir):
    """下载常用依赖包"""
    print("\n=== 下载常用依赖包 ===")
    
    # 常用依赖包
    common_packages = [
        "networkx==2.8.8",      # Python 3.8兼容版本
        "networkx",             # 最新版本
        "numpy",
        "opencv-python",
        "pillow",
        "matplotlib",
        "scipy",
        "pandas",
        "requests",
        "tqdm",
        "pyyaml",
        "seaborn",
        "psutil",
        "thop",
        "filelock",
        "jinja2", 
        "sympy",
        "typing-extensions",
        "setuptools",
        "wheel",
        "pip"
    ]
    
    success_count = 0
    for package in common_packages:
        if run_pip_download(package, package_dir):
            success_count += 1
    
    print(f"常用依赖包下载完成: {success_count}/{len(common_packages)}")
    return success_count > 0

def download_ml_packages(package_dir):
    """下载机器学习相关包"""
    print("\n=== 下载机器学习相关包 ===")
    
    ml_packages = [
        "scikit-learn",
        "scikit-image", 
        "albumentations",
        "imgaug",
        "tensorboard",
        "wandb",
        "comet-ml",
        "clearml",
        "roboflow"
    ]
    
    success_count = 0
    for package in ml_packages:
        if run_pip_download(package, package_dir):
            success_count += 1
    
    print(f"机器学习包下载完成: {success_count}/{len(ml_packages)}")
    return success_count > 0

def main():
    """主函数"""
    print("🚀 开始下载离线Python包...")
    print(f"Python版本: {sys.version}")
    print(f"操作系统: {platform.system()} {platform.release()}")
    
    package_dir = get_package_dir()
    print(f"包存储目录: {package_dir}")
    
    # 检查pip版本
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                              capture_output=True, text=True)
        print(f"pip版本: {result.stdout.strip()}")
    except Exception as e:
        print(f"无法获取pip版本: {e}")
    
    # 升级pip
    print("\n=== 升级pip ===")
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], 
                   capture_output=True)
    
    # 下载各类包
    results = []
    
    # 1. 下载PyTorch包
    results.append(("PyTorch", download_pytorch_packages(package_dir)))
    
    # 2. 下载Ultralytics包
    results.append(("Ultralytics", download_ultralytics_packages(package_dir)))
    
    # 3. 下载常用依赖
    results.append(("常用依赖", download_common_dependencies(package_dir)))
    
    # 4. 下载机器学习包
    results.append(("机器学习包", download_ml_packages(package_dir)))
    
    # 统计结果
    print("\n" + "="*50)
    print("📊 下载结果统计:")
    success_categories = 0
    for category, success in results:
        status = "✓ 成功" if success else "✗ 部分失败"
        print(f"  {category}: {status}")
        if success:
            success_categories += 1
    
    print(f"\n总体结果: {success_categories}/{len(results)} 个类别下载成功")
    
    # 列出下载的文件
    print(f"\n📦 已下载的包文件:")
    package_files = list(package_dir.glob("*.whl")) + list(package_dir.glob("*.tar.gz"))
    if package_files:
        for file in sorted(package_files):
            file_size = file.stat().st_size / (1024 * 1024)  # MB
            print(f"  {file.name} ({file_size:.1f} MB)")
        print(f"\n总计: {len(package_files)} 个包文件")
    else:
        print("  未找到下载的包文件")
    
    print("\n🎉 离线包下载完成!")
    return success_categories > 0

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断下载")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 下载过程出现异常: {e}")
        sys.exit(1)