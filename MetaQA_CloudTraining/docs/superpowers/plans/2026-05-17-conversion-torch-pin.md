# Conversion torch pin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the deploy tool as the only change surface while pinning the
`cloud-conversion` environment to a legacy-compatible `torch` stack that avoids
the newer `torch.onnx` exporter path failing on `onnx_ir.DataType.FLOAT4E2M1`.

**Architecture:** The deploy tool continues to own fixed-environment creation,
requirements syncing, and remote verification. The change narrows to
`deploy_tool/requirements-conversion.txt`, the conversion-environment import
probe in `deploy_tool/deploy_manager.py`, and focused tests in
`test/test_deploy_manager.py`. The new behavior makes the deploy tool assert
the intended `torch` family is present instead of letting `cloud-conversion`
float to a newer exporter stack at runtime.

**Tech Stack:** Python, unittest, Paramiko, pip requirements locks, PyTorch,
Ultralytics, ONNX

---

### Task 1: Lock the conversion torch contract with tests

**Files:**
- Modify:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`
- Test:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_step_verify_envs_checks_conversion_torch_version_guard(self):
    manager = DeployManager()
    manager._verify_remote_imports = Mock(side_effect=[(True, "ok"), (True, "ok"), (True, "ok")])

    ok, _ = manager._step_verify_envs(log_cb=lambda _msg: None)

    self.assertTrue(ok)
    conversion_call = manager._verify_remote_imports.call_args_list[2]
    self.assertIn("import torch", conversion_call.args[1])
    self.assertIn("torch.__version__", conversion_call.args[1])
    self.assertIn("startswith('2.6.')", conversion_call.args[1])


def test_requirements_conversion_pins_legacy_torch_stack(self):
    requirements_path = os.path.join(PROJECT_ROOT, "deploy_tool", "requirements-conversion.txt")
    text = Path(requirements_path).read_text(encoding="utf-8")

    self.assertIn("torch==2.6.0+cu124", text)
    self.assertIn("torchvision==0.21.0+cu124", text)
    self.assertIn("torchaudio==2.6.0+cu124", text)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
`python -m pytest test/test_deploy_manager.py -k "conversion_torch_version_guard or pins_legacy_torch_stack" -q`
Expected: FAIL because the deploy tool does not currently pin conversion
`torch`, and the conversion-environment probe does not check it.

- [ ] **Step 3: Write the minimal implementation**

```python
conversion_ok, conversion_detail = self._verify_remote_imports(
    self.fixed_conversion_python,
    "import torch; assert torch.__version__.startswith('2.6.'); ...",
    log_cb,
    "转换环境",
)
```

```text
--extra-index-url https://download.pytorch.org/whl/cu124
torch==2.6.0+cu124
torchvision==0.21.0+cu124
torchaudio==2.6.0+cu124
```

- [ ] **Step 4: Run the focused tests again**

Run:
`python -m pytest test/test_deploy_manager.py -k "conversion_torch_version_guard or pins_legacy_torch_stack" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add test/test_deploy_manager.py deploy_tool/deploy_manager.py deploy_tool/requirements-conversion.txt
git commit -m "test: lock conversion torch runtime in deploy tool"
```

### Task 2: Keep the conversion environment aligned with the pinned stack

**Files:**
- Modify:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\requirements-conversion.txt`
- Modify:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Test:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Keep the PyTorch wheel source explicit**

```text
--extra-index-url https://download.pytorch.org/whl/cu124
```

- [ ] **Step 2: Pin the conversion environment to the legacy-compatible torch family**

```text
torch==2.6.0+cu124
torchvision==0.21.0+cu124
torchaudio==2.6.0+cu124
```

- [ ] **Step 3: Extend the conversion probe so deployment fails before runtime drift**

```python
"import torch; assert torch.__version__.startswith('2.6.'); "
"from ultralytics import YOLO; import tensorflow; import numpy; "
"from PIL import Image; import onnx; from onnx import TensorProto; "
"assert hasattr(TensorProto, 'FLOAT4E2M1'); import onnx2tf; "
"import onnxscript; import onnx_ir; print('ok')"
```

- [ ] **Step 4: Run the deploy-manager suite**

Run: `python -m pytest test/test_deploy_manager.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add deploy_tool/requirements-conversion.txt deploy_tool/deploy_manager.py test/test_deploy_manager.py
git commit -m "fix: pin conversion torch stack in deploy tool"
```

### Task 3: Verify the edited deployment files stay clean

**Files:**
- Verify:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Verify:
  `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] **Step 1: Run diagnostics on the edited files**

Run diagnostics for:
`deploy_tool/deploy_manager.py`
`test/test_deploy_manager.py`
Expected: no new diagnostics

- [ ] **Step 2: Summarize the redeploy checkpoint**

```text
After local verification passes, redeploy with the updated deploy tool, watch
"安装 cloud-conversion 锁定依赖" for the pinned torch stack, then re-run a cloud
training or replay to confirm the runtime no longer drifts to torch 2.12.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/plans/2026-05-17-conversion-torch-pin.md
git commit -m "docs: add conversion torch pin plan"
```
