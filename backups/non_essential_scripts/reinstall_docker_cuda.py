#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import json
import time

def reinstall_docker_cuda():
    """重新安装Docker和CUDA组件"""
    
    with open('cloud_training_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=config['server']['hostname'],
        username=config['server']['username'],
        password=config['server']['password'],
        port=config['server'].get('port', 22)
    )

    print('=== 重新安装Docker和CUDA组件 ===')

    # 安装命令序列
    install_commands = [
        ('更新包列表', 'apt-get update'),
        ('安装Docker依赖', 'apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release'),
        ('添加Docker GPG密钥', 'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -'),
        ('添加Docker仓库', 'add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"'),
        ('再次更新包列表', 'apt-get update'),
        ('安装Docker CE', 'apt-get install -y docker-ce docker-ce-cli containerd.io'),
        ('启动Docker服务', 'service docker start'),
        ('检查Docker状态', 'docker --version'),
        ('安装NVIDIA驱动', 'apt-get install -y nvidia-driver-470'),
        ('安装CUDA工具包', 'apt-get install -y cuda-11-8'),
        ('检查NVIDIA驱动', 'nvidia-smi'),
        ('检查CUDA', 'nvcc --version')
    ]

    for name, cmd in install_commands:
        print(f'\n🔧 {name}...')
        try:
            # 使用sudo执行命令
            full_cmd = f'sudo {cmd}' if not cmd.startswith('sudo') else cmd
            stdin, stdout, stderr = ssh.exec_command(full_cmd)
            
            # 等待命令完成
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if exit_status == 0:
                print(f'✅ {name} 成功')
                if output and len(output) < 200:  # 只显示短输出
                    print(f'输出: {output}')
            else:
                print(f'❌ {name} 失败 (退出码: {exit_status})')
                if error:
                    print(f'错误: {error[:200]}...' if len(error) > 200 else error)
                    
        except Exception as e:
            print(f'❌ {name} 执行失败: {str(e)}')
        
        # 短暂延迟
        time.sleep(1)

    # 最终验证
    print('\n=== 最终验证 ===')
    verification_commands = [
        ('Docker版本', 'docker --version'),
        ('Docker服务状态', 'service docker status'),
        ('NVIDIA驱动', 'nvidia-smi'),
        ('CUDA版本', 'nvcc --version'),
        ('PyTorch CUDA支持', 'python3 -c "import torch; print(f\'CUDA可用: {torch.cuda.is_available()}, 设备数: {torch.cuda.device_count()}\');"')
    ]
    
    for name, cmd in verification_commands:
        print(f'\n📋 验证{name}:')
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if output:
                print(f'✅ {output}')
            if error and 'WARNING' not in error:
                print(f'⚠️ {error}')
        except Exception as e:
            print(f'❌ 验证失败: {str(e)}')

    ssh.close()
    print('\n🎉 重新安装完成！')

if __name__ == "__main__":
    reinstall_docker_cuda()