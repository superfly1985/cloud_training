#!/usr/bin/env python3
"""
全面的服务器环境检查脚本
检查Python环境、已安装包、CUDA环境等
"""

import subprocess
import sys
import os
import json
from datetime import datetime

def run_command(cmd):
    """执行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timeout',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'returncode': -1
        }

def check_system_info():
    """检查系统基本信息"""
    print("=== 系统基本信息 ===")
    
    # 操作系统信息
    os_info = run_command("cat /etc/os-release")
    if os_info['success']:
        print("操作系统信息:")
        print(os_info['stdout'])
    
    # 内核版本
    kernel = run_command("uname -r")
    if kernel['success']:
        print(f"内核版本: {kernel['stdout']}")
    
    # 系统架构
    arch = run_command("uname -m")
    if arch['success']:
        print(f"系统架构: {arch['stdout']}")
    
    print()

def check_python_environment():
    """检查Python环境"""
    print("=== Python环境检查 ===")
    
    # 检查所有可用的Python版本
    python_versions = []
    for py_cmd in ['python', 'python3', 'python3.8', 'python3.9', 'python3.10', 'python3.11']:
        result = run_command(f"which {py_cmd}")
        if result['success']:
            version_result = run_command(f"{py_cmd} --version")
            if version_result['success']:
                python_versions.append({
                    'command': py_cmd,
                    'path': result['stdout'],
                    'version': version_result['stdout']
                })
    
    print("可用的Python版本:")
    for py in python_versions:
        print(f"  {py['command']}: {py['version']} ({py['path']})")
    
    # 检查默认Python
    default_python = run_command("python3 --version")
    if default_python['success']:
        print(f"默认Python3版本: {default_python['stdout']}")
    
    # 检查Python路径
    python_path = run_command("which python3")
    if python_path['success']:
        print(f"Python3路径: {python_path['stdout']}")
    
    # 检查Python模块路径
    sys_path = run_command('python3 -c "import sys; print(\'\\n\'.join(sys.path))"')
    if sys_path['success']:
        print("Python模块搜索路径:")
        for path in sys_path['stdout'].split('\n'):
            if path.strip():
                print(f"  {path}")
    
    print()

def check_pip_environment():
    """检查pip环境"""
    print("=== Pip环境检查 ===")
    
    # 检查所有可用的pip版本
    pip_commands = ['pip', 'pip3', 'python -m pip', 'python3 -m pip']
    
    for pip_cmd in pip_commands:
        print(f"检查 {pip_cmd}:")
        
        # 检查pip是否存在
        if 'python' in pip_cmd:
            result = run_command(f"{pip_cmd} --version")
        else:
            which_result = run_command(f"which {pip_cmd}")
            if which_result['success']:
                result = run_command(f"{pip_cmd} --version")
            else:
                result = {'success': False, 'stderr': 'Command not found'}
        
        if result['success']:
            print(f"  ✓ {result['stdout']}")
            
            # 检查pip配置
            config_result = run_command(f"{pip_cmd} config list")
            if config_result['success'] and config_result['stdout']:
                print(f"  配置: {config_result['stdout']}")
        else:
            print(f"  ✗ 不可用: {result['stderr']}")
    
    print()

def check_installed_packages():
    """检查已安装的Python包"""
    print("=== 已安装的Python包 ===")
    
    # 使用pip list检查
    pip_list = run_command("python3 -m pip list")
    if pip_list['success']:
        print("通过pip list检查到的包:")
        lines = pip_list['stdout'].split('\n')
        for line in lines[:20]:  # 只显示前20个
            if line.strip():
                print(f"  {line}")
        if len(lines) > 20:
            print(f"  ... 还有 {len(lines) - 20} 个包")
    
    # 检查关键包
    key_packages = ['torch', 'ultralytics', 'numpy', 'opencv-python', 'pillow', 'matplotlib', 'yaml']
    print("\n关键包检查:")
    
    for package in key_packages:
        # 尝试导入包
        import_result = run_command(f'python3 -c "import {package.replace("-", "_") if package == "opencv-python" else package}; print(\\"OK\\")"')
        
        if import_result['success']:
            # 尝试获取版本
            if package == 'opencv-python':
                version_cmd = 'python3 -c "import cv2; print(cv2.__version__)"'
            elif package == 'yaml':
                version_cmd = 'python3 -c "import yaml; print(\\"PyYAML installed\\")"'
            else:
                version_cmd = f'python3 -c "import {package}; print({package}.__version__)"'
            
            version_result = run_command(version_cmd)
            if version_result['success']:
                print(f"  ✓ {package}: {version_result['stdout']}")
            else:
                print(f"  ✓ {package}: 已安装 (无法获取版本)")
        else:
            print(f"  ✗ {package}: 未安装")
    
    print()

def check_cuda_environment():
    """检查CUDA环境"""
    print("=== CUDA环境检查 ===")
    
    # 检查nvidia-smi
    nvidia_smi = run_command("nvidia-smi")
    if nvidia_smi['success']:
        print("NVIDIA GPU信息:")
        print(nvidia_smi['stdout'])
    else:
        print("✗ nvidia-smi不可用")
    
    # 检查CUDA版本
    cuda_version = run_command("nvcc --version")
    if cuda_version['success']:
        print(f"CUDA编译器版本:")
        print(cuda_version['stdout'])
    else:
        print("✗ nvcc不可用")
    
    # 检查CUDA路径
    cuda_home = run_command("echo $CUDA_HOME")
    if cuda_home['success'] and cuda_home['stdout']:
        print(f"CUDA_HOME: {cuda_home['stdout']}")
    
    # 检查PyTorch CUDA支持
    torch_cuda = run_command('python3 -c "import torch; print(f\\"PyTorch CUDA available: {torch.cuda.is_available()}\\"); print(f\\"CUDA version: {torch.version.cuda}\\"); print(f\\"Device count: {torch.cuda.device_count()}\\")"')
    if torch_cuda['success']:
        print("PyTorch CUDA信息:")
        print(torch_cuda['stdout'])
    
    print()

def check_conda_environment():
    """检查Conda环境"""
    print("=== Conda环境检查 ===")
    
    # 检查conda
    conda_version = run_command("conda --version")
    if conda_version['success']:
        print(f"Conda版本: {conda_version['stdout']}")
        
        # 检查conda环境列表
        conda_envs = run_command("conda env list")
        if conda_envs['success']:
            print("Conda环境列表:")
            print(conda_envs['stdout'])
        
        # 检查当前环境
        conda_info = run_command("conda info")
        if conda_info['success']:
            print("Conda信息:")
            print(conda_info['stdout'])
    else:
        print("✗ Conda不可用")
    
    print()

def check_jupyter_environment():
    """检查Jupyter环境"""
    print("=== Jupyter环境检查 ===")
    
    # 检查jupyter
    jupyter_version = run_command("jupyter --version")
    if jupyter_version['success']:
        print("Jupyter版本:")
        print(jupyter_version['stdout'])
    else:
        print("✗ Jupyter不可用")
    
    # 检查jupyterlab
    jupyterlab_version = run_command("jupyter lab --version")
    if jupyterlab_version['success']:
        print(f"JupyterLab版本: {jupyterlab_version['stdout']}")
    else:
        print("✗ JupyterLab不可用")
    
    print()

def main():
    """主函数"""
    print("=" * 60)
    print("全面服务器环境检查")
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    
    check_system_info()
    check_python_environment()
    check_pip_environment()
    check_installed_packages()
    check_cuda_environment()
    check_conda_environment()
    check_jupyter_environment()
    
    print("=" * 60)
    print("环境检查完成")
    print("=" * 60)

if __name__ == "__main__":
    main()