"""Tác vụ chạy ngầm chung (phân loại video, đồng bộ sản phẩm...), có thông báo khi xong."""
import logging
import threading

from . import db

log = logging.getLogger(__name__)

KIND_LABELS = {"classify": "Phân loại video bằng Gemini", "products": "Đồng bộ bảng sản phẩm"}


def start(kind: str, fn, *args) -> int:
    """Chạy fn(*args) ở luồng nền. fn trả về (message, usage_dict|None)."""
    with db.tx() as c:
        jid = c.execute(
            "INSERT INTO jobs(kind, status, message, created_at, notified) VALUES(?,?,?,?,0)",
            (kind, "pending", "", db.now_iso()),
        ).lastrowid

    def _run():
        tokens, cost = 0, 0.0
        try:
            message, usage = fn(*args)
            if usage:
                tokens, cost = usage.get("total_tokens", 0), usage.get("cost_usd", 0.0)
            status = "done"
        except Exception as e:  # noqa: BLE001
            log.exception("Job %s failed", kind)
            status, message = "error", str(e)
        with db.tx() as c:
            c.execute(
                "UPDATE jobs SET status=?, message=?, finished_at=?, total_tokens=?, cost_usd=?, notified=0 WHERE id=?",
                (status, str(message)[:2000], db.now_iso(), tokens, cost, jid),
            )

    threading.Thread(target=_run, daemon=True).start()
    return jid


def running(kind: str) -> bool:
    return bool(db.query_one("SELECT id FROM jobs WHERE kind=? AND status='pending'", (kind,)))
