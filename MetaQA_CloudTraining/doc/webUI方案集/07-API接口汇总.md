# API 接口汇总

---

## 1. 接口总览

| 模块 | 前缀 | 说明 |
|------|------|------|
| 系统初始化 | `/api/v1/init` | 环境检查、自动修复 |
| 数据集管理 | `/api/v1/datasets` | 数据集CRUD、上传、删除 |
| 训练任务 | `/api/v1/training` | 训练启动、停止、监控 |
| 产物包管理 | `/api/v1/packages` | 产物包列表、下载 |
| 系统信息 | `/api/v1/system` | GPU、磁盘、配置 |

---

## 2. 系统初始化接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/init/status` | GET | 获取初始化状态 |
| `/api/v1/init/check` | POST | 手动触发检查 |
| `/api/v1/init/fix` | POST | 自动修复问题 |
| `/api/v1/init/progress` | GET | 获取修复进度 |

### 2.1 获取初始化状态

**请求**: `GET /api/v1/init/status`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "ready",
    "checks": [
      {
        "name": "Python环境",
        "status": "pass",
        "message": "Python 3.10.12 已安装",
        "auto_fixable": false
      }
    ],
    "last_check": "2026-05-12T10:30:00Z"
  }
}
```

---

## 3. 数据集管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/upload/precheck` | POST | 上传前预检查 |
| `/api/v1/upload/init` | POST | 初始化上传 |
| `/api/v1/upload/chunk` | POST | 上传分片 |
| `/api/v1/upload/status/{upload_id}` | GET | 查询上传状态 |
| `/api/v1/upload/complete` | POST | 完成上传 |
| `/api/v1/datasets` | GET | 列出数据集 |
| `/api/v1/datasets` | POST | 创建数据集（本地扫描） |
| `/api/v1/datasets/{dataset_id}` | DELETE | 删除数据集 |
| `/api/v1/datasets/{dataset_id}/images` | DELETE | 删除图片 |
| `/api/v1/datasets/{dataset_id}/images` | GET | 列出图片（分页） |
| `/api/v1/datasets/{dataset_id}/images/{filename}/labels` | GET | 获取图片标注数据 |
| `/api/v1/datasets/{dataset_id}/images/{filename}/file` | GET | 获取图片文件 |
| `/api/v1/datasets/{dataset_id}/export` | GET | 导出数据集 |

### 3.1 上传前预检查

**请求**: `POST /api/v1/upload/precheck`

**请求体**:
```json
{
  "dataset_name": "焊点漏包",
  "mode": "create",
  "filenames": ["img001.jpg", "img002.jpg"],
  "total_size": 524288000
}
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "dataset_name": "焊点漏包",
    "has_duplicates": true,
    "duplicates": ["img001.jpg"],
    "new_files": ["img002.jpg"],
    "duplicate_count": 1,
    "new_count": 1,
    "skip_recommendation": "可跳过 1 个文件，节省约 5 MB"
  }
}
```

### 3.2 初始化上传

**请求**: `POST /api/v1/upload/init`

**请求体**:
```json
{
  "filename": "dataset.zip",
  "total_size": 524288000,
  "chunk_size": 10485760,
  "dataset_name": "焊点漏包"
}
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "upload_id": "upload_20260512_103000",
    "total_chunks": 50,
    "chunk_size": 10485760
  }
}
```

### 3.3 上传分片

**请求**: `POST /api/v1/upload/chunk`

**请求体** (multipart/form-data):
- `upload_id`: string
- `chunk_index`: int
- `chunk_data`: bytes

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "chunk_received": true,
    "received_chunks": [0, 1, 2],
    "missing_chunks": [3, 4, 5]
  }
}
```

### 3.4 完成上传

**请求**: `POST /api/v1/upload/complete`

**请求体**:
```json
{
  "upload_id": "upload_20260512_103000",
  "file_hash": "a1b2c3d4e5f6"
}
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "success": true,
    "dataset_id": "dataset_001",
    "extracted_path": "/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data/datasets/焊点漏包"
  }
}
```

### 3.5 列出数据集

**请求**: `GET /api/v1/datasets`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "datasets": [
      {
        "id": "dataset_001",
        "name": "焊点漏包",
        "description": "焊点漏包检测数据集",
        "image_count": 680,
        "label_count": 680,
        "classes": ["焊点漏包"],
        "last_modified": "2026-05-12T14:00:00Z"
      }
    ],
    "total": 1
  }
}
```

### 3.6 删除图片

**请求**: `DELETE /api/v1/datasets/{dataset_id}/images`

