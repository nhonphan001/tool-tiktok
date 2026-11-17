"""Lưu trữ SQLite: tài khoản, ảnh chụp số liệu theo thời gian, video, chiến lược, nhật ký."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    open_id TEXT PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    avatar_url TEXT,
    bio TEXT,
    profile_link TEXT,
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at INTEGER,
    refresh_expires_at INTEGER,
    scope TEXT,
    is_demo INTEGER DEFAULT 0,
    connected_at TEXT
);
CREATE TABLE IF NOT EXISTS account_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    follower_count INTEGER,
    following_count INTEGER,
    likes_count INTEGER,
    video_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_acc_snap ON account_snapshots(open_id, taken_at);
CREATE TABLE IF NOT EXISTS videos (
    id TEXT PRIMARY KEY,
    open_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    create_time INTEGER,
    cover_url TEXT,
    share_url TEXT,
    duration INTEGER,
    view_count INTEGER DEFAULT 0,
    like_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    share_count INTEGER DEFAULT 0,
    first_seen TEXT,
    last_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_videos_open ON videos(open_id, create_time);
CREATE TABLE IF NOT EXISTS video_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER,
    share_count INTEGER
);
CREATE INDEX IF NOT EXISTS idx_vid_snap ON video_snapshots(video_id, taken_at);
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,
    message TEXT,
    videos_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    open_id TEXT,
    created_at TEXT,
    source TEXT,
    model TEXT,
    goal TEXT,
    content_md TEXT
);
CREATE TABLE IF NOT EXISTS sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    target TEXT,
    status TEXT,
    message TEXT
);
CREATE TABLE IF NOT EXISTS ai_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT,
    kind TEXT,
    ref_id INTEGER,
    backend TEXT,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    thinking_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


# Cột bổ sung cho DB cũ (ALTER TABLE nếu chưa có)
MIGRATIONS = [
    ("strategies", "status", "TEXT DEFAULT 'done'"),
    ("strategies", "notified", "INTEGER DEFAULT 1"),
    ("strategies", "input_tokens", "INTEGER DEFAULT 0"),
    ("strategies", "output_tokens", "INTEGER DEFAULT 0"),
    ("strategies", "thinking_tokens", "INTEGER DEFAULT 0"),
    ("strategies", "total_tokens", "INTEGER DEFAULT 0"),
    ("strategies", "cost_usd", "REAL DEFAULT 0"),
    ("strategies", "duration_sec", "REAL DEFAULT 0"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    for table, col, decl in MIGRATIONS:
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    # Job đang chạy dở khi app khởi động lại -> đánh dấu lỗi
    conn.execute(
        "UPDATE strategies SET status='error', notified=0, content_md='Bị gián đoạn do ứng dụng khởi động lại. Hãy tạo lại.'"
        " WHERE status='pending'"
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _connect() -> sqlite3.Connection:
    path = settings.database_path
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _connect()
        _conn.executescript(SCHEMA)
        _migrate(_conn)
        _conn.commit()
    return _conn


def reset_connection() -> None:
    """Dùng cho test: đóng kết nối để mở lại với DATABASE_PATH mới."""
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


@contextmanager
def tx():
    with _lock:
        conn = get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def query(sql: str, params: tuple | dict = ()) -> list[dict]:
    with _lock:
        rows = get_conn().execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_one(sql: str, params: tuple | dict = ()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


# ---------- settings ----------
def load_settings() -> dict[str, str]:
    return {r["key"]: r["value"] for r in query("SELECT key, value FROM app_settings")}


def save_setting(key: str, value: str) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO app_settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


# ---------- accounts ----------
def get_active_account() -> dict | None:
    return query_one("SELECT * FROM accounts ORDER BY connected_at DESC LIMIT 1")


def upsert_account(data: dict) -> None:
    cols = list(data.keys())
    placeholders = ",".join("?" for _ in cols)
    updates = ",".join(f"{c}=excluded.{c}" for c in cols if c != "open_id")
    with tx() as c:
        c.execute(
            f"INSERT INTO accounts({','.join(cols)}) VALUES({placeholders}) "
            f"ON CONFLICT(open_id) DO UPDATE SET {updates}",
            tuple(data[k] for k in cols),
        )


def delete_account(open_id: str) -> None:
    with tx() as c:
        vids = [r[0] for r in c.execute("SELECT id FROM videos WHERE open_id=?", (open_id,)).fetchall()]
        for vid in vids:
            c.execute("DELETE FROM video_snapshots WHERE video_id=?", (vid,))
        for table in ("videos", "account_snapshots", "scans", "strategies"):
            c.execute(f"DELETE FROM {table} WHERE open_id=?", (open_id,))
        c.execute("DELETE FROM accounts WHERE open_id=?", (open_id,))


def log_sync(target: str, status: str, message: str) -> None:
    with tx() as c:
        c.execute(
            "INSERT INTO sync_log(created_at, target, status, message) VALUES(?,?,?,?)",
            (now_iso(), target, status, message[:2000]),
        )
