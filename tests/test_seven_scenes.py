import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import clips, db, gemini_requests as gr, mailbox, packages  # noqa: E402
from app.config import settings  # noqa: E402

LINE = "Cô Kim pha ấm trà nóng ngồi kể cho chị nghe chuyện năm mới thật nhẹ nhàng và ấm áp như một buổi tối bình yên bên nhau"
PHIEU = "\n".join([
    "anh_7_canh:", *[f'  canh_{k}_{(k - 1) * 10}_{k * 10}s: "{("A" * 28) + str(k)}"' for k in range(1, 8)], "",
    "# Phiếu gói 30 — Thử video 60 giây", "", "## Lời thoại 7 cảnh × 10 giây",
    *[f"{k}. (30 âm tiết) {LINE} cảnh {k}." for k in range(1, 8)], "",
    "## Chữ trên hình", "1. Tính cách", "", "## Caption", "Cô Kim trả lời bình luận #tiemtragiaima", "",
    "## Bình luận ghim", "Để lại ngày sinh dưới bình luận để Cô Kim giải mã", "",
    "## Prompt tạo video 10 giây (Veo / Flow)",
    *[f'{k}. **Cảnh {k} ({(k - 1) * 10}–{k * 10}s | ảnh …)**: Photorealistic video, she speaks: "{LINE} cảnh {k}." Voice …'
      for k in range(1, 8)], "", "nhan_video:", "  goi: 30", "  loai: 1", "  so_canh: 7",
])


def test_parse_and_save_seven_scenes():
    g = mailbox.merge([mailbox.parse(PHIEU, "SANXUAT-2311-GOI-30-THU-60S__XONG.md")])
    assert g["scene7"].endswith("cảnh 7.") and g["image7"].endswith("7") and g["prompt7"].startswith("Photorealistic")
    assert "scene7" in g["fields"] and "prompts" in g["fields"]
    packages.init()
    pid = packages.save({"goi": "30", "loai": 1, **{k: g.get(k, "") for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES)}})
    p = packages.get(pid)
    assert packages.n_scenes(p) == 7 and p["scene7"] and p["image7"] and p["prompt7"]
    chk = packages.check(p)
    assert not [i for i in chk["items"] if i["rule"] in ("Prompt", "Số cảnh")]
    md = packages.markdown(p, chk) if hasattr(packages, "markdown") else ""
    # gói 7 cảnh quá ngắn → cảnh báo độ dài
    short = {**p, **{f"scene{k}": "Cô Kim pha trà" for k in range(1, 8)}}
    assert [i for i in packages.check(short)["items"] if i["rule"] == "Độ dài"]


def test_clips_and_ghep_seven():
    packages.init()
    pid = packages.save({"goi": "31", "loai": 1, **{f"scene{k}": f"lời {k}" for k in range(1, 8)}})
    p = packages.get(pid)
    files = [{"id": f"F{k}" + "x" * 30, "name": f"Goi_31_canh_{k}.mp4", "modifiedTime": "2026-11-23T10:00:00Z"}
             for k in range(1, 8)]
    cl, new = clips.sync(p, files)
    assert len(cl) == 7 and sorted(new, key=int) == [str(k) for k in range(1, 8)]
    clips.save(pid, cl)
    for k in range(1, 7):
        clips.set_status(pid, str(k), "dat")
    assert not clips.all_ok(clips.load(packages.get(pid)))
    clips.set_status(pid, "7", "dat")
    cl = clips.load(packages.get(pid))
    assert clips.all_ok(cl)
    code, md = clips.ghep_letter(packages.get(pid), cl)
    assert "ĐẠT cả 7 clip" in md and "Goi_31_canh_7.mp4" in md and "1→7" in md and "TRÊN 61 giây" in md


def test_request_letter_seven(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    gr.init()
    monkeypatch.setattr(gr, "send", lambda rid: "ok")
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    assert "7 cảnh (video trên 60 giây)" in c.get("/requests").text
    c.post("/requests/new", data={"brief": "Thử 60 giây", "loai": "1", "goal": "comment", "scenes": "7"})
    r = db.query_one("SELECT * FROM gemini_requests ORDER BY id DESC LIMIT 1")
    md = r["letter_md"]
    assert "Định dạng: 7 cảnh × 10 giây" in md and "canh_7_60_70s" in md and "7. **Cảnh 7 (60–70s" in md
    assert "so_canh: 7" in md and "TRÊN 61 giây" in md


def test_package_page_seven(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    packages.init()
    pid = packages.save({"goi": "32", "loai": 3, **{f"scene{k}": f"lời {k}" for k in range(1, 8)}})
    c = TestClient(app)
    c.post("/login", data={"password": settings.app_password})
    html = c.get(f"/packages/{pid}").text
    assert 'name="scene7"' in html and 'name="scene8"' in html and "Video 60 giây (7 cảnh)" in html
    assert "Lời thoại cả 7 cảnh" in html
