# TFLite sample and package visibility implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TFLite conversion use local dataset samples instead of
`onnx2tf`'s downloaded test data, prevent failed or incomplete packages from
becoming visible products, and make package creation idempotent per task.

**Architecture:** Keep conversion and package creation centered in
`app/core/package_manager.py`, but split the new behavior into small helpers:
sample generation for `onnx2tf`, a stricter package lifecycle that only
inserts a package row after a successful ZIP, and an idempotent guard around
automatic package creation. Update the training/monitor flow so training tasks
show process states while the package list only shows finished ZIP artifacts.

**Tech Stack:** Python, SQLite, pytest, zipfile, NumPy, Pillow, Vue

---

### Task 1: Lock local sample generation in tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] **Step 1: Write a failing test for local sample generation**

```python
def test_convert_tflite_passes_local_sample_npy_to_onnx2tf(self):
    ...
    self.assertIn("custom_input_op_name_np_data_path", captured["script"])
```

The test must assert that `_convert_tflite()` writes a script containing a
local `.npy` sample path and no longer relies on the default downloaded
sample behavior.

- [ ] **Step 2: Write a failing test for sample source priority**

```python
def test_build_conversion_sample_prefers_val_images(self):
    sample_path = package_manager._build_conversion_sample(...)
    self.assertTrue(os.path.exists(sample_path))
```

Create both `images/val` and `images/train`, then assert the helper uses the
validation side first. Add a second test for the `images/train` fallback when
`images/val` is empty.

- [ ] **Step 3: Run the focused test set to verify failure**

Run:

```bash
python -m pytest "test/test_package_manager.py" -k "local_sample or sample_prefers_val or sample_falls_back_to_train" -q
```

Expected: FAIL because the current conversion code does not build any local
sample input.

### Task 2: Implement local `.npy` sample generation

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] **Step 1: Add a helper that finds source images from the task dataset**

```python
def _list_conversion_sample_images(dataset_dir: str) -> list[str]:
    ...
```

Search `images/val` first, then `images/train`, and only return a small set of
actual image files.

- [ ] **Step 2: Add a helper that builds a local `.npy` input sample**

```python
def _build_conversion_sample(task_row, dataset_dir: str, work_dir: str) -> str | None:
    ...
```

Use Pillow to load images, resize them to `task_row["input_size"]`, convert to
RGB, normalize to `float32`, stack to `NHWC`, and save a temporary `.npy`
inside `work_dir`.

- [ ] **Step 3: Pass the generated sample into `onnx2tf.convert()`**

```python
convert(
    ...,
    custom_input_op_name_np_data_path=[["images", sample_npy_path, mean, std]],
)
```

Keep the existing `fp32` and `fp16` output behavior. Do not add `int8`.

- [ ] **Step 4: Clean up temporary sample files after conversion**

```python
if sample_npy_path and os.path.exists(sample_npy_path):
    os.remove(sample_npy_path)
```

- [ ] **Step 5: Run the focused local-sample tests**

Run:

```bash
python -m pytest "test/test_package_manager.py" -k "local_sample or sample_prefers_val or sample_falls_back_to_train" -q
```

Expected: PASS.

### Task 3: Lock package visibility and idempotency in tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_monitor_refresh.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`

- [ ] **Step 1: Write a failing test for failed conversion invisibility**

```python
def test_create_package_does_not_insert_row_when_tflite_conversion_fails(self):
    with self.assertRaises(ValueError):
        package_manager.create_package("task-failed-convert")
```

The test must verify that no `packages` row is inserted and no visible package
dict is returned when TFLite generation fails.

- [ ] **Step 2: Write a failing test for single package row per task**

```python
def test_ensure_package_returns_existing_row_for_same_task(self):
    first = package_manager.create_package(task_id)
    second = package_manager.ensure_package(task_id)
    self.assertEqual(first["id"], second["id"])
```

Also assert that the database still contains exactly one row for that task.

- [ ] **Step 3: Write a failing monitor-side test**

```python
def test_refresh_task_metrics_does_not_duplicate_package_when_already_created(self):
    ...
```

This test should prove that monitor refresh no longer creates an extra package
record after the training watcher already created one.

- [ ] **Step 4: Run the focused visibility/idempotency tests**

Run:

