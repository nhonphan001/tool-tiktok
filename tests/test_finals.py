import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import db, finals, packages  # noqa: E402
from app.config import settings  # noqa: E402


def test_parse_names():
    assert finals.parse("Goi_29_TraTruaCuoiNam_Final_Sub.mp4") == ("29", "final")
    assert finals.parse("Goi_29_TraTruaCuoiNam_Clean_Master.mp4") == ("29", "clean")
    assert finals.parse("GOI-031_GiapTy1984_Final.mp4") == ("31", "final")
    assert finals.parse("Goi_27_canh_1.mp4") is None  # clip thô, không phải thành phẩm


def test_sync_attach_status_notify_and_late_package():
    db.get_conn()
    packages.init()
    finals.init()
    with db.tx() as c:
        c.execute("DELETE FROM jobs")
    pid = packages.save({"goi": "30", "loai": 3, "scene1": "Trà sáng", "caption": "Trà"})
    files = [{"id": "F30", "name": "Goi_30_TraSang_Final_Sub.mp4", "modifiedTime": "2026-11-25T03:00:00Z"},
             {"id": "C30", "name": "Goi_30_TraSang_Clean_Master.mp4", "modifiedTime": "2026-11-25T03:00:00Z"},
             {"id": "F31", "name": "Goi_31_GiapTy1984_Final_Sub.mp4", "modifiedTime": "2026-11-25T10:00:00Z"},
             {"id": "X", "name": "ghi_chu.mp4", "modifiedTime": "2026-11-25T10:00:00Z"}]
    msgs = finals.sync(files)
    p = packages.get(pid)
    assert p["final_video"] == "F30" and p["clean_video"] == "C30" and p["status"] == "cho_dang"
    assert any("Gói 30" in m and "chờ đăng" in m for m in msgs) and any("Gói 31" in m and "chưa có gói" in m for m in msgs)
    jobs = db.query("SELECT message, link FROM jobs WHERE kind='finals'")
    assert len(jobs) == 2 and any(j["link"] == f"/packages/{pid}#kit" for j in jobs)
    assert finals.sync(files) == []  # chạy lại không báo trùng
    # phiếu Gói 31 được nhập sau → lần đọc kế tiếp tự gắn video
    pid31 = packages.save({"goi": "31", "loai": 1, "scene1": "Lá số", "caption": "Giáp Tý"})
    msgs = finals.sync(files)
    assert packages.get(pid31)["final_video"] == "F31" and any("Gói 31" in m and "chờ đăng" in m for m in msgs)
    # đã đăng → không lùi trạng thái khi Gemini tải bản sửa
    with db.tx() as c:
        c.execute("UPDATE packages SET status='da_dang' WHERE id=?", (pid,))
    finals.sync(files + [{"id": "F30b", "name": "Goi_30_TraSang_v2_Final_Sub.mp4", "modifiedTime": "2026-11-25T05:00:00Z"}])
    p = packages.get(pid)
    assert p["final_video"] == "F30b" and p["status"] == "da_dang"


def test_packages_page_and_route(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(finals, "list_finals", lambda token=None: [])
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    page = c.get("/packages").text
    assert "Kiểm tra video thành phẩm" in page and "Thành phẩm" in page
    assert c.post("/packages/finals/sync", follow_redirects=False).status_code == 303
