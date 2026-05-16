# Web env check and repair alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deployed web runtime environment check and repair workflow
use the same environment contract, requirements synchronization, and final
verification rules as the deployment tool.

**Architecture:** Add one shared environment contract module that defines
fixed paths, requirements files, verification snippets, and aligned step
metadata. Refactor `system_manager.py`, `init_manager.py`, and
`deploy_manager.py` to read that contract instead of maintaining duplicated
rules. Keep deployment-only behavior in `deploy_manager.py`, and keep
web-runtime task orchestration in `system_manager.py` and `init_manager.py`.

**Tech Stack:** Python, FastAPI, subprocess-based environment probes, unittest,
Vue component in `static/js/system-tab.js`

---

## File map

This plan changes a focused set of files and gives each one one clear job.

- Create: `app/core/environment_contract.py`
  - Shared source of truth for fixed Python paths, requirements file mapping,
    aligned verification snippets, aligned check names, and aligned repair
    steps.
- Modify: `app/core/system_manager.py`
  - Replace handwritten environment rule copies with contract-driven checks and
    summaries.
- Modify: `app/core/init_manager.py`
  - Replace ad hoc repair behavior with requirements-file synchronization and
    aligned verification.
- Modify: `deploy_tool/deploy_manager.py`
  - Import aligned snippets and metadata from the shared contract instead of
    keeping private copies.
- Modify: `static/js/system-tab.js`
  - Update repair wording so the UI accurately describes unified repair.
- Test: `test/test_system_manager.py`
  - Lock contract-driven runtime checks.
- Test: `test/test_init_manager.py`
  - Lock contract-driven repair flow.
- Test: `test/test_deploy_manager.py`
  - Lock deployment-tool usage of the shared contract.

### Task 1: add the shared environment contract module

**Files:**
- Create: `app/core/environment_contract.py`
- Test: `test/test_system_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_environment_contract_exposes_aligned_runtime_constants(self):
    from app.core import environment_contract

    self.assertEqual(
        environment_contract.RUNTIME_ENV_REQUIREMENTS["training"],
        "deploy_tool/requirements-training.txt",
    )
    self.assertEqual(
        environment_contract.RUNTIME_ENV_REQUIREMENTS["conversion"],
        "deploy_tool/requirements-conversion.txt",
    )
    self.assertIn(
        "from ultralytics import YOLO",
        environment_contract.CONVERSION_IMPORT_CHECK_SNIPPET,
    )
    self.assertIn(
        "import onnx2tf",
        environment_contract.CONVERSION_GATE_SNIPPET,
    )
    self.assertEqual(
        environment_contract.RUNTIME_REPAIR_STEPS,
        [
            "检查固定路径",
            "检查训练环境",
            "检查转换环境",
            "创建缺失环境",
            "同步训练依赖",
            "同步转换依赖",
            "验证训练环境",
            "验证转换环境",
            "重新汇总检查结果",
        ],
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_system_manager.py -k "environment_contract_exposes_aligned_runtime_constants" -q`

Expected: FAIL with `ImportError` or missing attribute errors because
`environment_contract.py` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/environment_contract.py
import os


def _runtime_root() -> str:
    return os.path.join(os.path.expanduser("~"), "cloud-training-runtime").replace("\\", "/")


RUNTIME_ROOT = _runtime_root()
FIXED_BASE_PYTHON = os.path.join(RUNTIME_ROOT, "miniforge3", "bin", "python").replace("\\", "/")
FIXED_TRAINING_PYTHON = os.path.join(
    RUNTIME_ROOT, "miniforge3", "envs", "cloud-training", "bin", "python"
).replace("\\", "/")
FIXED_CONVERSION_PYTHON = os.path.join(
    RUNTIME_ROOT, "miniforge3", "envs", "cloud-conversion", "bin", "python"
).replace("\\", "/")
FIXED_CONDA = os.path.join(RUNTIME_ROOT, "miniforge3", "bin", "conda").replace("\\", "/")

RUNTIME_ENV_REQUIREMENTS = {
    "web": "deploy_tool/requirements-web.txt",
    "training": "deploy_tool/requirements-training.txt",
    "conversion": "deploy_tool/requirements-conversion.txt",
}

TRAINING_IMPORT_CHECK_SNIPPET = "import torch, ultralytics, onnx; print(torch.__version__)"
CONVERSION_IMPORT_CHECK_SNIPPET = (
    "from ultralytics import YOLO; import tensorflow; import numpy; "
    "from PIL import Image; import onnx2tf; print('ok')"
)
CONVERSION_GATE_SNIPPET = CONVERSION_IMPORT_CHECK_SNIPPET
ENV_ISOLATION_CHECK_SNIPPET = (
    "import importlib.util; "
    "print(int(importlib.util.find_spec('tensorflow') is not None)); "
    "print(int(importlib.util.find_spec('onnx2tf') is not None))"
)

