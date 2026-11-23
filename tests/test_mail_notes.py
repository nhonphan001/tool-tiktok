import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

import pytest  # noqa: E402

from app import db, mail_notes as mn  # noqa: E402
from app.config import settings  # noqa: E402

LETTER = """---
ma_yeu_cau: DANHGIA-2111-TOMTAT
loai: danh_gia
tu: Gemini
---

# Đánh giá chéo bản tóm tắt TOMTAT-2111-0505

Lịch 7 ngày lệch kế hoạch ở 3 dòng giỏ hàng.

```
cap_nhat_tool:
  posting_slots: "11:00, 12:00, 19:00"
  kpi_target_1: 1.650
  kpi_deadline_1: 26/11/2026
  kpi_like_view_min: 4,5%
  gemini_api_key: "abc"
  veo_budget_usd: 200
  content_rules: |
    Quy tắc mới dòng một rất dài để đủ hai mươi ký tự.
    Dòng hai.
```
"""


@pytest.fixture
def fresh(monkeypatch):
    db.get_conn()
    mn.init()
    with db.tx() as c:
        c.execute("DELETE FROM mail_notes")
        c.execute("DELETE FROM setting_changes")
    for k in ("posting_slots", "kpi_target_1", "kpi_deadline_1", "kpi_like_view_min", "content_rules"):
        monkeypatch.setattr(settings, k, getattr(settings, k))
    monkeypatch.setattr(settings, "auto_apply_updates", True)
    db.save_setting("auto_apply_updates", "true")  # _set() nạp lại cài đặt từ DB
    monkeypatch.setattr(settings, "mailbox_folder_ids", "FG,FC")
    yield
    for k in ("posting_slots", "kpi_target_1", "kpi_deadline_1", "kpi_like_view_min", "content_rules", "auto_apply_updates"):
        with db.tx() as c:
            c.execute("DELETE FROM app_settings WHERE key=?", (k,))


def test_parse_whitelist_and_validation():
    ups = {u["key"]: u for u in mn.parse_updates(LETTER)}
    assert ups["posting_slots"]["ok"] and ups["posting_slots"]["value"] == "11:00,12:00,19:00"
    assert ups["kpi_target_1"]["value"] == "1650" and ups["kpi_deadline_1"]["value"] == "2026-11-26"
    assert ups["kpi_like_view_min"]["value"] == "4.5"
    assert not ups["gemini_api_key"]["ok"] and not ups["veo_budget_usd"]["ok"]
    assert ups["content_rules"]["ok"] and not ups["content_rules"]["auto"] and "Dòng hai." in ups["content_rules"]["value"]
    assert not mn.validate("posting_slots", "25:00")["ok"]
    assert mn.sender_of(LETTER, False) == "Gemini" and mn.kind_of("DANHGIA-2111.md", LETTER) == "danh_gia"


def test_ingest_auto_apply_pending_and_revert(fresh):
    f = {"id": "F1", "name": "DANHGIA-2111-TOMTAT__GUI_CLAUDE.md", "modifiedTime": "2026-11-21T00:00:00Z"}
    n = mn.ingest(f, LETTER, "FC")
    assert settings.posting_slots == "11:00,12:00,19:00" and settings.kpi_target_1 == 1650
    st = {u["key"]: u.get("status") for u in n["updates"]}
    assert st["content_rules"] == "pending" and st["kpi_target_1"] == "applied"
    assert n["status"] == "partial"
    assert mn.ingest(f, LETTER, "FC") is None  # không đọc lại thư chưa sửa
    old_rules = settings.content_rules
    mn.decide("F1", "content_rules", "apply")
    assert settings.content_rules.startswith("Quy tắc mới") and mn.get("F1")["status"] == "applied"
    ch = next(c for c in mn.changes() if c["key"] == "content_rules")
    mn.revert(ch["id"])
    assert settings.content_rules == old_rules
    with pytest.raises(ValueError):
        mn.revert(ch["id"])


def test_manual_mode_and_first_run(fresh, monkeypatch):
    monkeypatch.setattr(settings, "auto_apply_updates", False)
    db.save_setting("auto_apply_updates", "false")
    before = settings.posting_slots
    n = mn.ingest({"id": "F2", "name": "CHOT-x.md", "modifiedTime": "1"}, LETTER.replace("11:00, 12:00", "10:30, 12:00"), "FG")
    assert settings.posting_slots == before and {u["key"]: u.get("status") for u in n["updates"]}["posting_slots"] == "pending"
    monkeypatch.setattr(settings, "auto_apply_updates", True)
    db.save_setting("auto_apply_updates", "true")
    n = mn.ingest({"id": "F3", "name": "CHOT-y.md", "modifiedTime": "1"}, LETTER.replace("11:00, 12:00", "10:30, 12:00"), "FG", True)
    assert settings.posting_slots == before  # lần nạp đầu không tự áp dụng


def test_page(fresh):
    from fastapi.testclient import TestClient
    from app.main import app

    mn.ingest({"id": "F4", "name": "DANHGIA-z.md", "modifiedTime": "2"}, LETTER, "FC")
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    html = c.get("/hop-thu").text
    assert "Hộp thư Claude" in html and "Quy tắc nội dung bắt buộc" in html and "Áp dụng" in html and "từ chối" in html
    c.post("/hop-thu/F4/content_rules", data={"action": "reject"})
    assert {u["key"]: u.get("status") for u in mn.get("F4")["updates"]}["content_rules"] == "rejected"


def test_claude_letters_copied_to_outbox(fresh, monkeypatch):
    from app import gemini_requests, notebooklm
    from app import db as _db

    pushed = []
    monkeypatch.setattr(notebooklm, "push_drive", lambda doc, text: pushed.append(text))
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "OUTBOX")
    now = _db.now_iso()
    letter = "---\nma_yeu_cau: SUA-2311-GOI-27-7-CANH\ntu: Claude\n---\n\n# Gói 27 bản 7 cảnh\n\nSửa cảnh 5 thêm “thật trọn vẹn”."
    mn.ingest({"id": "C1", "name": "SUA-2311-GOI-27-7-CANH__YEUCAU.md", "modifiedTime": now}, letter, "FG")
    mn.ingest({"id": "C2", "name": "CHOT-2311-X__YEUCAU.md", "modifiedTime": now}, "---\ntu: Claude\n---\n# X", "FG")
    mn.ingest({"id": "G2", "name": "CHOT-2311-X__XACNHAN.md", "modifiedTime": now}, "---\ntu: Gemini\n---\n# ok", "FC")
    names = [r["name"] for r in mn.claude_letters_for_gemini()]
    assert names == ["SUA-2311-GOI-27-7-CANH__YEUCAU.md"]  # thư đã có XACNHAN bị bỏ
    txt = gemini_requests.outbox_text()
    assert "THƯ CỦA CLAUDE ĐANG CHỜ GEMINI (1)" in txt and "thật trọn vẹn" in txt and "docs.google.com/document/d/C1" in txt
    assert mn.refresh_outbox() and "thật trọn vẹn" in pushed[-1]
