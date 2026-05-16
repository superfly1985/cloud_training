# Deploy archive upload implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-file SFTP deployment with local archive upload plus remote extract while keeping full-overwrite behavior and existing deploy step contracts.

**Architecture:** Keep `DeployManager.upload_files()` as the public upload entry so the GUI and deploy pipeline stay unchanged. Move the heavy lifting into small helper methods that collect files, build a temporary zip, upload that zip once, extract it on the server, and clean temporary artifacts on both sides.

**Tech Stack:** Python, Paramiko SFTP, remote Linux shell utilities, unittest

---

### Task 1: Lock the new upload contract with tests

This task captures the behavior change before implementation so the upload
refactor stays focused.

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] Add a test that `upload_files()` builds one archive, uploads it once, runs remote cleanup and unzip commands, and reports success counts based on collected local files.
- [ ] Add a test that failed remote extraction returns `False` and writes a readable failure log.
- [ ] Keep the existing `_step_upload()` contract unchanged so downstream deploy UI text does not need changes.

### Task 2: Implement archive-based upload helpers

This task changes only the deploy tool internals and keeps `main` orchestration
logic untouched.

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`

- [ ] Add focused helpers for building the temporary archive, choosing remote temp paths, extracting on the server, and cleaning temp files.
- [ ] Update `upload_files()` to call those helpers instead of iterating `sftp.put()` per file.
- [ ] Preserve existing exclusion rules, cancellation checks, progress callback compatibility, and summary counters.

### Task 3: Verify the deploy tool change

This task confirms the refactor is safe and keeps the edited Python files clean.

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\deploy_tool\deploy_manager.py`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\test\test_deploy_manager.py`

- [ ] Run `python -m pytest test/test_deploy_manager.py -q` from `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining`.
- [ ] Run diagnostics on the edited Python files and fix any introduced issues.
