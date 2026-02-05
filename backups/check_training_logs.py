#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko

def check_training_logs():
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect('152.136.245.138', username='root', password='Vonzeus01', timeout=30)
        
        print("📋 检查training.log的最后50行:")
        stdin, stdout, stderr = ssh.exec_command('tail -50 /root/training.log')
        log_tail = stdout.read().decode()
        print(log_tail)
        
        print("\n📋 检查yolo8_training.log的最后30行:")
        stdin, stdout, stderr = ssh.exec_command('tail -30 /root/yolo8_training.log')
        yolo_log_tail = stdout.read().decode()
        print(yolo_log_tail)
        
        print("\n📁 检查runs目录详细内容:")
        stdin, stdout, stderr = ssh.exec_command('find /root/runs -type f')
        files_in_runs = stdout.read().decode()
        print("runs目录中的所有文件:")
        print(files_in_runs if files_in_runs.strip() else "无文件")
        
        # 检查是否有训练完成的标志
        print("\n🔍 查找训练完成标志:")
        stdin, stdout, stderr = ssh.exec_command('grep -i "training complete\\|best\\|finished\\|done" /root/training.log | tail -10')
        completion_signs = stdout.read().decode()
        if completion_signs.strip():
            print("找到训练完成标志:")
            print(completion_signs)
        else:
            print("未找到明确的训练完成标志")
        
        ssh.close()
        
    except Exception as e:
        print(f"❌ 错误: {e}")

if __name__ == "__main__":
    check_training_logs()