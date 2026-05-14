import os
import uuid
import json
from datetime import datetime


def gen_id(prefix: str = "") -> str:
    short = uuid.uuid4().hex[:8]
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{prefix}{ts}{short}" if prefix else f"{ts}{short}"


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def safe_json_loads(text: str, default=None):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def safe_json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def calc_page(total: int, page: int, page_size: int) -> dict:
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "offset": offset,
    }
