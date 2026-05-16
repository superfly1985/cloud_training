# Upload abort and dashboard env implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make upload cancellation stop the current chunk immediately and fix the dashboard environment summary fields that show `-`.

**Architecture:** Keep the existing upload flow and only extend the front-end `XMLHttpRequest` wrapper so each modal can abort the active request safely. Trace the dashboard issue from UI bindings back to `/api/v1/system/status`, then patch the smallest layer that drops or misnames environment fields.

**Tech Stack:** Vue 3, vanilla JavaScript, FastAPI, Python

---

### Task 1: Stop the active upload chunk immediately

This task updates the front-end upload wrapper and both upload modals so
canceling an upload aborts the active `XMLHttpRequest` right away.

**Files:**
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\api.js`
- Modify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\modals.js`

- [ ] Add `abort()` support to `API.uploadChunk()` while keeping the current progress callback contract.
- [ ] Store the active request object in both upload modals and call `abort()` inside `cancelUpload()`.
- [ ] Clear the active request reference on success, failure, cancellation, and component unmount.

### Task 2: Verify upload cancellation changes

This task performs the minimum safe verification for the front-end-only
changes.

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\api.js`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\modals.js`

- [ ] Run editor diagnostics for both modified JavaScript files and confirm there are no errors.
- [ ] Run `node --check "static/js/api.js"` and `node --check "static/js/modals.js"` from the project root.

### Task 3: Trace dashboard environment placeholders

This task identifies why environment information on the dashboard renders as
`-` instead of meaningful values.

**Files:**
- Read: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\dashboard.js`
- Read: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\app.js`
- Read: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\api\system.py`
- Read: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\system_manager.py`

- [ ] Inspect the dashboard field bindings and record which keys render as `-`.
- [ ] Compare those keys with the payload returned by `/api/v1/system/status`.
- [ ] Patch the smallest layer that breaks the contract.

### Task 4: Verify the dashboard fix

This task confirms the repaired contract is internally consistent.

**Files:**
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\static\js\dashboard.js`
- Verify: `d:\01.AwesomeProject\03.云端训练\MetaQA_CloudTraining\app\core\system_manager.py`

- [ ] Run diagnostics for the edited files.
- [ ] If Python files change, run a focused syntax/import-safe check or targeted tests for the touched system status path.