**请求体**:
```json
{
  "images": ["img001.jpg", "img002.jpg"]
}
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "deleted_images": 2,
    "deleted_labels": 2
  }
}
```

### 3.7 列出图片（分页）

**请求**: `GET /api/v1/datasets/{dataset_id}/images?page=1&page_size=20`

**查询参数**:

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `page` | int | 1 | 页码 |
| `page_size` | int | 20 | 每页数量（1-100） |

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "images": [
      {
        "filename": "img001.jpg",
        "size": 131072,
        "has_label": true
      }
    ],
    "total": 680,
    "page": 1,
    "page_size": 20
  }
}
```

### 3.8 获取图片标注数据

**请求**: `GET /api/v1/datasets/{dataset_id}/images/{filename}/labels`

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "labels": [
      {
        "class_id": 0,
        "class_name": "焊点漏包",
        "x_center": 0.512,
        "y_center": 0.345,
        "width": 0.089,
        "height": 0.067
      }
    ],
    "class_names": {
      "0": "焊点漏包"
    }
  }
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `labels` | array | 标注列表（YOLO 格式，归一化坐标） |
| `labels[].class_id` | int | 类别 ID |
| `labels[].class_name` | string | 类别名称 |
| `labels[].x_center` | float | 中心点 X（0-1） |
| `labels[].y_center` | float | 中心点 Y（0-1） |
| `labels[].width` | float | 宽度（0-1） |
| `labels[].height` | float | 高度（0-1） |
| `class_names` | object | 类别 ID→名称映射 |

### 3.9 获取图片文件

**请求**: `GET /api/v1/datasets/{dataset_id}/images/{filename}/file`

**响应**: 图片文件二进制流（`FileResponse`），Content-Type 根据 MIME 类型自动设置（如 `image/jpeg`、`image/png`）。

**错误响应**:
```json
{
  "code": 404,
  "message": "图片不存在",
  "data": null
}
```

### 3.10 系统状态接口（顶部状态栏）

**请求**: `GET /api/v1/system/status`

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "status": "ready",
    "statusText": "系统正常",
    "gpu_usage": 89,
    "disk_usage": 67,
    "running_tasks": 2
  }
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 系统状态（`ready` / `partial` / `failed`） |
| `statusText` | string | 状态文字（如“系统正常”“部分检查需处理”） |
| `gpu_usage` | int | GPU 利用率百分比 |
| `disk_usage` | int | 磁盘使用率百分比 |
| `running_tasks` | int | 运行中训练任务数 |
| `python_version` | string | 当前 Web Python 版本 |
| `cuda_version` | string | 当前检测到的 CUDA 版本 |
| `ultralytics_version` | string | 当前检测到的 ultralytics 版本 |

---

## 4. 训练任务接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/training/start` | POST | 启动训练 |
| `/api/v1/training/{session_id}/stop` | POST | 停止训练 |
| `/api/v1/training/{session_id}/status` | GET | 查询训练状态 |
| `/api/v1/training/{session_id}/logs` | GET | 实时日志（SSE） |
| `/api/v1/training/{session_id}/ws` | WebSocket | 实时日志（WebSocket） |
| `/api/v1/training/{session_id}/chart` | GET | 获取图表数据 |
| `/api/v1/training/history` | GET | 训练历史 |

### 4.1 启动训练

**请求**: `POST /api/v1/training/start`

**请求体**:
```json
{
  "dataset_id": "dataset_001",
  "version_id": "v001",
  "model_name": "焊点漏包_v001",
  "base_model": "yolov8n.pt",
  "epochs": 100,
  "imgsz": 640,
  "batch": 16,
  "lr0": 0.01,
  "val_ratio": 0.2,
  "split_seed": 42,
  "device": "0",
  "patience": 50,
  "resume": false,
  "resume_path": null
}
```

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "train_20260512_103000",
    "status": "started",
    "run_dir": "/home/ubuntu/cloud-training-runtime/MetaQA_CloudTraining/data/runs/train_20260512_103000",
    "websocket_url": "ws://localhost:8090/api/v1/training/train_20260512_103000/ws"
  }
}
```

### 4.2 查询训练状态

**请求**: `GET /api/v1/training/{session_id}/status`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "session_id": "train_20260512_103000",
    "status": "running",
    "current_epoch": 45,
    "total_epochs": 100,
    "current_loss": 0.234,
    "best_map": 0.9234,
    "elapsed_time": 3600,
    "estimated_remaining": 4400
  }
}
```

### 4.3 获取图表数据

