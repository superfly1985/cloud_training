import os
import shutil
import subprocess
import platform
import threading

from app.core.environment_contract import CONVERSION_GATE_SNIPPET, ENV_ISOLATION_CHECK_SNIPPET
from app.utils.logger import get_logger
from app.utils.helpers import format_bytes
from app.config import get_config, get_data_dir
from app.models.database import get_connection


def _default_runtime_root() -> str:
    return os.path.join(os.path.expanduser("~"), "cloud-training-runtime").replace("\\", "/")


def _default_base_python() -> str:
    return os.path.join(_default_runtime_root(), "miniforge3", "bin", "python").replace("\\", "/")


def _default_training_python() -> str:
    return os.path.join(_default_runtime_root(), "miniforge3", "envs", "cloud-training", "bin", "python").replace("\\", "/")


def _default_conversion_python() -> str:
    return os.path.join(_default_runtime_root(), "miniforge3", "envs", "cloud-conversion", "bin", "python").replace("\\", "/")


def _default_conda() -> str:
    return os.path.join(_default_runtime_root(), "miniforge3", "bin", "conda").replace("\\", "/")


FIXED_BASE_PYTHON = _default_base_python()
FIXED_TRAINING_PYTHON = _default_training_python()
FIXED_CONVERSION_PYTHON = _default_conversion_python()
FIXED_CONDA = _default_conda()

CHECK_ITEM_NAMES = [
    "Python 环境",
    "CUDA 驱动",
    "GPU 可用性",
    "训练环境",
    "转换环境",
    "PyTorch",
    "Ultralytics",
    "ONNX",
    "TensorFlow",
    "onnx2tf",
    "转换门禁",
    "环境隔离",
    "磁盘空间",
    "数据目录",
]

_CHECK_STATE = {
    "lock": threading.Lock(),
    "active_task": None,
    "task_counter": 0,
    "history": [],
    "last_result": None,
}


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
    python_cmd = _get_web_python_cmd()
    ok, out, _ = _run_python_snippet(python_cmd, "import platform; print(platform.python_version())")
    if ok and out:
        return out.strip()
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
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "cuda version:" in line.lower():
                    marker = "cuda version:"
                    text = line.lower()
                    start = text.index(marker) + len(marker)
                    return line[start:].strip().split()[0].replace(",", "")
    except Exception:
        pass
    return "-"


def get_ultralytics_version() -> str:
    try:
        import ultralytics
        return ultralytics.__version__
    except ImportError:
        pass

    python_cmd = _get_training_python_cmd()
    ok, out, _ = _run_python_snippet(python_cmd, "import ultralytics; print(ultralytics.__version__)")
    if ok and out:
        return out.strip().splitlines()[-1]
    return "-"


def get_system_status() -> dict:
    snapshot = get_environment_check_task()
    summary = (snapshot or {}).get("summary") or {"status": "unknown", "statusText": "环境未检查"}
    gpu = get_gpu_info()
    disk = get_disk_info()
    return {
        "status": summary["status"],
        "statusText": summary["statusText"],
        **gpu,
        **disk,
        "python_version": get_python_version(),
        "cuda_version": get_cuda_version(),
        "ultralytics_version": get_ultralytics_version(),
        "running_tasks": get_running_task_count(),
        "check_status": (snapshot or {}).get("status", "idle"),
        "check_status_text": (snapshot or {}).get("statusText", "未执行环境检查"),
        "check_task_id": (snapshot or {}).get("task_id", ""),
    }


def get_running_task_count() -> int:
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT COUNT(*) FROM training_tasks WHERE status IN ('pending', 'running', 'converting', 'packaging')"
        ).fetchone()
        return int(row[0] if row else 0)
    except Exception:
        return 0


def start_environment_check_task() -> dict:
    with _CHECK_STATE["lock"]:
        active_task = _CHECK_STATE.get("active_task")
        if active_task and active_task["status"] in ("queued", "checking"):
            return _task_view(active_task)

        _CHECK_STATE["task_counter"] += 1
        task_id = f"check-{_CHECK_STATE['task_counter']:03d}"
        task = {
            "task_id": task_id,
            "status": "queued",
            "statusText": "等待开始环境检查",
            "summary": None,
            "checks": [],
        }
        _CHECK_STATE["active_task"] = task

    worker = threading.Thread(target=_run_check_pipeline, args=(task,), daemon=True)
    worker.start()
    return _task_view(task)


