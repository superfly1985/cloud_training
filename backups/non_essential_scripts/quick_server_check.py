#!/usr/bin/env python3
"""
快速SSH服务器环境检查脚本
"""

import paramiko
import json
import os

def load_config():
    """加载配置文件"""
    config_file = "cloud_training_config.json"
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get('server', {})
    return None

def run_ssh_command(ssh, command):
    """执行SSH命令"""
    try:
        stdin, stdout, stderr = ssh.exec_command(command)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        return {
            'success': len(error) == 0 or 'warning' in error.lower(),
            'output': output,
            'error': error
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': str(e)
        }

def main():
    """主函数"""
    config = load_config()
    if not config:
        print("❌ 无法加载配置文件")
        return
    
    # 建立SSH连接
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        if config.get('key_file') and os.path.exists(config['key_file']):
            ssh.connect(
                hostname=config['hostname'],
                port=config.get('port', 22),
                username=config['username'],
                key_filename=config['key_file']
            )
        else:
            ssh.connect(
                hostname=config['hostname'],
                port=config.get('port', 22),
                username=config['username'],
                password=config.get('password', '')
            )
        
        print("✅ SSH连接成功")
        print("=" * 60)
        
        # 检查系统信息
        print("🖥️  系统信息:")
        result = run_ssh_command(ssh, "cat /etc/os-release | grep PRETTY_NAME")
        if result['success']:
            print(f"   {result['output']}")
        
        result = run_ssh_command(ssh, "uname -r")
        if result['success']:
            print(f"   内核: {result['output']}")
        
        print()
        
        # 检查Python环境
        print("🐍 Python环境:")
        
        # 检查Python版本
        for py_cmd in ['python', 'python3', 'python3.10']:
            result = run_ssh_command(ssh, f"which {py_cmd}")
            if result['success'] and result['output']:
                version_result = run_ssh_command(ssh, f"{py_cmd} --version")
                if version_result['success']:
                    print(f"   ✅ {py_cmd}: {version_result['output']} ({result['output']})")
                else:
                    print(f"   ⚠️  {py_cmd}: 路径存在但无法获取版本")
            else:
                print(f"   ❌ {py_cmd}: 不存在")
        
        print()
        
        # 检查pip环境
        print("📦 Pip环境:")
        for pip_cmd in ['pip', 'pip3', 'python3 -m pip']:
            result = run_ssh_command(ssh, f"{pip_cmd} --version")
            if result['success']:
                print(f"   ✅ {pip_cmd}: {result['output']}")
            else:
                print(f"   ❌ {pip_cmd}: {result['error'][:100]}")
        
        print()
        
        # 检查关键Python包
        print("📚 关键Python包:")
        packages = {
            'torch': 'import torch; print("PyTorch " + torch.__version__)',
            'ultralytics': 'import ultralytics; print("Ultralytics " + ultralytics.__version__)',
            'numpy': 'import numpy; print("NumPy " + numpy.__version__)',
            'cv2': 'import cv2; print("OpenCV " + cv2.__version__)',
            'PIL': 'import PIL; print("Pillow " + PIL.__version__)',
            'matplotlib': 'import matplotlib; print("Matplotlib " + matplotlib.__version__)',
            'yaml': 'import yaml; print("PyYAML OK")'
        }
        
        for pkg_name, import_cmd in packages.items():
            # 使用单引号包围整个命令，避免引号冲突
            result = run_ssh_command(ssh, f"python3 -c '{import_cmd}'")
            if result['success']:
                print(f"   ✅ {pkg_name}: {result['output']}")
            else:
                print(f"   ❌ {pkg_name}: {result['error'][:100]}")
        
        print()
        
        # 检查CUDA环境
        print("🚀 CUDA环境:")
        
        # 检查nvidia-smi
        result = run_ssh_command(ssh, "nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits")
        if result['success']:
            print(f"   ✅ GPU信息: {result['output']}")
        else:
            print(f"   ❌ nvidia-smi: {result['error'][:100]}")
        
        # 检查CUDA版本
        result = run_ssh_command(ssh, "nvcc --version | grep release")
        if result['success']:
            print(f"   ✅ CUDA编译器: {result['output']}")
        else:
            print(f"   ❌ nvcc: {result['error'][:100]}")
        
        # 检查PyTorch CUDA
        cuda_cmd = 'import torch; print("PyTorch CUDA: " + str(torch.cuda.is_available()) + ", Version: " + str(torch.version.cuda))'
        result = run_ssh_command(ssh, f"python3 -c '{cuda_cmd}'")
        if result['success']:
            print(f"   ✅ PyTorch CUDA: {result['output']}")
        else:
            print(f"   ❌ PyTorch CUDA: {result['error'][:100]}")
        
        print()
        
        # 检查Conda环境
        print("🐍 Conda环境:")
        result = run_ssh_command(ssh, "conda --version")
        if result['success']:
            print(f"   ✅ Conda: {result['output']}")
            
            # 检查当前环境
            result = run_ssh_command(ssh, "conda info --envs")
            if result['success']:
                print("   环境列表:")
                for line in result['output'].split('\n')[:5]:  # 只显示前5行
                    if line.strip():
                        print(f"     {line}")
        else:
            print(f"   ❌ Conda: {result['error'][:100]}")
        
        print()
        
        # 检查Jupyter
        print("📓 Jupyter环境:")
        result = run_ssh_command(ssh, "jupyter lab --version")
        if result['success']:
            print(f"   ✅ JupyterLab: {result['output']}")
        else:
            print(f"   ❌ JupyterLab: {result['error'][:100]}")
        
        print()
        
        # 检查工作目录和更广泛的系统目录
        print("📁 系统目录结构:")
        result = run_ssh_command(ssh, "pwd")
        if result['success']:
            print(f"   当前目录: {result['output']}")
        
        # 检查多个重要目录
        important_dirs = [
            '/root',
            '/home',
            '/opt',
            '/usr/local',
            '/usr/local/bin',
            '/usr/bin',
            '/etc',
            '/var/log'
        ]
        
        for dir_path in important_dirs:
            result = run_ssh_command(ssh, f'ls -la {dir_path} 2>/dev/null | head -10')
            if result['success'] and result['output'].strip():
                print(f"   {dir_path}/ 目录内容:")
                for line in result['output'].split('\n')[:8]:  # 只显示前8行
                    if line.strip():
                        print(f"     {line}")
        
        # 检查Python相关的安装位置
        print("\n🔍 Python环境详细信息:")
        python_checks = [
            ('Python3路径', 'which python3'),
            ('Python3版本详细', 'python3 --version'),
            ('Python3模块路径', 'python3 -c "import sys; print(sys.path)"'),
            ('Pip3路径', 'which pip3'),
            ('Pip3版本详细', 'pip3 --version'),
            ('已安装包列表', 'pip3 list | head -20'),
            ('环境变量PATH', 'echo $PATH'),
            ('环境变量PYTHONPATH', 'echo $PYTHONPATH')
        ]
        
        for desc, cmd in python_checks:
            result = run_ssh_command(ssh, cmd)
            if result['success']:
                print(f"   ✅ {desc}: {result['output'][:200]}...")  # 限制输出长度
            else:
                print(f"   ❌ {desc}: {result['error'][:100]}...")
        
        # 检查可能的虚拟环境
        print("\n🐍 虚拟环境检查:")
        venv_checks = [
            ('检查conda环境', 'ls -la /opt/conda* /usr/local/conda* /home/*/anaconda* /home/*/miniconda* 2>/dev/null'),
            ('检查virtualenv', 'ls -la /home/*/venv* /opt/venv* /usr/local/venv* 2>/dev/null'),
            ('检查pip用户安装', 'ls -la ~/.local/lib/python*/site-packages/ 2>/dev/null | head -5'),
            ('检查系统Python包', 'ls -la /usr/lib/python3*/dist-packages/ 2>/dev/null | head -5')
        ]
        
        for desc, cmd in venv_checks:
            result = run_ssh_command(ssh, cmd)
            if result['success'] and result['output'].strip():
                print(f"   ✅ {desc}:")
                for line in result['output'].split('\n')[:5]:
                    if line.strip():
                        print(f"     {line}")
        
        # 检查Docker和容器环境
        print("\n🐳 容器环境检查:")
        container_checks = [
            ('Docker状态', 'docker --version 2>/dev/null'),
            ('Docker容器', 'docker ps -a 2>/dev/null'),
            ('Docker镜像', 'docker images 2>/dev/null | head -5')
        ]
        
        for desc, cmd in container_checks:
            result = run_ssh_command(ssh, cmd)
            if result['success']:
                print(f"   ✅ {desc}: {result['output'][:200]}...")
            else:
                print(f"   ❌ {desc}: 未安装或无权限")
        
        print("=" * 60)
        print("✅ 扩展环境检查完成")
        
    except Exception as e:
        print(f"❌ SSH连接失败: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    main()