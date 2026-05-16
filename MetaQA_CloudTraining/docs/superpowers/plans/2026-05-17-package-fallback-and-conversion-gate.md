# Package fallback and conversion gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the legacy three-stage TFLite conversion fallback chain for
package creation and align deploy-time plus runtime conversion gates to the
same lightweight legacy contract.

**Architecture:** `app/core/package_manager.py` stays the package orchestration
module, but `_convert_tflite()` gains the same staged fallback order used by
the legacy `ModelManager`: direct scripted `YOLO.export()`, then
`python -m ultralytics export`, then `yolo export`. `app/core/system_manager.py`
and `deploy_tool/deploy_manager.py` both enforce the same conversion gate so
deployment validation and runtime validation no longer disagree about what
"conversion environment is ready" means.

**Tech Stack:** Python, unittest, subprocess, Ultralytics, TensorFlow, Pillow,
numpy

---

### Task 1: lock the package fallback chain with failing tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Write the failing fallback tests**

```python
def test_convert_tflite_falls_back_to_python_module_export_after_script_failure(self):
    train_dir = os.path.join(self.tempdir.name, "train")
    os.makedirs(train_dir, exist_ok=True)
    best_pt = os.path.join(train_dir, "best.pt")
    dataset_yaml = os.path.join(train_dir, "data.yaml")
    open(best_pt, "wb").write(b"pt")
    open(dataset_yaml, "w", encoding="utf-8").write("path: /dataset\nnc: 1\nnames: ['x']\n")

    calls = []

    def fake_run(cmd, capture_output, text, timeout, cwd):
        calls.append(("script", cmd))
        class Result:
            returncode = 1
            stdout = ""
            stderr = "script failed"
        return Result()

    def fake_subprocess_cmd(command, timeout=3600):
        calls.append(("remote", command))
        if "-m ultralytics export" in command:
            fp32 = os.path.join(train_dir, "best_fp32.tflite")
            fp16 = os.path.join(train_dir, "best_fp16.tflite")
            open(fp32, "wb").write(b"fp32")
            open(fp16, "wb").write(b"fp16")
            return True, "ok"
        return False, "unexpected"

    with patch("app.core.package_manager.subprocess.run", side_effect=fake_run), \
         patch.object(package_manager, "_run_shell_command", side_effect=fake_subprocess_cmd):
        outputs = package_manager._convert_tflite(
            best_pt,
            sys.executable,
            "both",
            train_dir,
            dataset_yaml,
            640,
        )

    self.assertEqual(2, len(outputs))
    self.assertTrue(any("-m ultralytics export" in cmd for kind, cmd in calls if kind == "remote"))


def test_convert_tflite_falls_back_to_yolo_cli_after_python_module_failure(self):
    train_dir = os.path.join(self.tempdir.name, "train")
    os.makedirs(train_dir, exist_ok=True)
    best_pt = os.path.join(train_dir, "best.pt")
    dataset_yaml = os.path.join(train_dir, "data.yaml")
    open(best_pt, "wb").write(b"pt")
    open(dataset_yaml, "w", encoding="utf-8").write("path: /dataset\nnc: 1\nnames: ['x']\n")

    calls = []

    def fake_run(cmd, capture_output, text, timeout, cwd):
        calls.append(("script", cmd))
        class Result:
            returncode = 1
            stdout = ""
            stderr = "script failed"
        return Result()

    def fake_subprocess_cmd(command, timeout=3600):
        calls.append(("remote", command))
        if "-m ultralytics export" in command:
            return False, "module export failed"
        if command.startswith("yolo export "):
            fp32 = os.path.join(train_dir, "best_fp32.tflite")
            fp16 = os.path.join(train_dir, "best_fp16.tflite")
            open(fp32, "wb").write(b"fp32")
            open(fp16, "wb").write(b"fp16")
            return True, "ok"
        return False, "unexpected"

    with patch("app.core.package_manager.subprocess.run", side_effect=fake_run), \
         patch.object(package_manager, "_run_shell_command", side_effect=fake_subprocess_cmd):
        outputs = package_manager._convert_tflite(
            best_pt,
            sys.executable,
            "both",
            train_dir,
            dataset_yaml,
            640,
        )

    self.assertEqual(2, len(outputs))
    self.assertTrue(any(cmd.startswith("yolo export ") for kind, cmd in calls if kind == "remote"))
```

- [ ] **Step 2: Run the focused tests to verify red**

Run: `python -m pytest test/test_package_manager.py -k "falls_back_to_python_module_export or falls_back_to_yolo_cli" -q`
Expected: FAIL because `_convert_tflite()` only runs the scripted
`YOLO.export()` path today.

