import threading
import time
import re
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ttkbootstrap as ttkb

from src.ui.main_window import MainWindow
from src.ui.file_manager_window import FileManagerWindow
from src.ui.monitor_window import MonitorWindow
from src.core.config_manager import ConfigManager
from src.core.server_manager import ServerManager
from src.core.dataset_manager import DatasetManager
from src.core.training_manager import TrainingManager
from src.core.monitor_manager import MonitorManager
from src.core.environment_manager import EnvironmentManager
from src.core.network_monitor_manager import NetworkMonitorManager
from src.core.model_manager import ModelManager
from src.core.file_manager_manager import FileManagerManager
from src.core.training_monitor_manager import TrainingMonitorManager
from src.core.model_download_manager import ModelDownloadManager
from src.core.config_binding_manager import ConfigBindingManager
from src.core.training_log_manager import TrainingLogManager
from src.core.training_progress_manager import TrainingProgressManager
from src.utils.notifier import Notifier

class Application:
    """应用程序主类"""

    def __init__(self):
        # 尝试开启 DPI 感知
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

        self.config_manager = ConfigManager()
        self.server_manager = ServerManager(self.config_manager)
        self.dataset_manager = DatasetManager(self.config_manager)
        self.environment_manager = EnvironmentManager(self.server_manager)
        self.training_manager = TrainingManager(self.config_manager, self.server_manager, self.environment_manager)
        self.monitor_manager = MonitorManager(self.config_manager, self.server_manager)
        self.network_monitor_manager = NetworkMonitorManager()
        self.model_manager = ModelManager(self.config_manager, self.server_manager)
        self.file_manager_manager = FileManagerManager(self.server_manager)
        self.training_monitor_manager = TrainingMonitorManager(self.server_manager)
        self.model_download_manager = ModelDownloadManager(self.server_manager)
        self.config_binding_manager = ConfigBindingManager()
        self.training_log_manager = TrainingLogManager(archive_dir="logs")
        self.training_progress_manager = TrainingProgressManager()

        self.root = ttkb.Window(themename="cosmo")
        self.ui = MainWindow(self.root)
        self.ui.log_message = self._log_message
        self._setup_log_tags()
        self._ensure_startup_window_size()

        self._load_config_to_ui()
        self._bind_events()

        self._ping_after_id = None
        self._ping_monitor_enabled = False
        self._monitor_window = None
        self._monitor_after_id = None
        self._system_monitor_after_id = None
        self._system_monitor_busy = False
        self._loss_chart_refresh_busy = False
        self._loss_chart_refresh_fn = None
        self._training_running = False
        self._training_stop_requested = False
        self._upload_running = False
        self._upload_stop_requested = False
        self._remote_file_window = None
        self._model_list_window = None
        self._last_dataset_fp = ""
        self._dataset_ready = False
        self._autosave_after_id = None
        self._is_loading_config = False
        self._active_server_operation = None
        self._active_server_operation_label = ""
        self._server_op_prev_states = {}
        self._apply_connection_state("disconnected")
        self.ui.update_status_bar_network("--", "--")
        
        # 绑定窗口尺寸变化事件
        self.root.bind("<Configure>", self._on_window_resize)
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _ensure_startup_window_size(self):
        """启动窗口尺寸兜底（按屏幕自适应，优先加载保存的尺寸）。"""
        ui_cfg = self.config_manager.ui_config
        saved_w = ui_cfg.get('window_width', 1240)
        saved_h = ui_cfg.get('window_height', 900)
        saved_state = ui_cfg.get('window_state', 'normal')
        saved_x = ui_cfg.get('window_x', -1)
        saved_y = ui_cfg.get('window_y', -1)

        design_w, design_h = 1240, 900
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()

        # 预留边距，避免任务栏/缩放下可用区域不足
        safe_w = max(960, screen_w - 80)
        safe_h = max(640, screen_h - 120)

        # 最小尺寸不能超过当前可用安全尺寸，否则系统会强制压缩窗口
        min_w = min(1190, max(960, int(safe_w * 0.85)))
        min_h = min(720, max(640, int(safe_h * 0.82)))
        self.root.minsize(min_w, min_h)

        # 确定启动尺寸
        start_w = min(saved_w, screen_w - 40)
        start_h = min(saved_h, screen_h - 80)
        
        # 如果是初次运行或坐标无效，居中显示
        if saved_x < 0 or saved_y < 0 or saved_x > screen_w or saved_y > screen_h:
            x = (screen_w - start_w) // 2
            y = (screen_h - start_h) // 2
        else:
            x, y = saved_x, saved_y

        self.root.geometry(f"{start_w}x{start_h}+{x}+{y}")
        
        # 初始化状态栏尺寸显示
        self.ui.status_window_size_var.set(f"{start_w} x {start_h}")

        # 应用窗口状态
        if saved_state == "zoomed":
            self.root.after(100, lambda: self.root.state("zoomed"))
        elif safe_w < design_w or safe_h < design_h:
            # 小屏幕且未保存为最大化时，仍尝试优先最大化保证可读性
            self.root.after(100, lambda: self.root.state("zoomed"))

    def _on_window_resize(self, event):
        """处理窗口尺寸变化事件"""
        # 只处理主窗口的尺寸变化（避免子控件触发）
        if event.widget == self.root:
            state = self.root.state()
            self.config_manager.ui_config['window_state'] = state
            
            if state == "normal":
                # 只有在常规状态下才记录具体尺寸和位置
                w = self.root.winfo_width()
                h = self.root.winfo_height()
                x = self.root.winfo_x()
                y = self.root.winfo_y()
                self.config_manager.ui_config['window_width'] = w
                self.config_manager.ui_config['window_height'] = h
                self.config_manager.ui_config['window_x'] = x
                self.config_manager.ui_config['window_y'] = y
                self.ui.status_window_size_var.set(f"{w} x {h}")
            else:
                # 最大化状态下只更新状态栏文字
                w = self.root.winfo_width()
                h = self.root.winfo_height()
                self.ui.status_window_size_var.set(f"{w} x {h} (最大化)")
            self._schedule_auto_save(delay_ms=1200)

    def _center_child_window(self, child_win):
        """将子窗口默认居中到主窗口中心。"""
        if child_win is None:
            return
        self.root.update_idletasks()
        child_win.update_idletasks()
        parent_w = self.root.winfo_width()
        parent_h = self.root.winfo_height()
        parent_x = self.root.winfo_rootx()
        parent_y = self.root.winfo_rooty()
        child_w = child_win.winfo_width() or child_win.winfo_reqwidth()
        child_h = child_win.winfo_height() or child_win.winfo_reqheight()
        x = parent_x + max(0, (parent_w - child_w) // 2)
        y = parent_y + max(0, (parent_h - child_h) // 2)
        child_win.geometry(f"+{x}+{y}")

    def _begin_server_operation(self, op_key, op_label):
        """进入服务器操作互锁区，防止高风险操作并发。"""
        if self._active_server_operation and self._active_server_operation != op_key:
            self.ui.log_message(
                f"当前正在执行[{self._active_server_operation_label}]，请等待完成后再执行[{op_label}]。"
            )
            return False
        if self._active_server_operation == op_key:
            return True
        self._active_server_operation = op_key
        self._active_server_operation_label = op_label
        self._server_op_prev_states = {}
        lock_btns = [
            "btn_test_connection",
            "btn_file_manager",
            "btn_select_dataset",
            "btn_upload_dataset",
            "btn_clear_dataset",
            "btn_check_env",
            "btn_fix_env",
            "btn_download_model",
            "btn_start_training",
        ]
        for btn_name in lock_btns:
            if op_key == "training" and btn_name == "btn_start_training":
                continue
            if op_key == "upload_dataset" and btn_name == "btn_upload_dataset":
                continue
            btn = getattr(self.ui, btn_name, None)
            if btn is None:
                continue
            try:
                self._server_op_prev_states[btn_name] = str(btn.cget("state"))
                btn.config(state="disabled")
            except Exception:
                continue
        return True

    def _end_server_operation(self, op_key):
        """退出服务器操作互锁区并恢复按钮状态。"""
        if self._active_server_operation != op_key:
            return
        prev = dict(self._server_op_prev_states)
        self._active_server_operation = None
        self._active_server_operation_label = ""
        self._server_op_prev_states = {}
        for btn_name, state in prev.items():
            btn = getattr(self.ui, btn_name, None)
            if btn is None:
                continue
            try:
                btn.config(state=state)
            except Exception:
                continue
        self._set_operational_buttons_enabled(self.server_manager.is_connected)
        self._refresh_start_training_button_state()
        self._refresh_upload_button_state()

    def _setup_log_tags(self):
        """初始化日志颜色标签"""
        if not hasattr(self.ui, "log_text"):
            return
        text = self.ui.log_text
        text.tag_configure("log_info", foreground="#1f6feb")
        text.tag_configure("log_success", foreground="#1a7f37")
        text.tag_configure("log_warning", foreground="#9a6700")
        text.tag_configure("log_error", foreground="#cf222e")
        text.tag_configure("log_accent", foreground="#8250df")
        text.tag_configure("ansi_red", foreground="#cf222e")
        text.tag_configure("ansi_green", foreground="#1a7f37")
        text.tag_configure("ansi_yellow", foreground="#9a6700")
        text.tag_configure("ansi_blue", foreground="#1f6feb")
        text.tag_configure("ansi_magenta", foreground="#8250df")
        text.tag_configure("ansi_cyan", foreground="#0a7ea4")
        text.tag_configure("ansi_white", foreground="#57606a")

    def _infer_log_tag(self, text):
        t = str(text).lower()
        if any(k in t for k in ["error", "失败", "异常", "traceback", "❌"]):
            return "log_error"
        if any(k in t for k in ["warning", "warn", "警告"]):
            return "log_warning"
        if any(k in t for k in ["成功", "完成", "done", "✓", "connected"]):
            return "log_success"
        if any(k in t for k in ["epoch", "train", "loss", "val"]):
            return "log_accent"
        if t.startswith("$") or t.startswith(">"):
            return "log_info"
        return None

    def _append_colored_text(self, message):
        ansi_re = re.compile(r"\x1b\[([0-9;]+)m")
        color_map = {
            31: "ansi_red",
            32: "ansi_green",
            33: "ansi_yellow",
            34: "ansi_blue",
            35: "ansi_magenta",
            36: "ansi_cyan",
            37: "ansi_white",
            91: "ansi_red",
            92: "ansi_green",
            93: "ansi_yellow",
            94: "ansi_blue",
            95: "ansi_magenta",
            96: "ansi_cyan",
            97: "ansi_white",
        }
        text_widget = self.ui.log_text
        pos = 0
        current_tag = None

        if not ansi_re.search(message):
            tag = self._infer_log_tag(message)
            if tag:
                text_widget.insert(tk.END, message, tag)
            else:
                text_widget.insert(tk.END, message)
            return

        for m in ansi_re.finditer(message):
            start, end = m.span()
            if start > pos:
                segment = message[pos:start]
                if segment:
                    text_widget.insert(tk.END, segment, current_tag)
            codes = [c for c in m.group(1).split(";") if c.isdigit()]
            for code_s in codes:
                code = int(code_s)
                if code == 0:
                    current_tag = None
                elif code in color_map:
                    current_tag = color_map[code]
            pos = end

        if pos < len(message):
            tail = message[pos:]
            if tail:
                text_widget.insert(tk.END, tail, current_tag)

    def _log_message(self, msg):
        """处理日志消息并显示在UI中（支持彩色）"""
        if not hasattr(self.ui, "log_text"):
            print(msg)
            return

        message = str(msg)

        def append_in_ui():
            self._append_colored_text(message)
            self.ui.log_text.insert(tk.END, "\n")
            self.ui.log_text.see(tk.END)

        if threading.current_thread() is threading.main_thread():
            append_in_ui()
        else:
            self.root.after(0, append_in_ui)

    def _load_config_to_ui(self):
        """将配置加载到UI变量中（模块化映射）"""
        self._is_loading_config = True
        try:
            self.config_binding_manager.load_config_to_ui(self.ui, self.config_manager)
        finally:
            self._is_loading_config = False

    def _update_config_from_ui(self):
        """从UI变量中读取数据更新到配置中（模块化映射）"""
        self.config_binding_manager.update_config_from_ui(self.ui, self.config_manager)

    def _bind_events(self):
        """绑定事件处理"""
        self.ui.btn_test_connection.config(command=self._connect_server)
        self.ui.btn_file_manager.config(command=self._open_file_manager)

        self.ui.btn_select_dataset.config(command=self._select_dataset)
        self.ui.btn_upload_dataset.config(command=self._toggle_upload_dataset)
        self.ui.btn_clear_dataset.config(command=self._clear_dataset)

        self.ui.btn_check_env.config(command=self._check_environment)
        self.ui.btn_fix_env.config(command=self._fix_environment)
        self.ui.btn_start_training.config(command=self._toggle_training)
        self.ui.btn_download_model.config(command=self._download_model)
        self.ui.btn_fullscreen_monitor.config(command=self._open_fullscreen_monitor)
        if hasattr(self.ui, "btn_reserved_feature"):
            self.ui.btn_reserved_feature.config(command=self._show_reserved_feature_message)
        
        # 增加参数变动监听，实现自动推荐
        self.ui.base_model_var.trace_add("write", self._on_config_param_change)
        self.ui.image_size_var.trace_add("write", self._on_config_param_change)
        self.ui.dataset_path_var.trace_add("write", self._on_dataset_path_changed)
        self._bind_auto_save_traces()

    def _bind_auto_save_traces(self):
        """为核心配置项绑定自动持久化（防抖）。"""
        vars_for_autosave = [
            self.ui.hostname_var,
            self.ui.port_var,
            self.ui.username_var,
            self.ui.password_var,
            self.ui.dataset_path_var,
            self.ui.remote_dataset_path_var,
            self.ui.dataset_name_var,
            self.ui.epochs_var,
            self.ui.batch_size_var,
            self.ui.learning_rate_var,
            self.ui.image_size_var,
            self.ui.base_model_var,
            self.ui.model_name_suffix_var,
            self.ui.augment_scale_var,
            self.ui.augment_fliplr_var,
            self.ui.flipud_var,
            self.ui.perspective_var,
            self.ui.augment_hsv_h_var,
            self.ui.augment_hsv_s_var,
            self.ui.augment_hsv_v_var,
            self.ui.augment_scale_active_var,
            self.ui.augment_fliplr_active_var,
            self.ui.augment_flipud_active_var,
            self.ui.augment_perspective_active_var,
            self.ui.augment_hsv_h_active_var,
            self.ui.augment_hsv_s_active_var,
            self.ui.augment_hsv_v_active_var,
            self.ui.upload_max_workers_var,
        ]
        for v in vars_for_autosave:
            v.trace_add("write", self._on_config_var_changed)

    def _on_config_var_changed(self, *_):
        if self._is_loading_config:
            return
        self._schedule_auto_save()

    def _schedule_auto_save(self, delay_ms=800):
        if self._autosave_after_id:
            self.root.after_cancel(self._autosave_after_id)
        self._autosave_after_id = self.root.after(delay_ms, self._flush_auto_save)

    def _flush_auto_save(self):
        self._autosave_after_id = None
        try:
            self._update_config_from_ui()
            self.config_manager.save_config()
        except Exception:
            # 自动持久化场景下静默失败，避免打断用户操作
            pass

    def _on_dataset_path_changed(self, *_):
        if self._is_loading_config:
            return
        self._set_dataset_ready(False)

    def _on_config_param_change(self, *_):
        """当模型或图片尺寸变化时，自动推荐参数"""
        try:
            model = self.ui.base_model_var.get()
            imgsz = self.ui.image_size_var.get()
            if model and imgsz:
                batch, lr = self.training_manager.get_recommended_params(model, imgsz)
                self.ui.batch_size_var.set(str(batch))
                self.ui.learning_rate_var.set(str(lr))
        except Exception:
            pass

    def _trigger_loss_chart_refresh(self):
        """触发一次 Loss 刷新（训练中即时刷新用）"""
        if not self._training_running:
            return
        if callable(self._loss_chart_refresh_fn):
            self._loss_chart_refresh_fn()

    def _show_reserved_feature_message(self):
        """预留功能说明"""
        messagebox.showinfo("提示", "该区域功能开发中，后续将按计划逐步开放。")

    def _apply_connection_state(self, state):
        """统一更新连接状态（面板文字 + 底部图标）"""
        if state == "connecting":
            self.ui.connection_status_var.set("连接中")
            self.ui.connection_status_label.config(foreground="orange")
            self._set_operational_buttons_enabled(False)
        elif state == "connected":
            self.ui.connection_status_var.set("连接成功")
            self.ui.connection_status_label.config(foreground="green")
            self._start_ping_monitor()
            self._start_system_monitor()
            self._set_operational_buttons_enabled(True)
            self._refresh_start_training_button_state()
        elif state == "failed":
            self.ui.connection_status_var.set("连接失败")
            self.ui.connection_status_label.config(foreground="red")
            self._stop_ping_monitor()
            self._stop_system_monitor()
            self._set_operational_buttons_enabled(False)
        else:
            self.ui.connection_status_var.set("未连接")
            self.ui.connection_status_label.config(foreground="gray")
            self._stop_ping_monitor()
            self._stop_system_monitor()
            self._set_operational_buttons_enabled(False)
        
        self.ui.set_status_bar_connection_state(state)
        self._refresh_start_training_button_state()

    def _set_operational_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for btn_name in [
            "btn_file_manager",
            "btn_select_dataset",
            "btn_upload_dataset",
            "btn_clear_dataset",
            "btn_check_env",
            "btn_download_model",
            "btn_fullscreen_monitor",
        ]:
            btn = getattr(self.ui, btn_name, None)
            if btn is not None:
                btn.config(state=state)
        if hasattr(self.ui, "btn_fix_env") and not enabled:
            self.ui.btn_fix_env.config(state="disabled")
        if hasattr(self.ui, "btn_reserved_feature"):
            self.ui.btn_reserved_feature.config(state=state)
        if hasattr(self.ui, "btn_test_connection"):
            self.ui.btn_test_connection.config(state="normal")

    def _set_dataset_ready(self, ready):
        self._dataset_ready = bool(ready)
        self._refresh_start_training_button_state()

    def _refresh_start_training_button_state(self):
        if not hasattr(self.ui, "btn_start_training"):
            return
        if self._training_running:
            self._set_training_button_running(True)
            if not self.server_manager.is_connected:
                self.ui.btn_start_training.config(state="disabled")
            else:
                self.ui.btn_start_training.config(state="normal")
            return
        self._set_training_button_running(False)
        if not self.server_manager.is_connected:
            self.ui.btn_start_training.config(state="disabled")
            return
        self.ui.btn_start_training.config(state="normal" if self._dataset_ready else "disabled")

    def _set_training_button_running(self, running):
        """根据训练状态切换按钮文案与样式。"""
        if not hasattr(self.ui, "btn_start_training"):
            return
        if running:
            self.ui.btn_start_training.config(text="停止训练", bootstyle="danger")
        else:
            self.ui.btn_start_training.config(text="开始训练", bootstyle="success")

    def _set_upload_button_running(self, running):
        """根据上传状态切换按钮文案与样式。"""
        if not hasattr(self.ui, "btn_upload_dataset"):
            return
        if running:
            self.ui.btn_upload_dataset.config(text="停止上传", bootstyle="danger")
        else:
            self.ui.btn_upload_dataset.config(text="上传训练集", bootstyle="success")

    def _refresh_upload_button_state(self):
        """刷新上传按钮状态与文案。"""
        if not hasattr(self.ui, "btn_upload_dataset"):
            return
        self._set_upload_button_running(self._upload_running)
        if self._upload_running:
            self.ui.btn_upload_dataset.config(state="normal")

    def _toggle_upload_dataset(self):
        """上传按钮切换入口：未上传则开始，上传中则停止。"""
        if self._upload_running:
            self._stop_upload_dataset()
        else:
            self._upload_dataset()

    def _stop_upload_dataset(self):
        """请求停止当前上传任务。"""
        if not self._upload_running:
            return
        self._upload_stop_requested = True
        self.ui.upload_status_var.set("正在停止上传...")
        self.ui.log_message("已请求停止上传，等待当前传输中的文件结束...")

    def _toggle_training(self):
        """训练按钮切换入口：未运行则开始，运行中则停止。"""
        if self._training_running:
            self._stop_training()
        else:
            self._start_training()

    def _start_system_monitor(self):
        """开启系统状态监控"""
        if self._system_monitor_after_id:
            self.root.after_cancel(self._system_monitor_after_id)
        
        def update_loop():
            if not self.server_manager.is_connected:
                return

            # 避免上一次采集未结束时重复发起网络命令，减少卡顿与堆积
            if not self._system_monitor_busy:
                self._system_monitor_busy = True

                def collect_status():
                    try:
                        status = self.monitor_manager.get_system_status()
                        if "error" not in status:
                            self.root.after(0, lambda s=status: self._update_ui_system_status(s))
                    finally:
                        self._system_monitor_busy = False

                threading.Thread(target=collect_status, daemon=True).start()

            # 每 3 秒更新一次
            self._system_monitor_after_id = self.root.after(3000, update_loop)
            
        update_loop()

    def _stop_system_monitor(self):
        """停止系统状态监控"""
        if self._system_monitor_after_id:
            self.root.after_cancel(self._system_monitor_after_id)
            self._system_monitor_after_id = None
        
        # 重置 UI
        self.ui.update_cpu_chart(0)
        self.ui.update_gpu_chart(0)

    def _update_ui_system_status(self, status):
        """更新 UI 上的系统状态"""
        # CPU
        cpu = status.get('cpu_usage', 0)
        self.ui.update_cpu_chart(cpu)
        
        # GPU (取第一个 GPU)
        gpu_usages = status.get('gpu_usage', [])
        if gpu_usages:
            gpu = gpu_usages[0]
            self.ui.update_gpu_chart(gpu)
        else:
            self.ui.update_gpu_chart(0)

    def _start_ping_monitor(self):
        """启动底部状态栏的 Ping 监控"""
        self._stop_ping_monitor(reset_metrics=False)
        self._ping_monitor_enabled = True
        self._schedule_ping_check()
    
    def _stop_ping_monitor(self, reset_metrics=True):
        """停止 Ping 监控"""
        self._ping_monitor_enabled = False
        if self._ping_after_id:
            self.root.after_cancel(self._ping_after_id)
            self._ping_after_id = None
        if reset_metrics:
            self.ui.update_status_bar_network("--", "--")
    
    def _schedule_ping_check(self):
        if not self._ping_monitor_enabled:
            return
        threading.Thread(target=self._run_ping_check_once, daemon=True).start()

    def _run_ping_check_once(self):
        host = self.ui.hostname_var.get().strip()
        ping_text, loss_text = self.network_monitor_manager.measure_ping_loss(host)

        def update_ui():
            self.ui.update_status_bar_network(ping_text, loss_text, time.strftime("%H:%M:%S"))
            if loss_text == "100%":
                self.ui.set_status_bar_connection_state("failed")
            elif loss_text != "--":
                self.ui.set_status_bar_connection_state("connected")
            if self._ping_monitor_enabled:
                self._ping_after_id = self.root.after(2000, self._schedule_ping_check)

        self.root.after(0, update_ui)

    def _connect_server(self):
        """异步连接服务器"""
        try:
            self._update_config_from_ui()
        except ValueError:
            messagebox.showerror("参数错误", "端口必须是整数")
            return
        if not self._begin_server_operation("connect_server", "连接服务器"):
            return

        self.ui.log_message("正在连接服务器...")
        self._apply_connection_state("connecting")
        self._stop_ping_monitor(reset_metrics=True)
        self.ui.btn_test_connection.config(state="disabled")

        def connect_thread():
            success, msg = self.server_manager.connect()
            self.root.after(0, lambda: self._on_connect_result(success, msg))
            if success:
                self._load_system_info_async()

        threading.Thread(target=connect_thread, daemon=True).start()

    def _load_system_info_async(self):
        """后台异步加载服务器系统信息"""
        self.root.after(0, lambda: self._set_system_info_loading())

        def info_thread():
            success, message, sys_info = self.server_manager.get_system_info()
            self.root.after(0, lambda: self._on_system_info_result(success, message, sys_info))

        threading.Thread(target=info_thread, daemon=True).start()

    def _set_system_info_loading(self):
        """显示系统信息加载中状态"""
        loading_text = "获取中..."
        self.ui.hostname_info_var.set(loading_text)
        self.ui.os_info_var.set(loading_text)
        self.ui.cpu_info_var.set(loading_text)
        self.ui.gpu_info_var.set(loading_text)
        self.ui.memory_info_var.set(loading_text)
        self.ui.disk_info_var.set(loading_text)

    def _on_system_info_result(self, success, message, sys_info):
        """系统信息异步加载结果处理"""
        if success:
            self.ui.hostname_info_var.set(sys_info.get('hostname', '未知'))
            self.ui.os_info_var.set(sys_info.get('os', '未知'))
            self.ui.cpu_info_var.set(sys_info.get('cpu', '未知'))
            self.ui.gpu_info_var.set(sys_info.get('gpu', '未知'))
            self.ui.memory_info_var.set(sys_info.get('memory', '未知'))
            self.ui.disk_info_var.set(sys_info.get('disk', '未知'))
        else:
            self.ui.log_message(f"系统信息获取失败: {message}")
            self.ui.hostname_info_var.set("获取失败")
            self.ui.os_info_var.set("获取失败")
            self.ui.cpu_info_var.set("获取失败")
            self.ui.gpu_info_var.set("获取失败")
            self.ui.memory_info_var.set("获取失败")
            self.ui.disk_info_var.set("获取失败")

    def _on_connect_result(self, success, msg):
        """服务器连接结果处理"""
        self.ui.btn_test_connection.config(state="normal")
        self._end_server_operation("connect_server")
        if success:
            self.ui.log_message("服务器连接成功！")
            self._apply_connection_state("connected")
            self._start_ping_monitor()
            self.ui.log_message("正在后台获取系统信息...")
            self._auto_apply_saved_dataset_after_connect()
        else:
            self.ui.log_message(f"服务器连接失败: {msg}")
            self._apply_connection_state("failed")
            self._stop_ping_monitor(reset_metrics=True)

            self.ui.hostname_info_var.set("")
            self.ui.os_info_var.set("")
            self.ui.cpu_info_var.set("")
            self.ui.gpu_info_var.set("")
            self.ui.memory_info_var.set("")
            self.ui.disk_info_var.set("")
            self._set_dataset_ready(False)

    def _auto_apply_saved_dataset_after_connect(self):
        """连接成功后，若配置已有训练集路径则自动执行选择后的检查逻辑。"""
        dataset_path = self.ui.dataset_path_var.get().strip()
        if not dataset_path:
            self.ui.log_message("未检测到已保存训练集路径，跳过自动检查")
            return
        if not os.path.isdir(dataset_path):
            self.ui.log_message(f"已保存训练集路径无效，跳过自动检查: {dataset_path}")
            self._set_dataset_ready(False)
            return
        self.ui.log_message(f"检测到已保存训练集，自动检查: {dataset_path}")
        self._apply_selected_dataset(dataset_path, from_auto=True)

    def _check_environment(self):
        """检查环境（深度复刻原版显示格式）"""
        if not self._begin_server_operation("check_environment", "检查环境"):
            return

        def run_check():
            self.ui.log_message("=" * 60)
            self.ui.log_message("开始检查云端环境...")
            self.ui.log_message("=" * 60)
            
            report = self.environment_manager.check_environment(log_callback=lambda m: self.ui.log_message(m))
            
            def finish():
                self.ui.log_message("-" * 60)
                if report["errors"]:
                    self.ui.log_message(f"⚠ 发现 {len(report['errors'])} 个问题需要修复")
                    self.ui.btn_fix_env.config(state="normal")
                    self._env_check_passed = False
                else:
                    self.ui.log_message("✓ 环境检查通过，所有组件正常")
                    self.ui.btn_fix_env.config(state="disabled")
                    self._env_check_passed = True
                self.ui.log_message("=" * 60)
                self._end_server_operation("check_environment")
            
            self.root.after(0, finish)
            
        threading.Thread(target=run_check, daemon=True).start()

    def _fix_environment(self):
        """修复环境（深度复刻原版显示格式）"""
        if not self._begin_server_operation("fix_environment", "修复环境"):
            return
        self.ui.btn_fix_env.config(state="disabled")
        
        def run_fix():
            self.ui.log_message("=" * 60)
            self.ui.log_message("开始修复云端环境...")
            self.ui.log_message("=" * 60)
            
            success, _ = self.environment_manager.fix_environment(log_callback=lambda m: self.ui.log_message(m))

            def finish():
                if success:
                    self.ui.log_message("=" * 60)
                    self.ui.log_message("✓ 环境修复完成，复检通过")
                    self.ui.log_message("=" * 60)
                    self.ui.btn_fix_env.config(state="disabled")
                    self._env_check_passed = True
                else:
                    self.ui.log_message("=" * 60)
                    self.ui.log_message("❌ 环境修复失败，请检查上方日志")
                    self.ui.log_message("=" * 60)
                    self.ui.btn_fix_env.config(state="normal")
                    self._env_check_passed = False
                self._end_server_operation("fix_environment")
            
            self.root.after(0, finish)

        threading.Thread(target=run_fix, daemon=True).start()

    def _select_dataset(self):
        """选择本地训练集目录"""
        folder = filedialog.askdirectory(title="选择训练集目录")
        if folder:
            self._apply_selected_dataset(folder, from_auto=False)

    def _apply_selected_dataset(self, folder, from_auto=False):
        """复用“选择训练集”后的统一流程：设置路径 + 检查数据集。"""
        self.ui.dataset_path_var.set(folder)
        prefix = "已自动加载训练集" if from_auto else "已选择训练集"
        self.ui.log_message(f"{prefix}: {folder}")
        self._check_dataset()

    def _sync_dataset_count_labels(self, local_count=None, remote_count=None, class_count=None):
        """同步“数据集信息”区计数显示。"""
        if local_count is None:
            self.ui.local_image_count_var.set("本地图片数：-")
        else:
            self.ui.local_image_count_var.set(f"本地图片数：{int(local_count)} 张")

        if remote_count is None:
            self.ui.remote_image_count_var.set("云端图片数：-")
        else:
            self.ui.remote_image_count_var.set(f"云端图片数：{int(remote_count)} 张")

        if class_count is not None:
            self.ui.num_classes_var.set(str(int(class_count)))

    def _check_dataset(self, _from_locked=False):
        """检查数据集（增加指纹识别）"""
        if not _from_locked and not self._begin_server_operation("check_dataset", "检查数据集"):
            return
        try:
            dataset_path = self.ui.dataset_path_var.get()
            if not dataset_path:
                self.ui.log_message("请设置数据集路径")
                self._sync_dataset_count_labels(local_count=None, remote_count=None, class_count=None)
                self._set_dataset_ready(False)
                return

            # 检查指纹
            current_fp = self.dataset_manager.get_dataset_fingerprint(dataset_path)
            use_cache = self._last_dataset_fp and current_fp == self._last_dataset_fp
            if use_cache:
                self.ui.log_message("本地数据集未发生变化，跳过本地完整校验（指纹匹配）")
                success, message = True, "本地检查通过(缓存)"
                info = self.dataset_manager.get_dataset_info(dataset_path)
                self.ui.dataset_check_status_var.set("检查状态: 通过 (缓存)")
            else:
                self.ui.log_message("正在检查数据集...")
                success, message = self.dataset_manager.check_dataset(dataset_path)
                info = self.dataset_manager.get_dataset_info(dataset_path) if success else {}

            if success:
                self._last_dataset_fp = current_fp
                self.ui.log_message(f"数据集检查通过: {message}")
                local_image_count = int(info.get("image_count", 0))
                class_count = int(info.get("class_count", 0))
                local_summary = (
                    f"图像: {local_image_count}, 标签: {info.get('label_count', 0)}, 类别: {class_count}"
                )
                remote_path = self.ui.remote_dataset_path_var.get().strip() or "/root/yolo_dataset"
                remote_diff = self.dataset_manager.compare_remote_image_diff(
                    dataset_path, remote_path, self.server_manager
                )
                if remote_diff.get("ok"):
                    need = int(remote_diff.get("need_upload", 0))
                    skip = int(remote_diff.get("skip_count", 0))
                    remote_total = int(remote_diff.get("remote_total", 0))
                    self._sync_dataset_count_labels(
                        local_count=local_image_count,
                        remote_count=remote_total,
                        class_count=class_count,
                    )
                    self.ui.log_message(f"云端图片差异检查完成: 需上传 {need}，可跳过 {skip}")
                    summary = f"{local_summary} | 云端差异: 需上传 {need}, 可跳过 {skip}"
                else:
                    self._sync_dataset_count_labels(
                        local_count=local_image_count,
                        remote_count=None,
                        class_count=class_count,
                    )
                    msg = str(remote_diff.get("msg", "")).strip() or "云端差异检查失败"
                    self.ui.log_message(f"云端图片差异检查跳过/失败: {msg}")
                    summary = f"{local_summary} | 云端差异: {msg}"

                self.ui.dataset_summary_var.set(f"检查总结: {summary}")
                if not use_cache:
                    self.ui.dataset_check_status_var.set("检查状态: 通过")

                classes = info.get("classes", [])
                if not classes:
                    # 尝试从标签解析
                    ids = self.dataset_manager.parse_classes_from_labels(dataset_path)
                    classes = [(str(cid), f"class_{cid}") for cid in ids]
                
                self.ui.update_classes_table(classes)
                self._set_dataset_ready(True)
                Notifier.play_sound("success")
            else:
                self.ui.log_message(f"数据集检查失败: {message}")
                self.ui.dataset_check_status_var.set("检查状态: 失败")
                self.ui.dataset_summary_var.set(f"检查总结: {message}")
                self.ui.update_classes_table([])
                self._sync_dataset_count_labels(local_count=None, remote_count=None, class_count=None)
                self._set_dataset_ready(False)
                Notifier.play_sound("error")
        finally:
            if not _from_locked:
                self._end_server_operation("check_dataset")

    def _upload_dataset(self):
        """上传数据集（优化并发上传与通知）"""
        if self._upload_running:
            self.ui.log_message("上传任务正在进行中")
            return
        self._update_config_from_ui()
        dataset_path = self.ui.dataset_path_var.get()
        if not dataset_path:
            self.ui.log_message("请设置数据集路径")
            return
        if not self._begin_server_operation("upload_dataset", "上传数据集"):
            return

        remote_path = self.ui.remote_dataset_path_var.get().strip() or "/root/yolo_dataset"
        self._upload_running = True
        self._upload_stop_requested = False
        self._refresh_upload_button_state()
        self.ui.upload_status_var.set("正在上传...")
        self.ui.upload_progress_var.set(0)
        self.ui.log_message(f"开始上传训练集到: {remote_path}")

        def progress(current, total, rel_path):
            percent = (current / total * 100.0) if total > 0 else 100.0

            def update():
                self.ui.upload_progress_var.set(percent)
                self.ui.upload_status_var.set(f"上传中: {current}/{total}")
                self.ui.dataset_summary_var.set(f"当前文件: {rel_path}")
                # 降低日志频率，每 10% 或 最后一个文件才打印
                if current % max(1, total // 10) == 0 or current == total:
                    self.ui.log_message(f"上传进度: {current}/{total} ({int(percent)}%)")

            self.root.after(0, update)

        def do_upload():
            success, msg = self.dataset_manager.upload_dataset(
                dataset_path,
                remote_path,
                self.server_manager,
                progress_callback=progress,
                log_callback=lambda m: self.ui.log_message(m),
                stop_callback=lambda: self._upload_stop_requested,
            )

            def finish():
                if success:
                    self.ui.log_message(msg)
                    self.ui.upload_status_var.set("上传完成")
                    self.ui.upload_progress_var.set(100)
                    import os
                    Notifier.notify("上传完成", f"数据集已成功上云: {os.path.basename(dataset_path)}")
                    Notifier.play_sound("success")
                    # 上传完成后，立即触发一次数据集检查，以更新云端图片计数和差异状态
                    self._check_dataset(_from_locked=True)
                else:
                    if self._upload_stop_requested:
                        self.ui.log_message(msg)
                        self.ui.upload_status_var.set("上传已停止")
                    else:
                        self.ui.log_message(f"上传失败: {msg}")
                        self.ui.upload_status_var.set("上传失败")
                        Notifier.notify("上传失败", msg)
                        Notifier.play_sound("error")
                self._upload_running = False
                self._upload_stop_requested = False
                self._refresh_upload_button_state()
                self._end_server_operation("upload_dataset")

            self.root.after(0, finish)

        threading.Thread(target=do_upload, daemon=True).start()

    def _clear_dataset(self):
        """清空远程训练集"""
        if not self._begin_server_operation("clear_dataset", "清空远程训练集"):
            return
        remote_path = self.ui.remote_dataset_path_var.get().strip() or "/root/yolo_dataset"
        if not messagebox.askyesno("确认", f"确认清空远程目录？\n{remote_path}"):
            self._end_server_operation("clear_dataset")
            return
        self.ui.log_message(f"正在清空远程训练集: {remote_path}")

        def do_clear():
            success, msg = self.dataset_manager.clear_remote_dataset(remote_path, self.server_manager)

            def finish():
                if success:
                    self.ui.log_message("远程训练集已清空")
                    self.ui.dataset_summary_var.set("检查总结: 远程训练集已清空")
                    self._sync_dataset_count_labels(remote_count=0)
                    # 清空后立即再次检查训练集（含云端差异），确保状态与计数实时刷新
                    self._check_dataset(_from_locked=True)
                else:
                    self.ui.log_message(f"清空失败: {msg}")
                self._end_server_operation("clear_dataset")

            self.root.after(0, finish)

        threading.Thread(target=do_clear, daemon=True).start()

    def _start_training(self):
        """开始训练（流式日志回传 + 实时图表）"""
        if not self._begin_server_operation("training", "开始训练"):
            return
        if self._training_running:
            self.ui.log_message("训练已在进行中")
            self._end_server_operation("training")
            return
        dataset_path = self.ui.dataset_path_var.get()
        if not dataset_path:
            self.ui.log_message("请设置数据集路径")
            self._end_server_operation("training")
            return

        self._update_config_from_ui()
        self.config_manager.save_config()
        self.ui.log_message("正在准备训练环境...")
        self.ui.training_status_var.set("准备中")
        self.ui.status_duration_var.set("时长: 00:00:00")
        self.ui.status_eta_var.set("预计完成: --")
        # 新一轮训练开始前立即清空曲线，避免显示上次训练残留
        self.ui.update_loss_chart([], [], [], [])
        self._training_stop_requested = False
        self._training_running = True
        self._refresh_start_training_button_state()

        # 如果监控大屏已打开，通知其自动切换到最新训练
        if self._monitor_window and self._monitor_window.exists():
            self._monitor_window.auto_follow_latest()

        def run_training():
            start_at = time.time()
            self.training_progress_manager.reset(
                total_epochs=self.config_manager.training_config.get("epochs"),
                start_time=start_at,
            )
            model_name = self.training_manager.build_model_name()
            remote_dataset_path = self.ui.remote_dataset_path_var.get().strip() or "/root/yolo_dataset"
            self.training_monitor_manager.start_session(
                remote_dataset_path=remote_dataset_path,
                model_name=model_name,
                start_ts=start_at,
            )
            raw_log_path = self.training_log_manager.start_session(model_name=model_name)
            self.root.after(0, lambda p=raw_log_path: self.ui.log_message(f"训练日志归档: {p}"))
            
            # 开启图表刷新循环
            def refresh_chart_loop():
                if not self._training_running:
                    return
                if not self.server_manager.is_connected:
                    self.root.after(5000, refresh_chart_loop)
                    return
                if self._loss_chart_refresh_busy:
                    self.root.after(5000, refresh_chart_loop)
                    return

                self._loss_chart_refresh_busy = True

                def refresh_worker():
                    try:
                        data = self.training_monitor_manager.get_loss_series()
                        if not data:
                            return

                        epochs = data.get("epochs", [])
                        box_loss = data.get("box_loss", [])
                        cls_loss = data.get("cls_loss", [])
                        dfl_loss = data.get("dfl_loss", [])
                        if epochs:
                            self.root.after(
                                0,
                                lambda e=epochs, b=box_loss, c=cls_loss, d=dfl_loss:
                                self.ui.update_loss_chart(e, b, c, d)
                            )
                    finally:
                        self._loss_chart_refresh_busy = False
                        if self._training_running:
                            self.root.after(5000, refresh_chart_loop)

                threading.Thread(target=refresh_worker, daemon=True).start()

            self._loss_chart_refresh_fn = refresh_chart_loop
            # 延迟 10 秒开始刷新（等待文件生成）
            self.root.after(10000, refresh_chart_loop)

            # 定义日志回调函数
            def log_callback(msg):
                reduced_lines = self.training_log_manager.process_line(msg)
                for line in reduced_lines:
                    self.root.after(0, lambda m=line: self.ui.log_message(m))
                progress = self.training_progress_manager.update_from_log_line(msg)
                self.root.after(0, lambda p=progress: self._apply_training_progress_ui(p))
                msg_l = str(msg).lower()
                if "epoch" in msg_l or "results.csv" in msg_l:
                    self.root.after(500, self._trigger_loss_chart_refresh)

            self.ui.training_status_var.set("训练中")
            success, message = self.training_manager.start_training(log_callback=log_callback)

            def finish():
                for line in self.training_log_manager.flush():
                    self.ui.log_message(line)
                duration = int(time.time() - start_at)
                h = duration // 3600
                m = (duration % 3600) // 60
                s = duration % 60
                self.ui.status_duration_var.set(f"时长: {h:02d}:{m:02d}:{s:02d}")
                if success:
                    self.ui.training_status_var.set("训练完成")
                    self.ui.log_message(">>> 训练任务全部执行完毕")
                    Notifier.notify("训练完成", f"模型 {self.training_manager.build_model_name()} 训练结束！")
                    Notifier.play_sound("success")
                else:
                    if self._training_stop_requested:
                        self.ui.training_status_var.set("已停止")
                        self.ui.log_message(">>> 训练已手动停止")
                    else:
                        self.ui.training_status_var.set("训练失败")
                        self.ui.log_message(f"!!! 训练过程中断: {message}")
                        Notifier.notify("训练异常", message)
                        Notifier.play_sound("error")
                self.ui.status_eta_var.set("预计完成: --")
                raw_path = self.training_log_manager.get_raw_log_path()
                if raw_path:
                    self.ui.log_message(f"原始日志文件: {raw_path}")
                self._training_running = False
                self._training_stop_requested = False
                self._loss_chart_refresh_fn = None
                self.training_monitor_manager.end_session()
                self.training_log_manager.close_session()
                self._refresh_start_training_button_state()
                self._end_server_operation("training")

            self.root.after(0, finish)

        threading.Thread(target=run_training, daemon=True).start()

    def _stop_training(self):
        """停止训练任务。"""
        if not self._training_running:
            self.ui.log_message("当前没有进行中的训练任务")
            self._refresh_start_training_button_state()
            return
        if not self.server_manager.is_connected:
            messagebox.showerror("错误", "服务器未连接，无法下发停止指令")
            return
        if not messagebox.askyesno("确认", "确定要停止训练吗？"):
            return

        self._training_stop_requested = True
        self.ui.training_status_var.set("停止中")
        self.ui.log_message("正在下发停止训练指令...")
        self.ui.btn_start_training.config(state="disabled")

        def do_stop():
            success, msg = self.training_manager.stop_training()

            def finish():
                if success:
                    self.ui.log_message(f"✓ {msg}，等待训练线程退出...")
                else:
                    self._training_stop_requested = False
                    self.ui.log_message(f"❌ 停止训练失败: {msg}")
                self._refresh_start_training_button_state()

            self.root.after(0, finish)

        threading.Thread(target=do_stop, daemon=True).start()

    def _apply_training_progress_ui(self, progress):
        """将训练进度数据回填到 UI。"""
        if not isinstance(progress, dict):
            return
        status = progress.get("status_text")
        duration_text = progress.get("duration_text")
        eta_text = progress.get("eta_text")

        if status:
            self.ui.training_status_var.set(status)
        if duration_text:
            self.ui.status_duration_var.set(duration_text)
        if eta_text:
            self.ui.status_eta_var.set(eta_text)

    def _download_model(self):
        """打开服务器模型列表窗口（下载/删除/转换统一入口）。"""
        if self._active_server_operation:
            self.ui.log_message(f"当前正在执行[{self._active_server_operation_label}]，请稍后再打开模型列表。")
            return
        if not self.server_manager.is_connected:
            messagebox.showerror("错误", "请先连接服务器")
            return

        if hasattr(self, "_model_list_window") and self._model_list_window and self._model_list_window.winfo_exists():
            self._model_list_window.lift()
            self._model_list_window.focus_force()
            if hasattr(self, "_model_list_refresh_fn") and callable(self._model_list_refresh_fn):
                self._model_list_refresh_fn()
            return

        win = tk.Toplevel(self.root)
        win.title("服务器模型列表")
        win.geometry("1380x760")
        win.transient(self.root)
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        win.grab_set()
        win.focus_force()
        self._center_child_window(win)
        win.after(0, lambda: self._center_child_window(win))
        self._model_list_window = win

        def close_model_window():
            try:
                win.grab_release()
            except Exception:
                pass
            if win.winfo_exists():
                win.destroy()
            self._model_list_window = None

        win.protocol("WM_DELETE_WINDOW", close_model_window)

        ttk.Label(win, text="服务器模型列表", font=("Arial", 14, "bold")).pack(pady=(10, 6))

        list_frame = ttk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        columns = ("name", "ext", "run", "model", "imgsz", "epochs", "batch", "lr", "size", "date", "path")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        headings = {
            "name": "文件名",
            "ext": "扩展名",
            "run": "运行目录",
            "model": "原始模型",
            "imgsz": "图片尺寸",
            "epochs": "轮次",
            "batch": "Batch",
            "lr": "学习率",
            "size": "大小",
            "date": "创建时间",
            "path": "完整路径",
        }
        for col in columns:
            tree.heading(col, text=headings[col])
            tree.column(col, width=120, minwidth=80, stretch=False)

        tree.tag_configure("ext_pt", background="#dbeafe")
        tree.tag_configure("ext_onnx", background="#fef3c7")
        tree.tag_configure("ext_tflite", background="#fee2e2")
        tree.tag_configure("ext_zip", background="#dcfce7")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        action_frame = ttk.Frame(win)
        action_frame.pack(fill="x", padx=10, pady=(0, 6))

        status_var = tk.StringVar(value="状态: 准备就绪")
        detail_var = tk.StringVar(value="详情: -")
        speed_var = tk.StringVar(value="速度: -")
        progress_var = tk.DoubleVar(value=0)

        status_line = ttk.Frame(win)
        status_line.pack(fill="x", padx=10, pady=(0, 2))
        ttk.Label(status_line, textvariable=status_var).pack(side="left")
        ttk.Label(status_line, textvariable=speed_var).pack(side="right")

        progress_bar = ttk.Progressbar(win, variable=progress_var, maximum=100, mode="determinate")
        progress_bar.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Label(win, textvariable=detail_var).pack(fill="x", padx=10, pady=(0, 6))

        log_text = tk.Text(win, height=8, wrap="word")
        log_text.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        state = {"busy": False}
        model_by_item = {}

        def append_log(text):
            log_text.insert("end", f"{text}\n")
            log_text.see("end")

        def set_busy(busy, status_text):
            state["busy"] = bool(busy)
            status_var.set(f"状态: {status_text}")
            refresh_btn.config(state="disabled" if busy else "normal")
            close_btn.config(state="disabled" if busy else "normal")
            update_action_buttons()

        def set_progress_animating(animating):
            if animating:
                progress_bar.configure(mode="indeterminate")
                progress_bar.start(12)
            else:
                progress_bar.stop()
                progress_bar.configure(mode="determinate")

        def selected_models():
            models = []
            for item in tree.selection():
                m = model_by_item.get(item)
                if m:
                    models.append(m)
            return models

        def update_action_buttons(*_):
            models = selected_models()
            has_selected = len(models) > 0
            can_convert = has_selected and all(str(m.get("ext", "")).lower() == ".pt" for m in models)
            normal_or_disabled = "disabled" if state["busy"] else "normal"
            download_btn.config(state=normal_or_disabled if has_selected else "disabled")
            delete_btn.config(state=normal_or_disabled if has_selected else "disabled")
            convert_btn.config(state=normal_or_disabled if can_convert else "disabled")

        tree.bind("<<TreeviewSelect>>", update_action_buttons)

        def auto_fit_columns():
            width_map = {c: max(90, len(headings[c]) * 16 + 24) for c in columns}
            for item in tree.get_children(""):
                vals = tree.item(item, "values")
                for idx, col in enumerate(columns):
                    val = str(vals[idx]) if idx < len(vals) else ""
                    width_map[col] = min(760, max(width_map[col], len(val) * 9 + 30))
            for col in columns:
                tree.column(col, width=width_map[col], minwidth=80, stretch=False)

        def render_models(models):
            model_by_item.clear()
            for item in tree.get_children(""):
                tree.delete(item)
            for m in models:
                ext = str(m.get("ext", "")).lower()
                tag = ""
                if ext == ".pt":
                    tag = "ext_pt"
                elif ext == ".onnx":
                    tag = "ext_onnx"
                elif ext == ".tflite":
                    tag = "ext_tflite"
                elif ext == ".zip":
                    tag = "ext_zip"
                iid = tree.insert(
                    "",
                    "end",
                    values=(
                        m.get("name", ""),
                        ext or "-",
                        m.get("run_dir", ""),
                        m.get("base_model", ""),
                        m.get("image_size", ""),
                        m.get("epochs", ""),
                        m.get("batch", ""),
                        m.get("lr0", ""),
                        m.get("size", ""),
                        m.get("date", ""),
                        m.get("path", ""),
                    ),
                    tags=(tag,) if tag else (),
                )
                model_by_item[iid] = m
            auto_fit_columns()
            detail_var.set(f"详情: 共 {len(models)} 个模型文件")
            update_action_buttons()

        def refresh_models():
            if state["busy"]:
                return
            set_busy(True, "正在快速查询模型...")
            speed_var.set("速度: -")
            progress_var.set(0)
            detail_var.set("详情: 扫描训练产物目录 /root/runs 与数据集/runs")

            def worker():
                try:
                    models = self.model_manager.query_all_models()
                except Exception as e:
                    models = None
                    err = str(e)
                else:
                    err = ""

                def done():
                    if models is None:
                        append_log(f"❌ 查询失败: {err}")
                        detail_var.set("详情: 查询失败")
                    else:
                        render_models(models)
                        append_log(f"✓ 查询完成，共 {len(models)} 个文件")
                    set_busy(False, "就绪")

                self.root.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        def start_download():
            if state["busy"]:
                return
            models = selected_models()
            if not models:
                messagebox.showwarning("提示", "请先选择要下载的模型")
                return
            local_dir = filedialog.askdirectory(title="选择保存目录")
            if not local_dir:
                return

            download_targets = [{"name": m.get("name", "unknown"), "path": m.get("path", "")} for m in models]
            set_busy(True, "下载中")
            append_log(f"开始下载，共 {len(download_targets)} 个文件 -> {local_dir}")

            def on_progress(event):
                event_type = event.get("type")
                if event_type == "item" and event.get("stage") == "downloading":
                    progress_var.set(float(event.get("progress", 0.0)))
                    speed_var.set(f"速度: {event.get('speed_text', '-')}")
                    idx = int(event.get("index", 0))
                    total = int(event.get("total", 0))
                    name = event.get("name", "-")
                    transferred = int(event.get("transferred", 0))
                    total_size = int(event.get("total_size", 0))
                    detail_var.set(
                        f"详情: 正在下载 {idx}/{total} {name} ({transferred}/{total_size} bytes)"
                    )
                elif event_type == "item" and event.get("stage") == "finished":
                    if event.get("success"):
                        append_log(f"✓ 下载成功: {event.get('local_path', '')}")
                    else:
                        append_log(f"❌ 下载失败: {event.get('name', '-')} | {event.get('error', '未知错误')}")
                elif event_type == "finish":
                    succ = int(event.get("success_count", 0))
                    fail = int(event.get("fail_count", 0))
                    progress_var.set(100 if fail == 0 else float(progress_var.get()))
                    speed_var.set("速度: -")
                    detail_var.set(f"详情: 下载完成，成功 {succ}，失败 {fail}")
                    set_busy(False, "就绪")

            def worker():
                self.model_download_manager.download_models(
                    download_targets,
                    local_dir,
                    progress_callback=lambda e: self.root.after(0, lambda ev=e: on_progress(ev)),
                )

            threading.Thread(target=worker, daemon=True).start()

        def delete_selected():
            if state["busy"]:
                return
            models = selected_models()
            if not models:
                messagebox.showwarning("提示", "请先选择要删除的模型")
                return
            paths = [m.get("path", "") for m in models if m.get("path")]
            if not paths:
                messagebox.showwarning("提示", "选中项缺少路径，无法删除")
                return
            if not messagebox.askyesno("确认删除", f"确认删除选中的 {len(paths)} 个模型文件吗？"):
                return

            set_busy(True, "删除中")
            progress_var.set(0)
            speed_var.set("速度: -")
            detail_var.set(f"详情: 正在删除 {len(paths)} 个文件")

            def worker():
                success, msg = self.model_manager.remove_models(paths)

                def done():
                    if success:
                        append_log(f"✓ {msg}")
                        progress_var.set(100)
                        refresh_models()
                    else:
                        append_log(f"❌ 删除失败: {msg}")
                        set_busy(False, "就绪")

                self.root.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        def convert_selected():
            if state["busy"]:
                return
            models = selected_models()
            if not models:
                messagebox.showwarning("提示", "请先选择要转换的 .pt 模型")
                return
            bad = [m.get("name", "") for m in models if str(m.get("ext", "")).lower() != ".pt"]
            if bad:
                messagebox.showwarning("提示", "仅支持选中的 .pt 模型进行转换")
                return

            set_busy(True, "TFLite转换中")
            progress_var.set(0)
            detail_var.set(f"详情: 准备转换 {len(models)} 个 .pt 模型")
            speed_var.set("速度: -")

            def worker():
                preferred_export_python = self.config_manager.convert_config.get("python_export_cmd", "")
                python_cmd, ultra_ver = self.environment_manager.get_export_python_cmd(
                    preferred_cmd=preferred_export_python,
                    log_callback=lambda msg: self.root.after(0, lambda m=msg: self.ui.log_message(m)),
                )
                if not python_cmd:
                    self.root.after(0, lambda: append_log("❌ 转换失败: 未找到可用转换环境"))
                    self.root.after(0, lambda: detail_var.set("详情: 转换环境不可用"))
                    self.root.after(0, lambda: set_busy(False, "就绪"))
                    return

                if preferred_export_python != python_cmd:
                    self.config_manager.convert_config["python_export_cmd"] = python_cmd
                    self.config_manager.save_config()

                self.root.after(0, lambda p=python_cmd, v=ultra_ver: append_log(f"使用转换环境: {p} | ultralytics={v or 'unknown'}"))
                total = len(models)
                success_count = 0

                for idx, m in enumerate(models, start=1):
                    name = m.get("name", "unknown")
                    remote_path = m.get("path", "")
                    self.root.after(
                        0,
                        lambda i=idx, t=total, n=name: detail_var.set(f"详情: 正在转换 {i}/{t} {n}")
                    )
                    self.root.after(0, lambda p=(idx - 1) / total * 100.0: progress_var.set(p))
                    self.root.after(0, lambda: set_progress_animating(True))
                    ok, msg = self.model_manager.convert_remote_model_to_tflite(
                        remote_model=remote_path,
                        python_cmd=python_cmd,
                        log_callback=lambda mm: self.root.after(0, lambda mmm=mm: self.ui.log_message(mmm)),
                    )
                    self.root.after(0, lambda: set_progress_animating(False))
                    if ok:
                        success_count += 1
                        self.root.after(0, lambda n=name, mmsg=msg: append_log(f"✓ 转换成功: {n} | {mmsg}"))
                    else:
                        self.root.after(0, lambda n=name, mmsg=msg: append_log(f"❌ 转换失败: {n} | {mmsg}"))
                    self.root.after(0, lambda p=idx / total * 100.0: progress_var.set(p))

                def done():
                    fail_count = total - success_count
                    set_progress_animating(False)
                    detail_var.set(f"详情: 转换完成，成功 {success_count}，失败 {fail_count}")
                    set_busy(False, "就绪")
                    refresh_models()

                self.root.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        refresh_btn = ttk.Button(action_frame, text="刷新列表", bootstyle="secondary", command=refresh_models)
        download_btn = ttk.Button(action_frame, text="下载选中", bootstyle="success", command=start_download)
        delete_btn = ttk.Button(action_frame, text="删除模型", bootstyle="danger", command=delete_selected)
        convert_btn = ttk.Button(action_frame, text="TFLite转换", bootstyle="warning", command=convert_selected)
        close_btn = ttk.Button(action_frame, text="关闭", bootstyle="secondary", command=close_model_window)

        refresh_btn.pack(side="left", padx=(0, 6))
        download_btn.pack(side="left", padx=(0, 6))
        delete_btn.pack(side="left", padx=(0, 6))
        convert_btn.pack(side="left", padx=(0, 6))
        close_btn.pack(side="right")
        update_action_buttons()

        self._model_list_refresh_fn = refresh_models
        refresh_models()

    def _open_file_manager(self):
        """远程文件管理窗口"""
        if self._active_server_operation:
            self.ui.log_message(f"当前正在执行[{self._active_server_operation_label}]，请稍后再打开文件管理。")
            return
        if self._remote_file_window and self._remote_file_window.exists():
            self._remote_file_window.lift()
            return

        initial_path = self.ui.remote_dataset_path_var.get().strip() or "/root/yolo_dataset"
        self._remote_file_window = FileManagerWindow(
            self.root, 
            self.file_manager_manager, 
            initial_path=initial_path,
            log_callback=self.ui.log_message
        )

    def _open_fullscreen_monitor(self):
        """全屏监控窗口"""
        if not self.server_manager.is_connected:
            self.ui.log_message("服务器未连接，无法打开训练监控大屏")
            return
        if self._monitor_window and self._monitor_window.exists():
            self._monitor_window.lift()
            return

        self._monitor_window = MonitorWindow(
            parent=self.root,
            monitor_manager=self.monitor_manager,
            training_monitor_manager=self.training_monitor_manager,
            ui=self.ui,
            is_connected_fn=lambda: self.server_manager.is_connected,
            get_remote_dataset_path_fn=lambda: self.ui.remote_dataset_path_var.get(),
            get_model_name_fn=self.training_manager.build_model_name,
        )

    def _on_close(self):
        self._stop_ping_monitor(reset_metrics=False)
        
        # 关闭可能存在的子窗口
        if self._monitor_window and self._monitor_window.exists():
            self._monitor_window.close()
        if self._remote_file_window and self._remote_file_window.exists():
            self._remote_file_window.win.destroy()
        
        # 退出前保存所有配置，包括窗口尺寸
        self.config_manager.save_config()
        
        self.server_manager.disconnect()
        self.root.destroy()

    def run(self):
        """运行应用"""
        self.root.mainloop()

if __name__ == "__main__":
    app = Application()
    app.run()
