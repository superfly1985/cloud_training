#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查云端服务器的CUDA环境状态
"""

import paramiko

def check_cuda_status():
    """检查CUDA环境状态"""
    
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
        
        # 检查CUDA相关信息
        print("\n🔍 检查CUDA环境...")
        
        cuda_commands = [
            "nvidia-smi",
            "nvcc --version",
            "python3 -c \"import torch; print(f'PyTorch版本: {torch.__version__}')\"",
            "python3 -c \"import torch; print(f'CUDA可用: {torch.cuda.is_available()}')\"",
            "python3 -c \"import torch; print(f'CUDA设备数量: {torch.cuda.device_count()}')\"",
            "python3 -c \"import torch; print(f'当前CUDA设备: {torch.cuda.current_device() if torch.cuda.is_available() else \"无\"}')\"",
            "echo $CUDA_VISIBLE_DEVICES",
            "ls -la /usr/local/cuda*/bin/nvcc 2>/dev/null || echo 'CUDA编译器未找到'",
            "cat /proc/driver/nvidia/version 2>/dev/null || echo 'NVIDIA驱动信息未找到'"
        ]
        
        for cmd in cuda_commands:
            print(f"\n执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error and "No such file" not in error and "command not found" not in error:
                print(f"❌ 错误: {error}")
            elif output:
                print(f"✅ 输出: {output}")
            else:
                print("📋 无输出")
        
        # 检查Docker中的CUDA支持
        print("\n🐳 检查Docker中的CUDA支持...")
        docker_commands = [
            "docker --version",
            "docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvidia-smi 2>/dev/null || echo 'Docker GPU支持测试失败'",
            "docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu20.04 nvcc --version 2>/dev/null || echo 'Docker CUDA编译器测试失败'"
        ]
        
        for cmd in docker_commands:
            print(f"\n执行: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error and "No such file" not in error:
                print(f"❌ 错误: {error}")
            elif output:
                print(f"✅ 输出: {output}")
            else:
                print("📋 无输出")
        
        # 检查当前训练脚本的设备配置
        print("\n📄 检查当前训练脚本...")
        cmd = "cat /root/training_script.py | grep -A 5 -B 5 device"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        output = stdout.read().decode('utf-8').strip()
        if output:
            print(f"✅ 训练脚本中的设备配置:\n{output}")
        else:
            print("❌ 未找到设备配置")
        
        ssh.close()
        print("\n🎉 CUDA环境检查完成！")
        return True
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    print("🔍 开始检查CUDA环境状态...")
    check_cuda_status()