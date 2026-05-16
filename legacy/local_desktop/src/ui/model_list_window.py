import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk


class ModelListWindow:
    """服务器模型列表窗口：查询、下载、删除、TFLite 转换统一入口。"""

    COLUMNS = ("name", "ext", "run", "model", "imgsz", "epochs", "batch", "lr", "size", "date", "path")
    HEADINGS = {
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
    EXT_TAGS = {
        ".pt": "ext_pt",
        ".onnx": "ext_onnx",
        ".tflite": "ext_tflite",
        ".zip": "ext_zip",
    }

    def __init__(
        self,
        parent,
        model_manager,
        model_download_manager,
        environment_manager,
        config_manager,
        log_callback=None,
        get_tflite_format_fn=None,
    ):
        self.parent = parent
        self.model_manager = model_manager
        self.model_download_manager = model_download_manager
        self.environment_manager = environment_manager
        self.config_manager = config_manager
        self.log_callback = log_callback
        self.get_tflite_format_fn = get_tflite_format_fn

        self._busy = False
        self._model_by_item = {}

        self.win = tk.Toplevel(parent)
        self.win.title("服务器模型列表")
        self.win.geometry("1380x760")
        self.win.transient(parent)
        self.win.focus_force()
        self._center_to_parent()
        self.win.after(0, self._center_to_parent)
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)

        self._create_ui()
        self.refresh()

    def _center_to_parent(self):
        self.parent.update_idletasks()
        self.win.update_idletasks()
        pw = self.parent.winfo_width()
        ph = self.parent.winfo_height()
        px = self.parent.winfo_rootx()
        py = self.parent.winfo_rooty()
        ww = self.win.winfo_width() or self.win.winfo_reqwidth()
        wh = self.win.winfo_height() or self.win.winfo_reqheight()
        x = px + max(0, (pw - ww) // 2)
        y = py + max(0, (ph - wh) // 2)
        self.win.geometry(f"+{x}+{y}")

    def _create_ui(self):
        ttk.Label(self.win, text="服务器模型列表", font=("Arial", 14, "bold")).pack(pady=(10, 6))

        list_frame = ttk.Frame(self.win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(list_frame, columns=self.COLUMNS, show="headings", selectmode="extended")
        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADINGS[col])
            self.tree.column(col, width=120, minwidth=80, stretch=False)

        self.tree.tag_configure("ext_pt", background="#dbeafe")
        self.tree.tag_configure("ext_onnx", background="#fef3c7")
        self.tree.tag_configure("ext_tflite", background="#fee2e2")
        self.tree.tag_configure("ext_zip", background="#dcfce7")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<<TreeviewSelect>>", self._update_action_buttons)

        action_frame = ttk.Frame(self.win)
        action_frame.pack(fill="x", padx=10, pady=(0, 6))

        self.status_var = tk.StringVar(value="状态: 准备就绪")
        self.detail_var = tk.StringVar(value="详情: -")
        self.speed_var = tk.StringVar(value="速度: -")
        self.progress_var = tk.DoubleVar(value=0)

        status_line = ttk.Frame(self.win)
        status_line.pack(fill="x", padx=10, pady=(0, 2))
        ttk.Label(status_line, textvariable=self.status_var).pack(side="left")
        ttk.Label(status_line, textvariable=self.speed_var).pack(side="right")

        self.progress_bar = ttk.Progressbar(self.win, variable=self.progress_var, maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", padx=10, pady=(0, 4))
        ttk.Label(self.win, textvariable=self.detail_var).pack(fill="x", padx=10, pady=(0, 6))

        self.log_text = tk.Text(self.win, height=8, wrap="word")
        self.log_text.pack(fill="both", expand=False, padx=10, pady=(0, 10))

        self.refresh_btn = ttk.Button(action_frame, text="刷新列表", bootstyle="secondary", command=self.refresh)
        self.download_btn = ttk.Button(action_frame, text="下载选中", bootstyle="success", command=self._start_download)
        self.delete_btn = ttk.Button(action_frame, text="删除模型", bootstyle="danger", command=self._delete_selected)
        self.convert_btn = ttk.Button(action_frame, text="TFLite转换", bootstyle="warning", command=self._convert_selected)
        self.close_btn = ttk.Button(action_frame, text="关闭", bootstyle="secondary", command=self._on_close)

        self.refresh_btn.pack(side="left", padx=(0, 6))
        self.download_btn.pack(side="left", padx=(0, 6))
        self.delete_btn.pack(side="left", padx=(0, 6))
        self.convert_btn.pack(side="left", padx=(0, 6))
        self.close_btn.pack(side="right")
        self._update_action_buttons()

    def exists(self):
        return bool(self.win and self.win.winfo_exists())

    def lift(self):
        if self.exists():
            try:
                self.win.grab_set()
            except Exception:
                pass
            self.win.lift()
            self.win.focus_force()

    def _append_log(self, text):
        self.log_text.insert("end", f"{text}\n")
        self.log_text.see("end")

    def _set_busy(self, busy, status_text):
        self._busy = bool(busy)
        self.status_var.set(f"状态: {status_text}")
        self.refresh_btn.config(state="disabled" if busy else "normal")
        self.close_btn.config(state="disabled" if busy else "normal")
        self._update_action_buttons()

    def _set_progress_animating(self, animating):
        if animating:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start(12)
        else:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")

    def _selected_models(self):
        models = []
        for item in self.tree.selection():
            m = self._model_by_item.get(item)
            if m:
                models.append(m)
        return models

    def _update_action_buttons(self, *_):
        models = self._selected_models()
        has_selected = len(models) > 0
        can_convert = has_selected and all(str(m.get("ext", "")).lower() == ".pt" for m in models)
        normal_or_disabled = "disabled" if self._busy else "normal"
        self.download_btn.config(state=normal_or_disabled if has_selected else "disabled")
        self.delete_btn.config(state=normal_or_disabled if has_selected else "disabled")
        self.convert_btn.config(state=normal_or_disabled if can_convert else "disabled")

    def _auto_fit_columns(self):
        width_map = {c: max(90, len(self.HEADINGS[c]) * 16 + 24) for c in self.COLUMNS}
        for item in self.tree.get_children(""):
            vals = self.tree.item(item, "values")
            for idx, col in enumerate(self.COLUMNS):
                val = str(vals[idx]) if idx < len(vals) else ""
                width_map[col] = min(760, max(width_map[col], len(val) * 9 + 30))
        for col in self.COLUMNS:
            self.tree.column(col, width=width_map[col], minwidth=80, stretch=False)

    def _render_models(self, models):
        self._model_by_item.clear()
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        for m in models:
            ext = str(m.get("ext", "")).lower()
            tag = self.EXT_TAGS.get(ext, "")
            iid = self.tree.insert(
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
            self._model_by_item[iid] = m
        self._auto_fit_columns()
        self.detail_var.set(f"详情: 共 {len(models)} 个模型文件")
        self._update_action_buttons()

    def refresh(self):
        if self._busy:
            return
        self._set_busy(True, "正在快速查询模型...")
        self.speed_var.set("速度: -")
        self.progress_var.set(0)
        self.detail_var.set("详情: 扫描训练产物目录 /root/runs 与数据集/runs")

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
                    self._append_log(f"❌ 查询失败: {err}")
                    self.detail_var.set("详情: 查询失败")
                else:
                    self._render_models(models)
                    self._append_log(f"✓ 查询完成，共 {len(models)} 个文件")
                self._set_busy(False, "就绪")

            self.parent.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _start_download(self):
        if self._busy:
            return
        models = self._selected_models()
        if not models:
            messagebox.showwarning("提示", "请先选择要下载的模型", parent=self.win)
            return
        local_dir = filedialog.askdirectory(title="选择保存目录", parent=self.win)
        if not local_dir:
            return

        download_targets = [{"name": m.get("name", "unknown"), "path": m.get("path", "")} for m in models]
        self._set_busy(True, "下载中")
        self._append_log(f"开始下载，共 {len(download_targets)} 个文件 -> {local_dir}")

        def on_progress(event):
            event_type = event.get("type")
            if event_type == "item" and event.get("stage") == "downloading":
                self.progress_var.set(float(event.get("progress", 0.0)))
                self.speed_var.set(f"速度: {event.get('speed_text', '-')}")
                idx = int(event.get("index", 0))
                total = int(event.get("total", 0))
                name = event.get("name", "-")
                transferred = int(event.get("transferred", 0))
                total_size = int(event.get("total_size", 0))
                self.detail_var.set(
                    f"详情: 正在下载 {idx}/{total} {name} ({transferred}/{total_size} bytes)"
                )
            elif event_type == "item" and event.get("stage") == "finished":
                if event.get("success"):
                    self._append_log(f"✓ 下载成功: {event.get('local_path', '')}")
                else:
                    self._append_log(f"❌ 下载失败: {event.get('name', '-')} | {event.get('error', '未知错误')}")
            elif event_type == "finish":
                succ = int(event.get("success_count", 0))
                fail = int(event.get("fail_count", 0))
                self.progress_var.set(100 if fail == 0 else float(self.progress_var.get()))
                self.speed_var.set("速度: -")
                self.detail_var.set(f"详情: 下载完成，成功 {succ}，失败 {fail}")
                self._set_busy(False, "就绪")

        def worker():
            self.model_download_manager.download_models(
                download_targets,
                local_dir,
                progress_callback=lambda e: self.parent.after(0, lambda ev=e: on_progress(ev)),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _delete_selected(self):
        if self._busy:
            return
        models = self._selected_models()
        if not models:
            messagebox.showwarning("提示", "请先选择要删除的模型", parent=self.win)
            return
        paths = [m.get("path", "") for m in models if m.get("path")]
        if not paths:
            messagebox.showwarning("提示", "选中项缺少路径，无法删除", parent=self.win)
            return
        if not messagebox.askyesno("确认删除", f"确认删除选中的 {len(paths)} 个模型文件吗？", parent=self.win):
            return

        self._set_busy(True, "删除中")
        self.progress_var.set(0)
        self.speed_var.set("速度: -")
        self.detail_var.set(f"详情: 正在删除 {len(paths)} 个文件")

        def worker():
            success, msg = self.model_manager.remove_models(paths)

            def done():
                if success:
                    self._append_log(f"✓ {msg}")
                    self.progress_var.set(100)
                    self.refresh()
                else:
                    self._append_log(f"❌ 删除失败: {msg}")
                    self._set_busy(False, "就绪")

            self.parent.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _convert_selected(self):
        if self._busy:
            return
        models = self._selected_models()
        if not models:
            messagebox.showwarning("提示", "请先选择要转换的 .pt 模型", parent=self.win)
            return
        bad = [m.get("name", "") for m in models if str(m.get("ext", "")).lower() != ".pt"]
        if bad:
            messagebox.showwarning("提示", "仅支持选中的 .pt 模型进行转换", parent=self.win)
            return

        self._set_busy(True, "TFLite转换中")
        self.progress_var.set(0)
        self.detail_var.set(f"详情: 准备转换 {len(models)} 个 .pt 模型")
        self.speed_var.set("速度: -")

        def worker():
            preferred_export_python = self.config_manager.convert_config.get("python_export_cmd", "")
            python_cmd, ultra_ver = self.environment_manager.get_export_python_cmd(
                preferred_cmd=preferred_export_python,
                log_callback=lambda msg: self.parent.after(0, lambda m=msg: self._emit_log(m)),
            )
            if not python_cmd:
                self.parent.after(0, lambda: self._append_log("❌ 转换失败: 未找到可用转换环境"))
                self.parent.after(0, lambda: self.detail_var.set("详情: 转换环境不可用"))
                self.parent.after(0, lambda: self._set_busy(False, "就绪"))
                return

            if preferred_export_python != python_cmd:
                self.config_manager.convert_config["python_export_cmd"] = python_cmd
                self.config_manager.save_config()

            self.parent.after(
                0, lambda p=python_cmd, v=ultra_ver: self._append_log(f"使用转换环境: {p} | ultralytics={v or 'unknown'}")
            )
            total = len(models)
            success_count = 0

            for idx, m in enumerate(models, start=1):
                name = m.get("name", "unknown")
                remote_path = m.get("path", "")
                self.parent.after(
                    0,
                    lambda i=idx, t=total, n=name: self.detail_var.set(f"详情: 正在转换 {i}/{t} {n}"),
                )
                self.parent.after(0, lambda p=(idx - 1) / total * 100.0: self.progress_var.set(p))
                self.parent.after(0, lambda: self._set_progress_animating(True))

                tflite_format = "fp32"
                if self.get_tflite_format_fn:
                    try:
                        tflite_format = self.get_tflite_format_fn()
                    except Exception:
                        pass

                ok, msg = self.model_manager.convert_remote_model_to_tflite(
                    remote_model=remote_path,
                    python_cmd=python_cmd,
                    log_callback=lambda mm: self.parent.after(0, lambda mmm=mm: self._emit_log(mmm)),
                    tflite_format=tflite_format,
                )
                self.parent.after(0, lambda: self._set_progress_animating(False))
                if ok:
                    success_count += 1
                    self.parent.after(0, lambda n=name, mmsg=msg: self._append_log(f"✓ 转换成功: {n} | {mmsg}"))
                else:
                    self.parent.after(0, lambda n=name, mmsg=msg: self._append_log(f"❌ 转换失败: {n} | {mmsg}"))
                self.parent.after(0, lambda p=idx / total * 100.0: self.progress_var.set(p))

            def done():
                fail_count = total - success_count
                self._set_progress_animating(False)
                self.detail_var.set(f"详情: 转换完成，成功 {success_count}，失败 {fail_count}")
                self._set_busy(False, "就绪")
                self.refresh()

            self.parent.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def _emit_log(self, msg):
        if self.log_callback:
            self.log_callback(msg)

    def _on_close(self):
        try:
            self.win.grab_release()
        except Exception:
            pass
        if self.exists():
            self.win.destroy()
