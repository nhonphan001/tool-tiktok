"""Kiểm thử module thống kê bình luận TikTok Studio (/binh-luan)."""
import json
import os

os.environ["DATABASE_PATH"] = ":memory:"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["APP_PASSWORD"] = "pw"
os.environ["NOTEBOOKLM_MODE"] = "local"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import comment_stats, db, packages  # noqa: E402
from app.main import app  # noqa: E402


def _sample_items():
    return [
        {
            "idx": 1,
            "author_display": "khach_demo_01",
            "is_creator": False,
            "text": "Ôi em 17 tháng 4 1 9 84",
            "time_text": "3 giờ trước",
            "likes": 0,
            "reply_count": 0,
            "replied_by_creator": False,
            "video_caption": "Chị nào tuổi Giáp Tý 1984 bình luận năm sinh để Cô Kim xem giúp nha. #giapty1984",
            "video_id": None,
        },
        {
            "idx": 2,
            "author_display": "khach_demo_02",
            "is_creator": False,
            "text": "4_10 quý sửu cảm ơn cô kim rất nhiều ❤️",
            "time_text": "1 ngày trước",
            "likes": 2,
            "reply_count": 0,
            "replied_by_creator": False,
            "video_caption": "Tối nay 19h00, Cô Kim pha ấm trà nóng giải mã trọn vẹn lá số Bát Tự cho một chị tuổi Quý Sửu 1973",
            "video_id": None,
        },
        {
            "idx": 3,
            "author_display": "khach_demo_03",
            "is_creator": False,
            "text": "Xem giúp em lá số Nữ 12/03/1995 sinh lúc 8h sáng",
            "time_text": "1 tuần trước",
            "likes": 3,
            "reply_count": 1,
            "replied_by_creator": True,
            "video_caption": "Tối nay 19h00, Cô Kim pha ấm trà nóng giải mã trọn vẹn lá số Bát Tự cho một chị tuổi Quý Sửu 1973",
            "video_id": None,
        },
        {
            "idx": 4,
            "author_display": "khach_demo_04",
            "is_creator": False,
            "text": "Nam mô a di đà phật quý sửu cầu mong bình an và sức khỏe",
            "time_text": "1 ngày trước",
            "likes": 1,
            "reply_count": 0,
            "replied_by_creator": False,
            "video_caption": "Tối nay 19h00, Cô Kim pha ấm trà nóng giải mã trọn vẹn lá số Bát Tự cho một chị tuổi Quý Sửu 1973",
            "video_id": None,
        },
        {
            "idx": 5,
            "author_display": "khach_demo_05",
            "is_creator": False,
            "text": "cảm ơn cô nhiều lắm",
            "time_text": "2 ngày trước",
            "likes": 5,
            "reply_count": 0,
            "replied_by_creator": False,
            "video_caption": "Sáng 20/11, Cô Kim dọn bàn trà ra vườn hoa",
            "video_id": None,
        },
        {
            "idx": 6,
            "author_display": "khach_demo_06",
            "is_creator": False,
            "text": "🥰🥰🥰",
            "time_text": "2 giờ trước",
            "likes": 0,
            "reply_count": 0,
            "replied_by_creator": False,
            "video_caption": "Sáng 20/11, Cô Kim dọn bàn trà ra vườn hoa",
            "video_id": None,
        },
        {
            "idx": 7,
            "author_display": "tiemtragiaima",
            "is_creator": True,
            "text": "Chị em Giáp Tý 1984 năm nay thấy vất vả nhất chuyện gì?",
            "time_text": "1 ngày trước",
            "likes": 1,
            "reply_count": 0,
            "replied_by_creator": False,
            "video_caption": "Chị nào tuổi Giáp Tý 1984 bình luận năm sinh để Cô Kim xem giúp nha. #giapty1984",
            "video_id": None,
        },
    ]


def test_birth_extraction_and_classification():
    # Năm bị tách khoảng trắng '1 9 84'
    b1 = comment_stats.extract_birth_info("Ôi em 17 tháng 4 1 9 84")
    assert b1["payload"]["has_full_date"] is True
    assert (b1["payload"]["dd"], b1["payload"]["mm"], b1["payload"]["yy"]) == (17, 4, 1984)
    assert b1["payload"]["tu_tru"]
    assert comment_stats.classify_comment("Ôi em 17 tháng 4 1 9 84", False, b1) == "xin_la_so"

    # Ngày_tháng + Can Chi (4_10 quý sửu -> 4/10/1973)
    b2 = comment_stats.extract_birth_info("4_10 quý sửu cảm ơn cô kim rất nhiều ❤️")
    assert b2["payload"]["has_full_date"] is True
    assert (b2["payload"]["dd"], b2["payload"]["mm"], b2["payload"]["yy"]) == (4, 10, 1973)
    assert "Quý Sửu" in b2["can_chi_tags"]
    assert comment_stats.classify_comment("4_10 quý sửu cảm ơn cô kim rất nhiều ❤️", False, b2) == "xin_la_so"

    # Năm đứng độc lập kèm emoji
    b3 = comment_stats.extract_birth_info("🥰 1972 💋")
    assert b3["payload"]["has_birth_year"] is True and b3["payload"]["yy"] == 1972
    assert comment_stats.classify_comment("🥰 1972 💋", False, b3) == "xin_la_so"

    # Ngày dính sát dấu chấm 'ạ.18/04/1993'
    b4 = comment_stats.extract_birth_info("hữu duyên giúp em với ạ.18/04/1993")
    assert b4["payload"]["has_full_date"] is True
    assert (b4["payload"]["dd"], b4["payload"]["mm"], b4["payload"]["yy"]) == (18, 4, 1993)

    # Phân loại các nhóm khác
    assert comment_stats.classify_comment("Nam mô a di đà phật bình an", False) == "tam_su_cau_an"
    assert comment_stats.classify_comment("cảm ơn cô nhiều lắm", False) == "cam_on_don_nhan"
    assert comment_stats.classify_comment("🥰🥰🥰", False) == "emoji_khac"
    assert comment_stats.classify_comment("Câu hỏi mồi của kênh", True) == "kenh"


