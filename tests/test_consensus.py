import json
import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import chrome_reports, consensus, db, packages  # noqa: E402
from app.config import settings  # noqa: E402

VN = timezone(timedelta(hours=7))
OID = "oid_consensus"


def _setup():
    db.get_conn()
    packages.init()
    consensus.init()
    now = datetime.now(VN)
    with db.tx() as c:
        c.execute("DELETE FROM accounts")
        c.execute("INSERT INTO accounts(open_id, username, connected_at) VALUES(?,?,?)", (OID, "tiemtragiaima", db.now_iso()))
        for vid, days_ago, hour, views in (("7000000000000000001", 5, 11, 10200), ("7000000000000000002", 1, 19, 600),
                                           ("7000000000000000003", 4, 11, 9000)):
            ct = int((now - timedelta(days=days_ago)).replace(hour=hour, minute=0).timestamp())
            c.execute("INSERT OR REPLACE INTO videos(id, open_id, title, create_time, share_url, view_count, like_count,"
                      " comment_count, share_count) VALUES(?,?,?,?,?,?,?,?,?)",
                      (vid, OID, f"video {vid[-1]}", ct, f"https://t/{vid}", views, views // 10, 3, 2))
        # chuỗi API của video 3: tăng đều ~1.800/ngày 4 ngày (nghi quảng bá)
        for d in range(5):
            t = (now - timedelta(days=4 - d)).replace(hour=23, minute=0).astimezone(timezone.utc).isoformat()
            c.execute("INSERT INTO video_snapshots(video_id, taken_at, view_count, like_count, comment_count, share_count)"
                      " VALUES(?,?,?,?,?,?)", ("7000000000000000003", t, 1800 * d, 0, 0, 0))
        t = now.astimezone(timezone.utc).isoformat()
        c.execute("INSERT INTO video_snapshots(video_id, taken_at, view_count, like_count, comment_count, share_count)"
                  " VALUES(?,?,?,?,?,?)", ("7000000000000000001", t, 10200, 1020, 3, 2))
    pid = packages.save({"goi": "17", "loai": 3, "scene1": "Trà sáng", "caption": "Trà"})
    packages.link_video(pid, "7000000000000000001")
    pid2 = packages.save({"goi": "30", "loai": 1, "scene1": "Lá số", "caption": "Lá số 1984"})
    packages.link_video(pid2, "7000000000000000002")
    return now


def _report(now):
    data = {"schema": "tiktok-studio-quet/v1", "mode": "hang_ngay", "snapshot_at": now.isoformat(timespec="minutes"),
            "run": {"started_at": now.isoformat(), "finished_at": (now + timedelta(minutes=20)).isoformat(),
                    "tokens_est": {"total": 80000}},
            "videos": [
                {"video_id": "7000000000000000001", "goi": "17", "promoted": True,
                 "promo": {"spent": 281679, "views": 9889, "followers": 702},
                 "metrics": {"views": "11K", "likes": 993, "new_followers": 722, "avg_watch_s": 5.37, "completion_rate": 0.023},
                 "retention_pct": {"2": 53, "10": 8}, "traffic_source_pct": {"for_you": 95.7, "following": 1.3, "search": 0.1},
                 "hook": {"h_score": 2}},
                {"video_id": "7000000000000000002", "goi": "30", "promoted": False,
                 "metrics": {"views": 600, "likes": 66, "new_followers": 18, "avg_watch_s": 14.0},
                 "retention_pct": {"2": 61, "10": 30}, "hook": {"h_score": 6}, "comments": {"with_birth": 4}},
                {"video_id": "khong-hop-le"}]}
    return "# Quét kênh hằng ngày\n\n## 1. Tóm tắt\nGói 30 giữ chân 61%.\n\n```json\n" + json.dumps(data) + "\n```\n"


def test_ingest_merge_suspects_diff_and_md(monkeypatch):
    now = _setup()
    rid = chrome_reports.add(_report(now))
    assert consensus.ingest(rid) == 2
    rows = {r["video_id"]: r for r in consensus.merged(OID)}
    a, b = rows["7000000000000000001"], rows["7000000000000000002"]
    # tổng = API 10.200; trả phí 9.889 → tự nhiên 311; follower 722 − 702 = 20
    assert a["api_views"] == 10200 and a["organic_views"] == 311 and a["organic_followers"] == 20 and a["promoted"] == 1
    assert b["promoted"] == 0 and b["organic_views"] == 600 and b["organic_followers"] == 18 and b["follow_rate_org"] == 3.0
    assert a["goi"] == "17" and b["loai"] == 1
    sus = consensus.promo_suspects(OID)
    assert [s["video_id"] for s in sus] == ["7000000000000000003"] and "tăng đều" in sus[0]["reasons"][0]
    d = {x["video_id"]: x for x in consensus.diffs()}
    assert d["7000000000000000001"]["studio_views"] == 11000 and d["7000000000000000001"]["views_pct"] == 7.8
    md = consensus.build_md(OID)
    for s in ("BÁO CÁO ĐỒNG THUẬN", "Bảng video ghép", "So sánh nhóm", "Loại: Loại 1 (ít dữ liệu)", "nghi được Quảng bá",
              "7000000000000000003", "Chênh lệch API ↔ Studio", "Gói 30 giữ chân 61%", "dong-thuan/v1", "**CÓ**"):
        assert s in md, s
    # chỉ video tự nhiên vào so sánh nhóm: Loại 3 (Gói 17 có quảng bá) không xuất hiện
    assert "Loại: Loại 3" not in md
    ctx = chrome_reports.context_md(14)
    assert "BẮT BUỘC kiểm trang Quảng bá" in ctx and "7000000000000000003" in ctx

    sent = {}
    monkeypatch.setattr("app.notebooklm.push_drive", lambda doc, text: sent.update(doc=doc, text=text))
    assert consensus.after_report(rid) == "ok" and sent["doc"] == settings.consensus_doc_gemini and "dong-thuan/v1" in sent["text"]


def test_routes_and_strategy_prompt(monkeypatch):
    from fastapi.testclient import TestClient
    from app import strategy
    from app.main import app

    now = _setup()
    monkeypatch.setattr("app.notebooklm.push_drive", lambda doc, text: None)
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    r = c.post("/danh-gia", data={"text": _report(now)}, follow_redirects=False)
    assert r.status_code == 303
    import time
    for _ in range(50):
        if db.query("SELECT 1 FROM chrome_video_metrics"):
            break
        time.sleep(0.05)
    assert c.get("/dong-thuan").status_code == 200 and "Bảng video ghép" in c.get("/dong-thuan").text
    assert c.get("/dong-thuan.md").text.startswith("# BÁO CÁO ĐỒNG THUẬN")
    assert c.post("/dong-thuan/gui", follow_redirects=False).status_code == 303
    prompt = strategy._build_prompt(OID, "")
    assert "SỐ LIỆU ĐỒNG THUẬN" in prompt and "Bảng video ghép" in prompt


def test_full_scan_batches():
    from fastapi.testclient import TestClient
    from app.main import app

    now = _setup()
    with db.tx() as c:
        c.execute("DELETE FROM chrome_video_metrics")
        c.execute("DELETE FROM chrome_reports")
        for i in range(12):  # thêm 12 video cũ → tổng 15
            ct = int((now - timedelta(days=200 + i)).timestamp())
            c.execute("INSERT OR REPLACE INTO videos(id, open_id, title, create_time, view_count) VALUES(?,?,?,?,?)",
                      (f"71000000000000000{i:02d}", OID, f"cu {i}", ct, 300))
    md = chrome_reports.full_scan_md(10)
    assert "còn lại: 15" in md and "ĐỢT KẾ TIẾP: quét đúng 10 video" in md
    nxt = md.split("## ĐỢT KẾ TIẾP")[1].split("## Tất cả video")[0]
    assert "7000000000000000002" in nxt  # mới nhất trước
    rid = chrome_reports.add(_report(now))  # báo cáo có 2 video
    consensus.ingest(rid)
    md2 = chrome_reports.full_scan_md(10)
    assert "còn lại: 13" in md2 and "7000000000000000002" not in md2.split("## Tất cả video")[0]
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    assert "quét TOÀN BỘ" in c.get("/danh-gia/toan-bo").text
    import io, zipfile
    skill = zipfile.ZipFile(io.BytesIO(c.get("/danh-gia/skill.zip").content)).read("tiktok-studio-quet/SKILL.md").decode()
    assert "/danh-gia/toan-bo" in skill and "toàn bộ" in skill
