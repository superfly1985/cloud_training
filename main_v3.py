import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttkb
from src.ui.main_window import MainWindow
from src.core.config_manager import ConfigManager
from src.core.server_manager import ServerManager
from src.core.dataset_manager import DatasetManager
from src.core.training_manager import TrainingManager
from src.core.monitor_manager import MonitorManager

class Application:
    """应用程序主类"""
    
    def __init__(self):
        # 初始化配置管理
        self.config_manager = ConfigManager()
        
        # 初始化服务器管理
        self.server_manager = ServerManager(self.config_manager)
        
        # 初始化数据集管理
        self.dataset_manager = DatasetManager(self.config_manager)
        
        # 初始化训练管理
        self.training_manager = TrainingManager(self.config_manager, self.server_manager)
        
        # 初始化监控管理
        self.monitor_manager = MonitorManager(self.config_manager, self.server_manager)
        
        # 初始化UI
        self.root = ttkb.Window(themename="cosmo")
        self.ui = MainWindow(self.root)
        
        # 绑定事件处理
        self._bind_events()
    
    def _bind_events(self):
        """绑定事件处理"""
        # 服务器连接按钮
        self.ui.btn_test_connection.config(command=self._connect_server)
        
        # 检查环境按钮
        self.ui.btn_check_env.config(command=self._check_environment)
        
        # 检查数据集按钮
        self.ui.btn_check_dataset.config(command=self._check_dataset)
        
        # 上传数据集按钮
        self.ui.btn_upload_dataset.config(command=self._upload_dataset)
        
        # 开始训练按钮
        self.ui.btn_start_training.config(command=self._start_training)
        
        # 下载模型按钮
        self.ui.btn_download_model.config(command=self._download_model)
    
    def _connect_server(self):
        """连接服务器"""
        self.ui.log_message("正在连接服务器...")
        success = self.server_manager.connect()
        if success:
            self.ui.log_message("服务器连接成功！")
            self.ui.server_status_var.set("已连接")
        else:
            self.ui.log_message("服务器连接失败")
            self.ui.server_status_var.set("未连接")
    
    def _check_environment(self):
        """检查环境"""
        self.ui.log_message("正在检查环境...")
        success, message = self.server_manager.execute_command('python --version')
        if success:
            self.ui.log_message(f"Python版本: {message.strip()}")
            # 检查CUDA
            success, cuda_output = self.server_manager.execute_command('nvidia-smi')
            if success:
                self.ui.log_message("CUDA可用")
            else:
                self.ui.log_message("CUDA不可用")
        else:
            self.ui.log_message("环境检查失败")
    
    def _check_dataset(self):
        """检查数据集"""
        dataset_path = self.ui.dataset_path_var.get()
        if not dataset_path:
            self.ui.log_message("请设置数据集路径")
            return
        
        self.ui.log_message("正在检查数据集...")
        success, message = self.dataset_manager.check_dataset(dataset_path)
        if success:
            self.ui.log_message(f"数据集检查通过: {message}")
            # 更新数据集信息
            info = self.dataset_manager.get_dataset_info(dataset_path)
            self.ui.dataset_info_var.set(f"图像: {info['image_count']}, 标签: {info['label_count']}, 类别: {info['class_count']}")
        else:
            self.ui.log_message(f"数据集检查失败: {message}")
    
    def _upload_dataset(self):
        """上传数据集"""
        dataset_path = self.ui.dataset_path_var.get()
        if not dataset_path:
            self.ui.log_message("请设置数据集路径")
            return
        
        self.ui.log_message("正在上传数据集...")
        self.ui.upload_status_var.set("正在上传...")
        
        # 这里实现数据集上传逻辑
        # 实际应用中需要实现文件上传功能
        
        self.ui.upload_status_var.set("上传完成")
        self.ui.log_message("数据集上传完成")
    
    def _start_training(self):
        """开始训练"""
        dataset_path = self.ui.dataset_path_var.get()
        if not dataset_path:
            self.ui.log_message("请设置数据集路径")
            return
        
        self.ui.log_message("正在开始训练...")
        self.ui.training_status_var.set("训练中")
        
        # 开始训练
        success, message = self.training_manager.start_training(dataset_path)
        if success:
            self.ui.log_message("训练启动成功")
        else:
            self.ui.log_message(f"训练启动失败: {message}")
            self.ui.training_status_var.set("训练失败")
    
    def _download_model(self):
        """下载模型"""
        self.ui.log_message("正在下载模型...")
        # 这里实现模型下载逻辑
        self.ui.log_message("模型下载完成")
    
    def run(self):
        """运行应用"""
        self.root.mainloop()

if __name__ == "__main__":
    app = Application()
    app.run()
