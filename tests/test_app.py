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


def test_pricing_table(monkeypatch):
    from app import pricing

    monkeypatch.setattr(settings, "gemini_price_input", 0)
    monkeypatch.setattr(settings, "gemini_price_output", 0)
    assert pricing.price_for("gemini-3.8-flash", "vertex", "2026-11-18")[:2] == (0.825, 4.125)
    assert pricing.price_for("gemini-3.8-flash", "aistudio", "2026-11-18")[:2] == (0.75, 3.75)
    assert pricing.price_for("gemini-3.8-flash", "vertex", "2027-01-01")[:2] == (1.65, 8.25)
    assert pricing.price_for("gemini-3.8-flash", "aistudio", "2027-03-01")[:2] == (1.50, 7.50)
    assert pricing.price_for("model-la", "vertex")[:2] == (0.0, 0.0)
    # 12.000 vào + (3.500 ra + 1.500 suy luận) qua Vertex theo vùng, 18/11/2026
    c = strategy.estimate_cost(12000, 3500, 1500, "gemini-3.8-flash", "vertex", "2026-11-18T08:00:00+00:00")
    assert abs(c - (12000 * 0.825 + 5000 * 4.125) / 1e6) < 1e-12
    monkeypatch.setattr(settings, "gemini_price_input", 1.0)
    monkeypatch.setattr(settings, "gemini_price_output", 2.0)
    assert pricing.price_for("gemini-3.8-flash", "vertex")[2] == "nhập tay trong Cài đặt"


def test_recompute_costs(seeded, monkeypatch):
    monkeypatch.setattr(settings, "gemini_price_input", 0)
    monkeypatch.setattr(settings, "gemini_price_output", 0)
    with db.tx() as c:
        sid = c.execute(
            "INSERT INTO strategies(open_id, created_at, source, model, goal, content_md, status, input_tokens,"
            " output_tokens, thinking_tokens, total_tokens, cost_usd) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (seeded, "2026-11-17T08:58:00+00:00", "gemini", "gemini-3.8-flash", "", "x", "done", 10000, 2000, 1000,
             13000, 0.0105),
        ).lastrowid
        c.execute(
            "INSERT INTO ai_usage(created_at, kind, ref_id, backend, model, input_tokens, output_tokens,"
            " thinking_tokens, total_tokens, cost_usd) VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("2026-11-17T08:58:00+00:00", "strategy", sid, "vertex", "gemini-3.8-flash", 10000, 2000, 1000, 13000,
             0.0105),
        )
    strategy.recompute_costs()
    want = (10000 * 0.825 + 3000 * 4.125) / 1e6
    assert abs(db.query_one("SELECT cost_usd FROM strategies WHERE id=?", (sid,))["cost_usd"] - want) < 1e-12
    assert abs(db.query_one("SELECT cost_usd FROM ai_usage WHERE ref_id=?", (sid,))["cost_usd"] - want) < 1e-12


