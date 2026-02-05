#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试训练启动失败的原因
"""

import paramiko

def debug_training_start():
    """调试训练启动失败的原因"""
    
    # 服务器配置
    server_config = {
        'hostname': '152.136.245.138',
        'port': 22,
        'username': 'root',
        'password': 'Vonzeus01'
    }
    
    try:
        # 连接服务器
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(**server_config, timeout=30)
        
        print("✓ 已连接到服务器")
        
        # 检查训练脚本是否存在
        print("\n📄 检查训练脚本...")
        cmd = "ls -la /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        if error:
            print(f"❌ 错误: {error}")
        else:
            print(f"✅ 脚本存在: {output}")
        
        # 检查脚本内容
        print("\n📋 检查脚本内容...")
        cmd = "head -30 /root/training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"脚本开头:\n{output}")
        
        # 检查Python环境
        print("\n🐍 检查Python环境...")
        cmd = "which python3 && python3 --version"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"Python环境: {output}")
        
        # 尝试直接运行脚本（前台）
        print("\n🧪 尝试直接运行脚本...")
        cmd = "cd /root && timeout 30 python3 training_script.py"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        if output:
            print(f"✅ 输出: {output}")
        if error:
            print(f"❌ 错误: {error}")
        
        # 检查日志文件
        print("\n📋 检查日志文件...")
        cmd = "ls -la /root/training.log 2>/dev/null && cat /root/training.log || echo '日志文件不存在'"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"日志内容: {output}")
        
        # 检查进程
        print("\n🔍 检查相关进程...")
        cmd = "ps aux | grep python"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        print(f"Python进程: {output}")
        
        # 检查CUDA环境（简化版）
        print("\n🎮 快速检查CUDA...")
        cmd = "python3 -c \"import torch; print('CUDA:', torch.cuda.is_available(), 'Devices:', torch.cuda.device_count())\""
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        error = stderr.read().decode('utf-8').strip()
        
        if output:
            print(f"✅ CUDA状态: {output}")
        if error:
            print(f"❌ CUDA错误: {error}")
        
        ssh.close()
        print("\n🎉 调试检查完成！")
        return True
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        return False

if __name__ == "__main__":
    print("🔍 开始调试训练启动问题...")
    debug_training_start()