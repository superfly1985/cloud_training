#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查服务器环境脚本
"""

import paramiko
import json

# 服务器配置
HOST = "43.156.152.22"
PORT = 22
USERNAME = "root"
PASSWORD = "Vonzeus01"

def run_command(ssh, cmd, timeout=30):
    """执行命令并返回输出"""
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    return out, err

def check_python_env(ssh, python_cmd):
    """检查Python环境详情"""
    result = {
        'cmd': python_cmd,
        'exists': False,
        'version': '',
        'has_yaml': False,
        'has_pip': False,
        'packages': []
    }
    
    # 检查是否存在
    out, err = run_command(ssh, f'which {python_cmd}')
    if not out:
        return result
    result['exists'] = True
    
    # 检查版本
    out, err = run_command(ssh, f'{python_cmd} --version')
    result['version'] = out
    
    # 检查yaml模块
    out, err = run_command(ssh, f'{python_cmd} -c "import yaml; print(\"yaml_ok\")"')
    result['has_yaml'] = (out == 'yaml_ok')
    
    # 检查pip
    out, err = run_command(ssh, f'{python_cmd} -m pip --version')
    result['has_pip'] = 'pip' in out.lower()
    
    # 检查关键包
    packages_to_check = ['torch', 'ultralytics', 'numpy', 'cv2', 'PIL', 'matplotlib', 'yaml']
    for pkg in packages_to_check:
        if pkg == 'cv2':
            out, err = run_command(ssh, f'{python_cmd} -c "import cv2; print(cv2.__version__)"')
        elif pkg == 'PIL':
            out, err = run_command(ssh, f'{python_cmd} -c "import PIL; print(PIL.__version__)"')
        elif pkg == 'yaml':
            out, err = run_command(ssh, f'{python_cmd} -c "import yaml; print(\"OK\")"')
        else:
            out, err = run_command(ssh, f'{python_cmd} -c "import {pkg}; print({pkg}.__version__)"')
        
        if out and 'error' not in out.lower() and 'module' not in out.lower():
            result['packages'].append(f"{pkg}: {out}")
        else:
            result['packages'].append(f"{pkg}: 未安装")
    
    return result

def main():
    print("="*60)
    print("服务器环境检查报告")
    print("="*60)
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"\n连接服务器 {HOST}:{PORT}...")
        ssh.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=15)
        print("✓ 连接成功\n")
        
        # 检查系统信息
        print("-"*60)
        print("【系统信息】")
        print("-"*60)
        out, err = run_command(ssh, 'cat /etc/os-release | head -5')
        print(out)
        
        out, err = run_command(ssh, 'uname -a')
        print(f"内核: {out}")
        
        # 检查GPU
        print("\n-"*60)
        print("【GPU信息】")
        print("-"*60)
        out, err = run_command(ssh, 'nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || echo "未检测到NVIDIA GPU"')
        print(out)
        
        # 检查Python环境
        print("\n-"*60)
        print("【Python环境检查】")
        print("-"*60)
        
        python_cmds = [
            '/root/miniforge3/bin/python3',
            '/root/anaconda3/bin/python3',
            '/root/miniconda3/bin/python3',
            'python3',
            'python',
            '/usr/bin/python3',
            '/usr/bin/python'
        ]
        
        all_results = []
        for cmd in python_cmds:
            result = check_python_env(ssh, cmd)
            all_results.append(result)
            
            if result['exists']:
                print(f"\n>>> {cmd}")
                print(f"  版本: {result['version']}")
                print(f"  YAML模块: {'✓' if result['has_yaml'] else '✗'}")
                print(f"  PIP: {'✓' if result['has_pip'] else '✗'}")
                print("  已安装包:")
                for pkg in result['packages']:
                    print(f"    - {pkg}")
        
        # 推荐方案
        print("\n" + "="*60)
        print("【推荐方案】")
        print("="*60)
        
        # 找出最佳Python环境
        best_env = None
        for r in all_results:
            if r['exists'] and r['has_yaml']:
                if 'miniforge' in r['cmd'] or 'anaconda' in r['cmd'] or 'miniconda' in r['cmd']:
                    best_env = r
                    break
                elif best_env is None:
                    best_env = r
        
        if best_env:
            print(f"\n推荐使用的Python环境: {best_env['cmd']}")
            print(f"版本: {best_env['version']}")
            print("该环境已具备yaml模块，可直接使用。")
        else:
            print("\n未找到带yaml模块的Python环境，建议方案:")
            
            # 找存在的Python
            existing = [r for r in all_results if r['exists']]
            if existing:
                print(f"\n1. 使用系统Python并安装yaml:")
                print(f"   推荐命令: {existing[0]['cmd']}")
                print(f"   安装命令: {existing[0]['cmd']} -m pip install pyyaml")
                
                # 检查是否有apt
                out, err = run_command(ssh, 'which apt-get')
                if out:
                    print(f"\n   或使用系统包管理器:")
                    print(f"   apt-get update && apt-get install -y python3-yaml")
        
        # 检查训练相关目录
        print("\n-"*60)
        print("【目录检查】")
        print("-"*60)
        out, err = run_command(ssh, 'ls -la /root/ | grep -E "yolo|dataset|train" || echo "未找到YOLO相关目录"')
        print(out)
        
        # 检查磁盘空间
        print("\n-"*60)
        print("【磁盘空间】")
        print("-"*60)
        out, err = run_command(ssh, 'df -h /root')
        print(out)
        
        ssh.close()
        print("\n" + "="*60)
        print("检查完成")
        print("="*60)
        
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
