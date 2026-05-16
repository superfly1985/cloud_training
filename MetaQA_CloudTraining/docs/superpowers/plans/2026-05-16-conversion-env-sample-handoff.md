# Conversion environment sample handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move TFLite sample generation into the conversion environment and keep the deploy tool aligned with that environment boundary.

**Architecture:** `package_manager.py` stays the orchestration layer and stops building `.npy` samples inside the Web process. `_convert_tflite()` writes a conversion script that generates the sample and runs `onnx2tf` under the fixed conversion Python. The deploy tool continues to keep the Web environment light, while conversion-environment requirements and verification explicitly cover sample-generation dependencies.

**Tech Stack:** Python, unittest, sqlite3, Pillow, numpy, onnx2tf, TensorFlow, deployment helper scripts

---

### Task 1: Lock the package-manager regression with tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_convert_tflite_builds_sample_inside_conversion_script(self):
    ...
    self.assertIn("import numpy as np", captured["script"])
    self.assertIn("from PIL import Image", captured["script"])
    self.assertIn("np.save(sample_path, batch)", captured["script"])


def test_create_package_does_not_build_sample_in_web_process(self):
    ...
    mocked_build_sample.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_package_manager.py -k "sample_inside_conversion_script or does_not_build_sample_in_web_process" -q`
Expected: FAIL because the current code still builds `.npy` samples in the Web process.

- [ ] **Step 3: Write minimal implementation**

```python
def _convert_tflite(...):
    image_paths = _list_conversion_sample_images(dataset_dir) if dataset_dir else []
    script = f"""
import numpy as np
from PIL import Image
...
batch = np.stack(tensors, axis=0).astype(np.float32)
np.save(sample_path, batch)
...
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test/test_package_manager.py -k "sample_inside_conversion_script or does_not_build_sample_in_web_process" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add test/test_package_manager.py app/core/package_manager.py
git commit -m "fix: move tflite sample generation into conversion env"
```

### Task 2: Update package manager implementation

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Keep image discovery but remove Web-side sample generation from the conversion path**

```python
image_paths = _list_conversion_sample_images(dataset_dir) if dataset_dir else []
if not image_paths:
    return results
```

- [ ] **Step 2: Generate the sample in the conversion script**

```python
sample_path = os.path.join(work_dir, "_onnx2tf_input_sample.npy")
tensors = []
for image_path in image_paths:
    with Image.open(image_path) as image:
        rgb = image.convert("RGB").resize((imgsz, imgsz))
        tensors.append(np.asarray(rgb, dtype=np.float32))
batch = np.stack(tensors, axis=0).astype(np.float32)
np.save(sample_path, batch)
```

- [ ] **Step 3: Keep cleanup inside the conversion script**

```python
for path in (sample_path,):
    if os.path.exists(path):
        os.remove(path)
```

- [ ] **Step 4: Run the focused package-manager suite**

Run: `python -m pytest test/test_package_manager.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/package_manager.py test/test_package_manager.py
git commit -m "fix: run tflite prep inside conversion runtime"
```

### Task 3: Lock deploy-tool environment ownership with tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\requirements-conversion.txt`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_verify_envs_checks_numpy_and_pillow_in_conversion_env(self):
    ...
    self.assertIn("import numpy", captured["snippet"])
    self.assertIn("from PIL import Image", captured["snippet"])


def test_requirements_conversion_contains_pillow(self):
    ...
    self.assertIn("Pillow==", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test/test_deploy_manager.py -k "numpy_and_pillow or requirements_conversion_contains_pillow" -q`
Expected: FAIL because the current verification snippet and requirements file do not cover Pillow.

- [ ] **Step 3: Write minimal implementation**

```python
conversion_ok, conversion_detail = self._verify_remote_imports(
    self.fixed_conversion_python,
    "from ultralytics import YOLO; import numpy, tensorflow, onnx, onnx2tf; from PIL import Image; print('ok')",
    log_cb,
    "转换环境",
)
```

```text
Pillow==10.4.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest test/test_deploy_manager.py -k "numpy_and_pillow or requirements_conversion_contains_pillow" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add test/test_deploy_manager.py deploy_tool/deploy_manager.py deploy_tool/requirements-conversion.txt
git commit -m "fix: align deploy checks with conversion sample deps"
```

### Task 4: Run regression and syntax verification

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_app_startup.py`

- [ ] **Step 1: Run the main regression set**

Run: `python -m pytest test/test_package_manager.py test/test_deploy_manager.py test/test_app_startup.py -q`
Expected: PASS

- [ ] **Step 2: Run syntax verification**

Run: `python -m py_compile app/core/package_manager.py deploy_tool/deploy_manager.py test/test_package_manager.py test/test_deploy_manager.py`
Expected: PASS with no output

- [ ] **Step 3: Run diagnostics on edited files**

Use IDE diagnostics for:
- `app/core/package_manager.py`
- `deploy_tool/deploy_manager.py`
- `test/test_package_manager.py`
- `test/test_deploy_manager.py`

Expected: No new diagnostics

- [ ] **Step 4: Commit**

```bash
git add app/core/package_manager.py deploy_tool/deploy_manager.py deploy_tool/requirements-conversion.txt test/test_package_manager.py test/test_deploy_manager.py
git commit -m "test: verify conversion env sample handoff changes"
```
