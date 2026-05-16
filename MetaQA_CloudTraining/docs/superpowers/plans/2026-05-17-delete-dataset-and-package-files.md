# Delete dataset and package files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dataset deletion remove only the dataset directory and make
package deletion remove only the package zip file, with clear failure behavior
when physical deletion fails.

**Architecture:** Keep deletion orchestration inside
`app/core/dataset_manager.py` and `app/core/package_manager.py`, and keep the
API layer thin. Add focused regression tests first, then implement the minimal
manager-layer changes so missing targets remain cleanup-tolerant while real
filesystem deletion failures stop the operation.

**Tech Stack:** Python, FastAPI, sqlite3, unittest, tempfile, `unittest.mock`

---

## File map

This plan changes a very small set of files and keeps responsibilities aligned
with the existing module boundaries.

- Modify: `app/core/dataset_manager.py`
  - Tighten dataset deletion behavior so it distinguishes between a missing
    dataset directory and a real directory deletion failure.
- Modify: `app/core/package_manager.py`
  - Tighten package deletion behavior so it distinguishes between a missing zip
    file and a real file deletion failure.
- Modify: `test/test_dataset_manager.py`
  - Add deletion-focused regression tests around dataset directory removal and
    non-goals like preserving unrelated run directories and package zips.
- Modify: `test/test_package_manager.py`
  - Add deletion-focused regression tests around package zip removal and
    non-goals like preserving run directories.

### Task 1: lock dataset deletion boundaries with tests

**Files:**
- Modify: `test/test_dataset_manager.py`
- Test: `test/test_dataset_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_delete_dataset_removes_dataset_directory_only(self):
    run_dir = os.path.join(self.tempdir.name, "runs", "task-1")
    pkg_zip = os.path.join(self.tempdir.name, "runs", "packages", "pkg-1.zip")
    os.makedirs(run_dir, exist_ok=True)
    os.makedirs(os.path.dirname(pkg_zip), exist_ok=True)
    with open(os.path.join(run_dir, "best.pt"), "wb") as f:
        f.write(b"best")
    with open(pkg_zip, "wb") as f:
        f.write(b"zip")

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        ok = dataset_manager.delete_dataset(self.ds_id)

    self.assertTrue(ok)
    self.assertFalse(os.path.exists(self.ds_dir))
    self.assertTrue(os.path.exists(run_dir))
    self.assertTrue(os.path.exists(pkg_zip))


def test_delete_dataset_keeps_working_when_dataset_directory_is_missing(self):
    shutil.rmtree(self.ds_dir, ignore_errors=True)

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        ok = dataset_manager.delete_dataset(self.ds_id)

    status = self.conn.execute(
        "SELECT status FROM datasets WHERE id=?",
        (self.ds_id,),
    ).fetchone()["status"]
    image_count = self.conn.execute(
        "SELECT COUNT(*) FROM images WHERE dataset_id=?",
        (self.ds_id,),
    ).fetchone()[0]

    self.assertTrue(ok)
    self.assertEqual("deleted", status)
    self.assertEqual(0, image_count)


def test_delete_dataset_fails_when_existing_directory_cannot_be_removed(self):
    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir), \
         patch.object(dataset_manager.shutil, "rmtree", side_effect=PermissionError("busy")):
        ok = dataset_manager.delete_dataset(self.ds_id)

    status = self.conn.execute(
        "SELECT status FROM datasets WHERE id=?",
        (self.ds_id,),
    ).fetchone()["status"]

    self.assertFalse(ok)
    self.assertEqual("active", status)
    self.assertTrue(os.path.isdir(self.ds_dir))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test/test_dataset_manager.py -q`

Expected: FAIL because `delete_dataset()` currently commits the database change
before trying to remove the dataset directory and does not treat directory
deletion errors as a failed operation.

- [ ] **Step 3: Write minimal test helpers**

```python
# test/test_dataset_manager.py
import shutil


def _fake_data_dir(self, key: str) -> str:
    if key == "datasets_path":
        return self.tempdir.name
    if key == "temp_path":
        path = os.path.join(self.tempdir.name, "_temp")
        os.makedirs(path, exist_ok=True)
        return path
    if key == "runs_path":
        path = os.path.join(self.tempdir.name, "runs")
        os.makedirs(path, exist_ok=True)
        return path
    raise AssertionError(f"unexpected data dir key: {key}")
```

- [ ] **Step 4: Run tests again to confirm the failures are behavior failures**

Run: `python -m pytest test/test_dataset_manager.py -q`

Expected: FAIL on the new delete tests, not with import errors or helper errors.

- [ ] **Step 5: Commit**

