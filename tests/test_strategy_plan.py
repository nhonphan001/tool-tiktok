import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import compliance, db, gemini_requests, strategy_plan as sp  # noqa: E402
from app.config import settings  # noqa: E402

MD = """## 2. Mô thức
abc
### 3. Lịch đăng đề xuất 7 ngày tới (21/11 – 27/11/2026)
| Ngày | Giờ đăng | Chủ đề / Ý tưởng | Định dạng | Độ dài | Hook gợi ý (3 giây đầu) | Hashtag |
|---|---|---|---|---|---|---|
| **Thứ 7 (21/11)** | 11:00 | **[Có giỏ hàng]** Gói 16: Dọn ban thờ thanh tịnh cuối năm | Cô Kim | 32s | "Bao sái ban thờ thanh sạch." | #tiemtragiaima #battu #phongthuy |
| **Thứ 7 (21/11)** | 19:00 | Chữa lành cuối năm: Gửi người gánh vác | Cô Kim | 30s | "Chỉ còn 40 ngày" | #chualanh |
| CN (22/11) | 19:30 | Trả lời bình luận: nữ Quý Dậu 1993 | Cô Kim | 35s | "Gửi Quý Dậu 1993" | #battu |
| T3 (24/11) | 11:00 | [Có giỏ hàng] Gói 16: Góc thờ tự | Cô Kim | 30s | "Thỉnh khăn" | #caivan |
| T6 (27/11) | 11:00 | [Có giỏ hàng] Gói 16: Cuối năm | Cô Kim | 30s | "Lau dọn" | #caivan |
| T6 (27/11) | 11:00 | Giải mã lá số: Nhật can Mậu Thổ | Cô Kim | 32s | "Người tính Thổ" | #battu |
### 4. 10 ý tưởng
"""


def test_parse_and_warnings():
    rows = sp.parse_schedule(MD)
    assert [r["loai"] for r in rows] == [2, 3, 1, 2, 2, 1]
    assert rows[2]["nhom"] == 4 and rows[1]["nhom"] == 5 and rows[0]["ngay"] == "Thứ 7 (21/11)"
    w0 = " ".join(rows[0]["warnings"])
    assert "hashtag bói toán" in w0 and "12:00" in w0 and "hộ thân" not in w0  # "thờ thanh" không bị bắt nhầm
    assert any("thỉnh" in w for w in rows[3]["warnings"])
    assert any("tối đa 2/tuần" in w for w in rows[4]["warnings"]) and not any("tối đa" in w for w in rows[3]["warnings"])
    assert any("19:00" in w for w in rows[5]["warnings"])
    pre = sp.prefill(rows[0])
    assert pre["loai"] == 2 and pre["goal"] == "sale" and "#battu" not in pre["brief"].split("Hashtag gợi ý:")[1].split(".")[0] and pre["publish"] == "Thứ 7 (21/11), 11:00"
    assert "Có giỏ hàng" not in pre["title"]


def test_compliance_word_boundaries():
    for ok in ("bàn thờ thanh tịnh", "phù hợp với con", "trú tại Sài Gòn"):
        assert compliance.check(ok, True)["promise"] == [], ok
    assert compliance.check("bùa hộ thân", True)["promise"]
    assert compliance.check("cầu phù hộ", True)["promise"]


def test_strategy_page_quick_create(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    db.get_conn()
    gemini_requests.init()
    acc = db.get_active_account()
    if not acc:
        db.upsert_account({"open_id": "o1", "display_name": "x", "connected_at": db.now_iso()})
        acc = db.get_active_account()
    with db.tx() as c:
        sid = c.execute("INSERT INTO strategies(open_id, created_at, status, content_md, source) VALUES(?,?,?,?,?)",
                        (acc["open_id"], db.now_iso(), "done", MD, "gemini")).lastrowid
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    html = c.get(f"/strategy?id={sid}").text
    assert "Lịch 7 ngày → tạo gói nhanh" in html and f"/requests?sid={sid}&row=2" in html
    form = c.get(f"/requests?sid={sid}&row=2").text
    assert "Trả lời bình luận: nữ Quý Dậu 1993" in form and f'value="{sid}:2"' in form
    monkeypatch.setattr(gemini_requests, "send", lambda rid: "đã gửi")
    c.post("/requests/new", data={"brief": "x", "loai": "1", "goal": "comment", "plan_key": f"{sid}:2", "publish": "CN"})
    assert "Gói " in c.get(f"/strategy?id={sid}").text.split("Trả lời bình luận: nữ Quý Dậu 1993")[1].split("plan-row")[0]


def test_cycle_summary_after_strategy(monkeypatch):
    from app import cycle_summary, notebooklm, strategy

    db.get_conn()
    acc = db.get_active_account()
    if not acc:
        db.upsert_account({"open_id": "o1", "display_name": "x", "connected_at": db.now_iso()})
        acc = db.get_active_account()
    pushed = []
    monkeypatch.setattr(notebooklm, "push_drive", lambda doc, text: pushed.append((doc, text)))
    monkeypatch.setattr(settings, "summary_doc_gemini", "DOC_G")
    monkeypatch.setattr(settings, "summary_doc_claude", "DOC_C")
    monkeypatch.setattr(strategy, "call_gemini", lambda prompt: (MD, {
        "input_tokens": 1, "output_tokens": 1, "thinking_tokens": 0, "total_tokens": 2, "cost_usd": 0.001,
        "endpoint": "aistudio"}))
    res = strategy.run(strategy.start(acc["open_id"], ""))
    assert res["status"] == "done"
    rows = cycle_summary.all_rows()
    assert rows and rows[0]["pushed"] == "gemini,claude" and not rows[0]["error"]
    md = cycle_summary.get(rows[0]["id"])["md"]
    assert md.startswith("---\nma: TOMTAT-") and "## 3. Chiến lược vừa lập" in md and "| L2 |" in md
    assert "## 4. Điểm cần đánh giá chéo" in md and "dòng lịch có cảnh báo" in md
    assert [d for d, _ in pushed] == ["DOC_G", "DOC_C"] and pushed[0][1].startswith("# TÓM TẮT TỰ ĐỘNG")
