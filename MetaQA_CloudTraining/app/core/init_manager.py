import os
import subprocess
import sys

from app.utils.logger import get_logger
from app.utils.helpers import ensure_dir
from app.config import get_config, get_data_dir


def run_init() -> dict:
    logger = get_logger()
    logger.info("开始系统初始化...")

    dirs = ("datasets_path", "runs_path", "pretrained_path", "temp_path", "logs_path", "db_path")
    for key in dirs:
        path = get_data_dir(key)
        logger.info(f"  目录 [{key}]: {path}")

    _init_conda_envs(logger)

    logger.info("系统初始化完成")
    return {"status": "ok", "message": "系统初始化完成"}


def _init_conda_envs(logger):
    cfg = get_config()
    convert_cmd = cfg.get("convert", {}).get("python_export_cmd", "")
    if convert_cmd and os.path.exists(convert_cmd):
        logger.info(f"转换环境已就绪: {convert_cmd}")
    else:
        logger.warning(f"转换环境未找到: {convert_cmd}")


def auto_fix() -> dict:
    logger = get_logger()
    logger.info("开始自动修复...")

    dirs = ("datasets_path", "runs_path", "pretrained_path", "temp_path", "logs_path", "db_path")
    for key in dirs:
        get_data_dir(key)

    python_exe = sys.executable

    _try_fix_ultralytics(logger, python_exe)
    _try_install_package(logger, python_exe, "onnx", "onnx", timeout=120)
    _try_install_package(logger, python_exe, "tensorflow", "tensorflow", timeout=600)

    logger.info("自动修复完成")
    return {"status": "ok", "message": "自动修复完成"}


def _try_install_package(logger, python_exe, import_name, pip_name, timeout=120):
    try:
        __import__(import_name)
        logger.info(f"  {import_name} 已安装")
        return
    except ImportError:
        pass

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
    try:
        import ultralytics
        logger.info("  ultralytics 已可用")
        return
    except ImportError as e:
        err_text = str(e)

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

        try:
            import ultralytics
            logger.info("  ultralytics 现在可用")
            return
        except ImportError:
            pass

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

    try:
        import ultralytics
        logger.info("  ultralytics 安装后可用")
    except ImportError as e2:
        logger.warning(f"  ultralytics 仍不可用: {e2}")
