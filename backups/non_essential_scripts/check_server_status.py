#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import json

def check_server_status():
    """检查云端服务器当前状态"""
    
    # 读取配置
    with open('cloud_training_config.json', 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 连接服务器
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        hostname=config['server']['hostname'],
        username=config['server']['username'],
        password=config['server']['password'],
        port=config['server'].get('port', 22)
    )
    
    print('=== 云端服务器状态检查 ===')
    
    # 检查命令
    commands = {
        '正在运行的apt进程': 'ps aux | grep apt | grep -v grep',
        '正在运行的pip进程': 'ps aux | grep pip | grep -v grep', 
        '正在运行的安装进程': 'ps aux | grep install | grep -v grep',
        '系统负载': 'uptime',
        '内存使用': 'free -h',
        '磁盘使用': 'df -h /',
        '最近的进程': 'ps aux --sort=-%cpu | head -10'
    }
    
    for name, cmd in commands.items():
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            print(f'\n📋 {name}:')
            if output:
                print(output)
            else:
                print('  无相关进程运行')
        except Exception as e:
            print(f'  错误: {str(e)}')
    
    ssh.close()
    print('\n✅ 检查完成')

if __name__ == '__main__':
    check_server_status()