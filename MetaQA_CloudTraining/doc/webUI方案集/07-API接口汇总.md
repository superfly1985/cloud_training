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
    "extracted_path": "/opt/cloud-training/data/datasets/焊点漏包"
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
    "run_dir": "/opt/cloud-training/data/runs/train/焊点漏包_v001",
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

## 6. 系统信息接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/v1/system/info` | GET | 系统信息 |
| `/api/v1/system/gpu` | GET | GPU状态 |
| `/api/v1/system/disk` | GET | 磁盘空间 |
| `/api/v1/system/config` | GET | 系统配置 |

### 6.1 GPU状态

**请求**: `GET /api/v1/system/gpu`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "gpu_count": 1,
    "gpus": [
      {
        "index": 0,
        "name": "NVIDIA Tesla T4",
        "memory_total": "15360 MB",
        "memory_used": "2 MB",
        "memory_free": "14926 MB",
        "utilization": "0%",
        "temperature": "37°C"
      }
    ]
  }
}
```

### 6.2 磁盘空间

**请求**: `GET /api/v1/system/disk`

**响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "total": "49 GB",
    "used": "21 GB",
    "free": "27 GB",
    "usage_percent": "44%"
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