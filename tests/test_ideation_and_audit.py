"""Kiểm thử Bộ phận Ý tưởng (/y-tuong) và Bộ phận Kiểm toán & Tổng duyệt (/tong-duyet)."""
import os

os.environ["DATABASE_PATH"] = ":memory:"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["APP_PASSWORD"] = "pw"
os.environ["NOTEBOOKLM_MODE"] = "local"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import comment_stats, db, demo, ideation, packages, process_audit  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


def _seed_base():
    db.reset_connection()
    packages.init()
    ideation.init()
    process_audit.init()
    demo.seed(days=5, n_videos=5)
    # 1 gói đã làm Quý Sửu 1973 để test phát hiện chống trùng
    packages.save({
        "goi": "27", "loai": 1, "status": "da_dang",
        "title": "Giải mã Quý Sửu 1973 năm Đinh Mùi 2027",
        "caption": "Quý Sửu 1973 năm Đinh Mùi 2027",
        "scene1": "Chị tuổi Quý Sửu một chín bảy ba để lại ngày sinh dưới bình luận nha.",
    })
    # 1 gói chờ đăng có cảnh báo chữ 'comment' (Bộ quy tắc V2)
    packages.save({
        "goi": "34", "loai": 1, "status": "da_dung",
        "title": "Ất Sửu 1985 chờ đăng",
        "caption": "Chị nào tuổi Ất Sửu 1985 comment năm sinh nhé",
        "scene1": "Chị tuổi 85 comment năm sinh để Cô Kim xem nhé.",
    })
    # Bình luận thật (chưa trả lời) có ngày sinh 1984 và 1973
    comment_stats.import_comments([
        {
            "idx": 1, "author_display": "khach_rieng_84", "is_creator": False,
            "text": "Ôi em 17 tháng 4 1 9 84", "time_text": "3 giờ trước",
            "likes": 1, "reply_count": 0, "replied_by_creator": False,
            "video_caption": "Giáp Tý 1984",
        },
        {
            "idx": 2, "author_display": "khach_rieng_73", "is_creator": False,
            "text": "4_10 quý sửu cảm ơn cô kim", "time_text": "1 ngày trước",
            "likes": 1, "reply_count": 0, "replied_by_creator": False,
            "video_caption": "Quý Sửu 1973",
        },
    ])


def test_ideation_generate_dedup_and_approve():
    _seed_base()
    res = ideation.generate_batch()
    assert res["created"] >= 3
    # Chạy lại lần 2 không tạo trùng tiêu đề
    res2 = ideation.generate_batch()
    assert res2["created"] == 0

    rows = ideation.list_ideas("pending")
    assert rows
    # Không lộ nick khách trong ý tưởng
    blob = " ".join(f"{r['title']} {r['rationale']} {r['brief']}" for r in rows)
    assert "khach_rieng_84" not in blob and "khach_rieng_73" not in blob

    # Ý tưởng Quý Sửu 1973 phải có cảnh báo trùng Gói 27
    qs = next((r for r in rows if "1973" in r["title"] or "Quý Sửu" in r["title"]), None)
    assert qs is not None and "Gói 27" in qs["dup_warning"]

    # Ý tưởng Giáp Tý 1984 có đủ ngày sinh để prefill sang /requests
    gt = next((r for r in rows if "1984" in r["title"]), None)
    assert gt is not None and gt["birth"]["yy"] == 1984
    pre = ideation.prefill_request(gt)
    assert pre["loai"] == 1 and pre["scenes"] == 7 and pre["yy"] == 1984 and "một chín tám tư" in pre["brief"]


def test_process_audit_and_web_routes():
    _seed_base()
    ideation.generate_batch()
    d = process_audit.run_audit()
    assert len(d["checks"]) == 6
    assert d["overall"] in ("ok", "warn", "error")
    # Gói 34 (da_dung, có cảnh báo V2) phải hiện trong flagged_pkgs
    assert any(str(p["goi"]) == "34" and p["is_ready"] for p in d["flagged_pkgs"])
    md = process_audit.to_markdown(d)
    assert "BẢN TIN TỔNG DUYỆT QUY TRÌNH" in md and "khach_rieng_84" not in md

    c = TestClient(app)
    assert c.get("/y-tuong", follow_redirects=False).status_code == 303
    assert c.get("/tong-duyet", follow_redirects=False).status_code == 303

    c.post("/login", data={"password": "pw"})
    ry = c.get("/y-tuong")
    assert ry.status_code == 200 and "Bộ phận Ý tưởng" in ry.text

    rt = c.get("/tong-duyet")
    assert rt.status_code == 200 and "Bảng Tổng Duyệt Quy Trình" in rt.text and "Gói 34" in rt.text

    # Duyệt 1 ý tưởng -> chuyển thẳng sang /requests#moi với form đã điền sẵn
    first_id = ideation.list_ideas("pending")[0]["id"]
    ra = c.post(f"/y-tuong/{first_id}/duyet", follow_redirects=False)
    assert ra.status_code == 303 and ra.headers["location"] == "/requests#moi"
    assert ideation.get(first_id)["status"] == "approved"

    # Ký duyệt Bản tin Tổng duyệt
    rk = c.post("/tong-duyet/ky-duyet", data={"decision_note": "Chốt triển khai sáng 27/11"}, follow_redirects=True)
    assert rk.status_code == 200 and "Chốt triển khai sáng 27/11" in rk.text

    # Tải file Bản tin .md
    rmd = c.get("/tong-duyet/ban-tin.md")
    assert rmd.status_code == 200 and "text/markdown" in rmd.headers["content-type"]

    # Tài liệu V4 có mặt trong /tai-lieu & thanh điều hướng 5 khu + bottom-nav mobile hoạt động
    assert "QUY_TRINH_V4_Y_TUONG_VA_TONG_DUYET.md" in c.get("/tai-lieu").text
    assert 'class="hub-tabs"' in rt.text and 'class="bottom-nav"' in rt.text
    assert 'class="subnav"' in ry.text and "Ý tưởng" in ry.text and "Gói SX" in ry.text


def test_audit_and_ideas_studio_api():
    _seed_base()
    settings.api_token = "tok-v4"
    c = TestClient(app)
    hdr = {"x-api-token": "tok-v4"}

    assert c.get("/api/public/studio/audit").status_code == 401
    assert c.post("/api/public/studio/audit", json={"summary_md": "x"}).status_code == 401
    assert c.post("/api/public/studio/ideas", json={"ideas": []}).status_code == 401

    rg = c.get("/api/public/studio/audit", headers=hdr)
    assert rg.status_code == 200 and len(rg.json()["checks"]) == 6
    assert "khach_rieng_84" not in rg.text  # 0% PII qua API

    rp = c.post("/api/public/studio/audit", headers=hdr, json={
        "kind": "hang_ngay", "overall": "ok", "summary_md": "## Kiểm toán sáng 27/11\n- Mọi khâu ổn định.",
    })
    assert rp.status_code == 200 and rp.json()["ok"] is True

    ri = c.post("/api/public/studio/ideas", headers=hdr, json={
        "ideas": [{"title": "Nữ Nhâm Tuất 1982 · Điểm chuyển 2027", "loai": 1, "score": 91}],
    })
    assert ri.status_code == 200 and ri.json()["created"] == 1
