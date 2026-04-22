# YOLO 预训练模型与依赖（预装 PyTorch 路线）

## 环境准备（推荐）
- 位置：`D:\OneDrive\24.Visual AI\training_scripts`
- 执行：右键“使用 PowerShell 运行”或在终端执行
```
powershell -ExecutionPolicy Bypass -File .\setup_env.ps1
```
- 作用：创建虚拟环境 `.venv` 并安装所需依赖（CPU 版 Torch；如需 GPU，请改用 CUDA 对应的版本）。

## 快速获取预训练模型
- 方式一（脚本）：
```
.\.venv\Scripts\python.exe .\scripts\preinstalled_pytorch\download_pretrained.py
```
- 方式二（CLI，自动下载）：
```
.\.venv\Scripts\python.exe -m pip install ultralytics
yolo export model=yolov8n.pt format=onnx  # 将自动下载 yolov8n.pt
```
- 下载后存放：`training_scripts\models\yolov8*.pt`

## 训练（示例）
```
.\.venv\Scripts\python.exe .\scripts\preinstalled_pytorch\train_yolov8.py `
  --model yolov8n.pt `
  --data D:\data\your_dataset.yaml `
  --epochs 100 --imgsz 640
```

## 导出（示例）
```
.\.venv\Scripts\python.exe .\scripts\preinstalled_pytorch\export_model.py --model runs\detect\train\weights\best.pt --format onnx
```

## 主要依赖
- Python 3.10+（建议）
- ultralytics（YOLOv8）
- torch / torchvision（默认 CPU 版；若需 GPU，请根据 CUDA 版本替换）
- opencv-python、numpy、matplotlib、PyYAML、onnx（导出可选）

## 注意事项
- 若需 GPU 加速，请将 `requirements.txt` 中的 `torch/torchvision` 改为与你的 CUDA 版本匹配的轮子。
- 首次运行会自动下载权重到 Ultralytics 缓存目录；脚本会复制到 `models/` 便于统一管理。
