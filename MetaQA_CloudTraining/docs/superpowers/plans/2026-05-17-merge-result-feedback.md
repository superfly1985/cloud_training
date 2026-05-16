# Merge result feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show users a clear success summary and a persistent in-modal result area after a merge upload completes.

**Architecture:** Keep all logic inside `static/js/modals.js` and only enhance the `merge-dataset-modal` component. Read existing merge result fields from the upload API response, normalize missing values to `0`, build a summary string, and render both an immediate success alert and an in-modal result block.

**Tech Stack:** Vue component in plain JavaScript, existing upload API helpers

---

## File map

- Modify: `static/js/modals.js`
  - Add merge result state, summary generation, and result rendering to `merge-dataset-modal`.
- Test: manual verification in browser
  - No existing JS unit test harness covers this component, so verification stays focused on code diagnostics and manual flow.

### Task 1: add merge result state and UI

**Files:**
- Modify: `static/js/modals.js`

- [ ] **Step 1: Add merge result state**

```js
mergeResult: null,
mergeSummaryText: "",
```

- [ ] **Step 2: Add helper methods**

```js
normalizeMergeResult: function (data) {
  data = data || {};
  return {
    imagesImported: Number(data.images_imported || 0),
    imagesOverwritten: Number(data.images_overwritten || 0),
    labelsImported: Number(data.labels_imported || 0),
    labelsOverwritten: Number(data.labels_overwritten || 0),
  };
},
buildMergeSummary: function (result) {
  return "合并完成：图片新增 " + result.imagesImported +
    "，图片覆盖 " + result.imagesOverwritten +
    "，标签新增 " + result.labelsImported +
    "，标签覆盖 " + result.labelsOverwritten;
},
resetMergeResult: function () {
  this.mergeResult = null;
  this.mergeSummaryText = "";
},
```

- [ ] **Step 3: Render the in-modal result block**

```js
<div v-if="mergeResult && !uploading" class="upload-result-panel">
  <div class="form-hint" style="margin-top: 12px;">本次合并结果</div>
  <div class="upload-stats">
    <span>图片新增 {{ mergeResult.imagesImported }}</span>
    <span>图片覆盖 {{ mergeResult.imagesOverwritten }}</span>
  </div>
  <div class="upload-stats">
    <span>标签新增 {{ mergeResult.labelsImported }}</span>
    <span>标签覆盖 {{ mergeResult.labelsOverwritten }}</span>
  </div>
</div>
```

### Task 2: wire merge success handling

**Files:**
- Modify: `static/js/modals.js`

- [ ] **Step 1: Reset old results when a new file is selected or submit starts**

```js
this.resetMergeResult();
```

- [ ] **Step 2: Handle merge success**

```js
var normalized = self.normalizeMergeResult(res.data);
self.mergeResult = normalized;
self.mergeSummaryText = self.buildMergeSummary(normalized);
alert(self.mergeSummaryText);
```

- [ ] **Step 3: Keep the modal open after success**

```js
// remove self.$emit("close") on merge success
self.submitting = false;
```

### Task 3: verify behavior

**Files:**
- Modify: none

- [ ] **Step 1: Check diagnostics for `static/js/modals.js`**
- [ ] **Step 2: Manually verify merge success flow**

Use a merge upload and confirm:

- a success alert appears
- the modal stays open
- the result area shows all four counters
- missing fields display as `0`
- create/import flow still behaves as before
