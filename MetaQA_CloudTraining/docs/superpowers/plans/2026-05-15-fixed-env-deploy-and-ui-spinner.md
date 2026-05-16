# Fixed env deploy and UI spinner implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the fixed three-environment deployment and runtime model, add repair progress and mutual exclusion, and fix spinner animations so only the icon rotates.

**Architecture:** The backend stops guessing Python locations and uses fixed
paths from config for Web, training, and conversion. Deployment bootstraps the
remote layout, writes deploy state, and only slims `base` when the server is in
first-deploy or reset state. The frontend switches from one-shot repair to a
task-based progress model and uses icon-only rotation classes.

**Tech Stack:** FastAPI, Python subprocess/conda, Paramiko, Vue 3, plain CSS,
SQLite

---

### Task 1: Add fixed environment configuration and deployment state support

**Files:**
- Modify: `config/app_config.yaml`
- Modify: `app/core/system_manager.py`
- Modify: `app/core/init_manager.py`
- Modify: `deploy_tool/deploy_manager.py`
- Test: `test/test_system_manager.py`
- Test: `test/test_init_manager.py`

- [ ] **Step 1: Write failing tests for fixed-path environment checks**

```python
def test_training_env_uses_fixed_path():
    assert _get_training_python_cmd() == "/root/miniforge3/envs/cloud-training/bin/python"


def test_convert_env_uses_fixed_path():
    assert _get_convert_python_cmd() == "/root/miniforge3/envs/cloud-conversion/bin/python"
```

- [ ] **Step 2: Run targeted tests to verify current gaps**

Run: `python -m unittest test.test_system_manager -v`
Expected: FAIL because fixed-path behavior, deploy state checks, and new repair
progress objects are not implemented yet.

- [ ] **Step 3: Implement fixed-path environment helpers and state-aware checks**

```python
FIXED_BASE_PYTHON = "/root/miniforge3/bin/python"
FIXED_TRAINING_PYTHON = "/root/miniforge3/envs/cloud-training/bin/python"
FIXED_CONVERSION_PYTHON = "/root/miniforge3/envs/cloud-conversion/bin/python"
FIXED_CONDA = "/root/miniforge3/bin/conda"


def _get_training_python_cmd() -> str:
    cfg = get_config()
    return cfg.get("training", {}).get("python_cmd") or FIXED_TRAINING_PYTHON
```

- [ ] **Step 4: Implement deploy-state-aware bootstrap and base slimming guards**

```python
def needs_base_slimming(state: dict) -> bool:
    return (
        not state
        or not state.get("base_slimmed")
        or not state.get("base_slimmed_at")
        or not state.get("env_snapshot")
        or not state.get("version_locks")
    )
```

- [ ] **Step 5: Run focused tests again**

Run: `python -m unittest test.test_system_manager test.test_init_manager -v`
Expected: PASS


### Task 2: Add repair task progress, mutual exclusion, and log download support

**Files:**
- Modify: `app/core/init_manager.py`
- Modify: `app/api/init.py`
- Modify: `static/js/api.js`
- Modify: `static/js/system-tab.js`
- Test: `test/test_init_manager.py`

- [ ] **Step 1: Write failing tests for repair state lifecycle**

```python
def test_repair_task_reports_running_progress():
    task = start_repair_task()
    status = get_repair_status(task["task_id"])
    assert status["status"] in {"queued", "repairing", "success", "failed"}
```

- [ ] **Step 2: Run targeted tests to verify they fail**

Run: `python -m unittest test.test_init_manager -v`
Expected: FAIL because the API still runs repair synchronously and has no task
status or log download support.

- [ ] **Step 3: Implement repair manager state and log persistence**

```python
REPAIR_STATE = {
    "lock": threading.Lock(),
    "active_task": None,
    "history": [],
}


def append_repair_log(task: dict, message: str) -> None:
    task["logs"].append(message)
```

- [ ] **Step 4: Expose task APIs and wire the frontend polling UI**