def test_vertex_global_option_and_fallback(seeded, monkeypatch):
    import time as _t

    monkeypatch.setattr(settings, "gemini_api_key", "AQ.k")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.8-flash")
    monkeypatch.setattr(settings, "gemini_backend", "vertex")
    monkeypatch.setattr(settings, "gemini_price_input", 0)
    monkeypatch.setattr(settings, "gemini_price_output", 0)
    ok_body = {"candidates": [{"content": {"parts": [{"text": "## KQ"}]}}],
               "usageMetadata": {"promptTokenCount": 10000, "candidatesTokenCount": 2000, "thoughtsTokenCount": 0}}
    calls = []

    class R:
        def __init__(self, code, body):
            self.status_code, self._b = code, body

        def json(self):
            return self._b

    def fake_ok(url, **kw):
        calls.append(url)
        return R(200, ok_body)

    # global tắt (mặc định) hoặc thiếu mã project -> theo vùng
    monkeypatch.setattr(settings, "gemini_vertex_location", "global")
    monkeypatch.setattr(settings, "gemini_vertex_project", "")
    assert strategy.planned_endpoint() == "vertex"
    # global bật -> URL global, giá global
    monkeypatch.setattr(settings, "gemini_vertex_project", "nangtam-gemini")
    monkeypatch.setattr(strategy.httpx, "post", fake_ok)
    text, usage = strategy.call_gemini("hi")
    assert calls[-1] == ("https://aiplatform.googleapis.com/v1/projects/nangtam-gemini/locations/global/"
                         "publishers/google/models/gemini-3.8-flash:generateContent")
    assert usage["endpoint"] == "vertex_global" and usage["endpoint_note"] == ""
    assert abs(usage["cost_usd"] - (10000 * 0.75 + 2000 * 3.75) / 1e6) < 1e-12

    # global lỗi -> tự gọi lại theo vùng, có ghi chú, giá theo vùng
    def fake_fallback(url, **kw):
        calls.append(url)
        if "/locations/global/" in url:
            return R(403, {"error": {"message": "Permission denied on global"}})
        return R(200, ok_body)

    monkeypatch.setattr(strategy.httpx, "post", fake_fallback)
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    r = c.post("/strategy/generate", data={"goal": "vùng"}, follow_redirects=False)
    sid = int(r.headers["location"].split("id=")[1])
    for _ in range(50):
        row = db.query_one("SELECT * FROM strategies WHERE id=?", (sid,))
        if row["status"] != "pending":
            break
        _t.sleep(0.1)
    assert row["source"] == "gemini" and row["endpoint"] == "vertex"
    assert "global lỗi (HTTP 403" in row["endpoint_note"]
    assert abs(row["cost_usd"] - (10000 * 0.825 + 2000 * 4.125) / 1e6) < 1e-12
    page = c.get(f"/strategy?id={sid}").text
    assert "Vertex AI · theo vùng" in page and "global lỗi" in page
    fin = [f for f in c.get("/api/jobs").json()["finished"] if f.get("type") == "strategy" and f["id"] == sid]
    assert fin and fin[0]["endpoint_label"].startswith("Vertex AI · theo vùng")
    assert "Sẽ gọi: Vertex AI · global" in c.get("/strategy").text


def test_laso_page_and_comments(seeded, monkeypatch):
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    r = c.get("/laso?dd=5&mm=6&yy=1995&t=18:00&gioi=nu")
    assert r.status_code == 200 and "Kỷ Dậu" in r.text and "Nhật chủ Đinh Hỏa" in r.text
    assert "không có ngày 31" in c.get("/laso?dd=31&mm=2&yy=1995").text
    r = c.post("/laso/comments", data={"text": "Cô ơi xem giúp con 5/6/1995 giờ Dậu nữ ạ\nchồng 14/5/1991 4h, vợ 13/4/1995 âm lịch 6h30\nsn 1988"})
    assert r.status_code == 200
    assert "Ất Hợi – Tân Tỵ – Đinh Mão – Kỷ Dậu" in r.text and "Tân Mùi – Quý Tỵ – Giáp Thân – Bính Dần" in r.text
    assert "Ất Hợi – Tân Tỵ – Quý Mão – Ất Mão" in r.text and "Chỉ có năm sinh 1988" in r.text
    assert db.query_one("SELECT COUNT(*) AS n FROM app_settings WHERE value LIKE '%1995%'")["n"] == 0  # không lưu
    assert c.get("/api/public/laso?dd=5&mm=6&yy=1995").status_code == 401
    monkeypatch.setattr(settings, "api_token", "tk")
    j = c.get("/api/public/laso?dd=13&mm=4&yy=1995&t=06:00&lich=am&token=tk").json()
    assert j["tu_tru"] == "Ất Hợi – Tân Tỵ – Quý Mão – Ất Mão" and j["nhat_chu"] == "Quý"


