#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端训练脚本优化可视化GUI界面
包含服务器配置、数据集配置、训练监控等核心功能模块
"""

import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import json
import os
import sys
import threading
import subprocess
import re
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
import winsound
from plyer import notification

# 设置 matplotlib 支持中文
plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial']
plt.rcParams['axes.unicode_minus'] = False

class CloudTrainingGUI:
    def __init__(self, root):
        self.root = root
        self.app_version = "v2.2.10"
        self.default_runtime_mode = "preinstalled_pytorch"
        self.valid_runtime_modes = {"preinstalled_pytorch", "docker_ubuntu2204"}
        self.runtime_profiles = {
            "preinstalled_pytorch": {
                "display_name": "预装PyTorch",
                "expected_ubuntu": "20.04",
                "default_username": "root",
            },
            "docker_ubuntu2204": {
                "display_name": "Docker(Ubuntu22.04)",
                "expected_ubuntu": "22.04",
                "default_username": "ubuntu",
            },
        }
        self.root.title(f"云端训练脚本优化管理平台 {self.app_version}")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        
        # 配置文件路径
        self.config_file = "cloud_training_config.json"
        
        # 初始化配置
        self.server_config = {
            'hostname': '',
            'port': 22,
            'username': 'root',
            'password': 'Vonzeus01',
            'key_file': '',
            'runtime_mode': self.default_runtime_mode
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
            'base_model': 'yolov8s.pt',
            'model_name_suffix': '',
            # 图像增强参数
            'augment_scale': 0.5,
            'augment_fliplr': 0.5,
            'augment_hsv_h': 0.015,
            'augment_hsv_s': 0.7,
            'augment_hsv_v': 0.4
        }
        self.deploy_docker_config = {
            'image_repo': 'ultralytics/ultralytics',
            'image_tag': 'latest',
            'container_name': 'cloud_training_runner',
            'remote_deploy_dir': '/opt/cloud_training/docker_ubuntu2204',
            'host_workspace_dir': '/root/cloud_training_workspace',
            'enable_gpu': True,
            'last_status': '未部署',
            'last_deploy_time': ''
        }

        # 状态变量
        self.is_connected = False
        self.is_training = False
        self.is_monitoring = False
        self.upload_in_progress = False
        self.upload_progress = 0
        self.upload_cancel_event = threading.Event()
        self.dataset_check_passed = False
        self.remote_verify_passed = False
        self.last_dataset_fingerprint = ""
        self.last_dataset_check_time = ""
        self.last_upload_plan = None
        self._persistence_bound = False
        self.auto_recommend_running = False
        self.docker_deploy_in_progress = False
        
        # SSH客户端
        self.ssh_client = None
        
        # 监控数据存储
        self.max_data_points = 50  # 最多保存50个数据点
        self.gpu_utilization_data = deque(maxlen=self.max_data_points)
        self.gpu_memory_data = deque(maxlen=self.max_data_points)
        self.loss_box_data = deque(maxlen=self.max_data_points)
        self.loss_cls_data = deque(maxlen=self.max_data_points)
        self.loss_dfl_data = deque(maxlen=self.max_data_points)
        self.loss_epoch_data = deque(maxlen=self.max_data_points)
        self.last_loss_epoch = -1
        self._last_training_compact_line = ""
        self._last_training_log_text = ""
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
        self.training_run_name = None
        self._last_progress_update = 0.0
        self._run_dir_logged = False
        
        self.config = {
            'server': self.server_config,
            'dataset': self.dataset_config,
            'training': self.training_config,
            'deploy_docker': self.deploy_docker_config,
            'upload': {
                'max_workers': 8,
                'retry_times': 3
            }
        }
        self.load_config()
        self._apply_runtime_mode_defaults(force_username=False)
        
        # 设置UI
        self.setup_ui()
        self.update_action_button_states()
        self.root.protocol("WM_DELETE_WINDOW", self._on_app_close)
        
        # 设置日志
        self.setup_logging()

    def _normalize_runtime_mode(self, runtime_mode):
        mode = str(runtime_mode or "").strip()
        if mode not in self.valid_runtime_modes:
            return self.default_runtime_mode
        return mode

    def _get_runtime_profile(self, runtime_mode=None):
        mode = self._normalize_runtime_mode(runtime_mode or self.server_config.get("runtime_mode"))
        return self.runtime_profiles.get(mode, self.runtime_profiles[self.default_runtime_mode])

    def _apply_runtime_mode_defaults(self, force_username=False):
        mode = self._normalize_runtime_mode(self.server_config.get("runtime_mode"))
        profile = self._get_runtime_profile(mode)
        default_username = profile["default_username"]
        current_username = (self.server_config.get("username") or "").strip()
        if force_username or not current_username:
            self.server_config["username"] = default_username
            if hasattr(self, "username_var"):
                self.username_var.set(default_username)

    def _set_docker_deploy_status(self, text, color="gray"):
        if hasattr(self, "docker_deploy_status_var"):
            self.docker_deploy_status_var.set(text)
        if hasattr(self, "docker_deploy_status_label"):
            self.docker_deploy_status_label.config(foreground=color)

    def _refresh_docker_deploy_controls(self):
        if not hasattr(self, "deploy_docker_button"):
            return
        runtime_mode = self._normalize_runtime_mode(
            self.runtime_mode_var.get() if hasattr(self, "runtime_mode_var") else self.server_config.get("runtime_mode")
        )
        docker_mode = runtime_mode == "docker_ubuntu2204"
        enabled = docker_mode and self.is_connected and (not self.docker_deploy_in_progress)
        self.deploy_docker_button.configure(state=("normal" if enabled else "disabled"))
        if not docker_mode:
            self._set_docker_deploy_status("当前模式非 docker_ubuntu2204", "gray")

    def _build_connect_params(self):
        connect_params = {
            "hostname": self.server_config["hostname"],
            "port": self.server_config["port"],
            "username": self.server_config["username"],
        }
        if self.server_config.get("key_file"):
            connect_params["key_filename"] = self.server_config["key_file"]
        else:
            connect_params["password"] = self.server_config["password"]
        return connect_params

    def _build_docker_compose_content(self):
        deploy_cfg = self.config.get("deploy_docker", self.deploy_docker_config)
        image_repo = str(deploy_cfg.get("image_repo", "ultralytics/ultralytics")).strip() or "ultralytics/ultralytics"
        image_tag = str(deploy_cfg.get("image_tag", "latest")).strip() or "latest"
        container_name = str(deploy_cfg.get("container_name", "cloud_training_runner")).strip() or "cloud_training_runner"
        host_workspace_dir = str(deploy_cfg.get("host_workspace_dir", "/root/cloud_training_workspace")).strip() or "/root/cloud_training_workspace"
        remote_dataset_dir = str(self.dataset_config.get("remote_path", "/root/yolo_dataset")).strip() or "/root/yolo_dataset"
        enable_gpu = bool(deploy_cfg.get("enable_gpu", True))
        gpu_block = "    gpus: all\n" if enable_gpu else ""
        return (
            "name: cloud_training\n"
            "services:\n"
            "  trainer:\n"
            f"    image: {image_repo}:{image_tag}\n"
            f"    container_name: {container_name}\n"
            "    working_dir: /workspace\n"
            "    tty: true\n"
            "    stdin_open: true\n"
            "    restart: unless-stopped\n"
            f"{gpu_block}"
            "    environment:\n"
            "      YOLO_AUTOINSTALL: \"0\"\n"
            "      ULTRALYTICS_AUTOINSTALL: \"0\"\n"
            "      PYTHONDONTWRITEBYTECODE: \"1\"\n"
            "      TZ: \"Asia/Shanghai\"\n"
            "    command: [\"bash\", \"-lc\", \"sleep infinity\"]\n"
            "    volumes:\n"
            f"      - {host_workspace_dir}:/workspace\n"
            f"      - {remote_dataset_dir}:/workspace/dataset\n"
        )

    def one_click_deploy_docker(self):
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        runtime_mode = self._normalize_runtime_mode(self.server_config.get("runtime_mode"))
        if runtime_mode != "docker_ubuntu2204":
            messagebox.showwarning("提示", "仅在 docker_ubuntu2204 模式下可执行一键部署")
            return
        self.update_server_config()
        deploy_cfg = self.config.get("deploy_docker", self.deploy_docker_config)
        image_repo = str(deploy_cfg.get("image_repo", "")).strip()
        image_tag = str(deploy_cfg.get("image_tag", "")).strip()
        if not image_repo or not image_tag:
            messagebox.showerror("错误", "deploy_docker 配置缺失 image_repo 或 image_tag")
            return

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Docker 一键部署")
        progress_window.geometry("760x520")
        progress_window.transient(self.root)
        progress_window.grab_set()

        ttk.Label(progress_window, text="正在执行 Docker 一键部署...", font=("Arial", 12, "bold")).pack(pady=10)
        deploy_progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(progress_window, variable=deploy_progress_var, maximum=100).pack(fill='x', padx=16, pady=(0, 10))

        log_frame = ttk.Frame(progress_window)
        log_frame.pack(fill='both', expand=True, padx=16, pady=8)
        deploy_log = tk.Text(log_frame, wrap='word', font=('Consolas', 9))
        deploy_scrollbar = ttk.Scrollbar(log_frame, orient='vertical', command=deploy_log.yview)
        deploy_log.configure(yscrollcommand=deploy_scrollbar.set)
        deploy_log.pack(side='left', fill='both', expand=True)
        deploy_scrollbar.pack(side='right', fill='y')
        ttk.Button(progress_window, text="关闭", command=progress_window.destroy).pack(pady=(0, 12))

        def append_log(message):
            self.root.after(0, lambda m=message: deploy_log.insert(tk.END, m + "\n"))
            self.root.after(0, lambda: deploy_log.see(tk.END))

        def set_progress(v):
            self.root.after(0, lambda x=v: deploy_progress_var.set(x))

        def deploy_thread():
            ssh = None
            try:
                self.docker_deploy_in_progress = True
                self.root.after(0, self._refresh_docker_deploy_controls)
                self.root.after(0, lambda: self._set_docker_deploy_status("部署中...", "orange"))
                append_log("开始执行 Docker 一键部署")
                append_log("=" * 60)
                set_progress(3)

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(**self._build_connect_params(), timeout=20)
                append_log("SSH 已连接")
                set_progress(8)

                use_sudo = self.server_config.get("username", "").strip() != "root"
                sudo_prefix = "sudo " if use_sudo else ""

                def run_cmd(step_name, cmd, timeout=1800):
                    append_log(f"\n[{step_name}]")
                    append_log(f"$ {cmd}")
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
                    output = stdout.read().decode("utf-8", errors="ignore").strip()
                    err = stderr.read().decode("utf-8", errors="ignore").strip()
                    code = stdout.channel.recv_exit_status()
                    if output:
                        append_log(output)
                    if err:
                        append_log(err)
                    if code != 0:
                        raise RuntimeError(f"{step_name} 失败，退出码 {code}")

                run_cmd("安装依赖工具", f"{sudo_prefix}apt-get update -y && {sudo_prefix}apt-get install -y ca-certificates curl gnupg lsb-release")
                set_progress(20)
                run_cmd("准备 Docker keyrings", f"{sudo_prefix}install -m 0755 -d /etc/apt/keyrings")
                run_cmd("写入 Docker GPG", f"curl -fsSL https://download.docker.com/linux/ubuntu/gpg | {sudo_prefix}gpg --dearmor -o /etc/apt/keyrings/docker.gpg")
                run_cmd("修正 GPG 权限", f"{sudo_prefix}chmod a+r /etc/apt/keyrings/docker.gpg")
                set_progress(34)

                stdin, stdout, stderr = ssh.exec_command(". /etc/os-release && echo ${VERSION_CODENAME:-jammy}")
                codename = stdout.read().decode("utf-8", errors="ignore").strip() or "jammy"
                repo_line = (
                    f"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] "
                    f"https://download.docker.com/linux/ubuntu {codename} stable"
                )
                run_cmd(
                    "写入 Docker 官方仓库",
                    f"echo '{repo_line}' | {sudo_prefix}tee /etc/apt/sources.list.d/docker.list >/dev/null"
                )
                set_progress(45)

                run_cmd("安装 Docker 引擎", f"{sudo_prefix}apt-get update -y && {sudo_prefix}apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin")
                run_cmd("启动 Docker 服务", f"{sudo_prefix}systemctl enable --now docker")
                set_progress(58)

                remote_dir = str(deploy_cfg.get("remote_deploy_dir", "/opt/cloud_training/docker_ubuntu2204")).strip() or "/opt/cloud_training/docker_ubuntu2204"
                workspace_dir = str(deploy_cfg.get("host_workspace_dir", "/root/cloud_training_workspace")).strip() or "/root/cloud_training_workspace"
                dataset_dir = str(self.dataset_config.get("remote_path", "/root/yolo_dataset")).strip() or "/root/yolo_dataset"
                run_cmd("创建部署目录", f"{sudo_prefix}mkdir -p '{remote_dir}' '{workspace_dir}' '{dataset_dir}'")
                set_progress(66)

                remote_compose_path = f"{remote_dir}/docker-compose.yml"
                compose_content = self._build_docker_compose_content()
                sftp = ssh.open_sftp()
                with sftp.open(remote_compose_path, 'w') as f:
                    f.write(compose_content)
                sftp.close()
                append_log(f"已上传 compose: {remote_compose_path}")
                set_progress(74)

                run_cmd("拉取镜像", f"{sudo_prefix}docker compose -f '{remote_compose_path}' pull", timeout=3600)
                set_progress(84)
                run_cmd("启动容器", f"{sudo_prefix}docker compose -f '{remote_compose_path}' up -d", timeout=1200)
                set_progress(92)

                run_cmd("校验 Docker 版本", f"{sudo_prefix}docker --version")
                run_cmd("校验 Compose 版本", f"{sudo_prefix}docker compose version")
                run_cmd("校验容器状态", f"{sudo_prefix}docker compose -f '{remote_compose_path}' ps")
                set_progress(100)

                now_text = time.strftime("%Y-%m-%d %H:%M:%S")
                self.config["deploy_docker"]["last_status"] = "部署成功"
                self.config["deploy_docker"]["last_deploy_time"] = now_text
                self.save_config({"deploy_docker": self.config["deploy_docker"]})
                self.root.after(0, lambda: self._set_docker_deploy_status(f"部署成功 {now_text}", "green"))
                self.root.after(0, lambda: self.log_message("Docker 一键部署成功"))
                append_log("\n部署完成")
                self.root.after(0, lambda: messagebox.showinfo("成功", "Docker 一键部署完成"))
            except Exception as e:
                err = str(e)
                self.config["deploy_docker"]["last_status"] = f"部署失败: {err}"
                self.save_config({"deploy_docker": self.config["deploy_docker"]})
                self.root.after(0, lambda m=err: self._set_docker_deploy_status(f"部署失败: {m}", "red"))
                self.root.after(0, lambda m=err: self.log_message(f"Docker 一键部署失败: {m}"))
                append_log(f"\n部署失败: {err}")
                self.root.after(0, lambda m=err: messagebox.showerror("错误", f"Docker 一键部署失败:\n{m}"))
            finally:
                if ssh:
                    try:
                        ssh.close()
                    except Exception:
                        pass
                self.docker_deploy_in_progress = False
                self.root.after(0, self._refresh_docker_deploy_controls)

        threading.Thread(target=deploy_thread, daemon=True).start()

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

    def update_action_button_states(self):
        try:
            upload_enabled = self.upload_in_progress or (self.is_connected and self.dataset_check_passed)
            train_enabled = (not self.upload_in_progress) and self.is_connected and self.dataset_check_passed and self.remote_verify_passed
            if hasattr(self, 'upload_toggle_button'):
                self.upload_toggle_button.configure(state=("normal" if upload_enabled else "disabled"))
            if hasattr(self, 'start_training_button'):
                self.start_training_button.configure(state=("normal" if train_enabled else "disabled"))
            self._refresh_docker_deploy_controls()
        except Exception:
            pass

    def _apply_saved_augment_states(self):
        """应用保存的图像增强激活状态到UI"""
        try:
            for key, active_var in self.augment_active_vars.items():
                saved_state = self.training_config.get(f'{key}_active', True)
                active_var.set(saved_state)
        except Exception:
            pass

    def invalidate_dataset_pipeline(self, reason=None):
        self.dataset_check_passed = False
        self.remote_verify_passed = False
        self.last_dataset_fingerprint = ""
        self.last_dataset_check_time = ""
        self.last_upload_plan = None
        if hasattr(self, 'dataset_check_status_var'):
            self.dataset_check_status_var.set("检查状态: 未检查")
        if hasattr(self, 'dataset_summary_var'):
            self.dataset_summary_var.set("检查总结: 未生成")
        if reason:
            self.log_message(reason)
        self.update_action_button_states()

    def copy_text_to_clipboard(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            return True
        except Exception:
            return False

    def show_remote_verify_failure(self, msg, bad_text):
        copy_tip = ""
        if bad_text:
            if self.copy_text_to_clipboard(bad_text):
                copy_tip = "\n定位信息已复制到剪贴板"
        messagebox.showerror("云端验收失败", f"{msg}{copy_tip}")

    def _model_profile(self, model_name):
        import re
        name = str(model_name).lower()
        match = re.search(r'yolov\d+([a-z])', name)
        scale = match.group(1) if match else 's'
        if scale in ['c', 'b']:
            scale = 'm'
        if scale == 'e':
            scale = 'l'
        if scale not in ['n', 's', 'm', 'l', 'x']:
            scale = 's'
        return scale

    def _recommended_training_params(self, model_name, image_size):
        base_batch_640 = {
            'n': 32,
            's': 24,
            'm': 16,
            'l': 10,
            'x': 8
        }
        scale = self._model_profile(model_name)
        try:
            imgsz = int(image_size)
        except Exception:
            imgsz = 640
        if imgsz <= 0:
            imgsz = 640
        factor = (640.0 / float(imgsz)) ** 2
        rec_batch = int(round(base_batch_640.get(scale, 24) * factor))
        if rec_batch < 2:
            rec_batch = 2
        if rec_batch > 64:
            rec_batch = 64
        rec_lr = 0.01 * (rec_batch / 16.0)
        if rec_lr < 0.002:
            rec_lr = 0.002
        if rec_lr > 0.02:
            rec_lr = 0.02
        return {
            'batch_size': rec_batch,
            'learning_rate': round(rec_lr, 5)
        }

    def apply_auto_recommended_training_params(self, trigger_key):
        if self.auto_recommend_running:
            return
        if not hasattr(self, 'image_size_var') or not hasattr(self, 'base_model_var'):
            return
        try:
            imgsz_text = str(self.image_size_var.get()).strip()
            if not imgsz_text:
                return
            imgsz = int(imgsz_text)
        except Exception:
            return

        rec = self._recommended_training_params(self.base_model_var.get(), imgsz)
        changed = []
        self.auto_recommend_running = True
        try:
            if hasattr(self, 'batch_size_var'):
                current_batch = str(self.batch_size_var.get()).strip()
                next_batch = str(rec['batch_size'])
                if current_batch != next_batch:
                    self.batch_size_var.set(next_batch)
                    changed.append(f"batch={next_batch}")
            if hasattr(self, 'learning_rate_var'):
                current_lr = str(self.learning_rate_var.get()).strip()
                next_lr = f"{rec['learning_rate']:.5f}".rstrip('0').rstrip('.')
                if current_lr != next_lr:
                    self.learning_rate_var.set(next_lr)
                    changed.append(f"lr={next_lr}")
        finally:
            self.auto_recommend_running = False

        if changed:
            msg = f"已按{trigger_key}自动推荐参数: {', '.join(changed)}，可手动修改"
            if hasattr(self, 'upload_status_var'):
                self.upload_status_var.set(msg)
            self.log_message(msg)

    def _normalize_name_list(self, names):
        if isinstance(names, list):
            return [str(x) for x in names]
        if isinstance(names, dict):
            try:
                keys = sorted(names.keys(), key=lambda x: int(x))
            except Exception:
                keys = sorted(names.keys(), key=lambda x: str(x))
            return [str(names[k]) for k in keys]
        return []

    def _build_dataset_fingerprint(self, dataset_path):
        hasher = hashlib.sha256()
        for root, _, files in os.walk(dataset_path):
            for name in sorted(files):
                lower_name = name.lower()
                if lower_name.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.txt', '.yaml', '.yml')):
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, dataset_path).replace('\\', '/')
                    st = os.stat(full)
                    hasher.update(f"{rel}|{st.st_size}|{int(st.st_mtime)}".encode('utf-8', errors='ignore'))
        return hasher.hexdigest()

    def _build_expected_upload_map(self, dataset_path):
        expected = {}
        for root, _, files in os.walk(dataset_path):
            for name in files:
                local_file = os.path.join(root, name)
                rel_path = os.path.relpath(local_file, dataset_path).replace('\\', '/')
                if not self._should_upload_file(rel_path):
                    continue
                try:
                    expected[rel_path] = int(os.path.getsize(local_file))
                except Exception:
                    continue
        return expected

    def _format_bytes(self, size_bytes):
        try:
            size = float(size_bytes)
        except Exception:
            size = 0.0
        if size < 1024:
            return f"{int(size)} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.2f} GB"

    def quick_compare_remote_dataset(self, dataset_path, remote_path, progress_cb=None):
        result = {
            'ok': False,
            'msg': '',
            'expected_total': 0,
            'expected_total_bytes': 0,
            'remote_total': 0,
            'need_upload': 0,
            'skip_count': 0,
            'need_upload_bytes': 0,
            'todo_rel_paths': []
        }
        try:
            if callable(progress_cb):
                progress_cb("云端差异检查: 正在收集本地文件清单...")
            expected = self._build_expected_upload_map(dataset_path)
            result['expected_total'] = len(expected)
            result['expected_total_bytes'] = sum(int(v) for v in expected.values())
            if not self.is_connected:
                result['msg'] = "未连接服务器，已跳过云端差异检查"
                return result
            if not remote_path:
                result['msg'] = "远程路径为空，已跳过云端差异检查"
                return result
            if callable(progress_cb):
                progress_cb(f"云端差异检查: 本地可上传文件 {result['expected_total']}，正在读取云端...")

            self.update_server_config()
            connect_params = {
                'hostname': self.server_config['hostname'],
                'port': self.server_config['port'],
                'username': self.server_config['username']
            }
            if self.server_config['key_file']:
                connect_params['key_filename'] = self.server_config['key_file']
            elif self.server_config['password']:
                connect_params['password'] = self.server_config['password']

            remote_script = f"""import os, json
root = {repr(remote_path)}
out = {{}}
if os.path.isdir(root):
    for base, _, files in os.walk(root):
        for fn in files:
            full = os.path.join(base, fn)
            rel = os.path.relpath(full, root).replace('\\\\', '/')
            try:
                out[rel] = int(os.path.getsize(full))
            except Exception:
                pass
