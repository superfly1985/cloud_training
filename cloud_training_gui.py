#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端训练脚本优化可视化GUI界面
包含服务器配置、数据集配置、训练监控等核心功能模块
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import sys
import threading
import subprocess
import paramiko
from pathlib import Path
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from scp import SCPClient
import hashlib
import logging
import yaml
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.animation as animation
from collections import deque
import numpy as np

class CloudTrainingGUI:
    def __init__(self, root):
        self.root = root
        self.app_version = "v2.2.0"
        self.root.title(f"云端训练脚本优化管理平台 {self.app_version}")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # 配置文件路径
        self.config_file = "cloud_training_config.json"
        
        # 初始化配置
        self.server_config = {
            'hostname': '',
            'port': 22,
            'username': '',
            'password': '',
            'key_file': ''
        }
        
        self.dataset_config = {
            'local_path': '',
            'remote_path': '/root/yolo_dataset',
            'dataset_name': '',
            'classes': [],
            'num_classes': 0
        }
        
        self.training_config = {
            'epochs': 300,
            'batch_size': 20,
            'learning_rate': 0.01,
            'image_size': 1024,
            'base_model': 'yolov8s.pt'
        }

        # 状态变量
        self.is_connected = False
        self.is_training = False
        self.is_monitoring = False
        self.upload_progress = 0
        
        # SSH客户端
        self.ssh_client = None
        
        # 监控数据存储
        self.max_data_points = 50  # 最多保存50个数据点
        self.gpu_utilization_data = deque(maxlen=self.max_data_points)
        self.gpu_memory_data = deque(maxlen=self.max_data_points)
        self.cpu_data = deque(maxlen=self.max_data_points)
        self.memory_data = deque(maxlen=self.max_data_points)
        self.time_data = deque(maxlen=self.max_data_points)
        
        # 监控图表相关
        self.monitoring_figures = {}
        self.monitoring_canvases = {}
        self.monitoring_animations = {}
        self.monitoring_thread = None
        self.monitor_refresh_ms = 1000
        self._monitor_ui_pending = False
        self._last_monitor_update = 0.0
        self._last_monitor_log = 0.0
        self.debug_monitor = False
        self.training_log_file = None
        self.training_run_dir = None
        self._last_progress_update = 0.0
        self._run_dir_logged = False
        
        self.config = {
            'server': self.server_config,
            'dataset': self.dataset_config,
            'training': self.training_config,
            'upload': {
                'max_workers': 8,
                'retry_times': 3
            }
        }
        self.load_config()
        
        # 设置UI
        self.setup_ui()
        
        # 设置日志
        self.setup_logging()

    def _set_upload_progress(self, value):
        try:
            v = max(0.0, min(100.0, float(value)))
            if hasattr(self, 'upload_progress_var'):
                self.upload_progress_var.set(v)
            if hasattr(self, 'upload_progress_bar'):
                self.upload_progress_bar['value'] = v
                self.upload_progress_bar.update_idletasks()
        except Exception:
            pass

    def setup_logging(self):
        """设置日志系统"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('cloud_training_gui.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # 创建选项卡
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 服务器配置选项卡
        self.setup_server_tab()
        
        # 数据集配置选项卡
        self.setup_dataset_tab()
        
        # 训练监控选项卡
        self.setup_training_tab()
        
        # 状态栏
        self.setup_status_bar(main_frame)
    
    def setup_server_tab(self):
        """设置服务器配置选项卡"""
        server_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(server_frame, text="服务器配置")
        
        # 服务器信息框架
        server_info_frame = ttk.LabelFrame(server_frame, text="服务器连接信息", padding="10")
        server_info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # IP地址
        ttk.Label(server_info_frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.hostname_var = tk.StringVar(value=self.server_config['hostname'])
        ttk.Entry(server_info_frame, textvariable=self.hostname_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 端口
        ttk.Label(server_info_frame, text="端口:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value=str(self.server_config['port']))
        ttk.Entry(server_info_frame, textvariable=self.port_var, width=30).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 用户名
        ttk.Label(server_info_frame, text="用户名:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.username_var = tk.StringVar(value=self.server_config['username'])
        ttk.Entry(server_info_frame, textvariable=self.username_var, width=30).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 密码
        ttk.Label(server_info_frame, text="密码:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.password_var = tk.StringVar(value=self.server_config['password'])
        ttk.Entry(server_info_frame, textvariable=self.password_var, show="*", width=30).grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 密钥文件（可选）
        ttk.Label(server_info_frame, text="密钥文件:").grid(row=4, column=0, sticky=tk.W, pady=2)
        key_frame = ttk.Frame(server_info_frame)
        key_frame.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        self.key_file_var = tk.StringVar(value=self.server_config['key_file'])
        ttk.Entry(key_frame, textvariable=self.key_file_var, width=25).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(key_frame, text="选择", command=self.select_key_file).grid(row=0, column=1, padx=(5, 0))
        
        key_frame.columnconfigure(0, weight=1)
        server_info_frame.columnconfigure(1, weight=1)
        
        # 操作按钮框架
        button_frame = ttk.Frame(server_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="测试连接", command=self.test_connection).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="保存配置", command=self.save_server_config).grid(row=0, column=1, padx=(0, 10))
        ttk.Button(button_frame, text="获取服务器详细信息", command=self.get_server_info).grid(row=0, column=2, padx=(0, 10))
        
        # 连接状态显示
        self.connection_status_var = tk.StringVar(value="未连接")
        self.connection_status_label = ttk.Label(server_frame, textvariable=self.connection_status_var, foreground="red")
        self.connection_status_label.grid(row=2, column=0, columnspan=2, pady=10)
    
    def setup_dataset_tab(self):
        """设置数据集配置选项卡"""
        dataset_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(dataset_frame, text="数据集配置")
        
        # 配置主框架的网格权重
        dataset_frame.columnconfigure(0, weight=2)  # 左侧数据集配置区域
        dataset_frame.columnconfigure(1, weight=1)  # 右侧训练参数区域
        dataset_frame.rowconfigure(3, weight=1)     # 让日志区域可以扩展
        
        # 左侧：数据集配置区域
        left_frame = ttk.Frame(dataset_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_frame.columnconfigure(0, weight=1)
        
        # 数据集路径框架
        path_frame = ttk.LabelFrame(left_frame, text="数据集路径配置", padding="10")
        path_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 本地数据集路径
        ttk.Label(path_frame, text="本地数据集:").grid(row=0, column=0, sticky=tk.W, pady=2)
        local_path_frame = ttk.Frame(path_frame)
        local_path_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        self.local_path_var = tk.StringVar(value=self.dataset_config['local_path'])
        ttk.Entry(local_path_frame, textvariable=self.local_path_var, width=40).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(local_path_frame, text="选择", command=self.select_dataset_path).grid(row=0, column=1, padx=(5, 0))
        
        local_path_frame.columnconfigure(0, weight=1)
        
        # 远程数据集路径
        ttk.Label(path_frame, text="远程路径:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.remote_path_var = tk.StringVar(value=self.dataset_config['remote_path'])
        ttk.Entry(path_frame, textvariable=self.remote_path_var, width=40).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        path_frame.columnconfigure(1, weight=1)
        
        # 数据集信息框架
        info_frame = ttk.LabelFrame(left_frame, text="数据集信息", padding="10")
        info_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 数据集名称
        ttk.Label(info_frame, text="数据集名称:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.dataset_name_var = tk.StringVar(value=self.dataset_config['dataset_name'])
        ttk.Entry(info_frame, textvariable=self.dataset_name_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 类别数量
        ttk.Label(info_frame, text="类别数量:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.num_classes_var = tk.StringVar(value=str(self.dataset_config['num_classes']))
        ttk.Entry(info_frame, textvariable=self.num_classes_var, width=30, state="readonly").grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        info_frame.columnconfigure(1, weight=1)
        
        # 类别列表
        ttk.Label(info_frame, text="类别列表:").grid(row=2, column=0, sticky=(tk.W, tk.N), pady=2)
        self.classes_text = scrolledtext.ScrolledText(info_frame, height=5, width=40)
        self.classes_text.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # dataset.yaml配置框架
        yaml_frame = ttk.LabelFrame(left_frame, text="Dataset.yaml配置", padding="10")
        yaml_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # yaml配置显示
        ttk.Label(yaml_frame, text="当前配置:").grid(row=0, column=0, sticky=(tk.W, tk.N), pady=2)
        self.yaml_config_text = scrolledtext.ScrolledText(yaml_frame, height=6, width=50)
        self.yaml_config_text.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 路径问题检测结果
        ttk.Label(yaml_frame, text="路径检测:").grid(row=1, column=0, sticky=(tk.W, tk.N), pady=2)
        self.path_issues_text = scrolledtext.ScrolledText(yaml_frame, height=4, width=50)
        self.path_issues_text.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        yaml_frame.columnconfigure(1, weight=1)
        
        # 操作按钮框架
        dataset_button_frame = ttk.Frame(left_frame)
        dataset_button_frame.grid(row=3, column=0, pady=10)
        
        ttk.Button(dataset_button_frame, text="分析数据集", command=self.analyze_dataset).grid(row=0, column=0, padx=(0, 5))
        ttk.Button(dataset_button_frame, text="检查并修正", command=self.check_and_fix_dataset, style="Accent.TButton").grid(row=0, column=1, padx=(0, 5))
        ttk.Button(dataset_button_frame, text="上传数据集", command=self.upload_dataset).grid(row=0, column=2, padx=(0, 5))
        ttk.Button(dataset_button_frame, text="生成训练脚本", command=self.generate_training_script).grid(row=1, column=0, padx=(0, 5), pady=(5, 0))
        ttk.Button(dataset_button_frame, text="清理云端数据", command=self.clean_cloud_data).grid(row=1, column=1, padx=(0, 5), pady=(5, 0))
        
        # 右侧：训练参数配置区域
        right_frame = ttk.Frame(dataset_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        
        # 训练参数框架
        params_frame = ttk.LabelFrame(right_frame, text="训练参数配置", padding="10")
        params_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 训练轮数
        ttk.Label(params_frame, text="训练轮数:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.epochs_var = tk.StringVar(value=str(self.training_config['epochs']))
        ttk.Entry(params_frame, textvariable=self.epochs_var, width=20).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 批次大小
        ttk.Label(params_frame, text="批次大小:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.batch_size_var = tk.StringVar(value=str(self.training_config['batch_size']))
        ttk.Entry(params_frame, textvariable=self.batch_size_var, width=20).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 学习率
        ttk.Label(params_frame, text="学习率:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.learning_rate_var = tk.StringVar(value=str(self.training_config['learning_rate']))
        ttk.Entry(params_frame, textvariable=self.learning_rate_var, width=20).grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 图像大小
        ttk.Label(params_frame, text="图像大小:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.image_size_var = tk.StringVar(value=str(self.training_config['image_size']))
        ttk.Entry(params_frame, textvariable=self.image_size_var, width=20).grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 基础模型
        ttk.Label(params_frame, text="基础模型:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.base_model_var = tk.StringVar(value=self.training_config['base_model'])
        model_combo = ttk.Combobox(params_frame, textvariable=self.base_model_var, width=18)
        # 实际可用的YOLO模型版本选项
        model_combo['values'] = (
            # YOLOv8系列
            'yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt',
            # YOLOv9系列
            'yolov9c.pt', 'yolov9e.pt',
            # YOLOv10系列
            'yolov10n.pt', 'yolov10s.pt', 'yolov10m.pt', 'yolov10b.pt', 'yolov10l.pt', 'yolov10x.pt',
            # YOLOv11系列
            'yolov11n.pt', 'yolov11s.pt', 'yolov11m.pt', 'yolov11l.pt', 'yolov11x.pt'
        )
        model_combo.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        params_frame.columnconfigure(1, weight=1)
        
        # 训练控制框架
        control_frame = ttk.LabelFrame(right_frame, text="训练控制", padding="10")
        control_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(control_frame, text="下载模型", command=self.download_models).grid(row=0, column=0, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="删除模型", command=self.delete_models).grid(row=1, column=0, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="本地安装包", command=self.local_package_install, style="Accent.TButton").grid(row=2, column=0, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="上传设置", command=self.open_upload_settings).grid(row=3, column=0, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="开始训练", command=self.start_training).grid(row=4, column=0, pady=2, sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="停止训练", command=self.stop_training).grid(row=5, column=0, pady=2, sticky=(tk.W, tk.E))
        
        control_frame.columnconfigure(0, weight=1)

        # 训练状态显示
        status_frame = ttk.LabelFrame(right_frame, text="训练状态", padding="10")
        status_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        self.training_status_var = tk.StringVar(value="未开始")
        status_label = ttk.Label(status_frame, textvariable=self.training_status_var, font=("Arial", 10, "bold"))
        status_label.grid(row=0, column=0, pady=5)

        # 底部：上传进度和状态（跨越两列）
        progress_frame = ttk.Frame(dataset_frame)
        progress_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        progress_frame.columnconfigure(0, weight=1)
        # 上传进度
        self.upload_progress_var = tk.DoubleVar()
        self.upload_progress_bar = ttk.Progressbar(progress_frame, variable=self.upload_progress_var, maximum=100, mode='determinate', length=400)
        self.upload_progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        self.upload_status_var = tk.StringVar(value="准备就绪")
        ttk.Label(progress_frame, textvariable=self.upload_status_var).grid(row=1, column=0)

    def open_upload_settings(self):
        """打开上传参数设置窗口"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("上传参数设置")
        settings_window.geometry("400x250")
        settings_window.transient(self.root)
        settings_window.grab_set()
        settings_window.resizable(False, False)

        # 读取当前配置
        cfg = self.load_config()
        upload_cfg = cfg.get("upload", {})
        max_workers = upload_cfg.get("max_workers", 8)
        retry_times = upload_cfg.get("retry_times", 3)

        # 主框架
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill='both', expand=True)

        # 标题
        ttk.Label(main_frame, text="上传参数设置", font=("Arial", 14, "bold")).pack(pady=(0, 15))

        # 并发线程数
        ttk.Label(main_frame, text="并发线程数:").pack(anchor='w')
        workers_var = tk.IntVar(value=max_workers)
        workers_spin = ttk.Spinbox(main_frame, from_=1, to=32, textvariable=workers_var, width=10)
        workers_spin.pack(anchor='w', pady=(0, 10))

        # 重试次数
        ttk.Label(main_frame, text="重试次数:").pack(anchor='w')
        retry_var = tk.IntVar(value=retry_times)
        retry_spin = ttk.Spinbox(main_frame, from_=0, to=10, textvariable=retry_var, width=10)
        retry_spin.pack(anchor='w', pady=(0, 20))

        # 按钮区
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill='x')

        def save_and_close():
            # 更新配置
            cfg["upload"] = {
                "max_workers": workers_var.get(),
                "retry_times": retry_var.get()
            }
            self.save_config(cfg)
            messagebox.showinfo("保存成功", "上传参数已保存")
            settings_window.destroy()

        def cancel():
            settings_window.destroy()

        ttk.Button(btn_frame, text="保存", command=save_and_close).pack(side='right', padx=(5, 0))
        ttk.Button(btn_frame, text="取消", command=cancel).pack(side='right')
    
    def setup_training_tab(self):
        """设置训练监控选项卡"""
        training_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(training_frame, text="训练监控")
        
        # 配置主框架的网格权重
        training_frame.columnconfigure(0, weight=1)
        training_frame.columnconfigure(1, weight=1)
        training_frame.rowconfigure(1, weight=1)
        training_frame.rowconfigure(2, weight=1)
        
        # 顶部控制区域
        top_frame = ttk.Frame(training_frame)
        top_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)
        
        # 训练控制框架
        control_frame = ttk.LabelFrame(top_frame, text="训练控制", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # 控制按钮布局为2x2
        ttk.Button(control_frame, text="下载模型", command=self.download_models).grid(row=0, column=0, pady=2, padx=(0, 5), sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="删除模型", command=self.delete_models).grid(row=0, column=1, pady=2, padx=(5, 0), sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="开始监控", command=self.start_monitoring).grid(row=1, column=0, pady=2, padx=(0, 5), sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="停止监控", command=self.stop_monitoring).grid(row=1, column=1, pady=2, padx=(5, 0), sticky=(tk.W, tk.E))
        
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        
        # 训练状态框架
        status_frame = ttk.LabelFrame(top_frame, text="训练状态", padding="10")
        status_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        self.training_status_var = tk.StringVar(value="未开始")
        status_label = ttk.Label(status_frame, textvariable=self.training_status_var, font=("Arial", 12, "bold"))
        status_label.grid(row=0, column=0, pady=5)
        
        # 训练进度条
        self.training_progress_var = tk.DoubleVar()
        self.training_progress_bar = ttk.Progressbar(status_frame, variable=self.training_progress_var, maximum=100)
        self.training_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 当前epoch显示
        self.current_epoch_var = tk.StringVar(value="Epoch: 0/0")
        ttk.Label(status_frame, textvariable=self.current_epoch_var).grid(row=2, column=0, pady=2)
        
        status_frame.columnconfigure(0, weight=1)
        
        # 中部：主要内容区域（左侧监控，右侧日志）
        main_content_frame = ttk.Frame(training_frame)
        main_content_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # 配置主要内容区域网格：左侧监控占30%，右侧日志占70%
        main_content_frame.columnconfigure(0, weight=3, minsize=300)  # 左侧监控区域
        main_content_frame.columnconfigure(1, weight=7, minsize=700)  # 右侧日志区域
        main_content_frame.rowconfigure(0, weight=1)
        
        # 左侧：系统监控区域（竖向排列）
        monitor_frame = ttk.LabelFrame(main_content_frame, text="系统监控", padding="5")
        monitor_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # 配置监控区域网格：4行1列，竖向排列
        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.rowconfigure(0, weight=1)
        monitor_frame.rowconfigure(1, weight=1)
        monitor_frame.rowconfigure(2, weight=1)
        monitor_frame.rowconfigure(3, weight=1)
        
        # GPU利用率监控
        self.gpu_utilization_frame = ttk.LabelFrame(monitor_frame, text="GPU利用率", padding="3")
        self.gpu_utilization_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3))
        
        # GPU显存监控
        self.gpu_memory_frame = ttk.LabelFrame(monitor_frame, text="GPU显存使用率", padding="3")
        self.gpu_memory_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(3, 3))
        
        # CPU使用率监控
        self.cpu_frame = ttk.LabelFrame(monitor_frame, text="CPU使用率", padding="3")
        self.cpu_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(3, 3))
        
        # 内存使用率监控
        self.memory_frame = ttk.LabelFrame(monitor_frame, text="内存使用率", padding="3")
        self.memory_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(3, 0))
        
        # 初始化监控图表占位符
        self.init_monitoring_charts()
        
        # 右侧：日志显示框架
        log_frame = ttk.LabelFrame(main_content_frame, text="训练日志", padding="10")
        log_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=25, width=60)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
    
    def setup_status_bar(self, parent):
        """设置状态栏"""
        status_frame = ttk.Frame(parent)
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(status_frame, textvariable=self.status_var).grid(row=0, column=0, sticky=tk.W)
        
        # 时间显示
        self.time_var = tk.StringVar()
        ttk.Label(status_frame, textvariable=self.time_var).grid(row=0, column=1, sticky=tk.E)
        
        status_frame.columnconfigure(0, weight=1)
        
        # 更新时间
        self.update_time()
    
    def update_time(self):
        """更新时间显示"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_var.set(current_time)
        self.root.after(1000, self.update_time)
    
    def load_config(self):
        try:
            cfg = None
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = {}
            self.server_config.update(cfg.get('server', {}))
            self.dataset_config.update(cfg.get('dataset', {}))
            self.training_config.update(cfg.get('training', {}))
            upload_cfg = cfg.get('upload', {})
            self.config = {
                'server': self.server_config,
                'dataset': self.dataset_config,
                'training': self.training_config,
                'upload': {
                    'max_workers': upload_cfg.get('max_workers', 8),
                    'retry_times': upload_cfg.get('retry_times', 3)
                }
            }
            return {
                'server': dict(self.server_config),
                'dataset': dict(self.dataset_config),
                'training': dict(self.training_config),
                'upload': dict(self.config['upload'])
            }
        except Exception as e:
            self.log_message(f"加载配置失败: {e}")
            return {
                'server': dict(self.server_config),
                'dataset': dict(self.dataset_config),
                'training': dict(self.training_config),
                'upload': dict(self.config['upload'])
            }
    
    def save_config(self, cfg=None):
        try:
            if isinstance(cfg, dict):
                if 'server' in cfg:
                    self.server_config.update(cfg['server'])
                if 'dataset' in cfg:
                    self.dataset_config.update(cfg['dataset'])
                if 'training' in cfg:
                    self.training_config.update(cfg['training'])
                if 'upload' in cfg:
                    self.config['upload'] = {
                        'max_workers': cfg['upload'].get('max_workers', self.config['upload']['max_workers']),
                        'retry_times': cfg['upload'].get('retry_times', self.config['upload']['retry_times'])
                    }
            out = {
                'server': self.server_config,
                'dataset': self.dataset_config,
                'training': self.training_config,
                'upload': self.config['upload']
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            self.log_message("配置已保存")
        except Exception as e:
            self.log_message(f"保存配置失败: {e}")
    
    def select_key_file(self):
        """选择密钥文件"""
        filename = filedialog.askopenfilename(
            title="选择SSH密钥文件",
            filetypes=[("PEM files", "*.pem"), ("All files", "*.*")]
        )
        if filename:
            self.key_file_var.set(filename)
    
    def select_dataset_path(self):
        """选择数据集路径"""
        path = filedialog.askdirectory(title="选择数据集目录")
        if path:
            self.local_path_var.set(path)
            self.dataset_config['local_path'] = path
            # 自动分析数据集
            self.analyze_dataset()
    
    def test_connection(self):
        """测试服务器连接"""
        def test_thread():
            error_msg = None
            ssh = None
            try:
                self.update_server_config()
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # 连接参数
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                # 优化连接超时时间
                ssh.connect(**connect_params, timeout=15)
                
                # 测试命令
                stdin, stdout, stderr = ssh.exec_command('echo "Connection test successful"')
                result = stdout.read().decode().strip()
                
                # 🔧 关键修复：将成功的SSH连接赋值给self.ssh_client
                if self.ssh_client:
                    try:
                        self.ssh_client.close()
                    except:
                        pass
                self.ssh_client = ssh  # 不要关闭ssh，而是将其赋值给self.ssh_client
                
                self.root.after(0, lambda: self.connection_test_success())
                
            except paramiko.AuthenticationException as e:
                error_msg = f"认证失败: 用户名或密码错误 - {str(e)}"
                if ssh:
                    ssh.close()
                self.root.after(0, lambda msg=error_msg: self.connection_test_failed(msg))
            except paramiko.SSHException as e:
                error_msg = f"SSH连接错误: {str(e)}"
                if ssh:
                    ssh.close()
                self.root.after(0, lambda msg=error_msg: self.connection_test_failed(msg))
            except Exception as e:
                error_msg = f"连接失败: {str(e)}"
                if ssh:
                    ssh.close()
                self.root.after(0, lambda msg=error_msg: self.connection_test_failed(msg))
        
        threading.Thread(target=test_thread, daemon=True).start()
        self.connection_status_var.set("连接测试中...")
        self.connection_status_label.config(foreground="orange")
    
    def connection_test_success(self):
        """连接测试成功"""
        self.is_connected = True
        self.connection_status_var.set("连接成功")
        self.connection_status_label.config(foreground="green")
        self.log_message("服务器连接测试成功")
    
    def connection_test_failed(self, error):
        """连接测试失败"""
        self.is_connected = False
        self.connection_status_var.set(f"连接失败: {error}")
        self.connection_status_label.config(foreground="red")
        self.log_message(f"服务器连接测试失败: {error}")
    
    def update_server_config(self):
        """更新服务器配置"""
        self.server_config['hostname'] = self.hostname_var.get()
        self.server_config['port'] = int(self.port_var.get())
        self.server_config['username'] = self.username_var.get()
        self.server_config['password'] = self.password_var.get()
        self.server_config['key_file'] = self.key_file_var.get()
    
    def save_server_config(self):
        """保存服务器配置"""
        self.update_server_config()
        self.save_config()
        messagebox.showinfo("成功", "服务器配置已保存")
    
    def get_server_info(self):
        """获取服务器详细信息"""
        try:
            self.update_server_config()
            
            # 创建进度窗口
            progress_window = tk.Toplevel(self.root)
            progress_window.title("获取服务器信息")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            # 居中显示
            progress_window.geometry("+%d+%d" % (
                self.root.winfo_rootx() + 50,
                self.root.winfo_rooty() + 50
            ))
            
            # 进度标签
            progress_label = ttk.Label(progress_window, text="正在连接服务器...")
            progress_label.pack(pady=20)
            
            # 进度条
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill='x')
            progress_bar.start()
            
            # 取消按钮
            cancel_button = ttk.Button(progress_window, text="取消", 
                                     command=progress_window.destroy)
            cancel_button.pack(pady=10)
            
            # 在新线程中执行信息获取
            def get_info_thread():
                try:
                    server_info = self.collect_server_information()
                    progress_window.after(0, lambda: self.show_server_info_window(server_info, progress_window))
                except Exception as e:
                    progress_window.after(0, lambda: self.handle_server_info_error(str(e), progress_window))
            
            import threading
            thread = threading.Thread(target=get_info_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            messagebox.showerror("错误", f"获取服务器信息失败: {str(e)}")
    
    def collect_server_information(self):
        """收集服务器详细信息"""
        import paramiko
        
        # 建立SSH连接
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_params = {
            'hostname': self.server_config['hostname'],
            'port': self.server_config['port'],
            'username': self.server_config['username']
        }
        
        if self.server_config['key_file']:
            connect_params['key_filename'] = self.server_config['key_file']
        else:
            connect_params['password'] = self.server_config['password']
        
        ssh.connect(**connect_params, timeout=15)
        
        server_info = {
            'basic_info': {},
            'directory_structure': {},
            'environment_analysis': {},
            'system_resources': {}
        }
        
        try:
            # 1. 基本系统信息
            commands = {
                'hostname': 'hostname',
                'os_info': 'cat /etc/os-release',
                'kernel': 'uname -r',
                'uptime': 'uptime',
                'users': 'who',
                'disk_usage': 'df -h',
                'memory_info': 'free -h',
                'cpu_info': 'lscpu | head -20'
            }
            
            for key, cmd in commands.items():
                stdin, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode('utf-8', errors='ignore').strip()
                error = stderr.read().decode('utf-8', errors='ignore').strip()
                server_info['basic_info'][key] = output if output else error
            
            # 2. 目录结构分析 - 只显示root目录及其子目录
            # 获取根目录结构
            stdin, stdout, stderr = ssh.exec_command('ls -la /')
            server_info['directory_structure']['/ (根目录)'] = stdout.read().decode('utf-8', errors='ignore')
            
            # 获取root目录下的所有子目录详细结构
            stdin, stdout, stderr = ssh.exec_command('find /root -maxdepth 3 -type d 2>/dev/null | head -50')
            root_subdirs = stdout.read().decode('utf-8', errors='ignore').strip().split('\n')
            
            for subdir in root_subdirs:
                if subdir and subdir != '/root':
                    # 获取每个子目录的详细信息
                    stdin, stdout, stderr = ssh.exec_command(f'ls -la "{subdir}" 2>/dev/null || echo "Directory not accessible"')
                    dir_content = stdout.read().decode('utf-8', errors='ignore').strip()
                    if dir_content and dir_content != "Directory not accessible":
                        server_info['directory_structure'][subdir] = dir_content
            
            # 特别获取root主目录的详细信息
            stdin, stdout, stderr = ssh.exec_command('ls -la /root/')
            server_info['directory_structure']['/root (主目录)'] = stdout.read().decode('utf-8', errors='ignore')
            
            # 3. 运行环境检测
            env_commands = {
                'python_version': 'python3 --version 2>&1',
                'python_packages': 'pip3 list 2>/dev/null | head -50',
                'conda_info': 'conda info 2>/dev/null || echo "Conda not installed"',
                'conda_envs': 'conda env list 2>/dev/null || echo "Conda not installed"',
                'docker_version': 'docker --version 2>/dev/null || echo "Docker not installed"',
                'docker_images': 'docker images 2>/dev/null || echo "Docker not available"',
                'nvidia_smi': 'nvidia-smi 2>/dev/null || echo "NVIDIA drivers not installed"',
                'cuda_version': 'nvcc --version 2>/dev/null || echo "CUDA not installed"',
                'git_version': 'git --version 2>/dev/null || echo "Git not installed"',
                'node_version': 'node --version 2>/dev/null || echo "Node.js not installed"',
                'java_version': 'java -version 2>&1 || echo "Java not installed"'
            }
            
            for key, cmd in env_commands.items():
                stdin, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode('utf-8', errors='ignore').strip()
                server_info['environment_analysis'][key] = output
            
            # 4. 系统资源信息
            resource_commands = {
                'processes': 'ps aux | head -20',
                'network_connections': 'netstat -tuln 2>/dev/null | head -20 || ss -tuln | head -20',
                'mounted_filesystems': 'mount | grep -E "^/"',
                'environment_variables': 'env | sort | head -30',
                'crontab': 'crontab -l 2>/dev/null || echo "No crontab entries"',
                'services': 'systemctl list-units --type=service --state=running 2>/dev/null | head -20 || service --status-all 2>/dev/null | head -20'
            }
            
            for key, cmd in resource_commands.items():
                stdin, stdout, stderr = ssh.exec_command(cmd)
                output = stdout.read().decode('utf-8', errors='ignore').strip()
                server_info['system_resources'][key] = output
            
        finally:
            ssh.close()
        
        return server_info
    
    def show_server_info_window(self, server_info, progress_window):
        """显示服务器信息窗口"""
        progress_window.destroy()
        
        # 创建信息显示窗口
        info_window = tk.Toplevel(self.root)
        info_window.title("服务器详细信息")
        info_window.geometry("1000x700")
        info_window.transient(self.root)
        
        # 创建笔记本控件用于分类显示信息
        notebook = ttk.Notebook(info_window)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # 1. 基本信息标签页
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="基本信息")
        
        basic_text = tk.Text(basic_frame, wrap='word', font=('Consolas', 10))
        basic_scrollbar = ttk.Scrollbar(basic_frame, orient='vertical', command=basic_text.yview)
        basic_text.configure(yscrollcommand=basic_scrollbar.set)
        
        basic_content = "=== 服务器基本信息 ===\n\n"
        for key, value in server_info['basic_info'].items():
            basic_content += f"{key.upper()}:\n{value}\n\n"
        
        basic_text.insert('1.0', basic_content)
        basic_text.config(state='disabled')
        
        basic_text.pack(side='left', fill='both', expand=True)
        basic_scrollbar.pack(side='right', fill='y')
        
        # 2. 目录结构标签页
        dir_frame = ttk.Frame(notebook)
        notebook.add(dir_frame, text="目录结构")
        
        dir_text = tk.Text(dir_frame, wrap='word', font=('Consolas', 10))
        dir_scrollbar = ttk.Scrollbar(dir_frame, orient='vertical', command=dir_text.yview)
        dir_text.configure(yscrollcommand=dir_scrollbar.set)
        
        dir_content = "=== 目录结构信息 ===\n\n"
        for path, listing in server_info['directory_structure'].items():
            dir_content += f"目录: {path}\n"
            dir_content += "-" * 50 + "\n"
            dir_content += f"{listing}\n\n"
        
        dir_text.insert('1.0', dir_content)
        dir_text.config(state='disabled')
        
        dir_text.pack(side='left', fill='both', expand=True)
        dir_scrollbar.pack(side='right', fill='y')
        
        # 3. 环境分析标签页
        env_frame = ttk.Frame(notebook)
        notebook.add(env_frame, text="运行环境")
        
        env_text = tk.Text(env_frame, wrap='word', font=('Consolas', 10))
        env_scrollbar = ttk.Scrollbar(env_frame, orient='vertical', command=env_text.yview)
        env_text.configure(yscrollcommand=env_scrollbar.set)
        
        env_content = "=== 运行环境分析 ===\n\n"
        
        # 分析环境缺失情况
        missing_components = []
        critical_components = {
            'python_version': 'Python',
            'nvidia_smi': 'NVIDIA驱动',
            'cuda_version': 'CUDA',
            'docker_version': 'Docker',
            'git_version': 'Git'
        }
        
        for key, name in critical_components.items():
            if key in server_info['environment_analysis']:
                value = server_info['environment_analysis'][key]
                if 'not installed' in value or 'not available' in value:
                    missing_components.append(name)
        
        if missing_components:
            env_content += "⚠️ 缺失的关键组件:\n"
            for component in missing_components:
                env_content += f"  - {component}\n"
            env_content += "\n"
        else:
            env_content += "✅ 所有关键组件都已安装\n\n"
        
        env_content += "详细环境信息:\n"
        env_content += "=" * 50 + "\n\n"
        
        for key, value in server_info['environment_analysis'].items():
            env_content += f"{key.upper().replace('_', ' ')}:\n{value}\n\n"
        
        env_text.insert('1.0', env_content)
        env_text.config(state='disabled')
        
        env_text.pack(side='left', fill='both', expand=True)
        env_scrollbar.pack(side='right', fill='y')
        
        # 4. 系统资源标签页
        resource_frame = ttk.Frame(notebook)
        notebook.add(resource_frame, text="系统资源")
        
        resource_text = tk.Text(resource_frame, wrap='word', font=('Consolas', 10))
        resource_scrollbar = ttk.Scrollbar(resource_frame, orient='vertical', command=resource_text.yview)
        resource_text.configure(yscrollcommand=resource_scrollbar.set)
        
        resource_content = "=== 系统资源信息 ===\n\n"
        for key, value in server_info['system_resources'].items():
            resource_content += f"{key.upper().replace('_', ' ')}:\n{value}\n\n"
        
        resource_text.insert('1.0', resource_content)
        resource_text.config(state='disabled')
        
        resource_text.pack(side='left', fill='both', expand=True)
        resource_scrollbar.pack(side='right', fill='y')
        
        # 添加功能按钮
        button_frame = ttk.Frame(info_window)
        button_frame.pack(fill='x', padx=10, pady=5)
        
        # 安装缺失环境按钮
        ttk.Button(button_frame, text="安装缺失环境", 
                  command=lambda: self.install_missing_environment(server_info)).pack(side='left', padx=5)
        
        # 删除文件按钮
        ttk.Button(button_frame, text="删除文件/文件夹", 
                  command=lambda: self.delete_server_files()).pack(side='left', padx=5)
        
        # 导出报告按钮
        ttk.Button(button_frame, text="导出报告", 
                  command=lambda: self.export_server_report(server_info)).pack(side='right', padx=5)
        ttk.Button(button_frame, text="关闭", 
                  command=info_window.destroy).pack(side='right', padx=5)
    
    def handle_server_info_error(self, error_msg, progress_window):
        """处理服务器信息获取错误"""
        progress_window.destroy()
        messagebox.showerror("错误", f"获取服务器信息失败:\n{error_msg}")
    
    def export_server_report(self, server_info):
        """导出服务器信息报告"""
        try:
            from tkinter import filedialog
            import json
            from datetime import datetime
            
            # 选择保存位置
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt"), ("JSON文件", "*.json"), ("所有文件", "*.*")],
                title="保存服务器信息报告"
            )
            
            if filename:
                if filename.endswith('.json'):
                    # 保存为JSON格式
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(server_info, f, ensure_ascii=False, indent=2)
                else:
                    # 保存为文本格式
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"服务器信息报告\n")
                        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        f.write("=" * 60 + "\n\n")
                        
                        # 基本信息
                        f.write("基本信息:\n")
                        f.write("-" * 30 + "\n")
                        for key, value in server_info['basic_info'].items():
                            f.write(f"{key}: {value}\n")
                        f.write("\n")
                        
                        # 目录结构
                        f.write("目录结构:\n")
                        f.write("-" * 30 + "\n")
                        for path, listing in server_info['directory_structure'].items():
                            f.write(f"\n{path}:\n{listing}\n")
                        f.write("\n")
                        
                        # 环境分析
                        f.write("运行环境:\n")
                        f.write("-" * 30 + "\n")
                        for key, value in server_info['environment_analysis'].items():
                            f.write(f"{key}: {value}\n")
                        f.write("\n")
                        
                        # 系统资源
                        f.write("系统资源:\n")
                        f.write("-" * 30 + "\n")
                        for key, value in server_info['system_resources'].items():
                            f.write(f"{key}: {value}\n")
                
                messagebox.showinfo("成功", f"服务器信息报告已保存到: {filename}")
                
        except Exception as e:
            messagebox.showerror("错误", f"导出报告失败: {str(e)}")
    
    def install_missing_environment(self, server_info):
        """安装缺失的环境组件"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        # 定义所有可能的组件及其详细信息
        all_components = {
            'python_version': {
                'name': 'Python 3',
                'necessity': '必需',
                'description': 'Python运行环境，AI训练的基础',
                'install_cmd': 'apt update && apt install -y python3 python3-pip',
                'category': 'core',
                'size_mb': 50,
                'install_time': '2-3分钟'
            },
            'nvidia_smi': {
                'name': 'NVIDIA驱动',
                'necessity': '必需',
                'description': 'GPU驱动程序，GPU训练必须',
                'install_cmd': 'apt update && apt install -y nvidia-driver-470',
                'category': 'gpu',
                'size_mb': 300,
                'install_time': '5-8分钟'
            },
            'cuda_version': {
                'name': 'CUDA工具包',
                'necessity': '必需',
                'description': 'NVIDIA CUDA开发工具包，深度学习GPU加速',
                'install_cmd': 'wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/cuda-ubuntu2004.pin && mv cuda-ubuntu2004.pin /etc/apt/preferences.d/cuda-repository-pin-600 && apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/7fa2af80.pub && add-apt-repository "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/ /" && apt update && apt install -y cuda',
                'category': 'gpu',
                'size_mb': 2500,
                'install_time': '10-15分钟'
            },
            'docker_version': {
                'name': 'Docker',
                'necessity': '可选',
                'description': '容器化平台，用于环境隔离（容器环境中通常不需要）',
                'install_cmd': 'apt update && apt install -y docker.io && systemctl start docker && systemctl enable docker',
                'category': 'optional',
                'size_mb': 200,
                'install_time': '3-5分钟'
            },
            'git_version': {
                'name': 'Git',
                'necessity': '推荐',
                'description': '版本控制工具，用于代码管理',
                'install_cmd': 'apt update && apt install -y git',
                'category': 'tools',
                'size_mb': 30,
                'install_time': '1-2分钟'
            },
            'python_packages': {
                'name': 'Python AI包',
                'necessity': '必需',
                'description': 'PyTorch, Ultralytics等AI训练必需包',
                'install_cmd': 'pip3 install torch torchvision torchaudio ultralytics opencv-python pillow matplotlib tensorboard',
                'category': 'core',
                'size_mb': 1500,
                'install_time': '8-12分钟'
            }
        }
        
        # 分析缺失的组件
        missing_components = []
        
        # 检查系统组件
        for key, component_info in all_components.items():
            if key in server_info['environment_analysis']:
                value = server_info['environment_analysis'][key]
                if 'not installed' in value or 'not available' in value:
                    missing_components.append(key)
            elif key == 'python_packages':
                # 特殊检查Python包
                packages_info = server_info['environment_analysis'].get('python_packages', '')
                if 'torch' not in packages_info or 'ultralytics' not in packages_info:
                    missing_components.append(key)
        
        if not missing_components:
            messagebox.showinfo("信息", "所有关键组件都已安装，无需安装")
            return
        
        # 创建改进的安装选择窗口
        self.create_enhanced_install_window(missing_components, all_components)
    
    def create_enhanced_install_window(self, missing_components, all_components):
        """创建增强的组件选择安装窗口"""
        install_window = tk.Toplevel(self.root)
        install_window.title("环境组件安装选择")
        install_window.geometry("900x700")
        install_window.transient(self.root)
        install_window.grab_set()
        
        # 主框架
        main_frame = ttk.Frame(install_window)
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        # 标题
        title_label = ttk.Label(main_frame, text="选择要安装的环境组件", 
                               font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 说明文字
        info_label = ttk.Label(main_frame, 
                              text="请根据您的需求选择要安装的组件。必需组件对于AI训练是必须的，推荐组件能提升开发体验。",
                              font=("Arial", 10), foreground="gray")
        info_label.pack(pady=(0, 15))
        
        # 创建滚动框架
        canvas = tk.Canvas(main_frame, height=400)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # 组件选择变量
        install_vars = {}
        
        # 按类别分组显示组件
        categories = {
            'core': ('核心组件', '#e74c3c'),
            'gpu': ('GPU组件', '#f39c12'),
            'tools': ('开发工具', '#3498db'),
            'optional': ('可选组件', '#95a5a6')
        }
        
        for category, (category_name, color) in categories.items():
            category_components = [comp for comp in missing_components 
                                 if all_components[comp]['category'] == category]
            
            if not category_components:
                continue
                
            # 类别标题
            category_frame = ttk.LabelFrame(scrollable_frame, text=category_name, padding=10)
            category_frame.pack(fill='x', pady=(10, 5), padx=10)
            
            for comp_key in category_components:
                comp_info = all_components[comp_key]
                
                # 组件框架
                comp_frame = ttk.Frame(category_frame)
                comp_frame.pack(fill='x', pady=8)
                
                # 左侧：复选框和基本信息
                left_frame = ttk.Frame(comp_frame)
                left_frame.pack(side='left', fill='x', expand=True)
                
                # 复选框和组件名
                checkbox_frame = ttk.Frame(left_frame)
                checkbox_frame.pack(fill='x')
                
                var = tk.BooleanVar(value=(comp_info['necessity'] == '必需'))
                install_vars[comp_key] = (var, comp_info['install_cmd'])
                
                cb = ttk.Checkbutton(checkbox_frame, text=comp_info['name'], variable=var)
                cb.pack(side='left')
                
                # 必要性标签
                necessity_color = {
                    '必需': '#e74c3c',
                    '推荐': '#f39c12', 
                    '可选': '#95a5a6'
                }.get(comp_info['necessity'], '#95a5a6')
                
                necessity_label = tk.Label(checkbox_frame, text=f"[{comp_info['necessity']}]",
                                         font=("Arial", 9, "bold"), 
                                         fg=necessity_color)
                necessity_label.pack(side='left', padx=(10, 0))
                
                # 描述
                desc_label = ttk.Label(left_frame, text=comp_info['description'],
                                     font=("Arial", 9), foreground="gray")
                desc_label.pack(anchor='w', pady=(2, 0))
                
                # 右侧：安装信息
                right_frame = ttk.Frame(comp_frame)
                right_frame.pack(side='right')
                
                # 大小和时间信息
                size_text = f"大小: ~{comp_info['size_mb']}MB"
                time_text = f"时间: {comp_info['install_time']}"
                
                size_label = ttk.Label(right_frame, text=size_text, 
                                     font=("Arial", 8), foreground="blue")
                size_label.pack(anchor='e')
                
                time_label = ttk.Label(right_frame, text=time_text,
                                     font=("Arial", 8), foreground="green")
                time_label.pack(anchor='e')
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 底部信息和按钮
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill='x', pady=(20, 0))
        
        # 统计信息
        def update_stats():
            selected_count = sum(1 for var, _ in install_vars.values() if var.get())
            total_size = sum(all_components[comp]['size_mb'] 
                           for comp, (var, _) in install_vars.items() if var.get())
            stats_text = f"已选择 {selected_count} 个组件，预计下载 ~{total_size}MB"
            stats_label.config(text=stats_text)
        
        stats_label = ttk.Label(bottom_frame, text="", font=("Arial", 10))
        stats_label.pack(pady=(0, 10))
        
        # 为所有复选框绑定更新事件
        for var, _ in install_vars.values():
            var.trace('w', lambda *args: update_stats())
        
        update_stats()  # 初始更新
        
        # 按钮框架
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill='x')
        
        # 快速选择按钮
        quick_frame = ttk.Frame(button_frame)
        quick_frame.pack(side='left')
        
        def select_required():
            for comp_key, (var, _) in install_vars.items():
                var.set(all_components[comp_key]['necessity'] == '必需')
            update_stats()
        
        def select_all():
            for var, _ in install_vars.values():
                var.set(True)
            update_stats()
        
        def select_none():
            for var, _ in install_vars.values():
                var.set(False)
            update_stats()
        
        ttk.Button(quick_frame, text="仅必需", command=select_required).pack(side='left', padx=2)
        ttk.Button(quick_frame, text="全选", command=select_all).pack(side='left', padx=2)
        ttk.Button(quick_frame, text="全不选", command=select_none).pack(side='left', padx=2)
        
        # 主要按钮
        main_button_frame = ttk.Frame(button_frame)
        main_button_frame.pack(side='right')
        
        def start_installation():
            selected_components = []
            for comp_key, (var, install_cmd) in install_vars.items():
                if var.get():
                    selected_components.append((all_components[comp_key]['name'], install_cmd))
            
            if not selected_components:
                messagebox.showwarning("警告", "请至少选择一个组件进行安装")
                return
            
            install_window.destroy()
            self.execute_installation(selected_components)
        
        ttk.Button(main_button_frame, text="开始安装", command=start_installation).pack(side='right', padx=5)
        ttk.Button(main_button_frame, text="取消", command=install_window.destroy).pack(side='right', padx=5)
    
    def execute_installation(self, components):
        """执行安装过程"""
        # 创建安装进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("安装进度")
        progress_window.geometry("600x400")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # 进度显示
        tk.Label(progress_window, text="正在安装环境组件...", font=("Arial", 12)).pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill='x', padx=20, pady=10)
        
        # 日志显示
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        log_text = tk.Text(log_frame, wrap='word', font=('Consolas', 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        
        log_text.pack(side='left', fill='both', expand=True)
        log_scrollbar.pack(side='right', fill='y')
        
        def installation_thread():
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                total_components = len(components)
                for i, (name, install_cmd) in enumerate(components):
                    # 更新进度
                    progress = (i / total_components) * 100
                    self.root.after(0, lambda p=progress: progress_var.set(p))
                    
                    # 添加日志
                    self.root.after(0, lambda n=name: log_text.insert(tk.END, f"\n正在安装 {n}...\n"))
                    self.root.after(0, lambda: log_text.see(tk.END))
                    
                    # 执行安装命令
                    stdin, stdout, stderr = ssh.exec_command(install_cmd)
                    
                    # 实时显示输出
                    while True:
                        line = stdout.readline()
                        if not line:
                            break
                        self.root.after(0, lambda l=line: log_text.insert(tk.END, l))
                        self.root.after(0, lambda: log_text.see(tk.END))
                    
                    # 检查错误
                    error_output = stderr.read().decode('utf-8', errors='ignore')
                    if error_output:
                        self.root.after(0, lambda e=error_output: log_text.insert(tk.END, f"错误: {e}\n"))
                    
                    self.root.after(0, lambda n=name: log_text.insert(tk.END, f"{n} 安装完成\n"))
                
                # 完成安装
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: log_text.insert(tk.END, "\n所有组件安装完成！\n"))
                self.root.after(0, lambda: messagebox.showinfo("成功", "环境安装完成"))
                
                ssh.close()
                
            except Exception as e:
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n安装失败: {str(e)}\n"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"安装失败: {str(e)}"))
        
        import threading
        threading.Thread(target=installation_thread, daemon=True).start()
        
        # 关闭按钮
        ttk.Button(progress_window, text="关闭", command=progress_window.destroy).pack(pady=10)
    
    def delete_server_files(self):
        """删除服务器文件和文件夹"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        # 创建文件删除窗口
        delete_window = tk.Toplevel(self.root)
        delete_window.title("删除服务器文件")
        delete_window.geometry("700x500")
        delete_window.transient(self.root)
        delete_window.grab_set()
        
        # 标题
        title_label = ttk.Label(delete_window, text="选择要删除的文件和文件夹", font=("Arial", 12, "bold"))
        title_label.pack(pady=10)
        
        # 警告信息
        warning_label = ttk.Label(delete_window, text="⚠️ 警告：删除操作不可恢复，请谨慎选择！", 
                                 font=("Arial", 10), foreground="red")
        warning_label.pack(pady=5)
        
        # 文件浏览框架
        browse_frame = ttk.Frame(delete_window)
        browse_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 导航栏框架
        nav_frame = ttk.Frame(browse_frame)
        nav_frame.pack(fill='x', pady=(0, 10))
        
        # 返回上级目录按钮
        ttk.Button(nav_frame, text="← 上级", command=lambda: navigate_to_parent()).pack(side='left', padx=(0, 5))
        
        # 刷新按钮
        ttk.Button(nav_frame, text="刷新", command=lambda: load_directory(current_path_var.get())).pack(side='right')
        
        # 面包屑导航栏框架
        breadcrumb_frame = ttk.Frame(browse_frame)
        breadcrumb_frame.pack(fill='x', pady=(0, 10))
        
        # 当前路径显示
        current_path_var = tk.StringVar(value="/root")
        
        def create_breadcrumb():
            """创建面包屑导航"""
            # 清空现有的面包屑
            for widget in breadcrumb_frame.winfo_children():
                widget.destroy()
            
            current_path = current_path_var.get()
            path_parts = current_path.split('/')
            
            # 添加根目录
            if current_path != "/root":
                root_btn = ttk.Button(breadcrumb_frame, text="🏠 root", 
                                    command=lambda: load_directory("/root"))
                root_btn.pack(side='left')
                
                if len(path_parts) > 2 or (len(path_parts) == 2 and path_parts[1] != "root"):
                    ttk.Label(breadcrumb_frame, text=" > ").pack(side='left')
            
            # 添加路径中的每个部分
            accumulated_path = ""
            for i, part in enumerate(path_parts):
                if part == "" or part == "root":
                    continue
                
                accumulated_path += "/" + part
                if accumulated_path.startswith("//"):
                    accumulated_path = accumulated_path[1:]
                
                if i < len(path_parts) - 1:
                    # 中间路径，可点击
                    path_btn = ttk.Button(breadcrumb_frame, text=part,
                                        command=lambda p=accumulated_path: load_directory(p))
                    path_btn.pack(side='left')
                    ttk.Label(breadcrumb_frame, text=" > ").pack(side='left')
                else:
                    # 当前目录，不可点击
                    ttk.Label(breadcrumb_frame, text=part, font=("Arial", 9, "bold")).pack(side='left')
        
        # 文件列表框架
        list_frame = ttk.Frame(browse_frame)
        list_frame.pack(fill='both', expand=True)
        
        # 创建Treeview显示文件（添加复选框列）
        columns = ('selected', 'type', 'size', 'permissions', 'date')
        file_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        file_tree.heading('#0', text='文件名')
        file_tree.heading('selected', text='选择')
        file_tree.heading('type', text='类型')
        file_tree.heading('size', text='大小')
        file_tree.heading('permissions', text='权限')
        file_tree.heading('date', text='修改时间')
        
        file_tree.column('#0', width=200)
        file_tree.column('selected', width=50, anchor='center')
        file_tree.column('type', width=60)
        file_tree.column('size', width=80)
        file_tree.column('permissions', width=100)
        file_tree.column('date', width=120)
        
        # 滚动条
        tree_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=file_tree.yview)
        file_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        file_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # 选中的文件列表
        selected_files = set()
        
        def toggle_selection(event):
            """切换文件选择状态"""
            item = file_tree.identify_row(event.y)
            if item:
                if item in selected_files:
                    selected_files.remove(item)
                    file_tree.set(item, 'selected', '☐')
                else:
                    selected_files.add(item)
                    file_tree.set(item, 'selected', '☑')
        
        def on_double_click(event):
            """双击事件：进入目录或选择文件"""
            item = file_tree.identify_row(event.y)
            if item:
                file_type = file_tree.set(item, 'type')
                if file_type == "目录":
                    filename_with_icon = file_tree.item(item, 'text')
                    if filename_with_icon == "..":
                        navigate_to_parent()
                    else:
                        # 去除emoji图标前缀，提取纯文件名
                        import re
                        filename = re.sub(r'^[\U0001F300-\U0001F9FF]\s*', '', filename_with_icon)
                        print(f"Debug: 双击目录 - 原始: {filename_with_icon}, 提取: {filename}")
                        new_path = os.path.join(current_path_var.get(), filename).replace("\\", "/")
                        load_directory(new_path)
        
        def navigate_to_parent():
            """返回上级目录"""
            current_path = current_path_var.get()
            if current_path != "/" and current_path != "/root":
                parent_path = os.path.dirname(current_path)
                if not parent_path or parent_path == "/":
                    parent_path = "/root"
                load_directory(parent_path)
        
        def select_all():
            """全选所有文件"""
            for item in file_tree.get_children():
                filename = file_tree.item(item, 'text')
                if filename != "..":  # 不选择返回上级目录项
                    selected_files.add(item)
                    file_tree.set(item, 'selected', '☑')
        
        def deselect_all():
            """取消全选"""
            selected_files.clear()
            for item in file_tree.get_children():
                file_tree.set(item, 'selected', '☐')
        
        # 绑定事件
        file_tree.bind('<Button-1>', toggle_selection)
        file_tree.bind('<Double-1>', on_double_click)
        
        def load_directory(path="/root"):
            """加载目录内容"""
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                # 清空当前列表和选择
                for item in file_tree.get_children():
                    file_tree.delete(item)
                selected_files.clear()
                
                # 获取目录内容
                stdin, stdout, stderr = ssh.exec_command(f'ls -la "{path}"')
                output = stdout.read().decode('utf-8', errors='ignore')
                error_output = stderr.read().decode('utf-8', errors='ignore')
                
                # 添加调试信息
                print(f"Debug: 正在加载目录: {path}")
                print(f"Debug: ls命令输出长度: {len(output)}")
                if error_output:
                    print(f"Debug: ls命令错误输出: {error_output}")
                
                current_path_var.set(path)
                
                # 更新面包屑导航
                create_breadcrumb()
                
                # 如果不是根目录，添加返回上级目录选项
                if path != "/" and path != "/root":
                    file_tree.insert('', 'end', text="..", 
                                   values=("☐", "目录", "", "drwxr-xr-x", ""))
                
                lines = output.strip().split('\n')
                print(f"Debug: 总行数: {len(lines)}")
                
                # 跳过第一行总计信息
                if lines and lines[0].startswith('total'):
                    lines = lines[1:]
                
                directories = []
                files = []
                
                for i, line in enumerate(lines):
                    if line.strip():
                        print(f"Debug: 处理第{i+1}行: {line}")
                        # 使用正则表达式更准确地解析ls -la输出
                        import re
                        # ls -la的格式: permissions links owner group size month day time/year filename
                        match = re.match(r'^(\S+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\S+\s+\d+\s+\S+)\s+(.+)$', line)
                        
                        if match:
                            permissions = match.group(1)
                            size = match.group(5)
                            date = match.group(6)
                            filename = match.group(7)
                            
                            print(f"Debug: 解析到文件: {filename}, 权限: {permissions}")
                            
                            if filename in ['.', '..']:
                                continue
                            
                            file_type = "目录" if permissions.startswith('d') else "文件"
                            item_data = (filename, file_type, size, permissions, date)
                            
                            if file_type == "目录":
                                directories.append(item_data)
                            else:
                                files.append(item_data)
                        else:
                            print(f"Debug: 无法解析行: {line}")
                
                print(f"Debug: 找到 {len(directories)} 个目录, {len(files)} 个文件")
                
                def get_file_icon(filename, file_type):
                    """根据文件类型和扩展名返回合适的图标"""
                    if file_type == "目录":
                        return "📁"
                    
                    # 根据文件扩展名返回不同图标
                    ext = filename.lower().split('.')[-1] if '.' in filename else ''
                    
                    icon_map = {
                        'py': '🐍', 'python': '🐍',
                        'js': '📜', 'javascript': '📜',
                        'html': '🌐', 'htm': '🌐',
                        'css': '🎨',
                        'json': '📋',
                        'xml': '📋',
                        'txt': '📝', 'md': '📝', 'readme': '📝',
                        'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'bmp': '🖼️',
                        'mp4': '🎬', 'avi': '🎬', 'mov': '🎬', 'mkv': '🎬',
                        'mp3': '🎵', 'wav': '🎵', 'flac': '🎵',
                        'zip': '📦', 'rar': '📦', 'tar': '📦', 'gz': '📦',
                        'pdf': '📕',
                        'doc': '📄', 'docx': '📄',
                        'xls': '📊', 'xlsx': '📊',
                        'ppt': '📊', 'pptx': '📊',
                        'log': '📜',
                        'sh': '⚙️', 'bat': '⚙️', 'cmd': '⚙️',
                        'exe': '⚙️', 'msi': '⚙️',
                        'cfg': '⚙️', 'conf': '⚙️', 'ini': '⚙️',
                    }
                    
                    return icon_map.get(ext, '📄')
                
                def format_file_size(size_str):
                    """格式化文件大小显示"""
                    try:
                        size = int(size_str)
                        if size < 1024:
                            return f"{size} B"
                        elif size < 1024 * 1024:
                            return f"{size / 1024:.1f} KB"
                        elif size < 1024 * 1024 * 1024:
                            return f"{size / (1024 * 1024):.1f} MB"
                        else:
                            return f"{size / (1024 * 1024 * 1024):.1f} GB"
                    except:
                        return size_str
                
                # 先显示目录，再显示文件
                for filename, file_type, size, permissions, date in sorted(directories):
                    icon = get_file_icon(filename, file_type)
                    file_tree.insert('', 'end', text=f"{icon} {filename}", 
                                   values=("☐", file_type, size, permissions, date))
                
                for filename, file_type, size, permissions, date in sorted(files):
                    icon = get_file_icon(filename, file_type)
                    formatted_size = format_file_size(size)
                    file_tree.insert('', 'end', text=f"{icon} {filename}", 
                                   values=("☐", file_type, formatted_size, permissions, date))
                
                ssh.close()
                
            except Exception as e:
                messagebox.showerror("错误", f"加载目录失败: {str(e)}")
        
        # 初始加载根目录
        load_directory()
        
        # 选择控制框架
        selection_frame = ttk.Frame(browse_frame)
        selection_frame.pack(fill='x', pady=5)
        
        ttk.Button(selection_frame, text="全选", command=select_all).pack(side='left', padx=5)
        ttk.Button(selection_frame, text="取消全选", command=deselect_all).pack(side='left', padx=5)
        
        # 按钮框架
        button_frame = ttk.Frame(delete_window)
        button_frame.pack(fill='x', padx=20, pady=10)
        
        def delete_selected():
            if not selected_files:
                messagebox.showwarning("警告", "请选择要删除的文件或文件夹")
                return
            
            # 确认删除
            file_names = []
            for item in selected_files:
                filename_with_icon = file_tree.item(item, 'text')
                # 移除图标前缀（任何emoji + 空格的组合）
                import re
                filename = re.sub(r'^[\U0001F300-\U0001F9FF]\s*', '', filename_with_icon)
                print(f"Debug: 删除文件 - 原始: {filename_with_icon}, 提取: {filename}")
                
                if filename != "..":  # 不删除返回上级目录项
                    file_names.append(filename)
            
            if not file_names:
                messagebox.showwarning("警告", "没有有效的文件或文件夹可删除")
                return
            
            confirm_msg = f"确定要删除以下 {len(file_names)} 个项目吗？\n\n" + "\n".join(file_names[:10])
            if len(file_names) > 10:
                confirm_msg += f"\n... 还有 {len(file_names) - 10} 个项目"
            
            if messagebox.askyesno("确认删除", confirm_msg):
                self.execute_file_deletion(file_names, current_path_var.get(), delete_window)
        
        ttk.Button(button_frame, text="删除选中", command=delete_selected).pack(side='left', padx=5)
        ttk.Button(button_frame, text="取消", command=delete_window.destroy).pack(side='right', padx=5)
    
    def execute_file_deletion(self, file_names, current_path, parent_window):
        """执行文件删除操作"""
        parent_window.destroy()
        
        # 创建删除进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("删除进度")
        progress_window.geometry("500x300")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        tk.Label(progress_window, text="正在删除文件...", font=("Arial", 12)).pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill='x', padx=20, pady=10)
        
        # 删除日志
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        log_text = tk.Text(log_frame, wrap='word', font=('Consolas', 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        
        log_text.pack(side='left', fill='both', expand=True)
        log_scrollbar.pack(side='right', fill='y')
        
        def deletion_thread():
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                total_files = len(file_names)
                deleted_count = 0
                
                for i, filename in enumerate(file_names):
                    # 更新进度
                    progress = (i / total_files) * 100
                    self.root.after(0, lambda p=progress: progress_var.set(p))
                    
                    # 构建完整路径
                    full_path = os.path.join(current_path, filename).replace("\\", "/")
                    
                    # 添加日志
                    self.root.after(0, lambda f=filename: log_text.insert(tk.END, f"正在删除: {f}\n"))
                    self.root.after(0, lambda: log_text.see(tk.END))
                    
                    try:
                        # 执行删除命令
                        stdin, stdout, stderr = ssh.exec_command(f'rm -rf "{full_path}"')
                        stdout.read()  # 等待命令完成
                        
                        error_output = stderr.read().decode('utf-8', errors='ignore')
                        if error_output:
                            self.root.after(0, lambda f=filename, e=error_output: 
                                          log_text.insert(tk.END, f"删除 {f} 失败: {e}\n"))
                        else:
                            deleted_count += 1
                            self.root.after(0, lambda f=filename: 
                                          log_text.insert(tk.END, f"✓ 已删除: {f}\n"))
                    
                    except Exception as e:
                        self.root.after(0, lambda f=filename, err=str(e): 
                                      log_text.insert(tk.END, f"删除 {f} 失败: {err}\n"))
                
                # 完成删除
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n删除完成！成功删除 {deleted_count}/{total_files} 个项目\n"))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"删除完成！成功删除 {deleted_count}/{total_files} 个项目"))
                
                ssh.close()
                
            except Exception as e:
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n删除失败: {str(e)}\n"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"删除失败: {str(e)}"))
        
        import threading
        threading.Thread(target=deletion_thread, daemon=True).start()
        
        # 关闭按钮
        ttk.Button(progress_window, text="关闭", command=progress_window.destroy).pack(pady=10)
    
    def analyze_dataset(self):
        """分析数据集"""
        try:
            dataset_path = self.local_path_var.get()
            if not dataset_path or not os.path.exists(dataset_path):
                messagebox.showerror("错误", "请选择有效的数据集路径")
                return
            
            # 查找dataset.yaml文件
            yaml_file = os.path.join(dataset_path, 'dataset.yaml')
            if os.path.exists(yaml_file):
                # 读取并显示yaml配置
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    yaml_content = f.read()
                
                # 显示yaml配置内容
                self.yaml_config_text.delete(1.0, tk.END)
                self.yaml_config_text.insert(tk.END, yaml_content)
                
                # 解析yaml配置
                try:
                    yaml_data = yaml.safe_load(yaml_content)
                    
                    # 更新类别数量
                    if 'nc' in yaml_data:
                        num_classes = yaml_data['nc']
                        self.num_classes_var.set(str(num_classes))
                        self.dataset_config['num_classes'] = num_classes
                    
                    # 更新类别列表
                    if 'names' in yaml_data:
                        classes = yaml_data['names']
                        self.dataset_config['classes'] = classes
                        self.classes_text.delete(1.0, tk.END)
                        if isinstance(classes, dict):
                            for i, cls in classes.items():
                                self.classes_text.insert(tk.END, f"{i}: {cls}\n")
                        elif isinstance(classes, list):
                            for i, cls in enumerate(classes):
                                self.classes_text.insert(tk.END, f"{i}: {cls}\n")
                    
                    # 检查路径问题
                    self.check_yaml_paths(yaml_data, dataset_path)
                    
                except yaml.YAMLError as e:
                    self.log_message(f"YAML解析错误: {e}")
                    messagebox.showerror("错误", f"YAML文件格式错误: {e}")
                    return
            else:
                self.yaml_config_text.delete(1.0, tk.END)
                self.yaml_config_text.insert(tk.END, "未找到dataset.yaml文件")
                self.path_issues_text.delete(1.0, tk.END)
                self.path_issues_text.insert(tk.END, "错误: 未找到dataset.yaml文件")
            
            # 设置数据集名称
            dataset_name = os.path.basename(dataset_path)
            self.dataset_name_var.set(dataset_name)
            self.dataset_config['dataset_name'] = dataset_name
            
            self.log_message(f"数据集分析完成: {dataset_name}")
            
        except Exception as e:
            self.log_message(f"数据集分析失败: {e}")
            messagebox.showerror("错误", f"数据集分析失败: {e}")
    
    def check_yaml_paths(self, yaml_data, dataset_path):
        """检查yaml配置中的路径问题"""
        issues = []
        warnings = []
        
        # 检查路径配置
        if 'path' in yaml_data:
            path_value = yaml_data['path']
            if isinstance(path_value, str):
                # 检查是否包含Windows路径格式
                if '\\' in path_value or ':' in path_value:
                    issues.append(f"路径包含Windows格式: {path_value}")
                # 检查是否为绝对路径但不是标准云端路径
                if path_value.startswith('/') and not path_value.startswith('/root/'):
                    issues.append(f"路径可能不正确: {path_value}")
        
        # 检查train, val, test路径
        for key in ['train', 'val', 'test']:
            if key in yaml_data:
                path_value = yaml_data[key]
                if isinstance(path_value, str):
                    # 检查是否包含Windows路径格式
                    if '\\' in path_value or ':' in path_value:
                        issues.append(f"{key}路径包含Windows格式: {path_value}")
                    # 检查是否为绝对路径
                    if path_value.startswith('/'):
                        issues.append(f"{key}路径应使用相对路径: {path_value}")
        
        # 检查本地数据集文件结构
        if dataset_path and os.path.exists(dataset_path):
            # 检查是否存在Windows格式的文件名
            windows_files = []
            for root, dirs, files in os.walk(dataset_path):
                for file in files:
                    if '\\' in file or any(char in file for char in ['<', '>', ':', '"', '|', '?', '*']):
                        rel_path = os.path.relpath(os.path.join(root, file), dataset_path)
                        windows_files.append(rel_path)
            
            if windows_files:
                issues.append(f"发现{len(windows_files)}个包含Windows特殊字符的文件")
                if len(windows_files) <= 5:
                    for file in windows_files:
                        issues.append(f"  - {file}")
                else:
                    for file in windows_files[:3]:
                        issues.append(f"  - {file}")
                    issues.append(f"  - ... 还有{len(windows_files)-3}个文件")
            
            # 检查目录结构是否符合YOLO标准
            expected_dirs = ['train/images', 'train/labels', 'val/images', 'val/labels']
            missing_dirs = []
            for expected_dir in expected_dirs:
                full_path = os.path.join(dataset_path, expected_dir)
                if not os.path.exists(full_path):
                    missing_dirs.append(expected_dir)
            
            if missing_dirs:
                warnings.append(f"缺少标准YOLO目录结构: {', '.join(missing_dirs)}")
            
            # 检查是否有文件直接存储在根目录
            root_files = []
            for item in os.listdir(dataset_path):
                item_path = os.path.join(dataset_path, item)
                if os.path.isfile(item_path) and item.lower().endswith(('.jpg', '.jpeg', '.png', '.txt')):
                    root_files.append(item)
            
            if root_files:
                warnings.append(f"发现{len(root_files)}个文件直接存储在根目录，应移动到对应的子目录")
        
        # 显示检查结果
        self.path_issues_text.delete(1.0, tk.END)
        
        if issues:
            self.path_issues_text.insert(tk.END, "🔴 发现以下严重问题:\n")
            for issue in issues:
                self.path_issues_text.insert(tk.END, f"• {issue}\n")
            self.path_issues_text.insert(tk.END, "\n")
        
        if warnings:
            self.path_issues_text.insert(tk.END, "🟡 发现以下警告:\n")
            for warning in warnings:
                self.path_issues_text.insert(tk.END, f"• {warning}\n")
            self.path_issues_text.insert(tk.END, "\n")
        
        if issues or warnings:
            self.path_issues_text.insert(tk.END, "💡 建议点击'检查并修正'按钮自动修复所有问题")
        else:
            self.path_issues_text.insert(tk.END, "✅ 数据集配置和结构完全正确，无需修正")
    
    def check_and_fix_dataset(self):
        """检查并修正数据集配置"""
        try:
            dataset_path = self.local_path_var.get()
            if not dataset_path or not os.path.exists(dataset_path):
                messagebox.showerror("错误", "请先选择有效的数据集路径")
                return
            
            yaml_file = os.path.join(dataset_path, 'dataset.yaml')
            if not os.path.exists(yaml_file):
                messagebox.showerror("错误", "未找到dataset.yaml文件")
                return
            
            # 显示进度对话框
            progress_window = tk.Toplevel(self.root)
            progress_window.title("修正数据集")
            progress_window.geometry("400x200")
            progress_window.transient(self.root)
            progress_window.grab_set()
            
            progress_label = ttk.Label(progress_window, text="正在检查数据集...")
            progress_label.pack(pady=20)
            
            progress_bar = ttk.Progressbar(progress_window, mode='indeterminate')
            progress_bar.pack(pady=10, padx=20, fill=tk.X)
            progress_bar.start()
            
            progress_text = scrolledtext.ScrolledText(progress_window, height=6, width=50)
            progress_text.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
            
            def update_progress(message):
                progress_text.insert(tk.END, f"{message}\n")
                progress_text.see(tk.END)
                progress_window.update()
            
            # 读取当前配置
            update_progress("读取dataset.yaml文件...")
            with open(yaml_file, 'r', encoding='utf-8') as f:
                yaml_content = f.read()
            
            yaml_data = yaml.safe_load(yaml_content)
            
            # 备份原文件
            backup_file = yaml_file + f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            update_progress("备份原始配置文件...")
            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(yaml_content)
            
            # 修正本地目录结构
            update_progress("检查并修正本地目录结构...")
            self.fix_local_dataset_structure(dataset_path, update_progress)
            
            # 修正配置
            update_progress("修正YAML配置...")
            fixed_data = self.fix_yaml_config(yaml_data, dataset_path)
            
            # 保存修正后的配置
            update_progress("保存修正后的配置...")
            with open(yaml_file, 'w', encoding='utf-8') as f:
                yaml.dump(fixed_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
            
            # 修正云端目录结构
            update_progress("修正云端目录结构...")
            self.fix_cloud_dataset_structure(update_progress)
            
            progress_bar.stop()
            update_progress("✅ 数据集修正完成!")
            
            # 重新加载并显示
            self.analyze_dataset()
            
            self.log_message(f"数据集配置已修正，原文件备份为: {backup_file}")
            
            # 关闭进度窗口并显示成功消息
            progress_window.after(2000, progress_window.destroy)
            messagebox.showinfo("成功", f"数据集配置和结构已修正!\n原文件已备份为:\n{os.path.basename(backup_file)}")
            
        except Exception as e:
            self.log_message(f"修正数据集配置失败: {e}")
            messagebox.showerror("错误", f"修正数据集配置失败: {e}")
            if 'progress_window' in locals():
                progress_window.destroy()
    
    def fix_yaml_config(self, yaml_data, dataset_path):
        """修正yaml配置"""
        fixed_data = yaml_data.copy()
        
        # 获取数据集名称
        dataset_name = os.path.basename(dataset_path)
        
        # 修正主路径 - 设置为云端标准路径
        fixed_data['path'] = f'/root/{dataset_name}'
        
        # 修正train, val, test路径 - 使用相对路径
        if 'train' in fixed_data:
            fixed_data['train'] = 'train/images'
        if 'val' in fixed_data:
            fixed_data['val'] = 'val/images'
        if 'test' in fixed_data:
            fixed_data['test'] = 'test/images'
        
        # 确保nc和names字段存在
        if 'nc' not in fixed_data and 'names' in fixed_data:
            if isinstance(fixed_data['names'], dict):
                fixed_data['nc'] = len(fixed_data['names'])
            elif isinstance(fixed_data['names'], list):
                fixed_data['nc'] = len(fixed_data['names'])
        
        return fixed_data
    
    def fix_local_dataset_structure(self, dataset_path, update_progress):
        """修正本地数据集目录结构"""
        try:
            # 创建标准YOLO目录结构
            required_dirs = ['train/images', 'train/labels', 'val/images', 'val/labels', 'test/images', 'test/labels']
            for dir_path in required_dirs:
                full_path = os.path.join(dataset_path, dir_path)
                if not os.path.exists(full_path):
                    os.makedirs(full_path, exist_ok=True)
                    update_progress(f"创建目录: {dir_path}")
            
            # 移动根目录下的文件到对应子目录
            root_files = []
            for item in os.listdir(dataset_path):
                item_path = os.path.join(dataset_path, item)
                if os.path.isfile(item_path) and item.lower().endswith(('.jpg', '.jpeg', '.png', '.txt')):
                    root_files.append(item)
            
            if root_files:
                update_progress(f"发现{len(root_files)}个文件需要重新组织...")
                
                # 简单的文件分类逻辑：按文件名或数量分配到train/val
                image_files = [f for f in root_files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                label_files = [f for f in root_files if f.lower().endswith('.txt')]
                
                # 80% 训练，20% 验证
                train_count = int(len(image_files) * 0.8)
                
                for i, img_file in enumerate(image_files):
                    src_path = os.path.join(dataset_path, img_file)
                    if i < train_count:
                        dst_path = os.path.join(dataset_path, 'train/images', img_file)
                    else:
                        dst_path = os.path.join(dataset_path, 'val/images', img_file)
                    
                    if not os.path.exists(dst_path):
                        os.rename(src_path, dst_path)
                
                for label_file in label_files:
                    # 查找对应的图片文件
                    base_name = os.path.splitext(label_file)[0]
                    corresponding_img = None
                    for img_file in image_files:
                        if os.path.splitext(img_file)[0] == base_name:
                            corresponding_img = img_file
                            break
                    
                    if corresponding_img:
                        src_path = os.path.join(dataset_path, label_file)
                        img_index = image_files.index(corresponding_img)
                        if img_index < train_count:
                            dst_path = os.path.join(dataset_path, 'train/labels', label_file)
                        else:
                            dst_path = os.path.join(dataset_path, 'val/labels', label_file)
                        
                        if not os.path.exists(dst_path):
                            os.rename(src_path, dst_path)
                
                update_progress(f"重新组织了{len(root_files)}个文件")
            
        except Exception as e:
            update_progress(f"本地结构修正失败: {e}")
            raise e
    
    def fix_cloud_dataset_structure(self, update_progress):
        """修正云端数据集目录结构"""
        try:
            # 连接到云端服务器
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            update_progress("连接到云端服务器...")
            ssh.connect(
                hostname=self.server_config['hostname'],
                port=self.server_config['port'],
                username=self.server_config['username'],
                password=self.server_config['password']
            )
            
            dataset_name = self.dataset_config['dataset_name']
            remote_path = f"/root/{dataset_name}"
            
            # 检查云端目录结构
            update_progress("检查云端目录结构...")
            stdin, stdout, stderr = ssh.exec_command(f"ls -la {remote_path}")
            ls_output = stdout.read().decode()
            
            # 检查是否需要重组
            if "train" not in ls_output or "val" not in ls_output:
                update_progress("云端目录结构需要重组...")
                
                # 创建修复脚本
                fix_script = f"""#!/bin/bash
# 云端数据集结构修复脚本
cd {remote_path}

# 备份当前数据
echo "备份当前数据..."
cp -r . ../backup_{dataset_name}_$(date +%Y%m%d_%H%M%S)

# 创建标准目录结构
echo "创建标准目录结构..."
mkdir -p train/images train/labels val/images val/labels test/images test/labels

# 查找所有图片和标签文件
echo "查找文件..."
find . -maxdepth 1 -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" > /tmp/images.txt
find . -maxdepth 1 -name "*.txt" > /tmp/labels.txt

# 计算文件数量
img_count=$(wc -l < /tmp/images.txt)
train_count=$((img_count * 80 / 100))

echo "总图片数: $img_count, 训练集: $train_count"

# 移动图片文件
counter=0
while IFS= read -r img_file; do
    if [ $counter -lt $train_count ]; then
        mv "$img_file" train/images/
    else
        mv "$img_file" val/images/
    fi
    counter=$((counter + 1))
done < /tmp/images.txt

# 移动标签文件
while IFS= read -r label_file; do
    base_name=$(basename "$label_file" .txt)
    if [ -f "train/images/$base_name.jpg" ] || [ -f "train/images/$base_name.jpeg" ] || [ -f "train/images/$base_name.png" ]; then
        mv "$label_file" train/labels/
    else
        mv "$label_file" val/labels/
    fi
done < /tmp/labels.txt

# 清理临时文件
rm -f /tmp/images.txt /tmp/labels.txt

echo "云端目录结构修复完成!"
"""
                
                # 上传并执行修复脚本
                update_progress("上传修复脚本...")
                stdin, stdout, stderr = ssh.exec_command(f"cat > /tmp/fix_dataset.sh << 'EOF'\n{fix_script}\nEOF")
                stdout.read()
                
                update_progress("执行修复脚本...")
                stdin, stdout, stderr = ssh.exec_command("chmod +x /tmp/fix_dataset.sh && /tmp/fix_dataset.sh")
                script_output = stdout.read().decode()
                script_error = stderr.read().decode()
                
                if script_error:
                    update_progress(f"脚本执行警告: {script_error}")
                
                update_progress("云端结构修复完成")
            else:
                update_progress("云端目录结构正常")
            
            ssh.close()
            
        except Exception as e:
            update_progress(f"云端结构修正失败: {e}")
            if 'ssh' in locals():
                ssh.close()
            # 不抛出异常，允许本地修正继续进行
    
    def generate_training_script(self):
        """生成训练脚本"""
        try:
            if not self.dataset_config['local_path']:
                messagebox.showerror("错误", "请先选择数据集路径")
                return
            
            # 更新训练配置
            self.training_config['epochs'] = int(self.epochs_var.get())
            self.training_config['batch_size'] = int(self.batch_size_var.get())
            self.training_config['learning_rate'] = float(self.learning_rate_var.get())
            self.training_config['image_size'] = int(self.image_size_var.get())
            self.training_config['base_model'] = self.base_model_var.get()
            
            # 生成训练脚本内容
            script_content = self.create_training_script_content()
            
            # 保存脚本文件到相对目录
            script_file = "generated_training_script.py"
            with open(script_file, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            self.log_message(f"训练脚本已生成: {script_file}")
            messagebox.showinfo("成功", f"训练脚本已生成: {script_file}")
            
        except Exception as e:
            self.log_message(f"生成训练脚本失败: {e}")
            messagebox.showerror("错误", f"生成训练脚本失败: {e}")
    
    def create_training_script_content(self):
        """创建训练脚本内容"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dataset_name = self.dataset_config['dataset_name']
        num_classes = self.dataset_config['num_classes']
        remote_path = self.dataset_config['remote_path']
        epochs = self.training_config['epochs']
        batch_size = self.training_config['batch_size']
        learning_rate = self.training_config['learning_rate']
        image_size = self.training_config['image_size']
        base_model = self.training_config['base_model']
        
        script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成的YOLO训练脚本
数据集: {dataset_name}
类别数: {num_classes}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
训练参数: epochs={epochs}, batch={batch_size}, lr={learning_rate}
"""

import os
import sys
import torch
import yaml
from ultralytics import YOLO
from pathlib import Path
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    try:
        # 数据集配置
        dataset_path = "{remote_path}"
        yaml_path = os.path.join(dataset_path, "dataset.yaml")
        
        # 检查数据集
        if not os.path.exists(yaml_path):
            logger.error(f"数据集配置文件不存在: {{yaml_path}}")
            return
        
        # 检查并下载YOLO模型
        model_name = "{base_model}"
        logger.info(f"准备加载模型: {{model_name}}")
        
        def download_model_with_retry(model_name, max_retries=3):
            """带重试机制的模型下载函数"""
            import urllib.request
            import urllib.error
            import time
            import ssl
            
            # 创建SSL上下文，忽略证书验证（用于网络问题）
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"第 {{attempt + 1}} 次尝试加载模型: {{model_name}}")
                    
                    # 首先尝试直接加载（可能已存在）
                    if os.path.exists(model_name):
                        model = YOLO(model_name)
                        logger.info(f"模型 {{model_name}} 从本地加载成功")
                        return model
                    
                    # 尝试让YOLO自动下载
                    model = YOLO(model_name)
                    logger.info(f"模型 {{model_name}} 自动下载并加载成功")
                    return model
                    
                except Exception as e:
                    logger.warning(f"第 {{attempt + 1}} 次尝试失败: {{e}}")
                    
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10  # 递增等待时间
                        logger.info(f"等待 {{wait_time}} 秒后重试...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"所有 {{max_retries}} 次尝试都失败了")
                        raise e
            
            return None
        
        # 使用改进的下载函数
        try:
            model = download_model_with_retry(model_name)
            if model is None:
                raise Exception("模型下载失败")
        except Exception as e:
            logger.error(f"模型下载最终失败: {{e}}")
            logger.info("尝试使用备用方案...")
            
            # 备用方案：尝试使用其他可用的模型
            backup_models = ["yolov8s.pt", "yolov8n.pt", "yolov11s.pt", "yolov11n.pt"]
            model = None
            
            for backup_model in backup_models:
                if backup_model != model_name:
                    try:
                        logger.info(f"尝试备用模型: {{backup_model}}")
                        model = YOLO(backup_model)
                        logger.info(f"备用模型 {{backup_model}} 加载成功")
                        break
                    except Exception as backup_error:
                        logger.warning(f"备用模型 {{backup_model}} 也失败: {{backup_error}}")
                        continue
            
            if model is None:
                logger.error("所有模型下载尝试都失败，无法继续训练")
                raise Exception("无法下载任何可用的YOLO模型")
        
        # 开始训练
        logger.info("开始训练...")
        # 设备选择
        try:
            cuda_available = torch.cuda.is_available()
            cuda_count = torch.cuda.device_count()
            cuda_env = os.environ.get('CUDA_VISIBLE_DEVICES')
            logger.info(f"torch.cuda.is_available(): {{cuda_available}}")
            logger.info(f"torch.cuda.device_count(): {{cuda_count}}")
            logger.info(f"os.environ['CUDA_VISIBLE_DEVICES']: {{cuda_env}}")
            device_arg = '0' if cuda_available and cuda_count > 0 else 'cpu'
        except Exception:
            device_arg = 'cpu'
        # 若设备选择仍报错，降级为CPU重试
        try:
            results = model.train(
            data=yaml_path,
            epochs={epochs},
            batch={batch_size},
            lr0={learning_rate},
            imgsz={image_size},
            device=device_arg,
            project='runs/train',
            name='yolo_training_{timestamp}',
            save=True,
            save_period=10,
            val=True,
            plots=True
            )
        except Exception as dev_err:
            logger.warning(f"设备设置失败({{dev_err}})，切换为CPU重试...")
            results = model.train(
                data=yaml_path,
                epochs={epochs},
                batch={batch_size},
                lr0={learning_rate},
                imgsz={image_size},
                device='cpu',
                project='runs/train',
                name='yolo_training_{timestamp}',
                save=True,
                save_period=10,
                val=True,
                plots=True
            )
        
        logger.info("训练完成！")
        return results
        
    except Exception as e:
        logger.error(f"训练失败: {{e}}")
        raise

if __name__ == "__main__":
    main()
'''
        return script_content

    # ========== 并发+断点续传私有方法 ==========
    def _checkpoint_save(self, ckpt_path, done):
        """保存断点记录"""
        print(f'[DEBUG] _checkpoint_save -> {ckpt_path}  {len(done)} files')
        with open(ckpt_path, 'w', encoding='utf-8') as f:
            json.dump(done, f, ensure_ascii=False, indent=2)

    def _checkpoint_load(self, ckpt_path):
        """加载断点记录"""
        if not os.path.exists(ckpt_path):
            return {}
        try:
            with open(ckpt_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _upload_worker(self, ssh_transport, local_file, remote_file, retry_times):
        """单个文件上传（含重试）"""
        print(f'[DEBUG] _upload_worker start  {os.path.basename(local_file)}')
        import stat
        scp = SCPClient(ssh_transport)
        for attempt in range(1, retry_times + 1):
            try:
                # 使用SFTP进行秒传判断与目录创建
                with paramiko.SFTPClient.from_transport(ssh_transport) as sftp:
                    # 秒传：远程文件大小一致则跳过
                    try:
                        remote_stat = sftp.stat(remote_file)
                        local_size  = os.path.getsize(local_file)
                        if stat.S_ISREG(remote_stat.st_mode) and remote_stat.st_size == local_size:
                            return 'skip'
                    except FileNotFoundError:
                        pass

                    # 确保远程目录存在（逐级创建）
                    remote_dir = os.path.dirname(remote_file).replace("\\", "/")
                    parts = [p for p in remote_dir.split('/') if p]
                    prefix = '/' if remote_dir.startswith('/') else ''
                    built = []
                    for p in parts:
                        built.append(p)
                        path = prefix + '/'.join(built)
                        try:
                            st = sftp.stat(path)
                            if not stat.S_ISDIR(st.st_mode):
                                # 若同名非目录，则抛出异常
                                raise IOError(f"Remote path exists and is not a directory: {path}")
                        except FileNotFoundError:
                            try:
                                sftp.mkdir(path)
                            except Exception:
                                # 并发场景下可能已被其他线程创建，若已存在则忽略
                                try:
                                    st2 = sftp.stat(path)
                                    if not stat.S_ISDIR(st2.st_mode):
                                        raise
                                except Exception:
                                    raise

                # 上传文件
                scp.put(local_file, remote_file)
                print(f'[DEBUG] _upload_worker ok  {os.path.basename(local_file)}')
                return 'ok'
            except Exception as e:
                if attempt == retry_times:
                    print(f'[DEBUG] _upload_worker fail  {os.path.basename(local_file)}  {e}')
                    return f'fail:{e}'
                time.sleep(1)
        print(f'[DEBUG] _upload_worker fail:unknown  {os.path.basename(local_file)}')
        return 'fail:unknown'

    def upload_dataset(self):
        """并发+断点续传上传数据集到云端"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        if not self.dataset_config['local_path']:
            messagebox.showerror("错误", "请先选择数据集路径")
            return
        if not hasattr(self, 'upload_status_var'):
            self.upload_status_var = tk.StringVar(value="")
        if not hasattr(self, 'upload_progress_var'):
            self.upload_progress_var = tk.DoubleVar()

        def upload_thread():
            try:
                # 读取并发度与重试次数
                max_workers = self.config.get('upload', {}).get('max_workers', 8)
                retry_times = self.config.get('upload', {}).get('retry_times', 3)

                self.root.after(0, lambda: self.upload_status_var.set("正在扫描文件..."))
                self.root.after(0, lambda: self._set_upload_progress(0))

                # 建立 SSH 连接
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                ssh.connect(**connect_params)
                transport = ssh.get_transport()

                local_path  = self.dataset_config['local_path']
                remote_path = self.remote_path_var.get().rstrip('/')
                ckpt_path   = os.path.join(local_path, '.upload_checkpoint.json')

                # 扫描全部文件
                all_files = []
                for root, _, files in os.walk(local_path):
                    for f in files:
                        local_file = os.path.join(root, f)
                        rel_path   = os.path.relpath(local_file, local_path)
                        remote_file = f"{remote_path}/{rel_path}".replace('\\', '/')
                        all_files.append((local_file, remote_file))
                total = len(all_files)
                self.root.after(0, lambda: self.upload_status_var.set(f"共 {total} 个文件，加载断点..."))

                # 加载断点
                done = self._checkpoint_load(ckpt_path)  # {local_file: 'ok'/'skip'/...}
                todo = [(lf, rf) for lf, rf in all_files if done.get(lf) != 'ok' and done.get(lf) != 'skip']
                skip_count = total - len(todo)

                ok_count   = 0
                fail_list  = []
                lock       = threading.Lock()

                def update_ui():
                    with lock:
                        finished = ok_count + skip_count
                        percent  = (finished / total * 100) if total else 0
                        self.root.after(0, lambda: self._set_upload_progress(percent))
                        self.root.after(0, lambda: self.upload_status_var.set(
                            f"进度 {finished}/{total}  成功 {ok_count}  跳过 {skip_count}  失败 {len(fail_list)}"))

                update_ui()

                # 并发上传
                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    future_map = {}
                    for local_file, remote_file in todo:
                        fut = pool.submit(self._upload_worker, transport, local_file, remote_file, retry_times)
                        future_map[fut] = local_file

                    for fut in as_completed(future_map):
                        local_file = future_map[fut]
                        res = fut.result()
                        done[local_file] = res
                        if res == 'ok':
                            with lock:
                                ok_count += 1
                        elif res == 'skip':
                            with lock:
                                skip_count += 1
                        elif res.startswith('fail'):
                            with lock:
                                fail_list.append((local_file, res))
                        # 实时保存断点
                        self._checkpoint_save(ckpt_path, done)
                        update_ui()

                ssh.close()
                # 删除断点文件
                if os.path.exists(ckpt_path):
                    os.remove(ckpt_path)

                # 总结弹窗
                self.root.after(0, lambda: messagebox.showinfo(
                    "上传完成",
                    f"总计 {total}\n成功 {ok_count}\n跳过 {skip_count}\n失败 {len(fail_list)}"))
                self.root.after(0, lambda: self.upload_status_var.set("上传完成"))
                self.root.after(0, lambda: self.log_message("数据集上传完成"))

            except Exception as e:
                err = str(e)
                self.root.after(0, lambda err=err: self.upload_status_var.set(f"上传失败: {err}"))
                self.root.after(0, lambda err=err: self.log_message(f"数据集上传失败: {err}"))

        threading.Thread(target=upload_thread, daemon=True).start()
    
    def clean_cloud_data(self):
        """清理云端数据"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        if messagebox.askyesno("确认", "确定要清理云端数据吗？此操作不可恢复。"):
            def clean_thread():
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    connect_params = {
                        'hostname': self.server_config['hostname'],
                        'port': self.server_config['port'],
                        'username': self.server_config['username']
                    }
                    
                    if self.server_config['key_file']:
                        connect_params['key_filename'] = self.server_config['key_file']
                    else:
                        connect_params['password'] = self.server_config['password']
                    
                    ssh.connect(**connect_params)
                    
                    # 清理命令
                    remote_path = self.remote_path_var.get()
                    ssh.exec_command(f'rm -rf {remote_path}')
                    ssh.exec_command('rm -rf /root/runs')
                    ssh.exec_command('rm -f /root/*.py')
                    
                    ssh.close()
                    
                    self.root.after(0, lambda: self.log_message("云端数据清理完成"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"云端数据清理失败: {e}"))
            
            threading.Thread(target=clean_thread, daemon=True).start()
    
    def start_training(self):
        """开始训练"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        def training_thread():
            try:
                self.root.after(0, lambda: self.training_status_var.set("训练中..."))
                self.is_training = True
                
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                # 预下载模型
                self.root.after(0, lambda: self.log_message("🔄 开始预下载YOLO模型..."))
                selected_model = self.base_model_var.get()
                
                def predownload_model():
                    """预下载模型函数"""
                    try:
                        # 检查模型是否已存在
                        stdin, stdout, stderr = ssh.exec_command(f'ls -la /root/{selected_model}')
                        model_check = stdout.read().decode('utf-8')
                        
                        if selected_model in model_check:
                            self.root.after(0, lambda: self.log_message(f"✓ 模型 {selected_model} 已存在，跳过下载"))
                            return True
                        
                        # 模型不存在，开始下载
                        self.root.after(0, lambda: self.log_message(f"📥 开始下载模型 {selected_model}..."))
                        
                        # 使用Python下载模型
                        download_script = f'''
import os
import sys
import time
import urllib.request
import urllib.error
import ssl

def download_model_with_retry(model_name, max_retries=3):
    """带重试机制的模型下载函数"""
    # 创建SSL上下文，忽略证书验证
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # YOLO模型下载URL
    base_urls = [
        f"https://github.com/ultralytics/assets/releases/download/v8.2.0/{{model_name}}",
        f"https://github.com/ultralytics/assets/releases/download/v0.0.0/{{model_name}}",
        f"https://ultralytics.com/assets/{{model_name}}"
    ]
    
    for attempt in range(max_retries):
        print(f"第 {{attempt + 1}} 次尝试下载模型: {{model_name}}")
        
        # 首先尝试使用ultralytics自动下载
        try:
            from ultralytics import YOLO
            print("尝试使用ultralytics自动下载...")
            model = YOLO(model_name)
            print(f"模型 {{model_name}} 自动下载成功")
            return True
        except Exception as e:
            print(f"ultralytics自动下载失败: {{e}}")
        
        # 如果自动下载失败，尝试手动下载
        for url_template in base_urls:
            try:
                url = url_template.format(model_name=model_name)
                print(f"尝试从 {{url}} 下载...")
                
                request = urllib.request.Request(url)
                request.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                
                with urllib.request.urlopen(request, context=ssl_context, timeout=30) as response:
                    if response.status == 200:
                        with open(model_name, 'wb') as f:
                            f.write(response.read())
                        print(f"模型 {{model_name}} 下载成功")
                        return True
                    else:
                        print(f"下载失败，状态码: {{response.status}}")
            except Exception as e:
                print(f"从 {{url_template}} 下载失败: {{e}}")
                continue
        
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 10
            print(f"等待 {{wait_time}} 秒后重试...")
            time.sleep(wait_time)
    
    print(f"所有下载尝试都失败了")
    return False

# 执行下载
if download_model_with_retry("{selected_model}"):
    print("模型下载成功")
    sys.exit(0)
else:
    print("模型下载失败")
    sys.exit(1)
'''
                        
                        # 执行下载脚本
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && python3 -c "{download_script}"')
                        download_output = stdout.read().decode('utf-8')
                        download_error = stderr.read().decode('utf-8')
                        
                        # 显示下载过程
                        if download_output:
                            for line in download_output.split('\n'):
                                if line.strip():
                                    self.root.after(0, lambda msg=line.strip(): self.log_message(f"  {msg}"))
                        
                        if download_error:
                            for line in download_error.split('\n'):
                                if line.strip() and 'warning' not in line.lower():
                                    self.root.after(0, lambda msg=line.strip(): self.log_message(f"  ⚠ {msg}"))
                        
                        # 再次检查模型是否下载成功
                        stdin, stdout, stderr = ssh.exec_command(f'ls -la /root/{selected_model}')
                        final_check = stdout.read().decode('utf-8')
                        
                        if selected_model in final_check:
                            self.root.after(0, lambda: self.log_message(f"✓ 模型 {selected_model} 预下载成功"))
                            return True
                        else:
                            self.root.after(0, lambda: self.log_message(f"✗ 模型 {selected_model} 预下载失败"))
                            return False
                            
                    except Exception as e:
                        self.root.after(0, lambda err=str(e): self.log_message(f"✗ 模型预下载异常: {err}"))
                        return False
                
                # 执行预下载
                if not predownload_model():
                    self.root.after(0, lambda: self.log_message("⚠ 模型预下载失败，但继续训练（训练脚本中有备用下载机制）"))
                
                # 上传训练脚本
                script_content = self.create_training_script_content()
                with SCPClient(ssh.get_transport()) as scp:
                    # 创建临时脚本文件
                    temp_script = 'temp_training_script.py'
                    with open(temp_script, 'w', encoding='utf-8') as f:
                        f.write(script_content)
                    
                    scp.put(temp_script, '/root/training_script.py')
                    os.remove(temp_script)
                
                # 首先检查脚本是否上传成功
                self.root.after(0, lambda: self.log_message("检查训练脚本..."))
                stdin, stdout, stderr = ssh.exec_command('ls -la /root/training_script.py')
                script_check = stdout.read().decode('utf-8')
                if 'training_script.py' in script_check:
                    self.root.after(0, lambda: self.log_message("✓ 训练脚本上传成功"))
                    self.root.after(0, lambda: self.log_message(f"脚本信息: {script_check.strip()}"))
                else:
                    self.root.after(0, lambda: self.log_message("✗ 训练脚本上传失败"))
                    return
                
                # 检查Python环境 - 尝试多种Python命令
                self.root.after(0, lambda: self.log_message("检查Python环境..."))
                
                # 检查可用的Python命令
                python_cmd = None
                for cmd in ['python3', 'python', '/usr/bin/python3', '/usr/bin/python']:
                    stdin, stdout, stderr = ssh.exec_command(f'which {cmd} && {cmd} --version')
                    result = stdout.read().decode('utf-8')
                    if result and 'Python' in result:
                        python_cmd = cmd
                        self.root.after(0, lambda: self.log_message(f"✓ 找到Python命令: {cmd}"))
                        self.root.after(0, lambda: self.log_message(f"Python版本: {result.strip()}"))
                        break
                
                if not python_cmd:
                    self.root.after(0, lambda: self.log_message("✗ 未找到可用的Python命令"))
                    self.root.after(0, lambda: self.training_status_var.set("训练失败: 未找到Python"))
                    return
                
                # 检查必要的包
                self.root.after(0, lambda: self.log_message("检查必要的Python包..."))
                
                # 检查必要的包
                self.root.after(0, lambda: self.log_message("检查必要的Python包..."))
                
                # 检查核心包 - 改进的包检查策略
                self.root.after(0, lambda: self.log_message("🔍 检查Python环境和已安装包..."))
                
                # 首先检查Python版本和pip
                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} --version && pip3 --version')
                python_info = stdout.read().decode('utf-8')
                if python_info:
                    self.root.after(0, lambda: self.log_message(f"Python环境: {python_info.strip()}"))
                
                # 定义包检查策略 - 分为系统包和需要安装的包
                system_packages = {
                    'numpy': 'import numpy; print("NumPy: " + numpy.__version__)',
                    'cv2': 'import cv2; print("OpenCV: " + cv2.__version__)',
                    'PIL': 'import PIL; print("Pillow: " + PIL.__version__)',
                    'yaml': 'import yaml; print("PyYAML: OK")'
                }
                
                pip_packages = {
                    'torch': 'import torch; print("PyTorch: " + torch.__version__)',
                    'ultralytics': 'import ultralytics; print("Ultralytics: " + ultralytics.__version__)',
                    'matplotlib': 'import matplotlib; print("Matplotlib: " + matplotlib.__version__)'
                }
                
                # 检查系统包
                missing_packages = []
                available_packages = []
                
                self.root.after(0, lambda: self.log_message("检查系统预装包..."))
                for package_name, import_cmd in system_packages.items():
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c \'{import_cmd}\'')
                    package_info = stdout.read().decode('utf-8').strip()
                    package_errors = stderr.read().decode('utf-8').strip()
                    
                    if package_errors and 'ModuleNotFoundError' in package_errors:
                        self.root.after(0, lambda pkg=package_name: self.log_message(f"  ❌ {pkg}: 未安装"))
                        missing_packages.append(package_name)
                    elif package_info:
                        self.root.after(0, lambda info=package_info: self.log_message(f"  ✅ {info}"))
                        available_packages.append(package_info)
                
                # 检查需要pip安装的包
                self.root.after(0, lambda: self.log_message("检查深度学习包..."))
                pip_missing = []
                for package_name, import_cmd in pip_packages.items():
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c \'{import_cmd}\'')
                    package_info = stdout.read().decode('utf-8').strip()
                    package_errors = stderr.read().decode('utf-8').strip()
                    
                    if package_errors and 'ModuleNotFoundError' in package_errors:
                        self.root.after(0, lambda pkg=package_name: self.log_message(f"  ❌ {pkg}: 需要安装"))
                        pip_missing.append(package_name)
                    elif package_info:
                        self.root.after(0, lambda info=package_info: self.log_message(f"  ✅ {info}"))
                        available_packages.append(package_info)
                
                if available_packages:
                    self.root.after(0, lambda: self.log_message("✓ 已安装的包:"))
                    for pkg_info in available_packages:
                        self.root.after(0, lambda info=pkg_info: self.log_message(f"  - {info}"))
                
                # 处理系统包缺失（如果有的话）
                if missing_packages:
                    self.root.after(0, lambda: self.log_message(f"⚠ 检测到缺失的系统包: {', '.join(missing_packages)}"))
                    self.root.after(0, lambda: self.log_message("开始安装缺失的系统包..."))
                    
                    # 系统包映射
                    system_package_map = {
                        'numpy': 'python3-numpy',
                        'cv2': 'python3-opencv',
                        'PIL': 'python3-pil',
                        'yaml': 'python3-yaml'
                    }
                    
                    # 只安装真正缺失的系统包
                    packages_to_install = []
                    for missing_pkg in missing_packages:
                        if missing_pkg in system_package_map:
                            packages_to_install.append(system_package_map[missing_pkg])
                    
                    if packages_to_install:
                        # 更新包列表
                        self.root.after(0, lambda: self.log_message("更新系统包列表..."))
                        stdin, stdout, stderr = ssh.exec_command('cd /root && apt update')
                        update_output = stdout.read().decode('utf-8')
                        update_error = stderr.read().decode('utf-8')
                        
                        if update_error and 'error' in update_error.lower():
                            self.root.after(0, lambda err=update_error: self.log_message(f"包列表更新警告: {err[:200]}"))
                        else:
                            self.root.after(0, lambda: self.log_message("✓ 包列表更新完成"))
                        
                        # 安装缺失的系统包
                        for pkg in packages_to_install:
                            self.root.after(0, lambda p=pkg: self.log_message(f"安装 {p}..."))
                            stdin, stdout, stderr = ssh.exec_command(f'cd /root && apt install -y {pkg}')
                            install_output = stdout.read().decode('utf-8')
                            install_error = stderr.read().decode('utf-8')
                            
                            if install_error and any(keyword in install_error.lower() for keyword in ['error', 'failed']):
                                self.root.after(0, lambda p=pkg, err=install_error: self.log_message(f"✗ {p} 安装失败: {err[:100]}"))
                            else:
                                self.root.after(0, lambda p=pkg: self.log_message(f"✓ {p} 安装完成"))
                
                # 处理pip包安装（torch和ultralytics）
                if pip_missing:
                    self.root.after(0, lambda: self.log_message(f"需要安装的深度学习包: {', '.join(pip_missing)}"))
                    self.root.after(0, lambda: self.log_message("使用pip安装PyTorch和ultralytics..."))
                    
                    # 首先诊断Python环境和pip配置
                    self.root.after(0, lambda: self.log_message("🔍 诊断Python环境和pip配置..."))
                    
                    # 检查Python和pip的一致性
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import sys; print(f\\"Python executable: {sys.executable}\\"); print(f\\"Python version: {sys.version}\\"); print(f\\"Python path: {sys.path}\\")"')
                    python_env_info = stdout.read().decode('utf-8').strip()
                    self.root.after(0, lambda info=python_env_info: self.log_message(f"Python环境信息:\n{info}"))
                    
                    # 检查pip安装路径
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -m pip show pip')
                    pip_info = stdout.read().decode('utf-8').strip()
                    if pip_info:
                        self.root.after(0, lambda info=pip_info: self.log_message(f"Pip信息:\n{info[:300]}..."))
                    
                    # 检查远程服务器Python版本并选择兼容的包版本
                    python_version_cmd = f'cd /root && {python_cmd} -c "import sys; print(str(sys.version_info.major) + \\".\\\" + str(sys.version_info.minor))"'
                    stdin, stdout, stderr = ssh.exec_command(python_version_cmd)
                    python_version = stdout.read().decode('utf-8').strip()
                    self.root.after(0, lambda ver=python_version: self.log_message(f"🐍 远程服务器Python版本: {ver}"))
                    
                    # 如果检测到Python 3.8，尝试升级到3.13.7或3.9+
                    if python_version == "3.8":
                        self.root.after(0, lambda: self.log_message("⚠️ 检测到Python 3.8，建议升级到3.13.7或3.9+以获得更好的兼容性"))
                        self.root.after(0, lambda: self.log_message("🔄 尝试升级Python版本..."))
                        
                        try:
                            upgraded_python_cmd = self.upgrade_python_version(ssh, python_cmd)
                            if upgraded_python_cmd:
                                python_cmd = upgraded_python_cmd
                                self.root.after(0, lambda: self.log_message("✅ Python版本升级成功"))
                                
                                # 重新检查升级后的Python版本
                                python_version_cmd = f'cd /root && {python_cmd} -c "import sys; print(str(sys.version_info.major) + \\".\\\" + str(sys.version_info.minor))"'
                                stdin, stdout, stderr = ssh.exec_command(python_version_cmd)
                                python_version = stdout.read().decode('utf-8').strip()
                                self.root.after(0, lambda ver=python_version: self.log_message(f"🐍 升级后Python版本: {ver}"))
                            else:
                                self.root.after(0, lambda: self.log_message("⚠️ Python版本升级失败，继续使用当前版本"))
                        except Exception as e:
                            self.root.after(0, lambda err=str(e): self.log_message(f"❌ Python版本升级过程中出现错误: {err}"))
                            self.root.after(0, lambda: self.log_message("继续使用当前Python版本进行包安装"))
                    
                    # 定义pip安装命令（确保使用相同的Python环境）
                    pip_install_commands = []
                    # 处理NumPy兼容性
                    try:
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import numpy; print(numpy.__version__)"')
                        numpy_version = stdout.read().decode('utf-8').strip()
                        if numpy_version and numpy_version.split('.')[0] >= '2' and python_version in ["3.8", "3.9"]:
                            fix_uninstall = f'{python_cmd} -m pip uninstall -y numpy || true'
                            fix_install = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "numpy==1.26.4"'
                            pip_install_commands.append(("卸载不兼容numpy", fix_uninstall))
                            pip_install_commands.append(("安装兼容numpy", fix_install))
                            self.root.after(0, lambda v=numpy_version: self.log_message(f"⚙ 检测到NumPy {v} 与Python {python_version}不兼容，已执行兼容修复"))
                    except Exception as _:
                        pass
                    if 'numpy' in missing_packages:
                        pip_install_commands.append(("安装numpy", f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "numpy==1.26.4"'))
                    # OpenCV 与 NumPy 兼容性：当 NumPy 选用 1.26.x 时，固定 OpenCV 版本
                    pip_install_commands.append(("安装兼容的opencv-python", f"{python_cmd} -m pip install --force-reinstall --no-cache-dir 'opencv-python==4.7.0.72'"))
                    if 'torch' in pip_missing:
                        # 检测GPU
                        has_gpu = False
                        try:
                            stdin, stdout, stderr = ssh.exec_command('nvidia-smi -L')
                            gpu_list = stdout.read().decode('utf-8').strip()
                            has_gpu = bool(gpu_list)
                        except Exception:
                            has_gpu = False
                        # 安装兼容的networkx版本
                        networkx_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "networkx==2.8.8"'
                        pip_install_commands.append(("安装兼容的networkx", networkx_cmd))
                        if has_gpu:
                            # 优先使用 cu121；如失败后续回退在验证阶段处理
                            cuda_index = 'https://download.pytorch.org/whl/cu121'
                            if python_version in ["3.8", "3.9"]:
                                torch_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.1.0" "torchvision==0.16.0" "torchaudio==2.1.0" --index-url {cuda_index}'
                            else:
                                torch_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.2.0" "torchvision==0.17.0" "torchaudio==2.2.0" --index-url {cuda_index}'
                            pip_install_commands.append(("安装PyTorch(CUDA)", torch_cmd))
                            self.root.after(0, lambda: self.log_message("⚙ 检测到GPU，安装CUDA版PyTorch"))
                        else:
                            if python_version in ["3.8", "3.9"]:
                                torch_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.0.1" "torchvision==0.15.2" "torchaudio==2.0.2" --index-url https://download.pytorch.org/whl/cpu'
                                self.root.after(0, lambda: self.log_message(f"🔧 使用稳定的PyTorch 2.0.1(CPU)（兼容Python {python_version}）"))
                            else:
                                torch_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.1.0" "torchvision==0.16.0" "torchaudio==2.1.0" --index-url https://download.pytorch.org/whl/cpu'
                                self.root.after(0, lambda: self.log_message(f"🚀 使用稳定的PyTorch 2.1.0(CPU)（适用于Python {python_version}）"))
                            pip_install_commands.append(("安装PyTorch(CPU)", torch_cmd))
                    
                    if 'ultralytics' in pip_missing:
                        # 为了确保稳定性，Python 3.8和3.9都使用经过验证的兼容版本
                        if python_version in ["3.8", "3.9"]:
                            # 使用稳定的ultralytics 8.0.196版本，兼容Python 3.8和3.9
                            ultralytics_cmd = f'timeout 90 {python_cmd} -m pip install --timeout 20 -i https://pypi.tuna.tsinghua.edu.cn/simple "ultralytics==8.0.196"'
                            self.root.after(0, lambda: self.log_message(f"🔧 使用稳定的ultralytics 8.0.196版本（兼容Python {python_version}）"))
                        else:
                            # 对于Python 3.10+，使用较新但稳定的版本
                            ultralytics_cmd = f'timeout 90 {python_cmd} -m pip install --timeout 20 -i https://pypi.tuna.tsinghua.edu.cn/simple "ultralytics==8.1.0"'
                            self.root.after(0, lambda: self.log_message(f"🚀 使用稳定的ultralytics 8.1.0版本（适用于Python {python_version}）"))
                        pip_install_commands.append(("安装ultralytics", ultralytics_cmd))
                    
                    if 'matplotlib' in pip_missing:
                        # 安装兼容的matplotlib版本，避免循环导入问题
                        if python_version in ["3.8", "3.9"]:
                            matplotlib_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "matplotlib==3.7.5"'
                            self.root.after(0, lambda: self.log_message(f"🔧 安装matplotlib 3.7.5（兼容Python {python_version} 与NumPy 1.26）"))
                        else:
                            matplotlib_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "matplotlib==3.8.4"'
                            self.root.after(0, lambda: self.log_message(f"🚀 安装matplotlib 3.8.4（适用于Python {python_version}）"))
                        
                        # 清理用户站点中残留的matplotlib，避免与系统site-packages冲突
                        user_cleanup_cmds = [
                            'rm -rf /root/.local/lib/python3.9/site-packages/matplotlib || true',
                            'rm -rf /root/.local/lib/python3.9/site-packages/matplotlib-* || true'
                        ]
                        for c in user_cleanup_cmds:
                            pip_install_commands.append(("清理用户站点matplotlib", c))
                        pip_install_commands.append(("安装matplotlib", matplotlib_cmd))
                    
                    # 执行pip包安装
                    if pip_install_commands:
                        self.root.after(0, lambda: self.log_message("开始安装深度学习包..."))
                        
                        # 如果需要安装matplotlib，先清理可能存在的冲突包
                        if 'matplotlib' in pip_missing:
                            self.root.after(0, lambda: self.log_message("🧹 彻底清理matplotlib包冲突..."))
                            
                            # 1. 强制卸载所有系统matplotlib相关包
                            system_cleanup_cmds = [
                                'apt remove -y python3-matplotlib python3-matplotlib-dev python3-matplotlib-data || true',
                                'apt purge -y python3-matplotlib python3-matplotlib-dev python3-matplotlib-data || true',
                                'apt autoremove -y || true',
                                'apt autoclean || true'
                            ]
                            
                            for cleanup_cmd in system_cleanup_cmds:
                                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {cleanup_cmd}')
                                stdout.channel.recv_exit_status()  # 等待完成
                            
                            # 2. 强制清理pip中的matplotlib及相关包
                            pip_cleanup_cmds = [
                                f'{python_cmd} -m pip uninstall -y matplotlib || true',
                                f'{python_cmd} -m pip uninstall -y matplotlib-base || true',
                                f'{python_cmd} -m pip uninstall -y matplotlib-inline || true',
                                f'{python_cmd} -m pip cache purge || true'
                            ]
                            
                            for pip_cleanup_cmd in pip_cleanup_cmds:
                                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {pip_cleanup_cmd}')
                                stdout.channel.recv_exit_status()  # 等待完成
                            
                            # 3. 手动删除残留的matplotlib目录
                            manual_cleanup_cmds = [
                                'rm -rf /usr/lib/python3/dist-packages/matplotlib* || true',
                                'rm -rf /usr/lib/python3/dist-packages/mpl_toolkits* || true',
                                'rm -rf /usr/local/lib/python3.9/dist-packages/matplotlib* || true',
                                'rm -rf /usr/local/lib/python3.9/dist-packages/mpl_toolkits* || true',
                            ]
                            
                            for manual_cmd in manual_cleanup_cmds:
                                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {manual_cmd}')
                                stdout.channel.recv_exit_status()  # 等待完成
                            
                            # 4. 临时重命名系统Python包目录，强制禁用系统包
                            system_disable_cmds = [
                                'mv /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages.disabled || true',
                                'mkdir -p /usr/lib/python3/dist-packages || true',  # 创建空目录避免错误
                            ]
                            
                            for disable_cmd in system_disable_cmds:
                                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {disable_cmd}')
                                stdout.channel.recv_exit_status()  # 等待完成
                            
                        self.root.after(0, lambda: self.log_message("✓ matplotlib彻底清理完成，系统包路径已禁用"))
                        
                        # 若服务器存在GPU但当前PyTorch为CPU版本，添加CUDA版重装命令
                        try:
                            stdin, stdout, stderr = ssh.exec_command('nvidia-smi -L')
                            gpu_list = stdout.read().decode('utf-8').strip()
                            has_gpu = bool(gpu_list)
                        except Exception:
                            has_gpu = False
                        if has_gpu:
                            try:
                                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import torch, json; print(json.dumps({{\"compiled\": (torch.version.cuda is not None), \"torch_ver\": str(torch.__version__)}}))"')
                                torch_cuda_info = stdout.read().decode('utf-8').strip()
                            except Exception:
                                torch_cuda_info = ''
                            need_cuda_reinstall = True
                            try:
                                import json as _json
                                obj = _json.loads(torch_cuda_info) if torch_cuda_info else {}
                                has_cuda_build = False
                                try:
                                    has_cuda_build = any(('PyTorch:' in s) and ('+cu' in s) for s in available_packages)
                                except Exception:
                                    has_cuda_build = False
                                need_cuda_reinstall = (not bool(obj.get('compiled'))) and (not has_cuda_build)
                            except Exception:
                                need_cuda_reinstall = True
                            if need_cuda_reinstall:
                                cuda_index = 'https://download.pytorch.org/whl/cu121'
                                if python_version in ["3.8", "3.9"]:
                                    reinstall_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.1.0" "torchvision==0.16.0" "torchaudio==2.1.0" --index-url {cuda_index}'
                                else:
                                    reinstall_cmd = f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.2.0" "torchvision==0.17.0" "torchaudio==2.2.0" --index-url {cuda_index}'
                                pip_install_commands.append(("重装PyTorch为CUDA版", reinstall_cmd))
                                self.root.after(0, lambda: self.log_message("🔁 检测到GPU但PyTorch不支持CUDA，追加CUDA版重装"))
                            else:
                                self.root.after(0, lambda: self.log_message("✓ 检测到CUDA版PyTorch，无需重装"))
                        
                        # 在执行安装前，若服务器存在GPU但当前PyTorch为CPU版本，追加CUDA版重装命令
                        pass

                        # 执行pip安装命令
                        for cmd_desc, cmd in pip_install_commands:
                            self.root.after(0, lambda desc=cmd_desc: self.log_message(f"执行: {desc}"))
                            self.root.after(0, lambda: self.log_message("⏳ 正在下载和安装，请耐心等待..."))
                            
                            # 添加详细的pip命令，包含进度显示
                            enhanced_cmd = cmd + " --progress-bar on --verbose"
                            
                            # 简化安装命令，避免复杂的实时读取
                            self.root.after(0, lambda: self.log_message(f"执行安装命令: {enhanced_cmd}"))
                            
                            # 使用简单的阻塞执行，避免复杂的异步读取问题
                            stdin, stdout, stderr = ssh.exec_command(f'cd /root && {enhanced_cmd}')
                            
                            # 等待命令完成
                            exit_status = stdout.channel.recv_exit_status()
                            
                            # 读取完整输出
                            install_output = stdout.read().decode('utf-8', errors='ignore')
                            install_errors = stderr.read().decode('utf-8', errors='ignore')
                            
                            # 显示安装结果
                            self.root.after(0, lambda: self.log_message(f"安装命令退出状态: {exit_status}"))
                            
                            if install_output:
                                # 显示重要的安装信息
                                output_lines = install_output.split('\n')
                                for line in output_lines:
                                    if line.strip():
                                        if any(keyword in line for keyword in ['Successfully installed', 'Downloading', 'Installing', 'Using cached']):
                                            self.root.after(0, lambda l=line.strip(): self.log_message(f"📦 {l}"))
                                        elif 'ERROR' in line or 'Failed' in line:
                                            self.root.after(0, lambda l=line.strip(): self.log_message(f"❌ {l}"))
                            
                            if install_errors:
                                # 显示错误信息（过滤警告）
                                error_lines = install_errors.split('\n')
                                for line in error_lines:
                                    if line.strip() and 'WARNING' not in line and 'warning' not in line.lower():
                                        self.root.after(0, lambda l=line.strip(): self.log_message(f"⚠️ {l}"))
                            
                            # 检查安装是否成功 - 基于退出状态和输出内容
                            success_indicators = [
                                "Successfully installed",
                                "Requirement already satisfied"
                            ]
                            
                            error_indicators = [
                                "ERROR",
                                "Failed",
                                "Could not find",
                                "No matching distribution",
                                "Connection error",
                                "Timeout"
                            ]
                            
                            has_success = any(indicator in install_output for indicator in success_indicators)
                            has_error = any(indicator in install_output or indicator in install_errors for indicator in error_indicators)
                            
                            # 综合判断安装是否成功
                            install_success = (exit_status == 0) and (has_success or not has_error)
                            
                            if install_success:
                                self.root.after(0, lambda desc=cmd_desc: self.log_message(f"✓ {desc} 完成"))
                                
                                # 显示关键安装信息
                                if install_output:
                                    success_lines = [line for line in install_output.split('\n') if any(ind in line for ind in success_indicators)]
                                    if success_lines:
                                        self.root.after(0, lambda lines=success_lines[-1]: self.log_message(f"📦 {lines}"))
                            else:
                                self.root.after(0, lambda desc=cmd_desc: self.log_message(f"✗ {desc} 失败 (退出状态: {exit_status})"))
                                
                                # 显示错误信息
                                if install_errors:
                                    self.root.after(0, lambda err=install_errors: self.log_message(f"❌ 错误: {err.strip()[:300]}"))
                                if install_output and has_error:
                                    error_lines = [line for line in install_output.split('\n') if any(err in line for err in error_indicators)]
                                    if error_lines:
                                        self.root.after(0, lambda lines=error_lines[0]: self.log_message(f"❌ 安装错误: {lines}"))
                                
                                # 尝试从本地Environment_package目录安装
                                self.root.after(0, lambda: self.log_message(f"🔄 网络安装失败，尝试从本地包安装..."))
                                local_install_success = self.try_local_package_install(ssh, cmd_desc, python_cmd)
                                
                                if local_install_success:
                                    self.root.after(0, lambda desc=cmd_desc: self.log_message(f"✅ {desc} 本地安装成功"))
                                    install_success = True  # 更新安装状态
                                else:
                                    self.root.after(0, lambda desc=cmd_desc: self.log_message(f"❌ {desc} 本地安装也失败"))
                                
                                # 立即测试包是否可以导入 - 只在安装成功时进行
                                if install_success:
                                    package_name = None
                                    if "PyTorch" in cmd_desc:
                                        package_name = "torch"
                                    elif "ultralytics" in cmd_desc:
                                        package_name = "ultralytics"
                                    
                                    if package_name and package_name in pip_packages:
                                        test_cmd = pip_packages[package_name].split(';')[0]  # 只取import部分
                                        escaped_test_cmd = test_cmd.replace('"', '\\"')
                                        test_full_cmd = f'cd /root && {python_cmd} -c "{escaped_test_cmd}"'
                                        
                                        stdin, stdout, stderr = ssh.exec_command(test_full_cmd)
                                        test_exit_status = stdout.channel.recv_exit_status()
                                        test_output = stdout.read().decode('utf-8').strip()
                                        test_error = stderr.read().decode('utf-8').strip()
                                        
                                        if test_exit_status == 0 and test_output and not test_error:
                                            self.root.after(0, lambda p=package_name, out=test_output: self.log_message(f"✅ {p} 导入测试成功: {out}"))
                                        else:
                                            self.root.after(0, lambda p=package_name, err=test_error: self.log_message(f"⚠ {p} 安装后导入测试失败: {err[:100]}"))
                        
                        # 强制刷新Python模块缓存
                        self.root.after(0, lambda: self.log_message("🔄 刷新Python模块缓存..."))
                        cache_refresh_cmd = f'cd /root && {python_cmd} -c "import sys; import importlib; importlib.invalidate_caches(); print(\\"模块缓存已刷新\\")"'
                        stdin, stdout, stderr = ssh.exec_command(cache_refresh_cmd)
                        cache_output = stdout.read().decode('utf-8').strip()
                        if cache_output:
                            self.root.after(0, lambda out=cache_output: self.log_message(f"✓ {out}"))
                        
                        # 验证安装的深度学习包 - 增强版验证
                        self.root.after(0, lambda: self.log_message("🔍 验证深度学习包安装结果..."))
                        
                        # 首先检查包是否在site-packages中
                        for package in pip_missing:
                            if package in pip_packages:
                                # 检查包是否在site-packages中
                                check_installed_cmd = f'cd /root && {python_cmd} -m pip show {package}'
                                stdin, stdout, stderr = ssh.exec_command(check_installed_cmd)
                                pip_show_output = stdout.read().decode('utf-8').strip()
                                pip_show_error = stderr.read().decode('utf-8').strip()
                                
                                if pip_show_output:
                                    self.root.after(0, lambda p=package, out=pip_show_output: self.log_message(f"📦 {p} pip信息:\n{out[:200]}..."))
                                else:
                                    self.root.after(0, lambda p=package, err=pip_show_error: self.log_message(f"⚠ {p} pip show失败: {err[:100]}"))
                                
                                # 尝试导入验证
                                verify_cmd = pip_packages[package]
                                # 使用双引号包围Python命令，并转义内部双引号
                                escaped_cmd = verify_cmd.replace('"', '\\"')
                                full_cmd = f'cd /root && {python_cmd} -c "{escaped_cmd}"'
                                
                                self.root.after(0, lambda p=package, cmd=full_cmd: self.log_message(f"执行验证命令: {cmd}"))
                                
                                stdin, stdout, stderr = ssh.exec_command(full_cmd)
                                verify_output = stdout.read().decode('utf-8').strip()
                                verify_error = stderr.read().decode('utf-8').strip()
                                
                                if verify_error:
                                    self.root.after(0, lambda p=package, err=verify_error: self.log_message(f"✗ {p} 验证失败: {err[:200]}"))
                                    
                                    # 如果验证失败，尝试诊断问题
                                    self.root.after(0, lambda p=package: self.log_message(f"🔧 诊断 {p} 安装问题..."))
                                    
                                    # 检查包文件是否存在
                                    find_package_cmd = f'cd /root && find /usr/local/lib/python*/site-packages -name "{package}*" -type d 2>/dev/null || find /root/.local/lib/python*/site-packages -name "{package}*" -type d 2>/dev/null'
                                    stdin, stdout, stderr = ssh.exec_command(find_package_cmd)
                                    find_output = stdout.read().decode('utf-8').strip()
                                    
                                    if find_output:
                                        self.root.after(0, lambda p=package, paths=find_output: self.log_message(f"📁 找到 {p} 包文件: {paths}"))
                                    else:
                                        self.root.after(0, lambda p=package: self.log_message(f"❌ 未找到 {p} 包文件"))
                                        
                                elif verify_output:
                                    self.root.after(0, lambda p=package, out=verify_output: self.log_message(f"✓ {p} 验证成功: {out}"))
                                else:
                                    self.root.after(0, lambda p=package: self.log_message(f"⚠ {p} 验证无输出，可能安装有问题"))
                else:
                    self.root.after(0, lambda: self.log_message("✅ 所有深度学习包都已安装"))
                    
                    # 诊断Python环境
                    self.root.after(0, lambda: self.log_message("诊断Python环境..."))
                    
                    # 检查Python路径和pip路径
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && which {python_cmd}')
                    python_path = stdout.read().decode('utf-8').strip()
                    
                    # 检查多种pip命令
                    pip_commands = [f'{python_cmd} -m pip', 'pip3', 'pip']
                    pip_info = ""
                    working_pip_cmd = None
                    
                    for pip_cmd in pip_commands:
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {pip_cmd} --version')
                        output = stdout.read().decode('utf-8').strip()
                        error = stderr.read().decode('utf-8').strip()
                        
                        if output and not error:
                            pip_info = output
                            working_pip_cmd = pip_cmd
                            break
                        elif error:
                            self.root.after(0, lambda cmd=pip_cmd, err=error: self.log_message(f"尝试 {cmd}: {err[:100]}"))
                    
                    # 如果没有找到pip，尝试安装
                    if not working_pip_cmd:
                        self.root.after(0, lambda: self.log_message("未找到pip，尝试安装..."))
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py && {python_cmd} get-pip.py')
                        install_output = stdout.read().decode('utf-8')
                        install_error = stderr.read().decode('utf-8')
                        
                        if install_error:
                            self.root.after(0, lambda err=install_error: self.log_message(f"pip安装失败: {err[:200]}"))
                        else:
                            working_pip_cmd = f'{python_cmd} -m pip'
                            self.root.after(0, lambda: self.log_message("pip安装成功"))
                    
                    # 训练前兼容性修复：若NumPy为2.x，降级并固定OpenCV版本以避免ABI不兼容
                    try:
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import numpy; print(numpy.__version__)"')
                        numpy_version = stdout.read().decode('utf-8').strip()
                        if numpy_version and numpy_version.split('.')[0] >= '2':
                            self.root.after(0, lambda v=numpy_version: self.log_message(f"⚠ 检测到NumPy {v} 可能与Torch/CV2不兼容，执行兼容修复..."))
                            for c in [
                                f'{python_cmd} -m pip uninstall -y numpy || true',
                                f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "numpy==1.26.4"',
                                f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "opencv-python==4.7.0.72"'
                            ]:
                                ssh.exec_command(f'cd /root && {c}')[1].channel.recv_exit_status()
                            stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import numpy, cv2; print(numpy.__version__); print(cv2.__version__)"')
                            verify_out = stdout.read().decode('utf-8').strip()
                            self.root.after(0, lambda o=verify_out: self.log_message(f"✓ 兼容修复完成: {o}"))
                    except Exception:
                        pass
                    
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import sys; print(sys.path)"')
                    sys_path = stdout.read().decode('utf-8').strip()
                    
                    self.root.after(0, lambda: self.log_message(f"Python路径: {python_path}"))
                    self.root.after(0, lambda: self.log_message(f"Pip信息: {pip_info}"))
                    self.root.after(0, lambda: self.log_message(f"工作的pip命令: {working_pip_cmd}"))
                    self.root.after(0, lambda: self.log_message(f"Python模块搜索路径: {sys_path}"))
                    
                    # 重新检查包安装情况
                    self.root.after(0, lambda: self.log_message("重新检查包安装情况..."))
                    
                    # 重新检查所有包
                    final_missing = []
                    final_available = []
                    
                    for package_name, import_cmd in pip_packages.items():
                        # 使用转义的命令格式避免语法错误
                        escaped_cmd = import_cmd.replace('"', '\\"')
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "{escaped_cmd}"')
                        package_info = stdout.read().decode('utf-8')
                        package_errors = stderr.read().decode('utf-8')
                        
                        if package_errors and 'ModuleNotFoundError' in package_errors:
                            final_missing.append(package_name)
                        elif package_info:
                            final_available.append(package_info.strip())
                    
                    if final_available:
                        self.root.after(0, lambda: self.log_message("✓ 最终已安装的包:"))
                        for pkg_info in final_available:
                            self.root.after(0, lambda info=pkg_info: self.log_message(f"  - {info}"))
                    
                    # 设置检查结果变量
                    package_info = '\n'.join(final_available) if final_available else ''
                    package_errors = f"仍然缺失的包: {', '.join(final_missing)}" if final_missing else ''
                
                if package_info:
                    self.root.after(0, lambda: self.log_message(f"✓ 包检查成功: {package_info.strip()}"))
                if package_errors:
                    if 'ModuleNotFoundError' in package_errors:
                        self.root.after(0, lambda: self.log_message(f"✗ 包安装失败，无法继续训练: {package_errors.strip()}"))
                        self.root.after(0, lambda: self.log_message("🔧 建议的解决方案:"))
                        self.root.after(0, lambda: self.log_message("  1. 使用'本地安装包'按钮上传预下载的.whl文件"))
                        self.root.after(0, lambda: self.log_message("  2. 检查服务器网络连接是否正常"))
                        self.root.after(0, lambda: self.log_message("  3. 尝试使用不同的pip镜像源"))
                        self.root.after(0, lambda: self.log_message("  4. 检查服务器磁盘空间是否充足"))
                        self.root.after(0, lambda: self.training_status_var.set("训练失败: 缺少必要的Python包"))
                        return
                    else:
                        self.root.after(0, lambda: self.log_message(f"⚠ 包检查警告: {package_errors.strip()}"))
                
                # 使用nohup在后台执行训练脚本，并将输出重定向到日志文件
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                log_file = f'/root/training_log_{timestamp}.txt'
                
                # 刷新Python模块缓存
                self.root.after(0, lambda: self.log_message("刷新Python模块缓存..."))
                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import importlib; importlib.invalidate_caches(); print(\\"缓存已刷新\\")"')
                cache_result = stdout.read().decode('utf-8').strip()
                self.root.after(0, lambda: self.log_message(f"缓存刷新结果: {cache_result}"))
                
                self.root.after(0, lambda: self.log_message("开始执行训练脚本..."))
                self.root.after(0, lambda: self.log_message(f"使用Python命令: {python_cmd}"))
                self.root.after(0, lambda: self.log_message(f"日志文件: {log_file}"))
                self.training_log_file = log_file
                
                stdin, stdout, stderr = ssh.exec_command('nvidia-smi -L')
                gpu_list = stdout.read().decode('utf-8').strip()
                has_gpu = bool(gpu_list)
                if has_gpu:
                    stdin, stdout, stderr = ssh.exec_command(
                        f'cd /root && {python_cmd} -c "import torch, json; info={{\"available\": bool(torch.cuda.is_available()), \"compiled\": (torch.version.cuda is not None), \"ver\": str(torch.version.cuda), \"torch_ver\": str(torch.__version__)}}; print(json.dumps(info))"'
                    )
                    torch_info_raw = stdout.read().decode('utf-8').strip()
                    need_cuda = True
                    try:
                        import json as _json
                        info_obj = _json.loads(torch_info_raw) if torch_info_raw else {}
                        has_cuda_build = False
                        try:
                            has_cuda_build = any(('PyTorch:' in s) and ('+cu' in s) for s in available_packages)
                        except Exception:
                            has_cuda_build = False
                        need_cuda = (not bool(info_obj.get('compiled'))) and (not has_cuda_build)
                        self.root.after(0, lambda: self.log_message(f"PyTorch CUDA状态: available={info_obj.get('available')} compiled={info_obj.get('compiled')} ver={info_obj.get('ver')}"))
                    except Exception:
                        need_cuda = True
                    if need_cuda:
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import sys; print(str(sys.version_info.major)+\".\"+str(sys.version_info.minor))"')
                        pyver = stdout.read().decode('utf-8').strip()
                        cuda_index = 'https://download.pytorch.org/whl/cu121'
                        install_cuda = (
                            f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.1.0" "torchvision==0.16.0" "torchaudio==2.1.0" --index-url {cuda_index}'
                            if pyver in ['3.8','3.9'] else
                            f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "torch==2.2.0" "torchvision==0.17.0" "torchaudio==2.2.0" --index-url {cuda_index}'
                        )
                        self.root.after(0, lambda: self.log_message('安装CUDA版PyTorch...'))
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {install_cuda}')
                        stdout.channel.recv_exit_status()
                        self.root.after(0, lambda: self.log_message('CUDA版PyTorch安装完成，验证...'))
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import torch, json; print(json.dumps({{\"compiled\": (torch.version.cuda is not None), \"available\": bool(torch.cuda.is_available()), \"ver\": str(torch.version.cuda)}}))"')
                        verify_cuda = stdout.read().decode('utf-8').strip()
                        self.root.after(0, lambda v=verify_cuda: self.log_message(f'PyTorch CUDA验证: {v}'))
                    else:
                        self.root.after(0, lambda: self.log_message('✓ 检测到CUDA版PyTorch，无需重复安装'))
                
                # 临时禁用系统site-packages，避免使用系统中的NumPy 2.x
                try:
                    stdin, stdout, stderr = ssh.exec_command('mv /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages.disabled 2>/dev/null || true')
                    stdout.channel.recv_exit_status()
                    stdin, stdout, stderr = ssh.exec_command('mkdir -p /usr/lib/python3/dist-packages || true')
                    stdout.channel.recv_exit_status()
                    self.root.after(0, lambda: self.log_message("已禁用系统site-packages，优先使用pip安装的包"))
                except Exception:
                    pass
                
                try:
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import numpy; print(numpy.__version__)"')
                    numpy_ver = stdout.read().decode('utf-8').strip()
                    need_fix_numpy = bool(numpy_ver) and numpy_ver.startswith('2')
                except Exception:
                    need_fix_numpy = True
                if need_fix_numpy:
                    for c in [
                        f'{python_cmd} -m pip uninstall -y numpy || true',
                        f'{python_cmd} -m pip install --force-reinstall --no-cache-dir "numpy==1.26.4"'
                    ]:
                        ssh.exec_command(f'cd /root && {c}')[1].channel.recv_exit_status()
                try:
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import cv2; print(cv2.__version__)"')
                    cv2_ver_out = stdout.read().decode('utf-8').strip()
                    cv2_err = stderr.read().decode('utf-8').strip()
                    if (not cv2_ver_out) or ('_ARRAY_API' in cv2_err):
                        ssh.exec_command(f'cd /root && {python_cmd} -m pip install --force-reinstall --no-cache-dir "opencv-python==4.7.0.72"')[1].channel.recv_exit_status()
                except Exception:
                    ssh.exec_command(f'cd /root && {python_cmd} -m pip install --force-reinstall --no-cache-dir "opencv-python==4.7.0.72"')[1].channel.recv_exit_status()
                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import numpy, cv2; print(numpy.__version__); print(cv2.__version__)"')
                final_ver = stdout.read().decode('utf-8').strip()
                self.root.after(0, lambda v=final_ver: self.log_message(f"✓ 运行环境确认: {v}"))
                
                # 执行训练命令，使用精确的环境控制，确保用户本地包可访问
                # 1. 设置PYTHONNOUSERSITE=0确保用户包可用
                # 2. 设置PYTHONPATH优先使用用户本地路径
                # 3. 使用-E标志忽略环境变量，但不使用-s标志（-s会禁用用户包）
                # 4. 移除-I标志，因为它会禁用用户站点包目录
                env_setup = [
                    'export PYTHONNOUSERSITE=0',
                    'export MPLBACKEND=Agg',
                    'export CUDA_VISIBLE_DEVICES=0',
                    'export PYTHONDONTWRITEBYTECODE=1',
                    'unset PYTHONSTARTUP',
                    'export PYTHONPATH=/usr/local/lib/python3.9/dist-packages:/root/.local/lib/python3.9/site-packages:$PYTHONPATH'
                ]
                env_vars = ' && '.join(env_setup)
                
                # 使用-u确保无缓冲输出，移除-E标志以确保PYTHONPATH环境变量生效
                isolated_python_cmd = f'{python_cmd} -u'
                run_name = f'yolo_training_{timestamp}'
                self.training_run_dir = f'/root/runs/train/{run_name}'
                training_cmd = f'cd /root && {env_vars} && nohup {isolated_python_cmd} training_script.py > {log_file} 2>&1 &'
                stdin, stdout, stderr = ssh.exec_command(training_cmd)
                
                # 等待命令启动
                time.sleep(2)
                
                # 检查进程是否启动
                stdin, stdout, stderr = ssh.exec_command(f'ps aux | grep "{python_cmd}.*training_script.py" | grep -v grep')
                process_info = stdout.read().decode('utf-8')
                if process_info:
                    self.root.after(0, lambda: self.log_message("✓ 训练进程已启动"))
                    self.root.after(0, lambda: self.log_message(f"进程信息: {process_info.strip()}"))
                else:
                    self.root.after(0, lambda: self.log_message("⚠ 未检测到训练进程，可能已经完成或失败"))
                
                # 开始监控训练日志
                self.root.after(0, lambda: self.log_message("开始监控训练日志..."))
                
                # 实时读取日志文件并解析训练进度
                import re
                log_position = 0
                total_epochs = None
                total_steps = None
                current_epoch = None
                current_step = None
                
                while True:
                    # 读取日志文件的新内容
                    stdin, stdout, stderr = ssh.exec_command(f'tail -c +{log_position + 1} {log_file} 2>/dev/null || echo "日志文件不存在"')
                    new_content = stdout.read().decode('utf-8', errors='ignore')
                    
                    if new_content and new_content.strip() != "日志文件不存在":
                        lines = new_content.split('\n')
                        for line in lines:
                            if line.strip():
                                self.root.after(0, lambda l=line: self.log_message(f"[训练] {l.strip()}"))
                                # 解析总epoch
                                m_total = re.search(r'Starting training for\s+(\d+)\s+epochs', line)
                                if m_total:
                                    try:
                                        total_epochs = int(m_total.group(1))
                                    except:
                                        pass
                                # 解析tqdm进度 例如 "0%| | 0/14"
                                m_step = re.search(r'(\d+)%\|.*?(\d+)/(\d+)', line)
                                if m_step:
                                    try:
                                        pct = int(m_step.group(1))
                                        current_step = int(m_step.group(2))
                                        total_steps = int(m_step.group(3))
                                        status = f"训练中: epoch={current_epoch if current_epoch is not None else '?'}  步骤 {current_step}/{total_steps}  {pct}%"
                                        self.root.after(0, lambda s=status: self.training_status_var.set(s))
                                    except:
                                        pass
                                # 粗略解析当前epoch行（出现Epoch表头时递增）
                                if 'Epoch' in line and 'GPU_mem' in line:
                                    if current_epoch is None:
                                        current_epoch = 0
                                    else:
                                        current_epoch += 1
                                    if total_epochs:
                                        status = f"训练中: epoch {current_epoch}/{total_epochs}"
                                        self.root.after(0, lambda s=status: self.training_status_var.set(s))
                        log_position += len(new_content.encode('utf-8'))
                    
                    # 检查训练是否还在运行
                    stdin, stdout, stderr = ssh.exec_command(f'ps aux | grep "{python_cmd}.*training_script.py" | grep -v grep')
                    process_check = stdout.read().decode('utf-8')
                    
                    if not process_check:
                        self.root.after(0, lambda: self.log_message("训练进程已结束"))
                        break
                    
                    time.sleep(1)  # 每秒检查一次
                
                # 获取最终的日志内容
                self.root.after(0, lambda: self.log_message("获取最终训练结果..."))
                stdin, stdout, stderr = ssh.exec_command(f'tail -50 {log_file} 2>/dev/null || echo "无法读取日志文件"')
                final_log = stdout.read().decode('utf-8', errors='ignore')
                if final_log:
                    self.root.after(0, lambda: self.log_message("=== 最终训练日志 ==="))
                    for line in final_log.split('\n'):
                        if line.strip():
                            self.root.after(0, lambda l=line: self.log_message(f"[最终] {l.strip()}"))
                
                # 检查是否有错误日志文件
                stdin, stdout, stderr = ssh.exec_command(f'ls -la /root/training_error_*.json 2>/dev/null || echo "无错误文件"')
                error_files = stdout.read().decode('utf-8')
                if "training_error_" in error_files:
                    self.root.after(0, lambda: self.log_message("发现错误日志文件:"))
                    self.root.after(0, lambda: self.log_message(error_files.strip()))
                
                # 恢复系统包目录，避免影响其他系统功能
                try:
                    stdin, stdout, stderr = ssh.exec_command('mv /usr/lib/python3/dist-packages.disabled /usr/lib/python3/dist-packages 2>/dev/null || true')
                    stdout.channel.recv_exit_status()
                    self.root.after(0, lambda: self.log_message("✓ 系统包目录已恢复"))
                except:
                    pass  # 忽略恢复错误
                
                ssh.close()
                
                self.root.after(0, lambda: self.training_status_var.set("训练完成"))
                self.is_training = False
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: self.training_status_var.set(f"训练失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: self.log_message(f"训练失败: {msg}"))
                self.is_training = False
        
        threading.Thread(target=training_thread, daemon=True).start()
    
    def start_monitoring(self):
        """开始监控"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        if self.is_monitoring:
            messagebox.showinfo("提示", "监控已在运行中")
            return
        
        def monitoring_thread():
            self.is_monitoring = True
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                while self.is_monitoring:
                    # 检查GPU状态
                    stdin, stdout, stderr = ssh.exec_command('nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits')
                    gpu_info = stdout.read().decode().strip()
                    
                    if gpu_info:
                        self.root.after(0, lambda info=gpu_info: self.log_message(f"GPU状态: {info}"))
                    
                    # 检查训练进程
                    stdin, stdout, stderr = ssh.exec_command('ps aux | grep python | grep -v grep')
                    process_info = stdout.read().decode().strip()
                    
                    if 'training_script.py' in process_info:
                        self.root.after(0, lambda: self.log_message("训练进程运行中"))
                    
                    time.sleep(30)  # 每30秒检查一次
                
                ssh.close()
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"监控失败: {e}"))
            finally:
                self.is_monitoring = False
        
        threading.Thread(target=monitoring_thread, daemon=True).start()
        
        # 同时启动系统监控
        self.start_system_monitoring()
        
        self.log_message("开始监控训练状态")
    
    def stop_monitoring(self):
        """停止监控"""
        if not self.is_monitoring:
            messagebox.showinfo("提示", "监控未在运行")
            return
        
        if messagebox.askyesno("确认", "确定要停止监控吗？"):
            self.is_monitoring = False
            self.stop_system_monitoring()
            self.log_message("已停止监控")
            messagebox.showinfo("提示", "监控已停止")
    
    def stop_training(self):
        """停止训练"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        if messagebox.askyesno("确认", "确定要停止训练吗？"):
            def stop_thread():
                try:
                    ssh = paramiko.SSHClient()
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    
                    connect_params = {
                        'hostname': self.server_config['hostname'],
                        'port': self.server_config['port'],
                        'username': self.server_config['username']
                    }
                    
                    if self.server_config['key_file']:
                        connect_params['key_filename'] = self.server_config['key_file']
                    else:
                        connect_params['password'] = self.server_config['password']
                    
                    ssh.connect(**connect_params)
                    
                    # 停止训练进程
                    ssh.exec_command('pkill -f training_script.py')
                    
                    ssh.close()
                    
                    self.is_training = False
                    self.is_monitoring = False
                    
                    # 停止系统监控
                    self.root.after(0, self.stop_system_monitoring)
                    
                    self.root.after(0, lambda: self.training_status_var.set("已停止"))
                    self.root.after(0, lambda: self.log_message("训练已停止"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"停止训练失败: {e}"))
            
            threading.Thread(target=stop_thread, daemon=True).start()
    
    def download_models(self):
        """查询服务器内所有模型文件并选择下载"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        # 创建查询进度窗口
        query_window = tk.Toplevel(self.root)
        query_window.title("查询模型文件")
        query_window.geometry("400x150")
        query_window.transient(self.root)
        query_window.grab_set()
        
        # 居中显示
        query_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # 查询进度界面
        tk.Label(query_window, text="正在查询服务器模型文件...", font=("Arial", 10)).pack(pady=20)
        
        query_progress = ttk.Progressbar(query_window, mode='indeterminate')
        query_progress.pack(pady=10, padx=20, fill='x')
        query_progress.start()
        
        cancel_btn = ttk.Button(query_window, text="取消", command=query_window.destroy)
        cancel_btn.pack(pady=10)
        
        def query_models_thread():
            try:
                model_info = self.query_all_models()
                query_window.after(0, lambda: self.show_model_selection_window(model_info, query_window))
            except Exception as e:
                query_window.after(0, lambda: self.handle_model_query_error(str(e), query_window))
        
        import threading
        thread = threading.Thread(target=query_models_thread, daemon=True)
        thread.start()
    
    def delete_models(self):
        """删除服务器模型文件"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        
        # 创建查询进度窗口
        query_window = tk.Toplevel(self.root)
        query_window.title("查询模型文件")
        query_window.geometry("400x150")
        query_window.transient(self.root)
        query_window.grab_set()
        
        # 居中显示
        query_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # 查询进度界面
        tk.Label(query_window, text="正在查询服务器模型文件...", font=("Arial", 10)).pack(pady=20)
        
        query_progress = ttk.Progressbar(query_window, mode='indeterminate')
        query_progress.pack(pady=10, padx=20, fill='x')
        query_progress.start()
        
        cancel_btn = ttk.Button(query_window, text="取消", command=query_window.destroy)
        cancel_btn.pack(pady=10)
        
        def query_models_thread():
            try:
                model_info = self.query_all_models()
                query_window.after(0, lambda: self.show_model_deletion_window(model_info, query_window))
            except Exception as e:
                query_window.after(0, lambda: self.handle_model_query_error(str(e), query_window))
        
        import threading
        thread = threading.Thread(target=query_models_thread, daemon=True)
        thread.start()
    
    def show_model_deletion_window(self, model_info, query_window):
        """显示模型删除选择窗口"""
        query_window.destroy()
        
        if not model_info:
            messagebox.showinfo("信息", "服务器上没有找到模型文件")
            return
        
        # 创建模型删除窗口
        delete_window = tk.Toplevel(self.root)
        delete_window.title("删除模型文件")
        delete_window.geometry("800x600")
        delete_window.transient(self.root)
        delete_window.grab_set()
        
        # 居中显示
        delete_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # 标题和警告
        title_frame = ttk.Frame(delete_window)
        title_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(title_frame, text="选择要删除的模型文件", font=("Arial", 14, "bold")).pack()
        ttk.Label(title_frame, text="⚠️ 警告：删除操作不可恢复，请谨慎选择！", 
                 font=("Arial", 10), foreground="red").pack(pady=5)
        
        # 模型列表框架
        list_frame = ttk.Frame(delete_window)
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 创建Treeview显示模型
        columns = ('size', 'date', 'path')
        model_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        model_tree.heading('#0', text='模型文件名')
        model_tree.heading('size', text='文件大小')
        model_tree.heading('date', text='创建时间')
        model_tree.heading('path', text='文件路径')
        
        model_tree.column('#0', width=200)
        model_tree.column('size', width=100)
        model_tree.column('date', width=150)
        model_tree.column('path', width=300)
        
        # 滚动条
        tree_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=model_tree.yview)
        model_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        model_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # 填充模型数据
        for model in model_info:
            filename = os.path.basename(model['path'])
            model_tree.insert('', 'end', text=filename, 
                            values=(model['size'], model['date'], model['path']))
        
        # 选择控制框架
        control_frame = ttk.Frame(delete_window)
        control_frame.pack(fill='x', padx=20, pady=10)
        
        # 选择按钮
        select_frame = ttk.Frame(control_frame)
        select_frame.pack(side='left')
        
        def select_all():
            for item in model_tree.get_children():
                model_tree.selection_add(item)
        
        def deselect_all():
            model_tree.selection_remove(model_tree.selection())
        
        ttk.Button(select_frame, text="全选", command=select_all).pack(side='left', padx=5)
        ttk.Button(select_frame, text="取消全选", command=deselect_all).pack(side='left', padx=5)
        
        # 操作按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side='right')
        
        def delete_selected():
            selected_items = model_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请选择要删除的模型文件")
                return
            
            # 获取选中的模型信息
            selected_models = []
            for item in selected_items:
                values = model_tree.item(item, 'values')
                filename = model_tree.item(item, 'text')
                selected_models.append({
                    'filename': filename,
                    'path': values[2],
                    'size': values[0]
                })
            
            # 确认删除
            confirm_msg = f"确定要删除以下 {len(selected_models)} 个模型文件吗？\n\n"
            for model in selected_models[:5]:  # 只显示前5个
                confirm_msg += f"• {model['filename']} ({model['size']})\n"
            if len(selected_models) > 5:
                confirm_msg += f"... 还有 {len(selected_models) - 5} 个文件"
            
            if messagebox.askyesno("确认删除", confirm_msg):
                delete_window.destroy()
                self.execute_model_deletion(selected_models)
        
        ttk.Button(button_frame, text="删除选中", command=delete_selected).pack(side='right', padx=5)
        ttk.Button(button_frame, text="取消", command=delete_window.destroy).pack(side='right', padx=5)
    
    def execute_model_deletion(self, selected_models):
        """执行模型删除操作"""
        # 创建删除进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("删除模型")
        progress_window.geometry("600x400")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # 进度显示
        tk.Label(progress_window, text="正在删除模型文件...", font=("Arial", 12)).pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
        progress_bar.pack(fill='x', padx=20, pady=10)
        
        # 删除日志
        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        log_text = tk.Text(log_frame, wrap='word', font=('Consolas', 9))
        log_scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=log_text.yview)
        log_text.configure(yscrollcommand=log_scrollbar.set)
        
        log_text.pack(side='left', fill='both', expand=True)
        log_scrollbar.pack(side='right', fill='y')
        
        # 状态显示
        status_frame = ttk.Frame(progress_window)
        status_frame.pack(fill='x', padx=20, pady=5)
        
        status_var = tk.StringVar(value="准备删除...")
        ttk.Label(status_frame, textvariable=status_var).pack(side='left')
        
        deleted_count_var = tk.StringVar(value="0/0")
        ttk.Label(status_frame, textvariable=deleted_count_var).pack(side='right')
        
        def deletion_thread():
            try:
                import paramiko
                
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                total_models = len(selected_models)
                deleted_count = 0
                
                for i, model in enumerate(selected_models):
                    # 更新进度
                    progress = (i / total_models) * 100
                    self.root.after(0, lambda p=progress: progress_var.set(p))
                    
                    # 更新状态
                    self.root.after(0, lambda m=model: status_var.set(f"正在删除: {m['filename']}"))
                    self.root.after(0, lambda d=deleted_count, t=total_models: 
                                  deleted_count_var.set(f"{d}/{t}"))
                    
                    # 添加日志
                    self.root.after(0, lambda m=model: 
                                  log_text.insert(tk.END, f"正在删除: {m['filename']}\n路径: {m['path']}\n"))
                    self.root.after(0, lambda: log_text.see(tk.END))
                    
                    try:
                        # 执行删除命令
                        stdin, stdout, stderr = ssh.exec_command(f'rm -f "{model["path"]}"')
                        stdout.read()  # 等待命令完成
                        
                        error_output = stderr.read().decode('utf-8', errors='ignore')
                        if error_output:
                            self.root.after(0, lambda m=model, e=error_output: 
                                          log_text.insert(tk.END, f"删除 {m['filename']} 失败: {e}\n"))
                        else:
                            deleted_count += 1
                            self.root.after(0, lambda m=model: 
                                          log_text.insert(tk.END, f"✓ 已删除: {m['filename']}\n"))
                    
                    except Exception as e:
                        self.root.after(0, lambda m=model, err=str(e): 
                                      log_text.insert(tk.END, f"删除 {m['filename']} 失败: {err}\n"))
                    
                    self.root.after(0, lambda: log_text.insert(tk.END, "\n"))
                
                # 完成删除
                self.root.after(0, lambda: progress_var.set(100))
                self.root.after(0, lambda: status_var.set("删除完成"))
                self.root.after(0, lambda d=deleted_count, t=total_models: 
                              deleted_count_var.set(f"{d}/{t}"))
                self.root.after(0, lambda: log_text.insert(tk.END, f"删除完成！成功删除 {deleted_count}/{total_models} 个模型文件\n"))
                self.root.after(0, lambda: messagebox.showinfo("完成", f"删除完成！成功删除 {deleted_count}/{total_models} 个模型文件"))
                
                ssh.close()
                
            except Exception as e:
                self.root.after(0, lambda: log_text.insert(tk.END, f"\n删除失败: {str(e)}\n"))
                self.root.after(0, lambda: messagebox.showerror("错误", f"删除失败: {str(e)}"))
        
        import threading
        threading.Thread(target=deletion_thread, daemon=True).start()
        
        # 关闭按钮
        ttk.Button(progress_window, text="关闭", command=progress_window.destroy).pack(pady=10)
    
    def query_all_models(self):
        """查询服务器内所有模型文件和创建时间"""
        import paramiko
        
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_params = {
            'hostname': self.server_config['hostname'],
            'port': self.server_config['port'],
            'username': self.server_config['username']
        }
        
        if self.server_config['key_file']:
            connect_params['key_filename'] = self.server_config['key_file']
        else:
            connect_params['password'] = self.server_config['password']
        
        ssh.connect(**connect_params, timeout=30)
        
        model_info = []
        
        try:
            # 查找所有.pt模型文件
            cmd = 'find /root -name "*.pt" -type f -exec ls -la {} + 2>/dev/null | sort -k9'
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8', errors='ignore').strip()
            
            if output:
                lines = output.split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split()
                        if len(parts) >= 9:
                            # 解析文件信息
                            permissions = parts[0]
                            size = parts[4]
                            date = f"{parts[5]} {parts[6]} {parts[7]}"
                            file_path = ' '.join(parts[8:])
                            file_name = os.path.basename(file_path)
                            
                            # 获取文件大小（MB）
                            try:
                                size_mb = round(int(size) / (1024 * 1024), 2)
                            except:
                                size_mb = 0
                            
                            model_info.append({
                                'name': file_name,
                                'path': file_path,
                                'size': f"{size_mb} MB",
                                'date': date,
                                'permissions': permissions
                            })
            
            # 如果没有找到模型文件，查找可能的训练目录
            if not model_info:
                stdin, stdout, stderr = ssh.exec_command('find /root -type d -name "*train*" -o -name "*runs*" 2>/dev/null')
                dirs = stdout.read().decode('utf-8', errors='ignore').strip()
                if dirs:
                    model_info.append({
                        'name': '未找到模型文件',
                        'path': '但发现以下训练目录：\n' + dirs,
                        'size': '-',
                        'date': '-',
                        'permissions': '-'
                    })
        
        finally:
            ssh.close()
        
        return model_info
    
    def show_model_selection_window(self, model_info, query_window):
        """显示模型选择窗口"""
        query_window.destroy()
        
        if not model_info:
            messagebox.showinfo("信息", "服务器上未找到任何模型文件")
            return
        
        # 创建模型选择窗口
        selection_window = tk.Toplevel(self.root)
        selection_window.title("选择要下载的模型")
        selection_window.geometry("800x600")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        # 居中显示
        selection_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # 标题框架
        title_frame = ttk.Frame(selection_window)
        title_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(title_frame, text="选择要下载的模型文件", font=("Arial", 14, "bold")).pack()
        ttk.Label(title_frame, text="💾 选择需要下载的模型文件到本地", 
                 font=("Arial", 10), foreground="blue").pack(pady=5)
        
        # 模型列表框架
        list_frame = ttk.Frame(selection_window)
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # 创建Treeview显示模型信息
        columns = ('size', 'date', 'path')
        model_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings')
        
        # 设置列标题
        model_tree.heading('#0', text='模型文件名')
        model_tree.heading('size', text='文件大小')
        model_tree.heading('date', text='创建时间')
        model_tree.heading('path', text='文件路径')
        
        # 设置列宽
        model_tree.column('#0', width=200)
        model_tree.column('size', width=100)
        model_tree.column('date', width=150)
        model_tree.column('path', width=300)
        
        # 滚动条
        tree_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=model_tree.yview)
        model_tree.configure(yscrollcommand=tree_scrollbar.set)
        
        model_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        # 填充模型数据
        for model in model_info:
            filename = os.path.basename(model['path']) if model['path'] else model['name']
            model_tree.insert('', 'end', text=filename, 
                            values=(model['size'], model['date'], model['path']))
        
        # 选择控制框架
        control_frame = ttk.Frame(selection_window)
        control_frame.pack(fill='x', padx=20, pady=10)
        
        # 选择按钮
        select_frame = ttk.Frame(control_frame)
        select_frame.pack(side='left')
        
        def select_all():
            for item in model_tree.get_children():
                model_tree.selection_add(item)
        
        def deselect_all():
            model_tree.selection_remove(model_tree.selection())
        
        ttk.Button(select_frame, text="全选", command=select_all).pack(side='left', padx=5)
        ttk.Button(select_frame, text="取消全选", command=deselect_all).pack(side='left', padx=5)
        
        # 操作按钮
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side='right')
        
        def start_download():
            selected_items = model_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请至少选择一个模型文件")
                return
            
            # 选择本地保存目录
            local_dir = filedialog.askdirectory(title="选择模型保存目录")
            if not local_dir:
                return
            
            # 获取选中的模型信息
            selected_model_info = []
            for item in selected_items:
                values = model_tree.item(item, 'values')
                filename = model_tree.item(item, 'text')
                # 根据文件名在原始数据中查找对应的模型信息
                for model in model_info:
                    if (os.path.basename(model['path']) if model['path'] else model['name']) == filename:
                        selected_model_info.append(model)
                        break
            
            if selected_model_info:
                selection_window.destroy()
                self.download_selected_models(selected_model_info, local_dir)
        
        ttk.Button(button_frame, text="下载选中模型", command=start_download).pack(side='right', padx=5)
        ttk.Button(button_frame, text="取消", command=selection_window.destroy).pack(side='right', padx=5)
    
    def download_selected_models(self, selected_models, local_dir):
        """下载选中的模型文件"""
        # 创建下载进度窗口
        progress_window = tk.Toplevel(self.root)
        progress_window.title("下载模型")
        progress_window.geometry("500x200")
        progress_window.transient(self.root)
        progress_window.grab_set()
        
        # 居中显示
        progress_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        # 进度界面
        tk.Label(progress_window, text=f"正在下载 {len(selected_models)} 个模型文件...", 
                font=("Arial", 10)).pack(pady=10)
        
        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=450)
        progress_bar.pack(pady=10)
        
        status_label = tk.Label(progress_window, text="准备下载...", font=("Arial", 9))
        status_label.pack(pady=5)
        
        # 文件列表显示
        file_list_frame = ttk.Frame(progress_window)
        file_list_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        file_listbox = tk.Listbox(file_list_frame, height=6)
        file_scrollbar = ttk.Scrollbar(file_list_frame, orient='vertical', command=file_listbox.yview)
        file_listbox.configure(yscrollcommand=file_scrollbar.set)
        
        file_listbox.pack(side='left', fill='both', expand=True)
        file_scrollbar.pack(side='right', fill='y')
        
        # 取消按钮
        cancel_flag = {'cancelled': False}
        def cancel_download():
            cancel_flag['cancelled'] = True
            progress_window.destroy()
        
        cancel_btn = ttk.Button(progress_window, text="取消", command=cancel_download)
        cancel_btn.pack(pady=5)
        
        def download_thread():
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                else:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                
                downloaded_files = []
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                with SCPClient(ssh.get_transport()) as scp:
                    for i, model in enumerate(selected_models):
                        if cancel_flag['cancelled']:
                            break
                        
                        # 更新状态
                        self.root.after(0, lambda name=model['name']: 
                                      status_label.config(text=f"正在下载: {name}"))
                        
                        # 本地文件名
                        name_without_ext = os.path.splitext(model['name'])[0]
                        local_filename = f"{name_without_ext}_{timestamp}.pt"
                        local_file = os.path.join(local_dir, local_filename)
                        
                        try:
                            # 下载文件
                            scp.get(model['path'], local_file)
                            downloaded_files.append(local_filename)
                            
                            # 更新文件列表
                            self.root.after(0, lambda f=local_filename: 
                                          file_listbox.insert(tk.END, f"✓ {f}"))
                            
                            self.root.after(0, lambda f=local_filename: 
                                          self.log_message(f"已下载: {f}"))
                            
                        except Exception as e:
                            self.root.after(0, lambda f=model['name'], err=str(e): 
                                          file_listbox.insert(tk.END, f"✗ {f} - 失败: {err}"))
                        
                        # 更新进度
                        progress = (i + 1) * 100 / len(selected_models)
                        self.root.after(0, lambda p=progress: progress_var.set(p))
                
                if not cancel_flag['cancelled']:
                    self.root.after(0, lambda: status_label.config(text="下载完成！"))
                    self.root.after(0, lambda: self.log_message(
                        f"模型下载完成，成功下载 {len(downloaded_files)} 个文件"))
                    
                    # 3秒后关闭进度窗口
                    self.root.after(3000, progress_window.destroy)
                else:
                    self.root.after(0, lambda: self.log_message("下载已取消"))
                
                ssh.close()
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"下载模型失败: {e}"))
                self.root.after(0, progress_window.destroy)
        
        import threading
        threading.Thread(target=download_thread, daemon=True).start()
    
    def handle_model_query_error(self, error_msg, query_window):
        """处理模型查询错误"""
        query_window.destroy()
        messagebox.showerror("错误", f"查询模型文件失败:\n{error_msg}")
    
    def init_monitoring_charts(self):
        """初始化监控图表"""
        # 设置matplotlib样式
        plt.style.use('seaborn-v0_8-darkgrid')
        
        # 调整图表大小为原来的1/4（缩小图表）
        chart_width, chart_height = 2.5, 1.8
        
        # GPU利用率监控图表
        self.monitoring_figures['gpu_util'] = Figure(figsize=(chart_width, chart_height), dpi=80)
        self.monitoring_figures['gpu_util'].patch.set_facecolor('white')
        ax_gpu_util = self.monitoring_figures['gpu_util'].add_subplot(111)
        ax_gpu_util.set_title('GPU利用率', fontsize=9)
        ax_gpu_util.set_ylabel('利用率 (%)', fontsize=7)
        ax_gpu_util.set_ylim(0, 100)
        ax_gpu_util.grid(True, alpha=0.3)
        ax_gpu_util.tick_params(axis='both', which='major', labelsize=6)
        
        self.monitoring_canvases['gpu_util'] = FigureCanvasTkAgg(self.monitoring_figures['gpu_util'], self.gpu_utilization_frame)
        self.monitoring_canvases['gpu_util'].get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # GPU显存监控图表
        self.monitoring_figures['gpu_memory'] = Figure(figsize=(chart_width, chart_height), dpi=80)
        self.monitoring_figures['gpu_memory'].patch.set_facecolor('white')
        ax_gpu_memory = self.monitoring_figures['gpu_memory'].add_subplot(111)
        ax_gpu_memory.set_title('GPU显存使用率', fontsize=9)
        ax_gpu_memory.set_ylabel('使用率 (%)', fontsize=7)
        ax_gpu_memory.set_ylim(0, 100)
        ax_gpu_memory.grid(True, alpha=0.3)
        ax_gpu_memory.tick_params(axis='both', which='major', labelsize=6)
        
        self.monitoring_canvases['gpu_memory'] = FigureCanvasTkAgg(self.monitoring_figures['gpu_memory'], self.gpu_memory_frame)
        self.monitoring_canvases['gpu_memory'].get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # CPU使用率监控图表
        self.monitoring_figures['cpu'] = Figure(figsize=(chart_width, chart_height), dpi=80)
        self.monitoring_figures['cpu'].patch.set_facecolor('white')
        ax_cpu = self.monitoring_figures['cpu'].add_subplot(111)
        ax_cpu.set_title('CPU使用率', fontsize=9)
        ax_cpu.set_ylabel('使用率 (%)', fontsize=7)
        ax_cpu.set_ylim(0, 100)
        ax_cpu.grid(True, alpha=0.3)
        ax_cpu.tick_params(axis='both', which='major', labelsize=6)
        
        self.monitoring_canvases['cpu'] = FigureCanvasTkAgg(self.monitoring_figures['cpu'], self.cpu_frame)
        self.monitoring_canvases['cpu'].get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 内存使用率监控图表
        self.monitoring_figures['memory'] = Figure(figsize=(chart_width, chart_height), dpi=80)
        self.monitoring_figures['memory'].patch.set_facecolor('white')
        ax_memory = self.monitoring_figures['memory'].add_subplot(111)
        ax_memory.set_title('内存使用率', fontsize=9)
        ax_memory.set_ylabel('使用率 (%)', fontsize=7)
        ax_memory.set_ylim(0, 100)
        ax_memory.grid(True, alpha=0.3)
        ax_memory.tick_params(axis='both', which='major', labelsize=6)
        
        self.monitoring_canvases['memory'] = FigureCanvasTkAgg(self.monitoring_figures['memory'], self.memory_frame)
        self.monitoring_canvases['memory'].get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # 初始化空数据
        self.update_monitoring_charts()
    
    def start_system_monitoring(self):
        """开始系统监控"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
            
        self.is_monitoring = True
        self.monitoring_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        self.log_message("系统监控已启动")
    
    def stop_system_monitoring(self):
        """停止系统监控"""
        self.is_monitoring = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1)
        self.log_message("系统监控已停止")
    
    def monitoring_loop(self):
        """监控循环"""
        while self.is_monitoring and self.is_connected:
            try:
                # 检查SSH连接状态
                ssh_status = "已连接" if self.ssh_client and self.ssh_client.get_transport() and self.ssh_client.get_transport().is_active() else "未连接"
                
                if ssh_status == "未连接":
                    self.root.after(0, lambda: self.log_message("⚠️ SSH连接已断开，尝试重新连接..."))
                    # 直接在这里重新建立SSH连接，而不是调用test_connection()
                    try:
                        if self.ssh_client:
                            try:
                                self.ssh_client.close()
                            except:
                                pass
                        
                        ssh = paramiko.SSHClient()
                        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                        
                        connect_params = {
                            'hostname': self.server_config['hostname'],
                            'port': self.server_config['port'],
                            'username': self.server_config['username']
                        }
                        
                        if self.server_config['key_file']:
                            connect_params['key_filename'] = self.server_config['key_file']
                        else:
                            connect_params['password'] = self.server_config['password']
                        
                        ssh.connect(**connect_params, timeout=15)
                        self.ssh_client = ssh
                        self.root.after(0, lambda: self.log_message("✅ SSH重连成功"))
                        
                    except Exception as e:
                        self.root.after(0, lambda: self.log_message(f"❌ SSH重连失败: {str(e)}，监控数据将显示为0"))
                        time.sleep(5)
                        continue
                
                # 获取系统监控数据
                gpu_util = self.get_gpu_utilization()
                gpu_memory = self.get_gpu_memory_usage()
                cpu_usage = self.get_cpu_usage()
                memory_usage = self.get_memory_usage()
                
                # 详细调试信息：记录SSH状态和获取到的数值（限速）
                now = time.time()
                if now - self._last_monitor_log >= 10:
                    debug_msg = f"SSH状态: {ssh_status} | 监控数据 - GPU利用率: {gpu_util}%, GPU显存: {gpu_memory}%, CPU: {cpu_usage}%, 内存: {memory_usage}%"
                    self.root.after(0, lambda msg=debug_msg: self.log_message(msg))
                    self._last_monitor_log = now
                
                # 添加数据到队列
                current_time = time.time()
                self.time_data.append(current_time)
                self.gpu_utilization_data.append(gpu_util)
                self.gpu_memory_data.append(gpu_memory)
                self.cpu_data.append(cpu_usage)
                self.memory_data.append(memory_usage)
                
                # 更新图表（合并刷新，限速）
                self._schedule_monitor_update()
                # 更新训练进度（从日志或结果文件解析），每2秒一次
                if time.time() - self._last_progress_update >= 2:
                    self._update_training_progress()
                    self._last_progress_update = time.time()

                time.sleep(1)
                
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"监控数据获取失败: {e}"))
                time.sleep(5)  # 出错时等待5秒再重试
    
    def get_gpu_memory_usage(self):
        """获取GPU显存使用率"""
        try:
            if not self.ssh_client:
                return 0
                
            stdin, stdout, stderr = self.ssh_client.exec_command('nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits')
            output = stdout.read().decode().strip()
            
            if output:
                lines = output.split('\n')
                if lines:
                    used, total = map(int, lines[0].split(', '))
                    return (used / total) * 100 if total > 0 else 0
            return 0
        except:
            return 0
    
    def get_gpu_utilization(self):
        """获取GPU利用率"""
        try:
            if not self.ssh_client:
                return 0
                
            stdin, stdout, stderr = self.ssh_client.exec_command('nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits')
            output = stdout.read().decode().strip()
            
            if output:
                lines = output.split('\n')
                if lines:
                    utilization = int(lines[0])
                    return utilization
            return 0
        except:
            return 0
    
    def get_cpu_usage(self):
        """获取CPU使用率"""
        try:
            if not self.ssh_client:
                if hasattr(self, 'log_message'):
                    self.root.after(0, lambda: self.log_message("🔍 CPU监控: SSH客户端未连接"))
                return 0
                
            # 使用更可靠的CPU使用率获取方法
            cmd1 = "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'"
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd1)
            output = stdout.read().decode().strip()
            error_output = stderr.read().decode().strip()
            
            if self.debug_monitor and hasattr(self, 'log_message'):
                self.root.after(0, lambda: self.log_message(f"🔍 CPU命令1输出: '{output}', 错误: '{error_output}'"))
            
            if output and output.replace('.', '').replace('-', '').isdigit():
                cpu_usage = float(output)
                return min(max(cpu_usage, 0), 100)  # 限制在0-100之间
            
            # 备用方法：使用vmstat
            cmd2 = "vmstat 1 2 | tail -1 | awk '{print 100-$15}'"
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd2)
            output = stdout.read().decode().strip()
            error_output = stderr.read().decode().strip()
            
            if self.debug_monitor and hasattr(self, 'log_message'):
                self.root.after(0, lambda: self.log_message(f"🔍 CPU命令2输出: '{output}', 错误: '{error_output}'"))
            
            if output and output.replace('.', '').replace('-', '').isdigit():
                cpu_usage = float(output)
                return min(max(cpu_usage, 0), 100)
                
            return 0
        except Exception as e:
            # 记录错误但不中断程序
            if hasattr(self, 'log_message'):
                self.root.after(0, lambda: self.log_message(f"❌ CPU监控错误: {e}"))
            return 0
    
    def get_memory_usage(self):
        """获取内存使用率"""
        try:
            if not self.ssh_client:
                return 0
                
            # 使用更准确的内存使用率计算方法
            stdin, stdout, stderr = self.ssh_client.exec_command("free -m | grep '^Mem:' | awk '{printf \"%.1f\", ($3-$6-$7)/$2 * 100.0}'")
            output = stdout.read().decode().strip()
            
            if output and output.replace('.', '').isdigit():
                memory_usage = float(output)
                return min(max(memory_usage, 0), 100)  # 限制在0-100之间
            
            # 备用方法：简单计算
            stdin, stdout, stderr = self.ssh_client.exec_command("free | grep '^Mem:' | awk '{printf \"%.1f\", $3/$2 * 100.0}'")
            output = stdout.read().decode().strip()
            
            if output and output.replace('.', '').isdigit():
                memory_usage = float(output)
                return min(max(memory_usage, 0), 100)
                
            return 0
        except Exception as e:
            # 记录错误但不中断程序
            if hasattr(self, 'log_message'):
                self.root.after(0, lambda: self.log_message(f"内存监控错误: {e}"))
            return 0
    
    def get_network_io(self):
        """获取网络I/O速率"""
        try:
            if not self.ssh_client:
                return 0
                
            # 简化的网络I/O监控，返回接收速率
            stdin, stdout, stderr = self.ssh_client.exec_command("cat /proc/net/dev | grep eth0 | awk '{print $2}' | head -1")
            output = stdout.read().decode().strip()
            
            if output:
                # 这里简化处理，实际应该计算速率差
                return min(float(output) / 1024 / 1024 / 100, 100)  # 转换为MB/s并限制在100以内
            return 0
        except:
            return 0
    
    def update_monitoring_charts(self):
        """更新监控图表"""
        try:
            if not self.time_data:
                return
                
            # 准备时间轴数据
            if len(self.time_data) > 1:
                time_range = list(range(len(self.time_data)))
            else:
                time_range = [0]
            
            # 更新GPU利用率图表
            ax_gpu_util = self.monitoring_figures['gpu_util'].axes[0]
            ax_gpu_util.clear()
            ax_gpu_util.set_title('GPU利用率', fontsize=9)
            ax_gpu_util.set_ylabel('利用率 (%)', fontsize=7)
            ax_gpu_util.set_ylim(0, 100)
            ax_gpu_util.grid(True, alpha=0.3)
            ax_gpu_util.tick_params(axis='both', which='major', labelsize=6)
            if self.gpu_utilization_data:
                ax_gpu_util.plot(time_range, list(self.gpu_utilization_data), 'orange', linewidth=1.5)
                ax_gpu_util.fill_between(time_range, list(self.gpu_utilization_data), alpha=0.3, color='orange')
            self.monitoring_canvases['gpu_util'].draw()
            
            # 更新GPU显存图表
            ax_gpu_memory = self.monitoring_figures['gpu_memory'].axes[0]
            ax_gpu_memory.clear()
            ax_gpu_memory.set_title('GPU显存使用率', fontsize=9)
            ax_gpu_memory.set_ylabel('使用率 (%)', fontsize=7)
            ax_gpu_memory.set_ylim(0, 100)
            ax_gpu_memory.grid(True, alpha=0.3)
            ax_gpu_memory.tick_params(axis='both', which='major', labelsize=6)
            if self.gpu_memory_data:
                ax_gpu_memory.plot(time_range, list(self.gpu_memory_data), 'b-', linewidth=1.5)
                ax_gpu_memory.fill_between(time_range, list(self.gpu_memory_data), alpha=0.3, color='blue')
            self.monitoring_canvases['gpu_memory'].draw()
            
            # 更新CPU图表
            ax_cpu = self.monitoring_figures['cpu'].axes[0]
            ax_cpu.clear()
            ax_cpu.set_title('CPU使用率', fontsize=9)
            ax_cpu.set_ylabel('使用率 (%)', fontsize=7)
            ax_cpu.set_ylim(0, 100)
            ax_cpu.grid(True, alpha=0.3)
            ax_cpu.tick_params(axis='both', which='major', labelsize=6)
            if self.cpu_data:
                ax_cpu.plot(time_range, list(self.cpu_data), 'r-', linewidth=1.5)
                ax_cpu.fill_between(time_range, list(self.cpu_data), alpha=0.3, color='red')
            self.monitoring_canvases['cpu'].draw()
            
            # 更新内存图表
            ax_memory = self.monitoring_figures['memory'].axes[0]
            ax_memory.clear()
            ax_memory.set_title('内存使用率', fontsize=9)
            ax_memory.set_ylabel('使用率 (%)', fontsize=7)
            ax_memory.set_ylim(0, 100)
            ax_memory.grid(True, alpha=0.3)
            ax_memory.tick_params(axis='both', which='major', labelsize=6)
            if self.memory_data:
                ax_memory.plot(time_range, list(self.memory_data), 'g-', linewidth=1.5)
                ax_memory.fill_between(time_range, list(self.memory_data), alpha=0.3, color='green')
            self.monitoring_canvases['memory'].draw()

        except Exception as e:
            print(f"更新监控图表失败: {e}")

    def _schedule_monitor_update(self):
        if self._monitor_ui_pending:
            return
        self._monitor_ui_pending = True
        def _do_update():
            try:
                self.update_monitoring_charts()
            finally:
                self._monitor_ui_pending = False
                self._last_monitor_update = time.time()
        self.root.after(self.monitor_refresh_ms, _do_update)

    def _update_training_progress(self):
        try:
            if not self.ssh_client:
                return
            status_text = None
            # 若未知运行目录，尝试从日志中解析或从runs/train挑选最新
            if not self.training_run_dir:
                if self.training_log_file:
                    stdin, stdout, stderr = self.ssh_client.exec_command(f'tail -n 100 {self.training_log_file} 2>/dev/null || echo ""')
                    content = stdout.read().decode('utf-8', errors='ignore')
                    if content:
                        import re
                        m_run = re.search(r'Logging results to\s+(runs/train/[^\s]+)', content)
                        if m_run:
                            rel = m_run.group(1)
                            self.training_run_dir = f'/root/{rel}'
                if not self.training_run_dir:
                    stdin, stdout, stderr = self.ssh_client.exec_command('ls -1t /root/runs/train 2>/dev/null | head -n 1')
                    latest = stdout.read().decode('utf-8').strip()
                    if latest:
                        self.training_run_dir = f'/root/runs/train/{latest}'

            if self.training_log_file:
                stdin, stdout, stderr = self.ssh_client.exec_command(f'tail -n 200 {self.training_log_file} 2>/dev/null || echo ""')
                content = stdout.read().decode('utf-8', errors='ignore')
                if content:
                    import re
                    ansi = re.compile(r'\x1B\[[0-9;]*[A-Za-z]')
                    text = ansi.sub('', content)
                    m_total = re.search(r'Starting training for\s+(\d+)\s+epochs', text)
                    total_epochs = int(m_total.group(1)) if m_total else None
                    m_epoch = re.findall(r'^\s*Epoch', text, flags=re.MULTILINE)
                    current_epoch = len(m_epoch) if m_epoch else None
                    m_step = re.search(r'(\d+)%\|.*?(\d+)/(\d+)', text)
                    if m_step:
                        pct = int(m_step.group(1))
                        cur = int(m_step.group(2))
                        tot = int(m_step.group(3))
                        if total_epochs and current_epoch is not None:
                            status_text = f"训练中: epoch {current_epoch}/{total_epochs}  步骤 {cur}/{tot}  {pct}%"
                        else:
                            status_text = f"训练中: 步骤 {cur}/{tot}  {pct}%"
                    elif total_epochs and current_epoch is not None:
                        status_text = f"训练中: epoch {current_epoch}/{total_epochs}"
            if self.training_run_dir and not self._run_dir_logged:
                self._run_dir_logged = True
                self.root.after(0, lambda p=self.training_run_dir: self.log_message(f"训练目录: {p}"))
            if not status_text and self.training_run_dir:
                # 读取 results.csv 最后一条有效行（非表头）
                stdin, stdout, stderr = self.ssh_client.exec_command(f'awk "NR>1" {self.training_run_dir}/results.csv 2>/dev/null | tail -n 1')
                last = stdout.read().decode('utf-8', errors='ignore').strip()
                if last:
                    parts = last.split(',')
                    try:
                        ep = int(parts[0])
                        total_ep = None
                        try:
                            total_ep = int(self.training_config.get('epochs'))
                        except:
                            pass
                        if total_ep:
                            status_text = f"训练中: epoch {ep}/{total_ep}"
                        else:
                            status_text = f"训练中: epoch {ep}"
                    except:
                        pass
            if status_text:
                self.root.after(0, lambda s=status_text: self.training_status_var.set(s))
        except:
            pass
    
    def check_python_compatibility(self, wheel_path, target_python_version="3.8"):
        """检查wheel包是否与目标Python版本兼容"""
        try:
            import zipfile
            import re
            
            with zipfile.ZipFile(wheel_path, 'r') as wheel:
                # 查找METADATA文件
                metadata_files = [f for f in wheel.namelist() if f.endswith('METADATA') or f.endswith('PKG-INFO')]
                if not metadata_files:
                    return True  # 没有元数据，假设兼容
                
                metadata_content = wheel.read(metadata_files[0]).decode('utf-8')
                
                # 查找Requires-Python字段
                for line in metadata_content.split('\n'):
                    if line.startswith('Requires-Python:'):
                        requires_python = line.split(':', 1)[1].strip()
                        
                        # 检查是否与Python 3.8兼容
                        incompatible_patterns = [
                            r'>=3\.9',  # 要求3.9+
                            r'>3\.8',   # 要求大于3.8
                            r'>=3\.10', # 要求3.10+
                            r'>=3\.11', # 要求3.11+
                            r'>=3\.12', # 要求3.12+
                        ]
                        
                        for pattern in incompatible_patterns:
                            if re.search(pattern, requires_python.replace(' ', '')):
                                return False
                        
                        return True
                
                return True  # 没有指定Python版本要求，假设兼容
                
        except Exception as e:
            # 如果无法读取元数据，假设兼容
            return True

    def try_local_package_install(self, ssh, cmd_desc, python_cmd):
        """尝试从本地Environment_package目录安装包"""
        try:
            # 本地Environment_package目录路径
            local_package_dir = os.path.join(os.path.dirname(__file__), "Environment_package")
            
            if not os.path.exists(local_package_dir):
                self.root.after(0, lambda: self.log_message(f"❌ 本地包目录不存在: {local_package_dir}"))
                return False
            
            # 获取当前Python版本
            python_version_cmd = f'cd /root && {python_cmd} -c "import sys; print(str(sys.version_info.major) + \\".\\\" + str(sys.version_info.minor))"'
            stdin, stdout, stderr = ssh.exec_command(python_version_cmd)
            current_python_version = stdout.read().decode('utf-8').strip()
            
            # 根据安装描述确定需要的包
            import glob
            local_packages = []
            
            if "PyTorch" in cmd_desc or "torch" in cmd_desc.lower():
                # PyTorch相关包：检查平台兼容性和Python版本兼容性
                torch_files = glob.glob(os.path.join(local_package_dir, "torch-*.whl"))
                torchvision_files = glob.glob(os.path.join(local_package_dir, "torchvision-*.whl"))
                
                # 筛选兼容的torch包（排除Windows特定包）
                compatible_torch = []
                for torch_file in torch_files:
                    filename = os.path.basename(torch_file)
                    # 排除Windows特定包
                    if "win_amd64" in filename or "win32" in filename:
                        continue
                    # 选择通用包、Linux包或兼容当前Python版本的包
                    if ("py3-none-any" in filename or "linux" in filename or ("cp" in filename and "win" not in filename)) and self.check_python_compatibility(torch_file):
                        compatible_torch.append(torch_file)
                
                compatible_torchvision = []
                for tv_file in torchvision_files:
                    filename = os.path.basename(tv_file)
                    # 排除Windows特定包
                    if "win_amd64" in filename or "win32" in filename:
                        continue
                    # 选择通用包、Linux包或兼容当前Python版本的包
                    if ("py3-none-any" in filename or "linux" in filename or ("cp" in filename and "win" not in filename)) and self.check_python_compatibility(tv_file):
                        compatible_torchvision.append(tv_file)
                
                if compatible_torch:
                    # 根据当前Python版本选择最合适的包
                    if current_python_version == "3.8":
                        # 对于Python 3.8，优先选择cp38版本
                        cp38_torch = [f for f in compatible_torch if "cp38" in f]
                        if cp38_torch:
                            torch_file = sorted(cp38_torch)[-1]
                            self.root.after(0, lambda f=os.path.basename(torch_file): self.log_message(f"🔍 选择Python 3.8专用torch包: {f}"))
                        else:
                            # 如果没有cp38版本，选择通用版本
                            universal_torch = [f for f in compatible_torch if "py3-none-any" in f]
                            if universal_torch:
                                torch_file = sorted(universal_torch)[-1]
                                self.root.after(0, lambda f=os.path.basename(torch_file): self.log_message(f"🔍 选择通用torch包: {f}"))
                            else:
                                torch_file = sorted(compatible_torch)[-1]
                                self.root.after(0, lambda f=os.path.basename(torch_file): self.log_message(f"🔍 选择兼容torch包: {f}"))
                    else:
                        # 对于Python 3.9+，优先选择通用版本或最新版本，避免使用cp38专用包
                        universal_torch = [f for f in compatible_torch if "py3-none-any" in f]
                        linux_torch = [f for f in compatible_torch if "linux" in f and "cp38" not in f]
                        non_cp38_torch = [f for f in compatible_torch if "cp38" not in f]
                        
                        if universal_torch:
                            torch_file = sorted(universal_torch)[-1]
                            self.root.after(0, lambda f=os.path.basename(torch_file): self.log_message(f"🔍 选择通用torch包（适用于Python {current_python_version}）: {f}"))
                        elif linux_torch:
                            torch_file = sorted(linux_torch)[-1]
                            self.root.after(0, lambda f=os.path.basename(torch_file): self.log_message(f"🔍 选择Linux兼容torch包（适用于Python {current_python_version}）: {f}"))
                        elif non_cp38_torch:
                            torch_file = sorted(non_cp38_torch)[-1]
                            self.root.after(0, lambda f=os.path.basename(torch_file): self.log_message(f"🔍 选择兼容torch包（适用于Python {current_python_version}）: {f}"))
                        else:
                            # 如果只有cp38包，跳过本地安装，使用在线安装
                            self.root.after(0, lambda: self.log_message(f"⚠️ 跳过torch本地安装（只有Python 3.8专用包，当前版本为{current_python_version}），使用在线安装"))
                            torch_file = None
                    
                    if torch_file:
                        local_packages.append(torch_file)
                elif torch_files:
                    # 如果没有兼容版本，跳过本地安装
                    self.root.after(0, lambda: self.log_message(f"⚠️ 跳过torch本地安装（Python版本不兼容），使用在线安装"))
                
                if compatible_torchvision:
                    # 根据当前Python版本选择最合适的torchvision包
                    if current_python_version == "3.8":
                        # 对于Python 3.8，优先选择cp38版本
                        cp38_torchvision = [f for f in compatible_torchvision if "cp38" in f]
                        if cp38_torchvision:
                            torchvision_file = sorted(cp38_torchvision)[-1]
                            self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择Python 3.8专用torchvision包: {f}"))
                        else:
                            # 如果没有cp38版本，选择通用版本
                            universal_torchvision = [f for f in compatible_torchvision if "py3-none-any" in f]
                            if universal_torchvision:
                                torchvision_file = sorted(universal_torchvision)[-1]
                                self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择通用torchvision包: {f}"))
                            else:
                                torchvision_file = sorted(compatible_torchvision)[-1]
                                self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择兼容torchvision包: {f}"))
                    else:
                        # 对于Python 3.9+，优先选择通用版本或最新版本，避免使用cp38专用包
                        universal_torchvision = [f for f in compatible_torchvision if "py3-none-any" in f]
                        linux_torchvision = [f for f in compatible_torchvision if "linux" in f and "cp38" not in f]
                        non_cp38_torchvision = [f for f in compatible_torchvision if "cp38" not in f]
                        
                        if universal_torchvision:
                            torchvision_file = sorted(universal_torchvision)[-1]
                            self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择通用torchvision包（适用于Python {current_python_version}）: {f}"))
                        elif linux_torchvision:
                            torchvision_file = sorted(linux_torchvision)[-1]
                            self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择Linux兼容torchvision包（适用于Python {current_python_version}）: {f}"))
                        elif non_cp38_torchvision:
                            torchvision_file = sorted(non_cp38_torchvision)[-1]
                            self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择兼容torchvision包（适用于Python {current_python_version}）: {f}"))
                        else:
                            # 如果只有cp38包，跳过本地安装，使用在线安装
                            self.root.after(0, lambda: self.log_message(f"⚠️ 跳过torchvision本地安装（只有Python 3.8专用包，当前版本为{current_python_version}），使用在线安装"))
                            torchvision_file = None
                    
                    if torchvision_file:
                        local_packages.append(torchvision_file)
                        self.root.after(0, lambda f=os.path.basename(torchvision_file): self.log_message(f"🔍 选择兼容torchvision包: {f}"))
                    
                    local_packages.append(torchvision_file)
                elif torchvision_files:
                    self.root.after(0, lambda: self.log_message(f"⚠️ 跳过torchvision本地安装（Python版本不兼容）"))
                    
            elif "ultralytics" in cmd_desc.lower():
                # 首先安装基础依赖包（必须先安装）
                base_dependencies = ["typing_extensions-*.whl", "setuptools-*.whl", "wheel-*.whl"]
                for pattern in base_dependencies:
                    matches = glob.glob(os.path.join(local_package_dir, pattern))
                    if matches:
                        # 筛选Python 3.8兼容的包（排除Windows特定包）
                        compatible_matches = []
                        for match in matches:
                            filename = os.path.basename(match)
                            # 排除Windows特定包
                            if "win_amd64" in filename or "win32" in filename:
                                continue
                            # 选择通用包、Linux包或非Windows的cp38包
                            if ("py3-none-any" in filename or "py2.py3-none-any" in filename or "linux" in filename or ("cp38" in filename and "win" not in filename)) and self.check_python_compatibility(match):
                                compatible_matches.append(match)
                        
                        if compatible_matches:
                            # 优先级：1. 通用包 2. Linux包 3. cp38包 4. 其他兼容包
                            universal_matches = [f for f in compatible_matches if "py3-none-any" in f or "py2.py3-none-any" in f]
                            linux_matches = [f for f in compatible_matches if "linux" in f]
                            cp38_matches = [f for f in compatible_matches if "cp38" in f]
                            
                            if universal_matches:
                                dep_file = sorted(universal_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择通用基础包: {f}"))
                            elif linux_matches:
                                dep_file = sorted(linux_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择Linux基础包: {f}"))
                            elif cp38_matches:
                                dep_file = sorted(cp38_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择Python 3.8基础包: {f}"))
                            else:
                                dep_file = sorted(compatible_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择兼容基础包: {f}"))
                            
                            local_packages.append(dep_file)
                        else:
                            # 没有兼容版本时跳过
                            package_name = pattern.split('-')[0]
                            self.root.after(0, lambda p=package_name: self.log_message(f"⚠️ 跳过{p}（Python版本不兼容）"))
                            continue
                
                # Ultralytics包：选择Python 3.8兼容的版本
                ultralytics_files = glob.glob(os.path.join(local_package_dir, "ultralytics-*.whl"))
                
                if ultralytics_files:
                    # 筛选Python 3.8兼容的ultralytics包
                    compatible_ultralytics = [f for f in ultralytics_files if self.check_python_compatibility(f)]
                    
                    if compatible_ultralytics:
                        # 优先选择8.0.196版本（更稳定），如果没有则选择最新版本
                        preferred_version = None
                        latest_version = None
                        
                        for file in compatible_ultralytics:
                            if "8.0.196" in file:
                                preferred_version = file
                            if not latest_version or file > latest_version:
                                latest_version = file
                        
                        selected_file = preferred_version if preferred_version else latest_version
                        local_packages.append(selected_file)
                        self.root.after(0, lambda f=os.path.basename(selected_file): self.log_message(f"🔍 选择Python 3.8兼容ultralytics包: {f}"))
                    else:
                        self.root.after(0, lambda: self.log_message(f"⚠️ 跳过ultralytics（Python版本不兼容）"))
                    
                # 同时安装必要的依赖包（优先选择Python 3.8兼容版本）
                dependency_patterns = ["tqdm-*.whl", "pyyaml-*.whl", "requests-*.whl", "urllib3-*.whl"]
                for pattern in dependency_patterns:
                    matches = glob.glob(os.path.join(local_package_dir, pattern))
                    if matches:
                        # 筛选Python 3.8兼容的包（排除Windows特定包）
                        compatible_matches = []
                        for match in matches:
                            filename = os.path.basename(match)
                            # 排除Windows特定包
                            if "win_amd64" in filename or "win32" in filename:
                                continue
                            # 选择通用包、Linux包或非Windows的cp38包
                            if ("py3-none-any" in filename or "py2.py3-none-any" in filename or "linux" in filename or ("cp38" in filename and "win" not in filename)) and self.check_python_compatibility(match):
                                compatible_matches.append(match)
                        
                        if compatible_matches:
                            # 优先级：1. 通用包 2. Linux包 3. cp38包 4. 其他兼容包
                            universal_matches = [f for f in compatible_matches if "py3-none-any" in f or "py2.py3-none-any" in f]
                            linux_matches = [f for f in compatible_matches if "linux" in f]
                            cp38_matches = [f for f in compatible_matches if "cp38" in f]
                            
                            if universal_matches:
                                dep_file = sorted(universal_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择通用包: {f}"))
                            elif linux_matches:
                                dep_file = sorted(linux_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择Linux包: {f}"))
                            elif cp38_matches:
                                dep_file = sorted(cp38_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择Python 3.8包: {f}"))
                            else:
                                dep_file = sorted(compatible_matches)[-1]
                                self.root.after(0, lambda f=os.path.basename(dep_file): self.log_message(f"🔍 选择兼容包: {f}"))
                            
                            local_packages.append(dep_file)
                        else:
                            # 没有兼容版本时跳过
                            package_name = pattern.split('-')[0]
                            self.root.after(0, lambda p=package_name: self.log_message(f"⚠️ 跳过{p}（Python版本不兼容）"))
                        
            elif "networkx" in cmd_desc.lower():
                networkx_files = glob.glob(os.path.join(local_package_dir, "networkx-*.whl"))
                if networkx_files:
                    networkx_file = sorted(networkx_files)[-1]
                    local_packages.append(networkx_file)
                    self.root.after(0, lambda f=os.path.basename(networkx_file): self.log_message(f"🔍 选择networkx包: {f}"))
            else:
                self.root.after(0, lambda: self.log_message(f"❌ 未知的包类型: {cmd_desc}"))
                return False
            
            if not local_packages:
                self.root.after(0, lambda: self.log_message(f"❌ 本地目录中未找到相关包文件"))
                return False
            
            # 创建远程临时目录
            temp_dir = "/tmp/local_packages"
            ssh.exec_command(f"mkdir -p {temp_dir}")
            
            # 上传并安装包
            from scp import SCPClient
            with SCPClient(ssh.get_transport()) as scp:
                uploaded_files = []
                
                for local_package in local_packages:
                    package_name = os.path.basename(local_package)
                    remote_path = f"{temp_dir}/{package_name}"
                    
                    self.root.after(0, lambda name=package_name: self.log_message(f"📦 上传本地包: {name}"))
                    
                    try:
                        scp.put(local_package, remote_path)
                        uploaded_files.append(remote_path)
                        self.root.after(0, lambda name=package_name: self.log_message(f"✅ 上传完成: {name}"))
                    except Exception as e:
                        self.root.after(0, lambda name=package_name, err=str(e): self.log_message(f"❌ 上传失败 {name}: {err}"))
                        return False
                
                # 安装上传的包
                if uploaded_files:
                    # 先卸载可能冲突的旧版本
                    packages_to_uninstall = []
                    for file_path in uploaded_files:
                        filename = os.path.basename(file_path)
                        if filename.startswith("torch-"):
                            packages_to_uninstall.extend(["torch", "torchvision", "torchaudio"])
                        elif filename.startswith("ultralytics-"):
                            packages_to_uninstall.append("ultralytics")
                        elif filename.startswith("networkx-"):
                            packages_to_uninstall.append("networkx")
                    
                    # 执行卸载命令
                    if packages_to_uninstall:
                        uninstall_packages = " ".join(set(packages_to_uninstall))  # 去重
                        uninstall_cmd = f"cd /root && {python_cmd} -m pip uninstall -y {uninstall_packages}"
                        
                        self.root.after(0, lambda: self.log_message(f"🗑️ 卸载旧版本: {uninstall_packages}"))
                        
                        stdin, stdout, stderr = ssh.exec_command(uninstall_cmd)
                        uninstall_status = stdout.channel.recv_exit_status()
                        
                        if uninstall_status == 0:
                            self.root.after(0, lambda: self.log_message(f"✅ 旧版本卸载成功"))
                        else:
                            self.root.after(0, lambda: self.log_message(f"⚠️ 旧版本卸载完成（可能部分包不存在）"))
                    
                    # 安装新版本包
                    packages_str = " ".join(uploaded_files)
                    install_cmd = f"cd /root && {python_cmd} -m pip install --force-reinstall --no-deps {packages_str}"
                    
                    self.root.after(0, lambda: self.log_message(f"🔧 执行本地包安装: {install_cmd}"))
                    
                    stdin, stdout, stderr = ssh.exec_command(install_cmd)
                    exit_status = stdout.channel.recv_exit_status()
                    
                    install_output = stdout.read().decode('utf-8', errors='ignore')
                    install_errors = stderr.read().decode('utf-8', errors='ignore')
                    
                    # 检查安装结果
                    if exit_status == 0 and "Successfully installed" in install_output:
                        self.root.after(0, lambda: self.log_message(f"✅ 本地包安装成功"))
                        
                        # 显示安装的包信息
                        success_lines = [line for line in install_output.split('\n') if "Successfully installed" in line]
                        if success_lines:
                            self.root.after(0, lambda line=success_lines[0]: self.log_message(f"📦 {line.strip()}"))
                        
                        # 清理临时文件
                        ssh.exec_command(f"rm -rf {temp_dir}")
                        return True
                    else:
                        self.root.after(0, lambda: self.log_message(f"❌ 本地包安装失败 (退出状态: {exit_status})"))
                        if install_errors:
                            self.root.after(0, lambda err=install_errors: self.log_message(f"❌ 错误: {err.strip()[:200]}"))
                        return False
                        
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.log_message(f"❌ 本地包安装异常: {err}"))
            return False
    
    def local_package_install(self):
        """本地包安装功能"""
        def show_local_install_window():
            # 创建本地安装窗口
            install_window = tk.Toplevel(self.root)
            install_window.title("本地包安装")
            install_window.geometry("600x500")
            install_window.resizable(True, True)
            
            # 主框架
            main_frame = ttk.Frame(install_window, padding="10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # 说明标签
            info_label = ttk.Label(main_frame, text="选择本地安装包文件上传到服务器进行离线安装", 
                                 font=("Arial", 10))
            info_label.pack(pady=(0, 10))
            
            # 包选择框架
            package_frame = ttk.LabelFrame(main_frame, text="选择安装包", padding="10")
            package_frame.pack(fill=tk.X, pady=(0, 10))
            
            # PyTorch包选择
            torch_frame = ttk.Frame(package_frame)
            torch_frame.pack(fill=tk.X, pady=(0, 5))
            
            ttk.Label(torch_frame, text="PyTorch包 (.whl):").pack(side=tk.LEFT)
            self.torch_file_var = tk.StringVar()
            torch_entry = ttk.Entry(torch_frame, textvariable=self.torch_file_var, width=40)
            torch_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
            ttk.Button(torch_frame, text="选择", 
                      command=lambda: self.select_package_file(self.torch_file_var, "PyTorch")).pack(side=tk.RIGHT)
            
            # Ultralytics包选择
            ultralytics_frame = ttk.Frame(package_frame)
            ultralytics_frame.pack(fill=tk.X, pady=(0, 5))
            
            ttk.Label(ultralytics_frame, text="Ultralytics包 (.whl):").pack(side=tk.LEFT)
            self.ultralytics_file_var = tk.StringVar()
            ultralytics_entry = ttk.Entry(ultralytics_frame, textvariable=self.ultralytics_file_var, width=40)
            ultralytics_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
            ttk.Button(ultralytics_frame, text="选择", 
                      command=lambda: self.select_package_file(self.ultralytics_file_var, "Ultralytics")).pack(side=tk.RIGHT)
            
            # 依赖包目录选择
            deps_frame = ttk.Frame(package_frame)
            deps_frame.pack(fill=tk.X, pady=(0, 5))
            
            ttk.Label(deps_frame, text="依赖包目录:").pack(side=tk.LEFT)
            self.deps_dir_var = tk.StringVar()
            deps_entry = ttk.Entry(deps_frame, textvariable=self.deps_dir_var, width=40)
            deps_entry.pack(side=tk.LEFT, padx=(10, 5), fill=tk.X, expand=True)
            ttk.Button(deps_frame, text="选择", 
                      command=lambda: self.select_deps_directory()).pack(side=tk.RIGHT)
            
            # 安装选项
            options_frame = ttk.LabelFrame(main_frame, text="安装选项", padding="10")
            options_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.force_reinstall_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="强制重新安装", 
                           variable=self.force_reinstall_var).pack(anchor=tk.W)
            
            self.no_deps_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="不安装依赖", 
                           variable=self.no_deps_var).pack(anchor=tk.W)
            
            # 进度显示
            progress_frame = ttk.LabelFrame(main_frame, text="安装进度", padding="10")
            progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
            
            self.local_install_progress = ttk.Progressbar(progress_frame, mode='indeterminate')
            self.local_install_progress.pack(fill=tk.X, pady=(0, 5))
            
            self.local_install_log = scrolledtext.ScrolledText(progress_frame, height=10, width=70)
            self.local_install_log.pack(fill=tk.BOTH, expand=True)
            
            # 按钮框架
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill=tk.X)
            
            ttk.Button(button_frame, text="开始安装", 
                      command=lambda: self.execute_local_install(install_window)).pack(side=tk.LEFT, padx=(0, 10))
            ttk.Button(button_frame, text="取消", 
                      command=install_window.destroy).pack(side=tk.LEFT)
            
            # 帮助信息
            help_text = """
使用说明：
1. 从PyTorch官网下载对应的.whl文件
2. 从PyPI下载ultralytics的.whl文件
3. 可选择包含所有依赖包的目录
4. 点击"开始安装"进行离线安装
            """
            ttk.Label(main_frame, text=help_text, justify=tk.LEFT, 
                     foreground="gray").pack(pady=(10, 0))
        
        # 在新线程中显示窗口
        threading.Thread(target=show_local_install_window, daemon=True).start()
    
    def select_package_file(self, var, package_name):
        """选择包文件"""
        file_path = filedialog.askopenfilename(
            title=f"选择{package_name}包文件",
            filetypes=[("Wheel files", "*.whl"), ("All files", "*.*")]
        )
        if file_path:
            var.set(file_path)
    
    def select_deps_directory(self):
        """选择依赖包目录"""
        dir_path = filedialog.askdirectory(title="选择依赖包目录")
        if dir_path:
            self.deps_dir_var.set(dir_path)
    
    def execute_local_install(self, parent_window):
        """执行本地安装"""
        def install_packages():
            try:
                self.local_install_progress.start()
                self.local_install_log.delete(1.0, tk.END)
                
                # 检查连接
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                self.local_install_log.insert(tk.END, "🔗 连接到服务器...\n")
                parent_window.update()
                
                ssh.connect(
                    hostname=self.hostname_var.get(),
                    port=int(self.port_var.get()),
                    username=self.username_var.get(),
                    password=self.password_var.get()
                )
                
                self.local_install_log.insert(tk.END, "✅ 服务器连接成功\n")
                parent_window.update()
                
                # 创建临时目录
                temp_dir = "/tmp/local_packages"
                ssh.exec_command(f"mkdir -p {temp_dir}")
                
                # 上传文件
                with SCPClient(ssh.get_transport()) as scp:
                    uploaded_files = []
                    
                    # 上传PyTorch包
                    if self.torch_file_var.get():
                        self.local_install_log.insert(tk.END, f"📦 上传PyTorch包...\n")
                        parent_window.update()
                        torch_filename = os.path.basename(self.torch_file_var.get())
                        scp.put(self.torch_file_var.get(), f"{temp_dir}/{torch_filename}")
                        uploaded_files.append(f"{temp_dir}/{torch_filename}")
                        self.local_install_log.insert(tk.END, f"✅ PyTorch包上传完成\n")
                    
                    # 上传Ultralytics包
                    if self.ultralytics_file_var.get():
                        self.local_install_log.insert(tk.END, f"📦 上传Ultralytics包...\n")
                        parent_window.update()
                        ultralytics_filename = os.path.basename(self.ultralytics_file_var.get())
                        scp.put(self.ultralytics_file_var.get(), f"{temp_dir}/{ultralytics_filename}")
                        uploaded_files.append(f"{temp_dir}/{ultralytics_filename}")
                        self.local_install_log.insert(tk.END, f"✅ Ultralytics包上传完成\n")
                    
                    # 上传依赖包目录
                    if self.deps_dir_var.get() and os.path.isdir(self.deps_dir_var.get()):
                        self.local_install_log.insert(tk.END, f"📦 上传依赖包目录...\n")
                        parent_window.update()
                        scp.put(self.deps_dir_var.get(), temp_dir, recursive=True)
                        deps_dir_name = os.path.basename(self.deps_dir_var.get())
                        uploaded_files.append(f"{temp_dir}/{deps_dir_name}")
                        self.local_install_log.insert(tk.END, f"✅ 依赖包目录上传完成\n")
                
                # 安装包
                install_options = []
                if self.force_reinstall_var.get():
                    install_options.append("--force-reinstall")
                if self.no_deps_var.get():
                    install_options.append("--no-deps")
                
                options_str = " ".join(install_options)
                
                for package_path in uploaded_files:
                    self.local_install_log.insert(tk.END, f"🔧 安装 {os.path.basename(package_path)}...\n")
                    parent_window.update()
                    
                    if os.path.isdir(package_path.replace(temp_dir + "/", self.deps_dir_var.get() + "/")):
                        # 安装目录中的所有包
                        install_cmd = f"cd /root && pip3 install {options_str} {package_path}/*.whl"
                    else:
                        # 安装单个包
                        install_cmd = f"cd /root && pip3 install {options_str} {package_path}"
                    
                    stdin, stdout, stderr = ssh.exec_command(install_cmd)
                    
                    # 实时显示输出
                    while True:
                        line = stdout.readline()
                        if not line:
                            break
                        self.local_install_log.insert(tk.END, f"📥 {line}")
                        parent_window.update()
                    
                    # 检查错误
                    error_output = stderr.read().decode('utf-8')
                    if error_output:
                        self.local_install_log.insert(tk.END, f"⚠️ {error_output}\n")
                
                # 验证安装
                self.local_install_log.insert(tk.END, "🔍 验证安装结果...\n")
                parent_window.update()
                
                verification_cmd = "python3 -c 'import torch, ultralytics; print(f\"PyTorch: {torch.__version__}\"); print(f\"Ultralytics: {ultralytics.__version__}\")'"
                stdin, stdout, stderr = ssh.exec_command(verification_cmd)
                
                verification_output = stdout.read().decode('utf-8')
                if verification_output:
                    self.local_install_log.insert(tk.END, f"✅ 验证成功:\n{verification_output}\n")
                else:
                    error_output = stderr.read().decode('utf-8')
                    self.local_install_log.insert(tk.END, f"❌ 验证失败: {error_output}\n")
                
                # 清理临时文件
                ssh.exec_command(f"rm -rf {temp_dir}")
                self.local_install_log.insert(tk.END, "🧹 清理临时文件完成\n")
                
                ssh.close()
                self.local_install_log.insert(tk.END, "🎉 本地安装完成！\n")
                
            except Exception as e:
                self.local_install_log.insert(tk.END, f"❌ 安装失败: {str(e)}\n")
            finally:
                self.local_install_progress.stop()
        
        # 在新线程中执行安装
        threading.Thread(target=install_packages, daemon=True).start()
    
    def upgrade_python_version(self, ssh, current_python_cmd):
        """升级Python版本从3.8到3.13.7"""
        try:
            self.root.after(0, lambda: self.log_message("🔄 开始Python版本升级过程..."))
            
            # 1. 更新系统包列表
            self.root.after(0, lambda: self.log_message("📦 更新系统包列表..."))
            stdin, stdout, stderr = ssh.exec_command('cd /root && apt update')
            update_output = stdout.read().decode('utf-8')
            update_error = stderr.read().decode('utf-8')
            
            if 'error' in update_error.lower():
                self.root.after(0, lambda: self.log_message(f"⚠️ 包列表更新警告: {update_error[:200]}"))
            else:
                self.root.after(0, lambda: self.log_message("✓ 包列表更新完成"))
            
            # 2. 尝试安装Python 3.13.7（如果可用）或Python 3.9
            python_versions = [
                ("3.13", "python3.13"),
                ("3.9", "python3.9")
            ]
            
            installed_python_cmd = None
            
            for version_name, python_cmd in python_versions:
                self.root.after(0, lambda v=version_name: self.log_message(f"🐍 尝试安装Python {v}..."))
                
                # 构建安装命令
                if version_name == "3.13":
                    # 对于Python 3.13，可能需要从源码编译或使用PPA
                    install_cmd = f'''cd /root && 
                    apt install -y software-properties-common && 
                    add-apt-repository -y ppa:deadsnakes/ppa && 
                    apt update && 
                    apt install -y python{version_name} python{version_name}-dev python{version_name}-venv python{version_name}-distutils'''
                else:
                    # 对于Python 3.9
                    install_cmd = f'cd /root && apt install -y python{version_name} python{version_name}-dev python{version_name}-venv python{version_name}-distutils'
                
                stdin, stdout, stderr = ssh.exec_command(install_cmd)
                install_output = stdout.read().decode('utf-8')
                install_error = stderr.read().decode('utf-8')
                
                # 验证安装
                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} --version')
                version_check = stdout.read().decode('utf-8').strip()
                
                if f'Python {version_name}' in version_check:
                    self.root.after(0, lambda v=version_check: self.log_message(f"✓ Python安装成功: {v}"))
                    installed_python_cmd = python_cmd
                    break
                else:
                    self.root.after(0, lambda v=version_name: self.log_message(f"⚠️ Python {v}安装失败，尝试下一个版本"))
            
            if not installed_python_cmd:
                self.root.after(0, lambda: self.log_message("❌ 所有Python版本安装都失败"))
                return None
            
            # 3. 安装pip for 新Python版本
            self.root.after(0, lambda: self.log_message(f"📦 为{installed_python_cmd}安装pip..."))
            
            # 首先尝试使用get-pip.py
            pip_install_commands = [
                f'cd /root && curl -sS https://bootstrap.pypa.io/get-pip.py | {installed_python_cmd}',
                f'cd /root && {installed_python_cmd} -m ensurepip --upgrade',
                f'cd /root && apt install -y python3-pip && {installed_python_cmd} -m pip install --upgrade pip'
            ]
            
            pip_installed = False
            for cmd in pip_install_commands:
                self.root.after(0, lambda c=cmd: self.log_message(f"执行: {c.split('&&')[-1].strip()}"))
                stdin, stdout, stderr = ssh.exec_command(cmd)
                pip_output = stdout.read().decode('utf-8')
                pip_error = stderr.read().decode('utf-8')
                
                # 验证pip安装
                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {installed_python_cmd} -m pip --version')
                pip_version = stdout.read().decode('utf-8').strip()
                
                if 'pip' in pip_version:
                    self.root.after(0, lambda v=pip_version: self.log_message(f"✓ pip安装成功: {v}"))
                    pip_installed = True
                    break
                else:
                    self.root.after(0, lambda: self.log_message("⚠️ 尝试下一种pip安装方法..."))
            
            if not pip_installed:
                self.root.after(0, lambda: self.log_message("❌ pip安装失败"))
                return None
            
            # 4. 设置新Python版本为默认（可选）
            self.root.after(0, lambda: self.log_message(f"🔗 配置{installed_python_cmd}环境..."))
            
            # 创建符号链接或更新alternatives
            alternatives_cmd = f'''cd /root && 
            update-alternatives --install /usr/bin/python3 python3 /usr/bin/{installed_python_cmd} 2 && 
            update-alternatives --set python3 /usr/bin/{installed_python_cmd}'''
            
            stdin, stdout, stderr = ssh.exec_command(alternatives_cmd)
            alt_output = stdout.read().decode('utf-8')
            alt_error = stderr.read().decode('utf-8')
            
            # 验证默认Python版本
            stdin, stdout, stderr = ssh.exec_command('cd /root && python3 --version')
            default_version = stdout.read().decode('utf-8').strip()
            
            if installed_python_cmd.replace('python', 'Python ') in default_version:
                self.root.after(0, lambda: self.log_message(f"✓ 默认Python已更新: {default_version}"))
            else:
                self.root.after(0, lambda: self.log_message(f"⚠️ 默认Python仍为: {default_version}"))
            
            # 5. 升级核心包
            self.root.after(0, lambda: self.log_message("📦 升级核心Python包..."))
            core_packages = ['setuptools', 'wheel', 'pip']
            
            for package in core_packages:
                upgrade_cmd = f'cd /root && {installed_python_cmd} -m pip install --upgrade {package}'
                stdin, stdout, stderr = ssh.exec_command(upgrade_cmd)
                upgrade_output = stdout.read().decode('utf-8')
                
                if 'Successfully installed' in upgrade_output or 'Requirement already satisfied' in upgrade_output:
                    self.root.after(0, lambda p=package: self.log_message(f"✓ {p} 升级完成"))
                else:
                    self.root.after(0, lambda p=package: self.log_message(f"⚠️ {p} 升级可能有问题"))
            
            self.root.after(0, lambda: self.log_message("🎉 Python版本升级完成！"))
            return installed_python_cmd  # 返回新的Python命令
            
        except Exception as e:
            self.root.after(0, lambda err=str(e): self.log_message(f"❌ Python升级过程中出错: {err}"))
            return None
    
    def log_message(self, message):
        """添加日志消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        
        # 更新状态栏
        self.status_var.set(message)
        
        # 记录到日志文件
        self.logger.info(message)

def main():
    root = tk.Tk()
    app = CloudTrainingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
