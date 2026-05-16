import json
import os
import subprocess
import threading
import traceback
from datetime import datetime, timezone

from app.core.environment_contract import (
    CONVERSION_IMPORT_CHECK_SNIPPET,
    FIXED_BASE_PYTHON,
    FIXED_CONDA,
    FIXED_CONVERSION_PYTHON,
    FIXED_TRAINING_PYTHON,
    RUNTIME_ENV_REQUIREMENTS,
    RUNTIME_REPAIR_STEPS,
    TRAINING_IMPORT_CHECK_SNIPPET,
)
from app.utils.logger import get_logger
from app.config import get_config, get_data_dir, get_runtime_path
from app.core.system_manager import (
    get_environment_summary,
    run_environment_checks,
    store_environment_check_result,
)

REPAIR_STEPS = list(RUNTIME_REPAIR_STEPS)

_REPAIR_STATE = {
    "lock": threading.Lock(),
    "active_task": None,
    "task_counter": 0,
    "history": [],
}


def run_init() -> dict:
    logger = get_logger()
    logger.info("开始系统初始化...")

    dirs = ("datasets_path", "runs_path", "pretrained_path", "temp_path", "logs_path", "db_path")
    for key in dirs:
        path = get_data_dir(key)
        logger.info(f"  目录 [{key}]: {path}")

    checks = run_environment_checks()
    summary = get_environment_summary(checks)
    repair_task = get_auto_fix_task()

    logger.info("系统初始化完成")
    return {
        "status": summary["status"],
        "statusText": summary["statusText"],
        "checks": checks,
        "repairTask": repair_task,
    }


def _init_conda_envs(logger):
    cfg = get_config()
    training_cmd = cfg.get("training", {}).get("python_cmd") or FIXED_TRAINING_PYTHON
    convert_cmd = cfg.get("convert", {}).get("python_export_cmd") or FIXED_CONVERSION_PYTHON
    logger.info(f"训练环境目标: {training_cmd}")
    if convert_cmd and os.path.exists(convert_cmd):
        logger.info(f"转换环境已就绪: {convert_cmd}")
    else:
        logger.warning(f"转换环境未找到: {convert_cmd}")


def auto_fix() -> dict:
    return start_auto_fix_task()


def start_auto_fix_task() -> dict:
    with _REPAIR_STATE["lock"]:
        active_task = _REPAIR_STATE.get("active_task")
        if active_task and active_task["status"] in ("queued", "repairing"):
            return _task_view(active_task)

        _REPAIR_STATE["task_counter"] += 1
        task_id = f"fix-{_REPAIR_STATE['task_counter']:03d}"
        task = {
            "task_id": task_id,
            "status": "queued",
            "statusText": "等待执行",
            "current_step": "",
            "current_step_index": 0,
            "total_steps": len(REPAIR_STEPS),
            "percent": 0,
            "elapsed_seconds": 0,
            "started_at": _utc_now(),
            "ended_at": "",
            "steps": [{"name": name, "status": "pending"} for name in REPAIR_STEPS],
            "logs": [],
            "log_path": _repair_log_path(task_id),
            "summary": None,
        }
        _REPAIR_STATE["active_task"] = task

    worker = threading.Thread(target=_run_fix_pipeline, args=(task,), daemon=True)
    worker.start()
    return _task_view(task)


def get_auto_fix_task(task_id: str | None = None) -> dict | None:
    with _REPAIR_STATE["lock"]:
        active_task = _REPAIR_STATE.get("active_task")
        if task_id:
            if active_task and active_task["task_id"] == task_id:
                return _task_view(active_task)
            for item in reversed(_REPAIR_STATE["history"]):
                if item["task_id"] == task_id:
                    return _task_view(item)
            return None
        if active_task:
            return _task_view(active_task)
        if _REPAIR_STATE["history"]:
            return _task_view(_REPAIR_STATE["history"][-1])
        return None


def get_auto_fix_log_path(task_id: str | None = None) -> str | None:
    task = get_auto_fix_task(task_id)
    if not task:
        return None
    log_path = task.get("log_path") or ""
    if log_path and os.path.exists(log_path):
        return log_path
    return None


