"""Dấu đỏ "chưa xem" trên thanh menu và từng mục.

Mỗi khu vực lưu mốc "đã xem lần cuối" (app_settings: seen_<khu>). Khi anh Nhơn mở trang của khu đó:
- các mục mới hơn mốc cũ được đánh dấu chấm đỏ trong lần xem này (biến `seen_before` trong template),
- mốc được cập nhật thành "bây giờ" → lần sau dấu đỏ biến mất.
Lần đầu chạy (chưa có mốc) lấy mốc = lúc khởi tạo để không đỏ toàn bộ dữ liệu cũ.
"""
import logging

from . import db

log = logging.getLogger(__name__)

# khu → (đường dẫn trang đánh dấu đã xem, câu SQL đếm mục mới hơn mốc ?)
_N = "substr({c},1,19) > substr(?,1,19)"
SECTIONS = {
    "dashboard": (("/",), f"SELECT COUNT(*) AS n FROM scans WHERE status='ok' AND {_N.format(c='finished_at')}"),
    "strategy": (("/strategy",), f"SELECT COUNT(*) AS n FROM strategies WHERE status='done' AND {_N.format(c='created_at')}"),
    "packages": (("/packages",),
                 "SELECT (SELECT COUNT(*) FROM gemini_requests WHERE "
                 f"({_N.format(c='answered_at')} OR {_N.format(c='answer_modified')} OR {_N.format(c='video_seen')}))"
                 f" + (SELECT COUNT(*) FROM finals_seen WHERE kind='final' AND {_N.format(c='seen_at')}) AS n"),
    "requests": (("/requests",), f"SELECT COUNT(*) AS n FROM gemini_requests WHERE {_N.format(c='answered_at')}"
                                 f" OR {_N.format(c='answer_modified')}"),
    "mail": (("/hop-thu",), f"SELECT COUNT(*) AS n FROM mail_notes WHERE {_N.format(c='read_at')}"),
    "report": (("/report", "/tom-tat"), f"SELECT COUNT(*) AS n FROM cycle_summaries WHERE {_N.format(c='created_at')}"),
}


def _ensure_tables() -> None:
    try:
        from . import cycle_summary, gemini_requests, mail_notes

        cycle_summary.init()
        from . import finals

        finals.init()
        mail_notes.init()
        gemini_requests.init()
    except Exception:  # noqa: BLE001
        log.exception("unread init")


_ready = False


def seen(key: str) -> str:
    v = db.load_settings().get(f"seen_{key}")
    if not v:
        v = db.now_iso()
        db.save_setting(f"seen_{key}", v)
    return v


def mark(key: str) -> None:
    db.save_setting(f"seen_{key}", db.now_iso())


def counts() -> dict[str, int]:
    global _ready
    if not _ready:
        _ensure_tables()
        _ready = True
    out = {}
    for key, (_paths, sql) in SECTIONS.items():
        since = seen(key)
        try:
            n = (db.query_one(sql, (since,) * sql.count("?")) or {}).get("n", 0)
        except Exception:  # noqa: BLE001  (bảng chưa có cột/khi chạy test)
            n = 0
        out[key] = int(n or 0)
    try:
        from . import mail_notes

        out["mail"] += mail_notes.pending_count()  # cập nhật chờ duyệt luôn đỏ tới khi xử lý
    except Exception:  # noqa: BLE001
        pass
    return out


def section_for(path: str) -> str | None:
    for key, (paths, _sql) in SECTIONS.items():
        for p in paths:
            if (p == "/" and path == "/") or (p != "/" and (path == p or path.startswith(p + "/") or path.startswith(p + "?"))):
                return key
    return None


def visit(path: str) -> tuple[dict[str, int], str]:
    """Gọi khi hiển thị 1 trang: trả về (số mục mới mỗi khu, mốc cũ của khu đang xem) và đánh dấu đã xem."""
    c = counts()
    key = section_for(path)
    before = ""
    if key:
        before = seen(key)
        mark(key)
        c[key] = _pending_safe() if key == "mail" else 0
    return c, before


def _pending_safe() -> int:
    try:
        from . import mail_notes

        return mail_notes.pending_count()
    except Exception:  # noqa: BLE001
        return 0
