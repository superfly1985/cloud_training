import os
import subprocess
import signal
import yaml

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.utils.helpers import gen_id, ensure_dir
from app.config import get_data_dir, get_config


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
    row = conn.execute("SELECT * FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return

    ds_id = row["dataset_id"]
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    data_yaml = os.path.join(ds_dir, "data.yaml")

    _generate_data_yaml(ds_id, ds_dir, data_yaml)

    run_dir = row["run_dir"]
    script_path = _generate_train_script(row, data_yaml, run_dir)

    log_path = os.path.join(run_dir, "train.log")
    log_f = open(log_path, "w", encoding="utf-8")

    proc = subprocess.Popen(
        ["python", "-u", script_path],
        stdout=log_f,
        stderr=subprocess.STDOUT,
        cwd=run_dir,
    )

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
        final_status = "completed" if proc.returncode == 0 else "failed"
        c = get_connection()
        c.execute(
            "UPDATE training_tasks SET status=?, completed_at=? WHERE id=?",
            (final_status, now_iso(), task_id),
        )
        c.commit()

    t = threading.Thread(target=_watch, daemon=True)
    t.start()


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
    script = f"""
import sys
sys.path.insert(0, '.')
from ultralytics import YOLO

model = YOLO('yolov8{task_row['model_size']}.pt')
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
        "created_at": r["created_at"],
        "started_at": r["started_at"],
        "completed_at": r["completed_at"],
    }
