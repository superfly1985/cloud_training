#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import json

def check_docker_status():
    """检查Docker的详细安装状态并尝试修复"""
    
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

    print('=== Docker详细检查和修复 ===')

    commands = [
        ('检查Docker包', 'dpkg -l | grep docker'),
        ('检查Docker二进制文件', 'which docker || echo "Docker二进制文件未找到"'),
        ('尝试启动Docker服务', 'sudo systemctl start docker'),
        ('检查Docker服务状态', 'sudo systemctl status docker --no-pager'),
        ('测试Docker命令', 'docker --version'),
        ('检查Docker组', 'groups $USER'),
        ('检查NVIDIA驱动问题', 'nvidia-smi || echo "NVIDIA驱动有问题"'),
        ('检查CUDA版本', 'nvcc --version || echo "CUDA未安装"')
    ]

    for name, cmd in commands:
        print(f'\n📋 {name}:')
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if output:
                print(output)
            if error and 'WARNING' not in error:
                print(f'错误: {error}')
        except Exception as e:
            print(f'执行失败: {str(e)}')

    # 尝试修复Docker权限问题
    print('\n=== 尝试修复Docker权限 ===')
    fix_commands = [
        ('添加用户到docker组', f'sudo usermod -aG docker {config["server"]["username"]}'),
        ('重新加载组权限', 'newgrp docker'),
        ('再次测试Docker', 'docker --version')
    ]
    
    for name, cmd in fix_commands:
        print(f'\n🔧 {name}:')
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if output:
                print(output)
            if error and 'WARNING' not in error:
                print(f'错误: {error}')
        except Exception as e:
            print(f'执行失败: {str(e)}')

    ssh.close()
    print('\n🎉 Docker检查完成！')

if __name__ == "__main__":
    check_docker_status()