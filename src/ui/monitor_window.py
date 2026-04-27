import math
import threading
import tkinter as tk
import tkinter.ttk as tk_ttk
from collections import deque

import matplotlib.pyplot as plt
import ttkbootstrap as ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


class MonitorWindow:
    """训练监控大屏窗口（支持历史曲线切换、滚动/全局显示）。"""

    def __init__(
        self,
        parent,
        monitor_manager,
        training_monitor_manager,
        ui,
        is_connected_fn,
        get_remote_dataset_path_fn,
        get_model_name_fn,
    ):
        self.parent = parent
        self.monitor_manager = monitor_manager
        self.training_monitor_manager = training_monitor_manager
        self.ui = ui
        self.is_connected_fn = is_connected_fn
        self.get_remote_dataset_path_fn = get_remote_dataset_path_fn
        self.get_model_name_fn = get_model_name_fn

        self.after_id = None
        self._status_busy = False
        self._loss_busy = False
        self._history_busy = False
        self._tick_count = 0
        self._display_mode = "rolling"  # rolling / global

        self.gpu_util_data = deque(maxlen=180)
        self.gpu_mem_data = deque(maxlen=180)
        self.loss_epoch_data = []
        self.loss_box_data = []
        self.loss_cls_data = []
        self.loss_dfl_data = []

        self._history_rows = []
        self._tree_row_to_path = {}
        self.selected_results_path = ""
        self._manual_history_selection = False
        self._suspend_history_event = False

        self.win = tk.Toplevel(parent)
        self.win.title("训练监控大屏")
        self.win.geometry("1380x840")
        self.win.transient(parent)
        try:
            self.win.attributes("-topmost", True)
        except Exception:
            pass
        self.win.grab_set()
        self.win.focus_force()

        self._set_window_position()
        self.win.after(0, self._set_window_position)
        self._create_ui()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.refresh()

    def _set_window_position(self):
        self.parent.update_idletasks()
        self.win.update_idletasks()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        win_w = self.win.winfo_width() or self.win.winfo_reqwidth()
        win_h = self.win.winfo_height() or self.win.winfo_reqheight()
        x = parent_x + max(0, (parent_w - win_w) // 2)
        y = parent_y + max(0, (parent_h - win_h) // 2)
        self.win.geometry(f"+{x}+{y}")

    def _create_ui(self):
        plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans"]
        plt.rcParams["axes.unicode_minus"] = False

        toolbar = ttk.Frame(self.win)
        toolbar.pack(fill="x", padx=10, pady=5)
        ttk.Button(toolbar, text="返回", command=self._on_close, bootstyle="secondary").pack(side="left")
        ttk.Label(toolbar, text="训练监控大屏", font=("Arial", 14, "bold")).pack(side="left", padx=20)

        self.header_status_var = tk.StringVar(value="未开始")
        self.header_duration_var = tk.StringVar(value="时长: 00:00:00")
        self.header_eta_var = tk.StringVar(value="预计完成: --")
        ttk.Label(toolbar, textvariable=self.header_status_var, font=("Arial", 11, "bold"), foreground="#007bff").pack(
            side="left", padx=10
        )
        ttk.Label(toolbar, textvariable=self.header_duration_var, font=("Arial", 11)).pack(side="left", padx=5)
        ttk.Label(toolbar, textvariable=self.header_eta_var, font=("Arial", 11)).pack(side="left", padx=5)

        content = ttk.Frame(self.win)
        content.pack(fill="both", expand=True, padx=10, pady=5)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=0) # 固定宽度
        content.rowconfigure(0, weight=1)

        charts_frame = ttk.Frame(content)
        charts_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        charts_frame.columnconfigure(0, weight=1)
        charts_frame.columnconfigure(1, weight=1)
        charts_frame.rowconfigure(0, weight=1)
        charts_frame.rowconfigure(1, weight=3)

        gpu_util_frame = ttk.Labelframe(charts_frame, text="GPU利用率", padding=5)
        gpu_util_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.fig_gpu_util = Figure(figsize=(5.2, 2.4), dpi=100)
        self.ax_gpu_util = self.fig_gpu_util.add_subplot(111)
        self.canvas_gpu_util = FigureCanvasTkAgg(self.fig_gpu_util, gpu_util_frame)
        self.canvas_gpu_util.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        gpu_mem_frame = ttk.Labelframe(charts_frame, text="GPU显存使用率", padding=5)
        gpu_mem_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.fig_gpu_mem = Figure(figsize=(5.2, 2.4), dpi=100)
        self.ax_gpu_mem = self.fig_gpu_mem.add_subplot(111)
        self.canvas_gpu_mem = FigureCanvasTkAgg(self.fig_gpu_mem, gpu_mem_frame)
        self.canvas_gpu_mem.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        loss_frame = ttk.Labelframe(charts_frame, text="Loss曲线", padding=5)
        loss_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
        # 将切换按钮叠加在 Loss 曲线容器内 (在 canvas 之后创建并置顶)
        self.mode_btn_var = tk.StringVar(value="[滚动] / 全局")
        self.mode_btn = tk.Button(
            loss_frame,
            textvariable=self.mode_btn_var,
            command=self._toggle_display_mode,
            font=("Arial", 9, "bold"),
            bg="#fdfdfd",        # 极浅背景
            fg="#007bff",        # 蓝色文字
            activebackground="#e9ecef", # 点击时背景
            activeforeground="#0056b3", # 点击时文字
            relief="flat",       # 扁平化，不突兀
            padx=6,
            pady=1,
            cursor="hand2",
            highlightthickness=0
        )
        # 紧贴右上角对齐标题栏高度
        self.mode_btn.place(relx=0.99, y=-2, anchor="ne") 
        self.mode_btn.lift()        
        self.fig_loss = Figure(figsize=(12, 6.6), dpi=100)
        self.ax_loss = self.fig_loss.add_subplot(111)
        self.canvas_loss = FigureCanvasTkAgg(self.fig_loss, loss_frame)
        self.canvas_loss_widget = self.canvas_loss.get_tk_widget()
        self.canvas_loss_widget.pack(fill=tk.BOTH, expand=True)

        # 将切换按钮叠加在 Loss 曲线容器内 (在 canvas 之后创建并置顶)
        self.mode_btn_var = tk.StringVar(value="[滚动] / 全局")
        self.mode_btn = tk.Button(
            loss_frame,
            textvariable=self.mode_btn_var,
            command=self._toggle_display_mode,
            font=("Arial", 9, "bold"),
            bg="#f8f9fa",
            fg="#0d6efd",
            relief="raised",
            padx=8,
            pady=2,
            cursor="hand2",
            highlightthickness=0
        )
        # 使用 place 叠加显示，relx/rely 设定位置，并调用 lift 确保在最上层
        self.mode_btn.place(relx=0.97, rely=0.08, anchor="ne")
        self.mode_btn.lift()

        history_frame = ttk.Labelframe(content, text="历史训练列表", padding=6, width=350)
        history_frame.grid(row=0, column=1, sticky="nsew")
        history_frame.grid_propagate(False) # 强制固定宽度
        history_frame.rowconfigure(1, weight=1)
        history_frame.columnconfigure(0, weight=1)

        self.history_hint_var = tk.StringVar(value="当前: 跟随最新")
        ttk.Label(history_frame, textvariable=self.history_hint_var, foreground="#0a7ea4", font=("Arial", 9)).grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )

        tree_frame = ttk.Frame(history_frame)
        tree_frame.grid(row=1, column=0, sticky="nsew")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.history_tree = tk_ttk.Treeview(
            tree_frame,
            columns=("run_name", "mtime"),
            show="headings",
            selectmode="browse",
        )
        self.history_tree.heading("run_name", text="训练目录")
        self.history_tree.heading("mtime", text="更新时间")
        self.history_tree.column("run_name", width=250, minwidth=200, stretch=False, anchor="w")
        self.history_tree.column("mtime", width=150, minwidth=150, stretch=False, anchor="center")
        self.history_tree.grid(row=0, column=0, sticky="nsew")
        self.history_tree.bind("<<TreeviewSelect>>", self._on_history_select)

        y_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.history_tree.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        self.history_tree.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.history_tree.xview)
        x_scroll.grid(row=1, column=0, sticky="ew")
        self.history_tree.configure(xscrollcommand=x_scroll.set)

        action_row = ttk.Frame(history_frame)
        action_row.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(action_row, text="刷新列表", command=self._refresh_history_async, bootstyle="secondary-outline").pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(action_row, text="跟随最新", command=self._follow_latest_history, bootstyle="info-outline").pack(side="left")

        status_bar = ttk.Frame(self.win)
        status_bar.pack(fill="x", padx=10, pady=5)
        self.status_var = tk.StringVar(value="状态: 未开始")
        self.duration_var = tk.StringVar(value="时长: 00:00:00")
        self.eta_var = tk.StringVar(value="预计完成: --")
        self.loss_var = tk.StringVar(value="当前Loss: -")
        ttk.Label(status_bar, textvariable=self.status_var, font=("Arial", 10)).pack(side="left", padx=10)
        ttk.Label(status_bar, textvariable=self.duration_var, font=("Arial", 10)).pack(side="left", padx=10)
        ttk.Label(status_bar, textvariable=self.eta_var, font=("Arial", 10)).pack(side="left", padx=10)
        ttk.Label(status_bar, textvariable=self.loss_var, font=("Arial", 10)).pack(side="left", padx=10)

        self._draw_gpu_util_chart()
        self._draw_gpu_mem_chart()
        self._draw_loss_chart()

    def _safe_get_text(self, var_name, default_value):
        var = getattr(self.ui, var_name, None)
        if var is None or not hasattr(var, "get"):
            return default_value
        try:
            return str(var.get())
        except Exception:
            return default_value

    def _safe_float(self, value):
        try:
            return float(value)
        except Exception:
            return None

    def _is_finite_number(self, value):
        v = self._safe_float(value)
        return v is not None and math.isfinite(v)

    def _toggle_display_mode(self):
        self._display_mode = "global" if self._display_mode == "rolling" else "rolling"
        if self._display_mode == "global":
            self.mode_btn_var.set("滚动 / [全局]")
        else:
            self.mode_btn_var.set("[滚动] / 全局")
        self._draw_loss_chart()

    def _follow_latest_history(self):
        self._manual_history_selection = False
        self.selected_results_path = ""
        self.history_hint_var.set("当前: 跟随最新")
        self._refresh_history_async()
        self._refresh_loss_async()

    def auto_follow_latest(self):
        """外部调用：强制切换到跟随最新模式并立即刷新"""
        if not self.exists():
            return
        self.win.after(0, self._follow_latest_history)

    def _sync_training_status(self):
        status_text = self._safe_get_text("training_status_var", "未开始")
        duration_text = self._safe_get_text("status_duration_var", "时长: 00:00:00")
        eta_text = self._safe_get_text("status_eta_var", "预计完成: --")
        self.header_status_var.set(status_text)
        self.header_duration_var.set(duration_text)
        self.header_eta_var.set(eta_text)
        self.status_var.set(f"状态: {status_text}")
        self.duration_var.set(duration_text)
        self.eta_var.set(eta_text)

    def _draw_gpu_util_chart(self):
        self.fig_gpu_util.clear()
        self.ax_gpu_util = self.fig_gpu_util.add_subplot(111)
        self.ax_gpu_util.set_ylabel("利用率 (%)", fontsize=10)
        self.ax_gpu_util.set_ylim(0, 100)
        self.ax_gpu_util.grid(True, alpha=0.3)
        self.ax_gpu_util.tick_params(axis="both", which="major", labelsize=8)
        if self.gpu_util_data:
            x = list(range(len(self.gpu_util_data)))
            y = list(self.gpu_util_data)
            self.ax_gpu_util.plot(x, y, color="orange", linewidth=2, label="GPU利用率")
            self.ax_gpu_util.fill_between(x, y, alpha=0.3, color="orange")
            self.ax_gpu_util.legend(loc="upper right")
        self.canvas_gpu_util.draw()

    def _draw_gpu_mem_chart(self):
        self.fig_gpu_mem.clear()
        self.ax_gpu_mem = self.fig_gpu_mem.add_subplot(111)
        self.ax_gpu_mem.set_ylabel("使用率 (%)", fontsize=10)
        self.ax_gpu_mem.set_ylim(0, 100)
        self.ax_gpu_mem.grid(True, alpha=0.3)
        self.ax_gpu_mem.tick_params(axis="both", which="major", labelsize=8)
        if self.gpu_mem_data:
            x = list(range(len(self.gpu_mem_data)))
            y = list(self.gpu_mem_data)
            self.ax_gpu_mem.plot(x, y, color="#1f77b4", linewidth=2, label="显存使用率")
            self.ax_gpu_mem.fill_between(x, y, alpha=0.3, color="#1f77b4")
            self.ax_gpu_mem.legend(loc="upper right")
        self.canvas_gpu_mem.draw()

    def _calc_label_positions(self, items, min_gap_px=18.0):
        if not items:
            return []
        bbox = self.ax_loss.bbox
        x_min_px = float(bbox.xmin)
        x_max_px = float(bbox.xmax)
        y_min_px = float(bbox.ymin)
        y_max_px = float(bbox.ymax)
        left_margin = 52.0
        right_margin = 52.0
        y_margin = 16.0
        base_dy = 12.0
        x_shift = 70.0

        placed_y = []
        positions = []
        for item in items:
            try:
                x_px, y_px = self.ax_loss.transData.transform((item["x"], item["value"]))
                x_px = float(x_px)
                y_px = float(y_px)
            except Exception:
                continue

            x_pref = x_px + x_shift
            if x_pref > (x_max_px - right_margin):
                x_pref = x_px - x_shift
            x_label_px = min(max(x_pref, x_min_px + left_margin), x_max_px - right_margin)

            y_label_px = y_px + base_dy
            if placed_y:
                max_allowed = placed_y[-1] - min_gap_px
                if y_label_px > max_allowed:
                    y_label_px = max_allowed
            low = y_min_px + y_margin
            high = y_max_px - y_margin
            if high >= low:
                y_label_px = min(max(y_label_px, low), high)

            placed_y.append(y_label_px)
            positions.append((item, x_label_px, y_label_px))
        return positions

    def _last_finite_point(self, xs, ys):
        n = min(len(xs), len(ys))
        for idx in range(n - 1, -1, -1):
            if self._is_finite_number(ys[idx]):
                return xs[idx], float(ys[idx])
        return None, None

    def _annotate_current_values(self, x, box_data, cls_data, dfl_data):
        meta = [
            ("box", box_data, "#ff7f0e"),
            ("cls", cls_data, "#1f77b4"),
            ("dfl", dfl_data, "#2ca02c"),
        ]
        current_points = []
        for name, series, color in meta:
            x_last, y_last = self._last_finite_point(x, series)
            if x_last is None or y_last is None:
                continue
            current_points.append({"name": name, "x": x_last, "value": y_last, "color": color})
        current_points.sort(key=lambda item: item["value"], reverse=True)
        label_positions = self._calc_label_positions(current_points, min_gap_px=18.0)
        if not label_positions:
            return
        inv = self.ax_loss.transData.inverted()
        for item, x_px, y_px in label_positions:
            try:
                x_text, y_text = inv.transform((x_px, y_px))
            except Exception:
                continue
            self.ax_loss.text(
                x_text,
                y_text,
                f"{item['name']} {item['value']:.4f}",
                color=item["color"],
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
                bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor=item["color"], alpha=0.9),
                zorder=6,
            )

    def _find_global_min(self, series):
        best = None
        for v in series or []:
            if not self._is_finite_number(v):
                continue
            fv = float(v)
            if best is None or fv < best:
                best = fv
        return best

    def _draw_min_summary_top(self):
        box_min = self._find_global_min(self.loss_box_data)
        cls_min = self._find_global_min(self.loss_cls_data)
        dfl_min = self._find_global_min(self.loss_dfl_data)
        summary_text = (
            "最低Loss | "
            f"box: {box_min:.4f}    " if box_min is not None else "最低Loss | box: --    "
        )
        summary_text += f"cls: {cls_min:.4f}    " if cls_min is not None else "cls: --    "
        summary_text += f"dfl: {dfl_min:.4f}" if dfl_min is not None else "dfl: --"
        self.ax_loss.text(
            0.01,
            1.02,
            summary_text,
            transform=self.ax_loss.transAxes,
            color="#333333",
            fontsize=9.2,
            fontweight="bold",
            ha="left",
            va="bottom",
            clip_on=False,
        )

    def _build_visible_loss_series(self):
        x_all = list(self.loss_epoch_data)
        if not x_all:
            return [], [], [], []
        if self._display_mode == "global":
            return x_all, list(self.loss_box_data), list(self.loss_cls_data), list(self.loss_dfl_data)
        x_end = int(x_all[-1])
        x_start = max(1, x_end - 19)
        vis_x, vis_box, vis_cls, vis_dfl = [], [], [], []
        for i, ep in enumerate(x_all):
            if not (x_start <= ep <= x_end):
                continue
            vis_x.append(ep)
            vis_box.append(self.loss_box_data[i] if i < len(self.loss_box_data) else float("nan"))
            vis_cls.append(self.loss_cls_data[i] if i < len(self.loss_cls_data) else float("nan"))
            vis_dfl.append(self.loss_dfl_data[i] if i < len(self.loss_dfl_data) else float("nan"))
        return vis_x, vis_box, vis_cls, vis_dfl

    def _draw_loss_chart(self):
        self.fig_loss.clear()
        self.ax_loss = self.fig_loss.add_subplot(111)
        self.ax_loss.set_xlabel("Epoch", fontsize=10)
        self.ax_loss.set_ylabel("Loss", fontsize=10)
        self.ax_loss.grid(True, alpha=0.3)
        self.ax_loss.tick_params(axis="both", which="major", labelsize=8)

        vis_x, vis_box, vis_cls, vis_dfl = self._build_visible_loss_series()
        if vis_x:
            self.ax_loss.plot(vis_x, vis_box, color="#ff7f0e", linewidth=2, marker="o", markersize=3, label="box")
            self.ax_loss.plot(vis_x, vis_cls, color="#1f77b4", linewidth=2, marker="o", markersize=3, label="cls")
            self.ax_loss.plot(vis_x, vis_dfl, color="#2ca02c", linewidth=2, marker="o", markersize=3, label="dfl")
            if self._display_mode == "rolling":
                x_end = int(vis_x[-1])
                x_start = max(1, x_end - 19)
                self.ax_loss.set_xlim(x_start, x_start + 19)
            self.ax_loss.legend(loc="upper left", fontsize=9)
            self._annotate_current_values(vis_x, vis_box, vis_cls, vis_dfl)
            self._draw_min_summary_top()
        self.canvas_loss.draw()

    def _update_current_loss(self):
        total = 0.0
        count = 0
        for series in (self.loss_box_data, self.loss_cls_data, self.loss_dfl_data):
            if not series:
                continue
            value = self._safe_float(series[-1])
            if value is None or not math.isfinite(value):
                continue
            total += value
            count += 1
        self.loss_var.set(f"当前Loss: {total:.4f}" if count > 0 else "当前Loss: -")

    def _apply_system_status(self, status):
        if not self.exists() or not isinstance(status, dict) or status.get("error"):
            return
        gpu_usage = status.get("gpu_usage") or []
        if gpu_usage:
            value = self._safe_float(gpu_usage[0])
            self.gpu_util_data.append(value if value is not None else 0.0)
            self._draw_gpu_util_chart()
        gpu_mem_used = status.get("gpu_mem_used") or []
        gpu_mem_total = status.get("gpu_mem_total") or []
        if gpu_mem_used and gpu_mem_total:
            used = self._safe_float(gpu_mem_used[0])
            total = self._safe_float(gpu_mem_total[0])
            if used is not None and total and total > 0:
                mem_percent = max(0.0, min(100.0, used / total * 100.0))
                self.gpu_mem_data.append(mem_percent)
                self._draw_gpu_mem_chart()

    def _apply_loss_series(self, data):
        if not self.exists() or not isinstance(data, dict):
            return
        epochs = data.get("epochs") or []
        if not epochs:
            return
        self.loss_epoch_data = list(epochs)
        self.loss_box_data = list(data.get("box_loss") or [])
        self.loss_cls_data = list(data.get("cls_loss") or [])
        self.loss_dfl_data = list(data.get("dfl_loss") or [])
        self._draw_loss_chart()
        self._update_current_loss()

    def _refresh_system_status_async(self):
        if self._status_busy:
            return
        self._status_busy = True

        def worker():
            try:
                status = self.monitor_manager.get_system_status()
            except Exception:
                status = {}

            def apply_and_unlock():
                try:
                    self._apply_system_status(status)
                finally:
                    self._status_busy = False

            try:
                self.parent.after(0, apply_and_unlock)
            except Exception:
                self._status_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_history_async(self):
        if self._history_busy:
            return
        self._history_busy = True

        def worker():
            try:
                dataset_path = (self.get_remote_dataset_path_fn() or "").strip()
            except Exception:
                dataset_path = ""
            try:
                rows = self.training_monitor_manager.list_history_runs(remote_dataset_path=dataset_path, limit=200)
            except Exception:
                rows = []

            def apply_and_unlock():
                try:
                    self._apply_history_rows(rows)
                finally:
                    self._history_busy = False

            try:
                self.parent.after(0, apply_and_unlock)
            except Exception:
                self._history_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def _apply_history_rows(self, rows):
        if not self.exists():
            return
        self._history_rows = list(rows or [])
        self._tree_row_to_path = {}
        selected_path = self.selected_results_path
        selected_iid = None
        self.history_tree.delete(*self.history_tree.get_children())

        for idx, item in enumerate(self._history_rows):
            run_name = str(item.get("run_name") or "--")
            mtime_text = str(item.get("mtime_text") or "--")
            path = str(item.get("results_path") or "").strip()
            iid = f"row_{idx}"
            self.history_tree.insert("", "end", iid=iid, values=(run_name, mtime_text))
            self._tree_row_to_path[iid] = path
            if path and path == selected_path:
                selected_iid = iid

        if self._manual_history_selection:
            if selected_iid:
                self._suspend_history_event = True
                try:
                    self.history_tree.selection_set(selected_iid)
                    self.history_tree.see(selected_iid)
                finally:
                    self._suspend_history_event = False
            elif self._history_rows:
                self._manual_history_selection = False
                self.selected_results_path = str(self._history_rows[0].get("results_path") or "")
        elif self._history_rows:
            self.selected_results_path = str(self._history_rows[0].get("results_path") or "")
            selected_iid = "row_0"
            self._suspend_history_event = True
            try:
                self.history_tree.selection_set(selected_iid)
                self.history_tree.see(selected_iid)
            finally:
                self._suspend_history_event = False

        if self._manual_history_selection:
            self.history_hint_var.set(f"当前: 手动选择 {self._extract_run_name(self.selected_results_path)}")
        else:
            self.history_hint_var.set("当前: 跟随最新")

    def _extract_run_name(self, results_path):
        text = str(results_path or "").strip().rstrip("/")
        if not text:
            return "--"
        chunks = text.split("/")
        if len(chunks) >= 2:
            return chunks[-2]
        return text

    def _on_history_select(self, _event=None):
        if self._suspend_history_event:
            return
        selected = self.history_tree.selection()
        if not selected:
            return
        iid = selected[0]
        path = self._tree_row_to_path.get(iid, "")
        if not path:
            return
        self.selected_results_path = path
        self._manual_history_selection = True
        self.history_hint_var.set(f"当前: 手动选择 {self._extract_run_name(path)}")
        self._refresh_loss_async()

    def _refresh_loss_async(self):
        if self._loss_busy:
            return
        self._loss_busy = True

        def worker():
            try:
                dataset_path = (self.get_remote_dataset_path_fn() or "").strip()
            except Exception:
                dataset_path = ""
            try:
                model_name = (self.get_model_name_fn() or "").strip()
            except Exception:
                model_name = ""

            data = None
            path = (self.selected_results_path or "").strip()
            try:
                if path:
                    data = self.training_monitor_manager.get_loss_series_by_results_path(path)
                if not data and not self._manual_history_selection:
                    data = self.training_monitor_manager.get_loss_series(
                        remote_dataset_path=dataset_path,
                        model_name=model_name,
                    )
            except Exception:
                data = None

            def apply_and_unlock():
                try:
                    if data:
                        self._apply_loss_series(data)
                finally:
                    self._loss_busy = False

            try:
                self.parent.after(0, apply_and_unlock)
            except Exception:
                self._loss_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def refresh(self):
        if not self.exists():
            return
        self._sync_training_status()
        self._update_current_loss()

        connected = False
        try:
            connected = bool(self.is_connected_fn())
        except Exception:
            connected = False

        if connected:
            self._refresh_system_status_async()
            if self._tick_count % 2 == 0:
                self._refresh_loss_async()
            if self._tick_count % 5 == 0:
                self._refresh_history_async()

        self._tick_count += 1
        self.after_id = self.parent.after(1000, self.refresh)

    def close(self):
        self._on_close()

    def _on_close(self):
        if self.after_id:
            try:
                self.parent.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        if self.exists():
            try:
                self.win.grab_release()
            except Exception:
                pass
            self.win.destroy()

    def lift(self):
        if self.exists():
            self.win.lift()
            self.win.focus_force()

    def exists(self):
        try:
            return bool(self.win and self.win.winfo_exists())
        except Exception:
            return False
