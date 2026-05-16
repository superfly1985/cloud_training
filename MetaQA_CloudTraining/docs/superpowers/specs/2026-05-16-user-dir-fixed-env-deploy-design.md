# 统一用户目录固定三环境部署设计

本文档定义 `MetaQA_CloudTraining` 在新干净服务器上的新部署方案。该方案保留
“固定三环境、固定职责、不做大范围扫描”的核心原则，但不再依赖 `/root`
目录，也不再要求 `root` 直接登录。目标是让部署工具可以在 `ubuntu` 用户下
工作，把 Web、训练、转换、项目、日志和数据统一放入同一个用户目录根下。

本文档适用于以下场景：

- 新服务器是干净机器，历史环境污染少，适合按规划首次部署。
- 服务器可以用 `ubuntu` 用户登录。
- `ubuntu` 用户具备 `sudo -n` 能力，必要时可以执行系统级动作。
- 你希望继续沿用固定三环境模型，而不是回到动态搜索路径的旧方案。

## 1. 设计目标

本方案解决当前 `/root` 固定路径模型在新服务器上的三个现实问题。

1. 服务器可能不开放 `root` 直接登录，但 `ubuntu` 用户可登录且具备 sudo。
2. `/root/miniforge3` 与 `/root/MetaQA_CloudTraining` 的固定路径假设，不适合
   新干净服务器的标准化初始化。
3. 继续围绕旧服务器污染环境补丁式修复，成本高于在干净服务器上按统一规则
   从零部署。

本方案实施后必须满足以下结果：

- 固定路径依然成立，但固定根目录切换为用户目录。
- Web、训练、转换三环境都位于同一业务根目录下。
- 部署工具首次部署时可以自动引导安装 Miniforge。
- 日常部署不扫描候选路径，不猜测环境位置，只使用配置中的固定路径。
- 非必要动作不依赖 root；只有系统级操作才通过 `sudo -n` 执行。

## 2. 选型结论

本次选型在三种方案中明确选择“统一用户目录固定根”。

### 2.1 被放弃的方案

以下两种方案不作为本次主线方案。

- **继续 `/root` 固定路径**：改动最小，但依赖 `root` 登录与 `/root`
  可用性，不符合新干净服务器的登录现实。
- **用户目录与系统目录混合**：可以工作，但边界容易模糊，后期排障时最容易
  出现“到底哪个目录才是准的”问题。

### 2.2 采用的方案

本次采用“统一用户目录固定根”方案。

- SSH 登录用户固定为 `ubuntu`
- 业务根目录固定为 `/home/ubuntu/cloud-training-runtime`
- Miniforge、项目目录、数据目录、日志目录、运行状态文件都放在该根目录内
- 必要时使用 `sudo -n` 做系统级动作

采用该方案的原因如下：

- 与当前新服务器登录方式天然匹配。
- 不依赖 `/root` 与 root 直接登录。
- 仍然可以保持固定路径和固定职责。
- 后续迁移新服务器时，目录模型更稳定，重建成本更低。

## 3. 固定目录布局

本方案的核心是“固定根目录 + 固定展开路径”，而不是“自由路径 + 动态搜索”。

### 3.1 固定业务根目录

业务根目录固定为：

```text
/home/ubuntu/cloud-training-runtime
```

所有运行时目录都从这个根路径展开。

### 3.2 固定运行目录

目录布局固定如下：

| 类型 | 固定路径 |
| --- | --- |
| 业务根目录 | `/home/ubuntu/cloud-training-runtime` |
| Miniforge 根目录 | `/home/ubuntu/cloud-training-runtime/miniforge3` |
| 项目根目录 | `/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining` |
| 数据目录 | `/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data` |
| 部署状态文件 | `/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data/deploy_state.json` |
| 初始化状态文件 | `/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data/init_state.json` |
| 环境快照目录 | `/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data/logs` |

### 3.3 固定命令路径

命令路径固定如下：

| 类型 | 固定路径 |
| --- | --- |
| `conda` | `/home/ubuntu/cloud-training-runtime/miniforge3/bin/conda` |
| Web Python | `/home/ubuntu/cloud-training-runtime/miniforge3/bin/python` |
| 训练 Python | `/home/ubuntu/cloud-training-runtime/miniforge3/envs/cloud-training/bin/python` |
| 转换 Python | `/home/ubuntu/cloud-training-runtime/miniforge3/envs/cloud-conversion/bin/python` |