def _run_fix_pipeline(task: dict):
    logger = get_logger()
    start_ts = datetime.now()
    _set_task_status(task, "repairing", "开始自动修复")
    _append_task_log(task, "开始自动修复")

    dirs = ("datasets_path", "runs_path", "pretrained_path", "temp_path", "logs_path", "db_path")
    for key in dirs:
        get_data_dir(key)

    try:
        _execute_repair_step(task, 0, lambda: _check_fixed_paths())
        _execute_repair_step(task, 1, lambda: _inspect_env(FIXED_TRAINING_PYTHON, "训练环境"))
        _execute_repair_step(task, 2, lambda: _inspect_env(FIXED_CONVERSION_PYTHON, "转换环境"))
        _execute_repair_step(task, 3, lambda: _ensure_runtime_envs(task))
        _execute_repair_step(task, 4, lambda: _sync_runtime_requirements(task, "training"))
        _execute_repair_step(task, 5, lambda: _sync_runtime_requirements(task, "conversion"))
        _execute_repair_step(
            task,
            6,
            lambda: _verify_env_with_contract("训练环境", FIXED_TRAINING_PYTHON, TRAINING_IMPORT_CHECK_SNIPPET),
        )
        _execute_repair_step(
            task,
            7,
            lambda: _verify_env_with_contract("转换环境", FIXED_CONVERSION_PYTHON, CONVERSION_IMPORT_CHECK_SNIPPET),
        )
        _execute_repair_step(task, 8, lambda: _collect_runtime_summary(task))

        summary = task["summary"] or {"status": "ready", "statusText": "系统正常", "checks": []}
        _write_init_state(summary, task)
        _set_task_status(task, "success", summary["statusText"])
        _append_task_log(task, "自动修复完成")
        logger.info("自动修复完成")
    except Exception as exc:
        err_text = f"{type(exc).__name__}: {exc}"
        logger.error(f"自动修复失败: {err_text}")
        logger.error(traceback.format_exc())
        _append_task_log(task, f"自动修复失败: {err_text}")
        task["summary"] = {
            "status": "failed",
            "statusText": f"自动修复失败：{err_text}",
            "checks": run_environment_checks(),
        }
        store_environment_check_result(
            task["task_id"],
            "failed",
            "自动修复失败",
            {
                "status": task["summary"]["status"],
                "statusText": task["summary"]["statusText"],
            },
            task["summary"]["checks"],
        )
        _set_task_status(task, "failed", task["summary"]["statusText"])
    finally:
        task["elapsed_seconds"] = max(1, int((datetime.now() - start_ts).total_seconds()))
        task["ended_at"] = _utc_now()
        _archive_repair_log(task)
        with _REPAIR_STATE["lock"]:
            if _REPAIR_STATE.get("active_task") is task:
                _REPAIR_STATE["history"].append(task.copy())
                _REPAIR_STATE["history"] = _REPAIR_STATE["history"][-10:]
                _REPAIR_STATE["active_task"] = None


