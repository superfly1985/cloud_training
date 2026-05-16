import os
import csv

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger


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
        return {"epochs": [], "box_loss": [], "cls_loss": [], "dfl_loss": []}

    results_csv = _find_results_csv(row["run_dir"])
    if not results_csv:
        return {"epochs": [], "box_loss": [], "cls_loss": [], "dfl_loss": []}

    return _parse_csv(results_csv)


def refresh_task_metrics(task_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT run_dir, status, pid, completed_at, package_ready, package_id FROM training_tasks WHERE id=?",
        (task_id,),
    ).fetchone()
    if not row or not row["run_dir"]:
        return None

    results_csv = _find_results_csv(row["run_dir"])
    curve = _parse_csv(results_csv) if results_csv else {"epochs": [], "box_loss": [], "cls_loss": [], "dfl_loss": [], "map50": [], "map50_95": []}

    current_epoch = curve["epochs"][-1] if curve["epochs"] else 0
    box_loss = curve["box_loss"][-1] if curve["box_loss"] else 0
    cls_loss = curve["cls_loss"][-1] if curve["cls_loss"] else 0
    dfl_loss = curve["dfl_loss"][-1] if curve.get("dfl_loss") else 0
    map50 = curve["map50"][-1] if curve["map50"] else 0
    map50_95 = curve.get("map50_95", [0])[-1] if curve.get("map50_95") else 0

    status = _resolve_task_status(row)

    conn.execute(
        "UPDATE training_tasks SET current_epoch=?, box_loss=?, cls_loss=?, dfl_loss=?, map50=?, map50_95=?, status=? WHERE id=?",
        (current_epoch, box_loss, cls_loss, dfl_loss, map50, map50_95, status, task_id),
    )
    if status in ("completed", "failed", "stopped") and not row["completed_at"]:
        conn.execute(
            "UPDATE training_tasks SET completed_at=? WHERE id=?",
            (now_iso(), task_id),
        )
    conn.commit()

    return {
        "current_epoch": current_epoch,
        "box_loss": box_loss,
        "cls_loss": cls_loss,
        "dfl_loss": dfl_loss,
        "map50": map50,
        "map50_95": map50_95,
        "status": status,
        "package_ready": bool(row["package_ready"]) if "package_ready" in row.keys() else False,
        "package_id": row["package_id"] if "package_id" in row.keys() else "",
    }


def _resolve_task_status(task_row) -> str:
    current_status = task_row["status"] or "pending"
    if current_status in ("completed", "failed", "stopped", "converting", "packaging"):
        return current_status

    pid = int(task_row["pid"] or 0)
    if _is_process_alive(pid):
        return "running"

    run_dir = task_row["run_dir"]
    log_text = _read_train_log(run_dir).lower()
    has_best = bool(_find_weight_file(run_dir, "best.pt"))
    has_last = bool(_find_weight_file(run_dir, "last.pt"))

    if "epochs completed" in log_text or (has_best and has_last) or has_best:
        return "completed"

    if _has_failure_marker(log_text):
        return "failed"

    return "failed" if current_status in ("pending", "running") else current_status


def _ensure_task_package(task_id: str):
    try:
        from app.core.package_manager import ensure_package

        ensure_package(task_id)
    except Exception as e:
        get_logger().warning(f"自动创建产物包失败: {task_id}: {e}")


def _is_process_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_train_log(run_dir: str) -> str:
    log_path = os.path.join(run_dir, "train.log")
    if not os.path.exists(log_path):
        return ""
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


def _find_weight_file(run_dir: str, filename: str) -> str | None:
    direct = os.path.join(run_dir, "train", "weights", filename)
    if os.path.exists(direct):
        return direct
    for root, _, files in os.walk(run_dir):
        for file_name in files:
            if file_name == filename:
                return os.path.join(root, file_name)
    return None


def _has_failure_marker(log_text: str) -> bool:
    markers = ("traceback", "error", "exception", "failed", "runtimeerror")
    return any(marker in log_text for marker in markers)


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
    dfl_loss = []
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
                dl = _safe_float(row.get("train/dfl_loss", row.get("   train/dfl_loss", "")))
                m50 = _safe_float(row.get("metrics/mAP50(B)", row.get("metrics/mAP50(B)", "")))
                m5095 = _safe_float(row.get("metrics/mAP50-95(B)", row.get("metrics/mAP50-95(B)", "")))

                if epoch is not None:
                    epochs.append(int(epoch))
                    box_loss.append(bl if bl is not None else 0)
                    cls_loss.append(cl if cl is not None else 0)
                    dfl_loss.append(dl if dl is not None else 0)
                    map50.append(m50 if m50 is not None else 0)
                    map50_95.append(m5095 if m5095 is not None else 0)
    except Exception as e:
        get_logger().warning(f"解析 CSV 失败: {e}")

    return {
        "epochs": epochs,
        "box_loss": box_loss,
        "cls_loss": cls_loss,
        "dfl_loss": dfl_loss,
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
