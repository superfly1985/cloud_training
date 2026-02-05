#!/usr/bin/env python3
import paramiko
import json
import os

def run_ssh_command(ssh, command):
    try:
        stdin, stdout, stderr = ssh.exec_command(command, timeout=30)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        return {'success': True, 'output': output, 'error': error}
    except Exception as e:
        return {'success': False, 'output': '', 'error': str(e)}

def main():
    # 加载配置
    with open('cloud_training_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)['server']

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(config['hostname'], port=config['port'], username=config['username'], password=config['password'])
    
    print("✅ SSH连接成功")
    print("=" * 60)
    
    # 检查包的实际位置
    packages_to_check = ['cv2', 'PIL', 'numpy', 'matplotlib']
    
    for pkg in packages_to_check:
        print(f"\n🔍 检查 {pkg} 包:")
        
        # 检查包文件位置
        cmd = f'python3 -c "import {pkg}; print({pkg}.__file__)"'
        result = run_ssh_command(ssh, cmd)
        if result['success']:
            print(f"  位置: {result['output']}")
        else:
            print(f"  错误: {result['error']}")
    
    # 检查实际的dist-packages目录
    print(f"\n🔍 检查 /usr/lib/python3/dist-packages/ 目录:")
    result = run_ssh_command(ssh, 'ls -la /usr/lib/python3/dist-packages/ | head -20')
    if result['success']:
        print("目录内容:")
        for line in result['output'].split('\n'):
            if line.strip():
                print(f"  {line}")
    
    # 检查是否有torch相关的安装尝试
    print(f"\n🔍 检查torch安装历史:")
    result = run_ssh_command(ssh, 'pip3 show torch 2>/dev/null || echo "torch未安装"')
    if result['success']:
        print(f"  {result['output']}")
    
    result = run_ssh_command(ssh, 'pip3 show ultralytics 2>/dev/null || echo "ultralytics未安装"')
    if result['success']:
        print(f"  {result['output']}")
    
    ssh.close()
    print("\n" + "=" * 60)
    print("✅ 包位置检查完成")

if __name__ == "__main__":
    main()