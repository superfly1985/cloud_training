# Legacy ultralytics tflite rollback design

本设计用于替换当前新项目中的 `ONNX -> onnx2tf -> TFLite` 主转换链
路。远端离线回放已经证明，当前方案虽然修复了 Web 环境缺少
`numpy` 的问题，但 `onnx2tf 1.28.8` 仍会在内部校验阶段触发
`download_test_image_data()`，最终落到
`Cannot load file containing pickled data when allow_pickle=False`。用户
已经明确要求回退到旧版桌面工具中实际验证过可用的方式，也就是
`best.pt -> Ultralytics export(format='tflite')`。

## Problem summary

当前新项目的 TFLite 转换存在两类连续暴露的问题。

- 第一类问题是环境错配。Web 服务进程原先会在打包前生成本地样本 `.npy`，
  这要求 Web 环境直接具备 `numpy` 和 `Pillow`。
- 第二类问题是 `onnx2tf` 本身的内部行为。即便把样本生成下沉到转换环境，
  远端对现有任务做离线回放时仍然失败，报错链继续落在
  `download_test_image_data()` 和 `allow_pickle=False`。
- 这意味着当前失败点已经不是“环境中缺依赖”，而是“主转换方案本身不稳
  定”。
- 与之相对，旧版项目中真正跑通的链路已经确认存在于
  [model_manager.py](file:///d:/01.AwesomeProject/03.云端训练/src/core/model_manager.py#L379-L506)，
  其主路径是直接调用 `YOLO(best_pt).export(format='tflite', ...)` 连续导
  出 `fp16` 与 `fp32`。

因此，本次改造不再继续修补 `onnx2tf` 主链路，而是明确回退到旧版稳定方
式，并同步调整部署工具的环境保障。

## Selected approach

本次改造采用“旧版 Ultralytics 直导 TFLite 作为唯一主链路”的方案。

- TFLite 产物统一由 `best.pt` 直接导出。
- 导出时沿用旧版稳定参数：
  - `format='tflite'`
  - `imgsz=<task input_size>`
  - `batch=1`
  - `int8=False`
  - `nms=True`
  - `data=<resolved dataset yaml>`
- 通过两次导出生成双精度产物：
  - `half=True` 生成 `best_fp16.tflite`
  - `half=False` 生成 `best_fp32.tflite`
- `best.onnx` 继续保留为附带产物，但不再参与 TFLite 主转换逻辑。

这个方案直接回到用户已经验证过可用的路径，避免继续被 `onnx2tf` 的版本
级行为卡住。

## Architecture changes

### Package manager changes

`app/core/package_manager.py` 继续承担打包编排职责，但 TFLite 转换实现要
收敛到旧版方式。

- 保留 `create_package()` 当前已有的包生命周期控制：
  - 转换失败时 fail-closed
  - 不创建可见半成品包
  - 成功后才继续 ZIP 与入库
- 保留 `data.yaml` / `dataset.yaml` 的解析和回退逻辑。
- 保留 `best.onnx` 导出逻辑，作为附带产物继续进入打包结果。
- 删除 `onnx2tf` 主路径、样本图片枚举、样本 `.npy` 生成与临时脚本逻辑。
- `_convert_tflite()` 改为在固定转换环境中执行一个最小 Python 脚本，脚本
  内只做：
  - `from ultralytics import YOLO`
  - 加载 `best.pt`
  - 两次 `model.export(format='tflite', ...)`
  - 整理产出的 `_float16` / `_float32` 文件
  - 规范化命名为 `best_fp16.tflite` 与 `best_fp32.tflite`
  - 清理多余导出残留

这样 `package_manager.py` 仍是编排层，但不再承载与 `onnx2tf` 相关的复杂
分支。

### Deployment tool changes

部署工具必须随主链路变化一起收敛，否则会继续保障错误的依赖集合。

- `deploy_tool/requirements-conversion.txt` 的职责改为服务旧版直导链路。
- 转换环境必须明确保障以下依赖：
  - `ultralytics`
  - `tensorflow`
  - `numpy`
  - `Pillow`
- `onnx2tf` 不再是主依赖，也不再作为部署成功的校验条件。
- 如果当前转换环境里仍保留 `onnx2tf`，这不会阻碍部署，但部署工具不能再
  把它当作必需门禁。

### Remote testing usability

云端验证流程必须同时满足“可回放”和“低交互”两个要求。

- 在云端做离线回放、转换验证、打包验证时，不能要求用户在一次验证流程中反
  复输入密码。
- 部署工具或测试工具必须复用同一条已建立的 SSH 认证会话，或者显式支持基
  于已配置凭据的一次登录后批量执行命令。
- 所有远端检查、文件同步、离线回放和结果查询都必须走非交互流程，避免用户
  在一次测试里多次确认或补输密码。
- 这条要求适用于后续“部署后云端离线回放验证”，确保在不重新训练的前提下
  可以一键完成整条检查链路。

### Environment ownership

本次回退后，环境边界如下。

- Web 环境继续保持轻量，不为 TFLite 转换直接承担重型依赖。
- 转换环境同时承担：
  - `best.pt -> best.onnx`
  - `best.pt -> best_fp32.tflite`
  - `best.pt -> best_fp16.tflite`
- 这意味着部署工具对转换环境的校验必须覆盖旧版直导链真正使用的 import
  链，而不是继续围绕 `onnx2tf` 做验证。

## Data flow

修复后的打包链路如下。

1. 训练任务结束后进入 `create_package()`
2. 打包层找到 `run_dir`、`best.pt` 和可用的 `data.yaml`
3. 打包层先导出 `best.onnx`，保留现有附带产物能力
4. 打包层调用 `_convert_tflite()`，使用转换环境 Python 执行
   `YOLO(best.pt).export(format='tflite', ...)`
5. 转换环境连续导出 `half=False` 和 `half=True` 两种 TFLite
6. 转换脚本把文件整理成 `best_fp32.tflite` 和 `best_fp16.tflite`
7. 只有当 ONNX 与双 TFLite 都满足成功条件时，才继续生成 ZIP
8. 任意步骤失败时，继续保持 fail-closed，不创建可见产物

## Error handling

本次改造沿用当前严格的失败策略，但错误来源会更聚焦。

- 如果 `best.pt` 不存在，直接失败。
- 如果 `data.yaml` 解析失败或不存在，直接失败。
- 如果转换环境缺少 `ultralytics`、`tensorflow`、`numpy` 或 `Pillow`，转换
  前检查必须直接报错，并由部署工具尽量提前发现。
- 如果 `YOLO.export(format='tflite')` 任一轮失败，整个包创建失败，不入库。
- 如果只生成了单个 TFLite 文件，仍视为失败，不生成最终 ZIP。

## Testing strategy

本次改造至少覆盖以下验证。

- `package_manager` 的 TFLite 转换脚本必须调用
  `YOLO(...).export(format='tflite', ...)`，且同时覆盖 `half=True` 和
  `half=False`。
- 测试中不再出现 `onnx2tf`、`custom_input_op_name_np_data_path` 或样本
  `.npy` 相关断言。
- 部署工具的转换环境校验必须验证：
  - `ultralytics`
  - `tensorflow`
  - `numpy`
  - `PIL.Image`
- `requirements-conversion.txt` 不再要求 `onnx2tf` 作为必需依赖。
- 继续保留失败包不可见、重复包幂等、训练任务状态推进等已有测试。
- 最终必须做一次远端离线回放：
  - 不重新训练
  - 对现有已完成任务直接执行 `create_package()`
  - 验证 `best_fp16.tflite`、`best_fp32.tflite` 和最终 ZIP 均成功生成
- 云端验证脚本或工具必须支持复用单次登录态，验证过程中不重复要求输入密
  码。

## Scope limits

本次改造只回退 TFLite 主转换链路，不包含以下内容。

- 不回退训练任务状态分阶段逻辑。
- 不回退“未完成 ZIP 不可见”的产品规则。
- 不移除 `best.onnx` 产物。
- 不在本次范围内修改用户现有训练超参数与前端展示逻辑。
