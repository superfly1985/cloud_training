# Deploy GUI layout and web link design

This document defines the GUI-only redesign for
`deploy_tool/deploy_gui.py`. The goal is to make the deployment tool easier
to read and operate without changing the underlying deployment workflow in
`deploy_manager.py`.

The redesign has two user-facing outcomes:

1. Reorganize the layout into a more logical two-column workspace.
2. Add a button that opens the deployed server web UI directly after
   deployment.

## goals

The current deployment tool already works functionally, but its interface
puts most information into a single vertical stack. That makes the form,
status, progress, steps, and logs compete for attention in the same column.

This redesign must improve scanability and action clarity while preserving
all current deployment behavior.

The updated GUI must satisfy these goals:

- Group input and actions on the left.
- Group status, progress, steps, and logs on the right.
- Make the main deployment action more prominent than secondary actions.
- Provide a direct entry point to open the deployed web UI.
- Avoid changing deployment semantics, SSH behavior, or step execution logic.

## current problems

The current layout in `deploy_gui.py` is functionally complete but visually
flat. All major sections stack top-to-bottom:

- server connection
- deployment info
- deploy steps
- deploy buttons
- progress
- logs

This creates several usability problems:

- Primary actions are visually separated from the status they control.
- Logs take the largest area, but progress and summary status are more
  important during active deployment.
- The deploy-step row is dense and hard to scan when many steps exist.
- The success result is only written into the log as plain text.
- The server web URL is not exposed as a direct action.

## design summary

The redesigned GUI uses a left-right split.

- The left column is the control column.
- The right column is the monitoring column.

This keeps user intent clear:

- you configure and start actions on the left
- you watch state and review results on the right

The redesign stays inside `deploy_gui.py`. No deployment-manager behavior or
deployment step list changes are required for this work.

## layout structure

The window keeps a single main frame, but the content is reorganized into two
columns under the title.

### left column

The left column contains configuration and actions. It is narrower than the
right column and stays focused on concise interaction.

The left column includes these cards, in order:

1. **服务器连接**
   - IP address
   - SSH port
   - username
   - password
   - test connection button
   - connection status text

2. **部署信息**
   - local source path
   - resolved remote path
   - service port

3. **操作区**
   - deploy button
   - cancel button

4. **快速访问**
   - server web URL display
   - open server web button

This structure puts all "what you enter" and "what you click" in one place.

### right column

The right column contains live feedback. It gets more width because it must
show longer text and more dynamic status.

The right column includes these sections, in order:

1. **部署状态**
   - current step
   - current detail message
   - elapsed time
   - progress bar
   - compact progress label

2. **部署步骤**
   - vertical step list instead of one wide horizontal strip
   - each step keeps color-coded state
   - each row remains readable at smaller widths

3. **部署日志**
   - large log area
   - keeps current color tags and scroll behavior

This makes status readable without forcing the user to search through the log
for the current state.

## step presentation

The current deploy-step display uses one long horizontal row. That works only
while the user can visually parse many narrow labels in sequence.

The redesigned step display must change to a vertical or compact stacked
presentation. Each step item must still show these states:

- pending
- running
- success
- error
- skip

The existing state color logic in `_set_step_state()` can remain. Only the
layout of those step indicators changes.

## direct server web access

The redesigned GUI adds a dedicated way to open the deployed web UI.

### behavior

The GUI must keep a runtime URL derived from:

- host from the current connection form
- fixed service port from `SERVICE_PORT`

The resulting link format is:

`http://{host}:{SERVICE_PORT}`

The GUI must add:

- a read-only text display for the current server web URL
- an **打开服务器 Web** button

### enablement rules

The button must be disabled when no valid host is available.

The button becomes useful in two cases:

- after the user enters a host and the GUI can construct a URL
- especially after deployment succeeds, when the tool confirms the service is
  ready

The success state must make the button clearly available. The URL text must
also update when the host changes.

### action behavior

When the user clicks **打开服务器 Web**, the GUI opens the link with the
system default browser.

If the host is empty, the button remains disabled. If browser launch fails,
the GUI must show a visible error message instead of failing silently.

## interaction rules

The redesign keeps existing deployment behavior but improves how controls are
grouped.

- **测试连接** remains independent from deployment.
- **一键部署** remains the primary action.
- **取消部署** remains visible near the primary action.
- **打开服务器 Web** is a navigation/result action, not a deployment action.

This distinction matters because the web-link button must not look like a
deployment control.

## implementation boundaries

This work intentionally excludes backend behavior changes.

Out of scope:

- changing `deploy_manager.py` deployment steps
- changing SSH logic
- changing deployment result semantics
- changing packaging or upload behavior
- changing service verification logic

In scope:

- layout reorganization in `deploy_gui.py`
- button grouping and labeling
- step-display layout update
- server web link display and open action
- local GUI state required for button enablement

## testing

This work needs focused GUI-level regression checks.

Tests or verification must cover:

- host changes update the displayed server web URL
- the open-web button is disabled when host is empty
- deployment success updates the URL action state correctly
- the step list still reflects deploy-step state transitions
- log behavior remains unchanged

Because this is a Tkinter GUI, some checks can stay as targeted manual
verification if the codebase does not already have GUI automation for the
window structure.

## success criteria

This redesign is complete when all of the following are true:

- the GUI uses a left control column and right monitoring column
- the primary action area is visually clearer than before
- deploy steps are easier to scan than the current horizontal strip
- the deployed server web URL is visible in the interface
- the user can click one button to open the server web UI
- deployment logic remains unchanged

## next steps

Once this design is approved, the next step is to write an implementation
plan for the Tkinter layout refactor, button-state handling, and final GUI
verification.
