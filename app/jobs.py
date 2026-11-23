"""Tác vụ chạy ngầm chung (phân loại video, đồng bộ sản phẩm...), có thông báo khi xong."""
import logging
import threading

from . import db

log = logging.getLogger(__name__)

KIND_LABELS = {"classify": "Phân loại video bằng Gemini", "products": "Đồng bộ bảng sản phẩm",
               "mailbox": "Hộp thư Gemini", "clips": "Clip thô mới", "scan": "Quét TikTok",
               "send": "Gửi thư cho Gemini", "mail_check": "Kiểm tra thư trả lời", "mail_notes": "Đọc hộp thư",
               "summary": "Bản tóm tắt", "tts": "Tạo giọng 4 cảnh", "sync": "Đồng bộ Drive / NotebookLM",
               "drive_test": "Kiểm tra Drive", "mail_note": "Hộp thư", "veo": "Veo", "inbox_scan": "Quét phiếu trong hộp thư", "ask": "Gemini trả lời câu hỏi"}


def start(kind: str, fn, *args, link: str = "", label: str = "") -> int:
    """Chạy fn(*args) ở luồng nền. fn trả về (message, usage_dict|None) hoặc chỉ message (str).
    Trình duyệt tự hỏi /api/jobs và hiện thông báo khi xong — trang không phải chờ."""
    with db.tx() as c:
        jid = c.execute(
            "INSERT INTO jobs(kind, status, message, created_at, notified, link) VALUES(?,?,?,?,0,?)",
            (kind, "pending", label, db.now_iso(), link),
        ).lastrowid

    def _run():
        tokens, cost = 0, 0.0
        try:
            out = fn(*args)
            message, usage = out if isinstance(out, tuple) else (out, None)
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
