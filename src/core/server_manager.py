import paramiko
import os
import time

class ServerManager:
    """服务器管理模块"""
    
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.ssh_client = None
    
    def connect(self):
        """连接服务器"""
        try:
            server_config = self.config_manager.server_config
            
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if server_config['key_file']:
                # 使用密钥文件连接
                self.ssh_client.connect(
                    hostname=server_config['host'],
                    port=server_config['port'],
                    username=server_config['user'],
                    key_filename=server_config['key_file']
                )
            else:
                # 使用密码连接
                self.ssh_client.connect(
                    hostname=server_config['host'],
                    port=server_config['port'],
                    username=server_config['user'],
                    password=server_config['password']
                )
            return True
        except Exception as e:
            print(f"连接服务器失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        try:
            if self.ssh_client:
                self.ssh_client.close()
                self.ssh_client = None
        except Exception as e:
            print(f"断开连接失败: {e}")
    
    def execute_command(self, command):
        """执行命令"""
        try:
            if not self.ssh_client:
                if not self.connect():
                    return False, "未连接服务器"
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=60)
            output = stdout.read().decode('utf-8')
            error = stderr.read().decode('utf-8')
            
            if error:
                return False, error
            return True, output
        except Exception as e:
            return False, str(e)
    
    def upload_file(self, local_path, remote_path):
        """上传文件"""
        try:
            if not self.ssh_client:
                if not self.connect():
                    return False, "未连接服务器"
            
            sftp = self.ssh_client.open_sftp()
            sftp.put(local_path, remote_path)
            sftp.close()
            return True, "上传成功"
        except Exception as e:
            return False, str(e)
    
    def download_file(self, remote_path, local_path):
        """下载文件"""
        try:
            if not self.ssh_client:
                if not self.connect():
                    return False, "未连接服务器"
            
            sftp = self.ssh_client.open_sftp()
            sftp.get(remote_path, local_path)
            sftp.close()
            return True, "下载成功"
        except Exception as e:
            return False, str(e)
    
    def check_server_status(self):
        """检查服务器状态"""
        try:
            success, output = self.execute_command('uname -a')
            if success:
                return True, "服务器正常"
            return False, "服务器异常"
        except Exception as e:
            return False, str(e)
