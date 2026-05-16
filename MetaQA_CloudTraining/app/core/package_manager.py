import os
import json
import shutil
import zipfile
import subprocess
import sqlite3

import yaml

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.utils.helpers import gen_id, ensure_dir
from app.config import get_data_dir, get_config
from app.core.system_manager import FIXED_CONVERSION_PYTHON, FIXED_TRAINING_PYTHON


CALIBRATION_SAMPLE_FILENAME = "calibration_image_sample_data_20x128x128x3_float32.npy"


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


def ensure_package(task_id: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM packages WHERE task_id=? ORDER BY created_at DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if row:
        pkg = get_package(row["id"])
        _sync_task_package_state(task_id, pkg["id"])
        return pkg
    try:
        return create_package(task_id)
    except sqlite3.IntegrityError:
        row = conn.execute(
            "SELECT id FROM packages WHERE task_id=? ORDER BY created_at DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if not row:
            raise
        pkg = get_package(row["id"])
        _sync_task_package_state(task_id, pkg["id"])
        return pkg


def create_package(task_id: str) -> dict:
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM packages WHERE task_id=? ORDER BY created_at DESC LIMIT 1",
        (task_id,),
    ).fetchone()
    if existing:
        pkg = get_package(existing["id"])
        _sync_task_package_state(task_id, pkg["id"])
        return pkg

    task = conn.execute("SELECT * FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        raise ValueError(f"训练任务不存在: {task_id}")
    if task["status"] not in ("completed", "converting", "packaging"):
        raise ValueError(f"训练任务未完成: {task['status']}")

    pkg_id = f"pkg-{gen_id()}"
    now = now_iso()
    pkg_name = f"{task['dataset_name']}_{task['version']}.zip"

    run_dir = task["run_dir"]
    train_dir = os.path.join(run_dir, "train") if os.path.isdir(os.path.join(run_dir, "train")) else run_dir

    best_pt = _find_file(train_dir, "best.pt")
    if not best_pt:
        raise ValueError("未找到 best.pt，无法创建产物包")

    cfg = get_config()
    train_cmd = cfg.get("training", {}).get("python_cmd") or FIXED_TRAINING_PYTHON
    convert_cmd = cfg.get("convert", {}).get("python_export_cmd") or FIXED_CONVERSION_PYTHON
    tflite_format = cfg.get("convert", {}).get("tflite_format", "fp16")

    conversion_errors = []
    data_yaml = _resolve_dataset_yaml(task, run_dir, train_dir)
    dataset_dir = _resolve_dataset_dir(task, data_yaml)
    best_onnx = _find_file(train_dir, "best.onnx")
    if not best_onnx:
        best_onnx = _export_onnx(best_pt, train_cmd, train_dir)
        if not best_onnx:
            conversion_errors.append(_build_env_error("ONNX 导出失败", train_cmd, "训练环境"))

    tflite_files = []
    if best_pt and data_yaml and os.path.exists(data_yaml):
        tflite_files = _convert_tflite(best_pt, convert_cmd, tflite_format, train_dir, data_yaml, int(task["input_size"]), dataset_dir)
    elif best_pt:
        conversion_errors.append("TFLite 导出失败（缺少 dataset.yaml）")
    if best_pt and not tflite_files:
        tflite_files = _collect_tflite_files(train_dir)
    if best_pt and not tflite_files:
        conversion_errors.append(_build_env_error("TFLite 导出失败", convert_cmd, "转换环境"))

    conversion_meta = _build_conversion_meta(best_onnx, tflite_files, conversion_errors)
    if conversion_meta["conversion_status"] != "complete":
        message = conversion_meta["conversion_errors"][0] if conversion_meta["conversion_errors"] else "TFLite 转换失败，未生成最终产物包"
        raise ValueError(message)

    conn.execute(
        "UPDATE training_tasks SET status='packaging' WHERE id=?",
        (task_id,),
    )
    conn.commit()

    results_csv = _find_file(train_dir, "results.csv")

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
        "dataset_version": task["version"],
        "model_size": task["model_size"],
        "epochs": task["epochs"],
        "imgsz": task["input_size"],
        "batch": task["batch_size"],
        "best_map": task["map50"],
        "map50": task["map50"],
        "map50_95": task["map50_95"],
        "box_loss": task["box_loss"] if "box_loss" in task.keys() else None,
        "cls_loss": task["cls_loss"] if "cls_loss" in task.keys() else None,
        "dfl_loss": task["dfl_loss"] if "dfl_loss" in task.keys() else None,
        "training_time": _calc_training_time(task),
        "created_at": now,
        "conversion_status": conversion_meta["conversion_status"],
        "conversion_items": conversion_meta["conversion_items"],
        "conversion_errors": conversion_meta["conversion_errors"],
        "files": files_meta,
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
    _sync_task_package_state(task_id, pkg_id, now, conn=conn)
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
    if not directory or not os.path.isdir(directory):
        return None
    direct = os.path.join(directory, filename)
    if os.path.exists(direct):
        return direct
    for root, dirs, files in os.walk(directory):
        for f in files:
            if f == filename:
                return os.path.join(root, f)
    return None


def _resolve_dataset_yaml(task_row, run_dir: str, train_dir: str) -> str | None:
    for directory, filename in (
        (train_dir, "data.yaml"),
        (train_dir, "dataset.yaml"),
        (run_dir, "data.yaml"),
        (run_dir, "dataset.yaml"),
    ):
        path = _find_file(directory, filename)
        if path and os.path.exists(path):
            return path

    dataset_id = task_row["dataset_id"] if task_row and "dataset_id" in task_row.keys() else None
    if not dataset_id:
        return None
    dataset_dir = os.path.join(get_data_dir("datasets_path"), dataset_id)
    for filename in ("data.yaml", "dataset.yaml"):
        path = _find_file(dataset_dir, filename)
        if path and os.path.exists(path):
            return path
    return None


def _resolve_dataset_dir(task_row, dataset_yaml: str | None) -> str | None:
    if dataset_yaml and os.path.exists(dataset_yaml):
        try:
            with open(dataset_yaml, "r", encoding="utf-8") as f:
                parsed = yaml.safe_load(f) or {}
            yaml_path = parsed.get("path")
            if yaml_path and os.path.isdir(yaml_path):
                return yaml_path
        except Exception:
            pass

    dataset_id = task_row["dataset_id"] if task_row and "dataset_id" in task_row.keys() else None
    if not dataset_id:
        return None
    dataset_dir = os.path.join(get_data_dir("datasets_path"), dataset_id)
    return dataset_dir if os.path.isdir(dataset_dir) else None


def _list_conversion_sample_images(dataset_dir: str) -> list[str]:
    if not dataset_dir or not os.path.isdir(dataset_dir):
        return []
    image_names = []
    for rel_dir in (os.path.join("images", "val"), os.path.join("images", "train")):
        image_dir = os.path.join(dataset_dir, rel_dir)
        if not os.path.isdir(image_dir):
            continue
        image_names = [
            os.path.join(image_dir, name)
            for name in sorted(os.listdir(image_dir))
            if name.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp"))
        ]
        if image_names:
            break
    return image_names[:20]


def _build_conversion_sample(dataset_dir: str, sample_size: int, work_dir: str, filename: str = "_onnx2tf_input_sample.npy") -> str | None:
    import numpy as np
    from PIL import Image

    image_paths = _list_conversion_sample_images(dataset_dir)
    if not image_paths:
        return None
    tensors = []
    for image_path in image_paths:
        with Image.open(image_path) as image:
            rgb = image.convert("RGB").resize((sample_size, sample_size))
            tensors.append(np.asarray(rgb, dtype=np.float32))
    if not tensors:
        return None
    batch = np.stack(tensors, axis=0).astype(np.float32)
    sample_path = os.path.join(work_dir, filename)
    np.save(sample_path, batch)
    return sample_path


def _convert_tflite(best_pt: str, python_cmd: str, tflite_format: str, work_dir: str, dataset_yaml: str, imgsz: int, dataset_dir: str | None = None) -> list:
    logger = get_logger()
    results = []
    saved_model_dir = os.path.splitext(best_pt)[0] + "_saved_model"
    if not best_pt or not os.path.exists(best_pt):
        return results
    if not python_cmd or not os.path.exists(python_cmd):
        return results
    if not dataset_yaml or not os.path.exists(dataset_yaml):
        return results

    script = f"""
import glob
import json
import os
import shutil
import sys
try:
    os.environ['YOLO_AUTOINSTALL'] = '0'
    os.environ['ULTRALYTICS_AUTOINSTALL'] = '0'
    from ultralytics import YOLO

    best_pt = {json.dumps(best_pt)}
    dataset_yaml = {json.dumps(dataset_yaml)}
    requested_format = {json.dumps(tflite_format)}
    work_dir = {json.dumps(work_dir)}
    imgsz = {int(imgsz)}
    saved_model_dir = os.path.splitext(best_pt)[0] + "_saved_model"

    if not os.path.isfile(best_pt):
        raise FileNotFoundError(f'best.pt 不存在: {{best_pt}}')
    if not os.path.isfile(dataset_yaml):
        raise FileNotFoundError(f'dataset.yaml 不存在: {{dataset_yaml}}')

    if os.path.isdir(saved_model_dir):
        shutil.rmtree(saved_model_dir, ignore_errors=True)

    model = YOLO(best_pt)
    model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=True, nms=True, data=dataset_yaml)
    model.export(format='tflite', imgsz=imgsz, batch=1, int8=False, half=False, nms=True, data=dataset_yaml)

    stem = os.path.splitext(os.path.basename(best_pt))[0]
    fp32_src = ''
    fp16_src = ''
    for fp in sorted(glob.glob(os.path.join(saved_model_dir, '*.tflite'))):
        low = os.path.basename(fp).lower()
        if 'float16' in low and not fp16_src:
            fp16_src = fp
        elif not fp32_src:
            fp32_src = fp
    fp32_dst = os.path.join(work_dir, f'{{stem}}_fp32.tflite')
    fp16_dst = os.path.join(work_dir, f'{{stem}}_fp16.tflite')

    outputs = []
    if os.path.isfile(fp32_src):
        shutil.copy2(fp32_src, fp32_dst)
        outputs.append(fp32_dst)
    if os.path.isfile(fp16_src):
        shutil.copy2(fp16_src, fp16_dst)
        outputs.append(fp16_dst)

    print(json.dumps({{
        'dataset_yaml': dataset_yaml,
        'requested_format': requested_format,
        'outputs': outputs,
    }}, ensure_ascii=False))
except Exception as e:
    print(f'TFLite export failed: {{e}}', file=sys.stderr)
    sys.exit(1)
finally:
    pass
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
            results = _collect_generated_tflite_outputs(work_dir, saved_model_dir, "best")
        else:
            logger.error(f"TFLite 转换失败: {result.stderr or result.stdout}")
    except Exception as e:
        logger.error(f"TFLite 转换失败: {e}")

    if os.path.exists(script_path):
        os.remove(script_path)

    if results:
        return results

    yolo_bin = os.path.join(os.path.dirname(python_cmd), "yolo")
    export_env = _build_ultralytics_export_env()
    module_cmd = [
        python_cmd,
        yolo_bin,
        "export",
        f"model={best_pt}",
        "format=tflite",
        f"imgsz={int(imgsz)}",
        "int8=False",
        "nms=True",
        f"data={dataset_yaml}",
    ]
    ok_module, out_module = _run_shell_command(module_cmd, timeout=600, cwd=work_dir, env=export_env)
    if ok_module:
        results = _collect_generated_tflite_outputs(work_dir, saved_model_dir, "best")
        if results:
            return results
    elif out_module:
        logger.error(f"TFLite 模块回退失败: {out_module}")

    cli_cmd = [
        yolo_bin,
        "export",
        f"model={best_pt}",
        "format=tflite",
        f"imgsz={int(imgsz)}",
        "int8=False",
        "nms=True",
        f"data={dataset_yaml}",
    ]
    ok_cli, out_cli = _run_shell_command(cli_cmd, timeout=600, cwd=work_dir, env=export_env)
    if ok_cli:
        results = _collect_generated_tflite_outputs(work_dir, saved_model_dir, "best")
        if results:
            return results
    elif out_cli:
        logger.error(f"TFLite CLI 回退失败: {out_cli}")

    return results


def _export_onnx(best_pt: str, python_cmd: str, work_dir: str) -> str | None:
    logger = get_logger()
    if not best_pt or not os.path.exists(best_pt):
        return None
    if not python_cmd or not os.path.exists(python_cmd):
        return None

    script = f"""
import sys
try:
    from ultralytics import YOLO
    model = YOLO({json.dumps(best_pt)})
    model.export(format='onnx', imgsz=640)
    print('ONNX export done')
except Exception as e:
    print(f'ONNX export failed: {{e}}', file=sys.stderr)
    sys.exit(1)
"""
    script_path = os.path.join(work_dir, "_export_onnx.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)

    try:
        result = subprocess.run(
            [python_cmd, "-u", script_path],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=work_dir,
        )
        if result.returncode == 0:
            return _find_file(work_dir, "best.onnx")
        logger.error(f"ONNX 转换失败: {result.stderr or result.stdout}")
    except Exception as e:
        logger.error(f"ONNX 转换失败: {e}")
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
    return None


def _collect_tflite_files(work_dir: str) -> list:
    results = []
    for root, dirs, files in os.walk(work_dir):
        for f in files:
            if f.endswith(".tflite"):
                results.append(os.path.join(root, f))
    return results


def _build_ultralytics_export_env() -> dict[str, str]:
    env = os.environ.copy()
    env["YOLO_AUTOINSTALL"] = "0"
    env["ULTRALYTICS_AUTOINSTALL"] = "0"
    return env


def _run_shell_command(command, timeout: int = 3600, cwd: str | None = None, env: dict[str, str] | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            shell=isinstance(command, str),
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
        )
    except Exception as e:
        return False, str(e)
    output = (result.stdout or "").strip() or (result.stderr or "").strip()
    return result.returncode == 0, output


def _collect_generated_tflite_outputs(work_dir: str, saved_model_dir: str, stem: str) -> list[str]:
    fp32_dst = os.path.join(work_dir, f"{stem}_fp32.tflite")
    fp16_dst = os.path.join(work_dir, f"{stem}_fp16.tflite")
    normalized = []

    if os.path.isfile(fp32_dst):
        normalized.append(fp32_dst)
    if os.path.isfile(fp16_dst):
        normalized.append(fp16_dst)
    if normalized:
        return normalized

    fp32_src = ""
    fp16_src = ""
    if os.path.isdir(saved_model_dir):
        for fp in sorted(_collect_tflite_files(saved_model_dir)):
            low = os.path.basename(fp).lower()
            if "float16" in low and not fp16_src:
                fp16_src = fp
            elif not fp32_src:
                fp32_src = fp

    if fp32_src and not os.path.isfile(fp32_dst):
        shutil.copy2(fp32_src, fp32_dst)
    if fp16_src and not os.path.isfile(fp16_dst):
        shutil.copy2(fp16_src, fp16_dst)

    normalized = []
    if os.path.isfile(fp32_dst):
        normalized.append(fp32_dst)
    if os.path.isfile(fp16_dst):
        normalized.append(fp16_dst)
    return normalized


def _build_conversion_meta(best_onnx: str | None, tflite_files: list, errors: list) -> dict:
    items = {
        "onnx": "ready" if best_onnx and os.path.exists(best_onnx) else "missing",
        "tflite_fp16": "missing",
        "tflite_fp32": "missing",
    }
    for path in tflite_files:
        name = os.path.basename(path).lower()
        if "fp16" in name:
            items["tflite_fp16"] = "ready"
        elif "fp32" in name:
            items["tflite_fp32"] = "ready"
        else:
            if items["tflite_fp16"] == "missing":
                items["tflite_fp16"] = "ready"
            elif items["tflite_fp32"] == "missing":
                items["tflite_fp32"] = "ready"

    success_count = sum(1 for value in items.values() if value == "ready")
    if success_count == 0:
        status = "not_converted"
    elif success_count == len(items):
        status = "complete"
    else:
        status = "partial"

    return {
        "conversion_status": status,
        "conversion_items": items,
        "conversion_errors": errors,
    }


def _build_env_error(message: str, python_cmd: str, env_label: str) -> str:
    if not python_cmd:
        return f"{message}（{env_label}未配置）"
    if not os.path.exists(python_cmd):
        return f"{message}（{env_label}缺失: {python_cmd}）"
    return message


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


def _sync_task_package_state(task_id: str, pkg_id: str, completed_at: str | None = None, conn=None):
    if not task_id or not pkg_id:
        return
    own_conn = conn is None
    conn = conn or get_connection()
    conn.execute(
        "UPDATE training_tasks SET status='completed', package_ready=1, package_id=?, completed_at=? WHERE id=?",
        (pkg_id, completed_at or now_iso(), task_id),
    )
    if own_conn:
        conn.commit()


def _row_to_dict(r) -> dict:
    info = _load_package_info(r["file_path"])
    return {
        "id": r["id"],
        "name": r["name"],
        "dataset_name": r["dataset_name"],
        "version": r["version"],
        "size": r["size"],
        "map_val": r["map_val"],
        "box_loss": info.get("box_loss"),
        "cls_loss": info.get("cls_loss"),
        "dfl_loss": info.get("dfl_loss"),
        "training_time": r["training_time"],
        "created_at": r["created_at"],
        "file_path": r["file_path"],
        "conversion_status": info.get("conversion_status", "not_converted"),
        "conversion_items": info.get("conversion_items", {}),
        "conversion_errors": info.get("conversion_errors", []),
        "files": info.get("files", []),
    }


def _load_package_info(file_path: str) -> dict:
    if not file_path or not os.path.exists(file_path):
        return {}
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            files = [
                {"name": item.filename, "size": item.file_size}
                for item in zf.infolist()
                if not item.is_dir()
            ]
            file_names = set(zf.namelist())
            if "info.json" in file_names:
                info = json.loads(zf.read("info.json").decode("utf-8"))
                info["files"] = files
                return info
            return {"files": files}
    except Exception as e:
        get_logger().warning(f"读取产物包元数据失败: {file_path}: {e}")
        return {}