def test_mask_handle_and_dedup_import():
    assert comment_stats.mask_handle("tothuy193") == "to***93"
    assert comment_stats.mask_handle("abc") == "a***c"
    assert comment_stats.mask_handle("") == "(ẩn)"

    db.reset_connection()
    packages.init()
    packages.save({
        "goi": "27", "loai": 1, "title": "Quý Sửu 1973",
        "caption": "Tối nay 19h00, Cô Kim pha ấm trà nóng giải mã trọn vẹn lá số Bát Tự cho một chị tuổi Quý Sửu 1973",
    })

    items = _sample_items()
    r1 = comment_stats.import_comments(items, note="Đợt 1")
    assert r1 == {"total": 7, "inserted": 7, "updated": 0}

    # Nhập lại cùng dữ liệu với lượt thích tăng -> cập nhật, không nhân đôi
    items2 = [dict(x) for x in items]
    items2[0]["likes"] = 9
    items2[0]["replied_by_creator"] = True
    r2 = comment_stats.import_comments(items2, note="Đợt 2")
    assert r2 == {"total": 7, "inserted": 0, "updated": 7}

    d = comment_stats.dashboard_data(role="all")
    assert d["kpi"]["total"] == 7
    assert d["kpi"]["viewer_total"] == 6
    assert d["kpi"]["creator_total"] == 1
    assert d["kpi"]["replied"] == 2
    assert d["kpi"]["unreplied"] == 4
    assert d["kpi"]["xin_la_so"] == 3
    assert d["kpi"]["xin_la_so_full"] == 3
    assert any(v["goi"] == "27" for v in d["video_stats"])

    # Báo cáo Markdown ẩn danh 100% — KHÔNG chứa nick khách
    md_text = comment_stats.to_markdown(d)
    assert "Thống kê bình luận TikTok Studio" in md_text
    assert "khach_demo_01" not in md_text
    assert "khach_demo_02" not in md_text
    assert "Gói 27" in md_text


def test_comment_stats_routes_and_auth():
    db.reset_connection()
    packages.init()
    c = TestClient(app)

    # Bắt buộc đăng nhập
    assert c.get("/binh-luan", follow_redirects=False).status_code == 303
    assert c.get("/binh-luan/bao-cao.md", follow_redirects=False).status_code == 303

    c.post("/login", data={"password": "pw"})
    r0 = c.get("/binh-luan")
    assert r0.status_code == 200 and "Chưa có dữ liệu bình luận" in r0.text

    # Nhập JSON qua form
    payload = json.dumps(_sample_items(), ensure_ascii=False)
    ri = c.post("/binh-luan/import", data={"payload": payload, "note": "Test 26/11"}, follow_redirects=True)
    assert ri.status_code == 200
    assert "Bảng 1 · Theo nhóm bình luận" in ri.text
    assert "Bảng 3 · Thống kê theo từng Video" in ri.text
    # Mặc định ẩn nick khách
    assert "khach_demo_01" not in ri.text
    assert "kh***01" in ri.text

    # Bật xem nick nội bộ
    r_nick = c.get("/binh-luan?show_nick=1")
    assert r_nick.status_code == 200 and "@khach_demo_01" in r_nick.text

    # Đánh dấu đã trả lời thủ công
    row_id = comment_stats.dashboard_data(role="viewer")["rows"][0]["id"]
    rt = c.post(f"/binh-luan/{row_id}/trang-thai", data={"replied": "1", "back": "/binh-luan?role=viewer"}, follow_redirects=False)
    assert rt.status_code == 303 and rt.headers["location"] == "/binh-luan?role=viewer"
    assert comment_stats.dashboard_data(role="viewer")["kpi"]["replied"] == 2

    # Tải báo cáo ẩn danh .md
    rmd = c.get("/binh-luan/bao-cao.md")
    assert rmd.status_code == 200 and "text/markdown" in rmd.headers["content-type"]
    assert "khach_demo_01" not in rmd.text

    # Xoá toàn bộ dữ liệu cục bộ
    rc = c.post("/binh-luan/xoa-tat-ca", follow_redirects=True)
    assert rc.status_code == 200 and "Chưa có dữ liệu bình luận" in rc.text