def get_environment_check_task(task_id: str | None = None) -> dict | None:
    with _CHECK_STATE["lock"]:
        active_task = _CHECK_STATE.get("active_task")
        if task_id:
            if active_task and active_task.get("task_id") == task_id:
                return _task_view(active_task)
            for item in reversed(_CHECK_STATE["history"]):
                if item.get("task_id") == task_id:
                    return _task_view(item)
            last_result = _CHECK_STATE.get("last_result")
            if last_result and last_result.get("task_id") == task_id:
                return _task_view(last_result)
            return None
        if active_task:
            return _task_view(active_task)
        if _CHECK_STATE.get("last_result"):
            return _task_view(_CHECK_STATE["last_result"])
        if _CHECK_STATE["history"]:
            return _task_view(_CHECK_STATE["history"][-1])
        return {
            "task_id": "",
            "status": "idle",
            "statusText": "未执行环境检查",
            "summary": {"status": "unknown", "statusText": "环境未检查"},
            "checks": [],
        }


def store_environment_check_result(task_id: str, status: str, status_text: str, summary: dict, checks: list):
    payload = {
        "task_id": task_id,
        "status": status,
        "statusText": status_text,
        "summary": dict(summary or {"status": "unknown", "statusText": "环境未检查"}),
        "checks": [dict(item) for item in (checks or [])],
    }
    with _CHECK_STATE["lock"]:
        _CHECK_STATE["last_result"] = payload
    return payload


def _run_check_pipeline(task: dict):
    logger = get_logger()
    task["status"] = "checking"
    task["statusText"] = "环境检查中"
    try:
        checks = run_environment_checks()
        summary = get_environment_summary(checks)
        task["checks"] = checks
        task["summary"] = summary
        task["status"] = "success"
        task["statusText"] = "环境检查完成"
        store_environment_check_result(task["task_id"], "success", task["statusText"], summary, checks)
    except Exception as exc:
        logger.exception("环境检查失败")
        summary = {"status": "failed", "statusText": f"环境检查失败：{exc}"}
        task["checks"] = []
        task["summary"] = summary
        task["status"] = "failed"
        task["statusText"] = "环境检查失败"
        store_environment_check_result(task["task_id"], "failed", task["statusText"], summary, [])
    finally:
        with _CHECK_STATE["lock"]:
            _CHECK_STATE["history"].append(_task_view(task))
            _CHECK_STATE["history"] = _CHECK_STATE["history"][-10:]
            if _CHECK_STATE.get("active_task") is task:
                _CHECK_STATE["active_task"] = None


def _task_view(task: dict) -> dict:
    return {
        "task_id": task.get("task_id", ""),
        "status": task.get("status", "idle"),
        "statusText": task.get("statusText", ""),
        "summary": dict(task.get("summary") or {"status": "unknown", "statusText": "环境未检查"}),
        "checks": [dict(item) for item in task.get("checks", [])],
    }


def run_environment_checks() -> list:
    checks = []

    checks.append(_check_python())
    checks.append(_check_cuda_driver())
    checks.append(_check_gpu_available())
    checks.append(_check_training_env())
    checks.append(_check_convert_env())
    checks.append(_check_torch())
    checks.append(_check_ultralytics())
    checks.append(_check_onnx())
    checks.append(_check_tflite())
    checks.append(_check_onnx2tf())
    checks.append(_check_conversion_gate())
    checks.append(_check_env_isolation())
    checks.append(_check_disk_space())
    checks.append(_check_datasets_dir())

    return checks


def get_environment_summary(checks: list) -> dict:
    blocking_failures = [item for item in checks if item["status"] == "fail" and item.get("blocking", True)]
    degraded = [item for item in checks if item["status"] in ("fail", "warning")]

    if blocking_failures:
        names = "、".join(item["name"] for item in blocking_failures[:3])
        more = " 等" if len(blocking_failures) > 3 else ""
        return {"status": "failed", "statusText": f"阻断项异常：{names}{more}"}

    if degraded:
        names = "、".join(item["name"] for item in degraded[:3])
        more = " 等" if len(degraded) > 3 else ""
        return {"status": "partial", "statusText": f"部分检查需处理：{names}{more}"}

    return {"status": "ready", "statusText": "系统正常"}