def _seed_products():
    with db.tx() as c:
        c.execute("DELETE FROM products")
        c.execute("INSERT INTO products(code, element, name, link, status) VALUES(?,?,?,?,?)",
                  ("SP-THUY-02", "Thủy", "Vòng thạch anh tóc đen thiên nhiên", "https://vt.tiktok.com/x/", "Đang bán"))
        c.execute("INSERT INTO products(code, element, name, link, status) VALUES(?,?,?,?,?)",
                  ("SP-HOA-04", "Hỏa", "Vòng Tay Chu Sa Ngũ Lộ Thần Tài", "", "Chờ link"))


def test_package_checks_catch_known_mistakes(seeded):
    from app import packages

    _seed_products()
    # Gói lá số: kịch bản ghi nhầm Nhật chủ bằng can năm (lỗi Gói 3/13) + gắn SKU
    p = {"goi": "13", "loai": 1, "content_group": 1, "sku": "SP-THUY-02",
         "birth": {"dd": "5", "mm": "6", "yy": "1995", "t": "18:00", "lich": "duong", "gioi": "nu"},
         "scene1": "Lá số Ất Hợi – Tân Tỵ – Đinh Mão – Kỷ Dậu, Nhật chủ Ất Mộc nên cần thêm nước.",
         "caption": "Để lại ngày sinh dưới bình luận để Cô Kim giải mã #BatTu"}
    chk = packages.check(p)
    msgs = " | ".join(i["msg"] for i in chk["items"])
    assert "Nhật chủ Ất" in msgs and "Nhật chủ là Đinh" in msgs
    assert "không gắn giỏ hàng" in msgs and chk["errors"] >= 2 and not chk["ads_ok"]
    assert chk["hanh"] == "Thủy"
    p2 = dict(p, sku="", scene1="Nhật chủ Đinh Hỏa, lá số thiếu Thủy nên đeo vòng thạch anh sẽ giúp tâm an.")
    assert any(i["rule"] == "B.4.1" for i in packages.check(p2)["items"])
    p3 = dict(p, sku="", scene1="Nhật chủ Đinh Hỏa như ngọn đèn nhỏ giữa mùa hạ, cần dòng nước mát để cân bằng.")
    assert not any(i["rule"] == "B.4.1" for i in packages.check(p3)["items"])

    # Gói sản phẩm: nói lá số + tên SKU sai + bùa → nhiều lỗi
    bad = {"goi": "14", "loai": 2, "sku": "SP-THUY-02", "product_name": "Vòng Obsidian",
           "scene1": "Lá số thiếu Thủy thì đeo vòng này bổ sung hành Thủy, như lá bùa hộ mệnh.",
           "caption": "Xem thêm ở link bio nhé"}
    chk = packages.check(bad)
    rules = {i["rule"] for i in chk["items"] if i["level"] == "error"}
    assert {"B.1", "B.3", "B.4", "B.4.3"} <= rules and not chk["ads_ok"]

    # Gói sản phẩm sạch: đạt, được chạy quảng cáo
    good = {"goi": "15", "loai": 2, "sku": "SP-THUY-02", "product_name": "Vòng thạch anh tóc đen thiên nhiên",
            "scene1": "Vòng thạch anh tóc đen thiên nhiên, hạt tám ly, dây co giãn, hợp phối đồ màu tối đi làm hay đi chơi đều xinh nha cả nhà.",
            "caption": "Vòng thạch anh tóc đen thiên nhiên, hạt 8mm. Bấm giỏ hàng góc trái nhé! "
                       "Để lại ngày sinh dưới bình luận để Cô Kim giải mã"}
    chk = packages.check(good)
    assert chk["errors"] == 0 and chk["ads_ok"], chk["items"]
    blk = packages.nhan_video_block(good, chk)
    assert "ma_san_pham: SP-THUY-02" in blk and "duoc_chay_quang_cao: true" in blk and "hanh_dung_than: Thủy" in blk