这些路径必须通过配置生成，不得再在代码里写死 `/root/...`。

## 4. 固定三环境职责

虽然根目录从 `/root` 切到了用户目录，但三环境职责完全保持不变。

| 角色 | 固定路径 | 职责 | 禁止事项 |
| --- | --- | --- | --- |
| Web 环境 | `.../miniforge3/bin/python` | 运行 `run.py`、FastAPI、Uvicorn、基础系统接口 | 禁止承担训练与转换 |
| 训练环境 | `.../envs/cloud-training/bin/python` | 训练任务、`best.pt -> ONNX` 导出、训练监控 | 禁止安装 `tensorflow`、`onnx2tf` |
| 转换环境 | `.../envs/cloud-conversion/bin/python` | `ONNX -> TFLite` 转换与转换验证 | 禁止承担 Web 服务 |

本方案继续禁止以下行为：

- `which python`
- 搜索多个候选 Python 路径
- 按 `sys.executable` 猜测训练环境
- clone base 作为训练或转换环境

若固定路径不存在，则必须返回明确错误或进入首次引导流程，不允许隐式回退。

## 5. 登录与提权模型

本方案把“登录身份”和“执行权限”拆开处理，避免把所有事情都交给 root。

### 5.1 登录身份

SSH 登录用户固定为：

```text
ubuntu
```

部署工具所有连接、上传、目录检查、项目运行，默认都以 `ubuntu` 身份执行。

### 5.2 默认执行原则

默认原则如下：

- 项目目录创建、文件上传、Miniforge 安装、Conda 环境创建、项目运行全部以
  `ubuntu` 身份执行。
- 只有系统级动作才使用 `sudo -n`。
- 如果当前步骤不需要系统权限，则禁止无意义提权。

### 5.3 需要提权的动作

仅以下动作允许走 `sudo -n`：

- 安装系统依赖，例如 `libgl1`、`libglib2.0-0`
- 写入 systemd 系统服务文件
- 可选的系统级防火墙或端口配置

以下动作默认不需要提权：

- 安装 Miniforge 到用户目录
- 创建训练与转换环境
- 上传项目
- 安装 Python 锁定依赖
- 启动 Web 服务

## 6. 首次引导策略

与旧 `/root` 方案不同，新干净服务器不再要求你手工预装 `/root/miniforge3`。
首次部署时，部署工具必须具备“引导阶段”。

### 6.1 首次引导触发条件

以下任一条件成立时，进入首次引导：

1. 业务根目录不存在
2. Miniforge 固定路径不存在
3. 项目目录不存在
4. 部署状态文件不存在
5. 固定训练环境或固定转换环境不存在

### 6.2 首次引导步骤

首次引导顺序固定如下：

1. 检查 `ubuntu` 登录与 `sudo -n` 能力
2. 创建业务根目录
3. 检查 Miniforge 固定路径
4. 若 Miniforge 不存在，则安装到固定用户目录
5. 创建项目目录
6. 上传项目代码与锁定文件
7. 安装 Web 依赖
8. 创建训练环境
9. 创建转换环境
10. 安装训练依赖
11. 安装转换依赖
12. 验证三环境
13. 启动 Web 服务
14. 写入部署状态文件与环境快照

### 6.3 引导失败边界

若首次引导失败，必须遵守以下边界：

- 不得扫描其他路径继续尝试
- 不得切回 `/root` 路径
- 必须明确指出失败发生在哪一步
- 必须保留日志和当前状态文件

## 7. 部署工具改造范围

本方案要求对现有部署工具做一次“路径固定根可配置化”改造，但不改动其核心
思路。

### 7.1 需要可配置化的路径常量

现有部署工具中以下固定路径常量必须迁移为“基于远端固定根目录生成”：

- `REMOTE_DIR`
- `FIXED_CONDA`
- `FIXED_BASE_PYTHON`
- `FIXED_TRAINING_PYTHON`
- `FIXED_CONVERSION_PYTHON`
- `DEPLOY_STATE_PATH`

### 7.2 建议新增的部署配置项

部署 GUI 与部署配置文件建议新增以下字段：

