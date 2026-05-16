# Deploy tool debug handoff

这份交接文档用于保存今天在 `MetaQA_CloudTraining` 部署工具上的排查和
修改结果。你明天继续工作时，可以直接从本文档开始，不需要重新整理上下
文。

## 当前状态

今天已经完成了部署工具可视化增强的第一轮落地，并确认了一条新的高概率根
因。当前代码已经具备更清晰的部署步骤反馈，但环境安装链路仍有一个关键缺
陷尚未修复。

- 已完成部署 GUI 增强：
  - 增加当前步骤状态展示。
  - 增加当前子阶段文案展示。
  - 增加已耗时显示。
  - 增加运行中步骤的进度条刷新。
- 已完成部署后端增强：
  - 给长耗时命令增加心跳日志。
  - 给训练环境和转换环境安装步骤增加慢步骤提示。
  - 给固定环境验证增加真实失败详情，不再使用误导性固定文案。
- 已确认新的问题焦点：
  - 环境安装阶段可能失败，但被当前命令写法误判成成功。

## 今天已改动的文件

今天的代码改动集中在以下文件：

- `deploy_tool/deploy_manager.py`
- `deploy_tool/deploy_gui.py`
- `test/test_deploy_manager.py`

与部署可视化增强直接相关的关键位置如下：

- 心跳日志与子阶段透传：
  `deploy_tool/deploy_manager.py`
- 环境安装与验证逻辑：
  `deploy_tool/deploy_manager.py`
- GUI 当前状态和耗时展示：
  `deploy_tool/deploy_gui.py`
- 部署验证失败详情测试：
  `test/test_deploy_manager.py`

## 已确认的问题

今天已经确认两个不同层级的问题。

### 1. 旧的失败文案错误

旧逻辑会在固定环境验证失败时，仍然返回 `"固定环境验证完成"` 作为 detail，
导致 UI 出现：

```text
失败: 验证固定环境 - 固定环境验证完成
```

这个问题今天已经修正。现在训练环境或转换环境验证失败时，会返回真实失败
原因，例如：

- `训练环境验证失败: ...`
- `转换环境验证失败: ...`

### 2. 新确认的高概率根因

当前更关键的问题不是验证逻辑本身，而是安装步骤可能没有真正成功。

高风险代码位于 `deploy_tool/deploy_manager.py` 的 `_ensure_remote_env()`：

```python
code, out, err = self._run_command_with_heartbeat(
    f"cd {REMOTE_DIR} && {python_path} -m pip install -r {requirements_rel_path} 2>&1 | tail -20",
    timeout=3600,
    log_cb=log_cb,
    heartbeat_label=f"安装 {env_name} 锁定依赖",
)
```

这里把 `pip install` 的输出通过管道送给了 `tail -20`。在默认 shell 语义下，
如果没有启用 `pipefail`，最终返回码往往取最后一个命令 `tail` 的退出码。结
果就是：

1. `pip install -r ...` 可能已经失败。
2. `tail -20` 正常执行并退出。
3. 整个命令仍然可能返回 `0`。
4. 部署工具误以为安装成功。
5. 后续只有在 `import ultralytics` 验证时才暴露错误。

这与今天观察到的现象一致：

- 训练环境验证失败。
- 转换环境验证失败。
- 两边都在导入 `ultralytics` 时崩溃。

这更像是“依赖安装阶段没有真正完成”，而不是“验证命令写错了”。

## 目前证据

今天拿到的错误表现如下：

```text
训练环境验证失败: Traceback (most recent call last):
...
File "/root/miniforge3/envs/cloud-training/lib/python3.10/site-packages/ultralytics/__init__.py", line 11, in <module>
...

转换环境验证失败: Traceback (most recent call last):
...
File "/root/miniforge3/envs/cloud-conversion/lib/python3.10/site-packages/ultralytics/__init__.py", line 11, in <module>
...
```

从这条信息本身，还不能 100% 证明是哪个具体包缺失，但已经足够说明：

- `ultralytics` 导入链路有问题。
- 问题同时出现在训练环境和转换环境。
- 安装阶段比验证阶段更值得优先排查。

## 已完成验证

今天的本地验证已经完成，结果如下：

1. 运行部署工具相关测试：

```bash
python -m unittest discover -s test -p "test_deploy_manager.py" -v
```

结果：通过。

2. 运行全量测试：

```bash
python -m unittest discover -s test -p "test_*.py" -v
```

结果：通过。

3. 检查 diagnostics：

- `deploy_tool/deploy_manager.py`
- `deploy_tool/deploy_gui.py`
- `test/test_deploy_manager.py`

结果：无新增 diagnostics。

## 明天建议的第一步

明天继续时，优先处理安装步骤返回码被管道吞掉的问题，不要先改版本锁文件。
顺序建议如下。

1. 先修 `deploy_tool/deploy_manager.py` 中 `_ensure_remote_env()` 的安装命令。
2. 去掉 `| tail -20` 这种会掩盖真实退出码的写法。
3. 保留真实退出码的同时，再额外做日志摘要，而不是通过 shell 管道截断。
4. 新增测试，锁定“安装失败不能被当成成功”。
5. 重新跑部署。
6. 再根据新的真实安装失败日志判断是否还要补转换环境依赖。

## 明天建议补的测试

明天建议先补一条部署管理器测试，验证 `_ensure_remote_env()` 在依赖安装失败
时必须返回 `False`。

测试目标：

- 模拟 `_run_command_with_heartbeat()` 返回安装失败。
- 断言 `_ensure_remote_env()` 返回 `False`。
- 断言日志中会打印失败摘要。

## 次级怀疑点

如果明天修完安装返回码问题后，仍然出现 `ultralytics` 导入失败，再继续检查
下面这些方向：

- `deploy_tool/requirements-conversion.txt` 是否缺少 `opencv-python-headless`
  或 `pillow`。
- `ultralytics==8.3.148` 在训练环境与转换环境对 `numpy==1.26.4`、`torch`
  、`tensorflow` 的组合是否还存在兼容性问题。
- 云端机器是否出现网络或索引源问题，导致部分 wheel 没装成功。

在没有新的真实安装失败日志之前，不要先假设是这些次级问题。

## 相关文件

明天优先打开以下文件：

- `deploy_tool/deploy_manager.py`
- `deploy_tool/requirements-training.txt`
- `deploy_tool/requirements-conversion.txt`
- `test/test_deploy_manager.py`

如果需要回看今天的增强型可视化改动，再看：

- `deploy_tool/deploy_gui.py`

## 下一步

你明天恢复工作时，直接从安装步骤根因修复开始。第一目标不是“让验证通过”，
而是“让安装阶段的失败不能再被误判成成功”。拿到新的真实安装失败日志后，
再决定是否调整环境锁定依赖。
