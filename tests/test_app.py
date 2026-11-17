import os

os.environ["DATABASE_PATH"] = ":memory:"
os.environ["DISABLE_SCHEDULER"] = "1"
os.environ["APP_PASSWORD"] = "pw"
os.environ["NOTEBOOKLM_MODE"] = "local"
os.environ["GEMINI_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import analytics, db, demo, report, scanner, strategy  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    settings.export_dir = str(tmp_path_factory.mktemp("exports"))
    db.reset_connection()
    demo.seed(days=10, n_videos=20)
    return demo.DEMO_ID


def test_engagement():
    assert analytics.engagement({"view_count": 100, "like_count": 5, "comment_count": 3, "share_count": 2}) == 0.1
    assert analytics.engagement({"view_count": 0}) == 0


def test_overview_and_analysis(seeded):
    ov = analytics.overview(seeded)
    assert ov["latest"]["follower_count"] > 0
    assert ov["deltas"]["24h"]["follower_count"] > 0
    an = analytics.deep_analysis(seeded)
    assert len(an["weekday"]) == 7 and len(an["hour"]) == 24
    assert an["insights"]


def test_scan_and_velocity(seeded):
    res = scanner.run_scan("test")
    assert res["status"] == "ok"
    assert analytics.recent_velocity(seeded)
    files = os.listdir(settings.export_dir)
    assert "tiktok_report_latest.md" in files


def test_report_and_strategy_fallback(seeded):
    settings.channel_context = "Kênh trà thảo mộc"
    md = report.build_report(seeded)
    assert "Kênh trà thảo mộc" in md
    settings.channel_context = ""
    assert "Báo cáo kênh TikTok" in md and "| Ngày |" in md
    res = strategy.generate(seeded, "test")
    assert res["source"] == "rule" and "Hành động đề xuất" in res["content_md"]


def test_web_pages(seeded):
    c = TestClient(app)
    assert c.get("/privacy").status_code == 200 and c.get("/terms").status_code == 200
    assert c.get("/", follow_redirects=False).status_code == 303
    assert c.post("/login", data={"password": "bad"}).status_code == 401
    c.post("/login", data={"password": "pw"})
    for path in ["/", "/videos?sort=view_count", "/analytics", "/strategy", "/report", "/settings", "/videos/demo001"]:
        r = c.get(path)
        assert r.status_code == 200, path
    assert c.get("/api/overview").json()["latest"]
    c.post("/settings", data={"channel_context": "Tiệm trà"})
    assert settings.channel_context == "Tiệm trà"
    assert "Tiệm trà" in c.get("/settings").text
    c.post("/settings", data={"channel_context": ""})
    assert settings.channel_context == ""


def test_tiktok_verify_file(tmp_path, monkeypatch):
    from app import main

    monkeypatch.setattr(main, "VERIFY_DIR", str(tmp_path))
    (tmp_path / "tiktokAbC123.txt").write_text("tiktok-developers-site-verification=xyz")
    c = TestClient(app)
    r = c.get("/tiktokAbC123.txt")
    assert r.status_code == 200 and "verification=xyz" in r.text
    assert c.get("/tiktokMissing.txt").status_code == 404
    assert c.get("/tiktok..%2Fsecret.txt").status_code == 404


def test_localtime_vietnam():
    settings.timezone = "Asia/Ho_Chi_Minh"
    assert analytics.localtime("2026-11-17T07:30:20+00:00") == "17/11/2026 14:30"
    assert analytics.localtime(None) == "—"


def test_gemini_backend_url(monkeypatch):
    calls = {}

    class R:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

    def fake_post(url, **kw):
        calls["url"] = url
        calls["headers"] = kw["headers"]
        return R()

    monkeypatch.setattr(strategy.httpx, "post", fake_post)
    monkeypatch.setattr(settings, "gemini_api_key", "AQ.test")
    monkeypatch.setattr(settings, "gemini_model", "gemini-x-flash")
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    assert strategy.call_gemini("hi")[0] == "ok"
    assert calls["url"] == "https://aiplatform.googleapis.com/v1/publishers/google/models/gemini-x-flash:generateContent"
    assert calls["headers"]["x-goog-api-key"] == "AQ.test"
    monkeypatch.setattr(settings, "gemini_backend", "aistudio")
    strategy.call_gemini("hi")
    assert calls["url"].startswith("https://generativelanguage.googleapis.com/")


class _FakeResp:
    status_code = 200

    def json(self):
        return {
            "candidates": [{"content": {"parts": [{"text": "suy nghĩ", "thought": True}, {"text": "## Chiến lược AI"}]}}],
            "usageMetadata": {"promptTokenCount": 10000, "candidatesTokenCount": 2000, "thoughtsTokenCount": 1000,
                              "totalTokenCount": 13000},
        }


def test_background_strategy_with_usage(seeded, monkeypatch):
    import time as _t

    monkeypatch.setattr(strategy.httpx, "post", lambda url, **kw: _FakeResp())
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "gemini_price_input", 0.30)
    monkeypatch.setattr(settings, "gemini_price_output", 2.50)
    monkeypatch.setattr(settings, "usd_vnd_rate", 26000)
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    r = c.post("/strategy/generate", data={"goal": "test nền"}, follow_redirects=False)
    assert r.status_code == 303
    sid = int(r.headers["location"].split("id=")[1])
    for _ in range(50):
        row = db.query_one("SELECT * FROM strategies WHERE id=?", (sid,))
        if row["status"] != "pending":
            break
        _t.sleep(0.1)
    assert row["status"] == "done" and row["source"] == "gemini"
    assert row["content_md"] == "## Chiến lược AI"  # bỏ phần "thought"
    assert row["total_tokens"] == 13000
    # 10000*0.30/1e6 + 3000*2.50/1e6 = 0.003 + 0.0075
    assert abs(row["cost_usd"] - 0.0105) < 1e-9
    jobs = c.get("/api/jobs").json()
    assert any(f["id"] == sid and f["cost_vnd"] == 273 for f in jobs["finished"])
    assert not any(f["id"] == sid for f in c.get("/api/jobs").json()["finished"])  # chỉ báo 1 lần
    page = c.get(f"/strategy?id={sid}").text
    assert "13.000" in page and "273 ₫" in page
    assert strategy.usage_summary()["month"]["calls"] >= 1


def test_migrate_old_db(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE strategies (id INTEGER PRIMARY KEY, open_id TEXT, created_at TEXT, source TEXT,"
                 " model TEXT, goal TEXT, content_md TEXT)")
    conn.execute("INSERT INTO strategies(open_id, created_at, source, content_md) VALUES('x','2026-01-01','rule','a')")
    conn.commit()
    conn.close()
    old = settings.database_path
    settings.database_path = str(path)
    db.reset_connection()
    try:
        row = db.query_one("SELECT status, cost_usd FROM strategies")
        assert row == {"status": "done", "cost_usd": 0}
    finally:
        db.reset_connection()
        settings.database_path = old
