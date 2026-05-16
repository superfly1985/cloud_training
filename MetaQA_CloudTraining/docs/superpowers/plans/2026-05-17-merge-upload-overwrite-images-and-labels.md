# Merge upload overwrite images and labels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make merge uploads overwrite same-name images and labels
independently, while keeping new dataset import behavior unchanged.

**Architecture:** Keep `import_zip()` as the create/import path and move the new
overwrite behavior into `merge_dataset()` only. Implement merge handling as two
independent passes, one for images and one for labels, so label updates no
longer depend on whether an image was imported in the same upload. Recompute
dataset stats from disk after merge so `annotated_count` and class summaries
match the final files on disk.

**Tech Stack:** Python, sqlite3, zipfile, tempfile, unittest,
`unittest.mock`

---

## File map

This change touches one production module and one focused test module.

- Modify: `app/core/dataset_manager.py`
  - Keep create/import behavior stable.
  - Add merge-only overwrite logic for same-name images and same-name labels.
  - Return merge-oriented counters instead of “skipped duplicate” semantics.
- Modify: `test/test_dataset_manager.py`
  - Lock merge overwrite behavior for images and labels.
  - Lock the non-goals: no rename copies, no duplicate DB rows, create/import
    stays unchanged.

### Task 1: add failing tests for merge overwrite semantics

**Files:**
- Modify: `test/test_dataset_manager.py`
- Test: `test/test_dataset_manager.py`

- [ ] **Step 1: Add helpers for creating merge ZIP payloads**

```python
def _write_merge_zip(self, zip_name: str, entries: dict[str, bytes | str]) -> str:
    zip_path = os.path.join(self.tempdir.name, zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return zip_path
```

- [ ] **Step 2: Write the failing tests**

```python
def test_merge_dataset_overwrites_same_name_image(self):
    zip_path = self._write_merge_zip(
        "merge-image.zip",
        {"images/dup.jpg": b"new-image"},
    )

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        result = dataset_manager.merge_dataset(self.ds_id, zip_path)

    with open(os.path.join(self.images_dir, "dup.jpg"), "rb") as f:
        image_bytes = f.read()
    count = self.conn.execute(
        "SELECT COUNT(*) FROM images WHERE dataset_id=? AND filename=?",
        (self.ds_id, "dup.jpg"),
    ).fetchone()[0]

    self.assertEqual(b"new-image", image_bytes)
    self.assertEqual(1, count)
    self.assertEqual(1, result["images_overwritten"])


def test_merge_dataset_overwrites_same_name_label_independently(self):
    zip_path = self._write_merge_zip(
        "merge-label.zip",
        {"labels/dup.txt": "0 0.1 0.2 0.3 0.4\n"},
    )

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        result = dataset_manager.merge_dataset(self.ds_id, zip_path)

    with open(os.path.join(self.labels_dir, "dup.txt"), "r", encoding="utf-8") as f:
        label_text = f.read()

    self.assertEqual("0 0.1 0.2 0.3 0.4\n", label_text)
    self.assertEqual(1, result["labels_overwritten"])


def test_merge_dataset_only_image_keeps_existing_label(self):
    zip_path = self._write_merge_zip(
        "merge-image-only.zip",
        {"images/dup.jpg": b"image-only-update"},
    )

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        dataset_manager.merge_dataset(self.ds_id, zip_path)

    with open(os.path.join(self.images_dir, "dup.jpg"), "rb") as f:
        image_bytes = f.read()
    with open(os.path.join(self.labels_dir, "dup.txt"), "r", encoding="utf-8") as f:
        label_text = f.read()

    self.assertEqual(b"image-only-update", image_bytes)
    self.assertEqual("0 0.5 0.5 0.2 0.2\n", label_text)


def test_merge_dataset_only_label_keeps_existing_image(self):
    zip_path = self._write_merge_zip(
        "merge-label-only.zip",
        {"labels/dup.txt": "0 0.6 0.6 0.1 0.1\n"},
    )

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        dataset_manager.merge_dataset(self.ds_id, zip_path)

    with open(os.path.join(self.images_dir, "dup.jpg"), "rb") as f:
        image_bytes = f.read()
    with open(os.path.join(self.labels_dir, "dup.txt"), "r", encoding="utf-8") as f:
        label_text = f.read()

    self.assertEqual(b"old", image_bytes)
    self.assertEqual("0 0.6 0.6 0.1 0.1\n", label_text)


def test_merge_dataset_does_not_create_duplicate_db_rows_for_same_name_image(self):
    zip_path = self._write_merge_zip(
        "merge-no-dup-row.zip",
        {
            "images/dup.jpg": b"replace-image",
            "labels/dup.txt": "0 0.2 0.2 0.2 0.2\n",
        },
    )

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        dataset_manager.merge_dataset(self.ds_id, zip_path)

    rows = self.conn.execute(
        "SELECT id, filename FROM images WHERE dataset_id=? AND filename=?",
        (self.ds_id, "dup.jpg"),
    ).fetchall()

    self.assertEqual(1, len(rows))


def test_import_zip_create_path_still_renames_same_name_image(self):
    zip_path = self._write_merge_zip(
        "create-import.zip",
        {
            "images/dup.jpg": b"new-create-image",
            "labels/dup.txt": "0 0.3 0.3 0.3 0.3\n",
        },
    )

    with patch.object(dataset_manager, "get_connection", return_value=self.conn), \
         patch.object(dataset_manager, "get_data_dir", side_effect=self._fake_data_dir):
        result = dataset_manager.import_zip(self.ds_id, zip_path)

    filenames = [
        row["filename"]
        for row in self.conn.execute(
            "SELECT filename FROM images WHERE dataset_id=? ORDER BY filename",
            (self.ds_id,),
        ).fetchall()
    ]

    self.assertEqual(1, result["imported"])
    self.assertEqual(["dup.jpg", filenames[1]], filenames)
    self.assertTrue(filenames[1].startswith("dup_"))
    self.assertTrue(filenames[1].endswith(".jpg"))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest test/test_dataset_manager.py -k "merge_dataset_overwrites or only_image or only_label or no_duplicate_db_rows or create_path_still_renames" -q`