```bash
python -m pytest "test/test_package_manager.py" "test/test_monitor_refresh.py" -k "does_not_insert_row or existing_row_for_same_task or does_not_duplicate_package" -q
```

Expected: FAIL with the current behavior.

### Task 4: Implement package lifecycle and idempotency changes

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\training_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\models\database.py`

- [ ] **Step 1: Add a unique package constraint for `task_id`**

```python
CREATE UNIQUE INDEX IF NOT EXISTS idx_packages_task_id_unique
ON packages(task_id)
WHERE task_id != '';
```

Place this in the database migration/bootstrap path so existing databases pick
it up safely.

- [ ] **Step 2: Make package creation fail closed**

```python
if conversion_failed:
    raise ValueError("TFLite 转换失败，未生成最终产物包")
```

Do not insert into `packages` unless the ZIP file has been successfully built
and all required outputs exist.

- [ ] **Step 3: Make `ensure_package()` handle concurrency safely**

```python
try:
    insert ...
except sqlite3.IntegrityError:
    return existing
```

Use the unique constraint as the final guard, not only a pre-query.

- [ ] **Step 4: Keep only one automatic package trigger**

```python
if final_status == "completed":
    ensure_package(task_id)
```

Retain the training watcher as the package creator and remove monitor refresh
from direct package creation. Monitor refresh should update task status only.

- [ ] **Step 5: Add explicit task sub-status transitions**

```python
conn.execute("UPDATE training_tasks SET status='converting' WHERE id=?", ...)
conn.execute("UPDATE training_tasks SET status='packaging' WHERE id=?", ...)
```

Use them around ONNX/TFLite/ZIP steps so the frontend can reflect the process.

- [ ] **Step 6: Run the focused package lifecycle tests**

Run:

```bash
python -m pytest "test/test_package_manager.py" "test/test_monitor_refresh.py" -k "does_not_insert_row or existing_row_for_same_task or does_not_duplicate_package" -q
```

Expected: PASS.

### Task 5: Hide incomplete products in the frontend

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\training-tab.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\package-tab.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\api.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\mock-api.js`

- [ ] **Step 1: Write the failing frontend expectation in mock data tests or fixture-driven checks**

```javascript
// package list should only contain completed ZIP artifacts
```

If there is no frontend test harness, encode the expectation in mock data and
manual verification notes instead of adding noisy test scaffolding.

- [ ] **Step 2: Remove incomplete package entry points from the UI**

```javascript
if (task.status === 'completed' && task.package_id) { ... }
```

Show package navigation only when a finished package actually exists.

- [ ] **Step 3: Map process states in the training list**

```javascript
var map = { running: "训练中", converting: "转换中", packaging: "打包中", completed: "已完成", failed: "失败" };
```

- [ ] **Step 4: Run frontend syntax verification**

Run:

```bash
node --check "static/js/training-tab.js"
node --check "static/js/package-tab.js"
node --check "static/js/api.js"
node --check "static/js/mock-api.js"
```

Expected: PASS.

### Task 6: Run full verification

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\training_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\models\database.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_monitor_refresh.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_training_start.py`

- [ ] **Step 1: Run Python regressions**

Run:

```bash
python -m pytest "test/test_training_start.py" "test/test_package_manager.py" "test/test_monitor_refresh.py" -q
```

- [ ] **Step 2: Run Python syntax checks**

Run:

```bash
python -m py_compile "app/core/training_manager.py" "app/core/monitor_manager.py" "app/core/package_manager.py" "app/models/database.py" "test/test_training_start.py" "test/test_package_manager.py" "test/test_monitor_refresh.py"
```

- [ ] **Step 3: Run diff hygiene**

Run:

```bash
git diff --check -- "app/core/training_manager.py" "app/core/monitor_manager.py" "app/core/package_manager.py" "app/models/database.py" "static/js/training-tab.js" "static/js/package-tab.js" "static/js/api.js" "static/js/mock-api.js" "test/test_training_start.py" "test/test_package_manager.py" "test/test_monitor_refresh.py" "docs/superpowers/specs/2026-05-16-tflite-sample-and-package-visibility-design.md" "docs/superpowers/plans/2026-05-16-tflite-sample-and-package-visibility.md"
```

- [ ] **Step 4: Check diagnostics for all modified files**

Use the editor diagnostics tool on every modified Python, JavaScript, and
Markdown file and fix any introduced issues before finishing.
