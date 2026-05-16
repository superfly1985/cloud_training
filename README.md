# 云端训练仓库说明

这个仓库现在同时包含两条产品线：

- `MetaQA_CloudTraining/`：当前主产品，Web 版云端训练管理平台
- `legacy/local_desktop/`：旧本地版桌面工具，保留为可运行、可打包的遗留版本

日常开发默认以 Web 版为主，只有在查旧逻辑、兼容旧流程或重新打包旧桌面版时，
才进入 `legacy/local_desktop/`。

## 当前结构

仓库根目录现在按职责分层：

```text
03.云端训练/
├── MetaQA_CloudTraining/       # 当前主产品：Web 版
├── legacy/
│   └── local_desktop/          # 旧本地版：可运行、可打包
├── test/
│   ├── probes/                 # 保留的排障/探针脚本
│   └── samples/                # 少量测试样本
├── README.md
└── changelog.md
```

## Web 版

`MetaQA_CloudTraining/` 是当前主工作区，包含：

- FastAPI 后端
- Vue CDN 前端
- 部署工具
- Web 版设计文档与实施计划

常用入口：

```bash
cd MetaQA_CloudTraining
python run.py
```

详细结构请看：

- `MetaQA_CloudTraining/doc/webUI方案集/01-目录结构.md`

## 旧本地版

旧本地版已经迁移到 `legacy/local_desktop/`，并继续保留运行与打包能力。

常用文件：

- `legacy/local_desktop/main.py`
- `legacy/local_desktop/src/`
- `legacy/local_desktop/cloud_training.spec`
- `legacy/local_desktop/cloud_training_config.json`
- `legacy/local_desktop/setup_env.ps1`

### 运行

```bash
python legacy/local_desktop/main.py
```

### 安装依赖

```powershell
powershell -ExecutionPolicy Bypass -File .\legacy\local_desktop\setup_env.ps1
```

### 打包

```bash
pyinstaller legacy/local_desktop/cloud_training.spec
```

发布规则仍保持原约定：

- 使用 PyInstaller `onedir` 模式
- 发布目录使用 `release/`
- 目录命名遵循 `云端训练<版本号>`

## test 目录

根目录 `test/` 只保留仍有价值的内容：

- `test/probes/`：复用型排障脚本
- `test/samples/`：少量样本文件

历史输出、缓存、大体积模型对比产物和一次性 json 结果已清理，不再长期堆放在
根目录。

## 开发建议

- Web 版开发优先进入 `MetaQA_CloudTraining/`
- 旧本地版改动优先控制在 `legacy/local_desktop/`
- 一次性脚本与临时文件继续放 `test/`，但不要把输出产物长期保留在仓库中
