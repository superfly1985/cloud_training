# Legacy ultralytics tflite rollback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unstable `onnx2tf`-based TFLite conversion path with the legacy `Ultralytics export(format='tflite')` flow, update deploy-time dependency verification, and keep cloud replay testing non-interactive after a single login.

**Architecture:** `app/core/package_manager.py` remains the orchestration layer and continues to own package lifecycle, YAML resolution, ONNX export, and fail-closed packaging. `_convert_tflite()` switches to a minimal conversion-runtime script that loads `best.pt` with `YOLO` and exports `fp32` plus `fp16` directly. The deploy tool aligns its conversion-environment checks with this legacy path and adds a replay-friendly remote execution flow that reuses one authenticated SSH session for all verification steps.

**Tech Stack:** Python, unittest, sqlite3, Ultralytics, TensorFlow, Pillow, numpy, Paramiko, deployment helper scripts

---

### Task 1: Lock the legacy TFLite contract with failing tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_convert_tflite_uses_ultralytics_direct_export_twice(self):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout, cwd):
        script_path = cmd[2]
        with open(script_path, "r", encoding="utf-8") as rf:
            captured["script"] = rf.read()
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        for name in ("best_fp32.tflite", "best_fp16.tflite"):
            with open(os.path.join(cwd, name), "wb") as wf:
                wf.write(b"ok")
        return Result()

    with patch("app.core.package_manager.subprocess.run", side_effect=fake_run):
        outputs = package_manager._convert_tflite(
            best_pt,
            python_cmd,
            "both",
            train_dir,
            dataset_yaml,
            640,
        )

    self.assertEqual(2, len(outputs))
    self.assertIn("from ultralytics import YOLO", captured["script"])
    self.assertIn("model.export(format='tflite'", captured["script"])
    self.assertIn("half=True", captured["script"])
    self.assertIn("half=False", captured["script"])
    self.assertIn("nms=True", captured["script"])
    self.assertIn("data=data_yaml", captured["script"])