print(json.dumps({{"ok": True, "files": out}}, ensure_ascii=False))"""

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(**connect_params, timeout=15)

                # 使用优化的Python环境检测（优先方案+兼容方案）
                python_cmd = self.get_python_cmd_with_fallback(ssh)

                if not python_cmd:
                    result['msg'] = "未找到可用的Python命令"
                    return result

                cmd = f"{python_cmd} - <<'PY'\n" + remote_script + "\nPY"
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=180)
                out = stdout.read().decode('utf-8', errors='ignore').strip()
                err = stderr.read().decode('utf-8', errors='ignore').strip()
                if err:
                    result['msg'] = err
                    return result
                if not out:
                    result['msg'] = "云端差异检查无输出"
                    return result
                last_line = out.splitlines()[-1]
                obj = json.loads(last_line)
                remote_files = obj.get('files') if isinstance(obj, dict) else {}
                if not isinstance(remote_files, dict):
                    remote_files = {}
            finally:
                try:
                    ssh.close()
                except Exception:
                    pass

            todo_rel_paths = []
            need_upload_bytes = 0
            for rel_path, local_size in expected.items():
                if int(remote_files.get(rel_path, -1)) != int(local_size):
                    todo_rel_paths.append(rel_path)
                    need_upload_bytes += int(local_size)

            result['ok'] = True
            result['remote_total'] = len(remote_files)
            result['need_upload'] = len(todo_rel_paths)
            result['skip_count'] = len(expected) - len(todo_rel_paths)
            result['need_upload_bytes'] = need_upload_bytes
            result['todo_rel_paths'] = sorted(todo_rel_paths)
            if callable(progress_cb):
                progress_cb(
                    f"云端差异检查完成: 需上传 {result['need_upload']}，可跳过 {result['skip_count']}，预计 {self._format_bytes(need_upload_bytes)}"
                )
            return result
        except Exception as e:
            result['msg'] = str(e)
            return result

    def _build_check_summary_text(self, result):
        summary = result.get('summary') or {}
        splits = summary.get('splits') or {}
        split_text = " ".join([f"{k}:{v.get('images', 0)}/{v.get('labels', 0)}" for k, v in splits.items()]) or "-"
        elapsed = float(result.get('check_elapsed_sec', 0) or 0)
        base_text = (
            f"本地 images={summary.get('total_images', 0)} labels={summary.get('total_labels', 0)} "
            f"split[{split_text}] 耗时={elapsed:.1f}s"
        )
        remote_diff = result.get('remote_diff') or {}
        if remote_diff.get('ok'):
            return (
                f"{base_text} 云端: 总计{int(remote_diff.get('expected_total', 0))} "
                f"需上传{int(remote_diff.get('need_upload', 0))} "
                f"可跳过{int(remote_diff.get('skip_count', 0))} "
                f"待上传体积{self._format_bytes(remote_diff.get('need_upload_bytes', 0))}"
            )
        msg = str(remote_diff.get('msg', '')).strip()
        if msg:
            return f"{base_text} 云端差异未完成: {msg}"
        return base_text

    def _ensure_dataset_check_is_fresh(self):
        dataset_path = self.local_path_var.get().strip() if hasattr(self, 'local_path_var') else ''
        if not dataset_path or not os.path.isdir(dataset_path):
            self.invalidate_dataset_pipeline("数据集路径无效，已清除检查状态")
            return False
        if not self.dataset_check_passed or not self.last_dataset_fingerprint:
            return False
        current_fp = self._build_dataset_fingerprint(dataset_path)
        if current_fp != self.last_dataset_fingerprint:
            self.invalidate_dataset_pipeline("检测到数据集内容变化，请重新检查后再上传/训练")
            return False
        return True

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

    def get_python_cmd_with_fallback(self, ssh, log_func=None):
        """
        获取可用的Python命令（只探测，不安装）
        策略：优先使用miniforge3（标准环境），失败再只读回退
        """
        python_candidates = [
            "/root/miniforge3/bin/python3",
            "/root/miniconda3/bin/python3",
            "/root/anaconda3/bin/python3",
            "/opt/conda/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
            "python3",
            "python",
        ]
        for cmd in python_candidates:
            stdin, stdout, stderr = ssh.exec_command(
                f'{cmd} -c "import sys, subprocess; '
                f'print(sys.executable); '
                f'print(str(sys.version_info.major)+\'.\'+str(sys.version_info.minor)); '
                f'rc=subprocess.call([sys.executable, \'-m\', \'pip\', \'--version\'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); '
                f'print(\'PIP_OK\' if rc==0 else \'PIP_MISSING\')" 2>/dev/null'
            )
            out = stdout.read().decode('utf-8', errors='ignore').strip().splitlines()
            if len(out) >= 3 and out[-1].strip() == "PIP_OK":
                resolved = out[0].strip() or cmd
                if log_func:
                    log_func(f"✓ 使用Python解释器: {resolved}")
                return resolved

        if log_func:
            log_func("✗ 未找到可用Python解释器（仅探测模式，不自动安装）")
        return None
    
    def setup_ui(self):
        """设置用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        self.style = ttk.Style()
        # ttkbootstrap 原生支持 bootstyle="success" 等，不再需要自定义 TButton 样式

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        # !关键修复: 强制让 notebook 撑满所在网格的垂直空间
        main_frame.rowconfigure(0, weight=1)

        self.setup_dataset_tab()
        self._bind_persistence()
        
        # 状态栏 (由于已有日志输出，不再显示)
        # self.setup_status_bar(main_frame)
    
    def setup_server_tab(self):
        """设置服务器配置选项卡"""
        server_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(server_frame, text="服务器配置")
        
        # 服务器信息框架
        server_info_frame = ttk.Labelframe(server_frame, text="服务器连接信息", padding="10")
        server_info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # IP地址
        ttk.Label(server_info_frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.hostname_var = tk.StringVar(value=self.server_config['hostname'])
        ttk.Entry(server_info_frame, textvariable=self.hostname_var, width=30).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 端口
        ttk.Label(server_info_frame, text="端口:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value=str(self.server_config['port']))
        ttk.Entry(server_info_frame, textvariable=self.port_var, width=30).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 服务器种类
        ttk.Label(server_info_frame, text="服务器种类:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.runtime_mode_var = tk.StringVar(value=self._normalize_runtime_mode(self.server_config.get("runtime_mode")))
        runtime_combo = ttk.Combobox(
            server_info_frame,
            textvariable=self.runtime_mode_var,
            values=["preinstalled_pytorch", "docker_ubuntu2204"],
            state="readonly",
            width=30,
        )
        runtime_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        ttk.Label(
            server_info_frame,
            text="preinstalled_pytorch=Ubuntu20.04, docker_ubuntu2204=Ubuntu22.04",
            foreground="gray",
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))

        # 用户名
        ttk.Label(server_info_frame, text="用户名:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.username_var = tk.StringVar(value=self.server_config['username'])
        ttk.Entry(server_info_frame, textvariable=self.username_var, width=30).grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 密码
        ttk.Label(server_info_frame, text="密码:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.password_var = tk.StringVar(value=self.server_config['password'])
        ttk.Entry(server_info_frame, textvariable=self.password_var, show="*", width=30).grid(row=5, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
        # 密钥文件（可选）
        ttk.Label(server_info_frame, text="密钥文件:").grid(row=6, column=0, sticky=tk.W, pady=2)
        key_frame = ttk.Frame(server_info_frame)
        key_frame.grid(row=6, column=1, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)
        
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
        ttk.Button(button_frame, text="文件管理器", command=self.get_server_info).grid(row=0, column=2, padx=(0, 10))
        
        # 连接状态显示
        self.connection_status_var = tk.StringVar(value="未连接")
        self.connection_status_label = ttk.Label(server_frame, textvariable=self.connection_status_var, foreground="red")
        self.connection_status_label.grid(row=2, column=0, columnspan=2, pady=10)
    
    def setup_dataset_tab(self):
        """设置数据集配置选项卡"""
        # --- 创建滚动容器 ---
        outer_frame = ttk.Frame(self.notebook)
        # 确保outer_frame可以填满notebook
        outer_frame.pack(fill="both", expand=True)
        self.notebook.add(outer_frame, text="数据集配置")
        
        canvas = tk.Canvas(outer_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        dataset_frame = ttk.Frame(canvas, padding="10")
        canvas_window = canvas.create_window((0, 0), window=dataset_frame, anchor="nw")
        
        def configure_dataset_frame(event):
            # 更新滚动区域为 frame 的实际大小
            canvas.configure(scrollregion=canvas.bbox("all"))
        dataset_frame.bind("<Configure>", configure_dataset_frame)
        
        def configure_canvas(event):
            # 获取 canvas 所在窗口的实际大小
            canvas_width = event.width
            # 始终让内部 frame 的宽度和 canvas 一致
            canvas.itemconfig(canvas_window, width=canvas_width)
                
        canvas.bind("<Configure>", configure_canvas)
        
        # 将 canvas 上的事件绑定到外层 frame 上
        def _on_mousewheel(event):
            if canvas.winfo_ismapped():
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        outer_frame.bind_all("<MouseWheel>", _on_mousewheel)

        # --- 两列+底部布局容器 ---
        # 调整左右两列的权重比例，使左侧变窄，右侧变宽
        dataset_frame.columnconfigure(0, weight=1)
        dataset_frame.columnconfigure(1, weight=3)
        
        left_col = ttk.Frame(dataset_frame)
        left_col.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 5))
        left_col.columnconfigure(0, weight=1)
        
        right_col = ttk.Frame(dataset_frame)
        right_col.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N), padx=(5, 0))
        right_col.columnconfigure(0, weight=1)

        bottom_area = ttk.Frame(dataset_frame)
        bottom_area.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        bottom_area.columnconfigure(0, weight=1)
        dataset_frame.rowconfigure(1, weight=1)

        # ==================== 左侧列 (Left Column) ====================
        # 1. 服务器连接信息 (纵向排列)
        server_frame = ttk.Labelframe(left_col, text="服务器连接信息", padding="10")
        server_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        server_frame.columnconfigure(1, weight=1)

        ttk.Label(server_frame, text="服务器IP:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.hostname_var = tk.StringVar(value=self.server_config['hostname'])
        ttk.Entry(server_frame, textvariable=self.hostname_var).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(server_frame, text="端口:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value=str(self.server_config['port']))
        ttk.Entry(server_frame, textvariable=self.port_var).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(server_frame, text="服务器种类:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.runtime_mode_var = tk.StringVar(value=self._normalize_runtime_mode(self.server_config.get("runtime_mode")))
        runtime_combo = ttk.Combobox(
            server_frame,
            textvariable=self.runtime_mode_var,
            values=["preinstalled_pytorch", "docker_ubuntu2204"],
            state="readonly",
        )
        runtime_combo.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2)
        ttk.Label(
            server_frame,
            text="preinstalled_pytorch=Ubuntu20.04, docker_ubuntu2204=Ubuntu22.04",
            foreground="gray",
        ).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))

        ttk.Label(server_frame, text="用户名:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.username_var = tk.StringVar(value=self.server_config['username'])
        ttk.Entry(server_frame, textvariable=self.username_var).grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(server_frame, text="密码:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.password_var = tk.StringVar(value=self.server_config['password'])
        ttk.Entry(server_frame, textvariable=self.password_var, show="*").grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2)

        ttk.Label(server_frame, text="密钥文件:").grid(row=6, column=0, sticky=tk.W, pady=2)
        key_frame = ttk.Frame(server_frame)
        key_frame.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2)
        key_frame.columnconfigure(0, weight=1)
        self.key_file_var = tk.StringVar(value=self.server_config['key_file'])
        ttk.Entry(key_frame, textvariable=self.key_file_var).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(key_frame, text="选择", command=self.select_key_file, width=6).grid(row=0, column=1, padx=(5, 0))

        server_button_frame = ttk.Frame(server_frame)
        server_button_frame.grid(row=7, column=0, columnspan=2, pady=(10, 0))
        server_button_frame.columnconfigure(0, weight=1)
        server_button_frame.columnconfigure(1, weight=1)
        server_button_frame.columnconfigure(2, weight=1)
        server_button_frame.columnconfigure(3, weight=1)
        ttk.Button(server_button_frame, text="测试连接", command=self.test_connection).grid(row=0, column=0, padx=2, sticky=(tk.W, tk.E))
        ttk.Button(server_button_frame, text="保存配置", command=self.save_server_config).grid(row=0, column=1, padx=2, sticky=(tk.W, tk.E))
        ttk.Button(server_button_frame, text="文件管理器", command=self.get_server_info).grid(row=0, column=2, padx=2, sticky=(tk.W, tk.E))
        self.deploy_docker_button = ttk.Button(server_button_frame, text="一键部署Docker", command=self.one_click_deploy_docker)
        self.deploy_docker_button.grid(row=0, column=3, padx=2, sticky=(tk.W, tk.E))

        self.connection_status_var = tk.StringVar(value="未连接")
        self.connection_status_label = ttk.Label(server_frame, textvariable=self.connection_status_var, foreground="red", anchor="center")
        self.connection_status_label.grid(row=8, column=0, columnspan=2, pady=(5, 0), sticky=(tk.W, tk.E))
        self.docker_deploy_status_var = tk.StringVar(value=self.config.get("deploy_docker", {}).get("last_status", "未部署"))
        self.docker_deploy_status_label = ttk.Label(server_frame, textvariable=self.docker_deploy_status_var, foreground="gray", anchor="center")
        self.docker_deploy_status_label.grid(row=9, column=0, columnspan=2, pady=(3, 0), sticky=(tk.W, tk.E))
        self._refresh_docker_deploy_controls()

        # 2. 训练参数配置 (均分双列布局：左列基础参数，右列图像增强)
        params_frame = ttk.Labelframe(left_col, text="训练参数配置", padding="10")
        params_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        params_frame.columnconfigure(0, weight=1)
        params_frame.columnconfigure(1, weight=1)
        
        # 左列：基础参数
        left_params = ttk.Frame(params_frame)
        left_params.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        left_params.columnconfigure(0, weight=1)
        
        # 基础参数行配置
        base_params = [
            ("训练轮数:", 'epochs', self.training_config['epochs']),
            ("批次大小:", 'batch_size', self.training_config['batch_size']),
            ("学习率:", 'learning_rate', self.training_config['learning_rate']),
            ("图像大小:", 'image_size', self.training_config['image_size']),
        ]
        
        self.epochs_var = tk.StringVar(value=str(self.training_config['epochs']))
        self.batch_size_var = tk.StringVar(value=str(self.training_config['batch_size']))
        self.learning_rate_var = tk.StringVar(value=str(self.training_config['learning_rate']))
        self.image_size_var = tk.StringVar(value=str(self.training_config['image_size']))
        
        for i, (label, key, default) in enumerate(base_params):
            row_frame = ttk.Frame(left_params)
            row_frame.grid(row=i, column=0, sticky=(tk.W, tk.E), pady=3)
            row_frame.columnconfigure(1, weight=1)
            ttk.Label(row_frame, text=label).grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
            var = getattr(self, f'{key}_var')
            ttk.Entry(row_frame, textvariable=var, width=10).grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # 基础模型
        model_frame = ttk.Frame(left_params)
        model_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=3)
        model_frame.columnconfigure(1, weight=1)
        ttk.Label(model_frame, text="基础模型:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.base_model_var = tk.StringVar(value=self.training_config['base_model'])
        model_combo = ttk.Combobox(model_frame, textvariable=self.base_model_var, width=10)
        model_combo['values'] = (
            'yolov8n.pt', 'yolov8s.pt', 'yolov8m.pt', 'yolov8l.pt', 'yolov8x.pt',
            'yolov9c.pt', 'yolov9e.pt',
            'yolov10n.pt', 'yolov10s.pt', 'yolov10m.pt', 'yolov10b.pt', 'yolov10l.pt', 'yolov10x.pt',
            'yolov11n.pt', 'yolov11s.pt', 'yolov11m.pt', 'yolov11l.pt', 'yolov11x.pt'
        )
        model_combo.bind('<MouseWheel>', lambda e: "break")
        model_combo.grid(row=0, column=1, sticky=(tk.W, tk.E))

        # 模型命名后缀（用于训练产物重命名）
        model_name_frame = ttk.Frame(left_params)
        model_name_frame.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=3)
        model_name_frame.columnconfigure(1, weight=1)
        ttk.Label(model_name_frame, text="模型命名:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.model_name_suffix_var = tk.StringVar(value=self.training_config.get('model_name_suffix', ''))
        ttk.Entry(model_name_frame, textvariable=self.model_name_suffix_var, width=18).grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # 右列：图像增强参数（滑块）
        right_params = ttk.Frame(params_frame)
        right_params.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        right_params.columnconfigure(0, weight=1)
        
        # 图像增强参数配置（中文标签）
        augment_configs = [
            ("缩放增强:", 'augment_scale', 0.0, 1.0, 0.5),
            ("水平翻转:", 'augment_fliplr', 0.0, 1.0, 0.5),
            ("色调变化:", 'augment_hsv_h', 0.0, 0.1, 0.015),
            ("饱和变化:", 'augment_hsv_s', 0.0, 1.0, 0.7),
            ("亮度变化:", 'augment_hsv_v', 0.0, 1.0, 0.4),
        ]
        
        # 创建滑块变量
        for label, key, from_, to, default in augment_configs:
            setattr(self, f'{key}_var', tk.DoubleVar(value=self.training_config.get(key, default)))
        
        # 辅助函数：创建带数值显示、默认值标记和激活勾选框的滑块
        def create_augment_slider(parent, label_text, var, from_, to, default, row):
            """创建图像增强滑块控件（高对比度+默认值标记+激活勾选框）"""
            frame = ttk.Frame(parent)
            frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=2)
            frame.columnconfigure(1, weight=1)
            
            # 标签
            ttk.Label(frame, text=label_text, width=8).grid(row=0, column=0, sticky=tk.W)
            
            # 滑块容器（包含滑块和默认值标记）
            slider_container = tk.Frame(frame, bg='#f5f5f5')
            slider_container.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
            slider_container.columnconfigure(0, weight=1)
            
            # 计算默认值位置（百分比）
            default_pct = (default - from_) / (to - from_) if to != from_ else 0
            
            # 使用tk.Scale以支持自定义颜色（高对比度）
            resolution = 0.001 if to <= 1 else 0.01
            scale = tk.Scale(slider_container, from_=from_, to=to, orient=tk.HORIZONTAL,
                           variable=var, resolution=resolution,
                           showvalue=False, length=90, sliderlength=14,
                           bg='#f5f5f5', troughcolor='#888888',
                           activebackground='#1976D2', highlightthickness=0,
                           borderwidth=0)
            scale.grid(row=0, column=0, sticky=(tk.W, tk.E))
            
            # 默认值标记（小三角形）
            marker_frame = tk.Frame(slider_container, bg='#f5f5f5', height=8)
            marker_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
            marker_frame.grid_propagate(False)
            
            # 创建三角形标记
            def create_marker():
                canvas = tk.Canvas(marker_frame, bg='#f5f5f5', highlightthickness=0, 
                                 height=8, width=90)
                canvas.pack(fill=tk.X, expand=True)
                
                # 计算标记位置（考虑滑块内边距）
                pad = 8  # 滑块左右内边距
                avail_width = 90 - 2 * pad
                marker_x = pad + avail_width * default_pct
                
                # 绘制小三角形（默认值标记）
                canvas.create_polygon(
                    marker_x, 0, marker_x-3, 6, marker_x+3, 6,
                    fill='#FF5722', outline='#FF5722'
                )
                return canvas
            
            create_marker()
            
            # 数值显示（滑块右侧）
            value_label = ttk.Label(frame, text=f"{var.get():.3f}", width=6, foreground='#1976D2', font=('Microsoft YaHei', 9, 'bold'))
            value_label.grid(row=0, column=2, sticky=tk.E, padx=(5, 0))
            
            # 激活勾选框（数值右侧）
            active_var = tk.BooleanVar(value=True)
            active_check = ttk.Checkbutton(frame, text="启用", variable=active_var, width=5)
            active_check.grid(row=0, column=3, sticky=tk.W, padx=(5, 0))
            
            # 勾选框状态变化时更新滑块可用状态
            def toggle_active(*args):
                if active_var.get():
                    scale.config(state='normal', bg='#f5f5f5', troughcolor='#888888', activebackground='#1976D2')
                    value_label.config(foreground='#1976D2')
                else:
                    scale.config(state='disabled', bg='#e0e0e0', troughcolor='#cccccc', activebackground='#cccccc')
                    value_label.config(foreground='#999999')
            active_var.trace_add('write', toggle_active)
            
            # 更新数值显示
            def update_value(*args):
                value_label.config(text=f"{var.get():.3f}")
            var.trace_add('write', update_value)
            
            return scale, active_var
        
        # 创建5个滑块
        self.augment_active_vars = {}  # 存储激活状态变量
        for i, (label, key, from_, to, default) in enumerate(augment_configs):
            var = getattr(self, f'{key}_var')
            scale, active_var = create_augment_slider(right_params, label, var, from_, to, default, i)
            self.augment_active_vars[key] = active_var
        
        # 应用保存的激活状态到UI
        self.root.after(100, self._apply_saved_augment_states)

        # 3. 训练控制 (重新设计布局：6个按钮，2列3行)
        control_frame = ttk.Labelframe(left_col, text="训练控制", padding="10")
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 5))
        left_col.rowconfigure(2, weight=1)
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)

        # 第1行：检查环境 + 修复环境
        self.check_env_button = ttk.Button(control_frame, text="检查环境", command=self.check_environment, bootstyle="info")
        self.check_env_button.grid(row=0, column=0, pady=3, padx=2, sticky=(tk.W, tk.E))
        self.fix_env_button = ttk.Button(control_frame, text="修复环境", command=self.fix_environment, bootstyle="warning", state="disabled")
        self.fix_env_button.grid(row=0, column=1, pady=3, padx=2, sticky=(tk.W, tk.E))

        # 第2行：检查数据集 + 上传数据集
        self.process_dataset_button = ttk.Button(control_frame, text="检查数据集", command=self.process_dataset)
        self.process_dataset_button.grid(row=1, column=0, pady=3, padx=2, sticky=(tk.W, tk.E))
        self.upload_toggle_button = ttk.Button(control_frame, text="上传数据集", command=self.upload_dataset, bootstyle="success")
        self.upload_toggle_button.grid(row=1, column=1, pady=3, padx=2, sticky=(tk.W, tk.E))

        # 第3行：开始训练(带停止功能) + 下载模型
        self.start_training_button = ttk.Button(control_frame, text="开始训练", command=self.toggle_training, bootstyle="success")
        self.start_training_button.grid(row=2, column=0, pady=3, padx=2, sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="下载模型", command=self.download_models, bootstyle="info").grid(row=2, column=1, pady=3, padx=2, sticky=(tk.W, tk.E))

        # 初始化环境检查状态
        self.env_check_status = None  # None: 未检查, True: 正常, False: 异常
        self.env_check_fingerprint = None
        self.env_last_check_time = None

        # ==================== 右侧列 (Right Column) ====================
        # 1. 数据集路径配置
        path_frame = ttk.Labelframe(right_col, text="数据集路径配置", padding="10")
        path_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        path_frame.columnconfigure(1, weight=1)
        
        ttk.Label(path_frame, text="本地数据集:").grid(row=0, column=0, sticky=tk.E, pady=2)
        local_path_frame = ttk.Frame(path_frame)
        local_path_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        local_path_frame.columnconfigure(0, weight=1)
        
        self.local_path_var = tk.StringVar(value=self.dataset_config['local_path'])
        ttk.Entry(local_path_frame, textvariable=self.local_path_var).grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Button(local_path_frame, text="选择", command=self.select_dataset_path, width=5).grid(row=0, column=1, padx=(5, 0))
        
        ttk.Label(path_frame, text="远程路径:").grid(row=1, column=0, sticky=tk.E, pady=2)
        self.remote_path_var = tk.StringVar(value=self.dataset_config['remote_path'])
        ttk.Entry(path_frame, textvariable=self.remote_path_var).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # 3. 数据集信息
        info_frame = ttk.Labelframe(right_col, text="数据集信息", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        info_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)

        # 新增：本地/云端数据集状态显示区域
        dataset_status_frame = ttk.Frame(info_frame)
        dataset_status_frame.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(0, 10))
        dataset_status_frame.columnconfigure(0, weight=1)
        dataset_status_frame.columnconfigure(1, weight=1)

        # 统一字体
        info_font = ("Arial", 9)

        # 本地数据集信息 - 统一高度3行
        local_info_frame = ttk.Labelframe(dataset_status_frame, text="本地数据集", padding="8")
        local_info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 3))
        self.local_image_count_var = tk.StringVar(value="图片数: -")
        ttk.Label(local_info_frame, textvariable=self.local_image_count_var, font=info_font).pack(anchor=tk.W, pady=2)
        self.local_dataset_status_var = tk.StringVar(value="状态: 未检查")
        ttk.Label(local_info_frame, textvariable=self.local_dataset_status_var, font=info_font, foreground="gray").pack(anchor=tk.W, pady=2)
        ttk.Label(local_info_frame, text="", font=info_font).pack(anchor=tk.W, pady=2)  # 占位保持高度

        # 云端数据集信息 - 统一高度3行，按钮放右下角
        remote_info_frame = ttk.Labelframe(dataset_status_frame, text="云端数据集", padding="8")
        remote_info_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(3, 0))
        self.remote_image_count_var = tk.StringVar(value="图片数: -")
        ttk.Label(remote_info_frame, textvariable=self.remote_image_count_var, font=info_font).pack(anchor=tk.W, pady=2)
        self.remote_dataset_path_var = tk.StringVar(value="路径: -")
        ttk.Label(remote_info_frame, textvariable=self.remote_dataset_path_var, font=info_font, foreground="gray").pack(anchor=tk.W, pady=2)

        # 清空云端数据按钮 - 放在最后一行右侧
        ttk.Button(
            remote_info_frame,
            text="清空",
            command=self.clear_remote_dataset,
            bootstyle="danger-outline",
            width=6
        ).pack(anchor=tk.E, pady=(2, 0))

        # 原有控件行号+1
        ttk.Label(info_frame, text="数据集名称:").grid(row=1, column=0, sticky=tk.E, pady=2)
        self.dataset_name_var = tk.StringVar(value=self.dataset_config['dataset_name'])
        ttk.Entry(info_frame, textvariable=self.dataset_name_var, width=15).grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 10), pady=2)

        ttk.Label(info_frame, text="类别数量:").grid(row=1, column=2, sticky=tk.E, pady=2)
        self.num_classes_var = tk.StringVar(value=str(self.dataset_config['num_classes']))
        ttk.Entry(info_frame, textvariable=self.num_classes_var, width=10, state="readonly").grid(row=1, column=3, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)

        ttk.Label(info_frame, text="类别列表:").grid(row=2, column=0, sticky=(tk.E, tk.N), pady=2)
        self.classes_text = scrolledtext.ScrolledText(info_frame, height=2, width=40)
        self.classes_text.grid(row=2, column=1, columnspan=3, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        # 4. Dataset.yaml配置
        yaml_frame = ttk.Labelframe(right_col, text="Dataset.yaml配置", padding="10")
        yaml_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        yaml_frame.columnconfigure(1, weight=1)
        
        ttk.Label(yaml_frame, text="当前配置:").grid(row=0, column=0, sticky=(tk.E, tk.N), pady=2)
        self.yaml_config_text = scrolledtext.ScrolledText(yaml_frame, height=3, width=50)
        self.yaml_config_text.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)
        
        ttk.Label(yaml_frame, text="路径检测:").grid(row=1, column=0, sticky=(tk.E, tk.N), pady=2)
        self.path_issues_text = scrolledtext.ScrolledText(yaml_frame, height=2, width=50)
        self.path_issues_text.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(5, 0), pady=2)

        # 5. 操作进度提示 (放在右侧列的最下方)
        status_info_frame = ttk.Frame(right_col)
        status_info_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        status_info_frame.columnconfigure(0, weight=1)
        right_col.rowconfigure(4, weight=1) # 让它占据剩余空间
        
        self.upload_status_var = tk.StringVar(value="准备就绪")
        self.dataset_check_status_var = tk.StringVar(value="检查状态: 未检查")
        self.dataset_summary_var = tk.StringVar(value="检查总结: 未生成")
        self.upload_progress_var = tk.DoubleVar()
        
        ttk.Label(status_info_frame, text="操作进度提示:", font=("Arial", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        ttk.Label(status_info_frame, textvariable=self.upload_status_var, wraplength=400).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=2)
        ttk.Label(status_info_frame, textvariable=self.dataset_check_status_var, wraplength=400).grid(row=2, column=0, sticky=(tk.W, tk.E), pady=2)
        ttk.Label(status_info_frame, textvariable=self.dataset_summary_var, wraplength=400).grid(row=3, column=0, sticky=(tk.W, tk.E), pady=2)
        
        self.upload_progress_bar = ttk.Progressbar(status_info_frame, variable=self.upload_progress_var, maximum=100)
        self.upload_progress_bar.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=5)

        # ==================== 底部区域 (Bottom Area) ====================
        # (上传进度已移至上方控制区，此处只保留系统监控和日志)
        monitor_log_frame = ttk.Frame(bottom_area)
        monitor_log_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        monitor_log_frame.columnconfigure(0, weight=3, minsize=260)
        monitor_log_frame.columnconfigure(1, weight=7, minsize=600)
        monitor_log_frame.rowconfigure(0, weight=1)

        monitor_frame = ttk.Labelframe(monitor_log_frame, text="系统监控", padding="5")
        monitor_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.columnconfigure(1, weight=1)
        monitor_frame.rowconfigure(0, weight=1)
        monitor_frame.rowconfigure(1, weight=1)

        self.gpu_utilization_frame = ttk.Labelframe(monitor_frame, text="GPU利用率", padding="3")
        self.gpu_utilization_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3), padx=(0, 3))

        self.gpu_memory_frame = ttk.Labelframe(monitor_frame, text="GPU显存使用率", padding="3")
        self.gpu_memory_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3), padx=(3, 0))

        self.loss_frame = ttk.Labelframe(monitor_frame, text="Loss曲线", padding="3")
        self.loss_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(3, 0), padx=(0, 0))

        # 训练状态信息（从训练状态容器移入）
        self.training_info_frame = ttk.Frame(monitor_frame)
        self.training_info_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        self.training_info_frame.columnconfigure(0, weight=0)  # 状态 - 不扩展
        self.training_info_frame.columnconfigure(1, weight=0)  # 时长 - 不扩展
        self.training_info_frame.columnconfigure(2, weight=0)  # 预计完成 - 不扩展
        self.training_info_frame.columnconfigure(3, weight=1)  # 按钮 - 靠右

        # 训练中进度
        if not hasattr(self, "training_status_var"):
            self.training_status_var = tk.StringVar(value="未开始")
        ttk.Label(self.training_info_frame, textvariable=self.training_status_var, font=("Arial", 10, "bold"), foreground="#007bff").grid(row=0, column=0, sticky=tk.W, padx=5)

        # 训练时长
        self.status_duration_var = tk.StringVar(value="时长: 00:00:00")
        ttk.Label(self.training_info_frame, textvariable=self.status_duration_var, font=("Arial", 10)).grid(row=0, column=1, sticky=tk.W, padx=5)

        # 预计完成时间
        self.status_eta_var = tk.StringVar(value="预计完成: --")
        ttk.Label(self.training_info_frame, textvariable=self.status_eta_var, font=("Arial", 10)).grid(row=0, column=2, sticky=tk.W, padx=5)

        # 监控大屏按钮
        ttk.Button(
            self.training_info_frame,
            text="监控大屏",
            command=self.open_monitor_fullscreen,
            bootstyle="info",
            width=10
        ).grid(row=0, column=3, sticky=tk.E, padx=5)

        # 保留 self.current_epoch_var 引用以防其他地方报错
        self.current_epoch_var = tk.StringVar(value="Epoch: 0/0")

        self.init_monitoring_charts()

        log_frame = ttk.Labelframe(monitor_log_frame, text="训练日志", padding="10")
        log_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=60, font=('Consolas', 10))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

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
        control_frame = ttk.Labelframe(top_frame, text="训练控制", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
        
        # 控制按钮布局为2x2
        ttk.Button(control_frame, text="下载模型", command=self.download_models).grid(row=0, column=0, pady=2, padx=(0, 5), sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="删除模型", command=self.delete_models).grid(row=0, column=1, pady=2, padx=(5, 0), sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="开始监控", command=self.start_monitoring).grid(row=1, column=0, pady=2, padx=(0, 5), sticky=(tk.W, tk.E))
        ttk.Button(control_frame, text="停止监控", command=self.stop_monitoring).grid(row=1, column=1, pady=2, padx=(5, 0), sticky=(tk.W, tk.E))
        
        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        
        # 训练状态框架
        status_frame = ttk.Labelframe(top_frame, text="训练状态", padding="10")
        status_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(5, 0))
        
        if not hasattr(self, "training_status_var"):
            self.training_status_var = tk.StringVar(value="未开始")
        status_label = ttk.Label(status_frame, textvariable=self.training_status_var, font=("Arial", 12, "bold"))
        status_label.grid(row=0, column=0, pady=5)
        
        # 训练进度条
        self.training_progress_var = tk.DoubleVar()
        self.training_progress_bar = ttk.Progressbar(status_frame, variable=self.training_progress_var, maximum=100)
        self.training_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 当前epoch显示
        if not hasattr(self, "current_epoch_var"):
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
        monitor_container = ttk.Frame(main_content_frame)
        monitor_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        monitor_container.columnconfigure(0, weight=1)
        monitor_container.rowconfigure(1, weight=1)

        # 标题栏
        monitor_header = ttk.Frame(monitor_container)
        monitor_header.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Label(monitor_header, text="系统监控", font=("Arial", 10, "bold")).pack(side='left')

        monitor_frame = ttk.Labelframe(monitor_container, text="", padding="5")
        monitor_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        monitor_frame.columnconfigure(0, weight=1)
        monitor_frame.columnconfigure(1, weight=1)
        monitor_frame.rowconfigure(0, weight=1)
        monitor_frame.rowconfigure(1, weight=1)

        # GPU利用率监控
        self.gpu_utilization_frame = ttk.Labelframe(monitor_frame, text="GPU利用率", padding="3")
        self.gpu_utilization_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3), padx=(0, 3))

        # GPU显存监控
        self.gpu_memory_frame = ttk.Labelframe(monitor_frame, text="GPU显存使用率", padding="3")
        self.gpu_memory_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 3), padx=(3, 0))

        self.loss_frame = ttk.Labelframe(monitor_frame, text="Loss曲线", padding="3")
        self.loss_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(3, 0), padx=(0, 0))
        
        # 初始化监控图表占位符
        self.init_monitoring_charts()
        
        # 右侧：日志显示框架
        log_frame = ttk.Labelframe(main_content_frame, text="训练日志", padding="10")
        log_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=25, width=60, font=('Consolas', 10))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self._bind_persistence()
    
    # 移除或注释掉无用的状态栏相关代码
    # def setup_status_bar(self, parent):
    #     ...
    # def update_time(self):
    #     ...
    
    def load_config(self):
        try:
            cfg = None
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            if not isinstance(cfg, dict):
                cfg = {}
            self.server_config.update(cfg.get('server', {}))
            runtime_mode = self.server_config.get('runtime_mode', self.default_runtime_mode)
            if runtime_mode not in self.valid_runtime_modes:
                runtime_mode = self.default_runtime_mode
            self.server_config['runtime_mode'] = runtime_mode
            self.dataset_config.update(cfg.get('dataset', {}))
            self.training_config.update(cfg.get('training', {}))
            upload_cfg = cfg.get('upload', {})
            deploy_cfg = cfg.get('deploy_docker', {})
            self.deploy_docker_config.update(deploy_cfg)
            self.config = {
                'server': self.server_config,
                'dataset': self.dataset_config,
                'training': self.training_config,
                'deploy_docker': self.deploy_docker_config,
                'upload': {
                    'max_workers': upload_cfg.get('max_workers', 8),
                    'retry_times': upload_cfg.get('retry_times', 3)
                }
            }
            return {
                'server': dict(self.server_config),
                'dataset': dict(self.dataset_config),
                'training': dict(self.training_config),
                'deploy_docker': dict(self.config['deploy_docker']),
                'upload': dict(self.config['upload'])
            }
        except Exception as e:
            self.log_message(f"加载配置失败: {e}")
            return {
                'server': dict(self.server_config),
                'dataset': dict(self.dataset_config),
                'training': dict(self.training_config),
                'deploy_docker': dict(self.config['deploy_docker']),
                'upload': dict(self.config['upload'])
            }
    
    def save_config(self, cfg=None):
        try:
            if isinstance(cfg, dict):
                if 'server' in cfg:
                    self.server_config.update(cfg['server'])
                    runtime_mode = self.server_config.get('runtime_mode', self.default_runtime_mode)
                    if runtime_mode not in self.valid_runtime_modes:
                        runtime_mode = self.default_runtime_mode
                    self.server_config['runtime_mode'] = runtime_mode
                if 'dataset' in cfg:
                    self.dataset_config.update(cfg['dataset'])
                if 'training' in cfg:
                    self.training_config.update(cfg['training'])
                if 'deploy_docker' in cfg:
                    self.config['deploy_docker'] = {
                        'image_repo': cfg['deploy_docker'].get('image_repo', self.config['deploy_docker']['image_repo']),
                        'image_tag': cfg['deploy_docker'].get('image_tag', self.config['deploy_docker']['image_tag']),
                        'container_name': cfg['deploy_docker'].get('container_name', self.config['deploy_docker']['container_name']),
                        'remote_deploy_dir': cfg['deploy_docker'].get('remote_deploy_dir', self.config['deploy_docker']['remote_deploy_dir']),
                        'host_workspace_dir': cfg['deploy_docker'].get('host_workspace_dir', self.config['deploy_docker']['host_workspace_dir']),
                        'enable_gpu': bool(cfg['deploy_docker'].get('enable_gpu', self.config['deploy_docker']['enable_gpu'])),
                        'last_status': cfg['deploy_docker'].get('last_status', self.config['deploy_docker']['last_status']),
                        'last_deploy_time': cfg['deploy_docker'].get('last_deploy_time', self.config['deploy_docker']['last_deploy_time'])
                    }
                if 'upload' in cfg:
                    self.config['upload'] = {
                        'max_workers': cfg['upload'].get('max_workers', self.config['upload']['max_workers']),
                        'retry_times': cfg['upload'].get('retry_times', self.config['upload']['retry_times'])
                    }
            out = {
                'server': self.server_config,
                'dataset': self.dataset_config,
                'training': self.training_config,
                'deploy_docker': self.config['deploy_docker'],
                'upload': self.config['upload']
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            self.log_message("配置已保存")
        except Exception as e:
            self.log_message(f"保存配置失败: {e}")
    
    def _bind_text_persistence(self, widget, section, key):
        def on_modified(event):
            try:
                widget.edit_modified(False)
                text = widget.get('1.0', 'end').strip()
                if section == 'dataset' and key == 'classes':
                    lines = [x.strip() for x in text.replace(',', '\n').splitlines() if x.strip()]
                    self.save_config({'dataset': {'classes': lines, 'num_classes': len(lines)}})
                else:
                    self.save_config({section: {key: text}})
            except:
                pass
        widget.bind('<<Modified>>', on_modified)
    
    def _bind_persistence(self):
        if self._persistence_bound:
            return
        self._persistence_bound = True

        def bind(var, section, key, t='str'):
            def cb(*_):
                try:
                    val = var.get()
                    if t == 'int':
                        val = int(str(val).strip() or '0')
                    elif t == 'float':
                        val = float(str(val).strip() or '0')
                    else:
                        val = str(val).strip()
                    self.save_config({section: {key: val}})
                except:
                    pass
            try:
                var.trace_add('write', cb)
            except:
                try:
                    var.trace('w', cb)
                except:
                    pass
        
        if hasattr(self, 'hostname_var'):
            bind(self.hostname_var, 'server', 'hostname')
        if hasattr(self, 'port_var'):
            bind(self.port_var, 'server', 'port', 'int')
        if hasattr(self, 'username_var'):
            bind(self.username_var, 'server', 'username')
        if hasattr(self, 'password_var'):
            bind(self.password_var, 'server', 'password')
        if hasattr(self, 'key_file_var'):
            bind(self.key_file_var, 'server', 'key_file')
        if hasattr(self, 'runtime_mode_var'):
            bind(self.runtime_mode_var, 'server', 'runtime_mode')
            def _runtime_mode_changed(*_):
                try:
                    runtime_mode = self._normalize_runtime_mode(self.runtime_mode_var.get())
                    self.server_config['runtime_mode'] = runtime_mode
                    profile = self._get_runtime_profile(runtime_mode)
                    if hasattr(self, "username_var"):
                        self.username_var.set(profile["default_username"])
                    self.save_config({'server': {'runtime_mode': runtime_mode, 'username': profile["default_username"]}})
                    self._refresh_docker_deploy_controls()
                except Exception:
                    pass
            try:
                self.runtime_mode_var.trace_add('write', _runtime_mode_changed)
            except Exception:
                try:
                    self.runtime_mode_var.trace('w', _runtime_mode_changed)
                except Exception:
                    pass
        
        if hasattr(self, 'local_path_var'):
            bind(self.local_path_var, 'dataset', 'local_path')
            def _local_path_changed(*_):
                self.dataset_check_passed = False
                self.remote_verify_passed = False
                self.last_dataset_fingerprint = ""
                self.last_dataset_check_time = ""
                self.update_action_button_states()
            try:
                self.local_path_var.trace_add('write', _local_path_changed)
            except Exception:
                try:
                    self.local_path_var.trace('w', _local_path_changed)
                except Exception:
                    pass
        if hasattr(self, 'remote_path_var'):
            bind(self.remote_path_var, 'dataset', 'remote_path')
            def _remote_path_changed(*_):
                self.remote_verify_passed = False
                self.last_upload_plan = None
                self.update_action_button_states()
            try:
                self.remote_path_var.trace_add('write', _remote_path_changed)
            except Exception:
                try:
                    self.remote_path_var.trace('w', _remote_path_changed)
                except Exception:
                    pass
        if hasattr(self, 'dataset_name_var'):
            bind(self.dataset_name_var, 'dataset', 'dataset_name')
        if hasattr(self, 'num_classes_var'):
            bind(self.num_classes_var, 'dataset', 'num_classes', 'int')
        if hasattr(self, 'classes_text'):
            self._bind_text_persistence(self.classes_text, 'dataset', 'classes')
        
        if hasattr(self, 'epochs_var'):
            bind(self.epochs_var, 'training', 'epochs', 'int')
        if hasattr(self, 'batch_size_var'):
            bind(self.batch_size_var, 'training', 'batch_size', 'int')
        if hasattr(self, 'learning_rate_var'):
            bind(self.learning_rate_var, 'training', 'learning_rate', 'float')
        if hasattr(self, 'image_size_var'):
            bind(self.image_size_var, 'training', 'image_size', 'int')
            def _image_size_changed(*_):
                self.apply_auto_recommended_training_params("分辨率")
            try:
                self.image_size_var.trace_add('write', _image_size_changed)
            except Exception:
                try:
                    self.image_size_var.trace('w', _image_size_changed)
                except Exception:
                    pass
        if hasattr(self, 'base_model_var'):
            bind(self.base_model_var, 'training', 'base_model')
            def _base_model_changed(*_):
                self.apply_auto_recommended_training_params("基础模型")
            try:
                self.base_model_var.trace_add('write', _base_model_changed)
            except Exception:
                try:
                    self.base_model_var.trace('w', _base_model_changed)
                except Exception:
                    pass
        if hasattr(self, 'model_name_suffix_var'):
            bind(self.model_name_suffix_var, 'training', 'model_name_suffix')

    def _on_app_close(self):
        try:
            self.update_all_configs()
            self.save_config()
        except Exception:
            pass
        self.root.destroy()
    
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
            self.invalidate_dataset_pipeline("数据集路径已变更，请重新检查后再上传")
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

                # 连接门禁：按服务器种类校验 Ubuntu 主版本
                runtime_mode = self._normalize_runtime_mode(self.server_config.get("runtime_mode"))
                profile = self._get_runtime_profile(runtime_mode)
                expected_ubuntu = profile["expected_ubuntu"]
                stdin, stdout, stderr = ssh.exec_command("source /etc/os-release >/dev/null 2>&1 && echo ${VERSION_ID:-unknown}")
                detected_version = stdout.read().decode("utf-8", "ignore").strip().strip('"')
                if not detected_version.startswith(expected_ubuntu):
                    raise Exception(
                        f"系统版本不匹配: 当前 {detected_version or 'unknown'}，"
                        f"需 Ubuntu {expected_ubuntu}（服务器种类: {runtime_mode}）"
                    )
                
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
        self.start_system_monitoring()
        self.update_action_button_states()
        # 更新数据集状态显示
        self.update_dataset_status_display()
    
    def connection_test_failed(self, error):
        """连接测试失败"""
        self.is_connected = False
        self.connection_status_var.set(f"连接失败: {error}")
        self.connection_status_label.config(foreground="red")
        self.log_message(f"服务器连接测试失败: {error}")
        self.update_action_button_states()
    
    def update_all_configs(self, collect_errors=False):
        """统一从界面读取最新的所有配置并保存"""
        errors = []
        # 1. 更新服务器配置
        self.server_config['hostname'] = self.hostname_var.get().strip()
        try:
            self.server_config['port'] = int(self.port_var.get().strip())
        except ValueError:
            if collect_errors:
                errors.append("服务器端口必须是整数")
        self.server_config['username'] = self.username_var.get().strip()
        self.server_config['password'] = self.password_var.get()
        self.server_config['key_file'] = self.key_file_var.get().strip()
        if hasattr(self, 'runtime_mode_var'):
            self.server_config['runtime_mode'] = self._normalize_runtime_mode(self.runtime_mode_var.get())
        else:
            self.server_config['runtime_mode'] = self._normalize_runtime_mode(self.server_config.get('runtime_mode'))

        # 2. 更新数据集配置
        self.dataset_config['local_path'] = self.local_path_var.get().strip()
        self.dataset_config['remote_path'] = self.remote_path_var.get().strip()
        self.dataset_config['dataset_name'] = self.dataset_name_var.get().strip()
        # num_classes 是自动读取的，不需要手动更新回去

        # 3. 更新训练参数配置（逐项更新，单项失败不影响其它项）
        try:
            self.training_config['epochs'] = int(self.epochs_var.get().strip())
        except ValueError:
            if collect_errors:
                errors.append("训练轮次必须是整数")
        try:
            self.training_config['batch_size'] = int(self.batch_size_var.get().strip())
        except ValueError:
            if collect_errors:
                errors.append("批次大小必须是整数")
        try:
            self.training_config['learning_rate'] = float(self.learning_rate_var.get().strip())
        except ValueError:
            if collect_errors:
                errors.append("学习率必须是数字")
        try:
            self.training_config['image_size'] = int(self.image_size_var.get().strip())
        except ValueError:
            if collect_errors:
                errors.append("分辨率必须是整数")

        self.training_config['base_model'] = self.base_model_var.get().strip()
        self.training_config['model_name_suffix'] = self.model_name_suffix_var.get().strip()
        
        # 4. 更新图像增强参数（滑块值 + 激活状态）
        self.training_config['augment_scale'] = self.augment_scale_var.get()
        self.training_config['augment_fliplr'] = self.augment_fliplr_var.get()
        self.training_config['augment_hsv_h'] = self.augment_hsv_h_var.get()
        self.training_config['augment_hsv_s'] = self.augment_hsv_s_var.get()
        self.training_config['augment_hsv_v'] = self.augment_hsv_v_var.get()
        
        # 5. 更新图像增强激活状态
        self.training_config['augment_scale_active'] = self.augment_active_vars['augment_scale'].get()
        self.training_config['augment_fliplr_active'] = self.augment_active_vars['augment_fliplr'].get()
        self.training_config['augment_hsv_h_active'] = self.augment_active_vars['augment_hsv_h'].get()
        self.training_config['augment_hsv_s_active'] = self.augment_active_vars['augment_hsv_s'].get()
        self.training_config['augment_hsv_v_active'] = self.augment_active_vars['augment_hsv_v'].get()
        
        return errors

    def update_server_config(self):
        """更新服务器配置（向前兼容）"""
        self.update_all_configs()
    
    def save_server_config(self):
        """保存所有配置"""
        self.update_all_configs()
        self.save_config()
        messagebox.showinfo("成功", "所有配置已保存")
    
    def get_server_info(self):
        """打开服务器文件管理器"""
        self.open_server_file_explorer()
    
    def open_server_file_explorer(self):
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        try:
            self.update_server_config()
            win = tk.Toplevel(self.root)
            win.title("服务器文件管理器")
            win.geometry("950x620")
            win.transient(self.root)

            top = ttk.Frame(win, padding="8")
            top.pack(fill='x')
            current_path_var = tk.StringVar(value="/root")
            ttk.Label(top, text="当前路径:").pack(side='left')
            ttk.Entry(top, textvariable=current_path_var).pack(side='left', fill='x', expand=True, padx=6)

            tree_frame = ttk.Frame(win, padding=(8, 0, 8, 8))
            tree_frame.pack(fill='both', expand=True)
            columns = ('type', 'size', 'permissions', 'date')
            file_tree = ttk.Treeview(tree_frame, columns=columns, show='tree headings')
            file_tree.heading('#0', text='名称')
            file_tree.heading('type', text='类型')
            file_tree.heading('size', text='大小')
            file_tree.heading('permissions', text='权限')
            file_tree.heading('date', text='修改时间')
            file_tree.column('#0', width=320)
            file_tree.column('type', width=80, anchor='center')
            file_tree.column('size', width=100, anchor='e')
            file_tree.column('permissions', width=120, anchor='center')
            file_tree.column('date', width=150, anchor='center')
            tree_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=file_tree.yview)
            file_tree.configure(yscrollcommand=tree_scrollbar.set)
            file_tree.pack(side='left', fill='both', expand=True)
            tree_scrollbar.pack(side='right', fill='y')

            nav = ttk.Frame(win, padding=(8, 0, 8, 8))
            nav.pack(fill='x')

            def format_size(size_str):
                try:
                    size = int(size_str)
                    if size < 1024:
                        return f"{size} B"
                    if size < 1024 * 1024:
                        return f"{size / 1024:.1f} KB"
                    if size < 1024 * 1024 * 1024:
                        return f"{size / (1024 * 1024):.1f} MB"
                    return f"{size / (1024 * 1024 * 1024):.1f} GB"
                except Exception as e:
                    return size_str

            def load_directory(path):
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
                    stdin, stdout, stderr = ssh.exec_command(f'ls -la "{path}"')
                    output = stdout.read().decode('utf-8', errors='ignore')
                    err = stderr.read().decode('utf-8', errors='ignore')
                    ssh.close()
                    if err and not output:
                        messagebox.showerror("错误", f"读取目录失败: {err}")
                        return
                    for item in file_tree.get_children():
                        file_tree.delete(item)
                    current_path_var.set(path)
                    lines = output.strip().split('\n')
                    if lines and lines[0].startswith('total'):
                        lines = lines[1:]
                    if path not in ["/", "/root"]:
                        file_tree.insert('', 'end', text="..", values=("目录", "", "", ""))
                    import re
                    for line in lines:
                        m = re.match(r'^(\S+)\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\S+\s+\d+\s+\S+)\s+(.+)$', line)
                        if not m:
                            continue
                        permissions = m.group(1)
                        size = m.group(2)
                        date = m.group(3)
                        name = m.group(4)
                        if name in ['.', '..']:
                            continue
                        file_type = "目录" if permissions.startswith('d') else "文件"
                        file_tree.insert('', 'end', text=name, values=(file_type, format_size(size), permissions, date))
                except Exception as e:
                    messagebox.showerror("错误", f"加载目录失败: {str(e)}")

            def navigate_up():
                cur = current_path_var.get().strip() or "/root"
                if cur in ["/", "/root"]:
                    load_directory("/root")
                    return
                parent = os.path.dirname(cur.rstrip('/')) or "/root"
                load_directory(parent)

            def open_path():
                p = current_path_var.get().strip() or "/root"
                load_directory(p)

            def on_double_click(event):
                item = file_tree.identify_row(event.y)
                if not item:
                    return
                name = file_tree.item(item, 'text')
                ftype = file_tree.set(item, 'type')
                if name == "..":
                    navigate_up()
                    return
                if ftype == "目录":
                    cur = current_path_var.get().rstrip('/')
                    if not cur:
                        cur = "/root"
                    nxt = f"{cur}/{name}".replace('//', '/')
                    load_directory(nxt)

            file_tree.bind('<Double-1>', on_double_click)
            ttk.Button(nav, text="上级目录", command=navigate_up).pack(side='left')
            ttk.Button(nav, text="打开路径", command=open_path).pack(side='left', padx=6)
            ttk.Button(nav, text="刷新", command=lambda: load_directory(current_path_var.get())).pack(side='left')
            load_directory("/root")
        except Exception as e:
            messagebox.showerror("错误", f"打开文件管理器失败: {str(e)}")
    
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
            category_frame = ttk.Labelframe(scrollable_frame, text=category_name, padding=10)
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
    
    def process_dataset(self):
        try:
            dataset_path = self.local_path_var.get()
            if not dataset_path or not os.path.exists(dataset_path):
                messagebox.showerror("错误", "请选择有效的数据集路径")
                return

            self.dataset_check_passed = False
            self.remote_verify_passed = False
            self.update_action_button_states()
            self.log_message("开始检查数据集...")
            started_at = time.time()
            if hasattr(self, 'upload_status_var'):
                self.upload_status_var.set("检查中: 正在分析本地数据集...")
            if hasattr(self, 'dataset_summary_var'):
                self.dataset_summary_var.set("检查总结: 检查进行中...")
            self.analyze_dataset()

            def _process_task():
                def _live(msg):
                    if hasattr(self, 'upload_status_var'):
                        self.root.after(0, lambda m=msg: self.upload_status_var.set(m))
                try:
                    _live("本地检查中: 正在校验标签和目录结构...")
                    result = self.validate_local_dataset(dataset_path, progress_cb=_live)
                    if result.get('passed'):
                        _live("本地检查通过，正在检查云端差异...")
                        remote_path = self.remote_path_var.get().strip().replace('\\', '/').rstrip('/')
                        result['remote_diff'] = self.quick_compare_remote_dataset(dataset_path, remote_path, progress_cb=_live)
                    result['check_elapsed_sec'] = time.time() - started_at
                    self.root.after(0, lambda r=result: self.apply_local_check_result(r))
                except Exception as e:
                    self.root.after(0, lambda err=str(e): self.log_message(f"处理数据集失败: {err}"))
                    self.root.after(0, lambda err=str(e): messagebox.showerror("错误", f"处理数据集失败: {err}"))

            threading.Thread(target=_process_task, daemon=True).start()
            
        except Exception as e:
            self.log_message(f"启动处理任务失败: {e}")
            messagebox.showerror("错误", f"启动处理任务失败: {e}")

    def validate_local_dataset(self, dataset_path, max_errors=120, progress_cb=None):
        result = {
            'passed': False,
            'errors': [],
            'warnings': [],
            'summary': {},
            'fingerprint': ''
        }

        def add_error(msg):
            if len(result['errors']) < max_errors:
                result['errors'].append(msg)

        def add_warning(msg):
            if len(result['warnings']) < max_errors:
                result['warnings'].append(msg)

        yaml_file = os.path.join(dataset_path, 'dataset.yaml')
        if not os.path.exists(yaml_file):
            add_error("未找到 dataset.yaml")
            return result

        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                yaml_data = yaml.safe_load(f) or {}
        except Exception as e:
            add_error(f"dataset.yaml 读取失败: {e}")
            return result

        names = self._normalize_name_list(yaml_data.get('names'))
        nc_raw = yaml_data.get('nc')
        nc = None
        try:
            if nc_raw is not None:
                nc = int(nc_raw)
        except Exception:
            add_error(f"nc 非法: {nc_raw}")
        if nc is None and names:
            nc = len(names)
        if nc is None:
            add_error("dataset.yaml 缺少有效的 nc")
            nc = 0
        if names and len(names) != nc:
            add_error(f"names 数量({len(names)})与 nc({nc})不一致")

        image_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        split_stats = {}
        class_counter = {}
        total_labels = 0
        total_images = 0
        scanned_label_files = 0

        for split in ['train', 'val', 'test']:
            img_dir = os.path.join(dataset_path, split, 'images')
            lbl_dir = os.path.join(dataset_path, split, 'labels')
            if not os.path.isdir(img_dir) and not os.path.isdir(lbl_dir):
                continue
            if not os.path.isdir(img_dir):
                add_error(f"{split}/images 目录缺失")
                continue
            if not os.path.isdir(lbl_dir):
                add_error(f"{split}/labels 目录缺失")
                continue

            image_bases = set()
            label_bases = set()

            for fn in os.listdir(img_dir):
                if os.path.splitext(fn)[1].lower() in image_exts:
                    image_bases.add(os.path.splitext(fn)[0])
            for fn in os.listdir(lbl_dir):
                if fn.lower().endswith('.txt'):
                    label_bases.add(os.path.splitext(fn)[0])

            missing_labels = sorted(image_bases - label_bases)
            orphan_labels = sorted(label_bases - image_bases)
            if missing_labels:
                add_warning(f"{split} 有 {len(missing_labels)} 张图片缺少标签")
            if orphan_labels:
                add_error(f"{split} 有 {len(orphan_labels)} 个标签无对应图片")

            total_images += len(image_bases)
            total_labels += len(label_bases)
            split_stats[split] = {'images': len(image_bases), 'labels': len(label_bases)}
            if callable(progress_cb):
                progress_cb(f"本地检查中: {split} images={len(image_bases)} labels={len(label_bases)}")

            for base in sorted(label_bases):
                label_file = os.path.join(lbl_dir, f"{base}.txt")
                try:
                    with open(label_file, 'r', encoding='utf-8', errors='ignore') as f:
                        for idx, line in enumerate(f, 1):
                            text = line.strip()
                            if not text:
                                continue
                            parts = text.split()
                            if len(parts) != 5:
                                add_error(f"{split}/labels/{base}.txt 第{idx}行 列数不是5")
                                continue
                            try:
                                cls_raw = float(parts[0])
                                cls_id = int(cls_raw)
                                if cls_id != cls_raw:
                                    raise ValueError("not int")
                            except Exception:
                                add_error(f"{split}/labels/{base}.txt 第{idx}行 class_id 非整数")
                                continue
                            if cls_id < 0 or cls_id >= nc:
                                add_error(f"{split}/labels/{base}.txt 第{idx}行 class_id 越界(0..{max(nc - 1, 0)})")
                                continue
                            try:
                                x, y, w, h = map(float, parts[1:])
                            except Exception:
                                add_error(f"{split}/labels/{base}.txt 第{idx}行 bbox 非法")
                                continue
                            if w <= 0 or h <= 0:
                                add_error(f"{split}/labels/{base}.txt 第{idx}行 w/h 必须大于0")
                                continue
                            if not (0 <= x <= 1 and 0 <= y <= 1 and 0 <= w <= 1 and 0 <= h <= 1):
                                add_error(f"{split}/labels/{base}.txt 第{idx}行 bbox 超出0..1")
                                continue
                            class_counter[cls_id] = class_counter.get(cls_id, 0) + 1
                except Exception as e:
                    add_error(f"{split}/labels/{base}.txt 读取失败: {e}")
                scanned_label_files += 1
                if callable(progress_cb) and scanned_label_files % 200 == 0:
                    progress_cb(f"本地检查中: 已扫描标签文件 {scanned_label_files}")

        result['summary'] = {
            'nc': nc,
            'names': names,
            'splits': split_stats,
            'total_images': total_images,
            'total_labels': total_labels,
            'class_counter': class_counter
        }
        result['fingerprint'] = self._build_dataset_fingerprint(dataset_path)
        result['passed'] = len(result['errors']) == 0
        return result

    def apply_local_check_result(self, result):
        self.path_issues_text.delete(1.0, tk.END)
        if result.get('errors'):
            self.path_issues_text.insert(tk.END, "🔴 检查失败:\n")
            for msg in result['errors']:
                self.path_issues_text.insert(tk.END, f"• {msg}\n")
            if result.get('warnings'):
                self.path_issues_text.insert(tk.END, "\n🟡 警告:\n")
                for msg in result['warnings']:
                    self.path_issues_text.insert(tk.END, f"• {msg}\n")
            self.dataset_check_passed = False
            self.remote_verify_passed = False
            self.last_dataset_fingerprint = ""
            self.last_dataset_check_time = ""
            if hasattr(self, 'dataset_check_status_var'):
                self.dataset_check_status_var.set("检查状态: 失败")
            if hasattr(self, 'dataset_summary_var'):
                elapsed = float(result.get('check_elapsed_sec', 0) or 0)
                self.dataset_summary_var.set(
                    f"检查总结: 失败，错误{len(result.get('errors', []))}，警告{len(result.get('warnings', []))}，耗时{elapsed:.1f}s"
                )
            self.update_action_button_states()
            self.log_message("数据集检查失败，请修复后再上传")
            messagebox.showerror("检查失败", "数据集检查未通过，已阻止上传")
            return

        summary = result.get('summary', {})
        names = summary.get('names', [])
        nc = summary.get('nc', 0)
        self.num_classes_var.set(str(nc))
        self.dataset_config['num_classes'] = nc
        self.dataset_config['classes'] = names
        self.classes_text.delete(1.0, tk.END)
        for i, name in enumerate(names):
            self.classes_text.insert(tk.END, f"{i}: {name}\n")

        self.path_issues_text.insert(tk.END, "✅ 数据集检查通过\n")
        splits = summary.get('splits', {})
        for split in ['train', 'val', 'test']:
            if split in splits:
                info = splits[split]
                self.path_issues_text.insert(tk.END, f"• {split}: images={info['images']} labels={info['labels']}\n")
        if result.get('warnings'):
            self.path_issues_text.insert(tk.END, "\n🟡 警告:\n")
            for msg in result['warnings']:
                self.path_issues_text.insert(tk.END, f"• {msg}\n")

        remote_diff = result.get('remote_diff') or {}
        self.last_upload_plan = None
        if remote_diff.get('ok'):
            need_upload = int(remote_diff.get('need_upload', 0))
            skip_count = int(remote_diff.get('skip_count', 0))
            expected_total = int(remote_diff.get('expected_total', 0))
            self.last_upload_plan = {
                'fingerprint': result.get('fingerprint', ''),
                'remote_path': self.remote_path_var.get().replace('\\', '/').rstrip('/'),
                'todo_rel_paths': list(remote_diff.get('todo_rel_paths') or []),
                'expected_total': expected_total,
                'skip_count': skip_count,
                'checked_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            self.path_issues_text.insert(
                tk.END,
                f"\n☁️ 云端差异检查: 需上传 {need_upload}，已同步可跳过 {skip_count}，总计 {expected_total}\n"
            )
            self.log_message(f"云端差异检查完成：需上传{need_upload}，可跳过{skip_count}")
        else:
            msg = remote_diff.get('msg', '').strip()
            if msg:
                self.path_issues_text.insert(tk.END, f"\n☁️ 云端差异检查: {msg}\n")
                self.log_message(f"云端差异检查跳过/失败: {msg}")

        summary_text = self._build_check_summary_text(result)
        if hasattr(self, 'dataset_summary_var'):
            self.dataset_summary_var.set(f"检查总结: {summary_text}")
        self.log_message(f"检查总结: {summary_text}")
        self.path_issues_text.insert(tk.END, f"\n📌 检查总结: {summary_text}\n")

        self.dataset_check_passed = True
        auto_remote_passed = bool(remote_diff.get('ok')) and int(remote_diff.get('need_upload', -1)) == 0
        self.remote_verify_passed = auto_remote_passed
        self.last_dataset_fingerprint = result.get('fingerprint', '')
        self.last_dataset_check_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(self, 'dataset_check_status_var'):
            self.dataset_check_status_var.set(f"检查状态: 已通过 ({self.last_dataset_check_time})")
        self.update_action_button_states()
        if auto_remote_passed:
            self.log_message(f"数据集检查通过 ({self.last_dataset_check_time})，云端已同步，可直接开始训练")
            messagebox.showinfo("检查通过", "数据集检查通过，且云端已同步，可直接开始训练")
        else:
            self.log_message(f"数据集检查通过 ({self.last_dataset_check_time})，可开始上传")
            messagebox.showinfo("检查通过", "数据集检查通过，可上传数据集")

        # 更新数据集状态显示
        self.update_dataset_status_display()

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
            self.update_all_configs() # 确保获取最新的服务器配置
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            update_progress("连接到云端服务器...")
            
            connect_params = {
                'hostname': self.server_config['hostname'],
                'port': self.server_config['port'],
                'username': self.server_config['username'],
                'timeout': 15
            }
            if self.server_config['key_file']:
                connect_params['key_filename'] = self.server_config['key_file']
            elif self.server_config['password']:
                connect_params['password'] = self.server_config['password']
                
            ssh.connect(**connect_params)
            
            dataset_name = self.dataset_config['dataset_name']
            remote_path = self.dataset_config['remote_path'] # 使用用户配置的远程路径
            
            # 检查云端目录结构
            update_progress("检查云端目录结构...")
            stdin, stdout, stderr = ssh.exec_command(f"ls -la {remote_path}")
            ls_output = stdout.read().decode()
            
            # 检查是否需要重组
            if "train" not in ls_output or "val" not in ls_output:
                update_progress("云端目录结构需要重组...")
                
                # 创建修复脚本，移除耗时巨大的 cp -r 备份命令
                fix_script = f"""#!/bin/bash
# 云端数据集结构修复脚本
cd {remote_path} || exit 1

# 不再进行全量备份以节省时间和空间

# 创建标准目录结构
echo "创建标准目录结构..."
mkdir -p train/images train/labels val/images val/labels test/images test/labels

# 查找所有图片和标签文件
echo "查找文件..."
find . -maxdepth 1 -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" > /tmp/images.txt
find . -maxdepth 1 -name "*.txt" > /tmp/labels.txt

# 计算文件数量
img_count=$(wc -l < /tmp/images.txt)
if [ "$img_count" -eq 0 ]; then
    echo "未在根目录找到图片文件，跳过重组。"
    rm -f /tmp/images.txt /tmp/labels.txt
    exit 0
fi

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
                # 增加 nohup 后台执行，防止网络波动导致 SSH 会话阻塞
                stdin, stdout, stderr = ssh.exec_command("chmod +x /tmp/fix_dataset.sh && /tmp/fix_dataset.sh")
                
                # 增加超时控制读取
                import select
                channel = stdout.channel
                timeout = 60 # 设置60秒超时
                start_time = time.time()
                
                output = []
                while not channel.exit_status_ready():
                    if time.time() - start_time > timeout:
                        update_progress("脚本执行超时，但可能仍在后台运行。")
                        break
                    if channel.recv_ready():
                        output.append(channel.recv(1024).decode())
                    time.sleep(0.5)
                
                # 读取剩余输出
                if channel.recv_ready():
                    output.append(channel.recv(1024).decode())
                
                if channel.recv_stderr_ready():
                    error = channel.recv_stderr(1024).decode()
                    update_progress(f"脚本执行警告: {error}")
                
                update_progress("云端结构修复完成")
            else:
                update_progress("云端目录结构正常")
            
            ssh.close()
            
        except Exception as e:
            update_progress(f"云端结构修正失败: {e}")
            if 'ssh' in locals() and ssh:
                ssh.close()
            # 不抛出异常，允许本地修正继续进行
    
    def normalize_remote_dataset_yaml(self, ssh, python_cmd):
        """在训练前强制校正云端dataset.yaml路径，避免指向/root/datasets等错误目录"""
        remote_path = self.dataset_config.get('remote_path', '').replace('\\', '/').rstrip('/')
        if not remote_path:
            remote_path = '/root/yolo_dataset'
        remote_path = remote_path.rstrip('/')
        cmd = f"""cd /root && {python_cmd} - <<'PY'
