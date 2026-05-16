import os
import subprocess
import signal
import shutil
import sys
import yaml

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.utils.helpers import gen_id, ensure_dir
from app.config import get_data_dir, get_config
from app.core.system_manager import FIXED_TRAINING_PYTHON


def list_tasks() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM training_tasks ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        result.append(_row_to_dict(r))
    return result


def get_task(task_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def create_task(config: dict) -> dict:
    conn = get_connection()
    ds_id = config["dataset_id"]

    ds_row = conn.execute("SELECT name FROM datasets WHERE id=? AND status='active'", (ds_id,)).fetchone()
    if not ds_row:
        raise ValueError(f"数据集不存在: {ds_id}")
    ds_name = ds_row["name"]

    existing = conn.execute("SELECT COUNT(*) FROM training_tasks WHERE dataset_id=?", (ds_id,)).fetchone()[0]
    version = f"v{str(existing + 1).zfill(3)}"

    task_id = f"task-{gen_id()}"
    now = now_iso()

    cfg = get_config()
    train_cfg = cfg.get("training", {})

    run_dir = os.path.join(get_data_dir("runs_path"), task_id)
    ensure_dir(run_dir)

    conn.execute(
        """INSERT INTO training_tasks
        (id, dataset_id, dataset_name, version, model_size, input_size, epochs,
         current_epoch, batch_size, learning_rate, device, status, pid, run_dir,
         created_at, started_at, completed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            task_id, ds_id, ds_name, version,
            config.get("model_size", train_cfg.get("default_model_size", "n")),
            config.get("input_size", train_cfg.get("default_imgsz", 640)),
            config.get("epochs", train_cfg.get("default_epochs", 100)),
            0,
            config.get("batch_size", train_cfg.get("default_batch", 16)),
            config.get("learning_rate", train_cfg.get("default_lr0", 0.01)),
            config.get("device", "cuda:0"),
            "pending", 0, run_dir, now, "", "",
        ),
    )
    conn.commit()

    _start_training(task_id)

    return get_task(task_id)


def stop_task(task_id: str) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT pid, status FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row or row["status"] != "running":
        return False

    pid = row["pid"]
    if pid and pid > 0:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    now = now_iso()
    conn.execute(
        "UPDATE training_tasks SET status='stopped', completed_at=? WHERE id=?",
        (now, task_id),
    )
    conn.commit()
    return True


def _start_training(task_id: str):
    conn = get_connection()
    logger = get_logger()
    row = conn.execute("SELECT * FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return

    ds_id = row["dataset_id"]
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    data_yaml = os.path.join(ds_dir, "data.yaml")

    _generate_data_yaml(ds_id, ds_dir, data_yaml)

    run_dir = row["run_dir"]
    run_data_yaml = os.path.join(run_dir, "data.yaml")
    effective_data_yaml = data_yaml
    if os.path.exists(data_yaml):
        shutil.copy2(data_yaml, run_data_yaml)
        effective_data_yaml = run_data_yaml
    script_path = _generate_train_script(row, effective_data_yaml, run_dir)

    log_path = os.path.join(run_dir, "train.log")
    log_f = open(log_path, "w", encoding="utf-8")
    python_cmd = _get_training_python_cmd()

    try:
        proc = subprocess.Popen(
            [python_cmd, "-u", script_path],
            stdout=log_f,
            stderr=subprocess.STDOUT,
            cwd=run_dir,
        )
    except Exception as e:
        log_f.write(f"训练启动失败: {e}\n")
        log_f.flush()
        log_f.close()
        conn.execute(
            "UPDATE training_tasks SET status='failed', pid=0, completed_at=? WHERE id=?",
            (now_iso(), task_id),
        )
        conn.commit()
        logger.exception(f"启动训练任务失败: {task_id}")
        return

    now = now_iso()
    conn.execute(
        "UPDATE training_tasks SET status='running', pid=?, started_at=? WHERE id=?",
        (proc.pid, now, task_id),
    )
    conn.commit()

    import threading

    def _watch():
        proc.wait()
        log_f.close()
        _finalize_task_after_training(task_id, proc.returncode)

    t = threading.Thread(target=_watch, daemon=True)
    t.start()


def _get_training_python_cmd() -> str:
    cfg = get_config()
    return cfg.get("training", {}).get("python_cmd") or FIXED_TRAINING_PYTHON


def _generate_data_yaml(ds_id: str, ds_dir: str, output_path: str):
    conn = get_connection()
    row = conn.execute("SELECT split_ratio FROM datasets WHERE id=?", (ds_id,)).fetchone()
    split_ratio = row["split_ratio"] if row else 0.8

    data = {
        "path": ds_dir,
        "train": "images/train",
        "val": "images/val",
        "names": {},
    }

    img_dir = os.path.join(ds_dir, "images")
    lbl_dir = os.path.join(ds_dir, "labels")

    train_img_dir = os.path.join(img_dir, "train")
    val_img_dir = os.path.join(img_dir, "val")
    train_lbl_dir = os.path.join(lbl_dir, "train")
    val_lbl_dir = os.path.join(lbl_dir, "val")
    for d in (train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir):
        ensure_dir(d)

    import random
    cfg = get_config()
    seed = cfg.get("training", {}).get("default_split_seed", 42)
    random.seed(seed)

    images = [f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f))]
    random.shuffle(images)
    split_idx = int(len(images) * split_ratio)

    import shutil
    for i, fname in enumerate(images):
        base = os.path.splitext(fname)[0]
        src_img = os.path.join(img_dir, fname)
        src_lbl = os.path.join(lbl_dir, base + ".txt")

        if i < split_idx:
            dst_img_dir = train_img_dir
            dst_lbl_dir = train_lbl_dir
        else:
            dst_img_dir = val_img_dir
            dst_lbl_dir = val_lbl_dir

        shutil.move(src_img, os.path.join(dst_img_dir, fname))
        if os.path.exists(src_lbl):
            shutil.move(src_lbl, os.path.join(dst_lbl_dir, base + ".txt"))

    classes = set()
    for lbl_root, _, lbl_files in os.walk(lbl_dir):
        for lf in lbl_files:
            if lf.endswith(".txt"):
                with open(os.path.join(lbl_root, lf), "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        parts = line.strip().split()
                        if parts:
                            classes.add(parts[0])

    for i, cls in enumerate(sorted(classes)):
        data["names"][i] = cls

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


def _generate_train_script(task_row, data_yaml: str, run_dir: str) -> str:
    model_ref = _resolve_pretrained_model(task_row["model_size"])
    script = f"""
import sys
sys.path.insert(0, '.')
from ultralytics import YOLO

model = YOLO(r'{model_ref}')
results = model.train(
    data='{data_yaml}',
    epochs={task_row['epochs']},
    imgsz={task_row['input_size']},
    batch={task_row['batch_size']},
    lr0={task_row['learning_rate']},
    device='{task_row['device']}',
    project='{run_dir}',
    name='train',
    exist_ok=True,
    verbose=True,
)
"""
    script_path = os.path.join(run_dir, "run_train.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    return script_path


def _resolve_pretrained_model(model_size: str) -> str:
    filename = f"yolov8{model_size}.pt"
    pretrained_dir = get_data_dir("pretrained_path")
    model_path = os.path.join(pretrained_dir, filename)
    if os.path.exists(model_path):
        return os.path.abspath(model_path)
    return filename


def _finalize_task_after_training(task_id: str, returncode: int):
    conn = get_connection()
    logger = get_logger()

    if returncode != 0:
        conn.execute(
            "UPDATE training_tasks SET status='failed', pid=0, package_ready=0, package_id='', completed_at=? WHERE id=?",
            (now_iso(), task_id),
        )
        conn.commit()
        return

    conn.execute(
        "UPDATE training_tasks SET status='converting', pid=0, package_ready=0, package_id='', completed_at='' WHERE id=?",
        (task_id,),
    )
    conn.commit()

    try:
        from app.core.package_manager import ensure_package

        pkg = ensure_package(task_id)
        conn.execute(
            "UPDATE training_tasks SET status='completed', package_ready=1, package_id=?, completed_at=? WHERE id=?",
            (pkg["id"], now_iso(), task_id),
        )
        conn.commit()
    except Exception as e:
        logger.warning(f"训练完成后自动打包失败: {task_id}: {e}")
        conn.execute(
            "UPDATE training_tasks SET status='failed', package_ready=0, package_id='', completed_at=? WHERE id=?",
            (now_iso(), task_id),
        )
        conn.commit()


def _row_to_dict(r) -> dict:
    return {
        "id": r["id"],
        "dataset_name": r["dataset_name"],
        "dataset_id": r["dataset_id"],
        "version": r["version"],
        "model_size": r["model_size"],
        "input_size": r["input_size"],
        "epochs": r["epochs"],
        "current_epoch": r["current_epoch"],
        "batch_size": r["batch_size"],
        "learning_rate": r["learning_rate"],
        "device": r["device"],
        "status": r["status"],
        "map50": r["map50"],
        "map50_95": r["map50_95"],
        "box_loss": r["box_loss"],
        "cls_loss": r["cls_loss"],
        "dfl_loss": r["dfl_loss"] if "dfl_loss" in r.keys() else 0,
        "package_ready": bool(r["package_ready"]) if "package_ready" in r.keys() else False,
        "package_id": r["package_id"] if "package_id" in r.keys() else "",
        "created_at": r["created_at"],
        "started_at": r["started_at"],
        "completed_at": r["completed_at"],
    }
