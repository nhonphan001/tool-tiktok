import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import chrome_reports, db, gemini_requests as gr, packages, strategy_plan  # noqa: E402
from app.config import settings  # noqa: E402

S = "Cô Kim rót chén trà nóng mời cả nhà ngồi xuống nghỉ ngơi một chút giữa những ngày cuối năm bận rộn này nha"


def _perf(p):
    return [i["msg"] for i in packages.check(p)["items"] if i["rule"] == "Hiệu suất"]


def test_performance_warnings():
    base = {"goi": "90", "loai": 3, "scene1": S, "scene2": S, "scene3": S,
            "scene4": S + " bấm theo dõi Cô Kim nha", "caption": "Trà sáng", "on_screen": ""}
    msgs = _perf(base)
    assert any("cảnh 1–2" in m for m in msgs) and any("khung hình 0" in m for m in msgs)
    ok = {**base, "scene1": "Bấm theo dõi Cô Kim để mỗi sáng " + S[:60], "on_screen": "Sáng nay chậm lại 30 giây"}
    assert _perf(ok) == []
    assert any("250" in m for m in _perf({**ok, "caption": "x" * 260}))
    assert any("chỉ giờ" in m and "toi nay" in m for m in _perf({**ok, "caption": "Hẹn cả nhà tối nay"}))
    assert any("chỉ giờ" in m for m in _perf({**ok, "caption": "Đăng lúc 19h00"}))
    # lá số nói giờ sinh trong lời thoại → không cảnh báo
    la = {"goi": "91", "loai": 1, "scene1": "Comment năm sinh để Cô Kim xem giúp, chị sinh lúc 19 giờ ngày 20/2/1973 nha",
          "scene2": S, "scene3": S, "on_screen": "Quý Sửu 1973"}
    assert not any("chỉ giờ" in m for m in _perf(la))
    assert not any(i["rule"] == "CTA" for i in packages.check(la)["items"])


def test_ads_paused_letter_and_prefill():
    settings.ads_paused = True
    gr.init()
    rid = gr.create("Trà sáng", "Trà sáng", {"loai": 3, "goal": "follow", "ads": True, "ads_days": 7})
    req = next(r for r in gr.all_requests() if r["id"] == rid)
    letter = gr.build_letter(req)
    assert "Kế hoạch quảng cáo cần đề xuất" not in letter and "giây 3–8" in letter
    settings.ads_paused = False
    assert "Kế hoạch quảng cáo cần đề xuất" in gr.build_letter(req)
    settings.ads_paused = True
    r = strategy_plan._classify({"ngay": "T5 26/11", "gio": "12:30", "chu_de": "Lá số nữ Đinh Mùi 1967", "dinh_dang": "",
                                 "do_dai": "", "hook": "", "hashtag": "", "loai_col": "1"})
    assert strategy_plan.prefill(r)["scenes"] == 7


def test_chrome_reports_roundtrip():
    db.get_conn()
    packages.init()
    pid = packages.save({"goi": "92", "loai": 3, "scene1": S, "caption": "Trà sáng #CoKim"})
    req = chrome_reports.video_request(packages.get(pid))
    assert "Chỉ đọc" in req and "Gói 92" in req and "```json" in req
    assert "Video cần đánh giá" in chrome_reports.week_request(7)
    body = "# Đánh giá Gói 92\n\n## 1. Tóm tắt\nGiữ chân giây 2: 61%.\n\n## 2. Bảng\n...\n```json\n{\"goi\": \"92\", \"video_id\": \"7712345678901234567\"}\n```\n"
    rid = chrome_reports.add(body, pid=pid)
    r = chrome_reports.get(rid)
    assert r["title"] == "Đánh giá Gói 92" and r["video_id"] == "7712345678901234567"
    txt = chrome_reports.recent_for_prompt()
    assert "Giữ chân giây 2: 61%" in txt and '"goi": "92"' in txt


def test_chrome_routes():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    assert c.get("/danh-gia").status_code == 200
    r = c.post("/danh-gia", data={"text": "# Báo cáo tuần\n\n## Tóm tắt\n" + "x" * 80}, follow_redirects=False)
    assert r.status_code == 303
    rid = chrome_reports.list_reports()[0]["id"]
    assert "Báo cáo tuần" in c.get(f"/danh-gia/{rid}.md").text
    r = c.post("/danh-gia", files={"file": ("a.md", "# Từ file\n\n" + "y" * 80, "text/markdown")}, follow_redirects=False)
    assert r.status_code == 303 and chrome_reports.list_reports()[0]["title"] == "Từ file"
    pid = packages.save({"goi": "93", "loai": 3, "scene1": S, "caption": "Trà"})
    assert "Claude in Chrome" in c.get(f"/packages/{pid}").text
    assert c.post(f"/danh-gia/{rid}/xoa", follow_redirects=False).status_code == 303


def test_chrome_skill_and_context():
    import io
    import zipfile

    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    r = c.get("/danh-gia/ngu-canh?days=14")
    assert r.status_code == 200 and "Video và gói tương ứng" in r.text and "Bối cảnh quảng bá" in r.text
    z = zipfile.ZipFile(io.BytesIO(c.get("/danh-gia/skill.zip").content))
    names = set(z.namelist())
    assert {"tiktok-studio-quet/SKILL.md", "tiktok-studio-quet/references/checklist.md",
            "tiktok-studio-quet/references/report-template.md"} <= names
    skill = z.read("tiktok-studio-quet/SKILL.md").decode()
    assert skill.startswith("---\nname: tiktok-studio-quet\n") and "/danh-gia/ngu-canh" in skill
    assert "Tải skill" in c.get("/danh-gia").text
