import sqlite3
import os
import threading
from datetime import datetime

from app.config import get_data_dir

_local = threading.local()


def _get_db_path() -> str:
    db_dir = get_data_dir("db_path")
    return os.path.join(db_dir, "cloud_training.db")


def get_connection() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_get_db_path(), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA foreign_keys=ON")
    return _local.conn


def close_connection():
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def init_tables():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS datasets (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL UNIQUE,
        image_count INTEGER DEFAULT 0,
        annotated_count INTEGER DEFAULT 0,
        classes     TEXT DEFAULT '[]',
        total_size  INTEGER DEFAULT 0,
        split_ratio REAL DEFAULT 0.8,
        status      TEXT DEFAULT 'active',
        created_at  TEXT NOT NULL,
        updated_at  TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS images (
        id          TEXT PRIMARY KEY,
        dataset_id  TEXT NOT NULL,
        filename    TEXT NOT NULL,
        size        INTEGER DEFAULT 0,
        width       INTEGER DEFAULT 0,
        height      INTEGER DEFAULT 0,
        annotated   INTEGER DEFAULT 0,
        split_type  TEXT DEFAULT '',
        created_at  TEXT NOT NULL,
        FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS training_tasks (
        id              TEXT PRIMARY KEY,
        dataset_id      TEXT NOT NULL,
        dataset_name    TEXT NOT NULL,
        version         TEXT NOT NULL,
        model_size      TEXT DEFAULT 'n',
        input_size      INTEGER DEFAULT 640,
        epochs          INTEGER DEFAULT 100,
        current_epoch   INTEGER DEFAULT 0,
        batch_size      INTEGER DEFAULT 16,
        learning_rate   REAL DEFAULT 0.01,
        device          TEXT DEFAULT 'cuda:0',
        status          TEXT DEFAULT 'pending',
        pid             INTEGER DEFAULT 0,
        map50           REAL DEFAULT 0,
        map50_95        REAL DEFAULT 0,
        box_loss        REAL DEFAULT 0,
        cls_loss        REAL DEFAULT 0,
        run_dir         TEXT DEFAULT '',
        created_at      TEXT NOT NULL,
        started_at      TEXT DEFAULT '',
        completed_at    TEXT DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS packages (
        id              TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        dataset_name    TEXT NOT NULL,
        version         TEXT NOT NULL,
        task_id         TEXT DEFAULT '',
        size            INTEGER DEFAULT 0,
        map_val         REAL DEFAULT 0,
        training_time   TEXT DEFAULT '',
        file_path       TEXT DEFAULT '',
        status          TEXT DEFAULT 'ready',
        created_at      TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS upload_sessions (
        id              TEXT PRIMARY KEY,
        filename        TEXT NOT NULL,
        total_size      INTEGER NOT NULL,
        chunk_size      INTEGER NOT NULL,
        total_chunks    INTEGER NOT NULL,
        received_chunks TEXT DEFAULT '[]',
        target_path     TEXT DEFAULT '',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    );
    """)
    conn.commit()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