ALIGNED_ENV_CHECK_NAMES = [
    "训练环境",
    "转换环境",
    "PyTorch",
    "Ultralytics",
    "ONNX",
    "TensorFlow",
    "onnx2tf",
    "转换门禁",
    "环境隔离",
]

RUNTIME_REPAIR_STEPS = [
    "检查固定路径",
    "检查训练环境",
    "检查转换环境",
    "创建缺失环境",
    "同步训练依赖",
    "同步转换依赖",
    "验证训练环境",
    "验证转换环境",
    "重新汇总检查结果",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test/test_system_manager.py -k "environment_contract_exposes_aligned_runtime_constants" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/environment_contract.py test/test_system_manager.py
git commit -m "feat: add shared environment contract"
```

### Task 2: align `system_manager.py` to the shared contract

**Files:**
- Modify: `app/core/system_manager.py`
- Test: `test/test_system_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_system_manager_uses_shared_contract_for_conversion_gate(self):
    from app.core import environment_contract, system_manager

    with patch.object(system_manager, "_get_convert_python_cmd", return_value="/tmp/convert-python"), \
         patch.object(system_manager, "_run_python_snippet", return_value=(True, "ok", "")) as run_mock:
        result = system_manager._check_conversion_gate()

    self.assertEqual(result["status"], "pass")
    self.assertEqual(run_mock.call_args.args[1], environment_contract.CONVERSION_GATE_SNIPPET)


def test_system_manager_check_names_follow_aligned_contract(self):
    from app.core import environment_contract, system_manager

    checks = system_manager.run_environment_checks()
    names = [item["name"] for item in checks]
    for name in environment_contract.ALIGNED_ENV_CHECK_NAMES:
        self.assertIn(name, names)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_system_manager.py -k "shared_contract_for_conversion_gate or aligned_contract" -q`

Expected: FAIL because `system_manager.py` still contains private snippets and
private fixed-path constants.

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/system_manager.py
from app.core.environment_contract import (
    ALIGNED_ENV_CHECK_NAMES,
    CONVERSION_GATE_SNIPPET,
    ENV_ISOLATION_CHECK_SNIPPET,
    FIXED_BASE_PYTHON,
    FIXED_CONDA,
    FIXED_CONVERSION_PYTHON,
    FIXED_TRAINING_PYTHON,
    TRAINING_IMPORT_CHECK_SNIPPET,
    CONVERSION_IMPORT_CHECK_SNIPPET,
)


def _check_conversion_gate() -> dict:
    python_cmd = _get_convert_python_cmd()
    ok, _, err = _run_python_snippet(python_cmd, CONVERSION_GATE_SNIPPET, timeout=60)
    if ok:
        return {
            "name": "转换门禁",
            "status": "pass",
            "message": "转换环境导入链路完整",
            "auto_fixable": False,
            "blocking": True,
        }
    return {
        "name": "转换门禁",
        "status": "fail",
        "message": _format_probe_error("转换环境导入链路不完整", err, python_cmd),
        "auto_fixable": False,
        "blocking": True,
    }


def _check_env_isolation() -> dict:
    python_cmd = _get_training_python_cmd()
    ok, out, err = _run_python_snippet(python_cmd, ENV_ISOLATION_CHECK_SNIPPET)
    if not ok:
        return {
            "name": "环境隔离",
            "status": "fail",
            "message": _format_probe_error("无法检查训练环境隔离状态", err, python_cmd),
            "auto_fixable": True,
            "blocking": True,
        }
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    if len(lines) >= 2 and (lines[0] == "1" or lines[1] == "1"):
        return {
            "name": "环境隔离",
            "status": "fail",
            "message": "训练环境中检测到 tensorflow 或 onnx2tf",
            "auto_fixable": True,
            "blocking": True,
        }
    return {
        "name": "环境隔离",
        "status": "pass",
        "message": "训练环境未检测到 tensorflow/onnx2tf",
        "auto_fixable": True,
        "blocking": True,
    }
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest test/test_system_manager.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/system_manager.py test/test_system_manager.py
git commit -m "refactor: align system checks with shared environment contract"
```

### Task 3: align `init_manager.py` repair flow to deployment semantics

**Files:**
- Modify: `app/core/init_manager.py`
- Test: `test/test_init_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_repair_steps_match_shared_contract(self):
    from app.core import environment_contract, init_manager

    self.assertEqual(init_manager.REPAIR_STEPS, environment_contract.RUNTIME_REPAIR_STEPS)


def test_runtime_repair_syncs_requirements_instead_of_ad_hoc_package_installs(self):
    from app.core import init_manager

    task = {
        "logs": [],
        "steps": [{"name": name, "status": "pending"} for name in init_manager.REPAIR_STEPS],
        "total_steps": len(init_manager.REPAIR_STEPS),
        "percent": 0,
        "current_step": "",
        "current_step_index": 0,
    }

    with patch.object(init_manager, "_sync_runtime_requirements") as sync_mock, \
         patch.object(init_manager, "_verify_env_with_contract"), \
         patch.object(init_manager, "_collect_runtime_summary"):
        init_manager._run_runtime_alignment_steps(task)

    sync_mock.assert_any_call(task, "training")
    sync_mock.assert_any_call(task, "conversion")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_init_manager.py -k "runtime_repair" -q`

Expected: FAIL because `init_manager.py` still uses private repair steps and ad
hoc package installation helpers.

- [ ] **Step 3: Write minimal implementation**

```python
# app/core/init_manager.py
from app.core.environment_contract import (
    FIXED_CONDA,
    FIXED_CONVERSION_PYTHON,
    FIXED_TRAINING_PYTHON,
    RUNTIME_ENV_REQUIREMENTS,
    RUNTIME_REPAIR_STEPS,
    TRAINING_IMPORT_CHECK_SNIPPET,
    CONVERSION_IMPORT_CHECK_SNIPPET,
)

REPAIR_STEPS = list(RUNTIME_REPAIR_STEPS)


def _run_runtime_alignment_steps(task: dict):
    _execute_repair_step(task, 0, _check_fixed_paths)
    _execute_repair_step(task, 1, lambda: _inspect_env(FIXED_TRAINING_PYTHON, "训练环境"))
    _execute_repair_step(task, 2, lambda: _inspect_env(FIXED_CONVERSION_PYTHON, "转换环境"))
    _execute_repair_step(task, 3, _ensure_runtime_envs)
    _execute_repair_step(task, 4, lambda: _sync_runtime_requirements(task, "training"))
    _execute_repair_step(task, 5, lambda: _sync_runtime_requirements(task, "conversion"))
    _execute_repair_step(
        task,
        6,
        lambda: _verify_env_with_contract("训练环境", FIXED_TRAINING_PYTHON, TRAINING_IMPORT_CHECK_SNIPPET),
    )
    _execute_repair_step(
        task,
        7,
        lambda: _verify_env_with_contract("转换环境", FIXED_CONVERSION_PYTHON, CONVERSION_IMPORT_CHECK_SNIPPET),
    )
    _execute_repair_step(task, 8, lambda: _collect_runtime_summary(task))


def _sync_runtime_requirements(task: dict, env_name: str):
    python_exe = {
        "training": FIXED_TRAINING_PYTHON,
        "conversion": FIXED_CONVERSION_PYTHON,
    }[env_name]
    requirements_rel = RUNTIME_ENV_REQUIREMENTS[env_name]
    result = subprocess.run(
        [python_exe, "-m", "pip", "install", "-r", requirements_rel],
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=get_runtime_path(),
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or "").strip()[:300])


def _verify_env_with_contract(label: str, python_exe: str, snippet: str):
    result = subprocess.run([python_exe, "-c", snippet], capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"{label}验证失败: {(result.stderr or result.stdout).strip()[:300]}")


def _collect_runtime_summary(task: dict):
    checks = run_environment_checks()
    summary = get_environment_summary(checks)
    task["summary"] = {**summary, "checks": checks}
    store_environment_check_result(task["task_id"], "success", "自动修复完成", summary, checks)
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest test/test_init_manager.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/init_manager.py test/test_init_manager.py
git commit -m "refactor: align web repair flow with deployment env rules"
```

### Task 4: make `deploy_manager.py` consume the same contract

**Files:**
- Modify: `deploy_tool/deploy_manager.py`
- Test: `test/test_deploy_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_step_verify_envs_uses_shared_contract_snippets(self):
    from app.core import environment_contract
    from deploy_tool.deploy_manager import DeployManager

    manager = DeployManager()
    with patch.object(manager, "_verify_remote_imports", return_value=(True, "验证通过")) as verify_mock:
        ok, detail = manager._step_verify_envs(None, None, None, None, None, None, None)

    self.assertTrue(ok)
    self.assertEqual(detail, "固定环境验证通过")
    self.assertEqual(verify_mock.call_args_list[0].args[1], environment_contract.TRAINING_IMPORT_CHECK_SNIPPET)
    self.assertEqual(verify_mock.call_args_list[1].args[1], environment_contract.CONVERSION_IMPORT_CHECK_SNIPPET)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_deploy_manager.py -k "shared_contract_snippets" -q`

Expected: FAIL because `deploy_manager.py` still embeds the snippets inline.

- [ ] **Step 3: Write minimal implementation**

```python
# deploy_tool/deploy_manager.py
from app.core.environment_contract import (
    CONVERSION_IMPORT_CHECK_SNIPPET,
    FIXED_CONVERSION_PYTHON,
    FIXED_TRAINING_PYTHON,
    TRAINING_IMPORT_CHECK_SNIPPET,
)


def _step_verify_envs(self, host, port, user, password, local_dir, log_cb, progress_cb):
    training_ok, training_detail = self._verify_remote_imports(
        self.fixed_training_python,
        TRAINING_IMPORT_CHECK_SNIPPET,
        log_cb,
        "训练环境",
    )
    conversion_ok, conversion_detail = self._verify_remote_imports(
        self.fixed_conversion_python,
        CONVERSION_IMPORT_CHECK_SNIPPET,
        log_cb,
        "转换环境",
    )
    if training_ok and conversion_ok:
        return True, "固定环境验证通过"
    if not training_ok and conversion_ok:
        return False, training_detail
    if training_ok and not conversion_ok:
        return False, conversion_detail
    return False, f"{training_detail}；{conversion_detail}"
```

- [ ] **Step 4: Run focused tests to verify they pass**

Run: `python -m pytest test/test_deploy_manager.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_manager.py test/test_deploy_manager.py
git commit -m "refactor: make deploy manager use shared environment contract"
```

### Task 5: align frontend repair wording and preserve API shape

**Files:**
- Modify: `static/js/system-tab.js`
- Test: `test/test_init_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_runtime_fix_task_step_names_are_frontend_safe(self):
    from app.core import environment_contract, init_manager

    task = init_manager.start_auto_fix_task()
    step_names = [item["name"] for item in task["steps"]]
    self.assertEqual(step_names, environment_contract.RUNTIME_REPAIR_STEPS)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_init_manager.py -k "frontend_safe" -q`

Expected: FAIL if the API payload step list still uses drifted names.

- [ ] **Step 3: Write minimal implementation**

```javascript
// static/js/system-tab.js
<button v-if="check.status === 'fail' && check.auto_fixable"
        class="btn btn-sm btn-ghost"
        @click="fixOne(check)">
  统一修复
</button>
```

```javascript
fixOne: function (check) {
  if (check) {
    check.status = "checking";
  }
  this.autoFix();
},
```

- [ ] **Step 4: Run relevant tests and do a manual payload sanity check**

Run: `python -m pytest test/test_init_manager.py -q`

Expected: PASS

Manual check:

1. Open the system page.
2. Trigger **自动修复**.
3. Confirm the step names match the aligned contract.
4. Confirm per-item button wording no longer implies isolated one-item repair.

- [ ] **Step 5: Commit**

```bash
git add static/js/system-tab.js test/test_init_manager.py
git commit -m "fix: align web repair wording with unified runtime repair flow"
```

### Task 6: run final regression and diagnostics

**Files:**
- Verify: `app/core/environment_contract.py`
- Verify: `app/core/system_manager.py`
- Verify: `app/core/init_manager.py`
- Verify: `deploy_tool/deploy_manager.py`
- Verify: `static/js/system-tab.js`
- Test: `test/test_system_manager.py`
- Test: `test/test_init_manager.py`
- Test: `test/test_deploy_manager.py`

- [ ] **Step 1: Run the full aligned test set**

Run:

```bash
python -m pytest test/test_system_manager.py test/test_init_manager.py test/test_deploy_manager.py -q
```

Expected: PASS

- [ ] **Step 2: Check diagnostics for touched files**

Check:

- `app/core/environment_contract.py`
- `app/core/system_manager.py`
- `app/core/init_manager.py`
- `deploy_tool/deploy_manager.py`
- `static/js/system-tab.js`
- `test/test_system_manager.py`
- `test/test_init_manager.py`
- `test/test_deploy_manager.py`

Expected: no new diagnostics

- [ ] **Step 3: Do one runtime behavior sanity check**

Manual check:

1. Open the deployed web system page.
2. Run **重新检查**.
3. Confirm aligned items match deployment-tool verification conclusions.
4. Run **自动修复**.
5. Confirm the task reaches completion and a new check run reports the same
   aligned results.

- [ ] **Step 4: Commit**

```bash
git add app/core/environment_contract.py app/core/system_manager.py app/core/init_manager.py deploy_tool/deploy_manager.py static/js/system-tab.js test/test_system_manager.py test/test_init_manager.py test/test_deploy_manager.py
git commit -m "feat: align web environment checks and repair with deploy tool"
```
