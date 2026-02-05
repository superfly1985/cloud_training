#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import paramiko
import os
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('model_download_specific.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def download_models():
    # 云服务器配置
    hostname = '152.136.245.138'
    username = 'root'
    password = 'Vonzeus01'
    port = 22
    
    # 本地下载目录
    local_dir = r'd:\OneDrive\24.Visual AI\runs\detect\cloud_trained'
    
    # 确保本地目录存在
    os.makedirs(local_dir, exist_ok=True)
    
    # 远程模型路径
    remote_base_path = '/root/multi_class_industrial_detection/v3_multiclass_kading_bracket_doublepin_yolov8s_v3config'
    
    models_to_download = [
        ('weights/best.pt', 'best_v3_multiclass_industrial.pt'),
        ('weights/last.pt', 'last_v3_multiclass_industrial.pt'),
        ('results.png', 'training_results.png'),
        ('confusion_matrix.png', 'confusion_matrix.png'),
        ('results.csv', 'training_results.csv')
    ]
    
    try:
        # 连接SSH
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname, port=port, username=username, password=password, timeout=30)
        
        # 创建SFTP客户端
        sftp = ssh.open_sftp()
        
        logging.info(f"✅ 连接到云服务器成功")
        logging.info(f"📁 本地下载目录: {local_dir}")
        
        downloaded_files = []
        
        for remote_file, local_filename in models_to_download:
            remote_path = f"{remote_base_path}/{remote_file}"
            local_path = os.path.join(local_dir, local_filename)
            
            try:
                # 检查远程文件是否存在
                sftp.stat(remote_path)
                
                # 下载文件
                logging.info(f"📥 正在下载: {remote_file}")
                sftp.get(remote_path, local_path)
                
                # 验证下载
                if os.path.exists(local_path):
                    file_size = os.path.getsize(local_path)
                    logging.info(f"✅ 下载成功: {local_filename} ({file_size:,} bytes)")
                    downloaded_files.append((local_filename, file_size))
                else:
                    logging.error(f"❌ 下载失败: {local_filename}")
                    
            except FileNotFoundError:
                logging.warning(f"⚠️ 远程文件不存在: {remote_file}")
            except Exception as e:
                logging.error(f"❌ 下载 {remote_file} 时出错: {e}")
        
        # 下载训练配置文件
        try:
            config_files = ['args.yaml', 'opt.yaml']
            for config_file in config_files:
                remote_path = f"{remote_base_path}/{config_file}"
                local_path = os.path.join(local_dir, f"training_{config_file}")
                
                try:
                    sftp.get(remote_path, local_path)
                    logging.info(f"✅ 配置文件下载成功: {config_file}")
                    downloaded_files.append((f"training_{config_file}", os.path.getsize(local_path)))
                except FileNotFoundError:
                    logging.warning(f"⚠️ 配置文件不存在: {config_file}")
        except Exception as e:
            logging.warning(f"⚠️ 下载配置文件时出错: {e}")
        
        # 关闭连接
        sftp.close()
        ssh.close()
        
        # 生成下载报告
        if downloaded_files:
            logging.info(f"\n🎉 模型下载完成！")
            logging.info(f"📊 下载统计:")
            logging.info(f"   总文件数: {len(downloaded_files)}")
            
            total_size = sum(size for _, size in downloaded_files)
            logging.info(f"   总大小: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
            
            logging.info(f"\n📁 下载的文件:")
            for filename, size in downloaded_files:
                logging.info(f"   📄 {filename} ({size:,} bytes)")
            
            logging.info(f"\n📍 文件位置: {local_dir}")
            
            # 创建下载报告文件
            report_path = os.path.join(local_dir, 'download_report.txt')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"YOLOv8 多类工业检测模型下载报告\n")
                f.write(f"下载时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"云服务器: {hostname}\n")
                f.write(f"训练项目: v3_multiclass_kading_bracket_doublepin_yolov8s\n\n")
                f.write(f"下载文件列表:\n")
                for filename, size in downloaded_files:
                    f.write(f"  - {filename} ({size:,} bytes)\n")
                f.write(f"\n总文件数: {len(downloaded_files)}\n")
                f.write(f"总大小: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)\n")
            
            logging.info(f"📋 下载报告已保存: {report_path}")
            return True
        else:
            logging.error("❌ 没有成功下载任何文件")
            return False
            
    except Exception as e:
        logging.error(f"❌ 下载过程中出错: {e}")
        return False

if __name__ == "__main__":
    success = download_models()
    if success:
        print("\n✅ 模型下载任务完成！")
    else:
        print("\n❌ 模型下载任务失败！")