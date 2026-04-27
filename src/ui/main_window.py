#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端训练管理平台 v3.0.5 - 纯UI界面
仅负责布局和控件创建，不包含业务逻辑
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import scrolledtext
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import time
import numpy as np
import math


class MainWindow:
    """主窗口UI类 - 纯UI，不包含业务逻辑"""
    
    def __init__(self, root):
        self.root = root
        self.app_version = "v3.0.5"
        self.root.title(f"云端训练管理平台 {self.app_version}")
        self.root.geometry("1240x900")
        self.root.minsize(1190, 720)
        self.root.resizable(True, True)
        
        # 初始化所有UI变量（StringVar/IntVar等）
        self._init_variables()
        
        # 创建UI
        self._create_ui()
    
    def _init_variables(self):
        """初始化所有UI变量"""
        # --- UI状态回调等 ---
        self.log_message = lambda msg: print(msg) # 默认的打印函数，主程序会覆盖它
        
        # 服务器配置变量
        self.hostname_var = tk.StringVar(value="")
        self.port_var = tk.StringVar(value="22")
        self.username_var = tk.StringVar(value="root")
        self.password_var = tk.StringVar(value="")
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
        self.augment_scale_active_var = tk.BooleanVar(value=True)
        self.augment_fliplr_active_var = tk.BooleanVar(value=True)
        self.augment_flipud_active_var = tk.BooleanVar(value=True)
        self.augment_perspective_active_var = tk.BooleanVar(value=True)
        self.augment_hsv_h_active_var = tk.BooleanVar(value=True)
        self.augment_hsv_s_active_var = tk.BooleanVar(value=True)
        self.augment_hsv_v_active_var = tk.BooleanVar(value=True)
        
        # 数据集变量
        self.dataset_path_var = tk.StringVar(value="D:\\datasets\\train")
        self.local_path_var = tk.StringVar(value="")
        self.remote_path_var = tk.StringVar(value="/root/yolo_dataset")
        self.dataset_name_var = tk.StringVar(value="")
        self.num_classes_var = tk.StringVar(value="0")
        self.local_image_count_var = tk.StringVar(value="本地图片数：-")
        self.local_dataset_status_var = tk.StringVar(value="状态: 未检查")
        self.remote_image_count_var = tk.StringVar(value="云端图片数：-")
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
        self.upload_max_workers_var = tk.StringVar(value="8")
        self.training_status_var = tk.StringVar(value="未开始")
        self.status_duration_var = tk.StringVar(value="时长: 00:00:00")
        self.status_eta_var = tk.StringVar(value="预计完成: --")
        self.cpu_usage_var = tk.StringVar(value="0%")
        self.gpu_usage_var = tk.StringVar(value="0%")
        
        # 底部状态栏变量
        self.status_ping_var = tk.StringVar(value="--")
        self.status_loss_var = tk.StringVar(value="--")
        self.status_window_size_var = tk.StringVar(value="-- x --")
        self.status_time_var = tk.StringVar(value=time.strftime("%H:%M:%S"))
        
        # 悬浮提示状态
        self._tooltip_window = None
        self._right_frame = None
        self._server_section_frame = None
        self._monitor_section_frame = None
        self._log_section_frame = None
        self._top_row_sync_after_id = None
        self._last_loss_canvas_size = (0, 0)
    
    def _create_ui(self):
        """创建主UI"""
        # 创建Notebook
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=(5, 2))
        
        # 创建数据集配置选项卡
        self._create_dataset_tab()
        
        # 底部状态栏（不占用业务容器高度）
        self._create_bottom_status_bar()
    
    def _create_bottom_status_bar(self):
        """创建底部状态栏（连接图标 + Ping + 丢包 + 尺寸 + 时间）"""
        status_bar = ttk.Frame(self.root)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=(0, 5))
        
        self.status_icon_canvas = tk.Canvas(status_bar, width=12, height=12, highlightthickness=0)
        self.status_icon_canvas.pack(side=tk.LEFT, padx=(8, 6), pady=3)
        self.status_icon_dot = self.status_icon_canvas.create_oval(1, 1, 11, 11, fill="gray", outline="gray")
        
        ttk.Label(status_bar, text="|").pack(side=tk.LEFT, padx=4)
        ttk.Label(status_bar, text="Ping").pack(side=tk.LEFT, padx=(2, 2))
        ttk.Label(status_bar, textvariable=self.status_ping_var).pack(side=tk.LEFT, padx=(0, 2))
        
        ttk.Label(status_bar, text="|").pack(side=tk.LEFT, padx=4)
        ttk.Label(status_bar, text="丢包").pack(side=tk.LEFT, padx=(2, 2))
        ttk.Label(status_bar, textvariable=self.status_loss_var).pack(side=tk.LEFT, padx=(0, 2))
        
        ttk.Label(status_bar, text="|").pack(side=tk.LEFT, padx=4)
        ttk.Label(status_bar, text="尺寸").pack(side=tk.LEFT, padx=(2, 2))
        ttk.Label(status_bar, textvariable=self.status_window_size_var).pack(side=tk.LEFT, padx=(0, 2))
        
        ttk.Label(status_bar, text="|").pack(side=tk.LEFT, padx=4)
        ttk.Label(status_bar, textvariable=self.status_time_var).pack(side=tk.LEFT, padx=(2, 0))
    
    def set_status_bar_connection_state(self, state):
        """更新底部状态栏连接图标颜色"""
        color_map = {
            "disconnected": "gray",
            "connecting": "#d4a000",
            "connected": "#28a745",
            "failed": "#dc3545",
        }
        color = color_map.get(state, "gray")
        self.status_icon_canvas.itemconfig(self.status_icon_dot, fill=color, outline=color)
    
    def update_status_bar_network(self, ping_text, loss_text, time_text=None):
        """更新底部状态栏网络信息"""
        self.status_ping_var.set(ping_text)
        self.status_loss_var.set(loss_text)
        self.status_time_var.set(time_text or time.strftime("%H:%M:%S"))
    
    def _ellipsize_text(self, text, max_chars=16):
        """对长文本做省略显示，避免撑大容器"""
        value = str(text or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars - 3] + "..."
    
    def _show_tooltip(self, text, x_root, y_root):
        """显示悬浮提示"""
        self._hide_tooltip()
        if not text:
            return
        
        tip = tk.Toplevel(self.root)
        tip.wm_overrideredirect(True)
        try:
            tip.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        
        label = tk.Label(
            tip,
            text=text,
            justify=tk.LEFT,
            background="#fff8c4",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=3
        )
        label.pack()
        tip.wm_geometry(f"+{x_root + 12}+{y_root + 12}")
        self._tooltip_window = tip
    
    def _hide_tooltip(self, _event=None):
        """隐藏悬浮提示"""
        if self._tooltip_window is not None:
            self._tooltip_window.destroy()
            self._tooltip_window = None
    
    def _create_info_value_label(self, parent, row, column, source_var, max_chars=16):
        """创建固定宽度信息标签，并在悬停时显示完整文本"""
        display_var = tk.StringVar(value=self._ellipsize_text(source_var.get(), max_chars))
        
        def sync_display(*_args):
            display_var.set(self._ellipsize_text(source_var.get(), max_chars))
        
        source_var.trace_add('write', sync_display)
        
        label = ttk.Label(parent, textvariable=display_var, width=max_chars, anchor=tk.W)
        label.grid(row=row, column=column, sticky=tk.W, pady=2)
        
        def on_enter(event):
            full_text = str(source_var.get() or "").strip()
            # 只有被截断时才显示提示，避免干扰
            if len(full_text) > max_chars:
                self._show_tooltip(full_text, event.x_root, event.y_root)
        
        def on_motion(event):
            if self._tooltip_window is not None:
                self._tooltip_window.wm_geometry(f"+{event.x_root + 12}+{event.y_root + 12}")
        
        label.bind("<Enter>", on_enter)
        label.bind("<Motion>", on_motion)
        label.bind("<Leave>", self._hide_tooltip)
        label.bind("<ButtonPress>", self._hide_tooltip)
        
        return label
    
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
        main_frame.columnconfigure(0, weight=0, minsize=360)  # 左列固定宽度
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
        self._right_frame = right_frame
        right_frame.columnconfigure(0, weight=1, minsize=400)  # 中列：自适应宽度
        right_frame.columnconfigure(1, weight=0, minsize=380)  # 右列：固定宽度 380px
        # 右侧区域采用“内容驱动高度”，避免大块空白被撑开
        right_frame.rowconfigure(0, weight=0)                  # 监控和日志行
        right_frame.rowconfigure(1, weight=0)                  # 数据集信息行
        right_frame.rowconfigure(2, weight=0)
        
        # 第1行：系统监控 | 训练日志
        self._create_monitor_section(right_frame, row=0, column=0)
        self._create_log_section(right_frame, row=0, column=1)
        
        # 第2行：数据集信息 | 快捷功能
        self._create_dataset_info_section(right_frame, row=1, column=0)
        self._create_quick_cards_section(right_frame, row=1, column=1)
        
        # 第3行：操作进度（跨2列）
        self._create_progress_section(right_frame, row=2, column=0, columnspan=2)
        self.root.after(0, self._sync_top_row_height_to_server)

    def _schedule_sync_top_row_height(self, _event=None):
        """防抖调度：按服务器设置容器高度同步右侧第1行高度。"""
        if self._top_row_sync_after_id:
            self.root.after_cancel(self._top_row_sync_after_id)
        self._top_row_sync_after_id = self.root.after(30, self._sync_top_row_height_to_server)

    def _sync_top_row_height_to_server(self):
        """读取服务器设置高度，并将 right_frame 第0行与之对齐。"""
        self._top_row_sync_after_id = None
        if not self._right_frame or not self._server_section_frame:
            return
        self.root.update_idletasks()
        target_h = int(self._server_section_frame.winfo_height() or 0)
        if target_h <= 0:
            return

        self._right_frame.rowconfigure(0, weight=0, minsize=target_h)
        for section in (self._monitor_section_frame, self._log_section_frame):
            if not section:
                continue
            section.configure(height=target_h)
            section.grid_propagate(False)

    def _create_monitor_section(self, parent, row, column):
        """创建系统监控区域 - 优化空间占用，合并文字监控"""
        frame = ttk.Labelframe(parent, text="系统监控", padding="4")
        self._monitor_section_frame = frame
        # 与同排“训练日志”等高显示（容器同高）
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 2))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=0) # 状态信息行
        frame.rowconfigure(1, weight=1) # Loss 曲线行（自适应填充剩余空间）
        
        # 训练状态信息（两行显示，紧凑布局）
        status_frame = ttk.Frame(frame)
        status_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 1))
        status_frame.columnconfigure(0, weight=1)

        top_line = ttk.Frame(status_frame)
        top_line.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 0))
        top_line.columnconfigure(0, weight=1)

        left_top = ttk.Frame(top_line)
        left_top.grid(row=0, column=0, sticky=tk.W)
        ttk.Label(left_top, textvariable=self.training_status_var, font=("Arial", 10, "bold"),
                  foreground="#007bff").pack(side=tk.LEFT, padx=(5, 8))
        ttk.Label(left_top, text="CPU:", font=("Arial", 9)).pack(side=tk.LEFT)
        ttk.Label(left_top, textvariable=self.cpu_usage_var, font=("Arial", 9, "bold"),
                  foreground="#17a2b8").pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(left_top, text="GPU:", font=("Arial", 9)).pack(side=tk.LEFT)
        ttk.Label(left_top, textvariable=self.gpu_usage_var, font=("Arial", 9, "bold"),
                  foreground="#28a745").pack(side=tk.LEFT, padx=(2, 8))

        # 监控大屏按钮
        self.btn_fullscreen_monitor = ttk.Button(top_line, text="⛶", width=3, style="sm.TButton")
        self.btn_fullscreen_monitor.grid(row=0, column=1, sticky=tk.E, padx=5)

        bottom_line = ttk.Frame(status_frame)
        bottom_line.grid(row=1, column=0, sticky=(tk.W, tk.E))
        ttk.Label(bottom_line, textvariable=self.status_duration_var, font=("Arial", 9)).pack(side=tk.LEFT, padx=(5, 4))
        ttk.Label(bottom_line, textvariable=self.status_eta_var, font=("Arial", 9)).pack(side=tk.LEFT, padx=(0, 3))
        
        # 第1行：Loss曲线 (高度缩小)
        self.loss_frame = ttk.Labelframe(frame, text="Loss曲线", padding="6")
        self.loss_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        self.loss_frame.columnconfigure(0, weight=1)
        self.loss_frame.rowconfigure(0, weight=1)
        # 移除手动的 <Configure> 绑定，交由 Matplotlib 的 FigureCanvasTkAgg 自动处理尺寸变化
        
        # 初始化 Loss 图表 (减小 figsize 以降低高度)
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        self.loss_fig = Figure(figsize=(5, 0.95), dpi=90) # 初始化尺寸，后续随容器自适应
        self.loss_fig.patch.set_facecolor('#ffffff') # 强制白色背景避免残影
        self.loss_ax = self.loss_fig.add_subplot(111)
        self.loss_fig.subplots_adjust(left=0.07, right=0.985, top=0.94, bottom=0.16)
        self.loss_ax.grid(True, linestyle='--', alpha=0.6)
        self.loss_ax.tick_params(axis='both', which='major', labelsize=6)
        
        self.loss_canvas = FigureCanvasTkAgg(self.loss_fig, self.loss_frame)
        loss_widget = self.loss_canvas.get_tk_widget()
        loss_widget.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def update_cpu_chart(self, value):
        """更新 CPU 监控文字"""
        self.cpu_usage_var.set(f"{value}%")

    def update_gpu_chart(self, value):
        """更新 GPU 监控文字"""
        self.gpu_usage_var.set(f"{value}%")

    def update_loss_chart(self, epoch_data, box_data, cls_data, dfl_data):
        """更新 Loss 曲线图表 (增强点标记与自动标注)"""
        # 完全清空 Figure 以避免多重坐标轴残影
        self.loss_fig.clear()
        self.loss_ax = self.loss_fig.add_subplot(111)
        self.loss_fig.subplots_adjust(left=0.07, right=0.985, top=0.94, bottom=0.16)
        self.loss_ax.grid(True, linestyle='--', alpha=0.4)
        self.loss_ax.tick_params(axis='both', which='major', labelsize=6)
        
        if not epoch_data or len(epoch_data) == 0:
            self.loss_canvas.draw()
            return

        try:
            # 转换数据为 list 确保索引一致
            x = list(epoch_data)
            box_y = list(box_data) if box_data else []
            cls_y = list(cls_data) if cls_data else []
            dfl_y = list(dfl_data) if dfl_data else []

            # 1. 绘制基础曲线
            if box_y:
                self.loss_ax.plot(x, box_y, label='Box', color='#ff7f0e', linewidth=1.2, marker='o', markersize=2)
            if cls_y:
                self.loss_ax.plot(x, cls_y, label='Cls', color='#1f77b4', linewidth=1.2, marker='o', markersize=2)
            if dfl_y:
                self.loss_ax.plot(x, dfl_y, label='DFL', color='#2ca02c', linewidth=1.2, marker='o', markersize=2)

            # 2. 查找并标注历史最低点（点标记实装）
            def find_min_point(xs, ys):
                if not ys or len(ys) < 2: return None, None
                valid_ys = [(v, i) for i, v in enumerate(ys[:-1]) if np.isfinite(v)]
                if not valid_ys: return None, None
                min_v, min_idx = min(valid_ys, key=lambda x: x[0])
                return xs[min_idx], min_v

            min_points = []
            if box_y:
                mx, my = find_min_point(x, box_y)
                if mx is not None: min_points.append({'x': mx, 'y': my, 'color': '#ff7f0e', 'label': 'box'})
            if cls_y:
                mx, my = find_min_point(x, cls_y)
                if mx is not None: min_points.append({'x': mx, 'y': my, 'color': '#1f77b4', 'label': 'cls'})
            if dfl_y:
                mx, my = find_min_point(x, dfl_y)
                if mx is not None: min_points.append({'x': mx, 'y': my, 'color': '#2ca02c', 'label': 'dfl'})

            # 绘制最低点大圆点
            for pt in min_points:
                self.loss_ax.plot(pt['x'], pt['y'], marker='o', markersize=4, 
                                 markerfacecolor='white', markeredgecolor=pt['color'], 
                                 markeredgewidth=1, linestyle='None', zorder=5)
                # 添加标注文字
                self.loss_ax.annotate(f"{pt['y']:.3f}", xy=(pt['x'], pt['y']), 
                                     xytext=(3, 3), textcoords='offset points',
                                     fontsize=6, color=pt['color'], fontweight='bold')

            # 3. 添加右上角状态面板
            latest_epoch = x[-1]
            latest_total = 0
            count = 0
            if box_y: latest_total += box_y[-1]; count += 1
            if cls_y: latest_total += cls_y[-1]; count += 1
            if dfl_y: latest_total += dfl_y[-1]; count += 1
            
            panel_text = f"Epoch: {latest_epoch}"
            if count > 0:
                panel_text += f"\nLoss: {latest_total:.4f}"
            
            self.loss_ax.text(0.97, 0.97, panel_text, transform=self.loss_ax.transAxes,
                             ha='right', va='top', fontsize=7,
                             bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#cccccc', alpha=0.8))

            self.loss_ax.legend(fontsize=6, loc='upper left', framealpha=0.5)
            
        except Exception as e:
            print(f"Update loss chart error: {e}")

        self.loss_canvas.draw()

    def _create_log_section(self, parent, row, column):
        """创建训练日志区域"""
        frame = ttk.Labelframe(parent, text="训练日志", padding="10")
        self._log_section_frame = frame
        frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(0, 5))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(frame, height=15, width=40, font=('Consolas', 10))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
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
        
        ttk.Label(info_frame, text="类别数：").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Label(info_frame, textvariable=self.num_classes_var).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(info_frame, textvariable=self.local_image_count_var).pack(side=tk.LEFT, padx=10)
        ttk.Label(info_frame, textvariable=self.remote_image_count_var).pack(side=tk.LEFT, padx=10)
        
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
        
        # 初始清空示例数据
        for item in self.classes_tree.get_children():
            self.classes_tree.delete(item)
            
        # 按钮行
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        btn_frame.columnconfigure(3, weight=1)

        self.btn_select_dataset = ttk.Button(btn_frame, text="选择训练集")
        self.btn_select_dataset.grid(row=0, column=0, padx=(0, 5), sticky=tk.W)

        self.btn_upload_dataset = ttk.Button(btn_frame, text="上传训练集", bootstyle="success")
        self.btn_upload_dataset.grid(row=0, column=1, padx=(0, 5), sticky=tk.W)

        self.btn_clear_dataset = ttk.Button(btn_frame, text="清空训练集", bootstyle="danger")
        self.btn_clear_dataset.grid(row=0, column=2, padx=(0, 5), sticky=tk.W)

        self.cmb_upload_workers = ttk.Combobox(
            btn_frame,
            width=5,
            textvariable=self.upload_max_workers_var,
            state="readonly",
            justify="center",
            values=[str(i) for i in range(1, 33)],
        )
        self.cmb_upload_workers.grid(row=0, column=5, padx=(8, 0), sticky=tk.E)
    
    def update_classes_table(self, classes_list):
        """更新类别列表表格
        :param classes_list: 类别名称列表或包含 (id, name) 的元组列表
        """
        for item in self.classes_tree.get_children():
            self.classes_tree.delete(item)
            
        if not classes_list:
            return
            
        for idx, item in enumerate(classes_list):
            if isinstance(item, (list, tuple)):
                cid, name = item
            else:
                cid, name = idx, item
            self.classes_tree.insert("", tk.END, values=(str(cid), str(name)))
    
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
        
        # 预留卡片
        reserve_card = ttk.Labelframe(frame, text="预留", padding="10")
        reserve_card.grid(row=0, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0), pady=(0, 5))
        
        ttk.Label(reserve_card, text="该区域功能开发中").pack(pady=(12, 8))
        self.btn_reserved_feature = ttk.Button(reserve_card, text="查看说明", width=10)
        self.btn_reserved_feature.pack(pady=(0, 12))

    # ==================== Pack版本的方法（用于左列垂直排列） ====================
    
    def _create_server_section_pack(self, parent):
        """创建服务器设置区域 - Pack版本（左列）"""
        frame = ttk.Labelframe(parent, text="服务器设置", padding="10")
        self._server_section_frame = frame
        frame.pack(fill=tk.X, pady=(0, 5))
        frame.bind("<Configure>", self._schedule_sync_top_row_height)
        
        # 配置4列布局（前3行用2列，状态信息用4列）
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=0, minsize=130)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=0, minsize=130)
        
        # 第1行: 服务器IP 和 端口
        ttk.Label(frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.hostname_var, width=14).grid(
            row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(0, 5)
        )
        ttk.Label(frame, text="端口:").grid(row=0, column=2, sticky=tk.W, pady=5, padx=(8, 1))
        ttk.Entry(frame, textvariable=self.port_var, width=6).grid(
            row=0, column=3, sticky=tk.W, pady=5
        )
        
        # 第2行: 用户名
        ttk.Label(frame, text="用户名:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.username_var, width=20).grid(
            row=1, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5
        )

        # 第3行: 密码
        ttk.Label(frame, text="密码:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.password_var, show="*", width=20).grid(
            row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), pady=5
        )
        
        # 按钮行
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=(10, 0))
        self.btn_test_connection = ttk.Button(btn_frame, text="连接", width=8)
        self.btn_test_connection.pack(side=tk.LEFT, padx=(0, 5))
        self.btn_file_manager = ttk.Button(btn_frame, text="文件管理", width=8)
        self.btn_file_manager.pack(side=tk.LEFT, padx=(0, 5))
        
        # 状态信息（主机名、操作系统等）- 双列布局节省空间
        sep = ttk.Separator(frame, orient=tk.HORIZONTAL)
        sep.grid(row=4, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 5))

        # 连接状态显示（与 main_v3 逻辑对齐）
        self.connection_status_label = ttk.Label(frame, textvariable=self.connection_status_var, foreground="red")
        self.connection_status_label.grid(row=5, column=0, columnspan=4, pady=5)
        
        # 第1行：主机名 | 操作系统
        ttk.Label(frame, text="主机名:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.hostname_info_var = tk.StringVar(value="")
        self._create_info_value_label(frame, 6, 1, self.hostname_info_var, max_chars=16)
        ttk.Label(frame, text="操作系统:").grid(row=6, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.os_info_var = tk.StringVar(value="")
        self._create_info_value_label(frame, 6, 3, self.os_info_var, max_chars=16)
        
        # 第2行：CPU | GPU
        ttk.Label(frame, text="CPU:").grid(row=7, column=0, sticky=tk.W, pady=2)
        self.cpu_info_var = tk.StringVar(value="")
        self._create_info_value_label(frame, 7, 1, self.cpu_info_var, max_chars=16)
        ttk.Label(frame, text="GPU:").grid(row=7, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.gpu_info_var = tk.StringVar(value="")
        self._create_info_value_label(frame, 7, 3, self.gpu_info_var, max_chars=16)
        
        # 第3行：内存 | 磁盘
        ttk.Label(frame, text="内存:").grid(row=8, column=0, sticky=tk.W, pady=2)
        self.memory_info_var = tk.StringVar(value="")
        self._create_info_value_label(frame, 8, 1, self.memory_info_var, max_chars=16)
        ttk.Label(frame, text="磁盘:").grid(row=8, column=2, sticky=tk.W, padx=(15, 0), pady=2)
        self.disk_info_var = tk.StringVar(value="")
        self._create_info_value_label(frame, 8, 3, self.disk_info_var, max_chars=16)
    
    def _create_training_params_section_pack(self, parent):
        """创建训练参数区域 - Pack版本（左列） - 3行2列等发布局优化"""
        frame = ttk.Labelframe(parent, text="训练参数", padding="10")
        frame.pack(fill=tk.X, pady=(0, 5))
        
        # 强制1和3列绝对等宽，并配置权重
        frame.columnconfigure(1, weight=1, uniform="group1")
        frame.columnconfigure(3, weight=1, uniform="group1")
        
        # 第1行：训练轮数 和 批次大小
        ttk.Label(frame, text="训练轮数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.epochs_var, width=8).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(0, 15))
        
        ttk.Label(frame, text="批次大小:").grid(row=0, column=2, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.batch_size_var, width=8).grid(row=0, column=3, sticky=(tk.W, tk.E), pady=5)
        
        # 第2行：分辨率 和 学习率
        ttk.Label(frame, text="分辨率:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.image_size_var, width=8).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=(0, 15))
        
        ttk.Label(frame, text="学习率:").grid(row=1, column=2, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.learning_rate_var, width=8).grid(row=1, column=3, sticky=(tk.W, tk.E), pady=5)
        
        # 第3行：模型命名 和 基础模型
        ttk.Label(frame, text="模型命名:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Entry(frame, textvariable=self.model_name_suffix_var, width=8).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=(0, 15))
        
        ttk.Label(frame, text="基础模型:").grid(row=2, column=2, sticky=tk.W, pady=5)
        self.cmb_base_model = ttk.Combobox(frame, textvariable=self.base_model_var, width=12)
        self.cmb_base_model['values'] = (
            'yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt',
            'yolov9c.pt', 'yolov9e.pt',
            'yolov10n.pt', 'yolov10s.pt', 'yolov10m.pt', 'yolov10b.pt', 'yolov10l.pt', 'yolov10x.pt',
            'yolov11n.pt', 'yolov11s.pt', 'yolov11m.pt', 'yolov11l.pt', 'yolov11x.pt'
        )
        # 下拉框不强制填满（去掉 tk.E），使其长度更自然
        self.cmb_base_model.grid(row=2, column=3, sticky=tk.W, pady=5)
    
    def _create_augment_section_pack(self, parent):
        """创建图像增强区域 - Pack版本（左列）"""
        frame = ttk.Labelframe(parent, text="图像增强", padding="5")
        frame.pack(fill=tk.X, pady=(0, 5))
        frame.columnconfigure(1, weight=1)
        
        # 图像增强参数配置（7个参数：原5个 + 垂直翻转 + 透视变换）
        augment_configs = [
            ("augment_scale", "缩放增强:", self.augment_scale_var, 0.0, 1.0, 0.5, self.augment_scale_active_var),
            ("augment_fliplr", "水平翻转:", self.augment_fliplr_var, 0.0, 1.0, 0.5, self.augment_fliplr_active_var),
            ("augment_flipud", "垂直翻转:", self.flipud_var, 0.0, 1.0, 0.5, self.augment_flipud_active_var),
            ("augment_perspective", "透视变换:", self.perspective_var, 0.0, 1.0, 0.5, self.augment_perspective_active_var),
            ("augment_hsv_h", "色调变化:", self.augment_hsv_h_var, 0.0, 0.1, 0.015, self.augment_hsv_h_active_var),
            ("augment_hsv_s", "饱和变化:", self.augment_hsv_s_var, 0.0, 1.0, 0.7, self.augment_hsv_s_active_var),
            ("augment_hsv_v", "亮度变化:", self.augment_hsv_v_var, 0.0, 1.0, 0.4, self.augment_hsv_v_active_var),
        ]
        
        self.augment_sliders = {}
        self.augment_active_vars = {}
        
        for i, (key, label, var, from_, to, default, active_var) in enumerate(augment_configs):
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
            
            chk = ttk.Checkbutton(slider_frame, text="启用", variable=active_var, width=5)
            chk.grid(row=0, column=2, padx=(5, 0))
            
            self.augment_sliders[label] = (scale, value_label)
            self.augment_active_vars[key] = active_var
            
            # 绑定数值更新
            def update_value(*args, v=var, lbl=value_label):
                lbl.config(text=f"{v.get():.3f}")
            var.trace_add('write', update_value)


# 测试代码
if __name__ == "__main__":
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()
