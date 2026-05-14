import os
import csv

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.config import get_data_dir


def get_training_log(task_id: str, tail: int = 200) -> str:
    conn = get_connection()
    row = conn.execute("SELECT run_dir FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row or not row["run_dir"]:
        return ""

    log_path = os.path.join(row["run_dir"], "train.log")
    if not os.path.exists(log_path):
        return ""

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        return "".join(lines[-tail:])
    except Exception:
        return ""


def get_loss_curve(task_id: str) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT run_dir FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row or not row["run_dir"]:
        return {"epochs": [], "box_loss": [], "cls_loss": [], "map50": []}

    results_csv = _find_results_csv(row["run_dir"])
    if not results_csv:
        return {"epochs": [], "box_loss": [], "cls_loss": [], "map50": []}

    return _parse_csv(results_csv)


def refresh_task_metrics(task_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT run_dir, status FROM training_tasks WHERE id=?", (task_id,)).fetchone()
    if not row or not row["run_dir"]:
        return None

    results_csv = _find_results_csv(row["run_dir"])
    if not results_csv:
        return None

    curve = _parse_csv(results_csv)
    if not curve["epochs"]:
        return None

    last_idx = len(curve["epochs"]) - 1
    current_epoch = curve["epochs"][-1]
    box_loss = curve["box_loss"][-1] if curve["box_loss"] else 0
    cls_loss = curve["cls_loss"][-1] if curve["cls_loss"] else 0
    map50 = curve["map50"][-1] if curve["map50"] else 0
    map50_95 = curve.get("map50_95", [0])[-1] if curve.get("map50_95") else 0

    conn.execute(
        "UPDATE training_tasks SET current_epoch=?, box_loss=?, cls_loss=?, map50=?, map50_95=? WHERE id=?",
        (current_epoch, box_loss, cls_loss, map50, map50_95, task_id),
    )
    conn.commit()

    return {
        "current_epoch": current_epoch,
        "box_loss": box_loss,
        "cls_loss": cls_loss,
        "map50": map50,
        "map50_95": map50_95,
    }


def _find_results_csv(run_dir: str) -> str | None:
    train_dir = os.path.join(run_dir, "train")
    if os.path.isdir(train_dir):
        csv_path = os.path.join(train_dir, "results.csv")
        if os.path.exists(csv_path):
            return csv_path

    for root, dirs, files in os.walk(run_dir):
        for f in files:
            if f == "results.csv":
                return os.path.join(root, f)
    return None


def _parse_csv(csv_path: str) -> dict:
    epochs = []
    box_loss = []
    cls_loss = []
    map50 = []
    map50_95 = []

    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            reader.fieldnames = [n.strip() for n in reader.fieldnames]

            for row in reader:
                epoch = _safe_float(row.get("epoch", row.get("                  epoch", "")))
                bl = _safe_float(row.get("train/box_loss", row.get("   train/box_loss", "")))
                cl = _safe_float(row.get("train/cls_loss", row.get("   train/cls_loss", "")))
                m50 = _safe_float(row.get("metrics/mAP50(B)", row.get("metrics/mAP50(B)", "")))
                m5095 = _safe_float(row.get("metrics/mAP50-95(B)", row.get("metrics/mAP50-95(B)", "")))

                if epoch is not None:
                    epochs.append(int(epoch))
                    box_loss.append(bl if bl is not None else 0)
                    cls_loss.append(cl if cl is not None else 0)
                    map50.append(m50 if m50 is not None else 0)
                    map50_95.append(m5095 if m5095 is not None else 0)
    except Exception as e:
        get_logger().warning(f"解析 CSV 失败: {e}")

    return {
        "epochs": epochs,
        "box_loss": box_loss,
        "cls_loss": cls_loss,
        "map50": map50,
        "map50_95": map50_95,
    }


def _safe_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return None
