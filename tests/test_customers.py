import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import compliance, customers, db  # noqa: E402
from app.config import settings  # noqa: E402

MSG = ("Wow. Cô kim luận chính xác quá đỉnh .c mệt không dám than. Vậy cô cho hỏi năm tới c có tốt hơn không cô. "
       "Chẳng hạn như sức khỏe. Vì c bị đau xương khớp mãi thôi. Có kiêng màu sắc gì không cô.")
C = {"alias": "Chị Ngọc", "gioi": "nu", "dd": "20", "mm": "2", "yy": "1973", "t": "19:00", "lich": "duong"}


def test_colors_facts_templates():
    ch = customers.chart(C)
    col = customers.colors(ch)
    assert [h for h, _ in col["hop"]] == ["Mộc", "Hỏa"] and [h for h, _ in col["it"]] == ["Kim", "Thủy"] and col["sat_nguong"]
    facts = " ".join(customers.year_facts(ch))
    for s in ("Tỷ Kiên", "Hỷ thần", "Sửu – Mùi lục xung", "Hợi – Mùi bán hợp Mộc (đúng Dụng thần)", "Đại vận năm 2027: Canh Thân"):
        assert s in facts, s
    t = customers.templates(MSG, C, ch)
    assert len(t["public"]) <= 150 and "hộp thư" in t["public"] and "đi khám" in t["public"]
    assert "1973" not in t["public"] and "Ngọc" not in t["public"]  # công khai: không lộ ngày sinh / tên
    assert "xanh lá" in t["private"] and "trắng" in t["private"] and "không xem bệnh" in t["private"]
    for text in (t["public"], t["private"]):
        r = compliance.check(text, False)
        assert not r["promise"] and not r["offsite"], (text, r)
    no = customers.templates("cô xem giúp", {"gioi": "nam"}, None)
    assert "ngày giờ sinh" in no["public"] and "anh" in no["public"].lower()
    assert len(no["public"]) <= 150 and "bình luận" in no["public"].lower()
    assert "giờ sinh" in no["private"].lower() and "4 trụ" in no["private"].lower()

    # Trường hợp có ngày tháng năm sinh nhưng THIẾU GIỜ SINH -> gợi tò mò theo Nhật chủ & nhắc bổ sung giờ sinh
    c_no_hour = {"alias": "Chị Lan", "gioi": "nu", "dd": "17", "mm": "4", "yy": "1984", "t": "", "lich": "duong"}
    ch_no_hour = customers.chart(c_no_hour)
    t3 = customers.templates("Ôi em 17 tháng 4 1984", c_no_hour, ch_no_hour)
    assert t3["missing"] == ["giờ sinh"]
    assert len(t3["public"]) <= 150
    assert "giờ sinh" in t3["public"] and "4 trụ" in t3["public"] and "hộp thư" in t3["public"]
    assert "Tân Kim" in t3["public"]  # cá nhân hóa theo Nhật chủ, không chung chung
    assert "1984" not in t3["public"] and "Lan" not in t3["public"]
    assert "Trụ Giờ" in t3["private"] and "giờ sinh" in t3["private"]
    for text in (t3["public"], t3["private"]):
        r = compliance.check(text, False)
        assert not r["promise"] and not r["offsite"], (text, r)

    # Trường hợp thiếu cả giờ sinh lẫn giới tính
    c_min = {"alias": "Khách", "gioi": "", "dd": "28", "mm": "5", "yy": "1984", "t": "", "lich": "duong"}
    ch_min = customers.chart(c_min)
    t4 = customers.templates("sinh 28/5/1984", c_min, ch_min)
    assert t4["missing"] == ["giờ sinh", "giới tính"]
    assert len(t4["public"]) <= 150 and t4["public"].endswith("nha!") and "giờ sinh" in t4["public"] and "giới tính" in t4["public"]
    assert "Đại vận" in t4["private"]


def test_save_messages_tiers_delete():
    db.get_conn()
    customers.init()
    cid = customers.save(C)
    assert customers.get(cid)["tier"] == "moi"
    for i in range(3):
        customers.add_message(cid, "tin_nhan", "khach", f"tin {i}")
        customers.add_message(cid, "tin_nhan", "cokim", f"trả lời {i}")
    assert customers.get(cid)["tier"] == "than_thiet" and len(customers.messages(cid)) == 6
    assert customers.all_customers(q="1973")[0]["id"] == cid and customers.all_customers(tier="moi") == []
    customers.delete(cid)
    assert customers.get(cid) is None and customers.messages(cid) == []


def test_routes(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    assert "Soạn trả lời nhanh" in c.get("/khach-hang").text
    d = c.post("/api/khach-hang/goi-y", data={**C, "message": MSG, "ai": "0"}).json()
    assert d["public"] and d["private"] and d["issues"] == []
    r = c.post("/khach-hang", data={**C, "message": MSG, "channel": "tin_nhan"}, follow_redirects=False)
    cid = int(r.headers["location"].rsplit("/", 1)[1])
    page = c.get(f"/khach-hang/{cid}").text
    assert "Quý Sửu – Giáp Dần – Đinh Hợi – Canh Tuất" in page and "Màu hợp" in page and "xương khớp" in page
    d2 = c.post("/api/khach-hang/goi-y", data={"cid": cid, "message": "năm tới thế nào cô", "ai": "0"}).json()
    assert "2027" in d2["private"]
    # AI: giả lập Gemini
    from app import strategy

    monkeypatch.setattr(strategy, "call_gemini", lambda prompt, system, json_mode: (
        '{"binh_luan": "Thương chị, Cô Kim nhắn riêng cho chị trong hộp thư nha.", "tin_nhan": "Cô Kim chào chị...", "goi_y_video": "x"}',
        {"cost_usd": 0.001}))
    monkeypatch.setattr(strategy, "record_usage", lambda *a, **k: None)
    monkeypatch.setattr(settings, "gemini_api_key", "x")
    d3 = c.post("/api/khach-hang/goi-y", data={"cid": cid, "message": MSG, "ai": "1"}).json()
    assert d3["public"].startswith("Thương chị") and d3["idea"] == "x"
    assert c.post(f"/khach-hang/{cid}/tin", data={"message": "cảm ơn cô", "reply": "Cô Kim cảm ơn chị", "channel": "tin_nhan"},
                  follow_redirects=False).status_code == 303
    assert len(customers.messages(cid)) == 3
    # lưu từ trang Lá số
    r = c.post("/khach-hang/tu-laso", data={"text": "Chị Ngọc 20/2/1973 7 giờ tối nữ", "line": 1}, follow_redirects=False)
    assert r.status_code == 303 and "/khach-hang/" in r.headers["location"]
    new = customers.get(int(r.headers["location"].rsplit("/", 1)[1]))
    assert new["alias"] == "Chị Ngọc" and new["yy"] == 1973
