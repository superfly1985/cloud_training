#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查云端数据集目录结构脚本
用于诊断和修复数据集路径问题
"""

import paramiko
import json
import os
from datetime import datetime

def load_config():
    """加载云端训练配置"""
    config_file = 'cloud_training_config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        print(f"配置文件 {config_file} 不存在")
        return None

def connect_to_server(config):
    """连接到云端服务器"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        ssh.connect(
            hostname=config['server']['hostname'],
            port=config['server']['port'],
            username=config['server']['username'],
            password=config['server']['password'],
            timeout=30
        )
        
        print(f"✅ 成功连接到服务器 {config['server']['hostname']}")
        return ssh
    except Exception as e:
        print(f"❌ 连接服务器失败: {e}")
        return None

def check_directory_structure(ssh, base_path="/root"):
    """检查目录结构"""
    print(f"\n🔍 检查目录结构: {base_path}")
    
    # 检查主要目录
    directories_to_check = [
        "/root/yolo_dataset",
        "/root/datasets", 
        "/root/yolo_dataset/train",
        "/root/yolo_dataset/val",
        "/root/yolo_dataset/test",
        "/root/yolo_dataset/train/images",
        "/root/yolo_dataset/train/labels",
        "/root/yolo_dataset/val/images", 
        "/root/yolo_dataset/val/labels",
        "/root/yolo_dataset/test/images",
        "/root/yolo_dataset/test/labels"
    ]
    
    structure_info = {}
    
    for directory in directories_to_check:
        try:
            # 检查目录是否存在
            stdin, stdout, stderr = ssh.exec_command(f"ls -la {directory}")
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                output = stdout.read().decode('utf-8')
                structure_info[directory] = {
                    'exists': True,
                    'content': output.strip(),
                    'file_count': len([line for line in output.split('\n') if line.strip() and not line.startswith('total')])
                }
                print(f"✅ {directory} - 存在 ({structure_info[directory]['file_count']} 项)")
            else:
                structure_info[directory] = {
                    'exists': False,
                    'error': stderr.read().decode('utf-8').strip()
                }
                print(f"❌ {directory} - 不存在")
                
        except Exception as e:
            structure_info[directory] = {
                'exists': False,
                'error': str(e)
            }
            print(f"❌ {directory} - 检查失败: {e}")
    
    return structure_info

def check_dataset_yaml(ssh):
    """检查dataset.yaml文件内容"""
    print(f"\n📄 检查dataset.yaml文件")
    
    yaml_paths = [
        "/root/yolo_dataset/dataset.yaml",
        "/root/dataset.yaml",
        "/root/datasets/dataset.yaml"
    ]
    
    yaml_info = {}
    
    for yaml_path in yaml_paths:
        try:
            stdin, stdout, stderr = ssh.exec_command(f"cat {yaml_path}")
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                content = stdout.read().decode('utf-8')
                yaml_info[yaml_path] = {
                    'exists': True,
                    'content': content
                }
                print(f"✅ 找到 {yaml_path}")
                print(f"内容:\n{content}")
            else:
                yaml_info[yaml_path] = {
                    'exists': False,
                    'error': stderr.read().decode('utf-8').strip()
                }
                print(f"❌ {yaml_path} - 不存在")
                
        except Exception as e:
            yaml_info[yaml_path] = {
                'exists': False,
                'error': str(e)
            }
            print(f"❌ {yaml_path} - 检查失败: {e}")
    
    return yaml_info

def find_actual_dataset_location(ssh):
    """查找实际的数据集位置"""
    print(f"\n🔎 查找实际数据集位置")
    
    # 搜索可能的数据集位置
    search_commands = [
        "find /root -name '*.jpg' -o -name '*.png' -o -name '*.jpeg' | head -20",
        "find /root -name '*.txt' -path '*/labels/*' | head -10", 
        "find /root -type d -name 'images' | head -10",
        "find /root -type d -name 'labels' | head -10",
        "find /root -name 'dataset.yaml' | head -5"
    ]
    
    search_results = {}
    
    for i, command in enumerate(search_commands):
        try:
            stdin, stdout, stderr = ssh.exec_command(command)
            exit_code = stdout.channel.recv_exit_status()
            
            if exit_code == 0:
                output = stdout.read().decode('utf-8').strip()
                search_results[f"search_{i+1}"] = {
                    'command': command,
                    'output': output,
                    'files_found': len(output.split('\n')) if output else 0
                }
                print(f"🔍 {command}")
                if output:
                    print(f"找到 {len(output.split('\n'))} 个文件:")
                    for line in output.split('\n')[:5]:  # 只显示前5个
                        print(f"  {line}")
                    if len(output.split('\n')) > 5:
                        print(f"  ... 还有 {len(output.split('\n')) - 5} 个文件")
                else:
                    print("  未找到文件")
            else:
                search_results[f"search_{i+1}"] = {
                    'command': command,
                    'error': stderr.read().decode('utf-8').strip()
                }
                print(f"❌ 搜索失败: {command}")
                
        except Exception as e:
            search_results[f"search_{i+1}"] = {
                'command': command,
                'error': str(e)
            }
            print(f"❌ 搜索异常: {command} - {e}")
    
    return search_results

def generate_report(structure_info, yaml_info, search_results):
    """生成检查报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"dataset_structure_report_{timestamp}.json"
    
    report = {
        'timestamp': timestamp,
        'directory_structure': structure_info,
        'yaml_files': yaml_info,
        'search_results': search_results,
        'summary': {
            'total_directories_checked': len(structure_info),
            'existing_directories': len([d for d in structure_info.values() if d.get('exists', False)]),
            'yaml_files_found': len([y for y in yaml_info.values() if y.get('exists', False)]),
            'recommendations': []
        }
    }
    
    # 生成建议
    if not any(d.get('exists', False) for path, d in structure_info.items() if 'yolo_dataset' in path):
        report['summary']['recommendations'].append("需要创建 /root/yolo_dataset 目录结构")
    
    if not any(y.get('exists', False) for y in yaml_info.values()):
        report['summary']['recommendations'].append("需要创建或修复 dataset.yaml 文件")
    
    if not structure_info.get('/root/yolo_dataset/val/images', {}).get('exists', False):
        report['summary']['recommendations'].append("需要创建 /root/yolo_dataset/val/images 目录")
    
    # 保存报告
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 检查报告已保存到: {report_file}")
    return report

def main():
    """主函数"""
    print("🚀 开始检查云端数据集结构...")
    
    # 加载配置
    config = load_config()
    if not config:
        return
    
    # 连接服务器
    ssh = connect_to_server(config)
    if not ssh:
        return
    
    try:
        # 检查目录结构
        structure_info = check_directory_structure(ssh)
        
        # 检查YAML文件
        yaml_info = check_dataset_yaml(ssh)
        
        # 查找实际数据集位置
        search_results = find_actual_dataset_location(ssh)
        
        # 生成报告
        report = generate_report(structure_info, yaml_info, search_results)
        
        print("\n" + "="*60)
        print("📋 检查总结:")
        print(f"✅ 检查了 {report['summary']['total_directories_checked']} 个目录")
        print(f"✅ 找到 {report['summary']['existing_directories']} 个存在的目录")
        print(f"✅ 找到 {report['summary']['yaml_files_found']} 个YAML文件")
        
        if report['summary']['recommendations']:
            print("\n💡 建议:")
            for rec in report['summary']['recommendations']:
                print(f"  • {rec}")
        
    except Exception as e:
        print(f"❌ 检查过程中发生错误: {e}")
    
    finally:
        ssh.close()
        print("\n🔚 检查完成")

if __name__ == "__main__":
    main()