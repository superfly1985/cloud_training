import os
import json
import shutil
import zipfile
import subprocess

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.utils.helpers import gen_id, ensure_dir, format_bytes
from app.config import get_data_dir, get_config


def list_packages() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM packages ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        result.append(_row_to_dict(r))
    return result


def get_package(pkg_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM packages WHERE id=?", (pkg_id,)).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def create_package(task_id: str) -> dict:
    conn = get_connection()
    task = conn.execute("SELECT * FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        raise ValueError(f"训练任务不存在: {task_id}")
    if task["status"] != "completed":
        raise ValueError(f"训练任务未完成: {task['status']}")

    pkg_id = f"pkg-{gen_id()}"
    now = now_iso()
    pkg_name = f"{task['dataset_name']}_{task['version']}.zip"

    run_dir = task["run_dir"]
    train_dir = os.path.join(run_dir, "train") if os.path.isdir(os.path.join(run_dir, "train")) else run_dir

    best_pt = _find_file(train_dir, "best.pt")
    best_onnx = _find_file(train_dir, "best.onnx")

    cfg = get_config()
    convert_cmd = cfg.get("convert", {}).get("python_export_cmd", "")
    tflite_format = cfg.get("convert", {}).get("tflite_format", "fp16")

    tflite_files = []
    if best_onnx and convert_cmd and os.path.exists(convert_cmd):
        tflite_files = _convert_tflite(best_onnx, convert_cmd, tflite_format, train_dir)

    results_csv = _find_file(train_dir, "results.csv")
    data_yaml = _find_file(train_dir, "data.yaml")

    pkg_dir = os.path.join(get_data_dir("temp_path"), f"pkg_{pkg_id}")
    ensure_dir(pkg_dir)

    files_meta = []
    for src, label in [
        (best_pt, "best.pt"),
        (best_onnx, "best.onnx"),
        (results_csv, "results.csv"),
        (data_yaml, "dataset.yaml"),
    ]:
        if src and os.path.exists(src):
            dst = os.path.join(pkg_dir, label)
            shutil.copy2(src, dst)
            files_meta.append({"name": label, "size": os.path.getsize(dst)})

    for tf in tflite_files:
        fname = os.path.basename(tf)
        dst = os.path.join(pkg_dir, fname)
        if tf != dst:
            shutil.copy2(tf, dst)
        files_meta.append({"name": fname, "size": os.path.getsize(dst)})

    info = {
        "task_id": task_id,
        "dataset_name": task["dataset_name"],
        "version": task["version"],
        "model_size": task["model_size"],
        "map50": task["map50"],
        "map50_95": task["map50_95"],
        "created_at": now,
    }
    info_path = os.path.join(pkg_dir, "info.json")
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    files_meta.append({"name": "info.json", "size": os.path.getsize(info_path)})

    pkg_path = os.path.join(get_data_dir("runs_path"), "packages", pkg_name)
    ensure_dir(os.path.dirname(pkg_path))
    with zipfile.ZipFile(pkg_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in os.listdir(pkg_dir):
            zf.write(os.path.join(pkg_dir, item), item)

    shutil.rmtree(pkg_dir, ignore_errors=True)

    pkg_size = os.path.getsize(pkg_path)
    training_time = _calc_training_time(task)

    conn.execute(
        "INSERT INTO packages (id, name, dataset_name, version, task_id, size, map_val, training_time, file_path, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pkg_id, pkg_name, task["dataset_name"], task["version"], task_id, pkg_size, task["map50"], training_time, pkg_path, "ready", now),
    )
    conn.commit()

    return get_package(pkg_id)


def delete_package(pkg_id: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM packages WHERE id=?", (pkg_id,)).fetchone()
    if not row:
        return False

    if row["file_path"] and os.path.exists(row["file_path"]):
        os.remove(row["file_path"])

    conn.execute("DELETE FROM packages WHERE id=?", (pkg_id,))
    conn.commit()
    return True


def download_package(pkg_id: str) -> str | None:
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM packages WHERE id=?", (pkg_id,)).fetchone()
    if not row or not row["file_path"]:
        return None
    if not os.path.exists(row["file_path"]):
        return None
    return row["file_path"]


def _find_file(directory: str, filename: str) -> str | None:
    direct = os.path.join(directory, filename)
    if os.path.exists(direct):
        return direct
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f == filename:
                return os.path.join(root, f)
    return None


def _convert_tflite(onnx_path: str, python_cmd: str, tflite_format: str, work_dir: str) -> list:
    logger = get_logger()
    results = []

    script = f"""
import sys
try:
    from ultralytics import YOLO
    model = YOLO('{onnx_path}')
    model.export(format='tflite', imgsz=640)
    print('TFLite export done')
except Exception as e:
    print(f'TFLite export failed: {{e}}', file=sys.stderr)
    sys.exit(1)
"""
    script_path = os.path.join(work_dir, "_convert_tflite.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    try:
        result = subprocess.run(
            [python_cmd, "-u", script_path],
            capture_output=True, text=True, timeout=600,
            cwd=work_dir,
        )
        if result.returncode == 0:
            for root, dirs, files in os.walk(work_dir):
                for f in files:
                    if f.endswith(".tflite"):
                        results.append(os.path.join(root, f))
    except Exception as e:
        logger.error(f"TFLite 转换失败: {e}")

    if os.path.exists(script_path):
        os.remove(script_path)

    return results


def _calc_training_time(task_row) -> str:
    started = task_row["started_at"]
    completed = task_row["completed_at"]
    if not started or not completed:
        return "-"
    try:
        from datetime import datetime
        s = datetime.fromisoformat(started)
        e = datetime.fromisoformat(completed)
        diff = e - s
        hours = diff.seconds // 3600
        mins = (diff.seconds % 3600) // 60
        return f"{hours}h {mins:02d}m"
    except Exception:
        return "-"


def _row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "dataset_name": r["dataset_name"],
        "version": r["version"],
        "size": r["size"],
        "map_val": r["map_val"],
        "training_time": r["training_time"],
        "created_at": r["created_at"],
        "files": [],
    }
