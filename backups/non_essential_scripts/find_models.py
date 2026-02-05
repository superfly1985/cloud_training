#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko

def find_models():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('152.136.245.138', username='root', password='Vonzeus01', timeout=30)
        
        print("🔍 查找best.pt文件位置:")
        stdin, stdout, stderr = ssh.exec_command('find /root -name "best.pt" -type f')
        best_pt_files = stdout.read().decode().strip()
        if best_pt_files:
            print("找到best.pt文件:")
            for file in best_pt_files.split('\n'):
                if file.strip():
                    print(f"  📄 {file}")
                    # 获取文件信息
                    stdin, stdout, stderr = ssh.exec_command(f'ls -la "{file}"')
                    file_info = stdout.read().decode().strip()
                    print(f"     {file_info}")
        else:
            print("❌ 未找到best.pt文件")
        
        print("\n🔍 查找训练相关目录:")
        stdin, stdout, stderr = ssh.exec_command('find /root -name "*multiclass*" -type d')
        multiclass_dirs = stdout.read().decode().strip()
        if multiclass_dirs:
            print("找到multiclass相关目录:")
            for dir in multiclass_dirs.split('\n'):
                if dir.strip():
                    print(f"  📁 {dir}")
                    # 检查目录内容
                    stdin, stdout, stderr = ssh.exec_command(f'ls -la "{dir}"')
                    dir_content = stdout.read().decode()
                    print(f"     内容: {dir_content}")
        
        print("\n🔍 查找所有.pt文件:")
        stdin, stdout, stderr = ssh.exec_command('find /root -name "*.pt" -type f')
        all_pt_files = stdout.read().decode().strip()
        if all_pt_files:
            print("找到的.pt文件:")
            for file in all_pt_files.split('\n'):
                if file.strip():
                    print(f"  📄 {file}")
        
        ssh.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    find_models()