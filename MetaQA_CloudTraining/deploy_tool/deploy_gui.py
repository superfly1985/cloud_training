import os
import sys
import json
import base64
import math
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deploy_manager import DeployManager, DEPLOY_STEPS, SERVICE_PORT

LOCAL_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__), ), "..")
)

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "deploy_config.json")

COLOR_BG = "#1e1e2e"
COLOR_SURFACE = "#2a2a3d"
COLOR_PRIMARY = "#7c3aed"
COLOR_PRIMARY_HOVER = "#6d28d9"
COLOR_SUCCESS = "#22c55e"
COLOR_ERROR = "#ef4444"
COLOR_WARNING = "#f59e0b"
COLOR_TEXT = "#e2e8f0"
COLOR_TEXT_DIM = "#94a3b8"
COLOR_LOG_BG = "#0f0f1a"
COLOR_LOG_FG = "#a5f3fc"
COLOR_PROGRESS_BG = "#1e1e2e"
COLOR_PROGRESS_FG = "#7c3aed"

class DeployApp:

    def __init__(self, root):
        self.root = root
        self.root.title("MetaQA 云端训练 - 一键部署工具")
        self.root.geometry("800x750")
        self.root.minsize(720, 650)
        self.root.configure(bg=COLOR_BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.manager = DeployManager()
        self._deploying = False
        self._deploy_thread = None
        self._pass_visible = False
        self._deploy_started_at = None
        self._elapsed_job = None
        self.step_indicators = {}
        self.remote_dir_var = tk.StringVar(value="将按登录用户自动解析")
        self.server_web_url_var = tk.StringVar(value="")

        self._build_ui()
        self._center_window()
        self._load_config()

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"+{x}+{y}")

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                if cfg.get("host"):
                    self.host_var.set(cfg["host"])
                if cfg.get("port"):
                    self.port_var.set(cfg["port"])
                if cfg.get("user"):
                    self.user_var.set(cfg["user"])
                if cfg.get("password"):
                    try:
                        decoded = base64.b64decode(cfg["password"]).decode("utf-8")
                        self.pass_var.set(decoded)
                    except Exception:
                        pass
        except Exception:
            pass

    def _save_config(self):
        try:
            password = self.pass_var.get().strip()
            encoded_pwd = base64.b64encode(password.encode("utf-8")).decode("utf-8") if password else ""
            cfg = {
                "host": self.host_var.get().strip(),
                "port": self.port_var.get().strip(),
                "user": self.user_var.get().strip(),
                "password": encoded_pwd,
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        button_width = 18
        section_padding = 12
        section_gap = 10

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=COLOR_BG)
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=("Microsoft YaHei UI", 10))
        style.configure("Title.TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=("Microsoft YaHei UI", 14, "bold"))
        style.configure("TEntry", fieldbackground=COLOR_SURFACE, foreground=COLOR_TEXT, insertcolor=COLOR_TEXT)
        style.configure("TLabelframe", background=COLOR_BG, foreground=COLOR_TEXT, font=("Microsoft YaHei UI", 10))
        style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_PRIMARY, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("TButton", font=("Microsoft YaHei UI", 10))
        style.configure("Success.TLabel", background=COLOR_BG, foreground=COLOR_SUCCESS, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Error.TLabel", background=COLOR_BG, foreground=COLOR_ERROR, font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Warning.TLabel", background=COLOR_BG, foreground=COLOR_WARNING, font=("Microsoft YaHei UI", 10))
        style.configure("Dim.TLabel", background=COLOR_BG, foreground=COLOR_TEXT_DIM, font=("Microsoft YaHei UI", 9))

        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.title_label = ttk.Label(main_frame, text="MetaQA 云端训练部署工具", style="Title.TLabel")
        self.title_label.pack(anchor=tk.W, pady=(0, 16))

        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)
        content_frame.columnconfigure(0, weight=3)
        content_frame.columnconfigure(1, weight=5)
        content_frame.rowconfigure(0, weight=1)

        self.left_panel = ttk.Frame(content_frame)
        self.left_panel.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 10))

        self.right_panel = ttk.Frame(content_frame)
        self.right_panel.grid(row=0, column=1, sticky=tk.NSEW)

        self.conn_frame = ttk.LabelFrame(self.left_panel, text="服务器连接", padding=section_padding)
        self.conn_frame.pack(fill=tk.X, pady=(0, section_gap))

        fields = self.conn_frame
        row = 0

        ttk.Label(fields, text="IP地址:").grid(row=row, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.host_var = tk.StringVar()
        ttk.Entry(fields, textvariable=self.host_var, width=30).grid(row=row, column=1, sticky=tk.EW, pady=4)
        row += 1

        ttk.Label(fields, text="SSH端口:").grid(row=row, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.port_var = tk.StringVar(value="22")
        ttk.Entry(fields, textvariable=self.port_var, width=30).grid(row=row, column=1, sticky=tk.EW, pady=4)
        row += 1

        ttk.Label(fields, text="用户名:").grid(row=row, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        self.user_var = tk.StringVar(value="ubuntu")
        self.user_combo = ttk.Combobox(
            fields,
            textvariable=self.user_var,
            values=("ubuntu", "root"),
            width=28,
            state="normal",
        )
        self.user_combo.grid(row=row, column=1, sticky=tk.EW, pady=4)
        row += 1

        ttk.Label(fields, text="密码:").grid(row=row, column=0, sticky=tk.W, padx=(0, 8), pady=4)
        pass_frame = ttk.Frame(fields)
        pass_frame.grid(row=row, column=1, sticky=tk.EW, pady=4)
        self.pass_entry = ttk.Entry(pass_frame, show="*")
        self.pass_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.pass_var = tk.StringVar()
        self.pass_entry.config(textvariable=self.pass_var)
        self.toggle_pass_btn = tk.Button(
            pass_frame, text="显示", command=self._toggle_password,
            bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM, font=("Microsoft YaHei UI", 8),
            relief=tk.FLAT, padx=6, pady=0, cursor="hand2"
        )
        self.toggle_pass_btn.pack(side=tk.LEFT, padx=(4, 0))
        row += 1

        fields.columnconfigure(1, weight=1)

        btn_row = ttk.Frame(fields)
        btn_row.grid(row=row, column=0, columnspan=2, pady=(8, 0))

        self.test_btn = tk.Button(
            btn_row, text="测试连接", command=self._on_test,
            bg=COLOR_PRIMARY, fg="white", activebackground=COLOR_PRIMARY_HOVER,
            activeforeground="white", font=("Microsoft YaHei UI", 10, "bold"),
            relief=tk.FLAT, width=button_width, pady=4, cursor="hand2"
        )
        self.test_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.conn_status = ttk.Label(btn_row, text="", style="TLabel")
        self.conn_status.pack(side=tk.LEFT)

        self.info_frame = ttk.LabelFrame(self.left_panel, text="部署信息", padding=section_padding)
        self.info_frame.pack(fill=tk.X, pady=(0, section_gap))

        info_grid = self.info_frame
        ttk.Label(info_grid, text="本地源码:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8), pady=2)
        self.local_dir_var = tk.StringVar(value=LOCAL_DIR)
        ttk.Label(info_grid, textvariable=self.local_dir_var, style="Dim.TLabel").grid(row=0, column=1, sticky=tk.EW, pady=2)

        ttk.Label(info_grid, text="远程目录:").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=2)
        ttk.Label(info_grid, textvariable=self.remote_dir_var, style="Dim.TLabel").grid(row=1, column=1, sticky=tk.EW, pady=2)

        ttk.Label(info_grid, text="服务端口:").grid(row=2, column=0, sticky=tk.W, padx=(0, 8), pady=2)
        ttk.Label(info_grid, text=str(SERVICE_PORT), style="Dim.TLabel").grid(row=2, column=1, sticky=tk.EW, pady=2)

        ttk.Label(info_grid, text="服务器 Web:").grid(row=3, column=0, sticky=tk.NW, padx=(0, 8), pady=2)
        self.server_web_link = tk.Label(
            self.info_frame,
            textvariable=self.server_web_url_var,
            bg=COLOR_BG,
            fg=COLOR_PRIMARY,
            font=("Microsoft YaHei UI", 10, "underline"),
            cursor="hand2",
            anchor="w",
            justify=tk.LEFT,
            wraplength=260,
        )
        self.server_web_link.grid(row=3, column=1, sticky=tk.EW, pady=2)
        self.server_web_link.bind("<Button-1>", lambda _event: self._open_server_web())

        info_grid.columnconfigure(1, weight=1)

        self.action_frame = ttk.LabelFrame(self.left_panel, text="操作区", padding=section_padding)
        self.action_frame.pack(fill=tk.X, pady=(0, section_gap))

        deploy_btn_frame = ttk.Frame(self.action_frame)
        deploy_btn_frame.pack(fill=tk.X)

        self.deploy_btn = tk.Button(
            deploy_btn_frame, text="一键部署", command=self._on_deploy,
            bg=COLOR_SUCCESS, fg="white", activebackground="#16a34a",
            activeforeground="white", font=("Microsoft YaHei UI", 10, "bold"),
            relief=tk.FLAT, width=button_width, pady=6, cursor="hand2"
        )
        self.deploy_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.cancel_btn = tk.Button(
            deploy_btn_frame, text="取消部署", command=self._on_cancel,
            bg=COLOR_ERROR, fg="white", activebackground="#dc2626",
            activeforeground="white", font=("Microsoft YaHei UI", 10, "bold"),
            relief=tk.FLAT, width=button_width, pady=6, cursor="hand2", state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.steps_frame = ttk.LabelFrame(self.right_panel, text="部署步骤", padding=section_padding)
        self.steps_frame.pack(fill=tk.X, pady=(0, section_gap))

        steps_inner = ttk.Frame(self.steps_frame)
        steps_inner.pack(fill=tk.X)

        rows_per_column = math.ceil(len(DEPLOY_STEPS) / 2)
        steps_inner.columnconfigure(0, weight=1)
        steps_inner.columnconfigure(1, weight=1)

        for i, step in enumerate(DEPLOY_STEPS):
            row = i % rows_per_column
            column = i // rows_per_column
            indicator = tk.Label(
                steps_inner, text=f" {i+1}. {step} ",
                bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM,
                font=("Microsoft YaHei UI", 10), padx=10, pady=6, relief=tk.FLAT, anchor=tk.W
            )
            indicator.grid(row=row, column=column, padx=4, pady=2, sticky=tk.EW)
            self.step_indicators[step] = indicator

        self.log_frame = ttk.LabelFrame(self.right_panel, text="部署日志", padding=section_padding)
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            self.log_frame, wrap=tk.WORD, font=("Consolas", 10),
            bg=COLOR_LOG_BG, fg=COLOR_LOG_FG, insertbackground=COLOR_LOG_FG,
            selectbackground=COLOR_PRIMARY, relief=tk.FLAT, padx=10, pady=8
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.log_text.tag_configure("success", foreground=COLOR_SUCCESS)
        self.log_text.tag_configure("error", foreground=COLOR_ERROR)
        self.log_text.tag_configure("warning", foreground=COLOR_WARNING)
        self.log_text.tag_configure("info", foreground=COLOR_LOG_FG)
        self.log_text.tag_configure("step", foreground=COLOR_PRIMARY, font=("Consolas", 9, "bold"))

        self.bottom_status_frame = ttk.LabelFrame(content_frame, text="部署状态", padding=section_padding)
        self.bottom_status_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(section_gap, 0))

        summary_frame = ttk.Frame(self.bottom_status_frame)
        summary_frame.pack(fill=tk.X)

        self.progress_label = ttk.Label(summary_frame, text="", style="TLabel")
        self.progress_label.pack(side=tk.LEFT)

        self.elapsed_label = ttk.Label(summary_frame, text="", style="TLabel")
        self.elapsed_label.pack(side=tk.RIGHT)

        self.status_label = ttk.Label(self.bottom_status_frame, text="", style="TLabel")
        self.status_label.pack(fill=tk.X, pady=(4, 4))

        self.progress_bar = tk.Canvas(
            self.bottom_status_frame, height=8, bg=COLOR_PROGRESS_BG, highlightthickness=0
        )
        self.progress_bar.pack(fill=tk.X)

        self.user_var.trace_add("write", lambda *_: self._update_remote_dir_hint())
        self.host_var.trace_add("write", lambda *_: self._update_server_web_link_state())
        self._update_remote_dir_hint()
        self._update_server_web_link_state()

    def _guess_remote_home(self, user):
        user = (user or "").strip()
        if not user:
            return "<用户Home目录>"
        if user == "root":
            return "/root"
        return f"/home/{user}"

    def _update_remote_dir_hint(self):
        remote_home = self._guess_remote_home(self.user_var.get())
        self.remote_dir_var.set(f"{remote_home}/cloud-training-runtime/MetaQA_CloudTraining")

    def _build_server_web_url(self, host):
        host = (host or "").strip()
        if not host:
            return ""
        return f"http://{host}:{SERVICE_PORT}"

    def _update_server_web_link_state(self):
        url = self._build_server_web_url(self.host_var.get())
        self.server_web_url_var.set(url)
        if hasattr(self, "server_web_link") and self.server_web_link:
            self.server_web_link.config(
                fg=COLOR_PRIMARY if url else COLOR_TEXT_DIM,
                cursor="hand2" if url else "arrow",
            )

    def _open_server_web(self):
        url = self.server_web_url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "当前没有可打开的服务器 Web 链接")
            return
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror("错误", f"打开浏览器失败:\n{exc}")

    def _toggle_password(self):
        self._pass_visible = not self._pass_visible
        self.pass_entry.config(show="" if self._pass_visible else "*")
        self.toggle_pass_btn.config(text="隐藏" if self._pass_visible else "显示")

    def _set_step_state(self, step_name, state):
        indicator = self.step_indicators.get(step_name)
        if not indicator:
            return
        if state == "running":
            indicator.config(bg=COLOR_PRIMARY, fg="white")
        elif state == "success":
            indicator.config(bg=COLOR_SUCCESS, fg="white")
        elif state == "error":
            indicator.config(bg=COLOR_ERROR, fg="white")
        elif state == "skip":
            indicator.config(bg=COLOR_WARNING, fg="black")
        else:
            indicator.config(bg=COLOR_SURFACE, fg=COLOR_TEXT_DIM)

    def _reset_step_indicators(self):
        for step in DEPLOY_STEPS:
            self._set_step_state(step, "pending")

    def _log(self, msg, tag="info"):
        self.log_text.insert(tk.END, msg + "\n", tag)
        self.log_text.see(tk.END)

    def _update_progress(self, current, total, uploaded, skipped, failed):
        pct = (current / total * 100) if total > 0 else 0
        self.progress_label.config(text=f"{current}/{total} (新传:{uploaded} 跳过:{skipped})")
        self.progress_bar.delete("all")
        w = self.progress_bar.winfo_width()
        bar_w = w * (pct / 100)
        self.progress_bar.create_rectangle(0, 0, bar_w, 8, fill=COLOR_PROGRESS_FG, outline="")

    def _draw_progress_ratio(self, ratio, color=COLOR_PROGRESS_FG):
        safe_ratio = max(0.0, min(1.0, ratio))
        self.progress_bar.delete("all")
        w = self.progress_bar.winfo_width()
        bar_w = w * safe_ratio
        self.progress_bar.create_rectangle(0, 0, bar_w, 8, fill=color, outline="")

    def _update_runtime_status(self, step_name="", detail=""):
        text = detail or step_name
        self.status_label.config(text=text)

    def _schedule_elapsed_tick(self):
        if not self._deploying or not self._deploy_started_at:
            return
        elapsed = max(0, int(time.time() - self._deploy_started_at))
        mins, secs = divmod(elapsed, 60)
        hours, mins = divmod(mins, 60)
        if hours:
            text = f"已耗时 {hours:02d}:{mins:02d}:{secs:02d}"
        else:
            text = f"已耗时 {mins:02d}:{secs:02d}"
        self.elapsed_label.config(text=text)
        self._elapsed_job = self.root.after(1000, self._schedule_elapsed_tick)

    def _set_deploying(self, deploying):
        self._deploying = deploying
        state = tk.DISABLED if deploying else tk.NORMAL
        self.deploy_btn.config(state=state)
        self.test_btn.config(state=state)
        self.cancel_btn.config(state=tk.NORMAL if deploying else tk.DISABLED)
        if deploying:
            self._deploy_started_at = time.time()
            self.elapsed_label.config(text="已耗时 00:00")
            if self._elapsed_job:
                self.root.after_cancel(self._elapsed_job)
            self._elapsed_job = self.root.after(1000, self._schedule_elapsed_tick)
        else:
            self._deploy_started_at = None
            if self._elapsed_job:
                self.root.after_cancel(self._elapsed_job)
                self._elapsed_job = None

    def _get_conn_params(self):
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get().strip() or "22")
        except ValueError:
            messagebox.showwarning("提示", "SSH端口必须为数字")
            return None
        user = self.user_var.get().strip()
        password = self.pass_var.get().strip()
        if not host:
            messagebox.showwarning("提示", "请输入服务器IP地址")
            return None
        if not password:
            messagebox.showwarning("提示", "请输入密码")
            return None
        return host, port, user, password

    def _on_test(self):
        params = self._get_conn_params()
        if not params:
            return
        host, port, user, password = params

        self.test_btn.config(state=tk.DISABLED)
        self.conn_status.config(text="测试中...", style="TLabel")

        def do_test():
            ok, msg = self.manager.test_connection(host, port, user, password)
            self.root.after(0, lambda: self._on_test_result(ok, msg))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_result(self, ok, msg):
        self.test_btn.config(state=tk.NORMAL)
        if ok:
            self.conn_status.config(text=f"✓ {msg}", style="Success.TLabel")
            self._log(f"连接测试成功: {msg}", "success")
            self._save_config()
        else:
            self.conn_status.config(text=f"✗ {msg}", style="Error.TLabel")
            self._log(f"连接测试失败: {msg}", "error")

    def _on_deploy(self):
        params = self._get_conn_params()
        if not params:
            return
        host, port, user, password = params

        local_dir = self.local_dir_var.get().strip()
        if not os.path.isdir(local_dir):
            messagebox.showerror("错误", f"本地源码目录不存在:\n{local_dir}")
            return

        self.log_text.delete("1.0", tk.END)
        self._reset_step_indicators()
        self._log("开始部署...", "step")
        self._set_deploying(True)
        self.progress_label.config(text="")
        self._update_runtime_status("准备部署", "准备开始执行部署步骤")
        self.progress_bar.delete("all")

        step_callback = self._make_step_callback()

        def do_deploy():
            try:
                results = self.manager.full_deploy(
                    host, port, user, password, local_dir,
                    log_cb=lambda msg: self.root.after(0, lambda m=msg: self._log(m)),
                    progress_cb=lambda *a: self.root.after(0, lambda: self._update_progress(*a)),
                    step_cb=step_callback,
                )
                self.root.after(0, lambda: self._on_deploy_done(host, results))
            except Exception as e:
                self.root.after(0, lambda: self._on_deploy_error(str(e)))

        self._deploy_thread = threading.Thread(target=do_deploy, daemon=True)
        self._deploy_thread.start()

    def _make_step_callback(self):
        def on_step(step_name, state, detail=None):
            def apply_step():
                self._set_step_state(step_name, state)
                if step_name in DEPLOY_STEPS:
                    step_index = DEPLOY_STEPS.index(step_name)
                    if state == "running":
                        self._draw_progress_ratio((step_index + 0.2) / len(DEPLOY_STEPS))
                    elif state == "success":
                        self._draw_progress_ratio((step_index + 1) / len(DEPLOY_STEPS))
                    elif state == "error":
                        self._draw_progress_ratio((step_index + 1) / len(DEPLOY_STEPS), COLOR_ERROR)
                self._update_runtime_status(step_name, detail or f"{step_name}执行中")

            self.root.after(0, apply_step)
        return on_step

    def _on_deploy_done(self, host, results):
        self._set_deploying(False)
        self.manager.close()
        self._update_server_web_link_state()

        all_success = all(r["success"] for r in results.values())
        completed_steps = len(results)
        total_steps = len(DEPLOY_STEPS)

        self._log(f"\n{'='*50}", "step")
        if all_success:
            self._log("部署完成！所有步骤成功", "success")
            self._log(f"访问: http://{host}:{SERVICE_PORT}", "success")
            self._log("systemd 自启动已部署，服务器重启后会自动拉起服务", "success")
            self._save_config()
            self.progress_bar.delete("all")
            w = self.progress_bar.winfo_width()
            self.progress_bar.create_rectangle(0, 0, w, 8, fill=COLOR_SUCCESS, outline="")
            self.progress_label.config(text="部署完成 ✓")
            self._update_runtime_status("部署完成", "所有部署步骤已完成，已启用自启动")
        else:
            self._log(f"部署未完成 ({completed_steps}/{total_steps} 步骤)", "warning")
            self._log("可重新点击一键部署，将自动跳过已完成步骤", "warning")
            for step, r in results.items():
                if not r["success"]:
                    self._log(f"  失败: {step} - {r['detail']}", "error")
                    self._update_runtime_status(step, r["detail"])
                    break
            self.progress_label.config(text=f"部署中断 ({completed_steps}/{total_steps})")

        self._log(f"{'='*50}", "step")

    def _on_deploy_error(self, error_msg):
        self._set_deploying(False)
        self.manager.close()
        self._log(f"\n[异常] 部署出错: {error_msg}", "error")
        self._log("可重新点击一键部署，将自动跳过已完成步骤", "warning")
        self._update_runtime_status("部署异常", error_msg)

    def _on_cancel(self):
        if self._deploying:
            self.manager.cancel()
            self._log("\n[取消] 正在中断部署...", "warning")

    def _on_close(self):
        if self._deploying:
            if not messagebox.askyesno("确认", "部署正在进行中，确定要关闭吗？"):
                return
            self.manager.cancel()
        self.manager.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = DeployApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
