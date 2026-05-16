# Deploy GUI layout and web link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize `deploy_tool/deploy_gui.py` into a left-control and
right-monitoring layout, and add a direct button that opens the deployed
server web UI.

**Architecture:** Keep all deployment behavior inside `deploy_manager.py` and
confine this work to the Tkinter GUI layer. Add small GUI helpers for web URL
state and button enablement, then refactor `_build_ui()` into clearer left and
right regions while preserving the existing deploy callbacks and log flow.

**Tech Stack:** Python, Tkinter, ttk, `webbrowser`, unittest

---

## File map

This work stays focused on the existing GUI and its tests.

- Modify: `deploy_tool/deploy_gui.py`
  - Add server-web URL helpers and button state logic.
  - Refactor the layout into left and right columns.
  - Replace the horizontal step strip with a vertical status list.
- Modify: `test/test_deploy_gui.py`
  - Add focused tests for URL generation, button state, success-state URL
    updates, and step indicator behavior.

### Task 1: add server web URL helpers and open action

**Files:**
- Modify: `deploy_tool/deploy_gui.py`
- Test: `test/test_deploy_gui.py`

- [ ] **Step 1: Write the failing tests**

```python
import importlib
import os
import sys
import unittest
from unittest.mock import patch


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
DEPLOY_TOOL_ROOT = os.path.join(PROJECT_ROOT, "deploy_tool")
if DEPLOY_TOOL_ROOT not in sys.path:
    sys.path.insert(0, DEPLOY_TOOL_ROOT)


class DeployGuiTests(unittest.TestCase):
    def test_build_server_web_url_uses_host_and_service_port(self):
        deploy_gui = importlib.import_module("deploy_gui")

        app = deploy_gui.DeployApp.__new__(deploy_gui.DeployApp)
        self.assertEqual(
            app._build_server_web_url("43.133.91.5"),
            f"http://43.133.91.5:{deploy_gui.SERVICE_PORT}",
        )
        self.assertEqual(app._build_server_web_url(""), "")

    def test_update_server_web_link_state_disables_button_for_empty_host(self):
        deploy_gui = importlib.import_module("deploy_gui")

        class DummyVar:
            def __init__(self):
                self.value = ""

            def set(self, value):
                self.value = value

        class DummyButton:
            def __init__(self):
                self.state = None

            def config(self, **kwargs):
                if "state" in kwargs:
                    self.state = kwargs["state"]

        app = deploy_gui.DeployApp.__new__(deploy_gui.DeployApp)
        app.server_web_url_var = DummyVar()
        app.open_web_btn = DummyButton()
        app.host_var = type("HostVar", (), {"get": lambda self: ""})()

        app._update_server_web_link_state()

        self.assertEqual(app.server_web_url_var.value, "")
        self.assertEqual(app.open_web_btn.state, deploy_gui.tk.DISABLED)

    def test_open_server_web_uses_default_browser_for_current_url(self):
        deploy_gui = importlib.import_module("deploy_gui")

        app = deploy_gui.DeployApp.__new__(deploy_gui.DeployApp)
        app.server_web_url_var = type(
            "UrlVar",
            (),
            {"get": lambda self: "http://43.133.91.5:8090"},
        )()

        with patch.object(deploy_gui.webbrowser, "open", return_value=True) as open_mock:
            app._open_server_web()

        open_mock.assert_called_once_with("http://43.133.91.5:8090")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "server_web_url or server_web_link or open_server_web" -q
```

Expected: FAIL because the GUI does not yet define `_build_server_web_url()`,
`_update_server_web_link_state()`, or `_open_server_web()`.

- [ ] **Step 3: Write the minimal implementation**

