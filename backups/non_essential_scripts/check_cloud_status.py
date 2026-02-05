#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import sys

def check_cloud_status():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('152.136.245.138', username='root', password='Vonzeus01', timeout=30)
        
        print("✅ SSH连接成功")
        
        # 查找所有.pt文件
        print("\n🔍 查找.pt文件...")
        stdin, stdout, stderr = ssh.exec_command('find /root -name "*.pt" -type f')
        pt_files = stdout.read().decode().strip()
        if pt_files:
            print("找到的.pt文件:")
            for file in pt_files.split('\n'):
                if file.strip():
                    print(f"  📄 {file}")
        else:
            print("❌ 未找到.pt文件")
        
        # 查找runs目录
        print("\n🔍 查找runs目录...")
        stdin, stdout, stderr = ssh.exec_command('find /root -name "runs" -type d')
        runs_dirs = stdout.read().decode().strip()
        if runs_dirs:
            print("找到的runs目录:")
            for dir in runs_dirs.split('\n'):
                if dir.strip():
                    print(f"  📁 {dir}")
                    # 检查每个runs目录的内容
                    stdin, stdout, stderr = ssh.exec_command(f'ls -la {dir}')
                    content = stdout.read().decode()
                    print(f"    内容: {content}")
        else:
            print("❌ 未找到runs目录")
        
        # 检查当前目录
        print("\n🔍 检查当前目录...")
        stdin, stdout, stderr = ssh.exec_command('pwd')
        pwd = stdout.read().decode().strip()
        print(f"当前目录: {pwd}")
        
        stdin, stdout, stderr = ssh.exec_command('ls -la')
        ls_output = stdout.read().decode()
        print("目录内容:")
        print(ls_output)
        
        # 检查训练进程
        print("\n🔍 检查训练进程...")
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep python')
        processes = stdout.read().decode()
        print("Python进程:")
        print(processes)
        
        ssh.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False
    
    return True

if __name__ == "__main__":
    check_cloud_status()