def _check_python() -> dict:
    ver = get_python_version()
    ok = ver.startswith("3.")
    return {
        "name": "Python 环境",
        "status": "pass" if ok else "fail",
        "message": f"Python {ver} 已安装" if ok else f"Python 版本不兼容: {ver}",
        "auto_fixable": False,
        "blocking": True,
    }


def _check_cuda_driver() -> dict:
    try:
        result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=5)
        if result.returncode == 0:
            return {"name": "CUDA 驱动", "status": "pass", "message": "CUDA 驱动已安装", "auto_fixable": False, "blocking": True}
    except Exception:
        pass
    return {"name": "CUDA 驱动", "status": "fail", "message": "未检测到 CUDA 驱动", "auto_fixable": False, "blocking": True}


def _check_gpu_available() -> dict:
    gpu = get_gpu_info()
    if gpu["gpu_name"] != "-":
        return {"name": "GPU 可用性", "status": "pass", "message": f"{gpu['gpu_name']} 可访问", "auto_fixable": False, "blocking": True}
    return {"name": "GPU 可用性", "status": "fail", "message": "未检测到 GPU", "auto_fixable": False, "blocking": True}


def _check_training_env() -> dict:
    python_cmd = _get_training_python_cmd()
    if _python_exists(python_cmd):
        return {"name": "训练环境", "status": "pass", "message": f"训练环境可用: {python_cmd}", "auto_fixable": True, "blocking": True}
    return {"name": "训练环境", "status": "fail", "message": f"训练环境缺失: {python_cmd}", "auto_fixable": True, "blocking": True}


def _check_convert_env() -> dict:
    python_cmd = _get_convert_python_cmd()
    if _python_exists(python_cmd):
        return {"name": "转换环境", "status": "pass", "message": f"转换环境可用: {python_cmd}", "auto_fixable": True, "blocking": True}
    return {"name": "转换环境", "status": "fail", "message": f"转换环境缺失: {python_cmd}", "auto_fixable": True, "blocking": True}


def _check_torch() -> dict:
    python_cmd = _get_training_python_cmd()
    ok, out, err = _run_python_snippet(
        python_cmd,
        "import torch; print(torch.__version__); print('cuda=' + str(torch.cuda.is_available()))",
    )
    if not ok:
        return {"name": "PyTorch", "status": "fail", "message": _format_probe_error("PyTorch 不可用", err, python_cmd), "auto_fixable": True, "blocking": True}
    lines = out.splitlines()
    cuda_ready = any(line.strip().lower() == "cuda=true" for line in lines)
    if not cuda_ready:
        return {"name": "PyTorch", "status": "fail", "message": "torch 已安装但 CUDA 不可用", "auto_fixable": True, "blocking": True}
    version = lines[0].strip() if lines else "-"
    return {"name": "PyTorch", "status": "pass", "message": f"torch {version} 已安装且 CUDA 可用", "auto_fixable": True, "blocking": True}


def _check_ultralytics() -> dict:
    python_cmd = _get_training_python_cmd()
    ok, out, err = _run_python_snippet(python_cmd, "import ultralytics; print(ultralytics.__version__)")
    if ok:
        return {"name": "Ultralytics", "status": "pass", "message": f"ultralytics {out or '-'} 已安装", "auto_fixable": True, "blocking": True}
    return {"name": "Ultralytics", "status": "fail", "message": _format_probe_error("ultralytics 未安装", err, python_cmd), "auto_fixable": True, "blocking": True}


def _check_onnx() -> dict:
    python_cmd = _get_training_python_cmd()
    ok, out, err = _run_python_snippet(python_cmd, "import onnx; print(onnx.__version__)")
    if ok:
        return {"name": "ONNX", "status": "pass", "message": f"onnx {out or '-'} 已安装", "auto_fixable": True, "blocking": True}
    return {"name": "ONNX", "status": "fail", "message": _format_probe_error("onnx 未安装", err, python_cmd), "auto_fixable": True, "blocking": True}


def _check_tflite() -> dict:
    python_cmd = _get_convert_python_cmd()
    ok, out, err = _run_python_snippet(python_cmd, "import tensorflow as tf; print(tf.__version__)")
    if ok:
        return {"name": "TensorFlow", "status": "pass", "message": f"tensorflow {out or '-'} 可用", "auto_fixable": True, "blocking": True}
    return {"name": "TensorFlow", "status": "fail", "message": _format_probe_error("tensorflow 未安装（转换环境）", err, python_cmd), "auto_fixable": True, "blocking": True}


