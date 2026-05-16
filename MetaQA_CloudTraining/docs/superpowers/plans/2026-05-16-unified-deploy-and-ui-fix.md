# 统一用户目录部署与前端动画修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 彻底重构部署工具以支持“统一用户目录”方案，实现干净服务器的自动化引导（Bootstrap），并修复前端 Spinner 旋转导致的视觉偏移。

**Architecture:** 
1. 部署端：将硬编码的 `/root` 替换为动态获取的 `$HOME`，引入 `Bootstrap` 阶段处理 Miniforge 安装与环境创建，强制使用 `opencv-python-headless`。
2. 前端：重构 Spinner 实现，使用 `spin-icon` 容器仅旋转图标元素，避免容器整体旋转导致的偏移。

**Tech Stack:** Python (Paramiko), Vue.js, CSS Animations.

---

### Task 1: 重构部署路径常量与配置

**Files:**
- Modify: `deploy_tool/deploy_manager.py`
- Modify: `deploy_tool/deploy_config.json`

- [ ] **Step 1: 修改 `deploy_config.json` 默认值**

```json
{
  "host": "150.109.247.74",
  "port": "22",
  "user": "ubuntu",
  "password": "..."
}
```

- [ ] **Step 2: 在 `DeployManager` 中引入动态路径初始化逻辑**

移除头部的硬编码常量，改为在 `__init__` 或 `connect` 后根据远程环境动态生成。

```python
# deploy_manager.py

class DeployManager:
    def __init__(self):
        # ...
        self.remote_home = "/home/ubuntu" # 默认，连接后更新
        self.base_runtime_dir = ""
        self.remote_dir = ""
        self.fixed_conda = ""
        # ...

    def _update_paths(self, home_dir):
        self.remote_home = home_dir
        self.base_runtime_dir = f"{home_dir}/cloud-training-runtime"
        self.remote_dir = f"{self.base_runtime_dir}/MetaQA_CloudTraining"
        self.fixed_conda = f"{self.base_runtime_dir}/miniforge3/bin/conda"
        self.fixed_base_python = f"{self.base_runtime_dir}/miniforge3/bin/python"
        self.fixed_training_python = f"{self.base_runtime_dir}/miniforge3/envs/cloud-training/bin/python"
        self.fixed_conversion_python = f"{self.base_runtime_dir}/miniforge3/envs/cloud-conversion/bin/python"
        self.deploy_state_path = f"{self.remote_dir}/data/deploy_state.json"
```

- [ ] **Step 3: 修改 `connect` 方法以获取远程 Home 目录**

```python
    def connect(self, host, port, user, password, timeout=15):
        # ... 现有连接代码 ...
        code, out, err = self._exec(self.client, "echo $HOME")
        home_dir = out.strip() or f"/home/{user}"
        self._update_paths(home_dir)
```

---

### Task 2: 实现自动化引导 (Bootstrap) 逻辑

**Files:**
- Modify: `deploy_tool/deploy_manager.py`

- [ ] **Step 1: 增加 Miniforge 安装步骤**

```python
    def _install_miniforge(self, log_cb=None):
        if log_cb: log_cb("检查并安装 Miniforge...")
        code, out, err = self.run(f"test -x {self.fixed_conda} && echo EXISTS || echo MISSING")
        if out.strip() == "EXISTS":
            return True
        
        # 下载并安装
        installer = "Miniforge3-Linux-x86_64.sh"
        download_cmd = f"wget https://github.com/conda-forge/miniforge/releases/latest/download/{installer} -O /tmp/{installer}"
        install_cmd = f"bash /tmp/{installer} -b -p {self.base_runtime_dir}/miniforge3"
        
        self.run(f"mkdir -p {self.base_runtime_dir}")
        self._run_command_with_heartbeat(download_cmd, timeout=300, log_cb=log_cb, heartbeat_label="下载 Miniforge")
        self._run_command_with_heartbeat(install_cmd, timeout=600, log_cb=log_cb, heartbeat_label="安装 Miniforge")
        return True
```

- [ ] **Step 2: 修改 `_step_check_env` 以触发引导**

不再直接返回失败，而是标记需要引导。

- [ ] **Step 3: 调整 `full_deploy` 步骤序列**

```python
        steps = [
            ("连接服务器", self._step_connect),
            ("初始化目录与环境", self._step_bootstrap_runtime), # 新增：创建根目录，装 Miniforge
            ("上传文件", self._step_upload),
            # ... 后续步骤使用动态路径 ...
        ]
```

---

### Task 3: 适配 Sudo 与强制 Headless

**Files:**
- Modify: `deploy_tool/deploy_manager.py`
- Modify: `deploy_tool/requirements-web.txt`

- [ ] **Step 1: 在必要步骤前缀 `sudo -n`**

```python
    def _install_system_deps(self, log_cb=None):
        if log_cb: log_cb("安装系统运行库 (sudo)...")
        # 针对新服务器，确保 libgl1 等存在
        cmd = "sudo -n apt-get update && sudo -n apt-get install -y libgl1 libglib2.0-0"
        self._run_command_with_heartbeat(cmd, timeout=300, log_cb=log_cb, heartbeat_label="安装系统依赖")
```

- [ ] **Step 2: 确保 Web 依赖也使用 Headless (如果包含 opencv)**

检查 `requirements-web.txt`，如果未来加入 opencv，必须是 headless 版。当前 `requirements-training.txt` 已正确配置。

---

### Task 4: 修复前端 Spinner 动画

**Files:**
- Modify: `static/css/style.css`
- Modify: `static/js/modals.js`
- Modify: `static/js/system-tab.js`

- [ ] **Step 1: 在 CSS 中定义 `spin-icon` 动画**

```css
/* static/css/style.css */
.spin-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.spin-icon i, .spin-icon .bi {
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
```

- [ ] **Step 2: 替换 `modals.js` 中的 Spinner**

```javascript
// 修改前: <span class="spinner"></span>
// 修改后: <span class="spin-icon"><i class="bi bi-arrow-repeat"></i></span>
```

- [ ] **Step 3: 检查 `system-tab.js` 中的 Spinner 使用情况**

确保 `check-icon` 等位置使用 `spin-icon` 包装图标。

---

### Task 5: 验证

- [ ] **Step 1: 运行本地单元测试**
Run: `python -m unittest test/test_deploy_manager.py`

- [ ] **Step 2: 执行真实部署测试**
连接到 `150.109.247.74`，观察 bootstrap 流程。

- [ ] **Step 3: 浏览器检查动画**
打开“自动修复”或“新建训练”弹窗，确认图标旋转平稳。
