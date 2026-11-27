"""Kiểm tra Lịch đăng đề xuất 7 ngày trên /y-tuong & Nút Scan Studio API + nạp khách trên /khach-hang."""
from datetime import date

from fastapi.testclient import TestClient

from app import comment_stats, customers, db, ideation, main, packages


def _login(client: TestClient):
    client.post("/login", data={"password": main.settings.app_password})


def test_ideation_build_schedule_assigns_packages_and_ideas(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.database_path", str(tmp_path / "sched.db"))
    monkeypatch.setattr("app.config.settings.posting_slots", "11:00,12:00,19:00")
    db.reset_connection()
    packages.save({"goi": "37", "title": "Gói sẵn chờ đăng L1", "loai": 1, "status": "cho_dang", "scene1": "Lời 1"})
    packages.save({"goi": "38", "title": "Gói sẵn sản phẩm L2", "loai": 2, "status": "san_sang", "scene1": "Lời 1"})
    id1 = ideation.save_idea({"title": "Nữ Ất Sửu 1985", "loai": 1, "score": 92, "publish_slot": "19:00"})
    id3 = ideation.save_idea({"title": "Trà ấm Tiết Đại Tuyết", "loai": 3, "score": 85, "publish_slot": "11:00"})

    sched = ideation.build_schedule(days=3, start=date(2026, 11, 28))
    assert len(sched["days"]) == 3

    # Ngày đầu tiên (28/11): 11:00 nhận ý tưởng L3, 12:00 nhận Gói 38 L2, 19:00 nhận Gói 37 L1 (ưu tiên gói sẵn!)
    d0 = {s["time"]: s for s in sched["days"][0]["slots"]}
    assert d0["11:00"]["kind"] == "idea" and d0["11:00"]["ref_id"] == id3
    assert d0["12:00"]["kind"] == "package" and d0["12:00"]["goi"] == "38"
    assert d0["19:00"]["kind"] == "package" and d0["19:00"]["goi"] == "37"

    # Ngày thứ 2 (29/11): 19:00 nhận ý tưởng L1 (id1)
    d1 = {s["time"]: s for s in sched["days"][1]["slots"]}
    assert d1["19:00"]["kind"] == "idea" and d1["19:00"]["ref_id"] == id1
    assert id1 in sched["idea_schedule"]
    assert "29/11" in sched["idea_schedule"][id1]["full"]
    assert "19:00" in sched["idea_schedule"][id1]["full"]

    pre = ideation.prefill_request(ideation.get(id1), sched["idea_schedule"][id1])
    assert "29/11" in pre["publish"] and "19:00" in pre["publish"]


def test_customers_studio_scan_and_import_lead(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.database_path", str(tmp_path / "cust_scan.db"))
    db.reset_connection()
    comment_stats.init()
    customers.init()

    comment_stats.import_comments([
        {
            "author": "ngoclan1985",
            "text": "Cô Kim xem giúp em nữ 15/08/1985 dương lịch lúc 9h sáng ạ",
            "time_text": "1 giờ trước",
            "video_caption": "Tuổi Ất Sửu 1985 năm 2027",
            "replied_by_creator": False,
        }
    ], source="tiktok_studio", note="test")

    st = customers.studio_sync_status()
    assert st["studio_comments_total"] == 1
    assert st["studio_leads_total"] == 1
    sc_id = st["studio_leads"][0]["sc_id"]

    client = TestClient(main.app)
    _login(client)

    r_page = client.get("/khach-hang")
    assert r_page.status_code == 200
    assert "Scan Studio" in r_page.text
    assert "Lưu thành khách" in r_page.text

    r_scan = client.post("/khach-hang/scan-studio-api", data={"back": "/khach-hang"}, follow_redirects=True)
    assert r_scan.status_code == 200
    assert "Dữ liệu bình luận Studio" in r_scan.text or "API TikTok" in r_scan.text

    r_imp = client.post(f"/khach-hang/tu-binh-luan/{sc_id}", follow_redirects=False)
    assert r_imp.status_code == 303
    assert r_imp.headers["location"].startswith("/khach-hang/")

    # Sau khi lưu, lead đó không còn nằm trong danh sách chưa lưu nữa
    st2 = customers.studio_sync_status()
    assert st2["studio_leads_total"] == 0

    r_yt = client.get("/y-tuong")
    assert r_yt.status_code == 200
    assert "Lịch đăng đề xuất 7 ngày tới" in r_yt.text
