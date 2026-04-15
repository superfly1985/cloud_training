# 云端训练管理平台

## 项目简介

基于YOLOv8的云端训练管理GUI工具，支持服务器配置、数据集管理、训练监控和模型下载等功能。

## 版本信息

- **当前版本**: v2.2.7
- **主要功能**: 云端训练、实时监控、模型管理、监控大屏（纯云端模式）

## 目录结构

```
.
├── cloud_training_gui.py      # 主程序入口
├── cloud_training_config.json # 配置文件
├── cloud_training_gui.spec    # PyInstaller打包配置
├── requirements.txt           # Python依赖
├── README.md                  # 项目说明
│
├── src/                       # 源代码模块（预留）
├── tools/                     # 工具脚本
│   ├── check_server_env.py    # 服务器环境检查
│   ├── export_model.py        # 模型导出
│   └── train_yolov8.py        # 本地训练脚本
│
├── test/                      # 测试相关
│   ├── logs/                  # 测试日志
│   ├── mock_dataset/          # 测试数据集
│   └── scripts/               # 测试脚本
│
├── docs/                      # 文档
│   ├── 使用说明/              # 用户使用文档
│   └── 开发文档/              # 开发相关文档
│
├── assets/                    # 资源文件
│   ├── yolov8n.pt            # 预训练模型
│   └── icons/                # 图标资源
│
└── release/                   # 发布文件
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

## 注意事项

1. 首次使用前请配置服务器连接信息
2. 训练前请确保云端环境已正确配置
3. 建议先执行"检查环境"和"修复环境"后再开始训练
