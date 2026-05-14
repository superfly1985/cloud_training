import os
import shutil
import subprocess
import platform

from app.utils.logger import get_logger
from app.utils.helpers import format_bytes


def get_gpu_info() -> dict:
    logger = get_logger()
    info = {
        "gpu_usage": 0,
        "gpu_memory_used": 0,
        "gpu_memory_total": 0,
        "gpu_temp": 0,
        "gpu_name": "-",
    }
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,name",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 5:
                info["gpu_usage"] = int(parts[0].strip())
                info["gpu_memory_used"] = float(parts[1].strip()) / 1024
                info["gpu_memory_total"] = float(parts[2].strip()) / 1024
                info["gpu_temp"] = int(parts[3].strip())
                info["gpu_name"] = parts[4].strip()
    except Exception as e:
        logger.warning(f"获取GPU信息失败: {e}")
    return info


def get_disk_info() -> dict:
    try:
        usage = shutil.disk_usage("/")
        total = usage.total
        used = usage.used
        return {
            "disk_usage": round(used / total * 100),
            "disk_used_gb": round(used / (1024 ** 3), 1),
            "disk_total_gb": round(total / (1024 ** 3), 1),
        }
    except Exception:
        return {"disk_usage": 0, "disk_used_gb": 0, "disk_total_gb": 0}


def get_python_version() -> str:
    return platform.python_version()


def get_cuda_version() -> str:
    try:
        result = subprocess.run(["nvcc", "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "release" in line.lower():
                    return line.strip().split()[-1].replace(",", "")
    except Exception:
        pass
    return "-"


def get_ultralytics_version() -> str:
    try:
        import ultralytics
        return ultralytics.__version__
    except ImportError:
        return "-"


def get_system_status() -> dict:
    gpu = get_gpu_info()
    disk = get_disk_info()
    return {
        "status": "ready",
        "statusText": "系统正常",
        **gpu,
        **disk,
        "python_version": get_python_version(),
        "cuda_version": get_cuda_version(),
        "ultralytics_version": get_ultralytics_version(),
    }


def run_environment_checks() -> list:
    checks = []

    checks.append(_check_python())
    checks.append(_check_cuda_driver())
    checks.append(_check_gpu_available())
    checks.append(_check_ultralytics())
    checks.append(_check_onnx())
    checks.append(_check_tflite())
    checks.append(_check_disk_space())
    checks.append(_check_datasets_dir())

    return checks


def _check_python() -> dict:
    ver = get_python_version()
    ok = ver.startswith("3.")
    return {
        "name": "Python 环境",
        "status": "pass" if ok else "fail",
        "message": f"Python {ver} 已安装" if ok else f"Python 版本不兼容: {ver}",
        "auto_fixable": False,
    }


def _check_cuda_driver() -> dict:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return {"name": "CUDA 驱动", "status": "pass", "message": "CUDA 驱动已安装", "auto_fixable": False}
    except Exception:
        pass
    return {"name": "CUDA 驱动", "status": "fail", "message": "未检测到 CUDA 驱动", "auto_fixable": False}


def _check_gpu_available() -> dict:
    gpu = get_gpu_info()
    if gpu["gpu_name"] != "-":
        return {"name": "GPU 可用性", "status": "pass", "message": f"{gpu['gpu_name']} 可访问", "auto_fixable": False}
    return {"name": "GPU 可用性", "status": "fail", "message": "未检测到 GPU", "auto_fixable": False}


def _check_ultralytics() -> dict:
    ver = get_ultralytics_version()
    if ver != "-":
        return {"name": "Ultralytics", "status": "pass", "message": f"ultralytics {ver} 已安装", "auto_fixable": True}
    return {"name": "Ultralytics", "status": "fail", "message": "ultralytics 未安装", "auto_fixable": True}


def _check_onnx() -> dict:
    try:
        import onnx
        return {"name": "ONNX", "status": "pass", "message": f"onnx {onnx.__version__} 已安装", "auto_fixable": True}
    except ImportError:
        return {"name": "ONNX", "status": "fail", "message": "onnx 未安装", "auto_fixable": True}


def _check_tflite() -> dict:
    try:
        import tensorflow
        return {"name": "TFLite 依赖", "status": "pass", "message": f"tensorflow {tensorflow.__version__} 可用", "auto_fixable": True}
    except ImportError:
        return {"name": "TFLite 依赖", "status": "fail", "message": "tensorflow 未安装（转换环境）", "auto_fixable": True}


def _check_disk_space() -> dict:
    disk = get_disk_info()
    avail = disk["disk_total_gb"] - disk["disk_used_gb"]
    if avail > 50:
        return {"name": "磁盘空间", "status": "pass", "message": f"可用 {avail:.0f} GB", "auto_fixable": False}
    return {"name": "磁盘空间", "status": "fail", "message": f"剩余空间不足: {avail:.0f} GB", "auto_fixable": False}


def _check_datasets_dir() -> dict:
    from app.config import get_data_dir
    try:
        ds_path = get_data_dir("datasets_path")
        if os.path.isdir(ds_path):
            return {"name": "数据集目录", "status": "pass", "message": "已存在", "auto_fixable": True}
    except Exception:
        pass
    return {"name": "数据集目录", "status": "fail", "message": "目录不存在", "auto_fixable": True}
