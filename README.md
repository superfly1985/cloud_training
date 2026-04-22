# 云端训练管理平台

## 项目简介

基于YOLOv8的云端训练管理GUI工具，支持服务器配置、数据集管理、训练监控和模型下载等功能。

## 版本信息

- **当前版本**: v2.2.10
- **主要功能**: 云端训练、实时监控、模型管理、监控大屏、图像增强参数配置（含激活控制）（纯云端模式）

## 目录结构（已分层）

```text
.
├── cloud_training_gui.py                     # 主程序入口（统一入口）
├── cloud_training_config.json                # 服务器配置
├── cloud_training_gui.spec                   # PyInstaller 打包配置
├── requirements.txt                          # 当前运行依赖
├── README.md
│
├── configs/                                  # 运行配置分层
│   ├── preinstalled_pytorch/
│   └── docker_ubuntu2204/
│
├── deploy/                                   # 部署资产
│   └── docker_ubuntu2204/                    # Dockerfile/compose/lock 等
│
├── scripts/                                  # 环境脚本分层
│   ├── preinstalled_pytorch/
│   └── linux/
│
├── docs/
│   └── 开发文档/
│       ├── preinstalled_pytorch/
│       └── docker_ubuntu2204/
│
├── assets/                                   # 资源文件
└── changelog.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行程序

```bash
python cloud_training_gui.py
```

### 3. 打包发布

```bash
pyinstaller cloud_training_gui.spec
```

## 主要功能

- **服务器管理**: SSH连接配置、连接测试
- **数据集管理**: 本地检查、云端上传、差异对比
- **环境管理**: 云端环境检查、自动修复
- **训练控制**: 开始/停止训练、参数配置
- **实时监控**: GPU状态、训练进度、损失曲线
- **模型管理**: 训练结果查看、模型下载

## 使用说明

详细使用说明请参考 `docs/使用说明/` 目录下的文档。

## 开发文档

开发相关文档请参考 `docs/开发文档/` 目录。

### 路径重构说明

- 主入口不变：`cloud_training_gui.py`
- 通过服务器运行模式分流：`preinstalled_pytorch` 与 `docker_ubuntu2204`
- Ubuntu 22.04 Docker 相关文件统一放在 `deploy/docker_ubuntu2204/`

## 注意事项

1. 首次使用前请配置服务器连接信息
2. 训练前请确保云端环境已正确配置
3. 建议先执行"检查环境"和"修复环境"后再开始训练
