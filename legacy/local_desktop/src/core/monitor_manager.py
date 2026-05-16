import time

class MonitorManager:
    """监控管理模块"""
    
    def __init__(self, config_manager, server_manager):
        self.config_manager = config_manager
        self.server_manager = server_manager
    
    def get_system_status(self):
        """获取系统状态"""
        try:
            # 获取CPU使用率 (取 1 秒平均值更准确，但为了响应速度使用 top)
            cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'"
            cpu_success, cpu_output = self.server_manager.execute_command(cpu_cmd)
            
            # 获取内存使用情况 (MB -> GB)
            mem_cmd = "free -m | grep '^Mem:' | awk '{print $3, $2}'"
            mem_success, mem_output = self.server_manager.execute_command(mem_cmd)
            
            # 获取磁盘使用情况 (根目录)
            disk_cmd = "df -h / | tail -1 | awk '{print $3, $2, $5}'"
            disk_success, disk_output = self.server_manager.execute_command(disk_cmd)
            
            # 获取GPU使用率
            gpu_cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,name --format=csv,noheader,nounits"
            gpu_success, gpu_output = self.server_manager.execute_command(gpu_cmd)
            
            system_status = {
                'cpu_usage': float(cpu_output.strip()) if cpu_success and cpu_output.strip() else 0,
                'memory_used': round(int(mem_output.split()[0])/1024, 2) if mem_success and mem_output.strip() else 0,
                'memory_total': round(int(mem_output.split()[1])/1024, 2) if mem_success and mem_output.strip() else 0,
                'disk_used': disk_output.split()[0] if disk_success and disk_output.strip() else "0",
                'disk_total': disk_output.split()[1] if disk_success and disk_output.strip() else "0",
                'disk_percent': disk_output.split()[2].replace('%', '') if disk_success and disk_output.strip() else "0",
                'gpu_usage': [],
                'gpu_mem_used': [],
                'gpu_mem_total': [],
                'gpu_names': []
            }
            
            if gpu_success and gpu_output:
                for line in gpu_output.strip().split('\n'):
                    if line:
                        parts = line.split(',')
                        if len(parts) >= 4:
                            gpu_usage = parts[0].strip()
                            mem_used = parts[1].strip()
                            mem_total = parts[2].strip()
                            gpu_name = parts[3].strip()
                            system_status['gpu_usage'].append(float(gpu_usage))
                            system_status['gpu_mem_used'].append(round(int(mem_used)/1024, 2))
                            system_status['gpu_mem_total'].append(round(int(mem_total)/1024, 2))
                            system_status['gpu_names'].append(gpu_name)
            
            return system_status
        except Exception as e:
            return {'error': str(e)}
    
    def get_training_logs(self, lines=100):
        """获取训练日志"""
        try:
            log_path = f"{self.config_manager.server_config['remote_path']}/runs/train/exp/results.csv"
            command = f"tail -n {lines} {log_path}"
            success, output = self.server_manager.execute_command(command)
            
            if success:
                return output
            return "暂无日志"
        except Exception as e:
            return f"获取日志失败: {e}"
    
    def monitor_training(self, callback=None):
        """监控训练过程"""
        try:
            while True:
                # 获取系统状态
                system_status = self.get_system_status()
                
                # 获取训练状态
                training_status = "训练中"
                
                # 调用回调函数
                if callback:
                    callback(system_status, training_status)
                
                # 等待10秒
                time.sleep(10)
        except Exception as e:
            print(f"监控失败: {e}")
