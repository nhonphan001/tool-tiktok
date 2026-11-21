import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import db, unread  # noqa: E402
from app.config import settings  # noqa: E402


def test_badges_and_dots():
    from fastapi.testclient import TestClient
    from app import cycle_summary, mail_notes
    from app.main import app

    db.get_conn()
    cycle_summary.init()
    mail_notes.init()
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    c.get("/tom-tat")  # đặt mốc đã xem
    db.save_setting("seen_report", "2026-01-01T00:00:00+00:00")
    db.save_setting("seen_mail", "2026-01-01T00:00:00+00:00")
    with db.tx() as cur:
        cur.execute("INSERT INTO cycle_summaries(created_at, code, md) VALUES(?,?,?)", (db.now_iso(), "TOMTAT-X", "x"))
        cur.execute("INSERT OR REPLACE INTO mail_notes(file_id, name, sender, modified, kind, title, read_at, updates_json)"
                    " VALUES('M1','DANHGIA-1.md','Gemini','1','danh_gia','t',?,'[]')", (db.now_iso(),))
    html = c.get("/packages").text
    assert 'class="nav-dot"' in html and "menu-dot" in html
    page = c.get("/tom-tat").text  # mở trang → mục mới có chấm đỏ, menu Báo cáo hết đỏ
    assert 'class="new-dot"' in page
    assert unread.counts()["report"] == 0
    assert 'class="new-dot"' not in c.get("/tom-tat").text.split("<h1>")[1]  # lần sau hết chấm
    assert unread.counts()["mail"] >= 1
    c.get("/hop-thu")
    assert unread.counts()["mail"] == mail_notes.pending_count()


def test_section_for():
    assert unread.section_for("/") == "dashboard"
    assert unread.section_for("/packages/12") == "packages"
    assert unread.section_for("/tom-tat") == "report"
    assert unread.section_for("/videos") is None