def test_package_pages_link_and_auto_link(seeded):
    from app import packages, tags

    _seed_products()
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    assert c.get("/packages").status_code == 200
    r = c.get("/packages/new?dd=5&mm=6&yy=1995&t=18:00&gioi=nu")
    assert r.status_code == 200 and "Kỷ Dậu" in r.text
    r = c.post("/packages/save", data={"goi": "21", "title": "Thử", "loai": "1", "content_group": "1", "dd": "5",
                                       "mm": "6", "yy": "1995", "t": "18:00", "gioi": "nu",
                                       "scene1": "Nhật chủ Đinh Hỏa như ngọn đèn nhỏ", "caption": "x"},
               follow_redirects=False)
    pid = int(r.headers["location"].rsplit("/", 1)[1])
    page = c.get(f"/packages/{pid}").text
    assert "nhan_video:" in page and "goi: 21" in page
    md = c.get(f"/packages/{pid}/phieu.md")
    assert md.status_code == 200 and "Phiếu gói 21" in md.text and "Nhật chủ = can trụ Ngày" in md.text
    c.post(f"/packages/{pid}/link", data={"video_id": "demo003"})
    t = tags.get_all()["demo003"]
    assert t["goi"] == "21" and t["source"] == "package" and t["element"] == "Thủy" and t["has_cart"] == 0
    # tự khớp theo caption sau khi quét
    cap = "Vòng thạch anh tóc đen thiên nhiên hạt 8mm cho nàng công sở, bấm giỏ hàng góc trái nhé #TiemTraGiaiMa"
    with db.tx() as cx:
        cx.execute("UPDATE videos SET description=? WHERE id='demo010'", (cap,))
    pid2 = packages.save({"goi": "22", "loai": "2", "caption": cap})
    linked = packages.auto_link(seeded)
    assert (pid2, "demo010") in linked and packages.get(pid2)["link_source"] == "auto"
    assert "Gói sản xuất gần đây" in report.build_report(seeded)


def test_fixed_scan_times(monkeypatch):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from app import scheduler

    assert scheduler.parse_times("23:00, 05:00,11:00;17:00, 25:00, x") == [(5, 0), (11, 0), (17, 0), (23, 0)]
    monkeypatch.setattr(settings, "scan_times", "05:00,11:00,17:00,23:00")
    monkeypatch.setattr(settings, "timezone", "Asia/Ho_Chi_Minh")
    trig, label = scheduler.build_trigger()
    assert label == "giờ cố định 05:00, 11:00, 17:00, 23:00"
    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    nxt = trig.get_next_fire_time(None, datetime(2026, 11, 18, 12, 30, tzinfo=tz))
    assert nxt.astimezone(tz).hour == 17 and nxt.astimezone(tz).minute == 0
    monkeypatch.setattr(settings, "scan_times", "")
    assert scheduler.build_trigger()[1].startswith("mỗi ")


def test_khuyet_hanh_rule():
    from app import compliance

    assert compliance.check("Lá số khuyết Kim nên đeo vòng bạc", True)["level"] == "fortune_risk"
    assert compliance.check("khuyết hành Hỏa", True)["level"] == "fortune_risk"


def test_check_drive_without_key(monkeypatch, tmp_path):
    from app import notebooklm

    monkeypatch.setattr(settings, "google_service_account_file", str(tmp_path / "none.json"))
    res = notebooklm.check_drive()
    assert not res[0]["ok"] and "service account" in res[0]["msg"]
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    r = c.post("/settings/test-drive")
    assert r.status_code == 200 and "Không đọc được file service account" in r.text


