# web environment check and repair alignment design

This document defines the minimum design needed to make the cloud web
runtime environment check and repair workflow fully consistent with the
deployment tool in `MetaQA_CloudTraining`.

The scope is intentionally narrow. This design only covers environment
inspection and environment repair inside the deployed web application. It
does not redesign file upload, service restart, autostart configuration, or
package conversion flow.

## goals

This change keeps the existing module boundaries in the web runtime while
eliminating logic drift between the web UI and the deployment tool. The web
application must stop maintaining a weaker or different definition of
"environment is ready."

The updated behavior must satisfy these goals:

- The web runtime and the deployment tool use the same environment contract.
- The web runtime and the deployment tool report the same pass and fail
  conclusions on the same machine.
- The web runtime repair flow applies the same dependency synchronization and
  validation rules as the deployment tool for web, training, and conversion
  environments.
- The design stays modular. `main.py` does not regain business logic.

## current drift

The current codebase has two separate environment workflows.

`deploy_tool/deploy_manager.py` uses a deployment-oriented pipeline with
precheck, fixed environment creation, requirements synchronization, and final
fixed-environment verification. This is the stricter and more reliable
source of truth.

`app/core/system_manager.py` and `app/core/init_manager.py` expose a web
runtime environment check and repair flow, but they currently drift from the
deployment tool in several ways:

- They define their own check items and messages.
- They repair environments with ad hoc `pip install` and uninstall actions
  instead of requirements-file synchronization.
- They do not share the same step list, validation snippets, or dependency
  locks as the deployment tool.
- The frontend presents "single item repair," but the backend really runs a
  broader repair task.

This drift lets the web UI and deployment tool disagree about readiness,
which is exactly the failure mode this design must remove.

## design summary

This design keeps the web runtime modules and deploy tool modules separate,
but both sides must consume one shared environment contract.

- `app/core/system_manager.py` remains the runtime inspection module.
- `app/core/init_manager.py` remains the runtime repair orchestration module.
- `deploy_tool/deploy_manager.py` remains the deployment orchestration module.
- A new shared contract module defines environment paths, requirement files,
  validation snippets, step names, and alignment rules.

No environment-related rule may be duplicated in handwritten form across
these modules once the alignment is complete.

## shared environment contract

The shared contract is the core of this design. It prevents the web runtime
and deployment tool from drifting again later.

The contract module must define:

- fixed Python paths for `base`, `cloud-training`, and `cloud-conversion`
- requirement file locations for web, training, and conversion environments
- training environment verification snippet
- conversion environment verification snippet
- conversion gate snippet
- environment isolation verification snippet
- canonical step names for runtime repair
- user-facing labels for aligned check items

The deployment tool and the web runtime must both import these values instead
of rebuilding them locally.

If a future dependency lock or verification contract changes, the shared
module becomes the single place to update.

## aligned check behavior

The web runtime check pipeline must use the same environment contract as the
deployment tool for all environment-related checks.

This alignment applies to these check items:

- training environment
- conversion environment
- PyTorch
- Ultralytics
- ONNX
- TensorFlow
- onnx2tf
- conversion gate
- environment isolation

The web runtime can continue to expose extra local-only checks, such as disk
space or GPU visibility, but those checks must stay clearly separate from the
deployment-aligned environment contract.

For the aligned items, the following properties must match deployment-tool
behavior:

- target Python executable
- import or verification snippet
- blocking status
- user-facing item name
- pass and fail semantics

This means the web runtime must stop using weaker or differently worded
checks for training and conversion readiness.

## aligned repair behavior

The web runtime repair pipeline must match deployment-tool environment repair
semantics, while still staying inside the scope of a running web service.

The runtime repair flow must align to these steps:

1. validate fixed runtime paths
2. ensure the training environment exists
3. ensure the conversion environment exists
4. synchronize training requirements from
   `deploy_tool/requirements-training.txt`
5. synchronize conversion requirements from
   `deploy_tool/requirements-conversion.txt`
6. verify the training environment with the aligned verification snippet
7. verify the conversion environment with the aligned verification snippet
8. verify the final environment summary again

The web runtime does not need to copy deployment-only steps such as upload,
stop service, configure systemd, or start service verification. Those remain
deployment-tool responsibilities.

However, within the shared scope of environment readiness, the repair
behavior must match the deployment tool exactly:

- create missing conda environments with the fixed conda executable
- install dependencies from requirement files, not package-by-package guesses
- use the same final verification criteria
- preserve fixed environment names and fixed Python paths

Ad hoc package installation in `init_manager.py` must be replaced by
requirements synchronization so the runtime repair path stops diverging from
deployment.

## frontend behavior

The frontend in `static/js/system-tab.js` can keep its current task-based
presentation, but the meaning of the buttons and status labels must become
accurate.

The updated frontend behavior must follow these rules:

- The environment check list uses backend-supplied aligned check items.
- The auto-fix task shows step names that match the aligned repair pipeline.
- A per-item "repair" button must not imply a truly isolated one-item fix if
  the backend runs the whole repair pipeline.
- If a one-click item button remains, its label or helper text must make it
  clear that it triggers the unified environment repair workflow.

This prevents the UI from promising finer-grained behavior than the backend
actually supports.

## module responsibilities

This design keeps the existing module boundaries and clarifies what each
module owns.

`app/core/system_manager.py` owns:

- environment check task lifecycle
- runtime check execution
- environment summary generation

`app/core/init_manager.py` owns:

- repair task lifecycle
- aligned repair-step orchestration
- log capture and step progress updates

The new shared contract module owns:

- fixed paths
- requirements file mapping
- aligned verification snippets
- aligned environment check metadata
- aligned repair step metadata

`deploy_tool/deploy_manager.py` continues to own deployment-only behavior,
but it must read shared contract values instead of keeping its own copies of
those environment rules.

## testing

This change needs focused regression coverage that proves the web runtime and
deployment tool stay aligned.

Tests must cover:

- the shared contract returns the expected fixed paths and requirement files
- runtime check snippets match deployment verification snippets for aligned
  items
- runtime repair uses requirements-file synchronization instead of ad hoc
  package installation
- runtime repair step names match the aligned contract
- deployment tool still uses the same shared contract after refactor
- frontend-facing API payloads preserve the expected task structure

Tests do not need to start real conda environments. Mocked subprocess and
mocked command execution are sufficient for alignment coverage.

## out of scope

This design does not include the following work:

- changing deployment upload behavior
- changing service stop and start behavior
- changing systemd or autostart logic
- redesigning the web system page layout
- redesigning package conversion
- redesigning training flow

## success criteria

This work is complete when all of the following are true:

- the web runtime and deployment tool use one shared environment contract
- the web runtime check results match deployment-tool verification for aligned
  items
- the web runtime repair flow uses the same requirements files and final
  verification rules as the deployment tool
- the frontend no longer misrepresents the scope of environment repair
- local regression tests pass for touched modules
- later environment changes only require updating one shared contract instead
  of two drifting implementations

## next steps

Once this design is approved, the next step is to write an implementation
plan that introduces the shared contract module first, then migrates web
check logic, then migrates web repair logic, and finally updates frontend
wording and regression tests.
