# Merge result panel polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the merge success `alert` with a polished in-modal success card and a 2x2 result grid.

**Architecture:** Keep the behavior inside `merge-dataset-modal` and reuse existing response fields. `modals.js` owns the markup and state, while `style.css` owns the visual treatment for the success card and the four stat tiles.

**Tech Stack:** Vue component in plain JavaScript, existing global CSS

---

## File map

- Modify: `static/js/modals.js`
- Modify: `static/css/style.css`
- Test: diagnostics and JS syntax verification

### Task 1: polish the merge result markup

**Files:**
- Modify: `static/js/modals.js`

- [ ] **Step 1: Remove the merge success alert call**
- [ ] **Step 2: Replace the plain result block with success-card markup**
- [ ] **Step 3: Keep the existing result state and summary text logic**

### Task 2: add focused styles

**Files:**
- Modify: `static/css/style.css`

- [ ] **Step 1: Add a dedicated merge result card style**
- [ ] **Step 2: Add a 2x2 stat grid style**
- [ ] **Step 3: Keep colors and spacing aligned with the current design tokens**

### Task 3: verify the UI script

**Files:**
- Modify: none

- [ ] **Step 1: Run diagnostics for `static/js/modals.js` and `static/css/style.css`**
- [ ] **Step 2: Run `node --check static/js/modals.js`**