- [ ] **Step 3: Add one more failing test for fail-closed behavior**

```python
def test_create_package_stays_fail_closed_when_all_three_conversion_stages_fail(self):
    self._insert_task("task-all-fail")

    with patch.object(package_manager, "get_connection", return_value=self.conn), \
         patch.object(package_manager, "get_data_dir", side_effect=self._fake_get_data_dir), \
         patch.object(package_manager, "_export_onnx", return_value=None), \
         patch.object(package_manager, "_convert_tflite", return_value=[]):
        with self.assertRaises(ValueError):
            package_manager.create_package("task-all-fail")
```

- [ ] **Step 4: Run the new fail-closed test**

Run: `python -m pytest test/test_package_manager.py -k "all_three_conversion_stages_fail" -q`
Expected: PASS if existing fail-closed behavior still holds. If it fails, note
the regression before touching implementation.

- [ ] **Step 5: Commit the red test changes**

```bash
git add test/test_package_manager.py
git commit -m "test: lock legacy package fallback chain"
```

### Task 2: implement the legacy three-stage package fallback chain

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Add a small shell-command helper for fallback stages**

```python
def _run_shell_command(command: str, timeout: int = 3600) -> tuple[bool, str]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=None,
        shell=True,
    )
    return result.returncode == 0, (result.stdout or result.stderr or "")
```

- [ ] **Step 2: Keep the direct scripted export, but make it stage 1 only**

```python
script = f"""
import os
os.environ['YOLO_AUTOINSTALL'] = '0'
os.environ['ULTRALYTICS_AUTOINSTALL'] = '0'
from ultralytics import YOLO
import glob
import json
import shutil
import sys
model = YOLO(best_pt)
model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=False, nms=True, data=dataset_yaml)
model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=True, nms=True, data=dataset_yaml)
"""
```

- [ ] **Step 3: Extract output discovery into a helper reused by all stages**

```python
def _collect_generated_tflite_outputs(work_dir: str, saved_model_dir: str, stem: str) -> list[str]:
    fp32_src = ""
    fp16_src = ""
    for fp in sorted(glob.glob(os.path.join(saved_model_dir, "*.tflite"))):
        low = os.path.basename(fp).lower()
        if "float16" in low and not fp16_src:
            fp16_src = fp
        elif not fp32_src:
            fp32_src = fp
    normalized_paths = []
    if fp32_src:
        fp32_dst = os.path.join(work_dir, f"{stem}_fp32.tflite")
        shutil.copy2(fp32_src, fp32_dst)
        normalized_paths.append(fp32_dst)
    if fp16_src:
        fp16_dst = os.path.join(work_dir, f"{stem}_fp16.tflite")
        shutil.copy2(fp16_src, fp16_dst)
        normalized_paths.append(fp16_dst)
    return normalized_paths
```

- [ ] **Step 4: Implement stage 2 fallback with `python -m ultralytics export`**

```python
cmd = (
    f'"{python_cmd}" -m ultralytics export '
    f'model="{best_pt}" format=tflite imgsz={imgsz} int8=False nms=True data="{dataset_yaml}"'
)
ok, out = _run_shell_command(cmd)
if ok:
    outputs = _collect_generated_tflite_outputs(work_dir, saved_model_dir, stem)
    if outputs:
        return outputs
```

- [ ] **Step 5: Implement stage 3 fallback with `yolo export`**

```python
cmd = (
    f'yolo export model="{best_pt}" format=tflite '
    f'imgsz={imgsz} int8=False nms=True data="{dataset_yaml}"'
)
ok, out = _run_shell_command(cmd)
if ok:
    outputs = _collect_generated_tflite_outputs(work_dir, saved_model_dir, stem)
    if outputs:
        return outputs
```

- [ ] **Step 6: Preserve fail-closed behavior and emit useful errors**

```python
errors = [script_err, module_err, cli_err]
if not results:
    logger.error("TFLite 转换失败: " + " | ".join(err for err in errors if err))
```

- [ ] **Step 7: Run the focused package-manager tests**

Run: `python -m pytest test/test_package_manager.py -k "falls_back_to_python_module_export or falls_back_to_yolo_cli or all_three_conversion_stages_fail" -q`
Expected: PASS

- [ ] **Step 8: Run the full package-manager suite**

Run: `python -m pytest test/test_package_manager.py -q`
Expected: PASS

- [ ] **Step 9: Commit the package fallback implementation**

```bash
git add app/core/package_manager.py test/test_package_manager.py
git commit -m "feat: restore legacy package tflite fallback chain"
```

