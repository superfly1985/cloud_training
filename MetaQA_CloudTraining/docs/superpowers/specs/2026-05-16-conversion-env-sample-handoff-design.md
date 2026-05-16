# Conversion environment sample handoff design

本设计解决一个已经通过远端取证确认的线上问题：训练任务本身已经完成，
但训练完成后的自动打包会在 Web 服务进程里因为 `No module named
'numpy'` 失败，导致任务停在转换失败且没有最终产物。目标是把
`onnx2tf` 所需的本地样本生成完全下沉到转换环境，同时让部署工具明确保
障转换环境具备这条链路需要的依赖与验证。

## Problem summary

当前线上行为已经确认如下：

- 最新训练任务的 `train.log` 显示训练已完整结束，`best.pt` 和
  `results.csv` 已正常生成。
- Web 服务由 systemd 以
  `/home/ubuntu/cloud-training-runtime/miniforge3/bin/python run.py`
  启动。
- 远端 `server.log` 明确记录
  `训练完成后自动打包失败 ... No module named 'numpy'`。
- 同机 `python3` 可以导入 `numpy`，但 Web 服务实际使用的
  `miniforge3/bin/python` 不能导入 `numpy`。
- 当前
  [package_manager.py](file:///d:/01.AwesomeProject/03.云端训练/MetaQA_CloudTraining/app/core/package_manager.py)
  在 `_build_conversion_sample()` 中直接导入 `numpy` 和 `PIL`，这一步
  发生在 Web 进程里，而不是转换环境里。

因此，当前失败点并不是 `onnx2tf` 转换本身，而是“生成转换输入样本”这一
前置步骤放在了错误的运行环境中。

## Selected approach

本次改造采用“样本生成与模型转换同进程执行”的方案。

- Web 环境只负责收集训练目录、数据集目录和图片路径，不再承担 `numpy`、
  `Pillow` 依赖。
- 转换脚本由 `FIXED_CONVERSION_PYTHON` 执行，并在转换环境内部完成样本
  生成与 `onnx2tf.convert()` 调用。
- 部署工具继续保持 Web 环境轻量，同时把样本生成所需依赖明确归入转换环
  境，并在部署验证阶段进行导入校验。

这个方案可以保持环境边界清晰，避免以后再次出现“Web 能启动，但自动打包
 因依赖错位失败”的问题。

## Architecture changes

### Package manager responsibility

`package_manager.py` 仍负责打包编排，但职责调整如下：

- 保留数据集目录解析、样本图片枚举和转换结果收集。
- 删除 Web 进程内的样本 `.npy` 生成步骤。
- `_convert_tflite()` 改为把图片路径列表、输入尺寸、输出目录等参数写入临
  时转换脚本。
- 转换脚本在转换环境中导入 `numpy`、`PIL`、`onnx`、`onnx2tf`，生成本
  地 `.npy` 样本后继续执行转换。

这样主编排层依然只负责“准备参数并启动转换”，真正的数据预处理和模型转
换都留在环境正确的模块边界内。

### Conversion script responsibility

转换脚本承担以下完整职责：

- 接收 `onnx_path`、`dataset_yaml`、`image_paths`、`imgsz`、`output_dir`
  和请求格式。
- 读取第一输入节点名。
- 基于传入的图片路径在转换环境内生成 `float32`、`NHWC` 的 `.npy` 样本。
- 将样本通过 `custom_input_op_name_np_data_path` 传给 `onnx2tf`。
- 生成并整理 `best_fp32.tflite` 和 `best_fp16.tflite`。
- 在结束时删除临时样本文件和临时输出目录。

如果图片列表为空或脚本内样本生成失败，转换脚本直接退出并把错误交回打包
流程，打包流程继续沿用 fail-closed，不生成可见产物。

## Deployment tool changes

部署工具要跟着这次边界调整一起修正。

### Requirements ownership

- `deploy_tool/requirements-web.txt` 不新增 `numpy` 或 `Pillow`。
- `deploy_tool/requirements-conversion.txt` 必须显式包含：
  - `numpy`
  - `Pillow`
  - `onnx`
  - `tensorflow`
  - `onnx2tf`

### Verification changes

部署工具的转换环境验证不再只验证 `tensorflow` 和 `onnx2tf`，还必须同时
验证：

- `numpy`
- `PIL.Image`
- `onnx`

这样部署结束时就能提前发现“转换脚本会用到的依赖缺失”，而不是等用户训
练完才在自动打包阶段暴露问题。

## Data flow

修复后的数据流如下：

1. 训练结束后，打包入口进入 `create_package()`
2. Web 进程解析 `run_dir`、`dataset_yaml`、`dataset_dir`
3. Web 进程枚举样本图片路径，但不生成 `.npy`
4. `_convert_tflite()` 生成临时脚本并调用转换环境 Python
5. 转换环境脚本生成样本 `.npy`，然后执行 `onnx2tf`
6. 转换成功后输出 `best_fp32.tflite` 和 `best_fp16.tflite`
7. 打包流程继续进入 ZIP 生成与入库
8. 任意中间步骤失败时，继续保持 fail-closed，不创建可见产物

## Testing strategy

本次改造至少覆盖以下测试：

- `_convert_tflite()` 生成的脚本内部包含 `numpy`、`PIL` 导入和样本生成逻
  辑。
- Web 侧不再调用 `_build_conversion_sample()` 生成 `.npy` 文件。
- 主应用导入时仍不要求 Web 环境具备 `numpy` 或 `Pillow`。
- 部署工具验证转换环境时会同时校验 `numpy` 和 `PIL.Image`。
- `requirements-conversion.txt` 显式声明 `Pillow`。

## Scope limits

本次改造聚焦“样本生成下沉到转换环境”和“部署工具同步保障转换依赖”，不
包含以下内容：

- 不改变训练算法与超参数。
- 不把 Web 环境改成全功能环境。
- 不在本次范围内直接修改远端服务器现有环境。