import os
import json

# 尝试导入yaml库（支持pyyaml和ruamel.yaml）
try:
    import yaml
    def load_yaml(f):
        return yaml.safe_load(f) or {{}}
    def dump_yaml(data, f):
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
except ImportError:
    try:
        from ruamel.yaml import YAML
        ruamel_yaml = YAML()
        ruamel_yaml.preserve_quotes = True
        ruamel_yaml.allow_unicode = True
        def load_yaml(f):
            return ruamel_yaml.load(f) or {{}}
        def dump_yaml(data, f):
            ruamel_yaml.dump(data, f)
    except ImportError:
        print(json.dumps({{"ok": False, "msg": "未找到yaml库"}}, ensure_ascii=False))
        raise SystemExit(0)

remote_path = {repr(remote_path)}
yaml_file = os.path.join(remote_path, 'dataset.yaml')
result = {{"ok": False, "msg": "", "yaml_file": yaml_file}}

if not os.path.exists(yaml_file):
    result["msg"] = "dataset.yaml不存在"
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0)

with open(yaml_file, 'r', encoding='utf-8') as f:
    data = load_yaml(f)
if not isinstance(data, dict):
    data = {{}}

def first_existing(candidates):
    for rel in candidates:
        if os.path.isdir(os.path.join(remote_path, rel)):
            return rel
    return None