```bash
git add test/test_dataset_manager.py
git commit -m "test: add dataset deletion boundary coverage"
```

### Task 2: implement dataset deletion behavior

**Files:**
- Modify: `app/core/dataset_manager.py`
- Test: `test/test_dataset_manager.py`

- [ ] **Step 1: Write the minimal implementation**

```python
def delete_dataset(ds_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM datasets WHERE id=? AND status='active'",
        (ds_id,),
    ).fetchone()
    if not row:
        return False

    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    if os.path.isdir(ds_dir):
        try:
            shutil.rmtree(ds_dir)
        except OSError:
            conn.rollback()
            return False

    conn.execute(
        "UPDATE datasets SET status='deleted', updated_at=? WHERE id=?",
        (now_iso(), ds_id),
    )
    conn.execute("DELETE FROM images WHERE dataset_id=?", (ds_id,))
    conn.commit()
    return True
```

- [ ] **Step 2: Add a warning log for missing dataset directories**

```python
logger = get_logger()

if not os.path.isdir(ds_dir):
    logger.warning("删除数据集时目录不存在: %s", ds_dir)
else:
    try:
        shutil.rmtree(ds_dir)
    except OSError as exc:
        logger.error("删除数据集目录失败: %s", exc)
        conn.rollback()
        return False
```

- [ ] **Step 3: Run tests to verify dataset deletion passes**

Run: `python -m pytest test/test_dataset_manager.py -q`

Expected: PASS with all dataset tests green.

- [ ] **Step 4: Check diagnostics**

Run the editor diagnostics tool for:

- `app/core/dataset_manager.py`
- `test/test_dataset_manager.py`

Expected: no diagnostics.

- [ ] **Step 5: Commit**

```bash
git add app/core/dataset_manager.py test/test_dataset_manager.py
git commit -m "fix: enforce dataset file deletion boundaries"
```

### Task 3: lock package deletion boundaries with tests

**Files:**
- Modify: `test/test_package_manager.py`
- Test: `test/test_package_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_delete_package_removes_package_zip_only(self):
    run_dir = self._insert_task("task-delete-zip")
    pkg_zip = os.path.join(self.runs_path, "packages", "pkg-delete.zip")
    os.makedirs(os.path.dirname(pkg_zip), exist_ok=True)
    with open(pkg_zip, "wb") as f:
        f.write(b"zip")
    self.conn.execute(
        """
        INSERT INTO packages (
            id, name, dataset_name, version, task_id, size, map_val,
            training_time, file_path, status, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "pkg-delete",
            "测试数据集_v001.zip",
            "测试数据集",
            "v001",
            "task-delete-zip",
            3,
            0.95,
            "0h 02m",
            pkg_zip,
            "ready",
            "2026-05-17T00:00:00",
        ),
    )
    self.conn.commit()

    with patch.object(package_manager, "get_connection", return_value=self.conn):
        ok = package_manager.delete_package("pkg-delete")

    count = self.conn.execute(
        "SELECT COUNT(*) FROM packages WHERE id=?",
        ("pkg-delete",),
    ).fetchone()[0]
    self.assertTrue(ok)
    self.assertFalse(os.path.exists(pkg_zip))
    self.assertEqual(0, count)
    self.assertTrue(os.path.isdir(run_dir))


def test_delete_package_keeps_working_when_package_zip_is_missing(self):
    pkg_zip = os.path.join(self.runs_path, "packages", "pkg-missing.zip")
    self.conn.execute(
        """
        INSERT INTO packages (
            id, name, dataset_name, version, task_id, size, map_val,
            training_time, file_path, status, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "pkg-missing",
            "测试数据集_v001.zip",
            "测试数据集",
            "v001",
            "",
            0,
            0,
            "-",
            pkg_zip,
            "ready",
            "2026-05-17T00:00:00",
        ),
    )
    self.conn.commit()

    with patch.object(package_manager, "get_connection", return_value=self.conn):
        ok = package_manager.delete_package("pkg-missing")

    count = self.conn.execute(
        "SELECT COUNT(*) FROM packages WHERE id=?",
        ("pkg-missing",),
    ).fetchone()[0]
    self.assertTrue(ok)
    self.assertEqual(0, count)


def test_delete_package_fails_when_existing_zip_cannot_be_removed(self):
    pkg_zip = os.path.join(self.runs_path, "packages", "pkg-blocked.zip")
    os.makedirs(os.path.dirname(pkg_zip), exist_ok=True)
    with open(pkg_zip, "wb") as f:
        f.write(b"zip")
    self.conn.execute(
        """
        INSERT INTO packages (
            id, name, dataset_name, version, task_id, size, map_val,
            training_time, file_path, status, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            "pkg-blocked",
            "测试数据集_v001.zip",
            "测试数据集",
            "v001",
            "",
            3,
            0.95,
            "0h 02m",
            pkg_zip,
            "ready",
            "2026-05-17T00:00:00",
        ),
    )
    self.conn.commit()

    with patch.object(package_manager, "get_connection", return_value=self.conn), \
         patch.object(package_manager.os, "remove", side_effect=PermissionError("busy")):
        ok = package_manager.delete_package("pkg-blocked")

    count = self.conn.execute(
        "SELECT COUNT(*) FROM packages WHERE id=?",
        ("pkg-blocked",),
    ).fetchone()[0]
    self.assertFalse(ok)
    self.assertEqual(1, count)
    self.assertTrue(os.path.exists(pkg_zip))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test/test_package_manager.py -q`