def test_drive_check_and_push_mocked(seeded, monkeypatch, tmp_path):
    import json as _json

    from app import notebooklm

    keyf = tmp_path / "sa.json"
    keyf.write_text(_json.dumps({"client_email": "gemini-caller-229@nangtam-gemini.iam.gserviceaccount.com"}))
    monkeypatch.setattr(settings, "google_service_account_file", str(keyf))
    monkeypatch.setattr(settings, "google_doc_id_report", "DOC_R")
    monkeypatch.setattr(settings, "google_doc_id_strategy", "DOC_S")

    class Creds:
        token = "tok"

    monkeypatch.setattr(notebooklm, "_credentials", lambda scopes: Creds())

    class R:
        def __init__(self, code, body):
            self.status_code, self._b, self.text = code, body, _json.dumps(body)

        def json(self):
            return self._b

    def fake_get(url, **kw):
        if url.endswith("DOC_R"):
            return R(200, {"name": "BAO_CAO_TIKTOK_MANAGER", "capabilities": {"canEdit": True}})
        return R(200, {"name": "CHIEN_LUOC_TIKTOK_MANAGER", "capabilities": {"canEdit": False}})

    monkeypatch.setattr(notebooklm.httpx, "get", fake_get)
    res = notebooklm.check_drive()
    assert res[1]["ok"] and "có quyền sửa" in res[1]["msg"]
    assert not res[2]["ok"] and "CHỈ XEM" in res[2]["msg"]

    sent = []

    def fake_patch(url, content=None, headers=None, timeout=None):
        sent.append((url, headers, content))
        return R(200, {})

    monkeypatch.setattr(notebooklm.httpx, "patch", fake_patch)
    monkeypatch.setattr(settings, "notebooklm_mode", "drive")
    out = notebooklm.sync_all(seeded)
    assert [o["status"] for o in out] == ["ok", "ok"]
    assert sent[0][0].startswith("https://www.googleapis.com/upload/drive/v3/files/DOC_R?uploadType=media")
    assert sent[0][1]["Content-Type"].startswith("text/html")
    assert "<table>" in sent[0][2].decode("utf-8") and "## KPI" not in sent[0][2].decode("utf-8")


def test_public_dashboard_files(seeded, monkeypatch):
    c = TestClient(app)
    monkeypatch.setattr(settings, "api_token", "tk")
    assert c.get("/api/public/dashboard/tiktok_kenh.json").status_code == 401
    assert c.get("/api/public/dashboard/x.json?token=tk").status_code == 404
    for n in ("tiktok_kenh", "tiktok_kpi", "tiktok_khung_gio", "tiktok_video", "tiktok_tuan_thu"):
        j = c.get(f"/api/public/dashboard/{n}.json", headers={"x-api-token": "tk"}).json()
        assert "rows" in j and "meta" in j, n
    assert c.get("/api/public/dashboard/tiktok_kenh.json?token=tk").json()["rows"][0]["follower"] > 0


REAL_ROWS = [  # dữ liệu thật của bảng quản trị ngày 18/11 (cột A..N) + cột O "Tên dùng trong video" đề xuất
    ["SP-THUY-01", "Thủy", "Vòng Đá Aquamarine Xanh Biếc Hải Lam", "Vòng tay đá tự nhiên", "Xanh nước biển trong (Aquamarine)",
     "Hạ nhiệt Hỏa viêm, khơi thông mạch Tài Tinh và giữ tâm trí điềm tĩnh thông suốt",
     "Người khuyết Thủy như lá số này hãy đeo vòng đá Aquamarine xanh biếc Cô Kim ghim sẵn ở giỏ hàng góc trái nhé",
     "389.000 ₫", "15,0%", "https://www.tiktok.com/@tiemtragiaima", "https://shopee.vn", "https://www.lazada.vn",
     "Đang Bật", "Mã gắn giỏ hàng: SP-THUY-01"],
    ["SP-KIM-04", "Kim", "Lá Bồ Đề Mạ Vàng - Mặt Trước Hình Hoa Sen Và Chữ Phúc - Mặt Sau Hình Phật - Kèm Túi Nhung Chữ Lộc Phong Thủy Trang Trí",
     "Vật phẩm hộ mệnh bỏ ví / ốp điện thoại / bàn trà", "Lá Bồ Đề mạ vàng ánh kim kèm túi nhung đỏ thêu chữ Lộc",
     "Bồi đắp Kim khí thanh tịnh kết hợp sắc đỏ Hỏa ấm, giúp tịnh tâm, giữ bình an và tụ phúc lành cuối năm",
     "Lá Bồ Đề mạ vàng khắc hoa sen chữ Phúc kèm túi nhung chữ Lộc ở giỏ hàng góc trái sẽ giúp bạn gửi gắm ước nguyện bình an mỗi ngày",
     "68.000 ₫", "20,0%", "https://vt.tiktok.com/ZS9fokDfBWDLu-Madov/", "Chưa áp dụng", "Chưa áp dụng", "Đang Bật",
     "Mã gắn giỏ hàng: SP-KIM-04", "Lá bồ đề mạ vàng kèm túi nhung đỏ"],
]


