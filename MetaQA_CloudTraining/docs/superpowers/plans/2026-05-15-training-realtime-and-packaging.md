# Training realtime and packaging implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make training progress, logs, curves, and GPU usage refresh
in near real time, and automatically generate a package when training
finishes, with clear conversion status when ONNX or TFLite export fails.

**Architecture:** Keep the existing FastAPI plus static Vue structure and
add polling on the frontend. Concentrate training state convergence in
the backend refresh path so a task can move from `pending` or `running`
to `completed` or `failed` even if the process watcher misses it. Trigger
automatic packaging only once per task and surface conversion status in
both package metadata and UI.

**Tech Stack:** FastAPI, SQLite, Python subprocess management, Vue 3 CDN,
plain JavaScript polling, unittest

---

### Task 1: Add failing backend tests for task convergence and auto packaging

**Files:**
- Create: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_monitor_refresh.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\monitor_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_refresh_marks_task_completed_and_triggers_package_creation():
    result = refresh_task_metrics("task-1")
    assert result["status"] == "completed"
    assert package_calls == ["task-1"]


def test_refresh_marks_task_failed_when_process_exits_without_outputs():
    result = refresh_task_metrics("task-2")
    assert result["status"] == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s test -p "test_monitor_refresh.py"`
Expected: FAIL because `refresh_task_metrics()` does not currently return
status convergence or invoke package creation.

- [ ] **Step 3: Write minimal implementation**

```python
def refresh_task_metrics(task_id: str) -> dict | None:
    # Parse CSV if present.
    # Detect process state and completion markers from log/output files.
    # Update DB status to running/completed/failed.
    # Call create_package(task_id) once when task first becomes completed.
    return {
        "current_epoch": current_epoch,
        "box_loss": box_loss,
        "cls_loss": cls_loss,
        "map50": map50,
        "map50_95": map50_95,
        "status": status,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s test -p "test_monitor_refresh.py"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add test/test_monitor_refresh.py app/core/monitor_manager.py
git commit -m "fix: converge training status during metric refresh"
```

### Task 2: Extend package metadata and conversion status handling

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Test: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_package_manager.py`

- [ ] **Step 1: Write the failing test**

```python
def test_create_package_marks_partial_when_some_conversion_outputs_missing():
    pkg = create_package("task-1")
    assert pkg["conversion_status"] == "partial"
    assert "best.pt" in [item["name"] for item in pkg["files"]]


def test_create_package_marks_not_converted_when_only_base_files_exist():
    pkg = create_package("task-2")
    assert pkg["conversion_status"] == "not_converted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest discover -s test -p "test_package_manager.py"`
Expected: FAIL because package metadata currently does not track
conversion status and returned package payload has empty `files`.

- [ ] **Step 3: Write minimal implementation**

```python
info = {
    "task_id": task_id,
    "dataset_name": task["dataset_name"],
    "dataset_version": task["version"],
    "model_size": task["model_size"],
    "epochs": task["epochs"],
    "imgsz": task["input_size"],
    "batch": task["batch_size"],
    "best_map": task["map50"],
    "training_time": training_time,
    "conversion_status": conversion_status,
    "conversion_items": conversion_items,
    "conversion_errors": conversion_errors,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest discover -s test -p "test_package_manager.py"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/package_manager.py test/test_package_manager.py
git commit -m "feat: track package conversion status"
```

### Task 3: Make training list poll and refresh active tasks

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\training-tab.js`

- [ ] **Step 1: Add polling state**

```javascript
data: function () {
  return {
    tasks: [],
    loading: true,
    searchQuery: "",
    statusFilter: "",
    page: 1,
    pageSize: 15,
    jumpPage: 1,
    _pollTimer: null,
  };
}
```

- [ ] **Step 2: Implement active task refresh**

```javascript
refreshActiveTasks: function () {
  var self = this;
  var active = self.tasks.filter(function (task) {
    return task.status === "pending" || task.status === "running";
  });
  return Promise.all(active.map(function (task) {
    return API.refreshMetrics(task.id).then(function (res) {
      if (res && res.code === 0) {
        Object.assign(task, res.data);
      }
    }).catch(function () {});
  }));
}
```

- [ ] **Step 3: Start polling in mounted**

```javascript
mounted: function () {
  var self = this;
  self.load();
  self._pollTimer = setInterval(function () {
    self.load();
  }, 3000);
}
```

- [ ] **Step 4: Stop polling on unmount**

```javascript
beforeUnmount: function () {
  if (this._pollTimer) clearInterval(this._pollTimer);
}
```

- [ ] **Step 5: Commit**

```bash
git add static/js/training-tab.js
git commit -m "feat: poll training task list"
```

### Task 4: Make training log and curve dialogs refresh live

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\modals.js`

- [ ] **Step 1: Add timer lifecycle to log modal**

```javascript
data: function () {
  return {
    logLines: [],
    loading: true,
    _pollTimer: null,
  };
}
```

- [ ] **Step 2: Poll logs every 2 seconds**

```javascript
mounted: function () {
  var self = this;
  self.loadLog();
  self._pollTimer = setInterval(function () {
    self.loadLog();
  }, 2000);
}
```

- [ ] **Step 3: Poll curves every 3 seconds**

```javascript
mounted: function () {
  var self = this;
  self.loadChart();
  self._pollTimer = setInterval(function () {
    self.loadChart();
  }, 3000);
}
```

- [ ] **Step 4: Clean up timers**

```javascript
beforeUnmount: function () {
  if (this._pollTimer) clearInterval(this._pollTimer);
  document.removeEventListener("keydown", this._keyHandler);
}
```

- [ ] **Step 5: Commit**

```bash
git add static/js/modals.js
git commit -m "feat: auto refresh training log and curve modals"
```

### Task 5: Refresh GPU status more frequently

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\app.js`

- [ ] **Step 1: Replace the current 30 second polling interval**

```javascript
mounted: function () {
  this.handleHashChange();
  window.addEventListener("hashchange", this.handleHashChange);
  this.loadSystemStatus();
  var self = this;
  this._systemTimer = setInterval(function () {
    self.loadSystemStatus();
  }, 3000);
}
```

- [ ] **Step 2: Clear the system timer**

```javascript
beforeUnmount: function () {
  if (this._systemTimer) clearInterval(this._systemTimer);
  window.removeEventListener("hashchange", this.handleHashChange);
}
```

- [ ] **Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat: refresh system gpu status more often"
```

### Task 6: Surface conversion state in package APIs and package UI

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\package_manager.py`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\package-tab.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\modals.js`

- [ ] **Step 1: Return conversion metadata from package rows**

```python
return {
    "id": r["id"],
    "name": r["name"],
    "dataset_name": r["dataset_name"],
    "version": r["version"],
    "size": r["size"],
    "map_val": r["map_val"],
    "training_time": r["training_time"],
    "created_at": r["created_at"],
    "conversion_status": conversion_status,
    "files": files_meta,
}
```

- [ ] **Step 2: Add UI badge mapping**

```javascript
conversionStatusText: function (status) {
  var map = {
    complete: "已转换",
    partial: "部分转换",
    not_converted: "未转换",
  };
  return map[status] || "未知";
}
```

- [ ] **Step 3: Display the badge in package list and detail modal**

```javascript
<span class="badge" :class="conversionBadgeClass(pkg.conversion_status)">
  {{ conversionStatusText(pkg.conversion_status) }}
</span>
```

- [ ] **Step 4: Commit**

```bash
git add app/core/package_manager.py static/js/package-tab.js static/js/modals.js
git commit -m "feat: show conversion state in package management"
```

### Task 7: Run focused verification and clean temporary debugging scripts

**Files:**
- Delete: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\remote_server_inspect.py`
- Delete: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\remote_hotfix_apply.py`
- Delete: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\remote_start_server.py`

- [ ] **Step 1: Run backend tests**

Run:
`python -m unittest discover -s test -p "test_training_start.py"`

Expected: PASS

- [ ] **Step 2: Run new monitor and package tests**

Run:
`python -m unittest discover -s test -p "test_monitor_refresh.py"`

Expected: PASS

Run:
`python -m unittest discover -s test -p "test_package_manager.py"`

Expected: PASS

- [ ] **Step 3: Run diagnostics on edited frontend and backend files**

Run VS Code diagnostics for:
- `app/core/monitor_manager.py`
- `app/core/package_manager.py`
- `app/core/training_manager.py`
- `static/js/app.js`
- `static/js/training-tab.js`
- `static/js/modals.js`
- `static/js/package-tab.js`

Expected: no new diagnostics

- [ ] **Step 4: Remove one-off remote maintenance scripts**

```bash
git rm test/remote_server_inspect.py test/remote_hotfix_apply.py test/remote_start_server.py
```

- [ ] **Step 5: Commit**

```bash
git add test app static
git commit -m "feat: add realtime training updates and auto packaging"
```