Expected: FAIL because `delete_package()` currently deletes the database row
after a simple `os.remove()` branch and does not treat file deletion errors as
an explicit failed operation.

- [ ] **Step 3: Run the new tests only to isolate failures**

Run: `python -m pytest test/test_package_manager.py -k "delete_package" -q`

Expected: FAIL on the new package delete tests only.

- [ ] **Step 4: Commit**

```bash
git add test/test_package_manager.py
git commit -m "test: add package deletion boundary coverage"
```

### Task 4: implement package deletion behavior

**Files:**
- Modify: `app/core/package_manager.py`
- Test: `test/test_package_manager.py`

- [ ] **Step 1: Write the minimal implementation**

```python
def delete_package(pkg_id: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT file_path FROM packages WHERE id=?",
        (pkg_id,),
    ).fetchone()
    if not row:
        return False

    file_path = row["file_path"]
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            return False

    conn.execute("DELETE FROM packages WHERE id=?", (pkg_id,))
    conn.commit()
    return True
```

- [ ] **Step 2: Add logging for missing files versus failed deletion**

```python
logger = get_logger()

if file_path and not os.path.exists(file_path):
    logger.warning("删除产物时文件不存在: %s", file_path)
elif file_path:
    try:
        os.remove(file_path)
    except OSError as exc:
        logger.error("删除产物文件失败: %s", exc)
        return False
```

- [ ] **Step 3: Run package tests to verify they pass**

Run: `python -m pytest test/test_package_manager.py -q`

Expected: PASS with the new delete tests green and existing package tests still
passing.

- [ ] **Step 4: Check diagnostics**

Run the editor diagnostics tool for:

- `app/core/package_manager.py`
- `test/test_package_manager.py`

Expected: no diagnostics.

- [ ] **Step 5: Commit**

```bash
git add app/core/package_manager.py test/test_package_manager.py
git commit -m "fix: enforce package file deletion boundaries"
```

### Task 5: final verification

**Files:**
- Modify: none
- Test: `test/test_dataset_manager.py`
- Test: `test/test_package_manager.py`

- [ ] **Step 1: Run focused regression tests together**

Run: `python -m pytest test/test_dataset_manager.py test/test_package_manager.py -q`

Expected: PASS with all deletion-related and package conversion tests green.

- [ ] **Step 2: Manually inspect final behavior assumptions**

Confirm all of the following in the code:

- `delete_dataset()` deletes only `datasets/<ds_id>`
- `delete_dataset()` does not touch `run_dir`
- `delete_package()` deletes only `packages.file_path`
- `delete_package()` does not touch training artifacts
- missing targets are tolerated
- real filesystem deletion failures return `False`

- [ ] **Step 3: Commit**

```bash
git add app/core/dataset_manager.py app/core/package_manager.py test/test_dataset_manager.py test/test_package_manager.py
git commit -m "fix: align delete actions with file cleanup boundaries"
```

## Self-review

Spec coverage check:

- Dataset deletion removes its own directory: covered by Tasks 1-2.
- Dataset deletion preserves run directories and package zips: covered by Task 1.
- Package deletion removes its zip file only: covered by Tasks 3-4.
- Missing targets still allow record cleanup: covered by Tasks 1 and 3.
- Real filesystem deletion failures stop the delete action: covered by Tasks 2
  and 4.

Placeholder scan:

- No `TODO`, `TBD`, or unresolved “appropriate handling” placeholders remain.
- Every task includes exact file paths, concrete tests, concrete commands, and
  minimal implementation snippets.

Type consistency:

- `delete_dataset(ds_id: str) -> bool` stays unchanged across tasks.
- `delete_package(pkg_id: str) -> bool` stays unchanged across tasks.
- Test names and expected behaviors line up with the spec’s missing-target and
  hard-failure split.