```python
# deploy_tool/deploy_gui.py
import webbrowser


class DeployApp:
    def __init__(self, root):
        self.root = root
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

    def _build_server_web_url(self, host):
        host = (host or "").strip()
        if not host:
            return ""
        return f"http://{host}:{SERVICE_PORT}"

    def _update_server_web_link_state(self):
        url = self._build_server_web_url(self.host_var.get())
        self.server_web_url_var.set(url)
        if hasattr(self, "open_web_btn") and self.open_web_btn:
            self.open_web_btn.config(state=tk.NORMAL if url else tk.DISABLED)

    def _open_server_web(self):
        url = self.server_web_url_var.get().strip()
        if not url:
            messagebox.showwarning("提示", "当前没有可打开的服务器 Web 链接")
            return
        try:
            webbrowser.open(url)
        except Exception as exc:
            messagebox.showerror("错误", f"打开浏览器失败:\n{exc}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "server_web_url or server_web_link or open_server_web" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_gui.py test/test_deploy_gui.py
git commit -m "feat: add deploy gui server web link helpers"
```

### Task 2: refactor the GUI into left and right columns

**Files:**
- Modify: `deploy_tool/deploy_gui.py`
- Test: `test/test_deploy_gui.py`

- [ ] **Step 1: Write the failing layout test**

```python
def test_build_ui_creates_left_and_right_columns(self):
    deploy_gui = importlib.import_module("deploy_gui")

    with patch.object(deploy_gui.DeployApp, "_center_window", return_value=None), \
         patch.object(deploy_gui.DeployApp, "_load_config", return_value=None):
        root = deploy_gui.tk.Tk()
        root.withdraw()
        try:
            app = deploy_gui.DeployApp(root)
            self.assertTrue(hasattr(app, "left_panel"))
            self.assertTrue(hasattr(app, "right_panel"))
            self.assertEqual(int(app.left_panel.grid_info()["column"]), 0)
            self.assertEqual(int(app.right_panel.grid_info()["column"]), 1)
        finally:
            root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "left_and_right_columns" -q
```

Expected: FAIL because `_build_ui()` still packs everything into one stacked
column and does not expose `left_panel` or `right_panel`.

- [ ] **Step 3: Write the minimal implementation**

```python
# deploy_tool/deploy_gui.py
def _build_ui(self):
    main_frame = ttk.Frame(self.root, padding=15)
    main_frame.pack(fill=tk.BOTH, expand=True)

    title_label = ttk.Label(main_frame, text="MetaQA 云端训练部署工具", style="Title.TLabel")
    title_label.pack(anchor=tk.W, pady=(0, 12))

    content_frame = ttk.Frame(main_frame)
    content_frame.pack(fill=tk.BOTH, expand=True)
    content_frame.columnconfigure(0, weight=3)
    content_frame.columnconfigure(1, weight=5)
    content_frame.rowconfigure(0, weight=1)

    self.left_panel = ttk.Frame(content_frame)
    self.left_panel.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 10))

    self.right_panel = ttk.Frame(content_frame)
    self.right_panel.grid(row=0, column=1, sticky=tk.NSEW)

    conn_frame = ttk.LabelFrame(self.left_panel, text="服务器连接", padding=10)
    conn_frame.pack(fill=tk.X, pady=(0, 8))
    info_frame = ttk.LabelFrame(self.left_panel, text="部署信息", padding=10)
    info_frame.pack(fill=tk.X, pady=(0, 8))
    action_frame = ttk.LabelFrame(self.left_panel, text="操作区", padding=10)
    action_frame.pack(fill=tk.X, pady=(0, 8))
    quick_access_frame = ttk.LabelFrame(self.left_panel, text="快速访问", padding=10)
    quick_access_frame.pack(fill=tk.X, pady=(0, 8))
    status_frame = ttk.LabelFrame(self.right_panel, text="部署状态", padding=10)
    status_frame.pack(fill=tk.X, pady=(0, 8))
    self.progress_bar = tk.Canvas(status_frame, height=8, bg=COLOR_PROGRESS_BG, highlightthickness=0)
    self.progress_bar.pack(fill=tk.X)
    steps_frame = ttk.LabelFrame(self.right_panel, text="部署步骤", padding=8)
    steps_frame.pack(fill=tk.X, pady=(0, 8))
    steps_inner = ttk.Frame(steps_frame)
    steps_inner.pack(fill=tk.X)
    log_frame = ttk.LabelFrame(self.right_panel, text="部署日志", padding=4)
    log_frame.pack(fill=tk.BOTH, expand=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "left_and_right_columns" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_gui.py test/test_deploy_gui.py
git commit -m "refactor: split deploy gui into control and status columns"
```

