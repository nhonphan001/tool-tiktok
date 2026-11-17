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
    md = report.build_report(seeded)
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
