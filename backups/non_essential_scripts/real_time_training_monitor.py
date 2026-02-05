#!/usr/bin/env python3
"""
实时训练监控脚本
实时显示云服务器GPU训练进度和详情
"""

import paramiko
import time
import os
import sys
import json
from datetime import datetime
import threading
import queue

# 颜色代码
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# 云服务器配置
CLOUD_CONFIG = {
    'hostname': '152.136.245.138',
    'username': 'root',
    'password': 'Vonzeus01',
    'port': 22
}

class TrainingMonitor:
    def __init__(self):
        self.ssh = None
        self.running = True
        self.last_epoch = 0
        self.start_time = datetime.now()
        self.gpu_history = []
        self.loss_history = []
        
    def clear_screen(self):
        """清屏"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def print_header(self):
        """打印标题"""
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}🚀 云服务器GPU训练实时监控系统{Colors.END}")
        print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
        print(f"{Colors.YELLOW}服务器: {CLOUD_CONFIG['hostname']}{Colors.END}")
        print(f"{Colors.YELLOW}监控开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}{Colors.END}")
        print(f"{Colors.YELLOW}运行时长: {str(datetime.now() - self.start_time).split('.')[0]}{Colors.END}")
        print()
    
    def connect_ssh(self):
        """建立SSH连接"""
        try:
            self.ssh = paramiko.SSHClient()
            self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh.connect(
                hostname=CLOUD_CONFIG['hostname'],
                username=CLOUD_CONFIG['username'],
                password=CLOUD_CONFIG['password'],
                port=CLOUD_CONFIG['port'],
                timeout=10
            )
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ SSH连接失败: {str(e)}{Colors.END}")
            return False
    
    def get_gpu_status(self):
        """获取GPU状态"""
        try:
            stdin, stdout, stderr = self.ssh.exec_command(
                "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw --format=csv,noheader,nounits"
            )
            gpu_data = stdout.read().decode().strip()
            
            if gpu_data:
                parts = gpu_data.split(',')
                gpu_util = int(parts[0].strip())
                memory_used = int(parts[1].strip())
                memory_total = int(parts[2].strip())
                temperature = int(parts[3].strip())
                power_draw = float(parts[4].strip()) if len(parts) > 4 else 0
                
                memory_percent = round(memory_used / memory_total * 100, 1)
                
                # 保存历史数据
                self.gpu_history.append({
                    'time': datetime.now(),
                    'util': gpu_util,
                    'memory_percent': memory_percent,
                    'temperature': temperature
                })
                
                # 只保留最近100个数据点
                if len(self.gpu_history) > 100:
                    self.gpu_history.pop(0)
                
                return {
                    'utilization': gpu_util,
                    'memory_used': memory_used,
                    'memory_total': memory_total,
                    'memory_percent': memory_percent,
                    'temperature': temperature,
                    'power_draw': power_draw
                }
        except Exception as e:
            print(f"{Colors.RED}获取GPU状态失败: {str(e)}{Colors.END}")
        return None
    
    def get_training_processes(self):
        """获取训练进程信息"""
        try:
            stdin, stdout, stderr = self.ssh.exec_command("ps aux | grep python | grep -v grep")
            processes = stdout.read().decode().strip()
            
            training_processes = []
            if processes:
                for line in processes.split('\n'):
                    if any(keyword in line.lower() for keyword in ['train', 'gpu_training', 'yolo']):
                        parts = line.split()
                        if len(parts) >= 11:
                            training_processes.append({
                                'pid': parts[1],
                                'cpu': parts[2],
                                'memory': parts[3],
                                'command': ' '.join(parts[10:])
                            })
            
            return training_processes
        except Exception as e:
            print(f"{Colors.RED}获取进程信息失败: {str(e)}{Colors.END}")
        return []
    
    def get_training_logs(self, lines=10):
        """获取训练日志"""
        try:
            # 查找最新的训练日志文件
            stdin, stdout, stderr = self.ssh.exec_command(
                "find /root -name '*.log' -type f -exec ls -lt {} + | head -3"
            )
            log_files = stdout.read().decode().strip()
            
            if log_files:
                # 获取最新的日志文件
                latest_log = log_files.split('\n')[0].split()[-1]
                
                stdin, stdout, stderr = self.ssh.exec_command(f"tail -{lines} {latest_log}")
                log_content = stdout.read().decode().strip()
                
                # 解析训练进度
                epoch_info = self.parse_training_progress(log_content)
                
                return {
                    'file': latest_log,
                    'content': log_content,
                    'epoch_info': epoch_info
                }
        except Exception as e:
            print(f"{Colors.RED}获取训练日志失败: {str(e)}{Colors.END}")
        return None
    
    def parse_training_progress(self, log_content):
        """解析训练进度"""
        epoch_info = {}
        
        for line in log_content.split('\n'):
            if 'Epoch' in line and 'Loss' in line:
                try:
                    # 解析 "Epoch 650, Loss: 2.2996, GPU内存: 35.8MB" 格式
                    parts = line.split(',')
                    
                    # 提取Epoch
                    epoch_part = [p for p in parts if 'Epoch' in p][0]
                    epoch = int(epoch_part.split('Epoch')[1].strip())
                    
                    # 提取Loss
                    loss_part = [p for p in parts if 'Loss' in p][0]
                    loss = float(loss_part.split(':')[1].strip())
                    
                    # 提取GPU内存
                    memory_part = [p for p in parts if 'GPU内存' in p or 'GPU' in p]
                    gpu_memory = memory_part[0].split(':')[1].strip() if memory_part else "N/A"
                    
                    epoch_info = {
                        'epoch': epoch,
                        'loss': loss,
                        'gpu_memory': gpu_memory,
                        'time': datetime.now()
                    }
                    
                    # 更新历史数据
                    if epoch > self.last_epoch:
                        self.last_epoch = epoch
                        self.loss_history.append({'epoch': epoch, 'loss': loss})
                        
                        # 只保留最近50个数据点
                        if len(self.loss_history) > 50:
                            self.loss_history.pop(0)
                    
                except Exception as e:
                    continue
        
        return epoch_info
    
    def print_gpu_status(self, gpu_status):
        """打印GPU状态"""
        if not gpu_status:
            print(f"{Colors.RED}❌ 无法获取GPU状态{Colors.END}")
            return
        
        print(f"{Colors.BOLD}{Colors.GREEN}🔥 GPU状态{Colors.END}")
        print(f"{Colors.CYAN}├─ 使用率: {Colors.END}", end="")
        
        util = gpu_status['utilization']
        if util > 80:
            color = Colors.GREEN
        elif util > 50:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        print(f"{color}{util}%{Colors.END}")
        
        print(f"{Colors.CYAN}├─ 显存: {Colors.END}", end="")
        memory_bar = self.create_progress_bar(gpu_status['memory_percent'], 30)
        print(f"{memory_bar} {gpu_status['memory_used']}MB/{gpu_status['memory_total']}MB ({gpu_status['memory_percent']}%)")
        
        print(f"{Colors.CYAN}├─ 温度: {Colors.END}", end="")
        temp = gpu_status['temperature']
        if temp > 80:
            temp_color = Colors.RED
        elif temp > 60:
            temp_color = Colors.YELLOW
        else:
            temp_color = Colors.GREEN
        print(f"{temp_color}{temp}°C{Colors.END}")
        
        if gpu_status['power_draw'] > 0:
            print(f"{Colors.CYAN}└─ 功耗: {Colors.END}{gpu_status['power_draw']:.1f}W")
        else:
            print(f"{Colors.CYAN}└─ 功耗: {Colors.END}N/A")
        
        print()
    
    def create_progress_bar(self, percentage, width=30):
        """创建进度条"""
        filled = int(width * percentage / 100)
        bar = '█' * filled + '░' * (width - filled)
        
        if percentage > 80:
            color = Colors.GREEN
        elif percentage > 50:
            color = Colors.YELLOW
        else:
            color = Colors.RED
        
        return f"{color}[{bar}]{Colors.END}"
    
    def print_training_status(self, processes, logs):
        """打印训练状态"""
        print(f"{Colors.BOLD}{Colors.BLUE}🚂 训练状态{Colors.END}")
        
        if processes:
            # 只显示进程数量，不显示详细列表
            main_process = None
            total_cpu = 0
            total_memory = 0
            
            for proc in processes:
                total_cpu += float(proc['cpu'])
                total_memory += float(proc['memory'])
                if 'train_' in proc['command'] and float(proc['cpu']) > 50:
                    main_process = proc
            
            print(f"{Colors.CYAN}├─ 运行进程: {len(processes)}个{Colors.END}")
            if main_process:
                print(f"{Colors.CYAN}├─ 主训练进程: PID:{main_process['pid']} CPU:{main_process['cpu']}%{Colors.END}")
            print(f"{Colors.CYAN}├─ 总CPU使用: {total_cpu:.1f}%{Colors.END}")
            print(f"{Colors.CYAN}├─ 总内存使用: {total_memory:.1f}%{Colors.END}")
        else:
            print(f"{Colors.RED}├─ ❌ 没有发现训练进程{Colors.END}")
        
        if logs and logs['epoch_info']:
            epoch_info = logs['epoch_info']
            print(f"{Colors.CYAN}├─ 当前轮次: {Colors.END}{Colors.GREEN}{epoch_info['epoch']}{Colors.END}")
            print(f"{Colors.CYAN}├─ 当前损失: {Colors.END}{Colors.GREEN}{epoch_info['loss']:.4f}{Colors.END}")
            print(f"{Colors.CYAN}└─ GPU内存: {Colors.END}{Colors.GREEN}{epoch_info['gpu_memory']}{Colors.END}")
        else:
            print(f"{Colors.CYAN}└─ 训练进度: {Colors.END}{Colors.RED}无法获取{Colors.END}")
        
        print()
    
    def print_loss_trend(self):
        """打印损失趋势"""
        if len(self.loss_history) < 2:
            return
        
        print(f"{Colors.BOLD}{Colors.MAGENTA}📈 损失趋势 (最近10轮){Colors.END}")
        
        recent_losses = self.loss_history[-10:]
        
        for i, data in enumerate(recent_losses):
            symbol = "├─" if i < len(recent_losses) - 1 else "└─"
            
            # 计算趋势
            if i > 0:
                prev_loss = recent_losses[i-1]['loss']
                current_loss = data['loss']
                if current_loss < prev_loss:
                    trend = f"{Colors.GREEN}↓{Colors.END}"
                elif current_loss > prev_loss:
                    trend = f"{Colors.RED}↑{Colors.END}"
                else:
                    trend = f"{Colors.YELLOW}→{Colors.END}"
            else:
                trend = ""
            
            print(f"{Colors.CYAN}{symbol} Epoch {data['epoch']}: {Colors.END}{data['loss']:.4f} {trend}")
        
        print()
    
    def print_recent_logs(self, logs):
        """打印最近的日志"""
        if not logs or not logs['content']:
            return
        
        print(f"{Colors.BOLD}{Colors.WHITE}📋 最新训练日志{Colors.END}")
        print(f"{Colors.CYAN}文件: {logs['file']}{Colors.END}")
        print(f"{Colors.CYAN}{'─' * 60}{Colors.END}")
        
        log_lines = logs['content'].split('\n')[-5:]  # 只显示最后5行
        
        for line in log_lines:
            if line.strip():
                # 高亮关键信息
                if 'Epoch' in line:
                    print(f"{Colors.GREEN}{line}{Colors.END}")
                elif 'Error' in line or 'error' in line:
                    print(f"{Colors.RED}{line}{Colors.END}")
                elif 'Warning' in line or 'warning' in line:
                    print(f"{Colors.YELLOW}{line}{Colors.END}")
                else:
                    print(f"{Colors.WHITE}{line}{Colors.END}")
        
        print()
    
    def print_statistics(self):
        """打印统计信息"""
        if not self.gpu_history:
            return
        
        print(f"{Colors.BOLD}{Colors.YELLOW}📊 统计信息{Colors.END}")
        
        # GPU使用率统计
        gpu_utils = [data['util'] for data in self.gpu_history]
        avg_util = sum(gpu_utils) / len(gpu_utils)
        max_util = max(gpu_utils)
        min_util = min(gpu_utils)
        
        print(f"{Colors.CYAN}├─ GPU使用率: 平均{avg_util:.1f}% 最高{max_util}% 最低{min_util}%{Colors.END}")
        
        # 温度统计
        temps = [data['temperature'] for data in self.gpu_history]
        avg_temp = sum(temps) / len(temps)
        max_temp = max(temps)
        
        print(f"{Colors.CYAN}├─ GPU温度: 平均{avg_temp:.1f}°C 最高{max_temp}°C{Colors.END}")
        
        # 训练进度
        if self.loss_history:
            print(f"{Colors.CYAN}├─ 训练轮次: {self.last_epoch}{Colors.END}")
            latest_loss = self.loss_history[-1]['loss']
            print(f"{Colors.CYAN}└─ 最新损失: {latest_loss:.4f}{Colors.END}")
        else:
            print(f"{Colors.CYAN}└─ 训练进度: 暂无数据{Colors.END}")
        
        print()
    
    def monitor_loop(self):
        """主监控循环"""
        while self.running:
            try:
                # 清屏并打印标题
                self.clear_screen()
                self.print_header()
                
                # 检查SSH连接
                if not self.ssh or self.ssh.get_transport() is None:
                    print(f"{Colors.YELLOW}🔄 重新连接SSH...{Colors.END}")
                    if not self.connect_ssh():
                        print(f"{Colors.RED}❌ 连接失败，5秒后重试...{Colors.END}")
                        time.sleep(5)
                        continue
                    print(f"{Colors.GREEN}✅ SSH连接成功{Colors.END}")
                    print()
                
                # 获取各种状态信息
                gpu_status = self.get_gpu_status()
                processes = self.get_training_processes()
                logs = self.get_training_logs()
                
                # 显示信息
                self.print_gpu_status(gpu_status)
                self.print_training_status(processes, logs)
                self.print_loss_trend()
                self.print_recent_logs(logs)
                self.print_statistics()
                
                # 显示刷新信息
                print(f"{Colors.CYAN}🔄 自动刷新中... (按 Ctrl+C 退出) 下次刷新: 5秒后{Colors.END}")
                
                # 等待5秒
                time.sleep(5)
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}用户中断监控{Colors.END}")
                self.running = False
                break
            except Exception as e:
                print(f"{Colors.RED}监控出错: {str(e)}{Colors.END}")
                time.sleep(5)
    
    def start(self):
        """启动监控"""
        print(f"{Colors.BOLD}{Colors.GREEN}🚀 启动实时训练监控...{Colors.END}")
        
        if not self.connect_ssh():
            print(f"{Colors.RED}❌ 无法连接到服务器{Colors.END}")
            return
        
        try:
            self.monitor_loop()
        finally:
            if self.ssh:
                self.ssh.close()
            print(f"{Colors.GREEN}✅ 监控已停止{Colors.END}")

def main():
    """主函数"""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("=" * 60)
    print("🚀 云服务器GPU训练实时监控系统")
    print("=" * 60)
    print(f"{Colors.END}")
    print(f"{Colors.YELLOW}功能特性:{Colors.END}")
    print(f"{Colors.GREEN}✅ 实时GPU状态监控{Colors.END}")
    print(f"{Colors.GREEN}✅ 训练进程状态显示{Colors.END}")
    print(f"{Colors.GREEN}✅ 训练日志实时更新{Colors.END}")
    print(f"{Colors.GREEN}✅ 损失趋势分析{Colors.END}")
    print(f"{Colors.GREEN}✅ 彩色界面显示{Colors.END}")
    print()
    
    monitor = TrainingMonitor()
    monitor.start()

if __name__ == "__main__":
    main()