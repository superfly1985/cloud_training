# ONNX to TFLite package conversion implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken package-time `ONNX -> Ultralytics -> TFLite`
path with an `onnx2tf` conversion flow that generates both `fp32` and
`fp16` TFLite models and passes `dataset.yaml` into the conversion step.

**Architecture:** Keep ONNX export in the training environment and move
all TFLite generation to the conversion environment. Implement the new
logic inside `app/core/package_manager.py`, passing the resolved
`dataset.yaml` path into `_convert_tflite()` and generating canonical
`best_fp32.tflite` and `best_fp16.tflite` files in the training run
directory.

**Tech Stack:** Python, `subprocess`, `onnx2tf`, `unittest`, `pytest`

---

### Task 1: Lock the new package conversion contract in tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] Add a failing test that verifies `create_package()` passes the
  training run `data.yaml` path into `_convert_tflite()`.
- [ ] Add a failing test that verifies conversion metadata becomes
  `complete` when both `best_fp32.tflite` and `best_fp16.tflite` exist.
- [ ] Run:

```bash
python -m pytest "test/test_package_manager.py" -k "dataset_yaml or conversion_complete" -q
```

Expected: FAIL because `_convert_tflite()` does not accept or receive
the dataset YAML path yet.

### Task 2: Replace the broken ONNX conversion implementation

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] Update `create_package()` to resolve `data.yaml` before TFLite
  conversion and pass it into `_convert_tflite()`.
- [ ] Rewrite `_convert_tflite()` so it validates `onnx_path`,
  `python_cmd`, and `dataset_yaml`, then runs an `onnx2tf` script that
  produces both `best_fp32.tflite` and `best_fp16.tflite` without any
  `int8` conversion.
- [ ] Return the generated canonical TFLite paths from
  `_convert_tflite()`.
- [ ] Run:

```bash
python -m pytest "test/test_package_manager.py" -k "dataset_yaml or conversion_complete" -q
```

Expected: PASS.

### Task 3: Verify the generated conversion script contract

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] Add a failing test that intercepts the `_convert_tflite()`
  subprocess call and asserts the generated script references
  `onnx2tf`, writes both `best_fp32.tflite` and `best_fp16.tflite`,
  passes the dataset YAML path, and does not request `int8`.
- [ ] Run:

```bash
python -m pytest "test/test_package_manager.py" -k "onnx2tf" -q
```

Expected: FAIL before the implementation fully matches the contract.

### Task 4: Run focused verification

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] Run the full focused package test file:

```bash
python -m pytest "test/test_package_manager.py" -q
```

- [ ] Run syntax verification:

```bash
python -m py_compile "app/core/package_manager.py" "test/test_package_manager.py"
```

- [ ] Check editor diagnostics for both modified files and fix any
  introduced issues.