def _check_onnx2tf() -> dict:
    python_cmd = _get_convert_python_cmd()
    ok, out, err = _run_python_snippet(python_cmd, "import onnx2tf; print(getattr(onnx2tf, '__version__', 'ok'))")
    if ok:
        return {"name": "onnx2tf", "status": "pass", "message": f"onnx2tf {out or 'ok'} 可用", "auto_fixable": True, "blocking": True}
    return {"name": "onnx2tf", "status": "fail", "message": _format_probe_error("onnx2tf 未安装（转换环境）", err, python_cmd), "auto_fixable": True, "blocking": True}


def _check_conversion_gate() -> dict:
    python_cmd = _get_convert_python_cmd()
    ok, _, err = _run_python_snippet(python_cmd, CONVERSION_GATE_SNIPPET, timeout=60)
    if ok:
        return {"name": "转换门禁", "status": "pass", "message": "YOLO + TensorFlow + onnx2tf 均可导入", "auto_fixable": False, "blocking": True}
    return {"name": "转换门禁", "status": "fail", "message": _format_probe_error("转换环境导入链路不完整", err, python_cmd), "auto_fixable": False, "blocking": True}


def _check_env_isolation() -> dict:
    python_cmd = _get_training_python_cmd()
    ok, out, err = _run_python_snippet(
        python_cmd,
        ENV_ISOLATION_CHECK_SNIPPET,
    )
    if not ok:
        return {"name": "环境隔离", "status": "fail", "message": _format_probe_error("无法检查训练环境隔离状态", err, python_cmd), "auto_fixable": True, "blocking": True}
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    if len(lines) >= 2 and (lines[0] == "1" or lines[1] == "1"):
        return {"name": "环境隔离", "status": "fail", "message": "训练环境中检测到 tensorflow 或 onnx2tf", "auto_fixable": True, "blocking": True}
    return {"name": "环境隔离", "status": "pass", "message": "训练环境未检测到 tensorflow/onnx2tf", "auto_fixable": True, "blocking": True}


def _check_disk_space() -> dict:
    disk = get_disk_info()
    avail = disk["disk_total_gb"] - disk["disk_used_gb"]
    if avail > 8:
        return {"name": "磁盘空间", "status": "pass", "message": f"可用 {avail:.0f} GB", "auto_fixable": False, "blocking": False}
    return {"name": "磁盘空间", "status": "warning", "message": f"剩余空间不足: {avail:.0f} GB (建议至少 8 GB)", "auto_fixable": False, "blocking": False}


def _check_datasets_dir() -> dict:
    try:
        ds_path = get_data_dir("datasets_path")
        if os.path.isdir(ds_path):
            return {"name": "数据目录", "status": "pass", "message": f"已存在: {ds_path}", "auto_fixable": True, "blocking": False}
    except Exception:
        pass
    return {"name": "数据目录", "status": "warning", "message": "目录不存在", "auto_fixable": True, "blocking": False}


def _get_training_python_cmd() -> str:
    cfg = get_config()
    return cfg.get("training", {}).get("python_cmd") or FIXED_TRAINING_PYTHON


def _get_convert_python_cmd() -> str:
    cfg = get_config()
    return cfg.get("convert", {}).get("python_export_cmd") or FIXED_CONVERSION_PYTHON


def _get_web_python_cmd() -> str:
    cfg = get_config()
    return cfg.get("server", {}).get("python_cmd") or FIXED_BASE_PYTHON


def _python_exists(python_cmd: str) -> bool:
    return bool(python_cmd and os.path.exists(python_cmd))


def _run_python_snippet(python_cmd: str, code: str, timeout: int = 30) -> tuple[bool, str, str]:
    if not _python_exists(python_cmd):
        return False, "", f"Python 不存在: {python_cmd}"
    try:
        result = subprocess.run(
            [python_cmd, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip(), (result.stderr or "").strip()
    except Exception as e:
        return False, "", str(e)


def _format_probe_error(prefix: str, err: str, python_cmd: str) -> str:
    detail = (err or "").splitlines()
    suffix = detail[-1][:160] if detail else f"Python 不存在: {python_cmd}"
    return f"{prefix}: {suffix}"