def test_products_sheet_video_name_and_audit(seeded, monkeypatch):
    from app import packages, products

    class R:
        status_code = 200

        def json(self):
            return {"values": REAL_ROWS}

    class Creds:
        token = "t"

    monkeypatch.setattr(settings, "product_csv_url", "")
    monkeypatch.setattr(settings, "product_sheet_id", "SHEET")
    monkeypatch.setattr("app.notebooklm._credentials", lambda scopes: Creds())
    monkeypatch.setattr(products.httpx, "get", lambda *a, **k: R())
    msg, _ = products.sync()
    assert "2 sản phẩm" in msg and "1 mã chưa có link TikTok Shop thật" in msg and "1 mã chưa có “Tên dùng trong video”" in msg
    p = products.by_code()
    assert p["SP-KIM-04"]["video_name"] == "Lá bồ đề mạ vàng kèm túi nhung đỏ"
    assert not products.real_link(p["SP-THUY-01"]["link"]) and products.real_link(p["SP-KIM-04"]["link"])
    a1 = {x["field"] for x in products.audit(p["SP-THUY-01"])}
    assert "Lời thoại gợi ý" in a1  # "Người khuyết Thủy như lá số này hãy đeo…"
    a4 = {x["field"] for x in products.audit(p["SP-KIM-04"])}
    assert {"Phân loại", "Công năng", "Lời thoại gợi ý"} <= a4 and "Tên dùng trong video" not in a4

    pkg = {"goi": "T", "loai": 2, "sku": "SP-KIM-04", "product_name": "Lá bồ đề mạ vàng kèm túi nhung đỏ",
           "scene1": "Lá bồ đề mạ vàng kèm túi nhung đỏ, bấm giỏ hàng góc trái nhé", "caption": "Bấm giỏ hàng góc trái"}
    chk = packages.check(pkg)
    assert not any(i["rule"].startswith("B.3") and i["level"] == "error" for i in chk["items"]), chk["items"]
    assert not chk["ads_ok"] and any("KHÔNG chạy Quảng bá" in i["msg"] for i in chk["items"])  # "Vật phẩm hộ mệnh"
    pkg2 = dict(pkg, sku="SP-THUY-01", product_name="Vòng đá")
    rules = [i for i in packages.check(pkg2)["items"] if i["rule"].startswith("B.3")]
    assert any("link tạm" in i["msg"] for i in rules) and any(i["level"] == "error" for i in rules)
    c = TestClient(app)
    c.post("/login", data={"password": "pw"})
    page = c.get("/products").text
    assert "Tên dùng trong video" in page and "link tạm" in page


def test_system_report_renders():
    from app import system_report
    md = system_report.to_markdown()
    assert "BÁO CÁO TỰ ĐỘNG – TIKTOK MANAGER" in md and "| P1 |" in md and "P13" in md


def test_docs_pages_require_login_and_serve_pdf():
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    r = c.get("/tai-lieu/QUY_TRINH_CHOT_V2.pdf", follow_redirects=False)
    assert r.status_code in (302, 303, 307) and "/login" in r.headers["location"]
    c.post("/login", data={"password": os.environ.get("APP_PASSWORD", "admin")})
    from app.config import settings
    c.post("/login", data={"password": settings.app_password})
    assert "Quy trình luồng tự động" in c.get("/tai-lieu").text
    r = c.get("/tai-lieu/QUY_TRINH_CHOT_V2.pdf")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:4] == b"%PDF"
    assert "P8a" in c.get("/tai-lieu/xem/QUY_TRINH_CHOT_V2.md").text
    assert c.get("/tai-lieu/../../etc/passwd").status_code in (404, 307, 303, 302)


