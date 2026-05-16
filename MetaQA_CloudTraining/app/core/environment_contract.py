import os


def _runtime_root() -> str:
    return os.path.join(os.path.expanduser("~"), "cloud-training-runtime").replace("\\", "/")


RUNTIME_ROOT = _runtime_root()
FIXED_BASE_PYTHON = os.path.join(RUNTIME_ROOT, "miniforge3", "bin", "python").replace("\\", "/")
FIXED_TRAINING_PYTHON = os.path.join(
    RUNTIME_ROOT, "miniforge3", "envs", "cloud-training", "bin", "python"
).replace("\\", "/")
FIXED_CONVERSION_PYTHON = os.path.join(
    RUNTIME_ROOT, "miniforge3", "envs", "cloud-conversion", "bin", "python"
).replace("\\", "/")
FIXED_CONDA = os.path.join(RUNTIME_ROOT, "miniforge3", "bin", "conda").replace("\\", "/")

RUNTIME_ENV_REQUIREMENTS = {
    "web": "deploy_tool/requirements-web.txt",
    "training": "deploy_tool/requirements-training.txt",
    "conversion": "deploy_tool/requirements-conversion.txt",
}

TRAINING_IMPORT_CHECK_SNIPPET = "import torch, ultralytics, onnx; print(torch.__version__)"
CONVERSION_IMPORT_CHECK_SNIPPET = (
    "from ultralytics import YOLO; import tensorflow as tf; import numpy; "
    "from PIL import Image; import onnx2tf; print('ok')"
)
CONVERSION_GATE_SNIPPET = CONVERSION_IMPORT_CHECK_SNIPPET
ENV_ISOLATION_CHECK_SNIPPET = (
    "import importlib.util; "
    "print(int(importlib.util.find_spec('tensorflow') is not None)); "
    "print(int(importlib.util.find_spec('onnx2tf') is not None))"
)

ALIGNED_ENV_CHECK_NAMES = [
    "训练环境",
    "转换环境",
    "PyTorch",
    "Ultralytics",
    "ONNX",
    "TensorFlow",
    "onnx2tf",
    "转换门禁",
    "环境隔离",
]

RUNTIME_REPAIR_STEPS = [
    "检查固定路径",
    "检查训练环境",
    "检查转换环境",
    "创建缺失环境",
    "同步训练依赖",
    "同步转换依赖",
    "验证训练环境",
    "验证转换环境",
    "重新汇总检查结果",
]
