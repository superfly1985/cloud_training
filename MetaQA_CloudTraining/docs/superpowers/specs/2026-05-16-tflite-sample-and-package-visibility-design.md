# TFLite sample and package visibility design

本设计同时解决 `MetaQA_CloudTraining` 中两个已经确认的线上问题：
`onnx2tf` 在转换阶段会因为内部下载测试样本失败而中断，以及同一训练任务
可能重复生成产物记录并过早显示到前端。目标是让 `TFLite` 转换使用本地
训练集样本完成，打包流程只在最终 ZIP 成功生成后才创建可见产物，并让同
一任务的打包入口具备幂等性。

## Problem summary

当前线上问题已经通过远端取证确认：

- 最新任务运行目录已经包含 `data.yaml`，因此当前失败不再是缺少
  `dataset.yaml`。
- `onnx2tf 1.28.8` 对图像型输入会在普通 `convert()` 流程中调用
  `download_test_image_data()`，并尝试读取一份远端下载的 `.npy` 样本。
- 服务器上这一步会在 `numpy.load()` 时报
  `ValueError: Cannot load file containing pickled data when allow_pickle=False`。
- 同一训练任务的完成回调和监控刷新都会触发 `ensure_package()`，而现有打
  包逻辑只有“先查再插”，没有并发保护，所以同一个 `task_id` 会插入两
  条 `packages` 记录。
- 产物列表当前以 `packages` 表为依据，因此失败或未完成的包会过早出现在
  前端，不符合“只有完成 ZIP 才显示产物”的要求。

## Selected approach

本次改造采用一组互相配合的方案，避免只修一半。

- `onnx2tf` 输入样本改为本地生成，不再依赖库内部下载的默认测试图。
- 打包流程只在完整 ZIP 成功写出后才落库并对前端可见。
- 同一任务的自动打包入口收敛为幂等执行，避免同任务重复插入产物记录。
- 训练列表负责展示“训练中/转换中/打包中”等过程状态，产物列表只展示最
  终成品。

## Local sample generation design

转换模块必须为 `onnx2tf` 准备一份本地输入样本 `.npy`。这份样本不来自外
 部下载，而是从当前任务对应的数据集中抽取图片并做最小必要预处理后生成。

样本生成规则如下：

- 优先从数据集的 `images/val` 目录抽取图片。
- 如果 `images/val` 为空，则回退到 `images/train`。
- 至少抽取 1 张，最多抽取少量样本，保持实现简单和转换耗时可控。
- 依据任务的 `input_size` 将图片统一预处理为模型输入尺寸。
- 统一转换为 `RGB`、`float32`、`NHWC` 格式。
- 生成形如 `N x H x W x 3` 的 `.npy` 文件，并通过
  `custom_input_op_name_np_data_path` 传给 `onnx2tf.convert()`。

本地样本文件属于打包阶段的临时文件，不需要进入最终 ZIP。

## Package lifecycle design

打包流程必须区分“后台过程状态”和“最终产物可见性”。

### Training-side status

训练任务可以进入以下过程状态：

- `running`
- `converting`
- `packaging`
- `completed`
- `failed`

其中：

- `converting` 表示训练已结束，正在导出 `ONNX` 或生成 `TFLite`
- `packaging` 表示 `TFLite` 已完成，正在写入最终 ZIP
- `completed` 表示 ZIP 已完整生成并成功入库

### Package visibility

产物列表必须只展示最终成品。

- 如果 `ONNX`、`TFLite`、ZIP 任一步失败，则不创建可见 `packages` 记录。
- 如果 ZIP 尚未写出完成，则前端不显示该产物，也不显示产物跳转按钮。
- 如果任务失败，排查信息只保留在训练任务侧，不通过产物列表暴露。

这意味着失败包即使在后台保留临时目录或日志，也不能写入 `packages` 表，
更不能在前端产物区显示。

## Idempotency design

当前重复包问题来自两个自动入口并发触发同一任务打包。因此需要同时做代码
层和数据层的幂等保护。

代码层要求：

- 同一任务只能保留一个自动打包入口，另一个入口改为只刷新状态，不直接建
  包，或在进入打包前先进行原子化占位判断。
- `ensure_package()` 必须是幂等的，不能依赖“先查再插”的非原子模式。

数据层要求：

- `packages.task_id` 必须具备唯一性约束，防止同任务重复插入。
- 如果并发下已经存在同任务记录，后续调用必须直接返回已有记录，而不是重
  复创建。

## Data flow

本节定义修复后的完整数据流，确保训练、转换、打包和展示边界一致。

1. 训练完成后，任务状态从 `running` 进入 `converting`
2. 打包模块导出 `best.onnx`
3. 打包模块生成本地 `.npy` 样本并执行 `onnx2tf`
4. 同时生成 `best_fp32.tflite` 和 `best_fp16.tflite`
5. `TFLite` 成功后进入 `packaging`
6. ZIP 完整写出后再插入 `packages` 记录，并将任务状态设为 `completed`
7. 任何中间步骤失败都只更新训练任务状态，不生成可见产物

## Testing strategy

本次改造至少需要覆盖以下行为：

- `onnx2tf` 调用时使用本地生成的 `.npy` 样本，而不是默认下载样本。
- 本地样本优先从 `images/val` 抽取，缺失时回退 `images/train`。
- `TFLite` 转换失败时不会插入 `packages` 记录。
- ZIP 未完成时前端不会获得产物入口。
- 同一任务并发触发打包时最终只保留一条 `packages` 记录。

## Scope limits

本次改造聚焦在转换样本、打包幂等和产物可见性，不包含以下内容：

- 不修改训练超参数或训练算法本身。
- 不增加新的模型格式。
- 不把失败产物作为单独的后台审计功能暴露到前端。