Expected: FAIL because `merge_dataset()` currently delegates to
`import_zip(..., skip_existing=True)`, which skips same-name images and ties
label handling to image import.

- [ ] **Step 4: Verify failure reason is correct**

Run: `python -m pytest test/test_dataset_manager.py -k "merge_dataset_overwrites_same_name_label_independently" -q`

Expected: FAIL because `dup.txt` remains unchanged when the ZIP contains only a
label file.

- [ ] **Step 5: Commit**

```bash
git add test/test_dataset_manager.py
git commit -m "test: add merge overwrite coverage"
```

### Task 2: implement merge-only overwrite behavior

**Files:**
- Modify: `app/core/dataset_manager.py`
- Test: `test/test_dataset_manager.py`

- [ ] **Step 1: Replace merge delegation with a dedicated merge implementation**

```python
def merge_dataset(target_id: str, zip_path: str) -> dict:
    logger = get_logger()
    conn = get_connection()
    ds = get_dataset(target_id)
    if not ds:
        raise ValueError(f"数据集不存在: {target_id}")

    ds_dir = os.path.join(get_data_dir("datasets_path"), target_id)
    img_dir = os.path.join(ds_dir, "images")
    lbl_dir = os.path.join(ds_dir, "labels")
    ensure_dir(img_dir)
    ensure_dir(lbl_dir)

    temp_dir = os.path.join(get_data_dir("temp_path"), f"merge_{target_id}")
    ensure_dir(temp_dir)
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError("无效的 ZIP 文件")

    result = _merge_extracted_dataset_into_target(target_id, temp_dir, img_dir, lbl_dir, conn)
    shutil.rmtree(temp_dir, ignore_errors=True)
    _refresh_dataset_stats(target_id)
    conn.commit()
    logger.info(
        "数据集 %s 合并完成: 图片新增 %s, 图片覆盖 %s, 标签新增 %s, 标签覆盖 %s",
        target_id,
        result["images_imported"],
        result["images_overwritten"],
        result["labels_imported"],
        result["labels_overwritten"],
    )
    return result
```

- [ ] **Step 2: Add a focused helper that handles images and labels independently**