| 字段 | 示例值 |
| --- | --- |
| `remote_user` | `ubuntu` |
| `remote_port` | `22` |
| `remote_base_dir` | `/home/ubuntu/cloud-training-runtime` |
| `use_sudo` | `true` |
| `service_mode` | `nohup` |

其中 `remote_base_dir` 是所有固定路径的唯一根来源。

### 7.3 必须保持不变的原则

改造后仍然必须满足以下原则：

- 不扫描候选路径
- 不做环境角色猜测
- 不按系统现有 Python 自动选路径
- 不回退到 `/root` 方案

## 8. 服务启动方案

本方案在新服务器上优先采用依赖最少的启动策略。

### 8.1 默认方案

默认使用 `nohup` 启动 Web 服务：

```bash
cd /home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining && \
nohup /home/ubuntu/cloud-training-runtime/miniforge3/bin/python run.py \
> data/logs/server.log 2>&1 &
```

采用 `nohup` 作为默认方案的原因如下：

- 与当前项目现状最接近
- 不依赖 `supervisord`
- 便于在干净服务器上快速落地

### 8.2 可选增强方案

如后续需要更强的守护能力，可以增加以下可选模式：

- systemd 用户服务
- systemd 系统服务

但这些模式不作为第一阶段必需能力。

## 9. 环境安装与验证原则

本方案保留现有环境锁定文件思路，但对新服务器首次部署增加两个额外要求。

### 9.1 系统依赖要求

若导入链依赖系统动态库，例如 `cv2` 需要 `libGL.so.1`，部署工具必须在首次
引导阶段显式检查并安装缺失系统库，而不是把问题推迟到环境验证阶段。

典型系统依赖包括：

- `libgl1`
- `libglib2.0-0`

### 9.2 污染环境处理

如果训练环境或转换环境存在但验证失败，则后续实现建议采用“重建环境”而不是
“在旧环境上叠加补包”的策略。该策略对干净服务器首次部署影响较小，但对后续
维护很重要。

## 10. 状态文件与判定逻辑

本方案仍然需要 `deploy_state.json` 与 `init_state.json`，只是路径从 `/root`
目录迁移到用户目录。

### 10.1 部署状态文件路径

部署状态文件固定为：

```text
/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data/deploy_state.json
```

### 10.2 状态文件职责

部署状态文件仍然用于：

- 判定是否是首次部署
- 记录三环境布局版本
- 记录 base 是否瘦身完成
- 记录环境快照文件名
- 记录版本锁状态

### 10.3 与旧方案的差异

旧方案的判定依赖 `/root` 下的固定目录与状态文件；新方案则改为依赖用户目录
下的固定目录与状态文件。判定规则本身不变，只是固定根发生变化。

## 11. 与现有代码的兼容边界

本方案不是全量推翻，而是把“固定根”从 `/root` 迁移到可配置业务根目录。

### 11.1 需要改造的模块

后续实现至少会影响以下代码区域：

- `deploy_tool/deploy_manager.py`
- `deploy_tool/deploy_gui.py`
- `deploy_tool/deploy_config.json`
- `config/app_config.yaml`
- `app/config.py`
- 依赖固定路径的后端模块，例如训练、转换、系统检查与初始化修复模块

### 11.2 不需要推翻的设计

以下设计可以保留：

- 固定三环境职责划分
- 锁定依赖文件
- 部署状态文件
- 修复任务进度模型
- 前端进度展示与日志下载

## 12. 验收标准

本方案实施完成后，必须满足以下验收标准：

1. 部署工具可以使用 `ubuntu` 用户登录新服务器完成首次部署
2. 部署工具首次部署时可以自动安装 Miniforge 到用户目录
3. Web、训练、转换三环境都位于 `/home/ubuntu/cloud-training-runtime`
   根目录下
4. 后续部署不扫描候选路径，只使用配置生成的固定路径
5. 新服务器不开放 root 登录时，仍可完成完整部署
6. Web 服务默认可以通过 `nohup` 启动并被部署工具验证
7. 状态文件、日志目录、数据目录都位于统一业务根目录下
8. 原有固定三环境调用逻辑仍然成立

## 13. 下一步

如果你认可本设计，下一步实现建议分两阶段推进。

1. 先写实施计划，把“用户目录固定根”拆成部署工具改造、配置层改造、后端路
   径改造三个任务组。
2. 再按计划落代码，并优先打通新干净服务器的首次部署闭环。