train_rel = first_existing(['train/images']) or 'train/images'
val_rel = first_existing(['val/images', 'valid/images']) or 'val/images'
test_rel = first_existing(['test/images'])

data['path'] = remote_path
data['train'] = train_rel
data['val'] = val_rel
if test_rel:
    data['test'] = test_rel

if 'names' in data and 'nc' not in data:
    if isinstance(data['names'], list):
        data['nc'] = len(data['names'])
    elif isinstance(data['names'], dict):
        data['nc'] = len(data['names'])

with open(yaml_file, 'w', encoding='utf-8') as f:
    dump_yaml(data, f)

result["ok"] = True
result["msg"] = "dataset.yaml已校正"
result["path"] = data.get("path")
result["train"] = data.get("train")
result["val"] = data.get("val")
result["test"] = data.get("test")
print(json.dumps(result, ensure_ascii=False))
PY"""
        stdin, stdout, stderr = ssh.exec_command(cmd)
        out = stdout.read().decode('utf-8', errors='ignore').strip()
        err = stderr.read().decode('utf-8', errors='ignore').strip()
        if err:
            self.root.after(0, lambda e=err: self.log_message(f"⚠ 远程dataset.yaml校正警告: {e[:260]}"))
        if out:
            self.root.after(0, lambda o=out: self.log_message(f"dataset.yaml校正结果: {o}"))
        try:
            obj = json.loads(out.splitlines()[-1]) if out else {}
            return bool(obj.get('ok'))
        except Exception:
            return False
    
    def generate_training_script(self):
        """生成训练脚本"""
        try:
            if not self.dataset_config['local_path']:
                messagebox.showerror("错误", "请先选择数据集路径")
                return
            
            # 更新所有配置并保存
            self.update_all_configs()
            self.save_config()
            
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
        # 确保脚本中使用的也是经过清洗的纯正 Linux 路径
        remote_path = self.dataset_config['remote_path'].replace('\\', '/').rstrip('/')
        epochs = self.training_config['epochs']
        batch_size = self.training_config['batch_size']
        learning_rate = self.training_config['learning_rate']
        image_size = self.training_config['image_size']
        base_model = self.training_config['base_model']
        model_name_suffix = self.training_config.get('model_name_suffix', '')
        # 图像增强参数
        augment_scale = self.training_config.get('augment_scale', 0.5)
        augment_fliplr = self.training_config.get('augment_fliplr', 0.5)
        augment_hsv_h = self.training_config.get('augment_hsv_h', 0.015)
        augment_hsv_s = self.training_config.get('augment_hsv_s', 0.7)
        augment_hsv_v = self.training_config.get('augment_hsv_v', 0.4)
        # 图像增强激活状态
        augment_scale_active = self.training_config.get('augment_scale_active', True)
        augment_fliplr_active = self.training_config.get('augment_fliplr_active', True)
        augment_hsv_h_active = self.training_config.get('augment_hsv_h_active', True)
        augment_hsv_s_active = self.training_config.get('augment_hsv_s_active', True)
        augment_hsv_v_active = self.training_config.get('augment_hsv_v_active', True)
        
        script_content = f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动生成的YOLO训练脚本
数据集: {dataset_name}
类别数: {num_classes}
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
训练参数: epochs={epochs}, batch={batch_size}, lr={learning_rate}
增强参数: scale={augment_scale}, fliplr={augment_fliplr}, hsv_h={augment_hsv_h}, hsv_s={augment_hsv_s}, hsv_v={augment_hsv_v}
"""