### Task 3: add the quick access card and vertical step list

**Files:**
- Modify: `deploy_tool/deploy_gui.py`
- Test: `test/test_deploy_gui.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_ui_creates_open_server_web_button_and_url_label(self):
    deploy_gui = importlib.import_module("deploy_gui")

    with patch.object(deploy_gui.DeployApp, "_center_window", return_value=None), \
         patch.object(deploy_gui.DeployApp, "_load_config", return_value=None):
        root = deploy_gui.tk.Tk()
        root.withdraw()
        try:
            app = deploy_gui.DeployApp(root)
            self.assertEqual(app.open_web_btn.cget("text"), "打开服务器 Web")
            self.assertEqual(app.server_web_url_var.get(), "")
        finally:
            root.destroy()


def test_build_ui_creates_vertical_step_indicators(self):
    deploy_gui = importlib.import_module("deploy_gui")

    with patch.object(deploy_gui.DeployApp, "_center_window", return_value=None), \
         patch.object(deploy_gui.DeployApp, "_load_config", return_value=None):
        root = deploy_gui.tk.Tk()
        root.withdraw()
        try:
            app = deploy_gui.DeployApp(root)
            first = app.step_indicators[deploy_gui.DEPLOY_STEPS[0]].grid_info()
            second = app.step_indicators[deploy_gui.DEPLOY_STEPS[1]].grid_info()
            self.assertNotEqual(int(first["row"]), int(second["row"]))
        finally:
            root.destroy()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "open_server_web_button or vertical_step_indicators" -q
```

Expected: FAIL because the GUI does not yet render the quick-access card or a
vertical step list.

- [ ] **Step 3: Write the minimal implementation**

```python
# deploy_tool/deploy_gui.py
quick_access_frame = ttk.LabelFrame(self.left_panel, text="快速访问", padding=10)
quick_access_frame.pack(fill=tk.X, pady=(0, 8))

ttk.Label(quick_access_frame, text="服务器 Web:").pack(anchor=tk.W)
ttk.Label(
    quick_access_frame,
    textvariable=self.server_web_url_var,
    style="Dim.TLabel",
    wraplength=240,
).pack(anchor=tk.W, fill=tk.X, pady=(4, 8))

self.open_web_btn = tk.Button(
    quick_access_frame,
    text="打开服务器 Web",
    command=self._open_server_web,
    bg=COLOR_PRIMARY,
    fg="white",
    activebackground=COLOR_PRIMARY_HOVER,
    activeforeground="white",
    font=("Microsoft YaHei UI", 10, "bold"),
    relief=tk.FLAT,
    padx=16,
    pady=4,
    cursor="hand2",
    state=tk.DISABLED,
)
self.open_web_btn.pack(anchor=tk.W)

steps_inner = ttk.Frame(steps_frame)
steps_inner.pack(fill=tk.X)

for i, step in enumerate(DEPLOY_STEPS):
    indicator = tk.Label(
        steps_inner,
        text=f" {i+1}. {step} ",
        bg=COLOR_SURFACE,
        fg=COLOR_TEXT_DIM,
        font=("Microsoft YaHei UI", 9),
        padx=8,
        pady=4,
        relief=tk.FLAT,
        anchor="w",
    )
    indicator.grid(row=i, column=0, sticky=tk.EW, padx=0, pady=2)
    steps_inner.columnconfigure(0, weight=1)
    self.step_indicators[step] = indicator

self.host_var.trace_add("write", lambda *_: self._update_server_web_link_state())
self._update_server_web_link_state()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "open_server_web_button or vertical_step_indicators" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_gui.py test/test_deploy_gui.py
git commit -m "feat: add deploy gui quick web access and vertical step list"
```

### Task 4: connect deploy success to the web link state

**Files:**
- Modify: `deploy_tool/deploy_gui.py`
- Test: `test/test_deploy_gui.py`

- [ ] **Step 1: Write the failing test**

