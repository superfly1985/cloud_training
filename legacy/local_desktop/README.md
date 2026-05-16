# 旧本地版说明

这个目录保存旧本地版桌面工具。它已经从仓库根目录迁移到
`legacy/local_desktop/`，但仍然保留可运行和可打包能力，方便你继续查旧
逻辑、做兼容修复或重新发布桌面版。

## 目录内容

这个目录包含旧本地版运行所需的核心文件：

- `main.py`：桌面版入口
- `src/`：旧本地版模块代码
- `cloud_training_config.json`：本地配置文件
- `requirements.txt`：旧本地版依赖
- `setup_env.ps1`：依赖安装脚本
- `cloud_training.spec`：PyInstaller 打包配置
- `assets/`：打包时需要带上的资源文件

## 运行

如果你要直接运行旧本地版，在仓库根目录执行：

```bash
python legacy/local_desktop/main.py
```

如果你已经进入当前目录，也可以执行：

```bash
python main.py
```

## 安装依赖

这个目录自带 `setup_env.ps1`，会基于脚本所在目录创建 `.venv` 并安装依赖。

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\legacy\local_desktop\setup_env.ps1
```

如果要安装 CUDA 版 PyTorch，可使用：

```powershell
powershell -ExecutionPolicy Bypass -File .\legacy\local_desktop\setup_env.ps1 -GPU
```

## 打包

当前打包方式仍然沿用原规则：使用 PyInstaller 的 `onedir` 模式。

在仓库根目录执行：

```bash
python -m PyInstaller legacy/local_desktop/cloud_training.spec
```

当前 `cloud_training.spec` 已经改成按 `spec` 文件自身位置解析 `main.py` 和
`assets/`，所以从仓库根目录调用也能正常工作。

## 发布规则

旧本地版发布时继续遵循以下约定：

- 使用 PyInstaller `onedir` 模式
- 发布目录使用 `release/`
- 文件夹命名遵循 `云端训练<版本号>`

版本号格式仍按仓库约定使用 `vX.N.M`。

## 说明

这个目录是遗留桌面版，不再是当前主产品。当前主产品仍然是
`MetaQA_CloudTraining/` 下的 Web 版。
