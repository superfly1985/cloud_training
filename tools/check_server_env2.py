#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查服务器环境脚本 - 完整版
"""

import paramiko
import json

# 服务器配置
HOST = "43.133.224.112"
PORT = 22
USERNAME = "root"
PASSWORD = "Vonzeus01"

def run_command(ssh, cmd, timeout=60):
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
        'has_torch': False,
        'has_ultralytics': False,
        'packages': {}
    }
    
    # 检查是否存在
    out, err = run_command(ssh, f'which {python_cmd}')
    if not out:
        return result
    result['exists'] = True
    
    # 检查版本
    out, err = run_command(ssh, f'{python_cmd} --version')
    result['version'] = out
    
    # 检查pip
    out, err = run_command(ssh, f'{python_cmd} -m pip --version 2>/dev/null')
    result['has_pip'] = 'pip' in out.lower() if out else False
    
    # 检查关键包
    packages_to_check = {
        'yaml': 'import yaml; print("OK")',
        'torch': 'import torch; print(f"{torch.__version__}|cuda:{torch.cuda.is_available()}")',
        'ultralytics': 'import ultralytics; print(ultralytics.__version__)',
        'numpy': 'import numpy; print(numpy.__version__)',
        'cv2': 'import cv2; print(cv2.__version__)',
        'PIL': 'from PIL import Image; print(Image.__version__)',
        'matplotlib': 'import matplotlib; print(matplotlib.__version__)',
        'pandas': 'import pandas; print(pandas.__version__)',
        'scipy': 'import scipy; print(scipy.__version__)',
        'tqdm': 'import tqdm; print(tqdm.__version__)',
        'psutil': 'import psutil; print(psutil.__version__)',
        'requests': 'import requests; print(requests.__version__)',
        'paramiko': 'import paramiko; print(paramiko.__version__)',
    }
    
    for pkg, check_cmd in packages_to_check.items():
        out, err = run_command(ssh, f'{python_cmd} -c "{check_cmd}" 2>/dev/null')
        if out and 'error' not in out.lower() and 'module' not in out.lower() and 'traceback' not in out.lower():
            result['packages'][pkg] = out
            if pkg == 'yaml':
                result['has_yaml'] = True
            elif pkg == 'torch':
                result['has_torch'] = True
            elif pkg == 'ultralytics':
                result['has_ultralytics'] = True
        else:
            result['packages'][pkg] = None
    
    return result

def main():
    print("="*70)
    print("服务器环境完整检查报告")
    print(f"服务器: {HOST}")
    print("="*70)
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"\n连接服务器 {HOST}:{PORT}...")
        ssh.connect(HOST, port=PORT, username=USERNAME, password=PASSWORD, timeout=15)
        print("✓ 连接成功\n")
        
        # 检查系统信息
        print("-"*70)
        print("【系统信息】")
        print("-"*70)
        out, err = run_command(ssh, 'cat /etc/os-release | grep -E "^(NAME|VERSION|ID)="')
        print(out)
        
        out, err = run_command(ssh, 'uname -r')
        print(f"内核版本: {out}")
        
        out, err = run_command(ssh, 'nproc')
        print(f"CPU核心数: {out}")
        
        out, err = run_command(ssh, 'free -h | grep Mem')
        print(f"内存: {out}")
        
        # 检查GPU
        print("\n-"*70)
        print("【GPU信息】")
        print("-"*70)
        out, err = run_command(ssh, 'nvidia-smi --query-gpu=name,memory.total,driver_version,cuda_version --format=csv,noheader 2>/dev/null || echo "未检测到NVIDIA GPU"')
        print(out)
        
        if 'Tesla' in out or 'NVIDIA' in out:
            out, err = run_command(ssh, 'nvidia-smi -L 2>/dev/null')
            print(f"GPU列表:\n{out}")
        
        # 检查CUDA
        print("\n-"*70)
        print("【CUDA环境】")
        print("-"*70)
        out, err = run_command(ssh, 'which nvcc && nvcc --version 2>/dev/null | grep release || echo "nvcc未找到"')
        print(out)
        
        out, err = run_command(ssh, 'ls -d /usr/local/cuda* 2>/dev/null || echo "未找到CUDA目录"')
        print(f"CUDA目录: {out}")
        
        # 检查Python环境
        print("\n-"*70)
        print("【Python环境详细检查】")
        print("-"*70)
        
        python_cmds = [
            '/root/miniforge3/bin/python3',
            '/root/anaconda3/bin/python3',
            '/root/miniconda3/bin/python3',
            '/opt/conda/bin/python3',
            '/usr/local/bin/python3',
            'python3.10',
            'python3.9',
            'python3.8',
            'python3',
            'python',
            '/usr/bin/python3',
            '/usr/bin/python',
        ]
        
        all_results = []
        for cmd in python_cmds:
            result = check_python_env(ssh, cmd)
            all_results.append(result)
            
            if result['exists']:
                print(f"\n>>> {cmd}")
                print(f"  Python版本: {result['version']}")
                print(f"  PIP: {'✓' if result['has_pip'] else '✗'}")
                print(f"  YAML: {'✓' if result['has_yaml'] else '✗'}")
                print(f"  PyTorch: {'✓' if result['has_torch'] else '✗'}")
                print(f"  Ultralytics: {'✓' if result['has_ultralytics'] else '✗'}")
                
                # 显示已安装的包
                installed = [f"{k}={v}" for k, v in result['packages'].items() if v]
                if installed:
                    print(f"  已安装包: {', '.join(installed[:5])}")
                    if len(installed) > 5:
                        print(f"            {', '.join(installed[5:])}")
        
        # 推荐方案分析
        print("\n" + "="*70)
        print("【环境分析与推荐方案】")
        print("="*70)
        
        # 找出最佳Python环境
        best_env = None
        candidates = []
        
        for r in all_results:
            if r['exists']:
                score = 0
                if r['has_yaml']: score += 10
                if r['has_torch']: score += 10
                if r['has_ultralytics']: score += 10
                if r['has_pip']: score += 5
                if 'miniforge' in r['cmd'] or 'anaconda' in r['cmd'] or 'conda' in r['cmd']: score += 3
                candidates.append((score, r))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        if candidates and candidates[0][0] > 0:
            best_env = candidates[0][1]
            print(f"\n✓ 推荐使用的Python环境:")
            print(f"   命令: {best_env['cmd']}")
            print(f"   版本: {best_env['version']}")
            print(f"   完整度: {candidates[0][0]}/38 分")
            
            missing = []
            if not best_env['has_yaml']: missing.append('pyyaml')
            if not best_env['has_torch']: missing.append('torch')
            if not best_env['has_ultralytics']: missing.append('ultralytics')
            if not best_env['packages'].get('cv2'): missing.append('opencv-python')
            if not best_env['packages'].get('matplotlib'): missing.append('matplotlib')
            
            if missing:
                print(f"\n   需要安装的包:")
                print(f"   {best_env['cmd']} -m pip install {' '.join(missing)} -q")
        else:
            print("\n✗ 未找到合适的Python环境")
            existing = [r for r in all_results if r['exists']]
            if existing:
                print(f"\n建议安装miniforge或anaconda环境")
        
        # 检查训练相关目录
        print("\n-"*70)
        print("【YOLO/训练相关目录】")
        print("-"*70)
        out, err = run_command(ssh, 'ls -la /root/ 2>/dev/null | grep -E "yolo|dataset|train|ultralytics" || echo "未找到YOLO相关目录"')
        print(out)
        
        # 检查常见数据集路径
        out, err = run_command(ssh, 'ls -la /root/yolo_dataset 2>/dev/null || echo "/root/yolo_dataset 不存在"')
        if '不存在' not in out:
            print(f"\n/root/yolo_dataset 内容:")
            print(out[:500] if len(out) > 500 else out)
        
        # 检查磁盘空间
        print("\n-"*70)
        print("【磁盘空间】")
        print("-"*70)
        out, err = run_command(ssh, 'df -h')
        print(out)
        
        # 检查网络连接
        print("\n-"*70)
        print("【网络连接测试】")
        print("-"*70)
        out, err = run_command(ssh, 'ping -c 1 -W 3 8.8.8.8 >/dev/null 2>&1 && echo "外网连接正常" || echo "外网连接失败"')
        print(out)
        
        out, err = run_command(ssh, 'curl -s -o /dev/null -w "%{http_code}" https://github.com 2>/dev/null || echo "000"')
        if out == '200':
            print("GitHub访问: 正常")
        else:
            print(f"GitHub访问: 异常 (HTTP {out})")
        
        ssh.close()
        print("\n" + "="*70)
        print("检查完成")
        print("="*70)
        
        # 输出JSON格式结果供程序使用
        print("\n" + "="*70)
        print("【JSON格式结果】")
        print("="*70)
        json_result = {
            'host': HOST,
            'best_python': best_env['cmd'] if best_env else None,
            'best_packages': best_env['packages'] if best_env else {},
            'all_envs': [{k: v for k, v in r.items() if k != 'packages'} for r in all_results if r['exists']]
        }
        print(json.dumps(json_result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
