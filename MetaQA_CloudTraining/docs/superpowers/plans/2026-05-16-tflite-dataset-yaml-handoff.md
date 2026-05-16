# TFLite dataset YAML handoff implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure packaged TFLite conversion can always access the training
task's effective YAML by copying it into the run directory and adding a
package-time fallback lookup to the dataset directory.

**Architecture:** Keep the training-side YAML generation in
`app/core/training_manager.py`, but copy the generated file into the task
run directory so each run becomes self-contained. Update
`app/core/package_manager.py` to resolve YAML from the run directory first
and fall back to the dataset directory for old tasks, then keep the
package ZIP using the actual YAML chosen for conversion.

**Tech Stack:** Python, SQLite, pytest, zipfile

---

### Task 1: Lock YAML handoff behavior in tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_training_start.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\training_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] **Step 1: Write the failing training-side test**

```python
def test_start_training_copies_effective_data_yaml_into_run_dir():
    training_manager._start_training(task_id)
    assert os.path.exists(os.path.join(run_dir, "data.yaml"))
```

- [ ] **Step 2: Write the failing package fallback tests**

```python
def test_create_package_prefers_run_dir_yaml_for_tflite():
    pkg = package_manager.create_package(task_id)
    assert calls["dataset_yaml"] == os.path.join(run_dir, "data.yaml")

def test_create_package_falls_back_to_dataset_dir_yaml():
    pkg = package_manager.create_package(task_id)
    assert calls["dataset_yaml"] == os.path.join(dataset_dir, "data.yaml")
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest "test/test_training_start.py" "test/test_package_manager.py" -k "data_yaml or dataset_dir_yaml or run_dir_yaml" -q
```

Expected: FAIL because the current code does not copy the YAML into the
run directory and only looks in the training output directory during
packaging.

### Task 2: Implement training-side YAML handoff

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\training_manager.py`

- [ ] **Step 1: Copy the effective YAML into the run directory**

```python
run_data_yaml = os.path.join(run_dir, "data.yaml")
shutil.copy2(data_yaml, run_data_yaml)
```

Use the YAML that `_generate_data_yaml()` just produced, not the uploaded
archive's original file.

- [ ] **Step 2: Keep training script input unchanged or explicitly point it
to the copied run YAML**

```python
script_path = _generate_train_script(row, run_data_yaml, run_dir)
```

Make sure the training script and the copied run file stay in sync.

- [ ] **Step 3: Run the focused training test**

Run:

```bash
python -m pytest "test/test_training_start.py" -k "data_yaml" -q
```

Expected: PASS.

### Task 3: Implement package-time YAML resolution fallback

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] **Step 1: Add a focused YAML resolver**

```python
def _resolve_conversion_yaml(task_row, run_dir, train_dir):
    ...
```

Search in this order:

1. `train_dir/data.yaml`
2. `train_dir/dataset.yaml`
3. `run_dir/data.yaml`
4. `run_dir/dataset.yaml`
5. dataset directory `data.yaml`
6. dataset directory `dataset.yaml`

- [ ] **Step 2: Use the resolved YAML for conversion and packaging**

```python
data_yaml = _resolve_conversion_yaml(task, run_dir, train_dir)
```

Use the resolved path for `_convert_tflite()` and for the packaged
`dataset.yaml` file.

- [ ] **Step 3: Keep missing-YAML failure explicit**

```python
conversion_errors.append("TFLite 导出失败（缺少 dataset.yaml）")
```

Only emit this when every resolver path fails.

- [ ] **Step 4: Run the focused package tests**

Run:

```bash
python -m pytest "test/test_package_manager.py" -k "run_dir_yaml or dataset_dir_yaml or dataset_yaml" -q
```

Expected: PASS.

### Task 4: Run regression verification and cloud-ready checks

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\training_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_training_start.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Run targeted regressions**

Run:

```bash
python -m pytest "test/test_training_start.py" "test/test_package_manager.py" -q
```

- [ ] **Step 2: Run syntax verification**

Run:

```bash
python -m py_compile "app/core/training_manager.py" "app/core/package_manager.py" "test/test_training_start.py" "test/test_package_manager.py"
```

- [ ] **Step 3: Run diff hygiene and diagnostics**

Run:

```bash
git diff --check -- "app/core/training_manager.py" "app/core/package_manager.py" "test/test_training_start.py" "test/test_package_manager.py" "docs/superpowers/specs/2026-05-16-tflite-dataset-yaml-handoff-design.md" "docs/superpowers/plans/2026-05-16-tflite-dataset-yaml-handoff.md"
```

Then check editor diagnostics for all modified files and fix any
introduced issues.
