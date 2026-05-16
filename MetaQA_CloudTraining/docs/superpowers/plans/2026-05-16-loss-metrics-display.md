# Loss metrics display implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make training curves, the training list, and the package list all
show `box_loss`, `cls_loss`, and `dfl_loss` as the primary displayed
metrics.

**Architecture:** Extend the backend metrics pipeline so `dfl_loss` is
parsed from `results.csv`, stored on `training_tasks`, and written into
package `info.json`. Then update the frontend chart modal and the two
list views to replace `mAP@50` displays with a three-line loss block,
while keeping old records compatible by showing `-` for missing values.

**Tech Stack:** Python, SQLite, FastAPI, JavaScript, Vue, pytest

---

### Task 1: Lock backend `dfl_loss` behavior in tests

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_monitor_refresh.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] **Step 1: Write the failing monitor test**

```python
def test_refresh_task_metrics_updates_dfl_loss(...):
    metrics = monitor_manager.refresh_task_metrics(task_id)
    assert metrics["dfl_loss"] == 0.345
```

- [ ] **Step 2: Write the failing package test**

```python
def test_create_package_writes_loss_metrics_into_info_json(...):
    pkg = package_manager.create_package(task_id)
    assert info["box_loss"] == 0.12
    assert info["cls_loss"] == 0.23
    assert info["dfl_loss"] == 0.34
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
python -m pytest "test/test_monitor_refresh.py" "test/test_package_manager.py" -k "dfl_loss or loss_metrics" -q
```

Expected: FAIL because backend code does not yet parse, store, or write
`dfl_loss`.

### Task 2: Implement backend `dfl_loss` pipeline

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\models\database.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\models\schemas.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`

- [ ] **Step 1: Add storage support**

```python
def _ensure_column(conn, table, column, ddl):
    ...
```

Add `dfl_loss REAL DEFAULT 0` to `training_tasks` and make startup
idempotently add the column for existing databases.

- [ ] **Step 2: Extend schemas and monitor parsing**

```python
class TrainingInfo(BaseModel):
    ...
    dfl_loss: float = 0
```

Parse `train/dfl_loss` from `results.csv`, return it from
`get_loss_curve()`, and write it during `refresh_task_metrics()`.

- [ ] **Step 3: Write losses into package metadata**

```python
info = {
    ...
    "box_loss": task["box_loss"],
    "cls_loss": task["cls_loss"],
    "dfl_loss": task["dfl_loss"],
}
```

Also expose those fields in package rows loaded from `info.json`, with
graceful fallback when old ZIP files do not contain them.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python -m pytest "test/test_monitor_refresh.py" "test/test_package_manager.py" -k "dfl_loss or loss_metrics" -q
```

Expected: PASS.

### Task 3: Lock frontend loss display behavior in tests or focused checks

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\training-tab.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\package-tab.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\modals.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\mock-api.js`

- [ ] **Step 1: Update mock data contract first**

```javascript
task.dfl_loss = current > 0 ? +(0.3 - (current / epochs) * 0.2 + Math.random() * 0.02).toFixed(3) : 0;
```

Make the mock API return `dfl_loss` for task lists, logs, and loss curve
data so UI changes can be verified consistently.

- [ ] **Step 2: Replace training chart series**

```javascript
var series = [
  { data: data.box_loss, color: "#2563eb", label: "Box Loss" },
  { data: data.cls_loss, color: "#dc2626", label: "Cls Loss" },
  { data: data.dfl_loss, color: "#16a34a", label: "DFL Loss" },
];
```

- [ ] **Step 3: Replace table columns with three-line loss blocks**

```javascript
<th>损失值</th>
...
<div class="loss-stack">
  <div>box: {{ formatLoss(task.box_loss) }}</div>
  <div>cls: {{ formatLoss(task.cls_loss) }}</div>
  <div>dfl: {{ formatLoss(task.dfl_loss) }}</div>
</div>
```

Apply the same pattern to the training list and package list, showing `-`
for missing values.

- [ ] **Step 4: Run focused syntax checks**

Run:

```bash
node --check "static/js/training-tab.js"
node --check "static/js/package-tab.js"
node --check "static/js/modals.js"
node --check "static/js/mock-api.js"
```

Expected: PASS.

### Task 4: Run final verification

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\models\database.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\models\schemas.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\training-tab.js`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\package-tab.js`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\modals.js`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\mock-api.js`

- [ ] **Step 1: Run targeted backend tests**

Run:

```bash
python -m pytest "test/test_monitor_refresh.py" "test/test_package_manager.py" -q
```

- [ ] **Step 2: Run syntax verification**

Run:

```bash
python -m py_compile "app/models/database.py" "app/models/schemas.py" "app/core/monitor_manager.py" "app/core/package_manager.py"
node --check "static/js/training-tab.js"
node --check "static/js/package-tab.js"
node --check "static/js/modals.js"
node --check "static/js/mock-api.js"
```

- [ ] **Step 3: Run diff hygiene and diagnostics**

Run:

```bash
git diff --check -- "app/models/database.py" "app/models/schemas.py" "app/core/monitor_manager.py" "app/core/package_manager.py" "static/js/training-tab.js" "static/js/package-tab.js" "static/js/modals.js" "static/js/mock-api.js" "docs/superpowers/specs/2026-05-16-loss-metrics-display-design.md" "docs/superpowers/plans/2026-05-16-loss-metrics-display.md"
```

Then check editor diagnostics for all modified files and fix any
introduced issues.