import os
import sys
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")
# 训练阶段禁止任何自动拉包（由GUI环境检查/修复阶段统一处理）
os.environ["YOLO_AUTOINSTALL"] = "0"
os.environ["ULTRALYTICS_AUTOINSTALL"] = "0"
import torch
import tensorflow as tf
import yaml
import json
import re
import zipfile
import shutil
import time
from ultralytics import YOLO
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
        if model_name.startswith("yolov11"):
            logger.warning(f"当前环境中的Ultralytics版本较旧，模型 {{model_name}} 可能不可用，自动回退为 yolov8s.pt")
            model_name = "yolov8s.pt"
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
            backup_models = ["yolov8s.pt", "yolov8n.pt", "yolov8m.pt", "yolov8l.pt"]
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
        # 构建增强参数字典（仅包含激活的增强）
        augment_kwargs = {{}}
        if {augment_scale_active}:
            augment_kwargs['scale'] = {augment_scale}
        if {augment_fliplr_active}:
            augment_kwargs['fliplr'] = {augment_fliplr}
        if {augment_hsv_h_active}:
            augment_kwargs['hsv_h'] = {augment_hsv_h}
        if {augment_hsv_s_active}:
            augment_kwargs['hsv_s'] = {augment_hsv_s}
        if {augment_hsv_v_active}:
            augment_kwargs['hsv_v'] = {augment_hsv_v}
        
        try:
            results = model.train(
            data=yaml_path,
            epochs={epochs},
            batch={batch_size},
            lr0={learning_rate},
            imgsz={image_size},
            device=device_arg,
            project='/root/runs/train',
            name='yolo_training_{timestamp}',
            save=True,
            save_period=10,
            val=True,
            plots=True,
            **augment_kwargs
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
                project='/root/runs/train',
                name='yolo_training_{timestamp}',
                save=True,
                save_period=10,
                val=True,
                plots=True,
                **augment_kwargs
            )
        
        logger.info("训练完成，开始导出模型...")
        run_dir = None
        try:
            run_dir = str(getattr(getattr(model, "trainer", None), "save_dir", ""))
        except Exception:
            run_dir = ""
        run_dir = run_dir or '/root/runs/train/yolo_training_{timestamp}'
        best_candidates = [
            os.path.join(run_dir, 'weights', 'best.pt'),
            '/root/runs/train/yolo_training_{timestamp}/weights/best.pt'
        ]
        best_pt = None
        for p in best_candidates:
            if os.path.exists(p):
                best_pt = p
                break
        if not best_pt:
            raise Exception(f"未找到best.pt，候选路径: {{best_candidates}}")
        logger.info(f"best.pt路径: {{best_pt}}")

        def sanitize_name_suffix(text):
            clean = re.sub(r'[^0-9A-Za-z_\\-一-龥]+', '_', str(text or '').strip())
            clean = re.sub(r'_+', '_', clean).strip('_-')
            return clean[:64]

        def ensure_unique_path(path):
            if not os.path.exists(path):
                return path
            base, ext = os.path.splitext(path)
            idx = 1
            while True:
                candidate = f"{{base}}_{{idx}}{{ext}}"
                if not os.path.exists(candidate):
                    return candidate
                idx += 1

        # 统一命名尾缀：命名_时间戳
        safe_suffix = sanitize_name_suffix({model_name_suffix!r})
        # 命名时间戳统一使用东八区（UTC+8）
        def cn_now():
            return datetime.now(timezone(timedelta(hours=8)))

        artifact_stamp = cn_now().strftime("%Y%m%d_%H%M%S")
        name_part = safe_suffix if safe_suffix else "model"
        artifact_tag = f"{{name_part}}_{{artifact_stamp}}"
        renamed_best = ensure_unique_path(os.path.join(os.path.dirname(best_pt), f"best_{{artifact_tag}}.pt"))
        os.replace(best_pt, renamed_best)
        best_pt = renamed_best
        logger.info(f"best.pt已重命名: {{best_pt}}")

        export_status = {{"onnx": False, "tflite": False}}
        export_outputs = {{}}
        export_model = YOLO(best_pt)
        common_export_kwargs = {{
            "imgsz": {image_size},
            "batch": 1,
            "dynamic": False,
            "simplify": False
        }}

        def normalize_saved_model_dir(saved_out):
            saved_dir = str(saved_out)
            if saved_dir.endswith('.pb'):
                saved_dir = os.path.dirname(saved_dir)
            if not os.path.isdir(saved_dir):
                raise Exception(f"未找到SavedModel目录: {{saved_dir}}")
            return saved_dir

        def export_tflite_pair_from_saved_model(saved_dir):
            stem = os.path.splitext(os.path.basename(best_pt))[0]
            out_dir = os.path.dirname(best_pt)
            fp32_path = os.path.join(out_dir, f"{{stem}}_float32.tflite")
            fp16_path = os.path.join(out_dir, f"{{stem}}_float16.tflite")

            converter32 = tf.lite.TFLiteConverter.from_saved_model(saved_dir)
            converter32.experimental_new_converter = True
            tflite32 = converter32.convert()
            with open(fp32_path, "wb") as f:
                f.write(tflite32)

            converter16 = tf.lite.TFLiteConverter.from_saved_model(saved_dir)
            converter16.experimental_new_converter = True
            converter16.optimizations = [tf.lite.Optimize.DEFAULT]
            converter16.target_spec.supported_types = [tf.float16]
            tflite16 = converter16.convert()
            with open(fp16_path, "wb") as f:
                f.write(tflite16)
            return fp32_path, fp16_path

        for fmt in ["onnx", "tflite"]:
            try:
                logger.info(f"开始导出格式: {{fmt}}")
                if fmt == "onnx":
                    out = export_model.export(format="onnx", **common_export_kwargs)
                    export_status[fmt] = True
                    export_outputs[fmt] = str(out)
                    logger.info(f"{{fmt}}导出成功: {{out}}")
                else:
                    # tflite 目标：稳定产出 FP32 + FP16；导出阶段强制CPU规避GPU侧偶发转换异常
                    tflite_rounds = 3
                    tflite_last_err = None
                    for round_idx in range(1, tflite_rounds + 1):
                        logger.info(f"tflite导出第{{round_idx}}/{{tflite_rounds}}轮...")
                        prev_cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES")
                        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
                        try:
                            saved_out = export_model.export(format="saved_model", **common_export_kwargs)
                            saved_dir = normalize_saved_model_dir(saved_out)
                            fp32_path, fp16_path = export_tflite_pair_from_saved_model(saved_dir)
                            export_status[fmt] = True
                            export_outputs["tflite"] = fp32_path
                            export_outputs["tflite_fp32"] = fp32_path
                            export_outputs["tflite_fp16"] = fp16_path
                            logger.info(f"tflite导出成功(fp32): {{fp32_path}}")
                            logger.info(f"tflite导出成功(fp16): {{fp16_path}}")
                            break
                        except Exception as round_err:
                            tflite_last_err = round_err
                            logger.warning(f"tflite导出第{{round_idx}}轮失败: {{round_err}}")
                            if round_idx < tflite_rounds:
                                wait_sec = round_idx * 3
                                logger.info(f"等待{{wait_sec}}秒后重试tflite导出...")
                                time.sleep(wait_sec)
                        finally:
                            if prev_cuda_visible is None:
                                os.environ.pop("CUDA_VISIBLE_DEVICES", None)
                            else:
                                os.environ["CUDA_VISIBLE_DEVICES"] = prev_cuda_visible
                    if not export_status[fmt]:
                        raise Exception(f"tflite多轮重试失败: {{tflite_last_err}}")
            except Exception as export_err:
                export_outputs[fmt] = f"ERROR: {{export_err}}"
                logger.error(f"{{fmt}}导出失败: {{export_err}}")

        logger.info("导出结果: " + json.dumps({{"status": export_status, "outputs": export_outputs}}, ensure_ascii=False))
        # 导出成功判定：ONNX为必需，TFLite为可选（失败仅告警，不中断训练与打包）
        if not export_status.get("onnx", False):
            raise Exception(f"导出失败: {{export_status}}")
        if not export_status.get("tflite", False):
            logger.warning("tflite导出失败（可选项），已继续执行并保留pt/onnx与完整zip打包")
        
        # 训练产物统一打包：ZIP名=命名_时间戳，ZIP内文件统一追加同一尾缀
        def get_dataset_class_label(yaml_file):
            try:
                with open(yaml_file, "r", encoding="utf-8") as rf:
                    y = yaml.safe_load(rf) or {{}}
                names = y.get("names")
                label = None
                if isinstance(names, dict) and names:
                    def _k_sort(v):
                        sv = str(v)
                        return (0, int(sv)) if sv.isdigit() else (1, sv)
                    first_key = sorted(names.keys(), key=_k_sort)[0]
                    label = names.get(first_key)
                elif isinstance(names, list) and names:
                    label = names[0]
                safe_label = sanitize_name_suffix(label)
                return safe_label if safe_label else "dataset"
            except Exception:
                return "dataset"

        def build_tagged_name(src_path, tag, dataset_label):
            base = os.path.basename(src_path)
            stem, ext = os.path.splitext(base)
            if base.lower() == "dataset.yaml":
                return f"{{dataset_label}}_{{tag}}.yaml"
            # 已包含同一tag时不再叠加（例如 best_xxx_float32.tflite 中间已带 xxx=命名_时间戳）
            if stem.endswith(f"_{{tag}}") or (f"_{{tag}}_" in stem) or stem.startswith(f"{{tag}}_"):
                return base
            return f"{{stem}}_{{tag}}{{ext}}"

        pack_temp_dir = f"/tmp/train_pack_{{artifact_tag}}"
        if os.path.isdir(pack_temp_dir):
            shutil.rmtree(pack_temp_dir, ignore_errors=True)
        os.makedirs(pack_temp_dir, exist_ok=True)
        to_pack = []
        seen = set()

        def add_pack_file(path):
            if not path or (not os.path.isfile(path)):
                return
            real = os.path.realpath(path)
            if real in seen:
                return
            seen.add(real)
            to_pack.append(path)

        add_pack_file(best_pt)
        for p in export_outputs.values():
            if isinstance(p, str) and p and (not p.startswith("ERROR:")) and os.path.isfile(p):
                add_pack_file(p)

        # 常见训练附带文件（若存在则一并打包）
        for rel_name in [
            "args.yaml",
            "results.csv",
            "results.png",
            "confusion_matrix.png",
            "F1_curve.png",
            "P_curve.png",
            "PR_curve.png",
            "R_curve.png",
        ]:
            add_pack_file(os.path.join(run_dir, rel_name))
        add_pack_file(yaml_path)

        dataset_label = get_dataset_class_label(yaml_path)
        used_names = set()
        staged_files = []
        for src in to_pack:
            tagged_name = build_tagged_name(src, artifact_tag, dataset_label)
            unique_name = tagged_name
            stem, ext = os.path.splitext(tagged_name)
            i = 1
            while unique_name in used_names:
                unique_name = f"{{stem}}_{{i}}{{ext}}"
                i += 1
            used_names.add(unique_name)
            dst = os.path.join(pack_temp_dir, unique_name)
            shutil.copy2(src, dst)
            staged_files.append(dst)

        zip_path = ensure_unique_path(os.path.join(run_dir, f"{{artifact_tag}}.zip"))
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for fp in staged_files:
                zf.write(fp, arcname=os.path.basename(fp))
        shutil.rmtree(pack_temp_dir, ignore_errors=True)
        export_outputs["zip"] = zip_path
        logger.info(f"训练产物ZIP已生成: {{zip_path}}")
        logger.info("FINAL_STATUS: SUCCESS")
        return {{"train_results": str(results), "exports": export_outputs}}
        
    except Exception as e:
        logger.error(f"训练失败: {{e}}")
        logger.error("FINAL_STATUS: FAILED")
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

    def _upload_worker(self, connect_params, local_file, remote_file, retry_times, skip_remote_stat=False):
        """单个文件上传（含重试），每个线程独立建立连接避免通道冲突"""
        import stat
        
        # 提取远程目录
        remote_dir = os.path.dirname(remote_file).replace("\\", "/")
        
        for attempt in range(1, retry_times + 1):
            if self.upload_cancel_event.is_set():
                return 'cancel'
            ssh = None
            try:
                # 1. 独立建立SSH连接
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(**connect_params, timeout=10)
                
                # 2. 使用SFTP进行秒传判断与目录创建
                with ssh.open_sftp() as sftp:
                    # 确保远程目录存在（执行 mkdir -p 更安全快捷）
                    # 只在第一次尝试时或者真的需要时创建目录，防止疯狂发起命令
                    stdin, stdout, stderr = ssh.exec_command(f"mkdir -p '{remote_dir}'")
                    stdout.channel.recv_exit_status() # 等待目录创建完成

                    if not skip_remote_stat:
                        try:
                            remote_stat = sftp.stat(remote_file)
                            local_size  = os.path.getsize(local_file)
                            if stat.S_ISREG(remote_stat.st_mode) and remote_stat.st_size == local_size:
                                return 'skip'
                        except FileNotFoundError:
                            pass
                    
                    # 3. 使用 sftp.put 替代 scp，更加稳定且避免 No such file or directory 错误
                    if self.upload_cancel_event.is_set():
                        return 'cancel'
                    sftp.put(local_file, remote_file)
                    
                return 'ok'
                
            except Exception as e:
                if attempt == retry_times:
                    print(f'[DEBUG] _upload_worker fail {os.path.basename(local_file)} error: {e}')
                    return f'fail:{e}'
                time.sleep(1)
            finally:
                if ssh:
                    ssh.close()
                    
        return 'fail:unknown'

    def _set_upload_button_state(self, uploading):
        if not hasattr(self, 'upload_toggle_button'):
            return
        if uploading:
            self.upload_toggle_button.configure(text="停止上传", bootstyle="danger")
        else:
            self.upload_toggle_button.configure(text="上传数据集", bootstyle="success")
        self.update_action_button_states()

    def _should_upload_file(self, rel_path):
        rel = rel_path.replace('\\', '/').lstrip('./')
        lower_rel = rel.lower()
        parts = rel.split('/')
        if any(name.startswith('.') and name not in ['.'] for name in parts):
            return False
        if lower_rel.endswith('.upload_checkpoint.json'):
            return False
        if '.backup_' in lower_rel:
            return False
        if lower_rel in ['classes.txt', 'export_stats.txt']:
            return False
        if rel == 'dataset.yaml':
            return True
        if len(parts) >= 3 and parts[0] in ['train', 'val', 'test'] and parts[1] in ['images', 'labels']:
            if parts[1] == 'images':
                return os.path.splitext(lower_rel)[1] in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']
            return lower_rel.endswith('.txt')
        return False

    def verify_remote_dataset(self, connect_params, remote_path):
        result = {'ok': False, 'msg': '云端校验未执行'}
        ssh = None
        try:
            remote_script = f"""import os, json, yaml, math
dataset = {repr(remote_path)}
res = {{"ok": False, "msg": "", "bad": None, "counts": {{}}}}
yaml_file = os.path.join(dataset, "dataset.yaml")
if not os.path.exists(yaml_file):
    res["msg"] = "dataset.yaml不存在"
    print(json.dumps(res, ensure_ascii=False))
    raise SystemExit(0)
with open(yaml_file, "r", encoding="utf-8") as f:
    data = yaml.safe_load(f) or {{}}
try:
    nc = int(data.get("nc", 0))
except Exception:
    nc = 0
if nc <= 0:
    res["msg"] = "nc非法或缺失"
    print(json.dumps(res, ensure_ascii=False))
    raise SystemExit(0)
for split in ["train", "val", "test"]:
    img_dir = os.path.join(dataset, split, "images")
    lbl_dir = os.path.join(dataset, split, "labels")
    if not os.path.isdir(img_dir) and not os.path.isdir(lbl_dir):
        continue
    if not os.path.isdir(img_dir) or not os.path.isdir(lbl_dir):
        res["msg"] = f"{{split}}目录不完整"
        print(json.dumps(res, ensure_ascii=False))
        raise SystemExit(0)
    imgs = set()
    lbls = set()
    for fn in os.listdir(img_dir):
        ext = os.path.splitext(fn)[1].lower()
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]:
            imgs.add(os.path.splitext(fn)[0])
    for fn in os.listdir(lbl_dir):
        if fn.lower().endswith(".txt"):
            lbls.add(os.path.splitext(fn)[0])
    res["counts"][split] = {{"images": len(imgs), "labels": len(lbls)}}
    orphan = sorted(lbls - imgs)
    if orphan:
        res["msg"] = f"{{split}}存在无对应图片的标签"
        res["bad"] = {{"file": f"{{split}}/labels/{{orphan[0]}}.txt", "line": 0, "reason": "orphan_label"}}
        print(json.dumps(res, ensure_ascii=False))
        raise SystemExit(0)
    for base in sorted(lbls):
        p = os.path.join(lbl_dir, base + ".txt")
        with open(p, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                t = line.strip()
                if not t:
                    continue
                parts = t.split()
                if len(parts) != 5:
                    res["msg"] = "标签列数错误"
                    res["bad"] = {{"file": p, "line": idx, "reason": "len!=5", "content": t}}
                    print(json.dumps(res, ensure_ascii=False))
                    raise SystemExit(0)
                try:
                    cls = int(float(parts[0]))
                except Exception:
                    res["msg"] = "class_id非法"
                    res["bad"] = {{"file": p, "line": idx, "reason": "class_parse", "content": t}}
                    print(json.dumps(res, ensure_ascii=False))
                    raise SystemExit(0)
                if cls < 0 or cls >= nc:
                    res["msg"] = "class_id越界"
                    res["bad"] = {{"file": p, "line": idx, "reason": f"class_range_0_{{nc-1}}", "content": t}}
                    print(json.dumps(res, ensure_ascii=False))
                    raise SystemExit(0)
                try:
                    x, y, w, h = map(float, parts[1:])
                except Exception:
                    res["msg"] = "bbox非法"
                    res["bad"] = {{"file": p, "line": idx, "reason": "bbox_parse", "content": t}}
                    print(json.dumps(res, ensure_ascii=False))
                    raise SystemExit(0)
                if w <= 0 or h <= 0 or not (0 <= x <= 1 and 0 <= y <= 1 and 0 <= w <= 1 and 0 <= h <= 1):
                    res["msg"] = "bbox越界"
                    res["bad"] = {{"file": p, "line": idx, "reason": "bbox_range", "content": t}}
                    print(json.dumps(res, ensure_ascii=False))
                    raise SystemExit(0)
res["ok"] = True
res["msg"] = "云端数据集校验通过"
print(json.dumps(res, ensure_ascii=False))"""

            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(**connect_params, timeout=15)

            # 使用优化的Python环境检测（优先方案+兼容方案）
            python_cmd = self.get_python_cmd_with_fallback(ssh)

            if not python_cmd:
                result['msg'] = '未找到带有yaml模块的Python命令，且无法自动安装'
                return result
            
            cmd = f"{python_cmd} - <<'PY'\n" + remote_script + "\nPY"
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=180)
            out = stdout.read().decode('utf-8', errors='ignore').strip()
            err = stderr.read().decode('utf-8', errors='ignore').strip()
            if err:
                result['msg'] = err
                return result
            if not out:
                result['msg'] = "云端校验无输出"
                return result
            last_line = out.splitlines()[-1]
            obj = json.loads(last_line)
            return obj
        except Exception as e:
            result['msg'] = str(e)
            return result
        finally:
            if ssh:
                try:
                    ssh.close()
                except Exception:
                    pass

    def upload_dataset(self):
        """并发+断点续传上传数据集到云端"""
        if self.upload_in_progress:
            self.upload_cancel_event.set()
            if hasattr(self, 'upload_status_var'):
                self.upload_status_var.set("正在停止上传...")
            self.log_message("已请求停止上传，正在等待当前任务收尾...")
            return

        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        if not self.dataset_config['local_path']:
            messagebox.showerror("错误", "请先选择数据集路径")
            return
        if not self._ensure_dataset_check_is_fresh() or not self.dataset_check_passed:
            messagebox.showwarning("提示", "请先点击“检查数据集”并通过后再上传")
            self.update_action_button_states()
            return
        if not hasattr(self, 'upload_status_var'):
            self.upload_status_var = tk.StringVar(value="")
        if not hasattr(self, 'upload_progress_var'):
            self.upload_progress_var = tk.DoubleVar()

        self.upload_in_progress = True
        self.upload_cancel_event.clear()
        self._set_upload_button_state(True)

        def upload_thread():
            canceled = False
            try:
                # 读取并发度与重试次数
                max_workers_cfg = self.config.get('upload', {}).get('max_workers', 8)
                try:
                    max_workers_cfg = int(max_workers_cfg)
                except Exception:
                    max_workers_cfg = 8
                if max_workers_cfg < 1:
                    max_workers_cfg = 1
                if max_workers_cfg > 32:
                    max_workers_cfg = 32
                retry_times = self.config.get('upload', {}).get('retry_times', 3)

                self.root.after(0, lambda: self.upload_status_var.set("正在扫描文件..."))
                self.root.after(0, lambda: self._set_upload_progress(0))

                # 建立 SSH 连接，动态获取当前界面上的连接配置
                self.update_server_config() # 确保配置是最新的
                
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username']
                }
                
                if self.server_config['key_file']:
                    connect_params['key_filename'] = self.server_config['key_file']
                elif self.server_config['password']:
                    connect_params['password'] = self.server_config['password']
                
                ssh.connect(**connect_params)
                transport = ssh.get_transport()

                local_path  = self.dataset_config['local_path']
                # 强制使用正斜杠处理远端基础路径
                remote_path = self.remote_path_var.get().strip().replace('\\', '/').rstrip('/')
                ckpt_path   = os.path.join(local_path, '.upload_checkpoint.json')

                # 扫描全部文件
                all_files = []
                for root, _, files in os.walk(local_path):
                    if self.upload_cancel_event.is_set():
                        canceled = True
                        break
                    for f in files:
                        if self.upload_cancel_event.is_set():
                            canceled = True
                            break
                        local_file = os.path.join(root, f)
                        # 使用 os.path.relpath 计算相对路径，然后强制转换为 Unix 风格的正斜杠
                        rel_path   = os.path.relpath(local_file, local_path).replace('\\', '/')
                        if not self._should_upload_file(rel_path):
                            continue
                        # 确保组合后的路径也是纯正斜杠
                        remote_file = f"{remote_path}/{rel_path}"
                        all_files.append((local_file, remote_file, rel_path))
                    if canceled:
                        break
                total = len(all_files)
                self.root.after(0, lambda: self.upload_status_var.set(f"共 {total} 个文件，加载断点..."))

                # 加载断点
                done = self._checkpoint_load(ckpt_path)  # {local_file: 'ok'/'skip'/...}
                fast_plan_enabled = False
                skip_remote_stat = False
                plan = self.last_upload_plan if isinstance(self.last_upload_plan, dict) else None
                if plan:
                    plan_remote = str(plan.get('remote_path', '')).rstrip('/')
                    plan_fp = str(plan.get('fingerprint', ''))
                    if plan_remote == remote_path and plan_fp == self.last_dataset_fingerprint:
                        plan_todo = set(plan.get('todo_rel_paths') or [])
                        for lf, _, rel in all_files:
                            if rel not in plan_todo and done.get(lf) not in ['ok', 'skip']:
                                done[lf] = 'skip'
                        fast_plan_enabled = True
                        total_files = max(1, len(all_files))
                        if len(plan_todo) <= max(20, int(total_files * 0.2)):
                            skip_remote_stat = True
                            self.root.after(0, lambda: self.upload_status_var.set(
                                f"已复用检查阶段云端差异结果，预计直传 {len(plan_todo)} 个文件..."
                            ))
                        else:
                            self.root.after(0, lambda: self.upload_status_var.set(
                                f"已复用检查阶段云端差异结果，预计上传 {len(plan_todo)} 个文件，上传前将做秒传校验避免重复上传..."
                            ))
                todo = [(lf, rf) for lf, rf, _ in all_files if done.get(lf) != 'ok' and done.get(lf) != 'skip']
                skip_count = total - len(todo)
                todo_count = len(todo)

                sample_n = min(200, todo_count)
                sample_bytes = 0
                for i in range(sample_n):
                    try:
                        sample_bytes += int(os.path.getsize(todo[i][0]))
                    except Exception:
                        pass
                avg_size = (sample_bytes / sample_n) if sample_n > 0 else 0

                if avg_size <= 256 * 1024:
                    recommended_workers = 16
                elif avg_size <= 2 * 1024 * 1024:
                    recommended_workers = 12
                elif avg_size <= 8 * 1024 * 1024:
                    recommended_workers = 8
                else:
                    recommended_workers = 4

                if todo_count <= 10:
                    recommended_workers = min(recommended_workers, 3)
                elif todo_count <= 50:
                    recommended_workers = min(recommended_workers, 6)

                max_workers = max(1, min(max_workers_cfg, recommended_workers))
                self.root.after(0, lambda mw=max_workers, cfg=max_workers_cfg, n=todo_count: self.log_message(
                    f"上传并发线程: {mw}（配置上限 {cfg}，待上传 {n}）"
                ))

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
                        if self.upload_cancel_event.is_set():
                            canceled = True
                            break
                        fut = pool.submit(
                            self._upload_worker,
                            connect_params,
                            local_file,
                            remote_file,
                            retry_times,
                            skip_remote_stat
                        )
                        future_map[fut] = local_file

                    for fut in as_completed(future_map):
                        if self.upload_cancel_event.is_set():
                            canceled = True
                            for pending in future_map:
                                pending.cancel()
                            break
                        local_file = future_map[fut]
                        res = fut.result()
                        done[local_file] = res
                        if res == 'ok':
                            with lock:
                                ok_count += 1
                        elif res == 'skip':
                            with lock:
                                skip_count += 1
                        elif res == 'cancel':
                            canceled = True
                        elif res.startswith('fail'):
                            with lock:
                                fail_list.append((local_file, res))
                        # 实时保存断点
                        self._checkpoint_save(ckpt_path, done)
                        update_ui()

                ssh.close()
                # 删除断点文件
                if (not canceled) and (not self.upload_cancel_event.is_set()) and os.path.exists(ckpt_path):
                    os.remove(ckpt_path)

                if canceled or self.upload_cancel_event.is_set():
                    self.remote_verify_passed = False
                    self.root.after(0, lambda: self.upload_status_var.set("上传已停止，可再次点击继续断点续传"))
                    self.root.after(0, lambda: self.log_message("上传已停止，断点已保留"))
                else:
                    verify_res = self.verify_remote_dataset(connect_params, remote_path)
                    if verify_res.get('ok'):
                        self.remote_verify_passed = True
                        self.root.after(0, lambda: messagebox.showinfo(
                            "上传完成",
                            f"总计 {total}\n成功 {ok_count}\n跳过 {skip_count}\n失败 {len(fail_list)}\n云端验收通过，可开始训练"))
                        self.root.after(0, lambda: self.upload_status_var.set("上传完成，云端验收通过"))
                        self.root.after(0, lambda: self.log_message("数据集上传完成，云端验收通过"))
                        # 更新数据集状态显示
                        self.root.after(0, self.update_dataset_status_display)
                    else:
                        self.remote_verify_passed = False
                        bad = verify_res.get('bad') or {}
                        bad_tip = ""
                        bad_text = ""
                        if bad:
                            bad_tip = f"\n问题: {bad.get('file', '')} L{bad.get('line', 0)} {bad.get('reason', '')}"
                            bad_text = f"{bad.get('file', '')} L{bad.get('line', 0)} {bad.get('reason', '')}"
                        fail_msg = f"{verify_res.get('msg', '未知错误')}{bad_tip}"
                        self.root.after(0, lambda: self.upload_status_var.set("上传完成，但云端验收失败"))
                        self.root.after(0, lambda m=fail_msg: self.log_message(f"云端验收失败: {m}"))
                        self.root.after(0, lambda m=fail_msg, b=bad_text: self.show_remote_verify_failure(m, b))

            except Exception as e:
                err = str(e)
                self.remote_verify_passed = False
                self.root.after(0, lambda err=err: self.upload_status_var.set(f"上传失败: {err}"))
                self.root.after(0, lambda err=err: self.log_message(f"数据集上传失败: {err}"))
            finally:
                self.upload_in_progress = False
                self.upload_cancel_event.clear()
                self.root.after(0, lambda: self._set_upload_button_state(False))

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
                    # 确保获取的是用户界面上配置的最新路径，并且强制转换为纯正的 Linux 路径格式
                    remote_path = self.remote_path_var.get().replace('\\', '/').rstrip('/')
                    if not remote_path or remote_path == '/' or remote_path == '/root':
                        self.root.after(0, lambda: messagebox.showwarning("警告", "远程路径配置危险，禁止清理整个根目录！"))
                        return
                        
                    self.root.after(0, lambda: self.log_message(f"开始清理云端数据集目录: {remote_path}"))
                    ssh.exec_command(f"rm -rf '{remote_path}'")
                    ssh.exec_command("rm -rf /root/runs")
                    ssh.exec_command("rm -f /root/*.py")
                    
                    ssh.close()
                    
                    self.root.after(0, lambda: self.log_message("云端数据清理完成"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"云端数据清理失败: {e}"))

            threading.Thread(target=clean_thread, daemon=True).start()

    def _get_env_spec(self):
        """环境单一规则源：检查、修复、训练前门禁全部复用"""
        return {
            "system_packages": ["libgl1-mesa-glx", "libglib2.0-0", "libusb-1.0-0"],
            "python_packages": [
                {"name": "pyyaml", "pip": "pyyaml", "import_cmd": 'import yaml; print("OK")'},
                {"name": "numpy", "pip": "numpy==1.26.4", "import_cmd": "import numpy; print(numpy.__version__)", "min_ver": "1.26.0", "max_ver": "2.0.0"},
                {"name": "cv2", "pip": "opencv-python==4.7.0.72", "import_cmd": "import cv2; print(cv2.__version__)"},
                {"name": "PIL", "pip": "pillow", "import_cmd": "from PIL import Image; print(Image.__version__)"},
                {"name": "torch", "pip": "torch", "import_cmd": "import torch; print(torch.__version__)"},
                {"name": "ultralytics", "pip": "ultralytics", "import_cmd": "import ultralytics; print(ultralytics.__version__)"},
                {"name": "matplotlib", "pip": "matplotlib", "import_cmd": "import matplotlib; print(matplotlib.__version__)"},
                {"name": "onnx", "pip": "onnx==1.16.1", "import_cmd": "import onnx; print(onnx.__version__)", "exact_ver": "1.16.1"},
                {"name": "onnxsim", "pip": "onnxsim", "import_cmd": "import onnxsim; print(onnxsim.__version__)"},
                # onnx2tf 在新版本链路中依赖 ai_edge_litert
                {"name": "ai_edge_litert", "pip": "ai-edge-litert", "import_cmd": "import ai_edge_litert; print(getattr(ai_edge_litert, '__version__', 'OK'))"},
                # onnx2tf 在 TensorFlow 2.19 环境下通常还需要独立的 tf_keras 包
                {"name": "tf_keras", "pip": "tf-keras>=2.19,<2.20", "import_cmd": "import tf_keras; print(getattr(tf_keras, '__version__', 'OK'))", "min_ver": "2.19.0", "max_ver": "2.20.0"},
                {"name": "onnx2tf", "pip": "onnx2tf>=1.28.8,<1.29", "import_cmd": "import onnx2tf; print(getattr(onnx2tf, '__version__', 'OK'))", "min_ver": "1.28.8", "max_ver": "1.29.0"},
                {"name": "sng4onnx", "pip": "sng4onnx>=1.0.1", "import_cmd": "import sng4onnx; print(getattr(sng4onnx, '__version__', 'OK'))"},
                {"name": "onnx_graphsurgeon", "pip": "onnx_graphsurgeon>=0.3.26", "import_cmd": "import onnx_graphsurgeon as gs; print(getattr(gs, '__version__', 'OK'))"},
                # 当前云端镜像下 tflite_support 与部分 TF 组合存在 pybind 冲突，先降级为可选依赖
                {"name": "tflite_support", "pip": "tflite_support", "import_cmd": "import tflite_support; print(getattr(tflite_support, '__version__', 'OK'))", "optional": True},
                {"name": "onnxruntime", "pip": "onnxruntime-gpu", "import_cmd": "import onnxruntime as ort; print(ort.__version__)"},
                {"name": "flatbuffers", "pip": "flatbuffers", "import_cmd": "import flatbuffers; print(getattr(flatbuffers, '__version__', 'OK'))"},
                # Ultralytics 导出链要求 protobuf>=5；TensorFlow 2.19 要求 protobuf<6
                {"name": "protobuf", "pip": "protobuf>=5,<6", "import_cmd": "from google.protobuf import __version__ as v; print(v)", "min_ver": "5.0.0", "max_ver": "6.0.0"},
                {"name": "h5py", "pip": "h5py", "import_cmd": "import h5py; print(h5py.__version__)"},
                {"name": "tensorflow", "pip": "tensorflow>=2.19,<2.20", "import_cmd": "import tensorflow as tf; print(tf.__version__)", "min_ver": "2.19.0", "max_ver": "2.20.0"},
            ],
            "system_libs": [
                {"name": "libGL.so.1", "check_cmd": "ldconfig -p | grep libGL.so.1", "hint": "OpenCV需要", "fix_pkg": "libgl1-mesa-glx"},
                {"name": "libusb-1.0.so.0", "check_cmd": "ldconfig -p | grep libusb-1.0.so.0", "hint": "tflite_support需要", "fix_pkg": "libusb-1.0-0"},
            ],
        }

    def _first_import_error_line(self, text):
        lines = [ln.strip() for ln in str(text or "").splitlines() if ln.strip()]
        if not lines:
            return "无详细错误信息"
        for ln in lines:
            if any(k in ln for k in ["ImportError:", "ModuleNotFoundError:", "OSError:", "RuntimeError:", "TypeError:", "ValueError:", "Exception:", "Error:"]):
                return ln[:220]
        for ln in lines:
            # 过滤 TensorFlow 常见信息日志，避免误报为错误首行
            if self._is_benign_import_stderr_line(ln):
                continue
            if ln.startswith("Traceback") or ln.startswith("File "):
                continue
            return ln[:220]
        return lines[-1][:220]

    def _is_benign_import_stderr_line(self, line):
        t = (line or "").strip()
        if not t:
            return True
        lower = t.lower()
        benign_prefixes = [
            "i tensorflow/",
            "w0000",
            "e0000",
            "warning:",
            "all log messages before absl::initializelog() is called are written to stderr",
        ]
        if any(lower.startswith(p) for p in benign_prefixes):
            return True
        benign_contains = [
            "onednn custom operations are on",
            "unable to register cufft factory",
            "unable to register cudnn factory",
            "unable to register cublas factory",
            "computation placer already registered",
            "this tensorflow binary is optimized to use available cpu instructions",
            "to enable the following instructions:",
        ]
        if any(x in lower for x in benign_contains):
            return True
        return False

    def _ver_tuple(self, version_text):
        nums = []
        for seg in str(version_text or "").split("."):
            seg = "".join(ch for ch in seg if ch.isdigit())
            if not seg:
                break
            nums.append(int(seg))
        return tuple(nums[:3] or [0])

    def _version_reason(self, current, spec):
        cur = str(current or "").strip()
        if not cur:
            return "无法读取版本"
        exact_ver = spec.get("exact_ver")
        min_ver = spec.get("min_ver")
        max_ver = spec.get("max_ver")
        if exact_ver and cur != exact_ver:
            return f"版本不匹配({cur})，需 =={exact_ver}"
        cur_t = self._ver_tuple(cur)
        if min_ver and cur_t < self._ver_tuple(min_ver):
            return f"版本过低({cur})，需 >={min_ver}"
        if max_ver and cur_t >= self._ver_tuple(max_ver):
            return f"版本过高({cur})，需 <{max_ver}"
        return ""

    def _run_env_check_with_spec(self, ssh, python_cmd, log=True):
        spec = self._get_env_spec()
        missing = []
        versions = {}

        def _log(msg):
            if log:
                self.root.after(0, lambda m=msg: self.log_message(m))

        stdin, stdout, stderr = ssh.exec_command(f"{python_cmd} --version")
        py_ver = stdout.read().decode("utf-8", errors="ignore").strip()
        versions["python"] = py_ver or "unknown"
        _log(f"✓ Python版本: {versions['python']}")

        for pkg in spec["python_packages"]:
            is_optional = bool(pkg.get("optional"))
            escaped_cmd = pkg["import_cmd"].replace('"', '\\"')
            stdin, stdout, stderr = ssh.exec_command(f'{python_cmd} -c "{escaped_cmd}"')
            output = stdout.read().decode("utf-8", errors="ignore").strip()
            error = stderr.read().decode("utf-8", errors="ignore").strip()
            code = stdout.channel.recv_exit_status()
            merged = "\n".join([x for x in [output, error] if x]).strip()
            has_import_error = any(k in merged for k in ["ModuleNotFoundError", "ImportError", "Traceback", "Exception", "TypeError", "ValueError"])
            benign_stderr = all(self._is_benign_import_stderr_line(ln) for ln in error.splitlines()) if error else True
            if code != 0 or has_import_error or (not output and not benign_stderr):
                reason = self._first_import_error_line(merged)
                if is_optional:
                    versions[pkg["name"]] = f"OPTIONAL_FAIL:{reason[:60]}"
                    _log(f"  ⚠ {pkg['name']}: 可选依赖不可用（{reason}）")
                else:
                    missing.append({"type": "python", "name": pkg["name"], "reason": reason, "pip": pkg["pip"]})
                    _log(f"  ❌ {pkg['name']}: 未安装/不可用（{reason}）")
                continue
            cur_ver = str(output).splitlines()[0].strip() if output else "OK"
            versions[pkg["name"]] = cur_ver
            ver_reason = self._version_reason(cur_ver, pkg)
            if ver_reason:
                missing.append({"type": "python", "name": pkg["name"], "reason": ver_reason, "pip": pkg["pip"]})
                _log(f"  ❌ {pkg['name']}: {ver_reason}")
            else:
                _log(f"  ✅ {pkg['name']}: {cur_ver}")

        _log("检查系统库...")
        for lib in spec["system_libs"]:
            stdin, stdout, stderr = ssh.exec_command(lib["check_cmd"])
            found = stdout.read().decode("utf-8", errors="ignore").strip()
            if found:
                versions[lib["name"]] = "OK"
                _log(f"  ✅ {lib['name']}: 已安装")
            else:
                versions[lib["name"]] = "MISSING"
                reason = f"未安装（{lib['hint']}）"
                missing.append({"type": "system", "name": lib["name"], "reason": reason, "pip": lib["fix_pkg"]})
                _log(f"  ❌ {lib['name']}: {reason}")

        fingerprint_items = [f"{k}={versions[k]}" for k in sorted(versions.keys())]
        return {
            "missing": missing,
            "versions": versions,
            "fingerprint": "|".join(fingerprint_items),
        }

    def check_environment(self):
        """检查云端环境"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return

        self.log_message("=" * 60)
        self.log_message("开始检查云端环境...")
        self.log_message("=" * 60)

        def check_thread():
            try:
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username'],
                    'password': self.server_config['password']
                }

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(**connect_params, timeout=15)

                def log_callback(msg):
                    self.root.after(0, lambda m=msg: self.log_message(m))

                python_cmd = self.get_python_cmd_with_fallback(ssh, log_func=log_callback)
                if not python_cmd:
                    self.root.after(0, lambda: self.log_message("✗ 未找到可用的Python环境"))
                    self.root.after(0, lambda: self._set_env_check_status(False))
                    ssh.close()
                    return

                self.root.after(0, lambda p=python_cmd: self.log_message(f"✓ Python命令: {p}"))
                result = self._run_env_check_with_spec(ssh, python_cmd, log=True)
                ssh.close()

                self.root.after(0, lambda: self.log_message("-" * 60))
                if result["missing"]:
                    self.root.after(0, lambda c=len(result["missing"]): self.log_message(f"⚠ 发现 {c} 个问题需要修复"))
                    self.root.after(0, lambda: self._set_env_check_status(False))
                    self.env_check_fingerprint = None
                    self.env_last_check_time = time.time()
                else:
                    self.root.after(0, lambda: self.log_message("✓ 环境检查通过，所有组件正常"))
                    self.root.after(0, lambda: self._set_env_check_status(True))
                    self.env_check_fingerprint = result["fingerprint"]
                    self.env_last_check_time = time.time()

                self.root.after(0, lambda: self.log_message("=" * 60))

            except Exception as e:
                self.root.after(0, lambda err=str(e): self.log_message(f"✗ 环境检查失败: {err}"))
                self.root.after(0, lambda: self._set_env_check_status(False))
                self.env_check_fingerprint = None
                self.env_last_check_time = None

        threading.Thread(target=check_thread, daemon=True).start()

    def _set_env_check_status(self, status):
        """设置环境检查状态并更新修复按钮"""
        self.env_check_status = status
        if status is True:
            self.fix_env_button.configure(state="disabled")
        elif status is False:
            self.fix_env_button.configure(state="normal")
        else:
            # 未检查状态不允许直接修复，先执行检查拿到差异清单
            self.fix_env_button.configure(state="disabled")

    def fix_environment(self):
        """修复云端环境"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return

        if self.env_check_status is None:
            messagebox.showwarning("提示", "请先执行环境检查")
            return

        if self.env_check_status is True:
            messagebox.showinfo("提示", "环境正常，无需修复")
            return

        self.log_message("=" * 60)
        self.log_message("开始修复云端环境...")
        self.log_message("=" * 60)

        # 禁用修复按钮，防止重复点击
        self.fix_env_button.configure(state="disabled")

        def fix_thread():
            try:
                connect_params = {
                    'hostname': self.server_config['hostname'],
                    'port': self.server_config['port'],
                    'username': self.server_config['username'],
                    'password': self.server_config['password']
                }

                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                ssh.connect(**connect_params, timeout=15)

                python_cmd = self.get_python_cmd_with_fallback(ssh)
                if not python_cmd:
                    self.root.after(0, lambda: self.log_message("✗ 未找到Python环境，无法修复"))
                    return
                self.root.after(0, lambda p=python_cmd: self.log_message(f"✓ 修复使用Python: {p}"))

                # 先按统一规则源检查，仅修复缺失项
                spec = self._get_env_spec()
                before_result = self._run_env_check_with_spec(ssh, python_cmd, log=False)
                if not before_result["missing"]:
                    self.root.after(0, lambda: self.log_message("✓ 当前环境已通过统一检查，无需修复"))
                    self.env_check_fingerprint = before_result["fingerprint"]
                    self.env_last_check_time = time.time()
                    self.root.after(0, lambda: self._set_env_check_status(True))
                    ssh.close()
                    return

                missing_system_pkgs = []
                missing_python_names = set()
                for item in before_result["missing"]:
                    if item.get("type") == "system" and item.get("pip"):
                        missing_system_pkgs.append(item["pip"])
                    elif item.get("type") == "python":
                        missing_python_names.add(item.get("name"))
                # 系统库仍按规格白名单安装，但优先只装缺失项，避免无意义重复
                system_pkg_list = []
                for p in spec["system_packages"]:
                    if p in missing_system_pkgs:
                        system_pkg_list.append(p)
                if system_pkg_list:
                    system_pkg_str = " ".join(system_pkg_list)
                    self.root.after(0, lambda s=system_pkg_str: self.log_message(f"安装系统库: {s}"))
                    stdin, stdout, stderr = ssh.exec_command(f"apt-get update -qq && apt-get install -y {system_pkg_str} -qq")
                    sys_out = stdout.read().decode('utf-8', errors='ignore').strip()
                    sys_err = stderr.read().decode('utf-8', errors='ignore').strip()
                    sys_code = stdout.channel.recv_exit_status()
                else:
                    sys_out = ""
                    sys_err = ""
                    sys_code = 0
                def _is_benign_apt_line(line):
                    t = (line or "").strip().lower()
                    if not t:
                        return True
                    # 常见非致命提示：容器/精简系统缺少 apt-utils 时会出现
                    if "debconf: delaying package configuration, since apt-utils is not installed" in t:
                        return True
                    if t.startswith("debconf:"):
                        return True
                    if "warning" in t:
                        return True
                    return False
                sys_err_fatal = [ln for ln in sys_err.splitlines() if not _is_benign_apt_line(ln)]
                if sys_code != 0 or sys_err_fatal:
                    first_err = (sys_err_fatal[0] if sys_err_fatal else sys_err or sys_out or f"exit={sys_code}")[:260]
                    raise RuntimeError(f"系统库安装失败: {first_err}")
                if system_pkg_list:
                    self.root.after(0, lambda: self.log_message("✓ 系统库安装完成"))
                else:
                    self.root.after(0, lambda: self.log_message("✓ 系统库均已满足，跳过安装"))

                # 按单一规格源安装缺失Python包（含版本不符）
                required_python_packages = [item for item in spec["python_packages"] if (not item.get("optional")) and item.get("name") in missing_python_names]
                optional_python_packages = [item for item in spec["python_packages"] if item.get("optional")]
                packages_to_install = [item["pip"] for item in required_python_packages]
                if optional_python_packages:
                    optional_names = ", ".join([x["name"] for x in optional_python_packages])
                    self.root.after(0, lambda n=optional_names: self.log_message(f"⚠ 跳过可选依赖安装: {n}"))
                install_failed = []
                if packages_to_install:
                    self.root.after(0, lambda c=len(packages_to_install): self.log_message(f"按统一检查结果修复Python依赖，共 {c} 项"))
                for pkg in packages_to_install:
                    self.root.after(0, lambda p=pkg: self.log_message(f"安装 {p}..."))
                    stdin, stdout, stderr = ssh.exec_command(f'{python_cmd} -m pip install "{pkg}" -q')
                    out = stdout.read().decode('utf-8', errors='ignore').strip()
                    err = stderr.read().decode('utf-8', errors='ignore').strip()
                    code = stdout.channel.recv_exit_status()
                    err_fatal = [ln for ln in err.splitlines() if ln.strip() and 'warning' not in ln.lower()]
                    if code != 0 or err_fatal:
                        recheck_ok = False
                        for spec_item in spec["python_packages"]:
                            if spec_item["pip"] == pkg:
                                escaped_recheck = spec_item["import_cmd"].replace('"', '\\"')
                                stdin2, stdout2, stderr2 = ssh.exec_command(f'{python_cmd} -c "{escaped_recheck}"')
                                re_out = stdout2.read().decode('utf-8', errors='ignore').strip()
                                re_err = stderr2.read().decode('utf-8', errors='ignore').strip()
                                re_merged = "\n".join([x for x in [re_out, re_err] if x]).strip()
                                recheck_ok = bool(re_out) and not any(k in re_merged for k in ["Traceback", "ModuleNotFoundError", "ImportError", "Exception"])
                                break
                        if recheck_ok:
                            self.root.after(0, lambda p=pkg: self.log_message(f"⚠ {p} 安装有冲突提示，但导入可用，继续执行"))
                        else:
                            reason = (err_fatal[0] if err_fatal else err or out or f"exit={code}")[:260]
                            install_failed.append((pkg, reason))
                            self.root.after(0, lambda p=pkg, r=reason: self.log_message(f"✗ {p} 安装失败: {r}"))
                    else:
                        self.root.after(0, lambda p=pkg: self.log_message(f"✓ {p} 安装完成"))
                if (not packages_to_install):
                    self.root.after(0, lambda: self.log_message("✓ Python依赖均已满足，跳过安装"))

                if install_failed:
                    bad = "; ".join([f"{p}: {r}" for p, r in install_failed])[:420]
                    raise RuntimeError(f"以下包安装失败: {bad}")

                # 修复后按同一规则源复检，直接给出可训练状态
                verify_result = self._run_env_check_with_spec(ssh, python_cmd, log=False)
                if verify_result["missing"]:
                    bad = "; ".join([f"{x['name']}: {x['reason']}" for x in verify_result["missing"]])[:420]
                    raise RuntimeError(f"修复后复检仍失败: {bad}")

                ssh.close()

                self.root.after(0, lambda: self.log_message("=" * 60))
                self.root.after(0, lambda: self.log_message("✓ 环境修复完成，复检通过"))
                self.root.after(0, lambda: self.log_message("=" * 60))

                self.env_check_fingerprint = verify_result["fingerprint"]
                self.env_last_check_time = time.time()
                self.root.after(0, lambda: self._set_env_check_status(True))

            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"✗ 环境修复失败: {e}"))
                # 修复失败，允许再次尝试
                self.root.after(0, lambda: self.fix_env_button.configure(state="normal"))

        threading.Thread(target=fix_thread, daemon=True).start()

    def toggle_training(self):
        """切换训练状态（开始/停止）"""
        if hasattr(self, 'is_training') and self.is_training:
            self.stop_training()
        else:
            self.start_training()

    def update_training_button_state(self):
        """更新训练按钮状态"""
        if hasattr(self, 'is_training') and self.is_training:
            self.start_training_button.config(text="停止训练", bootstyle="danger")
        else:
            self.start_training_button.config(text="开始训练", bootstyle="success")

    def _notify_training_complete(self):
        """训练完成提示（通知+声音+闪烁+弹窗）"""
        try:
            # 1. 系统通知（右下角气泡）
            notification.notify(
                title="✅ 训练完成",
                message=f"YOLOv8 训练已完成\n总轮次: {self.training_config.get('epochs', 'N/A')} 轮\n时长: {self.status_duration_var.get()}",
                timeout=10,
                app_icon=None
            )
        except Exception as e:
            logging.warning(f"系统通知失败: {e}")
        
        try:
            # 2. 声音提示
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        except Exception as e:
            logging.warning(f"声音提示失败: {e}")
        
        try:
            # 3. 任务栏闪烁
            self.root.attributes('-topmost', True)
            self.root.attributes('-topmost', False)
        except Exception as e:
            logging.warning(f"任务栏闪烁失败: {e}")
        
        try:
            # 4. 弹窗提示
            epochs = self.training_config.get('epochs', 'N/A')
            duration = self.status_duration_var.get()
            messagebox.showinfo(
                "🎉 训练完成",
                f"训练已成功完成！\n\n"
                f"📊 总轮次: {epochs} 轮\n"
                f"⏱️ {duration}\n\n"
                f'请点击"下载模型"按钮获取训练结果。'
            )
        except Exception as e:
            logging.warning(f"弹窗提示失败: {e}")

    def start_training(self):
        """开始训练"""
        errors = self.update_all_configs(collect_errors=True)
        try:
            if int(self.training_config.get('epochs', 0)) <= 0:
                errors.append("训练轮次必须大于0")
        except Exception:
            errors.append("训练轮次无效")
        try:
            if int(self.training_config.get('batch_size', 0)) <= 0:
                errors.append("批次大小必须大于0")
        except Exception:
            errors.append("批次大小无效")
        try:
            if int(self.training_config.get('image_size', 0)) <= 0:
                errors.append("分辨率必须大于0")
        except Exception:
            errors.append("分辨率无效")
        try:
            if float(self.training_config.get('learning_rate', 0.0)) <= 0:
                errors.append("学习率必须大于0")
        except Exception:
            errors.append("学习率无效")
        if errors:
            uniq_errors = []
            for e in errors:
                if e not in uniq_errors:
                    uniq_errors.append(e)
            messagebox.showerror("参数错误", "\n".join(uniq_errors))
            return
        self.save_config()
        expected_epochs = int(self.training_config['epochs'])
        expected_batch_size = int(self.training_config['batch_size'])
        expected_learning_rate = float(self.training_config['learning_rate'])
        expected_image_size = int(self.training_config['image_size'])
        expected_base_model = self.training_config['base_model']
        expected_lr_str = str(expected_learning_rate)
        script_content = self.create_training_script_content()
        self.log_message(
            f"本次训练参数: model={expected_base_model}, imgsz={expected_image_size}, batch={expected_batch_size}, lr0={expected_lr_str}, epochs={expected_epochs}"
        )
        if not self.is_connected:
            messagebox.showerror("错误", "请先测试服务器连接")
            return
        if not self._ensure_dataset_check_is_fresh() or not self.dataset_check_passed:
            messagebox.showwarning("提示", "请先完成并通过“检查数据集”")
            self.update_action_button_states()
            return
        if not self.remote_verify_passed:
            messagebox.showwarning("提示", "请先上传数据集并通过云端验收")
            self.update_action_button_states()
            return
        if self.env_check_status is not True:
            messagebox.showwarning("提示", "请先执行并通过【检查环境】（或先点【修复环境】后复检通过）")
            return
        
        def training_thread():
            try:
                self.root.after(0, lambda: self.training_status_var.set("训练中..."))
                self.is_training = True
                self.root.after(0, self.update_training_button_state)
                self.training_start_time = time.time()
                self._last_eta_epoch = None
                self._last_eta_total = None
                if hasattr(self, "status_duration_var"):
                    self.root.after(0, lambda: self.status_duration_var.set("时长: 00:00:00"))
                if hasattr(self, "status_eta_var"):
                    self.root.after(0, lambda: self.status_eta_var.set("预计完成: --"))
                
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

                # 首先获取Python命令
                self.root.after(0, lambda: self.log_message("获取Python环境..."))
                python_cmd = self.get_python_cmd_with_fallback(ssh)

                if not python_cmd:
                    self.root.after(0, lambda: self.log_message("✗ 未找到可用的Python环境，请先执行'检查环境'和'修复环境'"))
                    self.root.after(0, lambda: self.training_status_var.set("训练失败: 未找到Python环境"))
                    return

                self.root.after(0, lambda: self.log_message(f"✓ 使用Python: {python_cmd}"))
                self.root.after(0, lambda: self.log_message("执行训练前环境门禁检查（只检查，不安装）..."))
                gate_result = self._run_env_check_with_spec(ssh, python_cmd, log=False)
                if gate_result["missing"]:
                    missing_text = ", ".join([f"{x['name']}({x['reason']})" for x in gate_result["missing"][:6]])
                    self.root.after(0, lambda m=missing_text: self.log_message(f"✗ 训练前环境门禁未通过: {m}"))
                    self.root.after(0, lambda: self.log_message("训练阶段已禁止自动拉包，请先点击【修复环境】"))
                    self.root.after(0, lambda: self.training_status_var.set("训练失败: 环境门禁未通过"))
                    return
                if self.env_check_fingerprint and gate_result["fingerprint"] != self.env_check_fingerprint:
                    self.root.after(0, lambda: self.log_message("⚠ 检测到环境已变化，已按最新环境结果继续训练"))
                self.env_check_fingerprint = gate_result["fingerprint"]
                self.env_last_check_time = time.time()
                self.root.after(0, lambda: self.log_message("✓ 训练前环境门禁通过"))

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
                        
                        upload_cmd = f"cat > /tmp/predownload_model.py << 'PY'\n{download_script}\nPY"
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {upload_cmd}')
                        stdout.channel.recv_exit_status()
                        stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} /tmp/predownload_model.py')
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

                stdin, stdout, stderr = ssh.exec_command("grep -nE 'epochs=|batch=|lr0=|imgsz=' /root/training_script.py")
                script_param_lines = stdout.read().decode('utf-8', errors='ignore')
                expected_tokens = [
                    f"epochs={expected_epochs}",
                    f"batch={expected_batch_size}",
                    f"lr0={expected_lr_str}",
                    f"imgsz={expected_image_size}"
                ]
                missing_tokens = [t for t in expected_tokens if t not in script_param_lines]
                if missing_tokens:
                    self.root.after(0, lambda m=", ".join(missing_tokens): self.log_message(f"✗ 训练脚本参数校验失败，缺少: {m}"))
                    self.root.after(0, lambda: self.training_status_var.set("训练失败: 脚本参数不一致"))
                    return
                self.root.after(0, lambda: self.log_message("✓ 训练脚本参数校验通过"))

                # 训练前强制校正远程dataset.yaml
                self.root.after(0, lambda: self.log_message("校正云端dataset.yaml路径..."))
                yaml_fixed = self.normalize_remote_dataset_yaml(ssh, python_cmd)
                if not yaml_fixed:
                    self.root.after(0, lambda: self.log_message("✗ 云端dataset.yaml校正失败，请先检查数据集上传是否完整"))
                    self.root.after(0, lambda: self.training_status_var.set("训练失败: dataset.yaml异常"))
                    return

                self.root.after(0, lambda: self.log_message("✓ 准备开始训练..."))

                                
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
                    # 仅做诊断，不做安装；训练阶段禁止任何自动修复
                    cuda_check_cmd = f'{python_cmd} -c "import torch; print(f\\"cuda_available={{torch.cuda.is_available()}}\\"); print(f\\"cuda_version={{torch.version.cuda}}\\"); print(f\\"torch_version={{torch.__version__}}\\")"'
                    stdin, stdout, stderr = ssh.exec_command(f'cd /root && {cuda_check_cmd}')
                    cuda_check_output = stdout.read().decode('utf-8').strip()
                    cuda_check_error = stderr.read().decode('utf-8').strip()

                    self.root.after(0, lambda: self.log_message(f"PyTorch CUDA检测输出: {cuda_check_output}"))
                    if cuda_check_error:
                        self.root.after(0, lambda: self.log_message(f"PyTorch CUDA检测错误: {cuda_check_error}"))

                    # 解析CUDA状态
                    cuda_available = False
                    cuda_version = None
                    torch_version = None

                    for line in cuda_check_output.split('\n'):
                        if 'cuda_available=' in line:
                            cuda_available = 'True' in line
                        elif 'cuda_version=' in line:
                            cuda_version = line.split('=', 1)[1]
                            if cuda_version == 'None':
                                cuda_version = None
                        elif 'torch_version=' in line:
                            torch_version = line.split('=', 1)[1]

                    self.root.after(0, lambda: self.log_message(f"PyTorch CUDA状态: available={cuda_available}, version={cuda_version}, torch={torch_version}"))
                self.root.after(0, lambda: self.log_message("✓ 训练阶段仅诊断，不执行任何安装/重装；环境检查与门禁已统一复用"))
                
                # 执行训练命令，使用精确的环境控制，确保用户本地包可访问
                # 1. 设置PYTHONNOUSERSITE=0确保用户包可用
                # 2. 设置PYTHONPATH优先使用用户本地路径
                # 3. 使用-E标志忽略环境变量，但不使用-s标志（-s会禁用用户包）
                # 4. 移除-I标志，因为它会禁用用户站点包目录
                stdin, stdout, stderr = ssh.exec_command(f'cd /root && {python_cmd} -c "import sys; print(str(sys.version_info.major)+\\".\\"+str(sys.version_info.minor))"')
                py_mm = stdout.read().decode('utf-8').strip() or '3.10'
                py_bin_dir = os.path.dirname(str(python_cmd).replace('\\', '/'))
                env_setup = [
                    'export PYTHONNOUSERSITE=0',
                    'export TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1',
                    'export YOLO_AUTOINSTALL=0',
                    'export ULTRALYTICS_AUTOINSTALL=0',
                    'export MPLBACKEND=Agg',
                    'export CUDA_VISIBLE_DEVICES=0',
                    'export PYTHONDONTWRITEBYTECODE=1',
                    f'export PATH={py_bin_dir}:$PATH',
                    'unset PYTHONSTARTUP',
                    f'export PYTHONPATH=/root/miniforge3/lib/python{py_mm}/site-packages:/root/.local/lib/python{py_mm}/site-packages:$PYTHONPATH'
                ]
                env_vars = ' && '.join(env_setup)
                
                # 使用-u确保无缓冲输出，移除-E标志以确保PYTHONPATH环境变量生效
                isolated_python_cmd = f'{python_cmd} -u'
                self._reset_loss_tracking()
                self._run_dir_logged = False
                run_name = f'yolo_training_{timestamp}'
                self.training_run_name = run_name
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
                ansi = re.compile(r'\x1B\[[0-9;]*[A-Za-z]')
                log_position = 0
                total_epochs = None
                total_steps = None
                current_epoch = None
                current_step = None
                saw_success_marker = False
                saw_failed_marker = False
                
                while True:
                    # 读取日志文件的新内容
                    stdin, stdout, stderr = ssh.exec_command(f'tail -c +{log_position + 1} {log_file} 2>/dev/null || echo "日志文件不存在"')
                    new_content = stdout.read().decode('utf-8', errors='ignore')
                    
                    if new_content and new_content.strip() != "日志文件不存在":
                        lines = new_content.split('\n')
                        for line in lines:
                            if line.strip():
                                self.root.after(0, lambda l=line: self.log_message(f"[训练] {l.strip()}"))
                                clean_line = ansi.sub('', line)
                                if 'FINAL_STATUS: SUCCESS' in clean_line:
                                    saw_success_marker = True
                                if 'FINAL_STATUS: FAILED' in clean_line:
                                    saw_failed_marker = True
                                # 解析总epoch
                                m_total = re.search(r'Starting training for\s+(\d+)\s+epochs', clean_line)
                                if m_total:
                                    try:
                                        total_epochs = int(m_total.group(1))
                                    except:
                                        pass
                                if total_epochs is None:
                                    m_total_args = re.search(r'epochs=(\d+)', clean_line)
                                    if m_total_args:
                                        try:
                                            total_epochs = int(m_total_args.group(1))
                                        except:
                                            pass
                                m_epoch_row = re.search(r'^\s*(\d+)\s*/\s*(\d+)\s+', clean_line)
                                if m_epoch_row:
                                    try:
                                        current_epoch = int(m_epoch_row.group(1))
                                        if total_epochs is None:
                                            total_epochs = int(m_epoch_row.group(2))
                                    except:
                                        pass
                                # 解析tqdm进度 例如 "0%| | 0/14"
                                m_step = re.search(r'(\d+)%\|.*?(\d+)/(\d+)', clean_line)
                                if m_step:
                                    try:
                                        current_step = int(m_step.group(2))
                                        total_steps = int(m_step.group(3))
                                    except:
                                        pass
                                if total_epochs and current_epoch:
                                    status = f"训练中: {current_epoch}/{total_epochs}"
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
                    if 'FINAL_STATUS: SUCCESS' in final_log:
                        saw_success_marker = True
                    if 'FINAL_STATUS: FAILED' in final_log:
                        saw_failed_marker = True
                
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

                if saw_success_marker and not saw_failed_marker:
                    self.root.after(0, lambda: self.training_status_var.set("✅ 训练+导出完成"))
                else:
                    self.root.after(0, lambda: self.training_status_var.set("❌ 训练或导出失败"))
                self._last_eta_epoch = None
                self._last_eta_total = None
                if hasattr(self, "status_eta_var"):
                    self.root.after(0, lambda: self.status_eta_var.set("预计完成: --"))
                self.is_training = False
                self.root.after(0, self.update_training_button_state)

                # 仅在训练+导出均完成时通知
                if saw_success_marker and not saw_failed_marker:
                    self.root.after(0, self._notify_training_complete)
                
            except Exception as e:
                error_msg = str(e)
                self.root.after(0, lambda msg=error_msg: self.training_status_var.set(f"训练失败: {msg}"))
                self.root.after(0, lambda msg=error_msg: self.log_message(f"训练失败: {msg}"))
                self._last_eta_epoch = None
                self._last_eta_total = None
                if hasattr(self, "status_eta_var"):
                    self.root.after(0, lambda: self.status_eta_var.set("预计完成: --"))
                self.is_training = False
                self.root.after(0, self.update_training_button_state)
        
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
                    self.root.after(0, self.update_training_button_state)
                    
                    # 停止系统监控
                    self.root.after(0, self.stop_system_monitoring)
                    
                    self.root.after(0, lambda: self.training_status_var.set("已停止"))
                    self._last_eta_epoch = None
                    self._last_eta_total = None
                    if hasattr(self, "status_eta_var"):
                        self.root.after(0, lambda: self.status_eta_var.set("预计完成: --"))
                    self.root.after(0, lambda: self.log_message("训练已停止"))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"停止训练失败: {e}"))
            
            threading.Thread(target=stop_thread, daemon=True).start()

    def clear_remote_dataset(self):
        """清空云端数据集"""
        if not self.is_connected:
            messagebox.showerror("错误", "请先连接服务器")
            return

        # 确认对话框
        if not messagebox.askyesno(
            "确认清空",
            "确定要清空云端数据集吗？\n\n"
            f"路径: {self.remote_path_var.get()}\n\n"
            "⚠️ 此操作不可恢复！",
            icon='warning'
        ):
            return

        self.log_message("正在清空云端数据集...")

        def clear_thread():
            try:
                remote_path = self.remote_path_var.get()

                # 检查远程路径是否存在
                check_cmd = f"test -d {remote_path} && echo 'EXISTS' || echo 'NOT_EXISTS'"
                stdin, stdout, stderr = self.ssh_client.exec_command(check_cmd)
                result = stdout.read().decode().strip()

                if result != 'EXISTS':
                    self.root.after(0, lambda: messagebox.showinfo("提示", "云端数据集路径不存在，无需清空"))
                    self.root.after(0, lambda: self.log_message("云端数据集路径不存在"))
                    return

                # 清空数据集目录（保留目录本身，删除内容）
                clear_cmd = f"rm -rf {remote_path}/*"
                stdin, stdout, stderr = self.ssh_client.exec_command(clear_cmd)
                error = stderr.read().decode().strip()

                if error and "No such file or directory" not in error:
                    raise Exception(f"清空失败: {error}")

                self.root.after(0, lambda: messagebox.showinfo("成功", "云端数据集已清空"))
                self.root.after(0, lambda: self.log_message("✅ 云端数据集已清空"))

                # 更新显示
                self.root.after(0, self.update_dataset_status_display)

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("错误", f"清空云端数据集失败: {e}"))
                self.root.after(0, lambda: self.log_message(f"❌ 清空云端数据集失败: {e}"))

        threading.Thread(target=clear_thread, daemon=True).start()

    def update_dataset_status_display(self):
        """更新数据集状态显示"""
        # 更新本地数据集状态
        try:
            local_path = self.local_path_var.get()
            if os.path.exists(local_path):
                # 统计图片数量
                image_count = 0
                for split in ['train', 'val', 'test']:
                    images_dir = os.path.join(local_path, split, 'images')
                    if os.path.exists(images_dir):
                        image_count += len([f for f in os.listdir(images_dir) if f.endswith(('.jpg', '.jpeg', '.png', '.bmp'))])
                self.local_image_count_var.set(f"图片数: {image_count}")
                self.local_dataset_status_var.set("状态: ✅ 已就绪")
            else:
                self.local_image_count_var.set("图片数: -")
                self.local_dataset_status_var.set("状态: ❌ 路径不存在")
        except Exception:
            self.local_image_count_var.set("图片数: -")
            self.local_dataset_status_var.set("状态: 未检查")

        # 更新云端数据集状态
        if self.is_connected:
            def check_remote():
                try:
                    remote_path = self.remote_path_var.get()
                    check_cmd = f"test -d {remote_path} && echo 'EXISTS' || echo 'NOT_EXISTS'"
                    stdin, stdout, stderr = self.ssh_client.exec_command(check_cmd)
                    result = stdout.read().decode().strip()

                    if result == 'EXISTS':
                        # 统计云端图片数量
                        count_cmd = f"find {remote_path} -type f \\( -name '*.jpg' -o -name '*.jpeg' -o -name '*.png' -o -name '*.bmp' \\) | wc -l"
                        stdin, stdout, stderr = self.ssh_client.exec_command(count_cmd)
                        remote_count = stdout.read().decode().strip()
                        self.remote_image_count_var.set(f"图片数: {remote_count}")
                        self.remote_dataset_path_var.set(f"路径: {remote_path}")
                    else:
                        self.remote_image_count_var.set("图片数: 0")
                        self.remote_dataset_path_var.set("路径: -")
                except Exception:
                    self.remote_image_count_var.set("图片数: -")
                    self.remote_dataset_path_var.set("路径: -")

            threading.Thread(target=check_remote, daemon=True).start()
        else:
            self.remote_image_count_var.set("图片数: -")
            self.remote_dataset_path_var.set("路径: 未连接")

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
        sftp = None
        try:
            sftp = ssh.open_sftp()
            # 搜索多个可能的路径，包括 /root/runs/train 和 /root/runs/detect/runs/train
            cmd = (
                'find /root/runs -type f \\( '
                '-name "best.pt" -o -name "best_*.pt" -o '
                '-name "best.onnx" -o -name "best_*.onnx" -o '
                '-name "best*.tflite" -o -name "*_*.zip" '
                '\\) -printf "%T@|%s|%p\\n" 2>/dev/null | sort -t"|" -k1,1nr'
            )
            stdin, stdout, stderr = ssh.exec_command(cmd)
            output = stdout.read().decode('utf-8', errors='ignore').strip()
            if not output:
                return model_info
            for line in output.splitlines():
                line = line.strip()
                if not line or '|' not in line:
                    continue
                parts = line.split('|', 2)
                if len(parts) != 3:
                    continue
                mtime_text, size_text, file_path = parts
                try:
                    mtime = float(mtime_text)
                except Exception:
                    mtime = 0.0
                try:
                    size_bytes = int(float(size_text))
                except Exception:
                    size_bytes = 0
                parent_dir = os.path.dirname(file_path)
                if os.path.basename(parent_dir) == 'weights':
                    run_root = os.path.dirname(parent_dir)
                else:
                    run_root = parent_dir
                run_dir = os.path.basename(run_root.rstrip('/')) or '-'
                args_path = f"{run_root}/args.yaml"
                args_data = {}
                try:
                    with sftp.open(args_path, 'r') as rf:
                        raw = rf.read()
                    if isinstance(raw, bytes):
                        raw = raw.decode('utf-8', errors='ignore')
                    parsed = yaml.safe_load(raw) or {}
                    if isinstance(parsed, dict):
                        args_data = parsed
                except Exception:
                    args_data = {}
                image_size = args_data.get('imgsz', args_data.get('img_size', '-'))
                base_model_raw = args_data.get('model', '-')
                base_model_name = os.path.basename(str(base_model_raw)) if base_model_raw not in (None, '') else '-'
                model_scale = self._model_profile(base_model_name).upper() if base_model_name != '-' else '-'
                base_model_display = f"{base_model_name} ({model_scale})" if base_model_name != '-' else '-'
                epochs = args_data.get('epochs', '-')
                batch = args_data.get('batch', '-')
                lr0 = args_data.get('lr0', args_data.get('lr', '-'))
                patience = args_data.get('patience', '-')
                optimizer = args_data.get('optimizer', '-')
                model_info.append({
                    'name': os.path.basename(file_path) or 'best.pt',
                    'path': file_path,
                    'size': self._format_bytes_text(size_bytes),
                    'size_bytes': size_bytes,
                    'date': datetime.fromtimestamp(max(0.0, mtime)).strftime("%Y-%m-%d %H:%M:%S"),
                    'mtime': mtime,
                    'run_dir': run_dir,
                    'image_size': image_size,
                    'base_model': base_model_display,
                    'base_model_name': base_model_name,
                    'model_scale': model_scale,
                    'epochs': epochs,
                    'batch': batch,
                    'lr0': lr0,
                    'patience': patience,
                    'optimizer': optimizer
                })
            model_info.sort(key=lambda x: float(x.get('mtime') or 0.0), reverse=True)
        finally:
            if sftp:
                try:
                    sftp.close()
                except Exception:
                    pass
            ssh.close()
        return model_info
    
    def show_model_selection_window(self, model_info, query_window):
        query_window.destroy()
        
        if not model_info:
            messagebox.showinfo("信息", "服务器上未找到可下载的模型文件（pt/onnx/tflite/zip）")
            return
        
        selection_window = tk.Toplevel(self.root)
        selection_window.title("选择要下载的模型文件")
        selection_window.geometry("1220x620")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        selection_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))
        
        title_frame = ttk.Frame(selection_window)
        title_frame.pack(fill='x', padx=20, pady=10)
        
        ttk.Label(title_frame, text="选择要下载的模型文件", font=("Arial", 14, "bold")).pack()
        ttk.Label(title_frame, text="💾 支持 .pt / .onnx / .tflite / .zip 多选批量下载（下载到同一目录，自动命名）", 
                 font=("Arial", 10), foreground="blue").pack(pady=5)
        
        list_frame = ttk.Frame(selection_window)
        list_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        columns = ('run_dir', 'imgsz', 'base_model', 'epochs', 'batch', 'lr0', 'patience', 'optimizer', 'date', 'size')
        model_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', selectmode='extended')
        model_tree.heading('#0', text='模型文件')
        model_tree.heading('run_dir', text='运行目录')
        model_tree.heading('imgsz', text='分辨率')
        model_tree.heading('base_model', text='基础模型')
        model_tree.heading('epochs', text='epochs')
        model_tree.heading('batch', text='batch')
        model_tree.heading('lr0', text='lr0')
        model_tree.heading('patience', text='patience')
        model_tree.heading('optimizer', text='optimizer')
        model_tree.heading('date', text='生成时间')
        model_tree.heading('size', text='文件大小')
        model_tree.column('#0', width=130, anchor='w')
        model_tree.column('run_dir', width=190, anchor='w')
        model_tree.column('imgsz', width=70, anchor='center')
        model_tree.column('base_model', width=170, anchor='w')
        model_tree.column('epochs', width=65, anchor='center')
        model_tree.column('batch', width=65, anchor='center')
        model_tree.column('lr0', width=80, anchor='center')
        model_tree.column('patience', width=80, anchor='center')
        model_tree.column('optimizer', width=100, anchor='center')
        model_tree.column('date', width=150, anchor='center')
        model_tree.column('size', width=90, anchor='center')
        tree_scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=model_tree.yview)
        model_tree.configure(yscrollcommand=tree_scrollbar.set)
        model_tree.pack(side='left', fill='both', expand=True)
        tree_scrollbar.pack(side='right', fill='y')
        
        model_map = {}
        for idx, model in enumerate(model_info):
            item_id = f"model_{idx}"
            model_map[item_id] = model
            model_tree.insert(
                '',
                'end',
                iid=item_id,
                text=(model.get('name') or 'best.pt'),
                values=(
                    model.get('run_dir', '-'),
                    model.get('image_size', '-'),
                    model.get('base_model', '-'),
                    model.get('epochs', '-'),
                    model.get('batch', '-'),
                    model.get('lr0', '-'),
                    model.get('patience', '-'),
                    model.get('optimizer', '-'),
                    model.get('date', '-'),
                    model.get('size', '-')
                )
            )
        
        control_frame = ttk.Frame(selection_window)
        control_frame.pack(fill='x', padx=20, pady=10)
        left_btn_frame = ttk.Frame(control_frame)
        left_btn_frame.pack(side='left')
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side='right')

        def select_all():
            ids = model_tree.get_children('')
            if ids:
                model_tree.selection_set(ids)

        def clear_selection():
            model_tree.selection_remove(model_tree.selection())

        ttk.Button(left_btn_frame, text="全选", command=select_all).pack(side='left', padx=5)
        ttk.Button(left_btn_frame, text="清空选择", command=clear_selection).pack(side='left', padx=5)
        
        def start_download():
            selected_items = model_tree.selection()
            if not selected_items:
                messagebox.showwarning("警告", "请至少选择一个模型文件")
                return
            selected_models = []
            for item_id in selected_items:
                m = model_map.get(item_id)
                if m:
                    selected_models.append(m)
            if not selected_models:
                return
            initial_dir = self.dataset_config.get('local_path') or os.getcwd()
            if not os.path.isdir(initial_dir):
                initial_dir = os.getcwd()
            output_dir = filedialog.askdirectory(
                title="选择模型保存目录（批量下载）",
                initialdir=initial_dir
            )
            if not output_dir:
                return
            selection_window.destroy()
            self.download_models_batch(selected_models, output_dir)
        
        ttk.Button(button_frame, text="下载所选模型", command=start_download).pack(side='right', padx=5)
        ttk.Button(button_frame, text="取消", command=selection_window.destroy).pack(side='right', padx=5)
    
    def _format_bytes_text(self, size_bytes):
        value = float(max(0, size_bytes))
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        while value >= 1024 and idx < len(units) - 1:
            value /= 1024.0
            idx += 1
        return f"{value:.1f}{units[idx]}"

    def _build_download_model_filename(self, model_name, image_size, model_scale, timestamp, run_dir=""):
        base = os.path.basename(model_name)
        stem, ext = os.path.splitext(base)
        if not ext:
            ext = ".pt"
        # ZIP 为训练完整包，优先保留远端原始命名（例如 命名_时间戳.zip）
        if ext.lower() == ".zip":
            safe_zip = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in base) or f"model_{timestamp}.zip"
            return safe_zip
        safe_stem = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in stem) or "best"
        safe_run = "".join(ch if str(ch).isalnum() or ch in ("-", "_") else "_" for ch in str(run_dir or "run")) or "run"
        safe_img = "".join(ch if str(ch).isalnum() or ch in ("-", "_") else "_" for ch in str(image_size if image_size not in (None, "") else "-")) or "-"
        safe_scale = "".join(ch if str(ch).isalnum() or ch in ("-", "_") else "_" for ch in str(model_scale if model_scale not in (None, "") else "-")) or "-"
        return f"{safe_run}__{safe_stem}__img{safe_img}__{safe_scale}__{timestamp}{ext}"

    def download_single_model(self, selected_model, local_file):
        progress_window = tk.Toplevel(self.root)
        progress_window.title("下载模型")
        progress_window.geometry("600x240")
        progress_window.transient(self.root)
        progress_window.grab_set()

        progress_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))

        remote_path = selected_model.get('path', '')
        model_name = selected_model.get('name') or os.path.basename(remote_path) or "best.pt"
        tk.Label(progress_window, text=f"正在下载: {model_name}", font=("Arial", 10)).pack(pady=10)

        progress_var = tk.DoubleVar()
        progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100, length=540)
        progress_bar.pack(pady=10)

        status_label = tk.Label(progress_window, text="准备下载...", font=("Arial", 9))
        status_label.pack(pady=5)

        cancel_flag = {'cancelled': False}

        def cancel_download():
            cancel_flag['cancelled'] = True
            try:
                progress_window.destroy()
            except Exception:
                pass

        cancel_btn = ttk.Button(progress_window, text="取消", command=cancel_download)
        cancel_btn.pack(pady=5)

        def download_thread():
            ssh = None
            sftp = None
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
                sftp = ssh.open_sftp()
                last_ui_time = 0.0
                try:
                    total_bytes = int(sftp.stat(remote_path).st_size)
                except Exception:
                    total_bytes = 0
                file_start_ts = time.time()
                file_last_ts = file_start_ts
                file_last_bytes = 0

                def progress_cb(transferred, total):
                    nonlocal last_ui_time, file_last_ts, file_last_bytes
                    if cancel_flag['cancelled']:
                        raise RuntimeError("用户取消下载")
                    now_ts = time.time()
                    dt = max(now_ts - file_last_ts, 1e-6)
                    speed = (transferred - file_last_bytes) / dt
                    file_last_ts = now_ts
                    file_last_bytes = transferred
                    if now_ts - last_ui_time < 0.2 and transferred < total:
                        return
                    last_ui_time = now_ts
                    denom = max(total_bytes, total, 1)
                    percent = min(100.0, (max(0, transferred) * 100.0 / denom))
                    progress_text = f"{self._format_bytes_text(transferred)}/{self._format_bytes_text(denom)}"
                    speed_text = f"{self._format_bytes_text(speed)}/s"
                    self.root.after(0, lambda p=percent: progress_var.set(p))
                    self.root.after(0, lambda pct=percent, txt=progress_text, spd=speed_text: status_label.config(text=f"下载中 {pct:.1f}%  {spd}  {txt}"))

                sftp.get(remote_path, local_file, callback=progress_cb)
                if cancel_flag['cancelled']:
                    self.root.after(0, lambda: self.log_message("下载已取消"))
                    return
                self.root.after(0, lambda: progress_var.set(100.0))
                self.root.after(0, lambda: status_label.config(text="下载完成"))
                self.root.after(0, lambda f=os.path.basename(local_file): self.log_message(f"模型下载完成: {f}"))
                self.root.after(0, lambda p=local_file: self.log_message(f"保存路径: {p}"))
                self.root.after(3000, progress_window.destroy)
            except Exception as e:
                self.root.after(0, lambda: self.log_message(f"下载模型失败: {e}"))
                self.root.after(0, progress_window.destroy)
            finally:
                if sftp:
                    try:
                        sftp.close()
                    except Exception:
                        pass
                if ssh:
                    try:
                        ssh.close()
                    except Exception:
                        pass

        threading.Thread(target=download_thread, daemon=True).start()

    def _ensure_unique_local_file(self, local_file):
        if not os.path.exists(local_file):
            return local_file
        base, ext = os.path.splitext(local_file)
        idx = 1
        while True:
            candidate = f"{base}_{idx}{ext}"
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def download_models_batch(self, selected_models, output_dir):
        progress_window = tk.Toplevel(self.root)
        progress_window.title("批量下载模型")
        progress_window.geometry("700x300")
        progress_window.transient(self.root)
        progress_window.grab_set()
        progress_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))

        total_count = len(selected_models)
        tk.Label(progress_window, text=f"准备批量下载 {total_count} 个模型文件", font=("Arial", 10)).pack(pady=10)

        overall_var = tk.DoubleVar()
        ttk.Label(progress_window, text="总体进度").pack()
        overall_bar = ttk.Progressbar(progress_window, variable=overall_var, maximum=100, length=640)
        overall_bar.pack(pady=5)

        current_var = tk.DoubleVar()
        ttk.Label(progress_window, text="当前文件进度").pack()
        current_bar = ttk.Progressbar(progress_window, variable=current_var, maximum=100, length=640)
        current_bar.pack(pady=5)

        status_label = tk.Label(progress_window, text="准备连接服务器...", font=("Arial", 9))
        status_label.pack(pady=8)
        result_label = tk.Label(progress_window, text="0/0", font=("Arial", 9))
        result_label.pack(pady=2)

        cancel_flag = {'cancelled': False}

        def cancel_download():
            cancel_flag['cancelled'] = True
            status_label.config(text="正在取消...")

        ttk.Button(progress_window, text="取消", command=cancel_download).pack(pady=6)

        def batch_thread():
            ssh = None
            sftp = None
            ok_count = 0
            fail_count = 0
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
                sftp = ssh.open_sftp()

                for idx, model in enumerate(selected_models, start=1):
                    if cancel_flag['cancelled']:
                        break
                    remote_path = model.get('path', '')
                    if not remote_path:
                        fail_count += 1
                        continue
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    default_filename = self._build_download_model_filename(
                        model.get('name', 'best.pt'),
                        model.get('image_size', '-'),
                        model.get('model_scale', '-'),
                        timestamp,
                        model.get('run_dir', '')
                    )
                    local_file = self._ensure_unique_local_file(os.path.join(output_dir, default_filename))
                    model_name = model.get('name') or os.path.basename(remote_path) or 'best.pt'
                    self.root.after(0, lambda i=idx, t=total_count, n=model_name: status_label.config(text=f"下载中 [{i}/{t}] {n}"))
                    self.root.after(0, lambda i=idx, t=total_count: overall_var.set(((i - 1) * 100.0) / max(1, t)))
                    self.root.after(0, lambda: current_var.set(0.0))

                    file_size = 0
                    try:
                        file_size = int(sftp.stat(remote_path).st_size)
                    except Exception:
                        file_size = 0

                    last_ui_time = 0.0

                    def progress_cb(transferred, total):
                        nonlocal last_ui_time
                        if cancel_flag['cancelled']:
                            raise RuntimeError("用户取消下载")
                        now_ts = time.time()
                        if now_ts - last_ui_time < 0.2 and transferred < total:
                            return
                        last_ui_time = now_ts
                        denom = max(file_size, total, 1)
                        pct = min(100.0, (max(0, transferred) * 100.0 / denom))
                        self.root.after(0, lambda p=pct: current_var.set(p))

                    try:
                        sftp.get(remote_path, local_file, callback=progress_cb)
                        ok_count += 1
                        self.root.after(0, lambda f=os.path.basename(local_file): self.log_message(f"模型下载完成: {f}"))
                        self.root.after(0, lambda p=local_file: self.log_message(f"保存路径: {p}"))
                    except Exception as e:
                        fail_count += 1
                        self.root.after(0, lambda n=model_name, err=str(e): self.log_message(f"下载失败: {n} -> {err}"))

                    self.root.after(0, lambda i=idx, t=total_count, o=ok_count, f=fail_count: result_label.config(text=f"{i}/{t}  成功{o}  失败{f}"))
                    self.root.after(0, lambda i=idx, t=total_count: overall_var.set((i * 100.0) / max(1, t)))

                if cancel_flag['cancelled']:
                    self.root.after(0, lambda: status_label.config(text="已取消批量下载"))
                else:
                    self.root.after(0, lambda: status_label.config(text="批量下载完成"))
                self.root.after(0, lambda o=ok_count, f=fail_count: messagebox.showinfo("下载完成", f"批量下载完成\n成功: {o}\n失败: {f}\n目录: {output_dir}"))
            except Exception as e:
                self.root.after(0, lambda err=str(e): messagebox.showerror("错误", f"批量下载失败: {err}"))
            finally:
                if sftp:
                    try:
                        sftp.close()
                    except Exception:
                        pass
                if ssh:
                    try:
                        ssh.close()
                    except Exception:
                        pass
                self.root.after(0, lambda: current_var.set(0 if cancel_flag['cancelled'] else current_var.get()))

        threading.Thread(target=batch_thread, daemon=True).start()
    
    def handle_model_query_error(self, error_msg, query_window):
        """处理模型查询错误"""
        query_window.destroy()
        messagebox.showerror("错误", f"查询模型文件失败:\n{error_msg}")
    
    def init_monitoring_charts(self):
        """初始化监控图表"""
        # 设置中文字体（必须在style之前）
        plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        plt.style.use('seaborn-v0_8-darkgrid')
        chart_width, chart_height = 3.0, 1.5
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

        self.monitoring_figures['loss'] = Figure(figsize=(6.2, 2.2), dpi=80)
        self.monitoring_figures['loss'].patch.set_facecolor('white')
        ax_loss = self.monitoring_figures['loss'].add_subplot(111)
        ax_loss.set_title('Loss曲线', fontsize=10)
        ax_loss.set_xlabel('Epoch', fontsize=8)
        ax_loss.set_ylabel('Loss', fontsize=8)
        ax_loss.grid(True, alpha=0.3)
        ax_loss.tick_params(axis='both', which='major', labelsize=7)
        self.monitoring_canvases['loss'] = FigureCanvasTkAgg(self.monitoring_figures['loss'], self.loss_frame)
        self.monitoring_canvases['loss'].get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.update_monitoring_charts()

    def open_monitor_fullscreen(self):
        """打开监控大屏弹窗"""
        if not self.is_connected:
            messagebox.showwarning("提示", "请先连接服务器")
            return

        # 创建弹窗
        monitor_window = tk.Toplevel(self.root)
        monitor_window.title("训练监控大屏")
        monitor_window.geometry("1200x800")
        monitor_window.transient(self.root)
        monitor_window.grab_set()

        # 居中显示
        monitor_window.geometry("+%d+%d" % (
            self.root.winfo_rootx() + 50,
            self.root.winfo_rooty() + 50
        ))

        # 顶部工具栏
        toolbar = ttk.Frame(monitor_window)
        toolbar.pack(fill='x', padx=10, pady=5)
        ttk.Button(toolbar, text="🔙 返回", command=monitor_window.destroy, bootstyle="secondary").pack(side='left')
        ttk.Label(toolbar, text="训练监控大屏", font=("Arial", 14, "bold")).pack(side='left', padx=20)
        
        # 大屏标题栏状态显示
        fullscreen_header_status = tk.StringVar(value="未开始")
        fullscreen_header_duration = tk.StringVar(value="时长: 00:00:00")
        fullscreen_header_eta = tk.StringVar(value="预计完成: --")
        ttk.Label(toolbar, textvariable=fullscreen_header_status, font=("Arial", 11, "bold"), foreground="#007bff").pack(side='left', padx=10)
        ttk.Label(toolbar, textvariable=fullscreen_header_duration, font=("Arial", 11)).pack(side='left', padx=5)
        ttk.Label(toolbar, textvariable=fullscreen_header_eta, font=("Arial", 11)).pack(side='left', padx=5)

        # 三图容器
        charts_frame = ttk.Frame(monitor_window)
        charts_frame.pack(fill='both', expand=True, padx=10, pady=5)
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)
        charts_frame.rowconfigure(0, weight=1)
        charts_frame.rowconfigure(1, weight=2)  # Loss曲线占更多空间

        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

        # GPU利用率 (左上)
        gpu_util_frame = ttk.Labelframe(charts_frame, text="GPU利用率", padding=5)
        gpu_util_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        fig_gpu_util = Figure(figsize=(6, 3.5), dpi=100)
        fig_gpu_util.patch.set_facecolor('white')
        ax_gpu_util = fig_gpu_util.add_subplot(111)
        ax_gpu_util.set_ylabel('利用率 (%)', fontsize=10)
        ax_gpu_util.set_ylim(0, 100)
        ax_gpu_util.grid(True, alpha=0.3)
        ax_gpu_util.tick_params(axis='both', which='major', labelsize=8)
        canvas_gpu_util = FigureCanvasTkAgg(fig_gpu_util, gpu_util_frame)
        canvas_gpu_util.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # GPU显存 (右上)
        gpu_mem_frame = ttk.Labelframe(charts_frame, text="GPU显存使用率", padding=5)
        gpu_mem_frame.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        fig_gpu_mem = Figure(figsize=(6, 3.5), dpi=100)
        fig_gpu_mem.patch.set_facecolor('white')
        ax_gpu_mem = fig_gpu_mem.add_subplot(111)
        ax_gpu_mem.set_ylabel('使用率 (%)', fontsize=10)
        ax_gpu_mem.set_ylim(0, 100)
        ax_gpu_mem.grid(True, alpha=0.3)
        ax_gpu_mem.tick_params(axis='both', which='major', labelsize=8)
        canvas_gpu_mem = FigureCanvasTkAgg(fig_gpu_mem, gpu_mem_frame)
        canvas_gpu_mem.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Loss曲线 (下方，跨两列)
        loss_frame = ttk.Labelframe(charts_frame, text="Loss曲线", padding=5)
        loss_frame.grid(row=1, column=0, columnspan=2, sticky='nsew', padx=5, pady=5)

        fig_loss = Figure(figsize=(12, 5), dpi=100)
        fig_loss.patch.set_facecolor('white')
        ax_loss = fig_loss.add_subplot(111)
        ax_loss.set_xlabel('Epoch', fontsize=10)
        ax_loss.set_ylabel('Loss', fontsize=10)
        ax_loss.grid(True, alpha=0.3)
        ax_loss.tick_params(axis='both', which='major', labelsize=8)
        canvas_loss = FigureCanvasTkAgg(fig_loss, loss_frame)
        canvas_loss.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # 底部状态栏
        status_bar = ttk.Frame(monitor_window)
        status_bar.pack(fill='x', padx=10, pady=5)

        fullscreen_status_var = tk.StringVar(value="状态: 未开始")
        fullscreen_duration_var = tk.StringVar(value="时长: 00:00:00")
        fullscreen_eta_var = tk.StringVar(value="预计完成: --")
        fullscreen_loss_var = tk.StringVar(value="当前Loss: -")

        ttk.Label(status_bar, textvariable=fullscreen_status_var, font=("Arial", 10)).pack(side='left', padx=10)
        ttk.Label(status_bar, textvariable=fullscreen_duration_var, font=("Arial", 10)).pack(side='left', padx=10)
        ttk.Label(status_bar, textvariable=fullscreen_eta_var, font=("Arial", 10)).pack(side='left', padx=10)
        ttk.Label(status_bar, textvariable=fullscreen_loss_var, font=("Arial", 10)).pack(side='left', padx=10)

        # 存储大屏图表引用
        self.fullscreen_figures = {
            'gpu_util': (fig_gpu_util, ax_gpu_util, canvas_gpu_util),
            'gpu_mem': (fig_gpu_mem, ax_gpu_mem, canvas_gpu_mem),
            'loss': (fig_loss, ax_loss, canvas_loss)
        }
        self.fullscreen_status_vars = {
            'status': fullscreen_status_var,
            'duration': fullscreen_duration_var,
            'eta': fullscreen_eta_var,
            'loss': fullscreen_loss_var,
            'header_status': fullscreen_header_status,
            'header_duration': fullscreen_header_duration,
            'header_eta': fullscreen_header_eta
        }

        # 启动大屏更新循环
        self.start_fullscreen_update(monitor_window)

    def start_fullscreen_update(self, window):
        """启动大屏实时更新"""
        def update_loop():
            try:
                if not window.winfo_exists():
                    return

                # 更新GPU利用率图表 - 使用与主界面相同的数据源
                if hasattr(self, 'gpu_utilization_data') and self.gpu_utilization_data:
                    fig, ax, canvas = self.fullscreen_figures['gpu_util']
                    ax.clear()
                    ax.set_title('GPU利用率', fontsize=10)
                    ax.set_ylabel('利用率 (%)', fontsize=10)
                    ax.set_ylim(0, 100)
                    ax.grid(True, alpha=0.3)
                    time_range = list(range(len(self.gpu_utilization_data)))
                    ax.plot(time_range, list(self.gpu_utilization_data), 'orange', linewidth=2, label='GPU利用率')
                    ax.fill_between(time_range, list(self.gpu_utilization_data), alpha=0.3, color='orange')
                    ax.legend(loc='upper right')
                    canvas.draw()

                # 更新GPU显存图表
                if hasattr(self, 'gpu_memory_data') and self.gpu_memory_data:
                    fig, ax, canvas = self.fullscreen_figures['gpu_mem']
                    ax.clear()
                    ax.set_title('GPU显存使用率', fontsize=10)
                    ax.set_ylabel('使用率 (%)', fontsize=10)
                    ax.set_ylim(0, 100)
                    ax.grid(True, alpha=0.3)
                    time_range = list(range(len(self.gpu_memory_data)))
                    ax.plot(time_range, list(self.gpu_memory_data), 'b-', linewidth=2, label='显存使用率')
                    ax.fill_between(time_range, list(self.gpu_memory_data), alpha=0.3, color='blue')
                    ax.legend(loc='upper right')
                    canvas.draw()

                # 更新Loss曲线 - 使用与主界面相同的数据源
                if hasattr(self, 'loss_epoch_data') and self.loss_epoch_data:
                    fig, ax, canvas = self.fullscreen_figures['loss']
                    ax.clear()
                    ax.set_title('Loss曲线', fontsize=10)
                    ax.set_xlabel('Epoch', fontsize=10)
                    ax.set_ylabel('Loss', fontsize=10)
                    ax.grid(True, alpha=0.3)

                    x = list(self.loss_epoch_data)
                    box_data = list(self.loss_box_data) if hasattr(self, 'loss_box_data') and self.loss_box_data else []
                    cls_data = list(self.loss_cls_data) if hasattr(self, 'loss_cls_data') and self.loss_cls_data else []
                    dfl_data = list(self.loss_dfl_data) if hasattr(self, 'loss_dfl_data') and self.loss_dfl_data else []

                    if box_data:
                        ax.plot(x, box_data, color='#ff7f0e', linewidth=2, marker='o', markersize=3, label='box')
                    if cls_data:
                        ax.plot(x, cls_data, color='#1f77b4', linewidth=2, marker='o', markersize=3, label='cls')
                    if dfl_data:
                        ax.plot(x, dfl_data, color='#2ca02c', linewidth=2, marker='o', markersize=3, label='dfl')
                    ax.legend(loc='upper left', fontsize=9)

                    # 大屏智能末端标注 - 避免重叠
                    end_values = []
                    if box_data:
                        end_values.append({'type': 'box', 'value': box_data[-1], 'x': x[-1], 'color': '#ff7f0e'})
                    if cls_data:
                        end_values.append({'type': 'cls', 'value': cls_data[-1], 'x': x[-1], 'color': '#1f77b4'})
                    if dfl_data:
                        end_values.append({'type': 'dfl', 'value': dfl_data[-1], 'x': x[-1], 'color': '#2ca02c'})

                    # 按值排序，让大的在上面
                    end_values.sort(key=lambda item: item['value'], reverse=True)

                    # 按像素间距动态避让，避免标签重叠
                    def _calc_adaptive_offsets(ax_obj, items, base_offset_pt=14.0, min_gap_px=16.0):
                        offsets = []
                        placed_y = []
                        px_per_pt = ax_obj.figure.dpi / 72.0
                        y_min_px = float(ax_obj.bbox.ymin)
                        y_max_px = float(ax_obj.bbox.ymax)
                        edge_margin_px = max(min_gap_px, 10.0)
                        for it in items:
                            try:
                                y_px = float(ax_obj.transData.transform((it['x'], it['value']))[1])
                            except Exception:
                                y_px = 0.0
                            label_y = y_px + base_offset_pt * px_per_pt
                            if placed_y:
                                max_allowed = placed_y[-1] - min_gap_px
                                if label_y > max_allowed:
                                    label_y = max_allowed
                            # 边界保护：避免标签超出绘图区被裁切
                            low = y_min_px + edge_margin_px
                            high = y_max_px - edge_margin_px
                            if high >= low:
                                label_y = min(max(label_y, low), high)
                            placed_y.append(label_y)
                            offsets.append((label_y - y_px) / px_per_pt)
                        return offsets

                    end_offsets = _calc_adaptive_offsets(ax, end_values, base_offset_pt=14.0, min_gap_px=18.0)
                    for i, item in enumerate(end_values):
                        y_offset = end_offsets[i] if i < len(end_offsets) else 0.0
                        ax.annotate(
                            f"{item['type']} {item['value']:.4f}",
                            xy=(item['x'], item['value']),
                            xytext=(12, y_offset),
                            textcoords='offset points',
                            color=item['color'],
                            fontsize=9,
                            fontweight='bold',
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=item['color'], alpha=0.8)
                        )

                    # 找到历史最低点（不包括最后一个点）
                    def find_min_except_last_fullscreen(xs, ys):
                        """找到历史最低点（不包括最后一个点）"""
                        n = min(len(xs), len(ys))
                        if n < 2:
                            return None, None
                        min_val = float('inf')
                        min_idx = -1
                        for idx in range(n - 1):  # 排除最后一个点
                            try:
                                yv = float(ys[idx])
                                if np.isfinite(yv) and yv < min_val:
                                    min_val = yv
                                    min_idx = idx
                            except Exception:
                                pass
                        if min_idx >= 0:
                            return xs[min_idx], min_val
                        return None, None

                    # 找到各曲线的历史最低点
                    min_box_x, min_box_val = find_min_except_last_fullscreen(x, box_data)
                    min_cls_x, min_cls_val = find_min_except_last_fullscreen(x, cls_data)
                    min_dfl_x, min_dfl_val = find_min_except_last_fullscreen(x, dfl_data)

                    # 标注历史最低点（灰色虚线框）
                    min_values = []
                    if min_box_x is not None and min_box_val is not None:
                        min_values.append({'type': 'box', 'value': min_box_val, 'x': min_box_x, 'color': '#ff7f0e'})
                    if min_cls_x is not None and min_cls_val is not None:
                        min_values.append({'type': 'cls', 'value': min_cls_val, 'x': min_cls_x, 'color': '#1f77b4'})
                    if min_dfl_x is not None and min_dfl_val is not None:
                        min_values.append({'type': 'dfl', 'value': min_dfl_val, 'x': min_dfl_x, 'color': '#2ca02c'})

                    # 按值排序
                    min_values.sort(key=lambda item: item['value'], reverse=True)

                    # 标注历史最低点（高对比 + 动态避让）
                    min_offsets = _calc_adaptive_offsets(ax, min_values, base_offset_pt=16.0, min_gap_px=20.0)
                    for i, item in enumerate(min_values):
                        # 先给最低点打一个醒目标记，避免文字重叠时找不到点
                        ax.plot(
                            [item['x']], [item['value']],
                            marker='o', markersize=5.5,
                            markerfacecolor='white',
                            markeredgecolor=item['color'],
                            markeredgewidth=1.6,
                            linestyle='None',
                            zorder=6
                        )
                        y_offset = min_offsets[i] if i < len(min_offsets) else 0.0
                        ax.annotate(
                            f"min:{item['value']:.4f}",
                            xy=(item['x'], item['value']),
                            xytext=(6, y_offset),
                            textcoords='offset points',
                            color='#111111',
                            fontsize=8.5,
                            ha='left',
                            va='bottom',
                            fontweight='bold',
                            bbox=dict(
                                boxstyle='round,pad=0.24',
                                facecolor='white',
                                edgecolor=item['color'],
                                linewidth=1.2,
                                alpha=0.95
                            ),
                            zorder=7
                        )

                    canvas.draw()

                # 更新状态栏
                if hasattr(self, 'training_status_var'):
                    status_text = self.training_status_var.get()
                    self.fullscreen_status_vars['status'].set(status_text)
                    # 同步到标题栏
                    self.fullscreen_status_vars['header_status'].set(status_text)
                if hasattr(self, 'status_duration_var'):
                    duration_text = self.status_duration_var.get()
                    self.fullscreen_status_vars['duration'].set(duration_text)
                    # 同步到标题栏
                    self.fullscreen_status_vars['header_duration'].set(duration_text)
                if hasattr(self, 'status_eta_var'):
                    eta_text = self.status_eta_var.get()
                    self.fullscreen_status_vars['eta'].set(eta_text)
                    self.fullscreen_status_vars['header_eta'].set(eta_text)
                # 计算当前总loss
                total_loss = 0
                loss_count = 0
                if hasattr(self, 'loss_box_data') and self.loss_box_data:
                    total_loss += self.loss_box_data[-1]
                    loss_count += 1
                if hasattr(self, 'loss_cls_data') and self.loss_cls_data:
                    total_loss += self.loss_cls_data[-1]
                    loss_count += 1
                if hasattr(self, 'loss_dfl_data') and self.loss_dfl_data:
                    total_loss += self.loss_dfl_data[-1]
                    loss_count += 1
                if loss_count > 0:
                    self.fullscreen_status_vars['loss'].set(f"当前Loss: {total_loss:.4f}")

                # 继续更新
                window.after(1000, update_loop)

            except Exception as e:
                logging.warning(f"大屏更新失败: {e}")
                if window.winfo_exists():
                    window.after(2000, update_loop)

        update_loop()

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
                
                now = time.time()
                if now - self._last_monitor_log >= 10:
                    self._last_monitor_log = now
                
                current_time = time.time()
                self.time_data.append(current_time)
                self.gpu_utilization_data.append(gpu_util)
                self.gpu_memory_data.append(gpu_memory)

                
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
            
            ax_loss = self.monitoring_figures['loss'].axes[0]
            ax_loss.clear()
            ax_loss.set_title('Loss曲线', fontsize=10)
            ax_loss.set_xlabel('Epoch', fontsize=8)
            ax_loss.set_ylabel('Loss', fontsize=8)
            ax_loss.grid(True, alpha=0.3)
            ax_loss.tick_params(axis='both', which='major', labelsize=7)
            if self.loss_epoch_data:
                x = list(self.loss_epoch_data)
                box_y = list(self.loss_box_data)
                cls_y = list(self.loss_cls_data)
                dfl_y = list(self.loss_dfl_data)
                if box_y:
                    ax_loss.plot(x, box_y, color='#ff7f0e', linewidth=1.6, marker='o', markersize=2, label='box')
                if cls_y:
                    ax_loss.plot(x, cls_y, color='#1f77b4', linewidth=1.6, marker='o', markersize=2, label='cls')
                if dfl_y:
                    ax_loss.plot(x, dfl_y, color='#2ca02c', linewidth=1.6, marker='o', markersize=2, label='dfl')

                def latest_valid_point(xs, ys):
                    n = min(len(xs), len(ys))
                    for idx in range(n - 1, -1, -1):
                        try:
                            xv = float(xs[idx])
                            yv = float(ys[idx])
                            if np.isfinite(xv) and np.isfinite(yv):
                                return xs[idx], yv
                        except Exception:
                            pass
                    return None, None

                def find_min_except_last(xs, ys):
                    """找到历史最低点（不包括最后一个点）"""
                    n = min(len(xs), len(ys))
                    if n < 2:
                        return None, None
                    min_val = float('inf')
                    min_idx = -1
                    for idx in range(n - 1):  # 排除最后一个点
                        try:
                            yv = float(ys[idx])
                            if np.isfinite(yv) and yv < min_val:
                                min_val = yv
                                min_idx = idx
                        except Exception:
                            pass
                    if min_idx >= 0:
                        return xs[min_idx], min_val
                    return None, None

                latest_epoch = None
                try:
                    latest_epoch = int(float(x[-1])) if x else None
                except Exception:
                    latest_epoch = None

                x_box, v_box = latest_valid_point(x, box_y)
                x_cls, v_cls = latest_valid_point(x, cls_y)
                x_dfl, v_dfl = latest_valid_point(x, dfl_y)

                # 找到历史最低点（不包括最后一个点）
                min_box_x, min_box_val = find_min_except_last(x, box_y)
                min_cls_x, min_cls_val = find_min_except_last(x, cls_y)
                min_dfl_x, min_dfl_val = find_min_except_last(x, dfl_y)

                # 智能标注 - 收集所有有效值并排序
                end_values = []
                if x_box is not None and v_box is not None:
                    end_values.append({'type': 'box', 'value': v_box, 'x': x_box, 'color': '#ff7f0e'})
                if x_cls is not None and v_cls is not None:
                    end_values.append({'type': 'cls', 'value': v_cls, 'x': x_cls, 'color': '#1f77b4'})
                if x_dfl is not None and v_dfl is not None:
                    end_values.append({'type': 'dfl', 'value': v_dfl, 'x': x_dfl, 'color': '#2ca02c'})

                # 按值排序，让大的在上面
                end_values.sort(key=lambda item: item['value'], reverse=True)

                # 按像素间距动态避让，避免标签重叠
                def _calc_adaptive_offsets(ax_obj, items, base_offset_pt=9.0, min_gap_px=12.0):
                    offsets = []
                    placed_y = []
                    px_per_pt = ax_obj.figure.dpi / 72.0
                    y_min_px = float(ax_obj.bbox.ymin)
                    y_max_px = float(ax_obj.bbox.ymax)
                    edge_margin_px = max(min_gap_px, 8.0)
                    for it in items:
                        try:
                            y_px = float(ax_obj.transData.transform((it['x'], it['value']))[1])
                        except Exception:
                            y_px = 0.0
                        label_y = y_px + base_offset_pt * px_per_pt
                        if placed_y:
                            max_allowed = placed_y[-1] - min_gap_px
                            if label_y > max_allowed:
                                label_y = max_allowed
                        # 边界保护：避免标签超出绘图区被裁切
                        low = y_min_px + edge_margin_px
                        high = y_max_px - edge_margin_px
                        if high >= low:
                            label_y = min(max(label_y, low), high)
                        placed_y.append(label_y)
                        offsets.append((label_y - y_px) / px_per_pt)
                    return offsets

                end_offsets = _calc_adaptive_offsets(ax_loss, end_values, base_offset_pt=9.0, min_gap_px=14.0)
                for i, item in enumerate(end_values):
                    y_offset = end_offsets[i] if i < len(end_offsets) else 0.0
                    ax_loss.annotate(
                        f"{item['type']} {item['value']:.4f}",
                        xy=(item['x'], item['value']),
                        xytext=(8, y_offset),
                        textcoords='offset points',
                        color=item['color'],
                        fontsize=7,
                        fontweight='bold',
                        bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=item['color'], alpha=0.7)
                    )

                # 标注历史最低点（灰色虚线框）
                min_values = []
                if min_box_x is not None and min_box_val is not None:
                    min_values.append({'type': 'box', 'value': min_box_val, 'x': min_box_x, 'color': '#ff7f0e'})
                if min_cls_x is not None and min_cls_val is not None:
                    min_values.append({'type': 'cls', 'value': min_cls_val, 'x': min_cls_x, 'color': '#1f77b4'})
                if min_dfl_x is not None and min_dfl_val is not None:
                    min_values.append({'type': 'dfl', 'value': min_dfl_val, 'x': min_dfl_x, 'color': '#2ca02c'})

                # 按值排序
                min_values.sort(key=lambda item: item['value'], reverse=True)

                # 标注历史最低点（高对比 + 动态避让）
                min_offsets = _calc_adaptive_offsets(ax_loss, min_values, base_offset_pt=11.0, min_gap_px=16.0)
                for i, item in enumerate(min_values):
                    ax_loss.plot(
                        [item['x']], [item['value']],
                        marker='o', markersize=4.2,
                        markerfacecolor='white',
                        markeredgecolor=item['color'],
                        markeredgewidth=1.2,
                        linestyle='None',
                        zorder=6
                    )
                    y_offset = min_offsets[i] if i < len(min_offsets) else 0.0
                    ax_loss.annotate(
                        f"min:{item['value']:.4f}",
                        xy=(item['x'], item['value']),
                        xytext=(5, y_offset),
                        textcoords='offset points',
                        color='#111111',
                        fontsize=7,
                        ha='left',
                        va='bottom',
                        fontweight='bold',
                        bbox=dict(
                            boxstyle='round,pad=0.18',
                            facecolor='white',
                            edgecolor=item['color'],
                            linewidth=1.0,
                            alpha=0.95
                        ),
                        zorder=7
                    )

                total_vals = [v for v in [v_box, v_cls, v_dfl] if v is not None and np.isfinite(v)]
                total_loss = sum(total_vals) if total_vals else None
                if latest_epoch is not None:
                    panel_text = f"Epoch: {latest_epoch}"
                    if total_loss is not None:
                        panel_text += f"\n总loss: {total_loss:.4f}"
                    ax_loss.text(
                        0.98, 0.98, panel_text,
                        transform=ax_loss.transAxes,
                        ha='right', va='top',
                        fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.25', facecolor='white', edgecolor='#999999', alpha=0.9)
                    )
                ax_loss.legend(loc='upper left', fontsize=7)
            self.monitoring_canvases['loss'].draw()

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

    def _reset_loss_tracking(self):
        self.loss_epoch_data.clear()
        self.loss_box_data.clear()
        self.loss_cls_data.clear()
        self.loss_dfl_data.clear()
        self.last_loss_epoch = -1

    def _calc_eta_text(self, current_epoch, total_epochs):
        """根据当前轮次估算完成时间（ETA）"""
        try:
            if not hasattr(self, "training_start_time") or not self.training_start_time:
                return "预计完成: --"
            if not current_epoch or not total_epochs or total_epochs <= 0:
                return "预计完成: --"
            progress = float(current_epoch) / float(total_epochs)
            if progress <= 0:
                return "预计完成: --"
            elapsed = max(0.0, time.time() - float(self.training_start_time))
            remain = max(0.0, elapsed * (1.0 / progress - 1.0))
            eta_ts = time.time() + remain
            eta_text = datetime.fromtimestamp(eta_ts).strftime("%H:%M:%S")
            return f"预计完成: {eta_text}"
        except Exception:
            return "预计完成: --"

    def _update_training_progress(self):
        try:
            if not self.ssh_client:
                return
            status_text = None
            current_epoch = None
            total_epochs = None
            parsed_run_dir = None
            if self.training_log_file:
                stdin, stdout, stderr = self.ssh_client.exec_command(f'tail -n 200 {self.training_log_file} 2>/dev/null || echo ""')
                content = stdout.read().decode('utf-8', errors='ignore')
                if content:
                    ansi = re.compile(r'\x1B\[[0-9;]*[A-Za-z]')
                    text = ansi.sub('', content)
                    self._last_training_log_text = text
                    m_run = re.search(r'(?:Logging results to|Results saved to)\s+([^\s]+)', text)
                    if m_run:
                        raw_path = (m_run.group(1) or '').strip().rstrip('.,;')
                        if raw_path.endswith('/'):
                            raw_path = raw_path[:-1]
                        if raw_path.endswith('results.csv'):
                            raw_path = os.path.dirname(raw_path)
                        if raw_path.startswith('/'):
                            parsed_run_dir = raw_path
                        else:
                            idx = raw_path.find('runs/')
                            if idx >= 0:
                                rel = raw_path[idx:]
                                parsed_run_dir = f'/root/{rel}'
                        if parsed_run_dir and self.training_run_name and (self.training_run_name not in parsed_run_dir):
                            parsed_run_dir = None
                    m_total = re.search(r'Starting training for\s+(\d+)\s+epochs', text)
                    total_epochs = int(m_total.group(1)) if m_total else total_epochs
                    if total_epochs is None:
                        m_total_args = re.search(r'epochs=(\d+)', text)
                        total_epochs = int(m_total_args.group(1)) if m_total_args else total_epochs
                    m_epoch_rows = re.findall(r'^\s*(\d+)\s*/\s*(\d+)\s+', text, flags=re.MULTILINE)
                    if m_epoch_rows:
                        try:
                            current_epoch = max(int(x[0]) for x in m_epoch_rows)
                            if total_epochs is None:
                                total_epochs = int(m_epoch_rows[-1][1])
                        except:
                            pass
                    m_step = re.search(r'(\d+)%\|.*?(\d+)/(\d+)', text)
                    if m_step:
                        if total_epochs and current_epoch:
                            status_text = f"训练中: {current_epoch}/{total_epochs}"
                    elif total_epochs and current_epoch:
                        status_text = f"训练中: {current_epoch}/{total_epochs}"
            if parsed_run_dir and parsed_run_dir != self.training_run_dir:
                self.training_run_dir = parsed_run_dir
                self._run_dir_logged = False
                self._reset_loss_tracking()
            if not self.training_run_dir:
                stdin, stdout, stderr = self.ssh_client.exec_command('ls -1t /root/runs/*/*/results.csv 2>/dev/null | head -n 1')
                latest_results = stdout.read().decode('utf-8', errors='ignore').strip()
                if latest_results:
                    self.training_run_dir = os.path.dirname(latest_results.replace('\\', '/'))
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
                        current_epoch = ep
                        if total_ep:
                            total_epochs = total_ep
                            status_text = f"训练中: {ep}/{total_ep}"
                        else:
                            status_text = f"训练中: {ep}"
                    except:
                        pass
            try:
                self._update_loss_curves_from_log(self._last_training_log_text)
            except Exception:
                pass
            self._update_loss_curves_from_results(expected_epoch=current_epoch)
            epoch_text = None
            if total_epochs or current_epoch is not None:
                if total_epochs:
                    epoch_text = f"Epoch: {current_epoch if current_epoch is not None else 0}/{total_epochs}"
                else:
                    epoch_text = f"Epoch: {current_epoch}/?"
            if status_text:
                self.root.after(0, lambda s=status_text: self.training_status_var.set(s))
            # 更新时长（不再依赖 epoch_text，避免解析短暂失败导致时长卡住）
            if hasattr(self, "status_duration_var") and hasattr(self, "training_start_time") and self.training_start_time and self.is_training:
                duration = time.time() - self.training_start_time
                m, s = divmod(int(duration), 60)
                h, m = divmod(m, 60)
                duration_text = f"时长: {h:02d}:{m:02d}:{s:02d}"
                self.root.after(0, lambda s=duration_text: self.status_duration_var.set(s))
            # 更新预计完成时间
            if hasattr(self, "status_eta_var"):
                if total_epochs is None:
                    try:
                        cfg_epochs = int(self.training_config.get('epochs'))
                        if cfg_epochs > 0:
                            total_epochs = cfg_epochs
                    except Exception:
                        pass
                # 兜底：若本轮未从日志解析到epoch，尝试从状态文本反解析（如“训练中: 19/300”）
                status_candidates = []
                if status_text:
                    status_candidates.append(str(status_text))
                if hasattr(self, "training_status_var"):
                    try:
                        status_candidates.append(str(self.training_status_var.get()))
                    except Exception:
                        pass
                for status_now in status_candidates:
                    if current_epoch is not None and total_epochs is not None:
                        break
                    m_ct = re.search(r'(\d+)\s*/\s*(\d+)', status_now)
                    if not m_ct:
                        continue
                    try:
                        parsed_cur = int(m_ct.group(1))
                        parsed_total = int(m_ct.group(2))
                        if parsed_cur > 0 and parsed_total > 0:
                            if current_epoch is None:
                                current_epoch = parsed_cur
                            if total_epochs is None:
                                total_epochs = parsed_total
                    except Exception:
                        continue
                # 缓存最近一次有效轮次，避免单次解析失败导致 ETA 回退为 --
                if current_epoch is not None and total_epochs is not None and current_epoch > 0 and total_epochs > 0:
                    self._last_eta_epoch = int(current_epoch)
                    self._last_eta_total = int(total_epochs)
                else:
                    cached_epoch = getattr(self, "_last_eta_epoch", None)
                    cached_total = getattr(self, "_last_eta_total", None)
                    if cached_epoch is not None and cached_total is not None and cached_epoch > 0 and cached_total > 0:
                        current_epoch = cached_epoch
                        total_epochs = cached_total
                eta_text = self._calc_eta_text(current_epoch, total_epochs)
                self.root.after(0, lambda s=eta_text: self.status_eta_var.set(s))

            if epoch_text:
                if hasattr(self, "current_epoch_var"):
                    self.root.after(0, lambda s=epoch_text: self.current_epoch_var.set(s))
        except:
            pass

    def _update_loss_curves_from_results(self, expected_epoch=None):
        if not self.ssh_client or not self.training_run_dir:
            return False
        def fetch_results_tail(run_dir):
            cmd_tail = f'tail -n 200 {run_dir}/results.csv 2>/dev/null'
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd_tail)
            return stdout.read().decode('utf-8', errors='ignore')

        out = fetch_results_tail(self.training_run_dir)
        if not out or ',' not in out:
            if self.training_run_name:
                return False
            stdin, stdout, stderr = self.ssh_client.exec_command('ls -1t /root/runs/*/*/results.csv 2>/dev/null | head -n 1')
            latest_results = stdout.read().decode('utf-8', errors='ignore').strip()
            if latest_results:
                new_run_dir = os.path.dirname(latest_results.replace('\\', '/'))
                if new_run_dir and new_run_dir != self.training_run_dir:
                    self.training_run_dir = new_run_dir
                    self._run_dir_logged = False
                    self._reset_loss_tracking()
                    out = fetch_results_tail(self.training_run_dir)
        if not out or ',' not in out:
            return False
        try:
            import io
            import csv
            reader = csv.reader(io.StringIO(out))
            rows = []
            for row in reader:
                clean_row = [str(c).strip() for c in row]
                if any(c for c in clean_row):
                    rows.append(clean_row)
            if not rows or len(rows) <= 1:
                return False
            header = [str(x).strip() for x in rows[0]]
            last = rows[-1]
        except Exception:
            return False
        if not header or not last:
            return False
        if len(last) < len(header):
            last.extend([''] * (len(header) - len(last)))
        row_map = {}
        for i, key in enumerate(header):
            if i < len(last):
                row_map[key.strip().lower()] = last[i]
        epoch_keys = ['epoch']
        box_keys = ['train/box_loss', 'box_loss']
        cls_keys = ['train/cls_loss', 'cls_loss']
        dfl_keys = ['train/dfl_loss', 'dfl_loss']
        def find_key(candidates, contains=None):
            for k in candidates:
                if k in row_map:
                    return k
            if contains:
                for k in row_map.keys():
                    if contains in k:
                        return k
            return None
        epoch = None
        epoch_key = find_key(epoch_keys)
        if epoch_key:
            try:
                epoch = int(float((row_map.get(epoch_key) or '').strip()))
            except Exception:
                epoch = None
        if epoch is None:
            try:
                epoch = int(float((last[0] or '').strip()))
            except Exception:
                epoch = None
        if epoch is None:
            return False
        if expected_epoch is not None:
            try:
                ep_now = int(expected_epoch)
                if epoch > ep_now + 2:
                    return False
            except Exception:
                pass
        if self.last_loss_epoch >= 0 and epoch < self.last_loss_epoch:
            if (self.last_loss_epoch - epoch) >= 5:
                self._reset_loss_tracking()
            else:
                return False
        def pick_float(keys, contains=None):
            key = find_key(keys, contains=contains)
            if key:
                try:
                    return float((row_map.get(key) or '').strip())
                except Exception:
                    pass
            return None
        box_loss = pick_float(box_keys, contains='box_loss')
        cls_loss = pick_float(cls_keys, contains='cls_loss')
        dfl_loss = pick_float(dfl_keys, contains='dfl_loss')
        if box_loss is None and cls_loss is None and dfl_loss is None:
            return False
        if epoch == self.last_loss_epoch and self.loss_epoch_data:
            try:
                if self.loss_box_data:
                    self.loss_box_data[-1] = box_loss if box_loss is not None else float('nan')
                if self.loss_cls_data:
                    self.loss_cls_data[-1] = cls_loss if cls_loss is not None else float('nan')
                if self.loss_dfl_data:
                    self.loss_dfl_data[-1] = dfl_loss if dfl_loss is not None else float('nan')
            except Exception:
                pass
        else:
            self.loss_epoch_data.append(epoch)
            self.loss_box_data.append(box_loss if box_loss is not None else float('nan'))
            self.loss_cls_data.append(cls_loss if cls_loss is not None else float('nan'))
            self.loss_dfl_data.append(dfl_loss if dfl_loss is not None else float('nan'))
        self.last_loss_epoch = epoch
        return True

    def _update_loss_curves_from_log(self, text):
        if not text:
            return False
        try:
            ansi = re.compile(r'\x1B\[[0-9;]*[A-Za-z]')
        except Exception:
            ansi = None
        def to_float(v):
            try:
                return float(v)
            except Exception:
                return None
        lines = text.splitlines()
        for line in reversed(lines):
            s = (line or '').strip()
            if not s:
                continue
            if ansi:
                try:
                    s = ansi.sub('', s)
                except Exception:
                    pass
            parts = s.split()
            if not parts:
                continue
            m = re.match(r'^(\d+)\s*/\s*(\d+)$', parts[0])
            if not m:
                m = re.match(r'^(\d+)/(\d+)$', parts[0])
            if not m:
                continue
            if len(parts) < 5:
                continue
            epoch = None
            try:
                epoch = int(m.group(1))
            except Exception:
                epoch = None
            if epoch is None:
                continue
            box = to_float(parts[2])
            cls = to_float(parts[3])
            dfl = to_float(parts[4])
            if box is None or cls is None or dfl is None:
                continue
            if self.last_loss_epoch >= 0 and epoch < self.last_loss_epoch:
                if (self.last_loss_epoch - epoch) >= 5:
                    self._reset_loss_tracking()
                else:
                    return False
            if epoch == self.last_loss_epoch and self.loss_epoch_data:
                try:
                    if self.loss_box_data:
                        self.loss_box_data[-1] = box
                    if self.loss_cls_data:
                        self.loss_cls_data[-1] = cls
                    if self.loss_dfl_data:
                        self.loss_dfl_data[-1] = dfl
                except Exception:
                    pass
                return True
            self.loss_epoch_data.append(epoch)
            self.loss_box_data.append(box)
            self.loss_cls_data.append(cls)
            self.loss_dfl_data.append(dfl)
            self.last_loss_epoch = epoch
            return True
        return False
    
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
            package_frame = ttk.Labelframe(main_frame, text="选择安装包", padding="10")
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
            options_frame = ttk.Labelframe(main_frame, text="安装选项", padding="10")
            options_frame.pack(fill=tk.X, pady=(0, 10))
            
            self.force_reinstall_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="强制重新安装", 
                           variable=self.force_reinstall_var).pack(anchor=tk.W)
            
            self.no_deps_var = tk.BooleanVar()
            ttk.Checkbutton(options_frame, text="不安装依赖", 
                           variable=self.no_deps_var).pack(anchor=tk.W)
            
            # 进度显示
            progress_frame = ttk.Labelframe(main_frame, text="安装进度", padding="10")
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
    
    def _normalize_training_log_message(self, message):
        text = str(message)
        ansi = re.compile(r'\x1B\[[0-9;]*[A-Za-z]')
        text = ansi.sub('', text)
        if text.startswith("[训练]"):
            body = text[4:].strip()
            if '\r' in body:
                body = body.split('\r')[-1].strip()
            body = re.sub(r'\s+', ' ', body)
            if not body:
                return None
            if ("it/s" in body or "%|" in body) and ("100%|" not in body) and ("Epoch" not in body) and ("Class" not in body):
                return None
            if body == self._last_training_compact_line:
                return None
            self._last_training_compact_line = body
            return f"[训练] {body}"
        return text.replace('\r', ' ').strip()

    def _detect_log_level(self, message):
        """根据消息内容自动识别日志级别"""
        msg = message.lower()
        if any(k in msg for k in ['成功', '完成', '通过', '✅', '已就绪', '验收通过']):
            return 'success'
        if any(k in msg for k in ['失败', '错误', '异常', '❌', '超时', '拒绝', '无法']):
            return 'error'
        if any(k in msg for k in ['警告', '注意', '⚠️', '缺失', '跳过']):
            return 'warning'
        if any(k in msg for k in ['训练', 'epoch', 'loss', '📊', '进度', '轮次', 'box_loss', 'cls_loss', 'dfl_loss']):
            return 'training'
        if any(k in msg for k in ['连接', '服务器', 'ssh', '🔧', '系统', '环境']):
            return 'system'
        return 'info'

    def log_message(self, message, level=None):
        """
        记录日志消息，支持颜色区分
        level: 'success', 'error', 'warning', 'info', 'training', 'system'
               None则自动识别
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        normalized = self._normalize_training_log_message(message)
        if not normalized:
            return

        # 自动识别颜色级别
        if level is None:
            level = self._detect_log_level(normalized)

        # 颜色映射
        color_map = {
            'success': '#28a745',  # 绿色
            'error': '#dc3545',    # 红色
            'warning': '#fd7e14',  # 橙色
            'training': '#007bff', # 蓝色
            'system': '#6f42c1',   # 紫色
            'info': '#212529',     # 黑色
        }

        log_entry = f"[{timestamp}] {normalized}\n"

        # 插入文本
        self.log_text.insert(tk.END, log_entry)

        # 为刚插入的行设置颜色tag
        start_idx = self.log_text.index("end-2l linestart")
        end_idx = self.log_text.index("end-1c")
        self.log_text.tag_add(level, start_idx, end_idx)
        self.log_text.tag_config(level, foreground=color_map.get(level, '#212529'))

        self.log_text.see(tk.END)

        if hasattr(self, 'status_var'):
            self.status_var.set(normalized)

        self.logger.info(normalized)

def main():
    root = ttk.Window(title="云端训练脚本优化管理平台", themename="cosmo", size=(1200, 800))
    # 设置全局字体
    default_font = ('Microsoft YaHei', 10)
    root.option_add("*Font", default_font)
    style = ttk.Style()
    style.configure('.', font=default_font)
    app = CloudTrainingGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
