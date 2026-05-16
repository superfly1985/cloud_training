import os
import json
import shutil
import zipfile
import yaml

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.utils.helpers import gen_id, safe_json_loads, safe_json_dumps, ensure_dir, format_bytes
from app.config import get_data_dir


def list_datasets() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM datasets WHERE status='active' ORDER BY created_at DESC").fetchall()
    result = []
    for r in rows:
        raw_classes = safe_json_loads(r["classes"])
        name_map = get_class_names(r["id"])
        if name_map:
            resolved = []
            for c in raw_classes:
                resolved.append({"id": str(c), "name": name_map.get(str(c), str(c))})
        else:
            resolved = [{"id": str(c), "name": str(c)} for c in raw_classes]
        result.append({
            "id": r["id"],
            "name": r["name"],
            "image_count": r["image_count"],
            "annotated_count": r["annotated_count"],
            "classes": resolved,
            "total_size": r["total_size"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return result


def get_dataset(ds_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM datasets WHERE id=?", (ds_id,)).fetchone()
    if not row:
        return None
    raw_classes = safe_json_loads(row["classes"])
    name_map = get_class_names(ds_id)
    if name_map:
        resolved = []
        for c in raw_classes:
            resolved.append({"id": str(c), "name": name_map.get(str(c), str(c))})
    else:
        resolved = [{"id": str(c), "name": str(c)} for c in raw_classes]
    return {
        "id": row["id"],
        "name": row["name"],
        "image_count": row["image_count"],
        "annotated_count": row["annotated_count"],
        "classes": resolved,
        "total_size": row["total_size"],
        "split_ratio": row["split_ratio"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_dataset(name: str, split_ratio: float = 0.8) -> dict:
    conn = get_connection()
    existing = conn.execute("SELECT id FROM datasets WHERE name=? AND status='active'", (name,)).fetchone()
    if existing:
        raise ValueError(f"数据集名称已存在: {name}")

    ds_id = f"ds-{gen_id()}"
    now = now_iso()
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    ensure_dir(ds_dir)
    for sub in ("images", "labels"):
        ensure_dir(os.path.join(ds_dir, sub))

    conn.execute(
        "INSERT INTO datasets (id, name, split_ratio, status, created_at, updated_at) VALUES (?,?,?,?,?,?)",
        (ds_id, name, split_ratio, "active", now, now),
    )
    conn.commit()
    return {"id": ds_id, "name": name, "created_at": now}


def delete_dataset(ds_id: str) -> bool:
    logger = get_logger()
    conn = get_connection()
    row = conn.execute("SELECT id FROM datasets WHERE id=? AND status='active'", (ds_id,)).fetchone()
    if not row:
        return False

    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    if os.path.isdir(ds_dir):
        try:
            shutil.rmtree(ds_dir)
        except OSError as exc:
            logger.error(f"删除数据集目录失败: {ds_dir}: {exc}")
            return False
    else:
        logger.warning(f"删除数据集时目录不存在: {ds_dir}")

    conn.execute("UPDATE datasets SET status='deleted', updated_at=? WHERE id=?", (now_iso(), ds_id))
    conn.execute("DELETE FROM images WHERE dataset_id=?", (ds_id,))
    conn.commit()
    return True


def list_images(ds_id: str, page: int = 1, page_size: int = 20) -> dict:
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM images WHERE dataset_id=?", (ds_id,)).fetchone()[0]
    offset = (page - 1) * page_size
    rows = conn.execute(
        "SELECT * FROM images WHERE dataset_id=? ORDER BY filename LIMIT ? OFFSET ?",
        (ds_id, page_size, offset),
    ).fetchall()

    images = []
    for r in rows:
        images.append({
            "id": r["id"],
            "filename": r["filename"],
            "thumbnail_url": f"/api/v1/datasets/{ds_id}/images/{r['filename']}/file",
            "size": r["size"],
            "width": r["width"],
            "height": r["height"],
            "annotated": bool(r["annotated"]),
            "split_type": r["split_type"],
        })

    return {
        "images": images,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def delete_images(ds_id: str, image_ids: list) -> int:
    conn = get_connection()
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    deleted = 0
    for img_id in image_ids:
        row = conn.execute("SELECT filename FROM images WHERE id=? AND dataset_id=?", (img_id, ds_id)).fetchone()
        if not row:
            continue
        fname = row["filename"]
        base = os.path.splitext(fname)[0]
        img_path = os.path.join(ds_dir, "images", fname)
        lbl_path = os.path.join(ds_dir, "labels", base + ".txt")
        if os.path.exists(img_path):
            os.remove(img_path)
        if os.path.exists(lbl_path):
            os.remove(lbl_path)
        conn.execute("DELETE FROM images WHERE id=?", (img_id,))
        deleted += 1

    _refresh_dataset_stats(ds_id)
    conn.commit()
    return deleted


def import_zip(ds_id: str, zip_path: str, skip_existing: bool = False) -> dict:
    logger = get_logger()
    conn = get_connection()
    ds = get_dataset(ds_id)
    if not ds:
        raise ValueError(f"数据集不存在: {ds_id}")

    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    img_dir = os.path.join(ds_dir, "images")
    lbl_dir = os.path.join(ds_dir, "labels")
    ensure_dir(img_dir)
    ensure_dir(lbl_dir)

    temp_dir = os.path.join(get_data_dir("temp_path"), f"unzip_{ds_id}")
    ensure_dir(temp_dir)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError("无效的 ZIP 文件")

    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    count = 0
    skipped = 0
    classes_set = set()

    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            src = os.path.join(root, f)
            ext = os.path.splitext(f)[1].lower()
            if ext in img_exts:
                dst = os.path.join(img_dir, f)
                if os.path.exists(dst):
                    if skip_existing:
                        skipped += 1
                        continue
                    base, e = os.path.splitext(f)
                    dst = os.path.join(img_dir, f"{base}_{gen_id()}{e}")
                shutil.move(src, dst)

                base_name = os.path.splitext(os.path.basename(dst))[0]
                lbl_src = _find_label(temp_dir, base_name)
                has_label = False
                if lbl_src:
                    lbl_dst = os.path.join(lbl_dir, base_name + ".txt")
                    shutil.move(lbl_src, lbl_dst)
                    has_label = True
                    with open(lbl_dst, "r", encoding="utf-8", errors="ignore") as lf:
                        for line in lf:
                            parts = line.strip().split()
                            if parts:
                                classes_set.add(parts[0])

                img_id = f"{ds_id}-img-{gen_id()}"
                fsize = os.path.getsize(dst)
                now = now_iso()
                conn.execute(
                    "INSERT OR IGNORE INTO images (id, dataset_id, filename, size, annotated, split_type, created_at) VALUES (?,?,?,?,?,?,?)",
                    (img_id, ds_id, os.path.basename(dst), fsize, int(has_label), "", now),
                )
                count += 1

    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            if f.lower() in ("dataset.yaml", "dataset.yml", "data.yaml", "data.yml"):
                src = os.path.join(root, f)
                dst = os.path.join(ds_dir, "dataset.yaml")
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                break

    shutil.rmtree(temp_dir, ignore_errors=True)
    _refresh_dataset_stats(ds_id)
    conn.commit()

    logger.info(f"数据集 {ds_id} 导入完成: {count} 张图片, 跳过重复 {skipped} 张")
    return {"imported": count, "skipped": skipped}


def merge_dataset(target_id: str, zip_path: str) -> dict:
    logger = get_logger()
    conn = get_connection()
    ds = get_dataset(target_id)
    if not ds:
        raise ValueError(f"数据集不存在: {target_id}")

    ds_dir = os.path.join(get_data_dir("datasets_path"), target_id)
    img_dir = os.path.join(ds_dir, "images")
    lbl_dir = os.path.join(ds_dir, "labels")
    ensure_dir(img_dir)
    ensure_dir(lbl_dir)

    temp_dir = os.path.join(get_data_dir("temp_path"), f"merge_{target_id}")
    ensure_dir(temp_dir)

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)
    except zipfile.BadZipFile:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise ValueError("无效的 ZIP 文件")

    result = _merge_extracted_dataset_into_target(target_id, temp_dir, img_dir, lbl_dir, conn)

    shutil.rmtree(temp_dir, ignore_errors=True)
    _refresh_dataset_stats(target_id)
    conn.commit()

    logger.info(
        "数据集 %s 合并完成: 图片新增 %s, 图片覆盖 %s, 标签新增 %s, 标签覆盖 %s",
        target_id,
        result["images_imported"],
        result["images_overwritten"],
        result["labels_imported"],
        result["labels_overwritten"],
    )
    return result


def _merge_extracted_dataset_into_target(ds_id: str, temp_dir: str, img_dir: str, lbl_dir: str, conn) -> dict:
    img_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    result = {
        "imported": 0,
        "images_imported": 0,
        "images_overwritten": 0,
        "labels_imported": 0,
        "labels_overwritten": 0,
    }
    touched_bases = set()

    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext not in img_exts:
                continue

            src = os.path.join(root, f)
            dst = os.path.join(img_dir, f)
            existed = os.path.exists(dst)
            if existed:
                os.remove(dst)
                result["images_overwritten"] += 1
            else:
                result["images_imported"] += 1
            shutil.move(src, dst)

            row = conn.execute(
                "SELECT id FROM images WHERE dataset_id=? AND filename=?",
                (ds_id, f),
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO images (id, dataset_id, filename, size, annotated, split_type, created_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        f"{ds_id}-img-{gen_id()}",
                        ds_id,
                        f,
                        os.path.getsize(dst),
                        0,
                        "",
                        now_iso(),
                    ),
                )
                result["imported"] += 1

            touched_bases.add(os.path.splitext(f)[0])

    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            if not f.endswith(".txt"):
                continue

            src = os.path.join(root, f)
            dst = os.path.join(lbl_dir, f)
            if os.path.exists(dst):
                os.remove(dst)
                result["labels_overwritten"] += 1
            else:
                result["labels_imported"] += 1
            shutil.move(src, dst)
            touched_bases.add(os.path.splitext(f)[0])

    for base_name in touched_bases:
        image_filename = _find_existing_image_filename(img_dir, base_name)
        if not image_filename:
            continue
        img_path = os.path.join(img_dir, image_filename)
        lbl_path = os.path.join(lbl_dir, base_name + ".txt")
        conn.execute(
            "UPDATE images SET size=?, annotated=? WHERE dataset_id=? AND filename=?",
            (
                os.path.getsize(img_path),
                int(os.path.exists(lbl_path)),
                ds_id,
                image_filename,
            ),
        )

    return result


def _find_existing_image_filename(img_dir: str, base_name: str) -> str | None:
    if not os.path.isdir(img_dir):
        return None
    for f in os.listdir(img_dir):
        if os.path.splitext(f)[0] == base_name:
            return f
    return None


def _find_label(search_dir: str, base_name: str) -> str | None:
    for root, dirs, files in os.walk(search_dir):
        for f in files:
            if os.path.splitext(f)[0] == base_name and f.endswith(".txt"):
                return os.path.join(root, f)
    return None


def _refresh_dataset_stats(ds_id: str):
    conn = get_connection()
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    img_dir = os.path.join(ds_dir, "images")

    img_count = 0
    ann_count = 0
    total_size = 0
    classes_set = set()

    if os.path.isdir(img_dir):
        for f in os.listdir(img_dir):
            fp = os.path.join(img_dir, f)
            if os.path.isfile(fp):
                img_count += 1
                total_size += os.path.getsize(fp)
                base = os.path.splitext(f)[0]
                lbl = os.path.join(ds_dir, "labels", base + ".txt")
                if os.path.exists(lbl):
                    ann_count += 1
                    with open(lbl, "r", encoding="utf-8", errors="ignore") as lf:
                        for line in lf:
                            parts = line.strip().split()
                            if parts:
                                classes_set.add(parts[0])

    now = now_iso()
    conn.execute(
        "UPDATE datasets SET image_count=?, annotated_count=?, classes=?, total_size=?, updated_at=? WHERE id=?",
        (img_count, ann_count, safe_json_dumps(sorted(classes_set)), total_size, now, ds_id),
    )


def get_class_names(ds_id: str) -> dict:
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)

    yaml_path = os.path.join(ds_dir, "dataset.yaml")
    if os.path.exists(yaml_path):
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
            if content and "names" in content:
                names = content["names"]
                if isinstance(names, dict):
                    return {str(k): str(v) for k, v in names.items()}
                if isinstance(names, list):
                    return {str(i): str(v) for i, v in enumerate(names)}
        except Exception:
            pass

    conn = get_connection()
    row = conn.execute("SELECT classes FROM datasets WHERE id=?", (ds_id,)).fetchone()
    if row:
        classes = safe_json_loads(row["classes"])
        return {str(c): str(c) for c in classes}

    return {}


def get_image_labels(ds_id: str, filename: str) -> list:
    ds_dir = os.path.join(get_data_dir("datasets_path"), ds_id)
    base = os.path.splitext(filename)[0]
    lbl_path = os.path.join(ds_dir, "labels", base + ".txt")

    if not os.path.exists(lbl_path):
        return []

    class_names = get_class_names(ds_id)
    labels = []

    with open(lbl_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 5:
                class_id = parts[0]
                x_center = float(parts[1])
                y_center = float(parts[2])
                width = float(parts[3])
                height = float(parts[4])
                class_name = class_names.get(str(class_id), class_id)
                labels.append({
                    "class_id": class_id,
                    "class_name": class_name,
                    "x_center": x_center,
                    "y_center": y_center,
                    "width": width,
                    "height": height,
                })

    return labels
