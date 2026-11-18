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
    for path in ["/", "/videos?sort=view_count", "/analytics", "/strategy", "/report", "/settings", "/videos/demo001",
                 "/compliance", "/products", "/videos?issues=1&untagged=1&group=1&element=Kim&sort=like_view"]:
        r = c.get(path)
        assert r.status_code == 200, path
    assert c.get("/api/overview").json()["latest"]
    c.post("/settings", data={"channel_context": "Tiệm trà"})
    assert settings.channel_context == "Tiệm trà"
    assert "Tiệm trà" in c.get("/settings").text
    c.post("/settings", data={"channel_context": ""})
    assert settings.channel_context.startswith("Kênh Tiệm Trà Giải Mã")  # trống = định vị mặc định


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



def test_compliance_rules():
    from app import compliance

    bad = ["Xem lá số tại Link Bio nhé", "tra ở trang tiểu sử", "nangtamchatluongsong.vn", "ib zalo cô",
           "mua trên Shopee", "Lazada có bán", "l.i.n.k ở b i o", "vào web của cô", "https://abc.xyz"]
    for t in bad:
        assert compliance.check(t, True)["level"] == "violation", t
    ok = ["bấm giỏ hàng góc trái", "để lại ngày sinh dưới bình luận để Cô Kim giải mã", "Tuổi Tý năm 2026 #battu",
          "dòng suối, ngọn đèn trên sa bàn"]
    for t in ok:
        assert compliance.check(t, True)["level"] == "ok", t
    assert compliance.check("vòng giúp chiêu tài", True)["level"] == "warning"
    assert compliance.check("xem trang cá nhân của Cô Kim", False)["level"] == "warning"
    assert compliance.check("Shopee", None)["level"] == "violation_if_cart"
    # web app
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    r = c.post("/compliance/check", data={"text": "Xem link bio", "has_cart": "1"})  # tự theo redirect
    assert "VI PHẠM" in r.text


def test_system_prompt_has_rules():
    assert "Link Bio" in strategy.full_system_prompt()
    assert "bấm giỏ hàng góc trái" in strategy.full_system_prompt()


def test_tags_and_kpi(seeded):
    from app import kpi, report, tags

    tags.save("demo001", {"goi": "13", "product_code": "", "element": "Thủy", "content_group": "2", "has_cart": "1",
                          "note": ""})
    t = tags.get_all()["demo001"]
    assert t["content_group"] == 2 and t["has_cart"] == 1 and t["source"] == "manual"
    ta = tags.tag_analysis(seeded)
    assert ta["tagged"] >= 1 and ta["by_element"][0]["key"] == "Thủy"
    k = kpi.summary(seeded)
    assert len(k["targets"]) == 2 and k["targets"][0]["current"] > 0
    assert {s["label"] for s in k["slots"]} >= {"Khung 07:00", "Khung 12:00", "Khung 19:30", "Ngoài khung"}
    md = report.build_report(seeded)
    assert "## KPI" in md and "không làm tròn" in md and "Kiểm tra tuân thủ" in md and "Hiệu quả theo nhãn" in md
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    c.post("/videos/demo002/tags", data={"goi": "7", "content_group": "5", "element": "Hỏa", "has_cart": "0",
                                         "product_code": "", "note": "x"})
    assert tags.get_all()["demo002"]["goi"] == "7"
    assert "Mốc 5.000 follower" in c.get("/").text


def test_classify_job(seeded, monkeypatch):
    import json as _json
    import time as _t

    from app import jobs, tags

    def fake(prompt, system=None, json_mode=False):
        assert json_mode
        ids = [line.split(" | ")[0] for line in prompt.split("VIDEO (id | tiêu đề | caption):\n")[1].splitlines()]
        return _json.dumps([{"id": i, "content_group": 1, "element": "Moc", "product_code": "FAKE",
                             "has_cart": None, "goi": ""} for i in ids]), dict(strategy.EMPTY_USAGE, total_tokens=5)

    monkeypatch.setattr(strategy, "call_gemini", fake)
    jid = jobs.start("classify", tags.classify, seeded)
    for _ in range(50):
        if db.query_one("SELECT status FROM jobs WHERE id=?", (jid,))["status"] != "pending":
            break
        _t.sleep(0.1)
    job = db.query_one("SELECT * FROM jobs WHERE id=?", (jid,))
    assert job["status"] == "done", job["message"]
    all_tags = tags.get_all()
    assert all_tags["demo001"]["source"] == "manual"  # không ghi đè nhãn tay
    ai = [t for t in all_tags.values() if t["source"] == "ai"]
    assert ai and ai[0]["element"] == "Mộc" and ai[0]["product_code"] == ""  # mã không có trong bảng -> bỏ
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    fin = c.get("/api/jobs").json()["finished"]
    assert any(f.get("type") == "job" and f["id"] == jid for f in fin)