### Task 3: align runtime and deploy-time conversion gates

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\system_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_system_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Write the failing runtime-gate test**

```python
def test_check_conversion_gate_uses_lightweight_legacy_import_contract(self):
    with patch.object(system_manager, "_get_convert_python_cmd", return_value="/tmp/py"), \
         patch.object(system_manager, "_run_python_snippet", return_value=(True, "ok", "")) as run_mock:
        result = system_manager._check_conversion_gate()

    self.assertEqual(result["status"], "pass")
    code = run_mock.call_args.args[1]
    self.assertIn("from ultralytics import YOLO", code)
    self.assertIn("import tensorflow as tf", code)
    self.assertIn("import numpy", code)
    self.assertIn("from PIL import Image", code)
    self.assertIn("import onnx2tf", code)
    self.assertNotIn("onnxscript", code)
    self.assertNotIn("onnx_ir", code)
```

- [ ] **Step 2: Update the deploy-gate test to the same contract**

```python
self.assertIn("from ultralytics import YOLO", conversion_call.args[1])
self.assertIn("import tensorflow", conversion_call.args[1])
self.assertIn("import numpy", conversion_call.args[1])
self.assertIn("from PIL import Image", conversion_call.args[1])
self.assertIn("import onnx2tf", conversion_call.args[1])
self.assertNotIn("onnxscript", conversion_call.args[1])
self.assertNotIn("onnx_ir", conversion_call.args[1])
self.assertNotIn("FLOAT4E2M1", conversion_call.args[1])
```

- [ ] **Step 3: Run the focused gate tests to verify red**

Run: `python -m pytest test/test_system_manager.py -k "lightweight_legacy_import_contract" -q`
Expected: FAIL because the runtime-gate test does not exist yet.

Run: `python -m pytest test/test_deploy_manager.py -k "legacy_conversion_imports" -q`
Expected: FAIL because deploy validation currently checks the heavier contract.

- [ ] **Step 4: Simplify the runtime gate implementation**

```python
code = (
    "import tensorflow as tf; "
    "import numpy; "
    "from PIL import Image; "
    "from ultralytics import YOLO; "
    "import onnx2tf; "
    "print('ok')"
)
```

- [ ] **Step 5: Simplify the deploy-time gate implementation to the same contract**

```python
conversion_ok, conversion_detail = self._verify_remote_imports(
    self.fixed_conversion_python,
    "from ultralytics import YOLO; import tensorflow; import numpy; from PIL import Image; import onnx2tf; print('ok')",
    log_cb,
    "转换环境",
)
```

- [ ] **Step 6: Run the focused gate tests again**

Run: `python -m pytest test/test_system_manager.py -k "lightweight_legacy_import_contract" -q`
Expected: PASS

Run: `python -m pytest test/test_deploy_manager.py -k "legacy_conversion_imports" -q`
Expected: PASS

- [ ] **Step 7: Run the full runtime and deploy suites**

Run: `python -m pytest test/test_system_manager.py test/test_deploy_manager.py -q`
Expected: PASS

- [ ] **Step 8: Commit the gate-alignment changes**

```bash
git add app/core/system_manager.py deploy_tool/deploy_manager.py test/test_system_manager.py test/test_deploy_manager.py
git commit -m "refactor: align conversion gates with legacy runtime contract"
```

### Task 4: final verification

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\system_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`

- [ ] **Step 1: Run the combined targeted regression**

Run: `python -m pytest test/test_package_manager.py test/test_system_manager.py test/test_deploy_manager.py -q`
Expected: PASS

- [ ] **Step 2: Check diagnostics for touched files**

Run the IDE diagnostics tool for:

```text
app/core/package_manager.py
app/core/system_manager.py
deploy_tool/deploy_manager.py
test/test_package_manager.py
test/test_system_manager.py
test/test_deploy_manager.py
```

Expected: no new diagnostics introduced by the change.

- [ ] **Step 3: Perform one cloud replay after deployment**

Run:

```bash
python -m pytest test/test_deploy_manager.py -k "run_remote_package_replay" -q
```

Then use the deploy GUI to redeploy and trigger one remote package replay for
the latest failed task. Expected: the logs now show all three conversion stages
in order before reporting final success or a narrowed conversion failure.

- [ ] **Step 4: Commit the final verification snapshot**

```bash
git add app/core/package_manager.py app/core/system_manager.py deploy_tool/deploy_manager.py test/test_package_manager.py test/test_system_manager.py test/test_deploy_manager.py
git commit -m "test: verify legacy package fallback alignment"
```
