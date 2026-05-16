# ONNX to TFLite package conversion design

This design updates the package conversion path in
`MetaQA_CloudTraining` so packaged training artifacts generate TFLite
models through `onnx2tf` instead of trying to re-export an ONNX file
through `Ultralytics`. The goal is to make the package pipeline match
the current environment split, preserve conversion quality, and include
the dataset metadata required by the converter.

## Problem summary

The current package flow exports `best.onnx` in the training
environment, then tries to load that ONNX file through `Ultralytics`
and call `export(format='tflite')` in the conversion environment. That
fails on the deployed server because the installed `Ultralytics`
version only supports `export()` from a `.pt` model. The result is a
partial package that contains `best.pt`, `best.onnx`, `results.csv`,
and `info.json`, but no TFLite files.

## Selected approach

This change uses `onnx2tf` as the only package-time ONNX-to-TFLite
converter.

- The training environment still exports `best.pt -> best.onnx`.
- The conversion environment now runs `onnx2tf` against `best.onnx`.
- The conversion step must generate both `fp32` and `fp16` TFLite
  outputs.
- The conversion step must not generate `int8`.
- The conversion step must receive the training run's `dataset.yaml`
  path so the converter has class and shape metadata available.

This approach fits the current architecture because the project already
separates training and conversion environments, and the deployed
conversion environment already contains `tensorflow` and `onnx2tf`.

## Conversion contract

The package builder must resolve the following inputs before starting
conversion:

- `best.onnx`
- conversion Python from `convert.python_export_cmd` or the fixed
  fallback conversion interpreter
- `dataset.yaml`, preferring the training run copy that is later packed
  into the ZIP
- the training image size from task metadata or config

The converter must produce these canonical outputs inside the training
run directory:

- `best_fp32.tflite`
- `best_fp16.tflite`

The packaging logic must continue to collect those files, mark
`conversion_items.tflite_fp32` and `conversion_items.tflite_fp16`, and
record a partial or failed status when either file is missing.

## Implementation outline

The implementation stays focused in `app/core/package_manager.py`.

- Update `create_package()` so it explicitly resolves the dataset YAML
  path and passes it into `_convert_tflite()`.
- Replace `_convert_tflite()` with an `onnx2tf`-based script runner
  that:
  - validates `onnx_path`, conversion Python, and dataset YAML
  - runs one `fp32` conversion and one `fp16` conversion
  - disables `int8`
  - writes outputs with canonical names in the training run directory
  - returns the generated file paths
- Keep the existing ONNX export logic in the training environment
  unchanged.

## Testing strategy

The change needs focused regression coverage in
`test/test_package_manager.py`.

- Verify `create_package()` passes `dataset.yaml` into
  `_convert_tflite()`.
- Verify conversion metadata becomes `complete` when both `fp32` and
  `fp16` outputs exist.
- Verify `_convert_tflite()` builds an `onnx2tf` script that generates
  both precisions and does not request `int8`.

## Scope limits

This design does not add a fallback `pt -> tflite` path. It also does
not change the manual model conversion tool in the legacy desktop code.
The work only fixes the package-generation pipeline in
`MetaQA_CloudTraining`.
