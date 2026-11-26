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
    assert any("cuối cảnh 1" in m for m in msgs) and any("khung hình 0" in m for m in msgs)
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


def test_run_info_and_clock():
    from fastapi.testclient import TestClient
    from app.main import app

    body = ("# Quét kênh hằng ngày 25/11/2026\n\n## 1. Tóm tắt\nok\n```json\n"
            '{"schema": "tiktok-studio-quet/v1", "mode": "hang_ngay", "run": {"started_at": "2026-11-25T16:30:05+07:00",'
            ' "finished_at": "2026-11-25T16:52:41+07:00", "tokens_est": {"input": 81000, "output": 4200, "total": 85200},'
            ' "exact_tokens": null}}\n```\n')
    info = chrome_reports.run_info(body)
    assert info["duration_min"] == 22.6 and info["tokens_est"] == 85200 and info["tokens_exact"] is None
    assert info["mode"] == "hang_ngay"
    assert chrome_reports.run_info("a" * 300)["tokens_est"] == 100  # không có khối run → ước tính đầu ra
    rid = chrome_reports.add(body)
    assert chrome_reports.list_reports()[0]["tokens_est"] == 85200 and chrome_reports.get(rid)["run_started"].startswith("2026-11-25T16:30")
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    assert "ISO: 20" in c.get("/danh-gia/gio").text
    page = c.get("/danh-gia").text
    assert "85,200 token" in page and "22.6 phút" in page
    z = c.get("/danh-gia/skill.zip").content
    import io, zipfile
    zz = zipfile.ZipFile(io.BytesIO(z))
    assert "/danh-gia/gio" in zz.read("tiktok-studio-quet/SKILL.md").decode()
    assert '"exact_tokens"' in zz.read("tiktok-studio-quet/references/report-template.md").decode()


def test_cta_second_estimate():
    # Gói 30 thật: CTA nằm giữa cảnh 2 (~giây 11) → cảnh báo; đưa vào cảnh 1 → hết cảnh báo
    s1 = "Thức giấc bên chén trà nóng, bạn đã kịp tha thứ cho những điều chưa trọn vẹn của chính mình chưa? Dừng lại vài giây nhé."
    s2 = "Mỗi sáng Cô Kim pha một ấm trà ngoài hiên nắng, cả nhà bấm theo dõi để ghé nha, rồi cùng nhau bỏ xuống chuyện cũ nhẹ lòng."
    base = {"goi": "94", "loai": 3, "on_screen": "Dành một chén trà sáng", "caption": "Trà sáng", "scene3": S, "scene4": S}
    msgs = _perf({**base, "scene1": s1, "scene2": s2})
    assert any("giây 11" in m and "CUỐI CẢNH 1" in m for m in msgs)
    s1b = "Bạn đã kịp tha thứ cho chính mình chưa? Bấm theo dõi Cô Kim, mỗi sáng mình cùng ngồi xuống uống chén trà nóng nha."
    assert _perf({**base, "scene1": s1b, "scene2": S}) == []


def test_checker_standalone_fortune_loai1_scenes_and_all_times():
    from app import compliance

    # (a) compliance.py bắt "tài lộc" đứng riêng và "muốn/cầu/... may mắn" nhưng không bắt nhầm lời chúc thường ngày
    r = compliance.check("Chị nào muốn may mắn tài lộc năm 2027 thì comment nha", has_cart=False)
    assert any(x["code"] == "may_man_tai_loc" for x in r["fortune"])
    assert any(x["code"] == "may_man_tai_loc" for x in compliance.check("Năm 2027 tài lộc dồi dào", False)["fortune"])
    assert any(x["code"] == "may_man_tai_loc" for x in compliance.check("Chị nào muốn may mắn năm tới", False)["fortune"])
    assert compliance.check("Chào buổi sáng, chúc cả nhà một ngày may mắn", True)["level"] == "ok"

    # (b) Loại 1 < 7 cảnh bị cảnh báo "Số cảnh" & liệt kê đủ mọi chữ chỉ giờ (không dừng ở lỗi đầu tiên)
    p = {
        "goi": "99", "loai": 1, "on_screen": "Tối nay xem lá số",
        "caption": "Tối nay 19h Cô Kim giải mã tuổi Bính Dần 1986, chị nào muốn may mắn tài lộc thì comment nha",
        "scene1": "Chị Bính Dần tám sáu ơi, tối nay ngồi uống trà nghe Cô Kim nói nha. Comment năm sinh để Cô Kim xem giúp.",
        "scene2": S, "scene3": S, "scene4": S,
    }
    items = packages.check(p)["items"]
    assert any(i["rule"] == "B.4" and "Caption:" in i["msg"] for i in items)
    assert any(i["rule"] == "Số cảnh" and "7 cảnh" in i["msg"] for i in items)
    time_msgs = [i["msg"] for i in items if i["rule"] == "Hiệu suất" and "chỉ giờ" in i["msg"]]
    assert any("Caption:" in m and "toi nay" in m and "19h" in m for m in time_msgs)
    assert any("Chữ trên hình:" in m and "toi nay" in m for m in time_msgs)
    assert any("Cảnh 1:" in m and "toi nay" in m for m in time_msgs)
