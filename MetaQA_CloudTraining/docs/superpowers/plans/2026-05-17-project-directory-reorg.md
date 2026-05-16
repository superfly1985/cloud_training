# Project directory reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the repository so the Web app stays the primary product, the legacy desktop app moves to `legacy/local_desktop/` and remains runnable/packageable, and obvious one-off junk is removed from the root.

**Architecture:** Keep `MetaQA_CloudTraining/` in place as the Web mainline. Move the old desktop app as a self-contained legacy product, then shrink `test/` and historical backups with explicit deletion rules, and finally update root-facing docs so the new structure is obvious.

**Tech Stack:** Python project structure, PyInstaller spec files, Markdown docs, file moves/deletions

---

## File map

- Modify: `README.md`
- Modify: `MetaQA_CloudTraining/doc/webUI方案集/01-目录结构.md`
- Move/Modify: `main.py`
- Move/Modify: `src/`
- Move/Modify: `cloud_training.spec`
- Move/Modify: `cloud_training_config.json`
- Move/Modify: `requirements.txt` and any desktop-only support files if still required by the legacy desktop app
- Create: `legacy/local_desktop/`
- Delete or move selected files from:
  - `test/`
  - `backup/`
  - root-level stale artifacts

### Task 1: inventory the legacy desktop runtime contract

**Files:**
- Read/Modify: `main.py`
- Read/Modify: `cloud_training.spec`
- Read/Modify: `cloud_training_config.json`
- Read/Modify: `setup_env.ps1`
- Read/Modify: `README.md`

- [ ] **Step 1: Read the desktop entrypoint and spec for root-relative assumptions**

Check:

- imports of `src`
- resource/config relative paths
- PyInstaller `pathex`, `datas`, and script entry

- [ ] **Step 2: List every file the desktop app still needs after migration**

Produce a concrete keep list such as:

- `main.py`
- `src/**`
- `cloud_training.spec`
- `cloud_training_config.json`
- desktop-only `requirements.txt` if used
- any runtime assets referenced by relative path

- [ ] **Step 3: Identify path fixes before any move**

Examples to confirm or adjust:

```python
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "cloud_training_config.json")
```

And in the spec:

```python
a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('.')],
)
```

Update these to be stable from `legacy/local_desktop/` before or during the move.

### Task 2: migrate the legacy desktop app into `legacy/local_desktop`

**Files:**
- Create: `legacy/local_desktop/`
- Move: `main.py`
- Move: `src/`
- Move: `cloud_training.spec`
- Move: `cloud_training_config.json`
- Move/Modify: desktop support files required by Task 1

- [ ] **Step 1: Create the legacy desktop target structure**

Target:

```text
legacy/
└─ local_desktop/
   ├─ main.py
   ├─ src/
   ├─ cloud_training.spec
   ├─ cloud_training_config.json
   └─ ...
```

- [ ] **Step 2: Move the desktop files as a single coherent unit**

Do not split the move across multiple partial locations. The desktop app must be self-contained under `legacy/local_desktop/`.

- [ ] **Step 3: Repair imports and relative paths if needed**

Keep the desktop runtime contract working from the new location. If a path depends on repo root, convert it to a file-relative path anchored on `legacy/local_desktop/`.

- [ ] **Step 4: Verify desktop startup from the new location**

Use the exact command that matches the desktop runtime:

```bash
python legacy/local_desktop/main.py
```

Expected:

- process starts without immediate import/path errors

- [ ] **Step 5: Verify desktop packaging from the new location**

Use the existing packaging rule, but from the relocated spec:

```bash
pyinstaller legacy/local_desktop/cloud_training.spec
```

Expected:

- spec resolves entrypoint and resources
- no missing-path error caused by the move

### Task 3: clean root-level junk and overgrown test artifacts

**Files:**
- Delete/Move: `test/**`
- Delete/Move: `backup/**`
- Delete: root stale artifacts confirmed unused

- [ ] **Step 1: Classify files in `test/` into keep, move, delete**

Use these buckets:

- keep: still-used reusable probes/tests
- move: useful but misplaced manual diagnostics
- delete: one-off outputs, cache, repeated models, stale logs

- [ ] **Step 2: Delete obvious garbage first**

Delete items such as:

- `__pycache__/`
- repeated `.tflite` compare outputs
- temporary image output folders
- stale `.json` probe result files with no continuing workflow value
- old log files with no diagnostic reuse

- [ ] **Step 3: Collapse `backup/` to only genuinely useful references**

Rules:

- remove duplicate old-code copies once `legacy/local_desktop/` exists
- remove expired reports, screenshots, exported diagrams, and temporary planning docs that no longer serve as unique references

- [ ] **Step 4: Keep a minimal useful test/probe structure**

Example target:

```text
test/
├─ probes/
├─ manual/
└─ samples/
```

Only create these folders if surviving files justify them.

### Task 4: update repository-facing docs and navigation

**Files:**
- Modify: `README.md`
- Modify: `MetaQA_CloudTraining/doc/webUI方案集/01-目录结构.md`

- [ ] **Step 1: Rewrite the root README opening**

It must clearly say:

- the Web app is the current main product
- the Web app lives in `MetaQA_CloudTraining/`
- the legacy desktop app lives in `legacy/local_desktop/`
- the legacy desktop app remains runnable and packageable

- [ ] **Step 2: Add a concise directory map to README**

Use a short structure like:

```text
MetaQA_CloudTraining/   当前 Web 主产品
legacy/local_desktop/  旧本地版
test/                  保留的测试与探针
```

- [ ] **Step 3: Update `01-目录结构.md` to match the new layout**

Remove outdated root-level structure references and document the split between Web and desktop tracks.

### Task 5: final verification

**Files:**
- Modify: none

- [ ] **Step 1: Run diagnostics on edited docs and any touched Python/spec files**

- [ ] **Step 2: Re-run desktop startup verification**

```bash
python legacy/local_desktop/main.py
```

Expected:

- no immediate import/path crash

- [ ] **Step 3: Re-run packaging verification**

```bash
pyinstaller legacy/local_desktop/cloud_training.spec
```

Expected:

- spec resolves successfully from the new location

- [ ] **Step 4: Sanity-check the root**

Confirm:

- root no longer contains desktop entry clutter
- `MetaQA_CloudTraining/` remains intact
- `test/` no longer contains obvious bulky garbage
- README matches the new structure
