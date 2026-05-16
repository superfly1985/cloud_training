# package fallback and conversion gate design

This document defines the minimum change set needed to bring
`MetaQA_CloudTraining` back in line with the known-good legacy behavior from
`d:\01.AwesomeProject\03.云端训练\main.py` and the old manager modules.

The scope is intentionally narrow. This design only covers two corrections:

1. Restore the legacy three-stage TFLite conversion fallback chain during
   package creation.
2. Unify conversion-environment gates so deployment-time validation and
   runtime validation enforce the same expectations.

## goals

This change restores the legacy conversion behavior without moving business
logic back into `main.py`. The package pipeline must continue to live in
module code, and `main.py` remains orchestration-only.

The updated behavior must satisfy these goals:

- Package creation uses the same practical conversion order as the legacy
  `ModelManager`.
- Runtime conversion and deployment-time checks stop using different
  definitions of "conversion environment is ready."
- Conversion failure reports stay fail-closed. If final TFLite artifacts are
  missing, the package must not be published.
- The change stays focused on package conversion and gate alignment. It does
  not redesign deployment, training orchestration, or package visibility.

## current drift from the legacy implementation

The current codebase diverges from the legacy implementation in two critical
ways.

First, the package pipeline only runs one scripted `YOLO.export()` attempt in
`app/core/package_manager.py`. If that attempt fails, the code only checks for
existing `.tflite` files on disk. The legacy implementation instead runs a
three-stage chain:

1. direct Python `YOLO.export(...)`
2. `python -m ultralytics export ...`
3. `yolo export ...`

Second, the current conversion gate is split across two different standards.
`app/core/system_manager.py` uses a relatively light runtime gate, while
`deploy_tool/deploy_manager.py` enforces a different and heavier deployment
gate. This makes deployment success an unreliable predictor of runtime
behavior.

## design summary

This design keeps the current module boundaries and only changes module
internals.

- `app/core/package_manager.py` remains the package orchestration module.
- `app/core/system_manager.py` remains the runtime environment inspection
  module.
- `deploy_tool/deploy_manager.py` remains the deployment validation module.

No business logic moves back into `main.py`.

## package conversion flow

The package conversion flow must be updated to match the legacy behavior more
closely.

`create_package()` continues to:

1. resolve `best.pt`
2. resolve `dataset.yaml`
3. ensure `best.onnx` exists if possible
4. attempt TFLite conversion
5. stay fail-closed if required outputs are missing

The internal TFLite conversion helper must change from a single scripted
attempt into a three-stage fallback chain:

1. run direct Python `YOLO(best_pt).export(...)` twice, once for fp32 and once
   for fp16
2. if stage 1 fails, run `python -m ultralytics export ...`
3. if stage 2 fails, run `yolo export ...`

Each stage must attempt to discover generated fp32 and fp16 TFLite files,
normalize them into canonical names in the working directory, and return the
successful outputs as structured results.

The package pipeline must keep its current fail-closed behavior. If no final
`best_fp32.tflite` and no usable fallback output exist, package creation must
raise an error and must not create a visible package record.

## conversion gate alignment

The runtime gate and deployment-time gate must enforce the same conversion
contract.

The aligned contract is:

- conversion Python exists and is executable
- `from ultralytics import YOLO` succeeds
- `import tensorflow` succeeds
- `import numpy` succeeds
- `from PIL import Image` succeeds
- `import onnx2tf` succeeds

This design intentionally aligns on the lightweight legacy gate. It does not
require deploy-time checks for `onnxscript`, `onnx_ir`, `FLOAT4E2M1`, or other
extra assertions that are not part of the legacy conversion gate itself.

`app/core/system_manager.py` and `deploy_tool/deploy_manager.py` must both use
this same contract. If the contract changes later, both places must change
together.

## autoinstall behavior

The legacy training script explicitly disabled Ultralytics autoinstall. The
current codebase does not apply the same protection to conversion execution.

To reduce runtime environment mutation, conversion execution should explicitly
disable Ultralytics autoinstall in the conversion subprocess context. This
applies to:

- scripted direct export in `package_manager.py`
- deployment-time conversion gate probes, when practical

This change is defensive. It is not a replacement for correct dependency
installation.

## testing

This change needs focused regression tests rather than broad new coverage.

Tests must cover:

- `package_manager` falls back from direct export to `python -m ultralytics`
  when the direct scripted stage fails
- `package_manager` falls back to `yolo export` when both earlier stages fail
- canonical output discovery still returns normalized fp32 and fp16 results
- package creation remains fail-closed when no usable TFLite output is produced
- deployment-time gate text matches the runtime gate contract
- runtime gate text matches the same contract

Tests do not need to exercise real remote conversion. Mocked subprocess and
command execution are sufficient for the new fallback logic and gate contract.

## out of scope

This design does not include the following work:

- redesigning training flow
- changing package database schema
- changing upload strategy
- changing release packaging
- adding a new conversion backend beyond the legacy fallback chain

## success criteria

This work is complete when all of the following are true:

- package conversion uses the restored three-stage fallback chain
- runtime and deploy-time gates enforce the same conversion contract
- package creation still blocks incomplete TFLite packages
- local regression tests pass for the touched modules
- a later cloud replay can validate the restored chain without requiring
  another architectural change first
