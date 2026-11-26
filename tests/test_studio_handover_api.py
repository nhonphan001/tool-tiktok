"""Kiểm thử cổng API bàn giao công đoạn TikTok Studio + Bình luận cho An (Antigravity)."""
import json
import os

os.environ["DATABASE_PATH"] = ":memory:"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["APP_PASSWORD"] = "pw"
os.environ["NOTEBOOKLM_MODE"] = "local"
os.environ["GEMINI_API_KEY"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app import chrome_reports, comment_stats, consensus, db, demo, packages  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


def _studio_md() -> str:
    payload = {
        "schema": "tiktok-studio-quet/v1",
        "mode": "hang_ngay",
        "snapshot_at": "2026-11-26T18:30:00+07:00",
        "videos": [
            {
                "video_id": "7712345678901234567",
                "goi": "33",
                "loai": 1,
                "scenes": 7,
                "promoted": False,
                "metrics": {"views": 820, "unique_viewers": 710, "likes": 45, "comments": 9, "new_followers": 14, "avg_watch_s": 18.4},
                "retention_pct": {"2": 64, "10": 38},
                "traffic_source_pct": {"for_you": 82, "following": 11, "search": 4},
            }
        ],
    }
    return "# Quét kênh hằng ngày 26/11/2026 (An)\n\n## Tóm tắt\nGiữ chân tốt.\n\n```json\n" + json.dumps(payload) + "\n```\n"


def test_studio_api_requires_token():
    db.reset_connection()
    settings.api_token = "an-secret-token"
    c = TestClient(app)

    for method, path in (
        ("get", "/api/public/studio/status"),
        ("get", "/api/public/studio/clock"),
        ("get", "/api/public/studio/context"),
        ("get", "/api/public/studio/full-scan"),
        ("post", "/api/public/studio/report"),
        ("post", "/api/public/studio/comments"),
        ("post", "/api/public/studio/consensus/push"),
    ):
        r = getattr(c, method)(path)
        assert r.status_code == 401, (method, path)
        r_bad = getattr(c, method)(path, headers={"x-api-token": "wrong"})
        assert r_bad.status_code == 401, (method, path)


def test_studio_api_end_to_end(monkeypatch):
    db.reset_connection()
    packages.init()
    demo.seed(days=5, n_videos=4)
    settings.api_token = "an-secret-token"
    pushed = []
    monkeypatch.setattr(consensus, "push", lambda: (pushed.append(1) or "ok"))

    c = TestClient(app)
    hdr = {"x-api-token": "an-secret-token"}

    # 1. Đọc mốc giờ, ngữ cảnh và danh sách quét toàn bộ
    assert "ISO: 20" in c.get("/api/public/studio/clock", headers=hdr).text
    ctx = c.get("/api/public/studio/context?days=14", headers=hdr)
    assert ctx.status_code == 200 and "ngữ cảnh quét Studio cho An" in ctx.text
    fs = c.get("/api/public/studio/full-scan?batch=5", headers=hdr)
    assert fs.status_code == 200 and "quét TOÀN BỘ kênh" in fs.text

    # 2. Đẩy báo cáo Studio (.md + JSON) -> tự lưu, tách số liệu & đẩy báo cáo đồng thuận
    r_short = c.post("/api/public/studio/report", headers=hdr, json={"body": "quá ngắn"})
    assert r_short.status_code == 400

    r_rep = c.post("/api/public/studio/report", headers=hdr, json={"body": _studio_md()})
    assert r_rep.status_code == 200
    j = r_rep.json()
    assert j["ok"] is True and j["ingested_videos"] == 1 and j["consensus_status"] == "ok"
    assert len(pushed) == 1
    assert chrome_reports.get(j["report_id"]) is not None

    # 3. Đẩy bình luận tiktokstudio/comment -> lưu nội bộ SQLite, phản hồi 0% PII
    comments_payload = {
        "note": "Quét bởi An 26/11",
        "comments": [
            {
                "idx": 1,
                "author_display": "nick_rieng_khong_lo",
                "is_creator": False,
                "text": "Xem giúp em 17/04/1984 ạ",
                "time_text": "1 giờ trước",
                "likes": 2,
                "reply_count": 0,
                "replied_by_creator": False,
                "video_caption": "Giáp Tý 1984",
            }
        ],
    }
    r_com = c.post("/api/public/studio/comments", headers=hdr, json=comments_payload)
    assert r_com.status_code == 200
    assert "nick_rieng_khong_lo" not in r_com.text  # tuyệt đối không lộ nick qua API
    jc = r_com.json()
    assert jc["ok"] is True and jc["inserted"] == 1 and jc["kpi"]["xin_la_so"] == 1

    # Không có endpoint GET công khai cho danh sách bình luận cá nhân
    assert c.get("/api/public/studio/comments", headers=hdr).status_code == 405

    # 4. Kiểm tra trạng thái bàn giao & kích hoạt đồng thuận
    st = c.get("/api/public/studio/status", headers=hdr)
    assert st.status_code == 200
    js = st.json()
    assert js["studio_owner"] == "An (Antigravity)"
    assert js["comments_kpi"]["total"] == 1
    assert "nick_rieng_khong_lo" not in st.text

    rp = c.post("/api/public/studio/consensus/push", headers=hdr)
    assert rp.status_code == 200 and rp.json()["consensus_status"] == "ok"
    assert len(pushed) == 2

    # 5. Kiểm tra giao diện đã cập nhật chủ sở hữu sang An (Antigravity)
    c.post("/login", data={"password": "pw"})
    dg = c.get("/danh-gia").text
    assert "An · Antigravity" in dg and "/api/public/studio/report" in dg
    dt = c.get("/dong-thuan").text
    assert "Báo cáo đồng thuận (TikTok API + Studio · An)" in dt
    assert comment_stats.dashboard_data(role="all")["kpi"]["total"] == 1