```python
def _merge_extracted_dataset_into_target(ds_id: str, temp_dir: str, img_dir: str, lbl_dir: str, conn) -> dict:
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    result = {
        "imported": 0,
        "images_imported": 0,
        "images_overwritten": 0,
        "labels_imported": 0,
        "labels_overwritten": 0,
    }

    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in img_exts:
                continue
            src = os.path.join(root, f)
            dst = os.path.join(img_dir, f)
            existed = os.path.exists(dst)
            if existed:
                os.remove(dst)
                result["images_overwritten"] += 1
            else:
                result["images_imported"] += 1
            shutil.move(src, dst)
            if not conn.execute(
                "SELECT 1 FROM images WHERE dataset_id=? AND filename=?",
                (ds_id, f),
            ).fetchone():
                conn.execute(
                    "INSERT INTO images (id, dataset_id, filename, size, annotated, split_type, created_at) VALUES (?,?,?,?,?,?,?)",
                    (f"{ds_id}-img-{gen_id()}", ds_id, f, os.path.getsize(dst), 0, "", now_iso()),
                )
                result["imported"] += 1

    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            if not f.endswith(".txt"):
                continue
            src = os.path.join(root, f)
            dst = os.path.join(lbl_dir, f)
            if os.path.exists(dst):
                os.remove(dst)
                result["labels_overwritten"] += 1
            else:
                result["labels_imported"] += 1
            shutil.move(src, dst)

    return result
```

- [ ] **Step 3: Keep create/import behavior unchanged**

```python
def import_zip(ds_id: str, zip_path: str, skip_existing: bool = False) -> dict:
    ...
    if os.path.exists(dst):
        if skip_existing:
            skipped += 1
            continue
        base, e = os.path.splitext(f)
        dst = os.path.join(img_dir, f"{base}_{gen_id()}{e}")
    ...
```

Expected outcome: only `merge_dataset()` changes behavior. `import_zip()`
remains the create/import path with its existing rename-on-conflict semantics.

- [ ] **Step 4: Run tests to verify merge behavior passes**

Run: `python -m pytest test/test_dataset_manager.py -k "merge_dataset_overwrites or only_image or only_label or no_duplicate_db_rows or create_path_still_renames" -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/core/dataset_manager.py test/test_dataset_manager.py
git commit -m "fix: overwrite same-name files during merge upload"
```

### Task 3: verify full dataset manager coverage

**Files:**
- Modify: none
- Test: `test/test_dataset_manager.py`

- [ ] **Step 1: Run the full dataset manager test file**

Run: `python -m pytest test/test_dataset_manager.py -q`

Expected: PASS, including the existing merge skip test after it is updated or
replaced by the new overwrite semantics.

- [ ] **Step 2: Check diagnostics**

Run the editor diagnostics tool for:

- `app/core/dataset_manager.py`
- `test/test_dataset_manager.py`

Expected: no diagnostics.

- [ ] **Step 3: Manually inspect final behavior boundaries**

Confirm all of the following in the code:

- `merge_dataset()` no longer calls `import_zip(..., skip_existing=True)`
- same-name images are overwritten in merge mode
- same-name labels are overwritten in merge mode
- labels can be merged without accompanying images
- create/import path still renames on name conflict
- merge path does not insert duplicate `images` rows for the same filename

- [ ] **Step 4: Commit**

```bash
git add app/core/dataset_manager.py test/test_dataset_manager.py
git commit -m "test: verify merge overwrite boundaries"
```

## Self-review

Spec coverage:

- Merge-only behavior change: covered by Tasks 1-2.
- Same-name image overwrite: covered by Task 1.
- Same-name label overwrite: covered by Task 1.
- Image/label independence: covered by Task 1.
- No hash comparison: preserved by Task 2.
- Create/import path unchanged: covered by Tasks 1-2.

Placeholder scan:

- No `TODO`, `TBD`, or vague “handle edge cases” placeholders remain.
- Each task contains exact file paths, exact commands, and concrete code
  snippets.

Type consistency:

- `merge_dataset(target_id: str, zip_path: str) -> dict` stays consistent.
- `import_zip(ds_id: str, zip_path: str, skip_existing: bool = False) -> dict`
  remains intact.
- Result keys are consistent across tests and implementation:
  `images_imported`, `images_overwritten`, `labels_imported`,
  `labels_overwritten`.