```python
def test_deploy_done_updates_server_web_url_and_enables_button(self):
    deploy_gui = importlib.import_module("deploy_gui")

    class DummyManager:
        def close(self):
            return None

    class DummyVar:
        def __init__(self):
            self.value = ""

        def set(self, value):
            self.value = value

        def get(self):
            return self.value

    class DummyButton:
        def __init__(self):
            self.state = None

        def config(self, **kwargs):
            if "state" in kwargs:
                self.state = kwargs["state"]

    app = deploy_gui.DeployApp.__new__(deploy_gui.DeployApp)
    app.manager = DummyManager()
    app.server_web_url_var = DummyVar()
    app.open_web_btn = DummyButton()
    app._deploying = False
    app._set_deploying = lambda deploying: None
    app._save_config = lambda: None
    app._log = lambda *args, **kwargs: None
    app._update_runtime_status = lambda *args, **kwargs: None
    app.progress_bar = type(
        "ProgressBar",
        (),
        {
            "delete": lambda self, *args: None,
            "winfo_width": lambda self: 100,
            "create_rectangle": lambda self, *args, **kwargs: None,
        },
    )()
    app.progress_label = type("ProgressLabel", (), {"config": lambda self, **kwargs: None})()
    app.host_var = type("HostVar", (), {"get": lambda self: "43.133.91.5"})()
    app._update_server_web_link_state = deploy_gui.DeployApp._update_server_web_link_state.__get__(app)
    app._build_server_web_url = deploy_gui.DeployApp._build_server_web_url.__get__(app)

    results = {step: {"success": True, "detail": "ok"} for step in deploy_gui.DEPLOY_STEPS}
    app._on_deploy_done("43.133.91.5", results)

    self.assertEqual(
        app.server_web_url_var.get(),
        f"http://43.133.91.5:{deploy_gui.SERVICE_PORT}",
    )
    self.assertEqual(app.open_web_btn.state, deploy_gui.tk.NORMAL)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "deploy_done_updates_server_web_url" -q
```

Expected: FAIL because `_on_deploy_done()` does not yet refresh the quick web
access state.

- [ ] **Step 3: Write the minimal implementation**

```python
# deploy_tool/deploy_gui.py
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
        self._save_config()
        self.progress_bar.delete("all")
        w = self.progress_bar.winfo_width()
        self.progress_bar.create_rectangle(0, 0, w, 8, fill=COLOR_SUCCESS, outline="")
        self.progress_label.config(text="部署完成 ✓")
        self._update_runtime_status("部署完成", "所有部署步骤已完成，已启用自启动")
    else:
        self._log(f"部署未完成 ({completed_steps}/{total_steps} 步骤)", "warning")
        self.progress_label.config(text=f"部署中断 ({completed_steps}/{total_steps})")
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python -m pytest test/test_deploy_gui.py -k "deploy_done_updates_server_web_url" -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_gui.py test/test_deploy_gui.py
git commit -m "fix: refresh deploy gui web link after successful deploy"
```

### Task 5: run full GUI regression and diagnostics

**Files:**
- Verify: `deploy_tool/deploy_gui.py`
- Verify: `test/test_deploy_gui.py`

- [ ] **Step 1: Run the GUI test file**

Run:

```bash
python -m pytest test/test_deploy_gui.py -q
```

Expected: PASS

- [ ] **Step 2: Run the broader deploy-tool regression**

Run:

```bash
python -m pytest test/test_deploy_gui.py test/test_deploy_manager.py -q
```

Expected: PASS

- [ ] **Step 3: Check diagnostics for touched files**

Check:

- `deploy_tool/deploy_gui.py`
- `test/test_deploy_gui.py`

Expected: no new diagnostics

- [ ] **Step 4: Do the manual UI sanity check**

Manual check:

1. Start the deploy GUI.
2. Confirm the window shows a left control column and right monitoring column.
3. Confirm the step list is vertical and readable.
4. Enter a host and confirm the server web URL text updates immediately.
5. Confirm **打开服务器 Web** is disabled when the host is empty.
6. Confirm **打开服务器 Web** launches the browser after deployment success.

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_gui.py test/test_deploy_gui.py
git commit -m "feat: redesign deploy gui layout and add server web quick access"
```
