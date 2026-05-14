import os
import json
import math

from app.models.database import get_connection, now_iso
from app.utils.logger import get_logger
from app.utils.helpers import gen_id, safe_json_loads, safe_json_dumps, ensure_dir
from app.config import get_data_dir


def init_upload(filename: str, total_size: int, chunk_size: int = 5 * 1024 * 1024) -> dict:
    conn = get_connection()
    session_id = f"upload-{gen_id()}"
    total_chunks = math.ceil(total_size / chunk_size)
    now = now_iso()
    temp_dir = get_data_dir("temp_path")
    target_path = os.path.join(temp_dir, f"{session_id}_{filename}")

    conn.execute(
        "INSERT INTO upload_sessions (id, filename, total_size, chunk_size, total_chunks, received_chunks, target_path, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (session_id, filename, total_size, chunk_size, total_chunks, safe_json_dumps([]), target_path, now, now),
    )
    conn.commit()

    return {
        "session_id": session_id,
        "chunk_size": chunk_size,
        "total_chunks": total_chunks,
    }


def upload_chunk(session_id: str, chunk_index: int, chunk_data: bytes) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM upload_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise ValueError(f"上传会话不存在: {session_id}")

    chunk_size = row["chunk_size"]
    chunk_dir = os.path.join(get_data_dir("temp_path"), session_id)
    ensure_dir(chunk_dir)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index:05d}")

    with open(chunk_path, "wb") as f:
        f.write(chunk_data)

    received = safe_json_loads(row["received_chunks"])
    if chunk_index not in received:
        received.append(chunk_index)

    conn.execute(
        "UPDATE upload_sessions SET received_chunks=?, updated_at=? WHERE id=?",
        (safe_json_dumps(sorted(received)), now_iso(), session_id),
    )
    conn.commit()

    total_chunks = row["total_chunks"]
    done = len(received) == total_chunks

    return {
        "session_id": session_id,
        "chunk_index": chunk_index,
        "received_chunks": len(received),
        "total_chunks": total_chunks,
        "complete": done,
    }


def complete_upload(session_id: str) -> str:
    conn = get_connection()
    row = conn.execute("SELECT * FROM upload_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise ValueError(f"上传会话不存在: {session_id}")

    received = safe_json_loads(row["received_chunks"])
    total_chunks = row["total_chunks"]
    if len(received) != total_chunks:
        raise ValueError(f"分片不完整: {len(received)}/{total_chunks}")

    chunk_dir = os.path.join(get_data_dir("temp_path"), session_id)
    target_path = row["target_path"]

    with open(target_path, "wb") as out:
        for i in range(total_chunks):
            chunk_path = os.path.join(chunk_dir, f"chunk_{i:05d}")
            if not os.path.exists(chunk_path):
                raise ValueError(f"分片文件缺失: chunk_{i:05d}")
            with open(chunk_path, "rb") as cf:
                out.write(cf.read())

    import shutil
    shutil.rmtree(chunk_dir, ignore_errors=True)

    conn.execute("DELETE FROM upload_sessions WHERE id=?", (session_id,))
    conn.commit()

    return target_path


def get_upload_status(session_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM upload_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        return None
    received = safe_json_loads(row["received_chunks"])
    return {
        "session_id": row["id"],
        "filename": row["filename"],
        "total_size": row["total_size"],
        "received_chunks": len(received),
        "total_chunks": row["total_chunks"],
        "complete": len(received) == row["total_chunks"],
    }
