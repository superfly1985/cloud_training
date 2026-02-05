#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import json
import time

def fix_dpkg_and_verify():
    """修复dpkg问题并验证安装状态"""
    
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
    
    print('🔧 修复dpkg中断问题...')
    
    # 设置非交互式环境并修复dpkg问题
    fix_commands = [
        'export DEBIAN_FRONTEND=noninteractive',
        'dpkg --configure -a --force-confdef --force-confold',
        'apt-get update -y',
        'apt-get -f install -y',
        'apt-get autoremove -y',
        'apt-get autoclean'
    ]
    
    # 组合命令以确保环境变量生效
    combined_cmd = ' && '.join(fix_commands)
    
    print(f'📋 执行修复命令...')
    try:
        stdin, stdout, stderr = ssh.exec_command(combined_cmd, timeout=600)
        
        # 显示输出
        output = stdout.read().decode('utf-8', errors='ignore')
        error = stderr.read().decode('utf-8', errors='ignore')
        
        if output:
            print('✅ 修复输出:')
            print(output[-1000:])  # 显示最后1000字符
        
        if error and 'WARNING' not in error:
            print('⚠️ 错误信息:')
            print(error[-500:])  # 显示最后500字符
            
    except Exception as e:
        print(f'❌ 修复失败: {str(e)}')
    
    print('\n🔍 验证组件安装状态...')
    
    verify_commands = {
        'Docker': 'docker --version',
        'Docker服务状态': 'systemctl is-active docker || echo "未运行"',
        'Git': 'git --version',
        'Python3': 'python3 --version',
        'NVIDIA驱动': 'nvidia-smi --query-gpu=name --format=csv,noheader || echo "未安装"'
    }
    
    for name, cmd in verify_commands.items():
        try:
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode().strip()
            
            if output and 'not found' not in output.lower():
                print(f'✅ {name}: {output}')
            else:
                print(f'❌ {name}: 未安装或不可用')
        except Exception as e:
            print(f'❌ {name}: 检查失败 - {str(e)}')
    
    # 检查系统状态
    print('\n📊 系统状态:')
    
    try:
        stdin, stdout, stderr = ssh.exec_command('df -h / && echo "---" && free -h')
        output = stdout.read().decode().strip()
        print(output)
    except Exception as e:
        print(f'系统状态检查失败: {str(e)}')
    
    ssh.close()
    print('\n🎉 检查完成！')

if __name__ == '__main__':
    fix_dpkg_and_verify()