def _try_install_package(logger, python_exe, import_name, pip_name, timeout=120):
    if _can_import(python_exe, import_name):
        logger.info(f"  {import_name} 已安装: {python_exe}")
        return

    logger.info(f"尝试安装 {pip_name}...")
    try:
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", pip_name],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            logger.info(f"  {pip_name} 安装成功")
        else:
            logger.warning(f"  {pip_name} 安装返回 {result.returncode}: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        logger.error(f"安装 {pip_name} 超时")
    except Exception as e:
        logger.error(f"安装 {pip_name} 失败: {e}")


def _try_fix_ultralytics(logger, python_exe):
    if _can_import(python_exe, "ultralytics"):
        logger.info(f"  ultralytics 已可用: {python_exe}")
        return

    err_text = _probe_import_error(python_exe, "ultralytics")

    if "libGL" in err_text or "opencv" in err_text.lower() or "cv2" in err_text.lower():
        logger.info("检测到 opencv 系统依赖缺失 (libGL)，尝试安装 opencv-python-headless...")
        try:
            subprocess.run(
                [python_exe, "-m", "pip", "install", "opencv-python-headless"],
                capture_output=True, text=True, timeout=180,
            )
            logger.info("  opencv-python-headless 安装完成")
        except Exception as ex:
            logger.warning(f"  opencv-python-headless 安装失败: {ex}")

        if _can_import(python_exe, "ultralytics"):
            logger.info("  ultralytics 现在可用")
            return

    logger.info("尝试安装 ultralytics...")
    try:
        subprocess.run(
            [python_exe, "-m", "pip", "install", "ultralytics"],
            capture_output=True, text=True, timeout=300,
        )
    except Exception as ex:
        logger.error(f"安装 ultralytics 失败: {ex}")

    try:
        subprocess.run(
            [python_exe, "-m", "pip", "install", "opencv-python-headless"],
            capture_output=True, text=True, timeout=180,
        )
    except Exception:
        pass

    if _can_import(python_exe, "ultralytics"):
        logger.info("  ultralytics 安装后可用")
    else:
        logger.warning(f"  ultralytics 仍不可用: {_probe_import_error(python_exe, 'ultralytics')}")


def _try_remove_package(logger, python_exe, package_name, timeout=180):
    if not _can_import(python_exe, package_name):
        return
    logger.info(f"尝试移除 {package_name}...")
    try:
        result = subprocess.run(
            [python_exe, "-m", "pip", "uninstall", "-y", package_name],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            logger.info(f"  {package_name} 已移除")
        else:
            logger.warning(f"  {package_name} 移除返回 {result.returncode}: {result.stderr[:200]}")
    except Exception as e:
        logger.warning(f"移除 {package_name} 失败: {e}")


def _can_import(python_exe: str, module_name: str) -> bool:
    if not python_exe or not os.path.exists(python_exe):
        return False
    try:
        result = subprocess.run(
            [python_exe, "-c", f"import {module_name}"],
            capture_output=True, text=True, timeout=20,
        )
        return result.returncode == 0
    except Exception:
        return False


def _probe_import_error(python_exe: str, module_name: str) -> str:
    if not python_exe or not os.path.exists(python_exe):
        return f"python 不存在: {python_exe}"
    try:
        result = subprocess.run(
            [python_exe, "-c", f"import {module_name}"],
            capture_output=True, text=True, timeout=20,
        )
        return (result.stderr or result.stdout or "").strip()
    except Exception as e:
        return str(e)


def _execute_repair_step(task: dict, index: int, action):
    step = task["steps"][index]
    step["status"] = "running"
    task["current_step"] = step["name"]
    task["current_step_index"] = index + 1
    task["percent"] = int(index / max(1, task["total_steps"]) * 100)
    _append_task_log(task, f"[步骤] {step['name']}")
    action()
    step["status"] = "success"
    task["percent"] = int((index + 1) / max(1, task["total_steps"]) * 100)


def _check_fixed_paths():
    if not os.path.exists(FIXED_CONDA):
        raise FileNotFoundError(f"固定 conda 不存在: {FIXED_CONDA}")
    if not os.path.exists(FIXED_BASE_PYTHON):
        raise FileNotFoundError(f"固定 Web Python 不存在: {FIXED_BASE_PYTHON}")


def _inspect_env(python_cmd: str, label: str):
    if os.path.exists(python_cmd):
        return


def _ensure_runtime_envs(task: dict):
    if not os.path.exists(FIXED_TRAINING_PYTHON):
        _create_conda_env(task, "cloud-training")
    if not os.path.exists(FIXED_CONVERSION_PYTHON):
        _create_conda_env(task, "cloud-conversion")


def _sync_runtime_requirements(task: dict, env_name: str):
    python_cmd = FIXED_TRAINING_PYTHON if env_name == "training" else FIXED_CONVERSION_PYTHON
    requirements_rel = RUNTIME_ENV_REQUIREMENTS[env_name]
    _install_requirements(task, python_cmd, _get_lock_file(os.path.basename(requirements_rel)), timeout=2400)


def _verify_env_with_contract(label: str, python_cmd: str, snippet: str):
    task = {
        "logs": [],
        "log_path": "",
    }
    _run_checked_command(task, [python_cmd, "-c", snippet], timeout=90)


def _collect_runtime_summary(task: dict):
    checks = run_environment_checks()
    summary = get_environment_summary(checks)
    task["summary"] = {**summary, "checks": checks}
    store_environment_check_result(task["task_id"], "success", "自动修复完成", summary, checks)


def _install_training_packages(task: dict):
    _install_requirements(task, FIXED_TRAINING_PYTHON, _get_lock_file("requirements-training.txt"), timeout=2400)
    _try_remove_package(get_logger(), FIXED_TRAINING_PYTHON, "tensorflow", timeout=180)
    _try_remove_package(get_logger(), FIXED_TRAINING_PYTHON, "onnx2tf", timeout=180)


def _install_conversion_packages(task: dict):
    _install_requirements(task, FIXED_CONVERSION_PYTHON, _get_lock_file("requirements-conversion.txt"), timeout=2400)


def _verify_training_env(task: dict):
    _run_checked_command(
        task,
        [
            FIXED_TRAINING_PYTHON,
            "-c",
            "import torch, ultralytics, onnx; "
            "print(torch.__version__); "
            "print('cuda=' + str(torch.cuda.is_available())); "
            "print(ultralytics.__version__); "
            "print(onnx.__version__)",
        ],
        timeout=60,
    )


def _verify_conversion_env(task: dict):
    _run_checked_command(
        task,
        [
            FIXED_CONVERSION_PYTHON,
            "-c",
            "from ultralytics import YOLO; import tensorflow, onnx2tf, onnx; "
            "print('ok'); print(tensorflow.__version__)",
        ],
        timeout=90,
    )


def _clean_runtime_caches(task: dict):
    for python_cmd in (FIXED_TRAINING_PYTHON, FIXED_CONVERSION_PYTHON):
        if os.path.exists(python_cmd):
            _run_checked_command(task, [python_cmd, "-m", "pip", "cache", "purge"], timeout=300, allow_failure=True)
    _run_checked_command(task, [FIXED_CONDA, "clean", "-a", "-y"], timeout=600, allow_failure=True)


def _create_conda_env(task: dict, env_name: str):
    _append_task_log(task, f"创建环境: {env_name}")
    _run_checked_command(
        task,
        [FIXED_CONDA, "create", "-y", "-n", env_name, "python=3.10"],
        timeout=1800,
    )


def _install_requirements(task: dict, python_cmd: str, requirements_path: str, timeout: int):
    if not os.path.exists(python_cmd):
        raise FileNotFoundError(f"Python 不存在: {python_cmd}")
    if not os.path.exists(requirements_path):
        raise FileNotFoundError(f"依赖锁定文件不存在: {requirements_path}")
    _append_task_log(task, f"安装依赖: {os.path.basename(requirements_path)}")
    _run_checked_command(
        task,
        [python_cmd, "-m", "pip", "install", "-r", requirements_path],
        timeout=timeout,
    )


def _run_checked_command(task: dict, cmd: list[str], timeout: int, allow_failure: bool = False):
    _append_task_log(task, "$ " + " ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"命令超时: {' '.join(cmd)}") from exc

    output = (result.stdout or "").strip()
    error = (result.stderr or "").strip()
    if output:
        _append_task_log(task, output.splitlines()[-1][:400])
    if error:
        _append_task_log(task, error.splitlines()[-1][:400])

    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(f"命令失败({result.returncode}): {' '.join(cmd)}")


def _write_init_state(summary: dict, task: dict):
    state_path = get_runtime_path("init_state_path")
    payload = {
        "updated_at": _utc_now(),
        "status": summary["status"],
        "statusText": summary["statusText"],
        "last_task_id": task["task_id"],
    }
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _task_view(task: dict) -> dict:
    status = task.get("status", "queued")
    return {
        "task_id": task.get("task_id", ""),
        "status": status,
        "statusText": task.get("statusText") or ("修复进行中" if status in ("queued", "repairing") else ""),
        "current_step": task.get("current_step", ""),
        "current_step_index": task.get("current_step_index", 0),
        "total_steps": task.get("total_steps", 0),
        "percent": task.get("percent", 0),
        "elapsed_seconds": task.get("elapsed_seconds", 0),
        "started_at": task.get("started_at", ""),
        "ended_at": task.get("ended_at", ""),
        "steps": [dict(item) for item in task.get("steps", [])],
        "logs": list(task.get("logs", [])[-50:]),
        "log_path": task.get("log_path", ""),
        "summary": task.get("summary"),
    }


def _set_task_status(task: dict, status: str, text: str):
    task["status"] = status
    task["statusText"] = text


def _append_task_log(task: dict, message: str):
    stamp = datetime.now().strftime("[%H:%M:%S]")
    line = f"{stamp} {message}"
    task["logs"].append(line)
    task["logs"] = task["logs"][-400:]
    log_path = task.get("log_path")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def _repair_log_path(task_id: str) -> str:
    log_dir = get_data_dir("logs_path")
    return os.path.join(log_dir, f"init-fix-{task_id}.log")


def _archive_repair_log(task: dict):
    latest_path = os.path.join(get_data_dir("logs_path"), "init-fix.log")
    current_path = task.get("log_path")
    if current_path and os.path.exists(current_path):
        with open(current_path, "r", encoding="utf-8") as src, open(latest_path, "w", encoding="utf-8") as dst:
            dst.write(src.read())


def _get_lock_file(name: str) -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "deploy_tool", name)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