def test_convert_tflite_script_no_longer_mentions_onnx2tf(self):
    captured = {}

    def fake_run(cmd, capture_output, text, timeout, cwd):
        script_path = cmd[2]
        with open(script_path, "r", encoding="utf-8") as rf:
            captured["script"] = rf.read()
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        for name in ("best_fp32.tflite", "best_fp16.tflite"):
            with open(os.path.join(cwd, name), "wb") as wf:
                wf.write(b"ok")
        return Result()

    with patch("app.core.package_manager.subprocess.run", side_effect=fake_run):
        package_manager._convert_tflite(
            best_pt,
            python_cmd,
            "both",
            train_dir,
            dataset_yaml,
            640,
        )

    self.assertNotIn("onnx2tf", captured["script"])
    self.assertNotIn("custom_input_op_name_np_data_path", captured["script"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_package_manager.py -k "uses_ultralytics_direct_export_twice or no_longer_mentions_onnx2tf" -q`
Expected: FAIL because the current implementation still builds an `onnx2tf`
conversion script.

- [ ] **Step 3: Write the minimal implementation to satisfy the new contract**

```python
def _convert_tflite(best_pt, python_cmd, tflite_format, work_dir, dataset_yaml, imgsz, dataset_dir=None):
    script = f"""
from ultralytics import YOLO
...
model = YOLO(best_pt)
model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=False, nms=True, data=data_yaml)
model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=True, nms=True, data=data_yaml)
"""
```

- [ ] **Step 4: Run the focused tests again**

Run: `python -m pytest test/test_package_manager.py -k "uses_ultralytics_direct_export_twice or no_longer_mentions_onnx2tf" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add test/test_package_manager.py app/core/package_manager.py
git commit -m "test: lock legacy ultralytics tflite conversion flow"
```

### Task 2: Replace the package-manager conversion path

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Remove the ONNX-to-TFLite specific helpers from the active path**

```python
def _convert_tflite(...):
    if not best_pt or not os.path.exists(best_pt):
        return results
    if not dataset_yaml or not os.path.exists(dataset_yaml):
        return results
```

- [ ] **Step 2: Generate a direct-export conversion script**

```python
script = f"""
import glob
import json
import os
import shutil
import sys
from ultralytics import YOLO

best_pt = {json.dumps(best_pt)}
data_yaml = {json.dumps(dataset_yaml)}
imgsz = {int(imgsz)}
work_dir = {json.dumps(work_dir)}

model = YOLO(best_pt)
model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=False, nms=True, data=data_yaml)
model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=True, nms=True, data=data_yaml)
"""
```

- [ ] **Step 3: Normalize the generated outputs to canonical package names**

```python
stem = os.path.splitext(os.path.basename(best_pt))[0]
saved_model_dir = os.path.splitext(best_pt)[0] + "_saved_model"
fp32_dst = os.path.join(work_dir, f"{stem}_fp32.tflite")
fp16_dst = os.path.join(work_dir, f"{stem}_fp16.tflite")
```

- [ ] **Step 4: Keep strict fail-closed behavior when either TFLite output is missing**

```python
conversion_meta = _build_conversion_meta(best_onnx, tflite_files, conversion_errors)
if conversion_meta["conversion_status"] != "complete":
    raise ValueError(message)
```

- [ ] **Step 5: Run the package-manager suite**

Run: `python -m pytest test/test_package_manager.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/core/package_manager.py test/test_package_manager.py
git commit -m "fix: restore legacy ultralytics tflite export path"
```

### Task 3: Align deploy-time conversion dependencies with the legacy flow

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\requirements-conversion.txt`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Write the failing deploy-tool tests**

```python
def test_verify_envs_checks_legacy_conversion_imports(self):
    captured = {}

    def fake_verify(python_cmd, snippet, log_cb, label):
        captured["snippet"] = snippet
        return True, "ok"

    with patch.object(self.manager, "_verify_remote_imports", side_effect=fake_verify):
        self.manager.verify_fixed_envs(log_cb=lambda msg: None)

    self.assertIn("from ultralytics import YOLO", captured["snippet"])
    self.assertIn("import tensorflow", captured["snippet"])
    self.assertIn("import numpy", captured["snippet"])
    self.assertIn("from PIL import Image", captured["snippet"])
    self.assertNotIn("onnx2tf", captured["snippet"])


def test_requirements_conversion_does_not_require_onnx2tf(self):
    text = requirements_path.read_text(encoding="utf-8")
    self.assertIn("ultralytics==", text)
    self.assertIn("tensorflow==", text)
    self.assertIn("numpy==", text)
    self.assertIn("Pillow==", text)
    self.assertNotIn("onnx2tf==", text)
```

- [ ] **Step 2: Run the failing deploy-tool tests**

Run: `python -m pytest test/test_deploy_manager.py -k "legacy_conversion_imports or does_not_require_onnx2tf" -q`
Expected: FAIL because the current deploy verification still checks the
`onnx2tf` path and the conversion requirements still declare `onnx2tf`.

- [ ] **Step 3: Update deploy verification and requirements**

```python
conversion_ok, conversion_detail = self._verify_remote_imports(
    self.fixed_conversion_python,
    "from ultralytics import YOLO; import tensorflow, numpy; from PIL import Image; print('ok')",
    log_cb,
    "转换环境",
)
```

```text
numpy==1.26.4
Pillow==10.4.0
ultralytics==8.3.148
tensorflow==2.19.0
tf-keras==2.19.0
```

- [ ] **Step 4: Run the deploy-tool tests again**

Run: `python -m pytest test/test_deploy_manager.py -k "legacy_conversion_imports or does_not_require_onnx2tf" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_manager.py deploy_tool/requirements-conversion.txt test/test_deploy_manager.py
git commit -m "fix: align deploy checks with legacy tflite conversion"
```

### Task 4: Add replay-friendly remote verification without repeated password prompts

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Write the failing tests for single-session replay**

```python
def test_run_remote_replay_uses_existing_ssh_session(self):
    manager.client = MagicMock()
    manager.sftp = MagicMock()
    manager.remote_dir = "/srv/MetaQA_CloudTraining"
    manager.fixed_base_python = "/runtime/miniforge3/bin/python"
    manager._exec = MagicMock(return_value=(0, "PKG_OK", ""))
    logs = []
    ok, detail = manager.run_remote_package_replay("task-123", log_cb=logs.append)
    self.assertTrue(ok)
    manager._exec.assert_called_once()
    self.assertIn("PKG_OK", detail)


def test_run_remote_replay_does_not_reconnect(self):
    with patch.object(manager, "connect") as mocked_connect:
        manager.client = MagicMock()
        manager.fixed_base_python = "/runtime/miniforge3/bin/python"
        manager.remote_dir = "/srv/MetaQA_CloudTraining"
        manager._exec = MagicMock(return_value=(0, "PKG_OK", ""))
        manager.run_remote_package_replay("task-123")
    mocked_connect.assert_not_called()
```

- [ ] **Step 2: Run the replay tests to verify they fail**

Run: `python -m pytest test/test_deploy_manager.py -k "remote_replay_uses_existing_ssh_session or remote_replay_does_not_reconnect" -q`
Expected: FAIL because no dedicated replay helper exists yet.

- [ ] **Step 3: Implement a replay helper that reuses the current Paramiko session**

```python
def run_remote_package_replay(self, task_id, log_cb=None):
    if not self.client:
        return False, "未连接服务器"
    cmd = (
        f"cd {self.remote_dir} && "
        f"{self.fixed_base_python} - <<'PY'\n"
        "from app.core.package_manager import create_package\n"
        f"pkg = create_package({task_id!r})\n"
        "print(pkg['file_path'])\n"
        "PY"
    )
    code, out, err = self._exec(self.client, cmd, timeout=3600)
    return code == 0, out or err
```

- [ ] **Step 4: Run the replay tests again**

Run: `python -m pytest test/test_deploy_manager.py -k "remote_replay_uses_existing_ssh_session or remote_replay_does_not_reconnect" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/deploy_manager.py test/test_deploy_manager.py
git commit -m "feat: add single-session remote package replay helper"
```

### Task 5: Run regression, diagnostics, and a cloud replay verification

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_app_startup.py`

- [ ] **Step 1: Run the local regression suite**

Run: `python -m pytest test/test_package_manager.py test/test_deploy_manager.py test/test_app_startup.py -q`
Expected: PASS

- [ ] **Step 2: Run syntax verification**

Run: `python -m py_compile app/core/package_manager.py deploy_tool/deploy_manager.py test/test_package_manager.py test/test_deploy_manager.py test/test_app_startup.py`
Expected: PASS with no output

- [ ] **Step 3: Run diagnostics on edited files**

Use IDE diagnostics for:
- `app/core/package_manager.py`
- `deploy_tool/deploy_manager.py`
- `test/test_package_manager.py`
- `test/test_deploy_manager.py`

Expected: No new diagnostics

- [ ] **Step 4: Perform a non-training cloud replay verification**

Run the replay helper against an existing finished task, for example
`task-2026051622131441f79c73`, using the already-connected session.

Expected:
- `create_package()` succeeds
- `best_fp32.tflite` exists in the run directory
- `best_fp16.tflite` exists in the run directory
- final ZIP exists
- replay flow completes without asking for the password again

- [ ] **Step 5: Commit**

```bash
git add app/core/package_manager.py deploy_tool/deploy_manager.py deploy_tool/requirements-conversion.txt test/test_package_manager.py test/test_deploy_manager.py
git commit -m "test: verify legacy tflite rollback and replay flow"
```
