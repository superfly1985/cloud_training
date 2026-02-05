#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端服务器清理脚本
用于清理云端服务器上的训练模型、数据集和临时文件
避免影响后续训练任务

作者: AI Assistant
创建时间: 2025-01-25
"""

import paramiko
import os
import sys
import logging
from datetime import datetime
import json
from typing import List, Dict, Tuple

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'cloud_cleanup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CloudCleanup:
    """云端清理工具类"""
    
    def __init__(self, config_file='cloud_config.json'):
        # 加载配置文件
        self.config_file = config_file
        self.load_config()
        
        # 云服务器配置
        self.cloud_config = self.config.get('cloud_server', {})
        
        # 安全设置
        self.safety_settings = self.config.get('safety_settings', {})
        
        # 从配置文件获取清理设置
        cleanup_settings = self.config.get('cleanup_settings', {})
        
        # 需要清理的目录列表
        self.cleanup_directories = cleanup_settings.get('directories_to_clean', [
            '/root/yolo_dataset/',           # YOLO数据集目录
            '/root/runs/train/',             # 训练结果目录
            '/root/runs/detect/',            # 检测结果目录
            '/root/runs/val/',               # 验证结果目录
            '/root/ultralytics_cache/',      # Ultralytics缓存目录
            '/tmp/yolo*',                    # 临时YOLO文件
            '/tmp/training*',                # 临时训练文件
        ])
        
        # 需要清理的文件模式
        self.cleanup_file_patterns = cleanup_settings.get('file_patterns_to_clean', [
            '*.pt',                          # PyTorch模型文件
            '*.pth',                         # PyTorch权重文件
            '*.onnx',                        # ONNX模型文件
            '*.engine',                      # TensorRT引擎文件
            '*.jpg',                         # 图片文件
            '*.jpeg',                        # 图片文件
            '*.png',                         # 图片文件
            '*.txt',                         # 标注文件
            '*.yaml',                        # 配置文件
            '*.yml',                         # 配置文件
            '*.log',                         # 日志文件
        ])
        
        # 保护目录 (不会被删除)
        self.protected_directories = cleanup_settings.get('protected_directories', [
            '/root/',
            '/home/',
            '/etc/',
            '/usr/',
            '/var/',
            '/bin/',
            '/sbin/',
            '/lib/',
            '/opt/',
        ])
        
        self.ssh_client = None
        self.cleanup_report = {
            'start_time': None,
            'end_time': None,
            'deleted_files': [],
            'deleted_directories': [],
            'errors': [],
            'total_freed_space': 0
        }
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                logger.info(f"已加载配置文件: {self.config_file}")
            else:
                logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                self.config = {}
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self.config = {}
    
    def validate_config(self) -> bool:
        """验证配置"""
        if not self.cloud_config.get('hostname') or self.cloud_config.get('hostname') == '你的云服务器IP地址':
            logger.error("请先配置云服务器IP地址")
            return False
        
        if not self.cloud_config.get('username'):
            logger.error("请配置用户名")
            return False
        
        if not self.cloud_config.get('password') and not self.cloud_config.get('key_filename'):
            logger.error("请配置密码或密钥文件")
            return False
        
        return True
    
    def connect_to_server(self) -> bool:
        """连接到云服务器"""
        try:
            logger.info("正在连接到云服务器...")
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 连接参数
            connect_params = {
                'hostname': self.cloud_config['hostname'],
                'port': self.cloud_config['port'],
                'username': self.cloud_config['username'],
                'timeout': 30
            }
            
            # 使用密码或密钥认证
            if self.cloud_config.get('key_filename'):
                connect_params['key_filename'] = self.cloud_config['key_filename']
            else:
                connect_params['password'] = self.cloud_config['password']
            
            self.ssh_client.connect(**connect_params)
            logger.info("成功连接到云服务器")
            return True
            
        except Exception as e:
            logger.error(f"连接云服务器失败: {e}")
            return False
    
    def execute_command(self, command: str) -> Tuple[str, str, int]:
        """执行SSH命令"""
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            stdout_data = stdout.read().decode('utf-8')
            stderr_data = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            return stdout_data, stderr_data, exit_code
        except Exception as e:
            logger.error(f"执行命令失败: {command}, 错误: {e}")
            return "", str(e), -1
    
    def get_directory_size(self, directory: str) -> int:
        """获取目录大小（字节）"""
        try:
            command = f"du -sb {directory} 2>/dev/null | cut -f1"
            stdout, stderr, exit_code = self.execute_command(command)
            if exit_code == 0 and stdout.strip():
                return int(stdout.strip())
            return 0
        except:
            return 0
    
    def check_directory_exists(self, directory: str) -> bool:
        """检查目录是否存在"""
        command = f"test -d {directory} && echo 'exists' || echo 'not_exists'"
        stdout, stderr, exit_code = self.execute_command(command)
        return stdout.strip() == 'exists'
    
    def is_protected_directory(self, directory: str) -> bool:
        """检查是否为受保护目录"""
        for protected in self.protected_directories:
            if directory.startswith(protected) and directory != protected:
                # 允许删除受保护目录下的特定子目录
                continue
            elif directory == protected:
                return True
        return False
    
    def list_files_in_directory(self, directory: str) -> List[str]:
        """列出目录中的文件"""
        try:
            command = f"find {directory} -type f 2>/dev/null | head -20"  # 限制显示前20个文件
            stdout, stderr, exit_code = self.execute_command(command)
            if exit_code == 0:
                return [f.strip() for f in stdout.split('\n') if f.strip()]
            return []
        except:
            return []
    
    def cleanup_directory(self, directory: str) -> bool:
        """清理指定目录"""
        try:
            # 检查目录是否存在
            if not self.check_directory_exists(directory):
                logger.info(f"目录不存在，跳过: {directory}")
                return True
            
            # 检查是否为受保护目录
            if self.is_protected_directory(directory):
                logger.warning(f"受保护目录，跳过: {directory}")
                return True
            
            # 获取目录大小
            size_before = self.get_directory_size(directory)
            
            # 列出部分文件用于报告
            files_sample = self.list_files_in_directory(directory)
            
            logger.info(f"正在清理目录: {directory}")
            logger.info(f"目录大小: {size_before / (1024*1024):.2f} MB")
            
            if files_sample:
                logger.info(f"包含文件示例: {files_sample[:5]}")  # 显示前5个文件
            
            # 删除目录
            command = f"rm -rf {directory}"
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code == 0:
                logger.info(f"成功删除目录: {directory}")
                self.cleanup_report['deleted_directories'].append({
                    'path': directory,
                    'size': size_before,
                    'files_sample': files_sample[:10]  # 保存前10个文件名
                })
                self.cleanup_report['total_freed_space'] += size_before
                return True
            else:
                error_msg = f"删除目录失败: {directory}, 错误: {stderr}"
                logger.error(error_msg)
                self.cleanup_report['errors'].append(error_msg)
                return False
                
        except Exception as e:
            error_msg = f"清理目录异常: {directory}, 错误: {e}"
            logger.error(error_msg)
            self.cleanup_report['errors'].append(error_msg)
            return False
    
    def cleanup_files_by_pattern(self, base_dir: str, pattern: str) -> bool:
        """根据文件模式清理文件"""
        try:
            # 查找匹配的文件
            command = f"find {base_dir} -name '{pattern}' -type f 2>/dev/null"
            stdout, stderr, exit_code = self.execute_command(command)
            
            if exit_code != 0:
                return True  # 没有找到文件，认为成功
            
            files = [f.strip() for f in stdout.split('\n') if f.strip()]
            if not files:
                return True
            
            logger.info(f"找到 {len(files)} 个匹配文件: {pattern}")
            
            # 删除文件
            for file_path in files:
                delete_command = f"rm -f '{file_path}'"
                stdout, stderr, exit_code = self.execute_command(delete_command)
                
                if exit_code == 0:
                    self.cleanup_report['deleted_files'].append(file_path)
                else:
                    error_msg = f"删除文件失败: {file_path}, 错误: {stderr}"
                    logger.error(error_msg)
                    self.cleanup_report['errors'].append(error_msg)
            
            return True
            
        except Exception as e:
            error_msg = f"清理文件模式异常: {pattern}, 错误: {e}"
            logger.error(error_msg)
            self.cleanup_report['errors'].append(error_msg)
            return False
    
    def show_cleanup_preview(self) -> bool:
        """显示清理预览"""
        logger.info("=" * 60)
        logger.info("云端清理预览")
        logger.info("=" * 60)
        
        total_size = 0
        total_dirs = 0
        total_files = 0
        
        # 检查目录
        for directory in self.cleanup_directories:
            if self.check_directory_exists(directory):
                size = self.get_directory_size(directory)
                files = self.list_files_in_directory(directory)
                total_size += size
                total_dirs += 1
                total_files += len(files)
                
                logger.info(f"目录: {directory}")
                logger.info(f"  大小: {size / (1024*1024):.2f} MB")
                logger.info(f"  文件数: {len(files)}")
                if files:
                    logger.info(f"  示例文件: {files[:3]}")
                logger.info("")
        
        logger.info(f"总计:")
        logger.info(f"  目录数: {total_dirs}")
        logger.info(f"  文件数: {total_files}")
        logger.info(f"  总大小: {total_size / (1024*1024):.2f} MB")
        logger.info("=" * 60)
        
        return total_dirs > 0 or total_files > 0
    
    def perform_cleanup(self) -> bool:
        """执行清理操作"""
        try:
            self.cleanup_report['start_time'] = datetime.now()
            logger.info("开始执行云端清理...")
            
            # 清理目录
            for directory in self.cleanup_directories:
                self.cleanup_directory(directory)
            
            # 清理根目录下的特定文件模式
            for pattern in self.cleanup_file_patterns:
                self.cleanup_files_by_pattern('/root/', pattern)
            
            self.cleanup_report['end_time'] = datetime.now()
            logger.info("云端清理完成")
            return True
            
        except Exception as e:
            error_msg = f"清理过程异常: {e}"
            logger.error(error_msg)
            self.cleanup_report['errors'].append(error_msg)
            return False
    
    def generate_cleanup_report(self) -> str:
        """生成清理报告"""
        report_file = f"cloud_cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 计算清理时间
        if self.cleanup_report['start_time'] and self.cleanup_report['end_time']:
            duration = self.cleanup_report['end_time'] - self.cleanup_report['start_time']
            self.cleanup_report['duration_seconds'] = duration.total_seconds()
        
        # 保存报告
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.cleanup_report, f, ensure_ascii=False, indent=2, default=str)
        
        # 打印摘要
        logger.info("=" * 60)
        logger.info("清理报告摘要")
        logger.info("=" * 60)
        logger.info(f"删除目录数: {len(self.cleanup_report['deleted_directories'])}")
        logger.info(f"删除文件数: {len(self.cleanup_report['deleted_files'])}")
        logger.info(f"释放空间: {self.cleanup_report['total_freed_space'] / (1024*1024):.2f} MB")
        logger.info(f"错误数: {len(self.cleanup_report['errors'])}")
        logger.info(f"详细报告: {report_file}")
        logger.info("=" * 60)
        
        return report_file
    
    def disconnect(self):
        """断开SSH连接"""
        if self.ssh_client:
            self.ssh_client.close()
            logger.info("已断开云服务器连接")

def main():
    """主函数"""
    print("云端服务器清理工具")
    print("=" * 50)
    
    # 检查配置
    cleanup = CloudCleanup()
    
    # 验证配置
    if not cleanup.validate_config():
        print("配置验证失败，请检查 cloud_config.json 文件:")
        print("1. 设置正确的 hostname (云服务器IP地址)")
        print("2. 设置正确的 username (通常是 root)")
        print("3. 设置 password 或 key_filename")
        print("4. 确认需要清理的目录列表")
        return
    
    try:
        # 连接服务器
        if not cleanup.connect_to_server():
            print("无法连接到云服务器，请检查配置")
            return
        
        # 显示清理预览
        print("\n正在扫描云端文件...")
        has_files = cleanup.show_cleanup_preview()
        
        if not has_files:
            print("没有找到需要清理的文件")
            return
        
        # 确认清理
        print("\n警告: 此操作将永久删除上述文件和目录!")
        confirm = input("确认执行清理? (输入 'YES' 确认): ")
        
        if confirm != 'YES':
            print("清理操作已取消")
            return
        
        # 执行清理
        success = cleanup.perform_cleanup()
        
        # 生成报告
        report_file = cleanup.generate_cleanup_report()
        
        if success:
            print(f"\n清理完成! 详细报告已保存到: {report_file}")
        else:
            print(f"\n清理过程中出现错误，请查看报告: {report_file}")
    
    except KeyboardInterrupt:
        print("\n清理操作被用户中断")
    except Exception as e:
        print(f"\n清理过程中出现异常: {e}")
    finally:
        cleanup.disconnect()

if __name__ == "__main__":
    main()