def test_post_plan_suggestions_goi17():
    from app import post_plan
    plan_txt = ("- Mục tiêu Quảng bá (Promote): Tăng người theo dõi (More followers), chạy liên tục 7 ngày (nội dung không gắn ngày). "
                "- Giờ đăng & Giờ bật Quảng bá: - Đăng video tự nhiên lúc 07:00 sáng 19/11. - Chờ video lên kênh và bật chiến dịch "
                "Quảng bá vào 11:00 – 11:30 trưa 19/11. - Đối tượng mục tiêu (Target Audience): - Giới tính: Nữ (70–80% hoặc chọn "
                "Tất cả). - Độ tuổi: 25 – 44 tuổi (nhóm tương tác cao). - Khu vực: Việt Nam (toàn quốc). - Sở thích (Interests): "
                "Trà đạo & Đồ uống, Sống chậm / Thiền định & Thư giãn, Trang trí nhà cửa. - Theo dõi KPI 7 ngày: CPF.")
    g = post_plan.from_ads_plan(plan_txt)
    assert g["gioi_tinh"] == "Nữ" and g["do_tuoi"] == "25 – 44 tuổi" and g["khu_vuc"] == "Việt Nam"
    assert g["so_thich"].startswith("Trà đạo & Đồ uống") and g["so_ngay_qc"] == "7 ngày liên tục"
    assert g["bat_qc_luc"] == "11:00 – 11:30" and g["muc_tieu_qc"].startswith("Người theo dõi")
    p = {"id": 1, "loai": 3, "ads_plan": plan_txt, "post_plan_json": "{}"}
    req = {"opts": {"loai": 3, "goal": "follow", "ads": True, "ads_days": 7, "publish": "Sáng 19/11, 07:00"}}
    s = post_plan.suggest(p, {"ads_ok": True}, req, "12:00")
    assert s["quang_cao"][0] == "Có" and s["gio_hang"][0] == "Không" and s["gioi_tinh"][0] == "Nữ"
    assert s["gio_dang"][0] == "Sáng 19/11, 07:00" and "AI" in s["nhan_ai"][0]
    # Loại 1 không bao giờ quảng cáo, kể cả khi đã lưu "Có"
    s1 = post_plan.suggest({"id": 2, "loai": 1, "post_plan_json": '{"quang_cao": "Có"}'}, {"ads_ok": False}, None, "19:30")
    assert s1["quang_cao"][0].startswith("Không") and s1["gio_dang"][0] == "19:30" and "do_tuoi" not in s1


def test_media_routes_serve_package_images(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import media, packages
    from app.config import settings
    from app.main import app
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"0" * 200)
    calls = []

    def fake_fetch(fid):
        calls.append(fid)
        return str(img), {"name": "CANH.jpg", "mimeType": "image/jpeg"}

    monkeypatch.setattr(media, "fetch", fake_fetch)
    pid = packages.save({"goi": "99", "loai": 3, "scene1": "x", "image1": "1R-eg5lKwn_8rHbMNXGPnmf3na-4K0njV",
                         "image2": "https://drive.google.com/file/d/1tSNE42aBWK32a7pH3fJGZ_I0BpRl2u-v/view"})
    c = TestClient(app)
    assert c.get(f"/media/{pid}/image1", follow_redirects=False).status_code in (302, 303, 307)  # cần đăng nhập
    c.post("/login", data={"password": settings.app_password})
    r = c.get(f"/media/{pid}/image1?download=1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and "attachment" in r.headers["content-disposition"]
    assert c.get(f"/media/{pid}/image3").status_code == 404           # cảnh không có ảnh
    assert c.get(f"/media/{pid}/caption").status_code == 404          # không phải trường media
    z = c.get(f"/media/{pid}/images.zip")
    assert z.status_code == 200 and z.content[:2] == b"PK"
    assert calls[-2:] == ["1R-eg5lKwn_8rHbMNXGPnmf3na-4K0njV", "1tSNE42aBWK32a7pH3fJGZ_I0BpRl2u-v"]
    html = c.get(f"/packages/{pid}").text
    assert f"/media/{pid}/image1" in html and "Tải cả 4 ảnh" in html
