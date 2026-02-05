#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import json

def check_cloud_environment():
    """检查云端环境状态"""
    try:
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

        # 检查关键环境组件
        commands = {
            'Python': 'python3 --version',
            'NVIDIA驱动': 'nvidia-smi --query-gpu=name --format=csv,noheader,nounits',
            'CUDA': 'nvcc --version',
            'Docker': 'docker --version',
            'Git': 'git --version',
            'Ultralytics': 'pip show ultralytics | grep Version'
        }

        print('=== 云端环境检查结果 ===')
        missing_count = 0
        
        for name, cmd in commands.items():
            try:
                stdin, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode().strip()
                error = stderr.read().decode().strip()
                
                if output and 'not found' not in output:
                    first_line = output.split('\n')[0]
                    print(f'✓ {name}: {first_line}')
                else:
                    print(f'✗ {name}: 未安装或不可用')
                    missing_count += 1
                    
            except Exception as e:
                print(f'✗ {name}: 检查失败 - {str(e)[:50]}')
                missing_count += 1

        print(f'\n总结: {len(commands) - missing_count}/{len(commands)} 个组件可用')
        if missing_count > 0:
            print(f'缺失 {missing_count} 个组件')
        else:
            print('所有关键组件都已安装')

        ssh.close()
        return missing_count == 0
        
    except Exception as e:
        print(f'连接失败: {e}')
        return False

if __name__ == '__main__':
    check_cloud_environment()