**请求**: `GET /api/v1/training/{session_id}/chart`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "epochs": [1, 2, 3, 4, 5],
    "box_loss": [0.5, 0.4, 0.35, 0.3, 0.28],
    "cls_loss": [0.8, 0.6, 0.5, 0.45, 0.4],
    "dfl_loss": [0.3, 0.25, 0.22, 0.2, 0.18],
    "precision": [0.7, 0.75, 0.8, 0.85, 0.88],
    "recall": [0.65, 0.7, 0.75, 0.8, 0.85],
    "map50": [0.6, 0.65, 0.7, 0.75, 0.8],
    "map50_95": [0.4, 0.45, 0.5, 0.55, 0.6]
  }
}
```

---

## 5. 产物包管理接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/packages` | GET | 产物包列表 |
| `/api/v1/packages/{package_id}` | GET | 产物包详情 |
| `/api/v1/packages/{package_id}/download` | GET | 下载产物包 |
| `/api/v1/packages/{package_id}` | DELETE | 删除产物包 |
| `/api/v1/models/convert` | POST | 手动触发模型转换 |

### 5.1 产物包列表

**请求**: `GET /api/v1/packages`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "packages": [
      {
        "id": "pkg_001",
        "name": "焊点漏包_v001.zip",
        "dataset_name": "焊点漏包",
        "version": "v001",
        "size": "14.5 MB",
        "map": 0.9234,
        "training_time": "1h 45m",
        "created_at": "2026-05-11T10:30:00Z"
      }
    ],
    "total": 1
  }
}
```

### 5.2 产物包详情

**请求**: `GET /api/v1/packages/{package_id}`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "pkg_001",
    "name": "焊点漏包_v001.zip",
    "dataset_name": "焊点漏包",
    "version": "v001",
    "size": "14.5 MB",
    "map": 0.9234,
    "training_time": "1h 45m",
    "created_at": "2026-05-11T10:30:00Z",
    "files": {
      "best_pt": "best.pt",
      "best_onnx": "best.onnx",
      "best_fp16_tflite": "best_fp16.tflite",
      "best_fp32_tflite": "best_fp32.tflite",
      "results_csv": "results.csv",
      "dataset_yaml": "dataset.yaml"
    }
  }
}
```

---

## 6. 系统接口

当前版本的系统相关接口已经收敛到 `/api/v1/system/*` 这组路由，旧文档中的
`/system/info`、`/system/gpu`、`/system/disk`、`/system/config`
不再是当前实现。

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/system/status` | GET | 获取顶部状态栏与系统概览信息 |
| `/api/v1/system/checks` | GET | 获取最近一次环境检查任务 |
| `/api/v1/system/checks` | POST | 启动环境检查任务 |
| `/api/v1/system/fix` | POST | 启动自动修复任务 |
| `/api/v1/system/fix/current` | GET | 获取当前修复任务 |
| `/api/v1/system/fix/{task_id}` | GET | 查询指定修复任务状态 |
| `/api/v1/system/fix/{task_id}/log` | GET | 下载修复日志 |

### 6.1 环境检查任务

**请求**: `GET /api/v1/system/checks`

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "check-001",
    "status": "success",
    "statusText": "环境检查完成",
    "summary": {
      "status": "ready",
      "statusText": "系统正常"
    },
    "checks": [
      {
        "name": "训练环境",
        "status": "pass",
        "message": "训练环境可用",
        "auto_fixable": true,
        "blocking": true
      }
    ]
  }
}
```

### 6.2 自动修复任务

**请求**: `GET /api/v1/system/fix/{task_id}`

**响应**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "task_id": "fix-001",
    "status": "repairing",
    "statusText": "开始自动修复",
    "current_step": "同步训练依赖",
    "current_step_index": 5,
    "total_steps": 9,
    "percent": 55,
    "elapsed_seconds": 96,
    "steps": [
      { "name": "检查固定路径", "status": "success" },
      { "name": "检查训练环境", "status": "success" },
      { "name": "检查转换环境", "status": "success" },
      { "name": "创建缺失环境", "status": "success" },
      { "name": "同步训练依赖", "status": "running" }
    ],
    "logs": [
      "[10:30:00] 开始自动修复",
      "[10:30:12] [步骤] 同步训练依赖"
    ]
  }
}
```

---

## 7. 通用响应格式

### 7.1 成功响应

```json
{
  "code": 200,
  "message": "success",
  "data": { }
}
```

### 7.2 错误响应

```json
{
  "code": 400,
  "message": "参数错误",
  "detail": "dataset_id 不能为空"
}
```

### 7.3 状态码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源不存在 |
| 409 | 资源冲突 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用（初始化中）|