```javascript
API.startSystemFix = function () {
  return axios.post("/api/v1/init/auto-fix");
};

API.getSystemFixStatus = function (taskId) {
  return axios.get("/api/v1/init/auto-fix/" + encodeURIComponent(taskId));
};
```

- [ ] **Step 5: Run focused tests again**

Run: `python -m unittest test.test_init_manager -v`
Expected: PASS


### Task 3: Update deployment flow to fixed three-environment strategy

**Files:**
- Modify: `deploy_tool/deploy_gui.py`
- Modify: `deploy_tool/deploy_manager.py`
- Test: `test/test_deploy_manager.py`

- [ ] **Step 1: Write failing tests for first-deploy detection and base-slim gate**

```python
def test_first_deploy_requires_base_slim_when_state_missing():
    assert needs_remote_base_slim(None) is True
```

- [ ] **Step 2: Run targeted tests to verify current behavior fails**

Run: `python -m unittest test.test_deploy_manager -v`
Expected: FAIL because deploy manager still uses the old 9-step flow.

- [ ] **Step 3: Implement the 12-step deploy flow and base-slim retry rule**

```python
steps = [
    ("连接服务器", self._step_connect),
    ("环境检查", self._step_check_env),
    ("停止旧服务", self._step_stop_service),
    ("判定首次部署", self._step_detect_bootstrap),
    ("上传文件", self._step_upload),
    ("安装 Web 依赖", self._step_install_web_deps),
    ("创建训练环境", self._step_prepare_training_env),
    ("创建转换环境", self._step_prepare_conversion_env),
    ("验证训练环境", self._step_verify_training_env),
    ("验证转换环境", self._step_verify_conversion_env),
    ("瘦身 base", self._step_slim_base),
    ("启动并验证服务", self._step_start_and_verify),
]
```

- [ ] **Step 4: Run focused tests again**

Run: `python -m unittest test.test_deploy_manager -v`
Expected: PASS


### Task 4: Fix spinner behavior and convert status icon animation to icon-only rotation

**Files:**
- Modify: `static/css/style.css`
- Modify: `static/js/system-tab.js`
- Modify: `static/js/modals.js`
- Test: Manual verification in browser

- [ ] **Step 1: Audit current spinner usage and identify container-level animation**

```css
.spinner {
  animation: spin 0.6s linear infinite;
}
```

- [ ] **Step 2: Replace container-level rotation with icon-only animation helpers**

```css
.spin-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.spin-icon > i,
.spin-icon::before {
  animation: spin 0.8s linear infinite;
  transform-origin: center;
}
```

- [ ] **Step 3: Update check and modal markup to rotate only the icon element**

```html
<span class="check-icon checking">
  <span class="spin-icon"><i class="bi bi-arrow-repeat" aria-hidden="true"></i></span>
</span>
```

- [ ] **Step 4: Verify manually**

Run: start the app, open upload modal and system repair page.
Expected: the ring or icon rotates, the container stays centered, and no
horizontal bar or skewed orbit appears.


### Task 5: Run integrated verification

**Files:**
- Modify: `test/test_system_manager.py`
- Modify: `test/test_init_manager.py`
- Modify: `test/test_deploy_manager.py`

- [ ] **Step 1: Run backend tests**

Run: `python -m unittest discover -s test -p "test_*.py"`
Expected: PASS

- [ ] **Step 2: Run diagnostics on touched files**

Run diagnostics for:
- `app/core/init_manager.py`
- `app/core/system_manager.py`
- `deploy_tool/deploy_manager.py`
- `static/js/system-tab.js`
- `static/css/style.css`

Expected: no new diagnostics

- [ ] **Step 3: Smoke-check the main UX flows**

Run:
1. Deploy first-time scenario
2. Repair task start and polling
3. Repair log download
4. Upload modal spinner
5. System check spinner

Expected: fixed environments are used, repair is serialized, and icon-only
rotation is visually correct.
