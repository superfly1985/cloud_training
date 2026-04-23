#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端训练管理平台 v3.0.0 - 纯UI界面
仅负责布局和控件创建，不包含业务逻辑
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import scrolledtext


class MainWindow:
    """主窗口UI类 - 纯UI，不包含业务逻辑"""
    
    def __init__(self, root):
        self.root = root
        self.app_version = "v3.0.0"
        self.root.title(f"云端训练管理平台 {self.app_version}")
        self.root.geometry("1200x850")
        self.root.minsize(1150, 680)
        self.root.resizable(True, True)
        
        # 初始化所有UI变量（StringVar/IntVar等）
        self._init_variables()
        
        # 创建UI
        self._create_ui()
    
    def _init_variables(self):
        """初始化所有UI变量"""
        # 服务器配置变量
        self.hostname_var = tk.StringVar(value="")
        self.port_var = tk.StringVar(value="22")
        self.username_var = tk.StringVar(value="root")
        self.password_var = tk.StringVar(value="")
        self.key_file_var = tk.StringVar(value="")
        self.connection_status_var = tk.StringVar(value="未连接")
        
        # 训练参数变量
        self.epochs_var = tk.StringVar(value="300")
        self.batch_size_var = tk.StringVar(value="20")
        self.learning_rate_var = tk.StringVar(value="0.01")
        self.image_size_var = tk.StringVar(value="1024")
        self.base_model_var = tk.StringVar(value="yolov8s.pt")
        self.model_name_suffix_var = tk.StringVar(value="")
        
        # 图像增强变量
        self.augment_scale_var = tk.DoubleVar(value=0.5)
        self.augment_fliplr_var = tk.DoubleVar(value=0.5)
        self.augment_hsv_h_var = tk.DoubleVar(value=0.015)
        self.augment_hsv_s_var = tk.DoubleVar(value=0.7)
        self.augment_hsv_v_var = tk.DoubleVar(value=0.4)
        
        # 数据集变量
        self.dataset_path_var = tk.StringVar(value="D:\\datasets\\train")
        self.local_path_var = tk.StringVar(value="")
        self.remote_path_var = tk.StringVar(value="/root/yolo_dataset")
        self.dataset_name_var = tk.StringVar(value="")
        self.num_classes_var = tk.StringVar(value="0")
        self.local_image_count_var = tk.StringVar(value="图片数: -")
        self.local_dataset_status_var = tk.StringVar(value="状态: 未检查")
        self.remote_image_count_var = tk.StringVar(value="图片数: -")
        self.remote_dataset_path_var = tk.StringVar(value="路径: -")
        
        # 图像增强变量（设计稿要求）
        self.scale_var = tk.DoubleVar(value=0.35)
        self.fliplr_var = tk.DoubleVar(value=0.35)
        self.flipud_var = tk.DoubleVar(value=0.35)
        self.perspective_var = tk.DoubleVar(value=0.35)
        self.hsv_h_var = tk.DoubleVar(value=0.35)
        self.hsv_s_var = tk.DoubleVar(value=0.35)
        self.hsv_v_var = tk.DoubleVar(value=0.35)
        
        # 状态变量
        self.upload_status_var = tk.StringVar(value="准备就绪")
        self.dataset_check_status_var = tk.StringVar(value="检查状态: 未检查")
        self.dataset_summary_var = tk.StringVar(value="检查总结: 未生成")
        self.upload_progress_var = tk.DoubleVar(value=0)
        self.training_status_var = tk.StringVar(value="未开始")
        self.status_duration_var = tk.StringVar(value="时长: 00:00:00")
        self.status_eta_var = tk.StringVar(value="预计完成: --")
    
    def _create_ui(self):
        """创建主UI"""
        # 创建Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)
        
        # 创建数据集配置选项卡
        self._create_dataset_tab()
    
    def _create_dataset_tab(self):
        """创建数据集配置选项卡 - 严格按照设计稿布局"""
        # 创建主容器（无滚动条）
        outer_frame = ttk.Frame(self.notebook)
        outer_frame.pack(fill="both", expand=True)
        self.notebook.add(outer_frame, text="数据集配置")
        
        # 主Frame直接放在outer_frame中
        main_frame = ttk.Frame(outer_frame, padding="10")
        main_frame.pack(fill="both", expand=True)
        
        # ==================== 混合布局：左列独立 + 中右grid ====================
        
        # 主布局分为左右两大部分
        main_frame.columnconfigure(0, weight=0, minsize=320)  # 左列固定宽度
        main_frame.columnconfigure(1, weight=1)              # 中右列自适应
        
        # 左列Frame - 垂直pack排列
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=0)
        
        # 左列容器（垂直紧密排列）
        self._create_server_section_pack(left_frame)
        self._create_training_params_section_pack(left_frame)
        self._create_augment_section_pack(left_frame)
        
        # 中右列Frame - 内部使用grid
        right_frame = ttk.Frame(main_frame)
        right_frame.grid(row=0, column=1, sticky=(tk.N, tk.S, tk.W, tk.E), padx=5, pady=0)
        right_frame.columnconfigure(0, weight=1, minsize=400)  # 中列
        right_frame.columnconfigure(1, weight=1, minsize=300)  # 右列
        right_frame.rowconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        right_frame.rowconfigure(2, weight=0)
        
        # 第1行：系统监控 | 训练日志
        self._create_monitor_section(right_frame, row=0, column=0)
        self._create_log_section(right_frame, row=0, column=1)
        
        # 第2行：数据集信息 | 快捷功能
        self._create_dataset_info_section(right_frame, row=1, column=0)
        self._create_quick_cards_section(right_frame, row=1, column=1)
        
        # 第3行：操作进度（跨2列）
        self._create_progress_section(right_frame, row=2, column=0, columnspan=2)
    
    def _create_server_section(self, parent, row, column):
        """创建服务器设置区域 - 严格按照设计稿"""
        frame = ttk.Labelframe(parent, text="服务器设置", padding="10")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=0)
        
        # 配置4列布局（前3行用2列，状态信息用4列）
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=1)
        
        # 服务器IP
        ttk.Label(frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.hostname_var, width=20).grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 端口
        ttk.Label(frame, text="端口:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.port_var, width=20).grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 用户名
        ttk.Label(frame, text="用户名:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.username_var, width=20).grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 按钮行
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=(10, 0))
        self.btn_test_connection = ttk.Button(btn_frame, text="连接")
        self.btn_test_connection.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_save_config = ttk.Button(btn_frame, text="保存")
        self.btn_save_config.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_file_manager = ttk.Button(btn_frame, text="文件管理")
        self.btn_file_manager.pack(side=tk.LEFT, padx=(0, 5))
        
        # 状态信息（主机名、操作系统等）- 双列布局节省空间
        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(row=4, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 5))
        
        # 第1行：主机名 | 操作系统
        ttk.Label(frame, text="主机名:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.hostname_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.hostname_info_var).grid(row=5, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="操作系统:").grid(row=5, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.os_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.os_info_var).grid(row=5, column=3, sticky=tk.W, pady=2)
        
        # 第2行：CPU | GPU
        ttk.Label(frame, text="CPU:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.cpu_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.cpu_info_var).grid(row=6, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="GPU:").grid(row=6, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.gpu_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.gpu_info_var).grid(row=6, column=3, sticky=tk.W, pady=2)
        
        # 第3行：内存 | 磁盘
        ttk.Label(frame, text="内存:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.memory_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.memory_info_var).grid(row=7, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="磁盘:").grid(row=7, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.disk_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.disk_info_var).grid(row=7, column=3, sticky=tk.W, pady=2)
        
        # 第4行：Ping | 连接状态
        ttk.Label(frame, text="Ping:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.ping_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.ping_info_var).grid(row=8, column=1, sticky=tk.W, pady=2)
        self.connection_status_var = tk.StringVar(value="未连接")
        ttk.Label(frame, text="连接状态:").grid(row=8, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        
        # 连接状态图标+文本
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=8, column=3, sticky=tk.W, pady=2)
        # 使用 Canvas 绘制圆点，兼容性更好
        self.status_canvas = tk.Canvas(status_frame, width=12, height=12, bg="white", highlightthickness=0)
        self.status_canvas.create_oval(1, 1, 11, 11, fill="red", outline="red")
        self.status_canvas.pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.connection_status_var).pack(side=tk.LEFT, padx=(5, 0))
    
    def _create_monitor_section(self, parent, row, column):
        """创建系统监控区域 - 严格按照设计稿"""
        frame = ttk.Labelframe(parent, text="系统监控", padding="10")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(0, weight=0)
        frame.rowconfigure(1, weight=1)
        frame.rowconfigure(2, weight=1)
        
        # 训练状态信息（设计稿顶部）
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Label(status_frame, textvariable=self.training_status_var, font=("Arial", 12, "bold"), 
                 foreground="#007bff").pack(side=tk.LEFT, padx=5)
        ttk.Label(status_frame, textvariable=self.status_duration_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(status_frame, textvariable=self.status_eta_var).pack(side=tk.LEFT, padx=5)
        
        # 监控大屏按钮（右侧图标）
        self.btn_fullscreen_monitor = ttk.Button(status_frame, text="⛶", width=3)
        self.btn_fullscreen_monitor.pack(side=tk.RIGHT, padx=5)
        
        # 第1行：CPU监控和GPU监控
        self.cpu_frame = ttk.Labelframe(frame, text="CPU监控", padding="10")
        self.cpu_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=(0, 5))
        self.cpu_usage_var = tk.StringVar(value="0%")
        ttk.Label(self.cpu_frame, textvariable=self.cpu_usage_var, font=("Arial", 16, "bold")).pack(expand=True, pady=20)
        
        self.gpu_frame = ttk.Labelframe(frame, text="GPU监控", padding="10")
        self.gpu_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 5))
        self.gpu_usage_var = tk.StringVar(value="0%")
        ttk.Label(self.gpu_frame, textvariable=self.gpu_usage_var, font=("Arial", 16, "bold")).pack(expand=True, pady=20)
        
        # 第2行：Loss曲线
        self.loss_frame = ttk.Labelframe(frame, text="Loss曲线", padding="10")
        self.loss_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(5, 0))
        ttk.Label(self.loss_frame, text="Loss曲线区域").pack(expand=True, pady=30)
    
    def _create_log_section(self, parent, row, column):
        """创建训练日志区域"""
        frame = ttk.Labelframe(parent, text="训练日志", padding="10")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(frame, height=15, width=40, font=('Consolas', 10))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def _create_training_params_section(self, parent, row, column):
        """创建训练参数区域 - 严格按照设计稿"""
        frame = ttk.Labelframe(parent, text="训练参数", padding="10")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=0)
        frame.columnconfigure(1, weight=1)
        
        # 第1行：训练轮数和批次大小
        ttk.Label(frame, text="训练轮数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.epochs_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="批次大小:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Entry(frame, textvariable=self.batch_size_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=5)
        
        # 第2行：训练轮次和分辨率
        ttk.Label(frame, text="训练轮次:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.epochs_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="分辨率:").grid(row=1, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Entry(frame, textvariable=self.image_size_var, width=10).grid(row=1, column=3, sticky=tk.W, pady=5)
        
        # 第3行：学习率和模型命名
        ttk.Label(frame, text="学习率:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.learning_rate_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="模型命名:").grid(row=2, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Entry(frame, textvariable=self.model_name_suffix_var, width=10).grid(row=2, column=3, sticky=tk.W, pady=5)
        
        # 第4行：基础模型
        ttk.Label(frame, text="基础模型:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.cmb_base_model = ttk.Combobox(frame, textvariable=self.base_model_var, width=15)
        self.cmb_base_model['values'] = (
            'yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt',
            'yolov9c.pt', 'yolov9e.pt',
            'yolov10n.pt', 'yolov10s.pt', 'yolov10m.pt', 'yolov10b.pt', 'yolov10l.pt', 'yolov10x.pt',
            'yolov11n.pt', 'yolov11s.pt', 'yolov11m.pt', 'yolov11l.pt', 'yolov11x.pt'
        )
        self.cmb_base_model.grid(row=3, column=1, columnspan=3, sticky=tk.W, pady=5, padx=(0, 5))
    
    def _create_progress_section(self, parent, row, column, columnspan=1):
        """创建操作进度区域 - 紧凑布局"""
        frame = ttk.Labelframe(parent, text="操作进度", padding="5")
        frame.grid(row=row, column=column, columnspan=columnspan, sticky=(tk.W, tk.E), padx=5, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        
        ttk.Label(frame, textvariable=self.upload_status_var, wraplength=700, font=('Arial', 9)).grid(row=0, column=0, sticky=tk.W, pady=1)
        ttk.Label(frame, textvariable=self.dataset_check_status_var, wraplength=700, font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=1)
        ttk.Label(frame, textvariable=self.dataset_summary_var, wraplength=700, font=('Arial', 9)).grid(row=2, column=0, sticky=tk.W, pady=1)
        
        self.progress_bar = ttk.Progressbar(frame, variable=self.upload_progress_var, maximum=100)
        self.progress_bar.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
    
    def _create_augment_section(self, parent, row, column):
        """创建图像增强区域 - 紧凑布局"""
        frame = ttk.Labelframe(parent, text="图像增强", padding="5")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E), padx=5, pady=0)
        frame.columnconfigure(1, weight=1)
        
        # 图像增强参数配置
        augment_configs = [
            ("缩放增强:", self.augment_scale_var, 0.0, 1.0, 0.5),
            ("水平翻转:", self.augment_fliplr_var, 0.0, 1.0, 0.5),
            ("色调变化:", self.augment_hsv_h_var, 0.0, 0.1, 0.015),
            ("饱和变化:", self.augment_hsv_s_var, 0.0, 1.0, 0.7),
            ("亮度变化:", self.augment_hsv_v_var, 0.0, 1.0, 0.4),
        ]
        
        self.augment_sliders = {}
        self.augment_active_vars = {}
        
        for i, (label, var, from_, to, default) in enumerate(augment_configs):
            ttk.Label(frame, text=label, width=10, font=('Arial', 9)).grid(row=i, column=0, sticky=tk.W, pady=2)
            
            slider_frame = ttk.Frame(frame)
            slider_frame.grid(row=i, column=1, sticky=(tk.W, tk.E), pady=2)
            slider_frame.columnconfigure(0, weight=1)
            
            resolution = 0.001 if to <= 1 else 0.01
            scale = tk.Scale(slider_frame, from_=from_, to=to, orient=tk.HORIZONTAL,
                           variable=var, resolution=resolution,
                           showvalue=False, length=100, sliderlength=12)
            scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            value_label = ttk.Label(slider_frame, text=f"{var.get():.3f}", width=6, font=('Arial', 9))
            value_label.grid(row=0, column=1, padx=(5, 0))
            
            active_var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(slider_frame, text="启用", variable=active_var, width=5)
            chk.grid(row=0, column=2, padx=(5, 0))
            
            self.augment_sliders[label] = (scale, value_label)
            self.augment_active_vars[label] = active_var
            
            # 绑定数值更新
            def update_value(*args, v=var, lbl=value_label):
                lbl.config(text=f"{v.get():.3f}")
            var.trace_add('write', update_value)
    
    def _create_dataset_info_section(self, parent, row, column):
        """创建数据集信息区域 - 严格按照设计稿"""
        frame = ttk.Labelframe(parent, text="数据集信息", padding="10")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        frame.columnconfigure(1, weight=1)
        
        # 本地路径
        ttk.Label(frame, text="本地路径:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.dataset_path_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # 云端路径
        ttk.Label(frame, text="云端路径:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.remote_dataset_path_var, width=30).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5)
        
        # 类别数、本地图片数和云端图片数（同一行）
        info_frame = ttk.Frame(frame)
        info_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Label(info_frame, text="类别数：3").pack(side=tk.LEFT, padx=10)
        ttk.Label(info_frame, text="本地图片数：60 张").pack(side=tk.LEFT, padx=10)
        ttk.Label(info_frame, text="云端图片数：60 张").pack(side=tk.LEFT, padx=10)
        
        # 类别列表
        ttk.Label(frame, text="类别列表:").grid(row=4, column=0, sticky=tk.W, pady=5)
        
        # 创建Treeview容器（带滚动条）
        tree_container = ttk.Frame(frame)
        tree_container.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=5)
        tree_container.columnconfigure(0, weight=1)
        tree_container.rowconfigure(0, weight=1)
        
        # 创建Treeview
        columns = ("序号", "类别名称")
        self.classes_tree = ttk.Treeview(tree_container, columns=columns, show="headings", height=4)
        self.classes_tree.heading("序号", text="序号", anchor=tk.W)
        self.classes_tree.heading("类别名称", text="类别名称", anchor=tk.W)
        self.classes_tree.column("序号", width=50, minwidth=50, anchor=tk.W)
        self.classes_tree.column("类别名称", width=150, minwidth=100, anchor=tk.W)
        self.classes_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.classes_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.classes_tree.configure(yscrollcommand=scrollbar.set)
        
        # 插入示例数据
        self.classes_tree.insert("", tk.END, values=("0", "汽车"))
        self.classes_tree.insert("", tk.END, values=("1", "建筑物"))
        self.classes_tree.insert("", tk.END, values=("2", "飞机"))
        self.classes_tree.insert("", tk.END, values=("3", "工人"))
        
        # 按钮行
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=(10, 0))
        
        self.btn_select_dataset = ttk.Button(btn_frame, text="选择训练集")
        self.btn_select_dataset.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_upload_dataset = ttk.Button(btn_frame, text="上传训练集", bootstyle="success")
        self.btn_upload_dataset.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_check_dataset = ttk.Button(btn_frame, text="检查训练集")
        self.btn_check_dataset.pack(side=tk.LEFT, padx=(0, 5))
        
        self.btn_clear_dataset = ttk.Button(btn_frame, text="清空训练集", bootstyle="danger")
        self.btn_clear_dataset.pack(side=tk.LEFT, padx=(0, 5))
    
    def _create_quick_cards_section(self, parent, row, column):
        """创建快捷功能卡片区域 - 严格按照设计稿"""
        frame = ttk.Labelframe(parent, text="快捷功能", padding="10")
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        
        # 训练控制卡片
        training_card = ttk.Labelframe(frame, text="训练控制", padding="10")
        training_card.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5), pady=(0, 5))
        
        self.btn_check_env = ttk.Button(training_card, text="检查环境", width=10)
        self.btn_check_env.pack(pady=5, fill=tk.X)
        
        self.btn_fix_env = ttk.Button(training_card, text="修复环境", width=10, state="disabled")
        self.btn_fix_env.pack(pady=5, fill=tk.X)
        
        self.btn_start_training = ttk.Button(training_card, text="开始训练", width=10, bootstyle="success")
        self.btn_start_training.pack(pady=5, fill=tk.X)
        
        # 模型管理卡片
        model_card = ttk.Labelframe(frame, text="模型管理", padding="10")
        model_card.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 5), pady=(0, 5))
        
        self.btn_download_model = ttk.Button(model_card, text="下载模型", width=10, bootstyle="info")
        self.btn_download_model.pack(pady=5, fill=tk.X)
        
        self.btn_convert_tflite = ttk.Button(model_card, text="TFLite转换", width=10)
        self.btn_convert_tflite.pack(pady=5, fill=tk.X)
        
        # 预留卡片
        reserve_card = ttk.Labelframe(frame, text="预留", padding="10")
        reserve_card.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 5))
        
        ttk.Label(reserve_card, text="预留功能区域").pack(expand=True, pady=20)

    # ==================== Pack版本的方法（用于左列垂直排列） ====================
    
    def _create_server_section_pack(self, parent):
        """创建服务器设置区域 - Pack版本（左列）"""
        frame = ttk.Labelframe(parent, text="服务器设置", padding="10")
        frame.pack(fill=tk.X, pady=(0, 5))
        
        # 配置4列布局（前3行用2列，状态信息用4列）
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=1)
        
        # 服务器IP
        ttk.Label(frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.hostname_var, width=20).grid(row=0, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 端口
        ttk.Label(frame, text="端口:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.port_var, width=20).grid(row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 用户名
        ttk.Label(frame, text="用户名:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.username_var, width=20).grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5)
        
        # 按钮行
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=(10, 0))
        self.btn_test_connection = ttk.Button(btn_frame, text="连接", width=8)
        self.btn_test_connection.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_save_config = ttk.Button(btn_frame, text="保存", width=8)
        self.btn_save_config.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_file_manager = ttk.Button(btn_frame, text="文件管理", width=8)
        self.btn_file_manager.pack(side=tk.LEFT, padx=(0, 5))
        
        # 状态信息（主机名、操作系统等）- 双列布局节省空间
        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(row=4, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 5))
        
        # 第1行：主机名 | 操作系统
        ttk.Label(frame, text="主机名:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.hostname_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.hostname_info_var).grid(row=5, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="操作系统:").grid(row=5, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.os_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.os_info_var).grid(row=5, column=3, sticky=tk.W, pady=2)
        
        # 第2行：CPU | GPU
        ttk.Label(frame, text="CPU:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.cpu_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.cpu_info_var).grid(row=6, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="GPU:").grid(row=6, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.gpu_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.gpu_info_var).grid(row=6, column=3, sticky=tk.W, pady=2)
        
        # 第3行：内存 | 磁盘
        ttk.Label(frame, text="内存:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.memory_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.memory_info_var).grid(row=7, column=1, sticky=tk.W, pady=2)
        ttk.Label(frame, text="磁盘:").grid(row=7, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.disk_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.disk_info_var).grid(row=7, column=3, sticky=tk.W, pady=2)
        
        # 第4行：Ping | 连接状态
        ttk.Label(frame, text="Ping:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.ping_info_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.ping_info_var).grid(row=8, column=1, sticky=tk.W, pady=2)
        self.connection_status_var = tk.StringVar(value="未连接")
        ttk.Label(frame, text="连接状态:").grid(row=8, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        ttk.Label(frame, textvariable=self.connection_status_var).grid(row=8, column=3, sticky=tk.W, pady=2)
    
    def _create_training_params_section_pack(self, parent):
        """创建训练参数区域 - Pack版本（左列）"""
        frame = ttk.Labelframe(parent, text="训练参数", padding="10")
        frame.pack(fill=tk.X, pady=(0, 5))
        frame.columnconfigure(1, weight=1)
        
        # 第1行：训练轮数和批次大小
        ttk.Label(frame, text="训练轮数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.epochs_var, width=10).grid(row=0, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="批次大小:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Entry(frame, textvariable=self.batch_size_var, width=10).grid(row=0, column=3, sticky=tk.W, pady=5)
        
        # 第2行：训练轮次和分辨率
        ttk.Label(frame, text="训练轮次:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.epochs_var, width=10).grid(row=1, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="分辨率:").grid(row=1, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Entry(frame, textvariable=self.image_size_var, width=10).grid(row=1, column=3, sticky=tk.W, pady=5)
        
        # 第3行：学习率和模型命名
        ttk.Label(frame, text="学习率:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.learning_rate_var, width=10).grid(row=2, column=1, sticky=tk.W, pady=5)
        
        ttk.Label(frame, text="模型命名:").grid(row=2, column=2, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Entry(frame, textvariable=self.model_name_suffix_var, width=10).grid(row=2, column=3, sticky=tk.W, pady=5)
        
        # 第4行：基础模型
        ttk.Label(frame, text="基础模型:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.cmb_base_model = ttk.Combobox(frame, textvariable=self.base_model_var, width=15)
        self.cmb_base_model['values'] = (
            'yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt',
            'yolov9c.pt', 'yolov9e.pt',
            'yolov10n.pt', 'yolov10s.pt', 'yolov10m.pt', 'yolov10b.pt', 'yolov10l.pt', 'yolov10x.pt',
            'yolov11n.pt', 'yolov11s.pt', 'yolov11m.pt', 'yolov11l.pt', 'yolov11x.pt'
        )
        self.cmb_base_model.grid(row=3, column=1, columnspan=3, sticky=tk.W, pady=5, padx=(0, 5))
    
    def _create_augment_section_pack(self, parent):
        """创建图像增强区域 - Pack版本（左列）"""
        frame = ttk.Labelframe(parent, text="图像增强", padding="5")
        frame.pack(fill=tk.X, pady=(0, 5))
        frame.columnconfigure(1, weight=1)
        
        # 图像增强参数配置（7个参数：原5个 + 垂直翻转 + 透视变换）
        augment_configs = [
            ("缩放增强:", self.augment_scale_var, 0.0, 1.0, 0.5),
            ("水平翻转:", self.augment_fliplr_var, 0.0, 1.0, 0.5),
            ("垂直翻转:", self.flipud_var, 0.0, 1.0, 0.5),
            ("透视变换:", self.perspective_var, 0.0, 1.0, 0.5),
            ("色调变化:", self.augment_hsv_h_var, 0.0, 0.1, 0.015),
            ("饱和变化:", self.augment_hsv_s_var, 0.0, 1.0, 0.7),
            ("亮度变化:", self.augment_hsv_v_var, 0.0, 1.0, 0.4),
        ]
        
        self.augment_sliders = {}
        self.augment_active_vars = {}
        
        for i, (label, var, from_, to, default) in enumerate(augment_configs):
            # 增加字体大小从9改为11，改善可读性
            ttk.Label(frame, text=label, width=10, font=('Arial', 11)).grid(row=i, column=0, sticky=tk.W, pady=5)
            
            slider_frame = ttk.Frame(frame)
            slider_frame.grid(row=i, column=1, sticky=(tk.W, tk.E), pady=5)
            slider_frame.columnconfigure(0, weight=1)
            
            resolution = 0.001 if to <= 1 else 0.01
            scale = tk.Scale(slider_frame, from_=from_, to=to, orient=tk.HORIZONTAL,
                           variable=var, resolution=resolution,
                           showvalue=False, length=100, sliderlength=12)
            scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            value_label = ttk.Label(slider_frame, text=f"{var.get():.3f}", width=6, font=('Arial', 10))
            value_label.grid(row=0, column=1, padx=(5, 0))
            
            active_var = tk.BooleanVar(value=True)
            chk = ttk.Checkbutton(slider_frame, text="启用", variable=active_var, width=5)
            chk.grid(row=0, column=2, padx=(5, 0))
            
            self.augment_sliders[label] = (scale, value_label)
            self.augment_active_vars[label] = active_var
            
            # 绑定数值更新
            def update_value(*args, v=var, lbl=value_label):
                lbl.config(text=f"{v.get():.3f}")
            var.trace_add('write', update_value)


# 测试代码
if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()
