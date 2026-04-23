import time

class MonitorManager:
    """监控管理模块"""
    
    def __init__(self, config_manager, server_manager):
        self.config_manager = config_manager
        self.server_manager = server_manager
    
    def get_system_status(self):
        """获取系统状态"""
        try:
            # 获取CPU使用率
            cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'"
            cpu_success, cpu_output = self.server_manager.execute_command(cpu_cmd)
            
            # 获取内存使用情况
            mem_cmd = "free -m | awk 'NR==2{print $3, $2}'"
            mem_success, mem_output = self.server_manager.execute_command(mem_cmd)
            
            # 获取GPU使用率
            gpu_cmd = "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader"
            gpu_success, gpu_output = self.server_manager.execute_command(gpu_cmd)
            
            system_status = {
                'cpu_usage': float(cpu_output.strip()) if cpu_success else 0,
                'memory_used': int(mem_output.split()[0]) if mem_success else 0,
                'memory_total': int(mem_output.split()[1]) if mem_success else 0,
                'gpu_usage': [],
                'gpu_mem_used': [],
                'gpu_mem_total': []
            }
            
            if gpu_success and gpu_output:
                for line in gpu_output.strip().split('\n'):
                    if line:
                        parts = line.split(',')
                        if len(parts) >= 3:
                            gpu_usage = parts[0].strip().replace('%', '')
                            mem_used = parts[1].strip().replace('MiB', '')
                            mem_total = parts[2].strip().replace('MiB', '')
                            system_status['gpu_usage'].append(float(gpu_usage))
                            system_status['gpu_mem_used'].append(int(mem_used))
                            system_status['gpu_mem_total'].append(int(mem_total))
            
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