def test_products_csv(monkeypatch):
    from app import products

    csv_text = "Bảng sản phẩm\nMã SP,Hành,Tên sản phẩm,Giá,Link TikTok,Trạng thái\n" \
               "SP-THUY-02,Thủy,Vòng thạch anh tóc đen thiên nhiên,250k,https://vt.tiktok.com/x/,Đang bán\n" \
               "SP-HOA-04,HỎA,Vòng Tay Chu Sa,300k,,Chờ link\n,,,,,\n"

    class R:
        status_code = 200
        content = csv_text.encode("utf-8")

    monkeypatch.setattr(products.httpx, "get", lambda *a, **k: R())
    monkeypatch.setattr(settings, "product_csv_url", "https://example.com/x.csv")
    msg, _ = products.sync()
    assert "2 sản phẩm" in msg and "1 mã chưa có link" in msg
    p = products.by_code()
    assert p["SP-THUY-02"]["element"] == "Thủy" and p["SP-HOA-04"]["element"] == "Hỏa"
    assert p["SP-THUY-02"]["link"].startswith("https://")


def test_public_api(seeded, monkeypatch):
    c = TestClient(app)
    assert c.get("/api/public/summary").status_code == 401
    monkeypatch.setattr(settings, "api_token", "secret-token")
    assert c.get("/api/public/summary?token=wrong").status_code == 401
    r = c.get("/api/public/summary", headers={"x-api-token": "secret-token"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "*"
    d = r.json()
    assert d["latest"]["follower_count"] > 0 and "kpi" in d and "videos" in d
    assert "## KPI" in c.get("/api/public/report.md?token=secret-token").text


def test_fortune_amulet_rules():
    """Video bị TikTok từ chối quảng bá ngày 18/11/2026 (bói toán + bùa hộ mệnh)."""
    from app import compliance

    cap = ("khi lá số Bát Tự thiếu hụt nguồn năng lượng Kim sáng suốt, bạn rất dễ lo âu. Mang theo Lá Bồ Đề Mạ Vàng "
           "bên mình sẽ giúp nhắc tâm luôn tĩnh tại và nhẹ nhàng đón điều lành. Bấm vào Giỏ hàng góc trái "
           "#PhongThuyBinhAn")
    r = compliance.check(cap, True)
    assert r["level"] == "fortune_risk" and r["no_ads"]
    assert {"bu_khuyet_la_so", "may_man_tai_loc", "binh_an"} <= {x["code"] for x in r["fortune"]}
    for t in ["Lá bùa hộ mệnh", "giúp trấn trạch, hóa giải vận hạn", "chắc chắn sẽ gặp quý nhân",
              "đeo vòng để bổ sung hành Thủy"]:
        assert compliance.check(t, True)["level"] == "fortune_risk", t
    for t in ["Vòng thạch anh tóc đen thiên nhiên, hạt 8mm, dây co giãn. Bấm giỏ hàng góc trái",
              "Chào buổi sáng, chúc cả nhà một ngày may mắn", "Đêm Trà Giải Mã cùng Cô Kim"]:
        assert compliance.check(t, True)["level"] == "ok", t
    assert compliance.check("Xem link bio", True)["level"] == "violation"  # vi phạm nặng hơn vẫn ưu tiên


def test_rules_default_not_frozen(seeded):
    from app import config as cfg

    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    c.post("/settings", data={"content_rules": cfg._default_text("content_rules.md", "CONTENT_RULES")})
    assert db.load_settings().get("content_rules") == ""
    assert "Lá Bồ Đề" in settings.content_rules and "bói toán" in strategy.full_system_prompt()
