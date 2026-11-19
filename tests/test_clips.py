import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import clips, db, gemini_requests as gr, packages  # noqa: E402
from app.config import settings  # noqa: E402

FILES = [
    {"id": "A" * 33, "name": "Goi_18_canh_1.mp4", "modifiedTime": "2026-11-19T05:00:00Z"},
    {"id": "B" * 33, "name": "Goi_18_canh_2.mp4", "modifiedTime": "2026-11-19T05:01:00Z"},
    {"id": "C" * 33, "name": "GOI-18-CANH-3.mp4", "modifiedTime": "2026-11-19T05:02:00Z"},
    {"id": "D" * 33, "name": "Goi_18_canh_4.mp4", "modifiedTime": "2026-11-19T05:03:00Z"},
    {"id": "E" * 33, "name": "Goi_180_canh_1.mp4", "modifiedTime": "2026-11-19T06:00:00Z"},   # gói khác
    {"id": "F" * 33, "name": "Goi_17_canh_1.mp4", "modifiedTime": "2026-11-19T06:00:00Z"},
]


def _pkg():
    db.get_conn()
    packages.init()
    with db.tx() as c:
        c.execute("DELETE FROM packages")
        c.execute("DELETE FROM jobs")
    return packages.save({"goi": "18", "title": "Lá số", "loai": 1, "scene1": "x", "on_screen": "Hook 18"})


def test_match_sync_review_and_redo(monkeypatch):
    pid = _pkg()
    p = packages.get(pid)
    cl, new = clips.sync(p, FILES)
    assert sorted(new) == ["1", "2", "3", "4"] and cl["1"]["id"] == "A" * 33 and cl["3"]["status"] == "cho_duyet"
    clips.save(pid, cl)
    clips.set_status(pid, "1", "lam_lai", "méo mặt")
    for k in "234":
        clips.set_status(pid, k, "dat")
    assert not clips.all_ok(clips.load(packages.get(pid)))
    # anh Nhơn tạo lại cảnh 1 → bản mới về "Chờ duyệt", giữ ghi chú, đếm lần
    files2 = FILES + [{"id": "G" * 33, "name": "Goi_18_canh_1_v2.mp4", "modifiedTime": "2026-11-19T07:00:00Z"}]
    cl2, new2 = clips.sync(packages.get(pid), files2)
    assert new2 == ["1"] and cl2["1"]["status"] == "cho_duyet" and cl2["1"]["rounds"] == 1 and cl2["2"]["status"] == "dat"
    clips.save(pid, cl2)
    clips.set_status(pid, "1", "dat")
    assert clips.all_ok(clips.load(packages.get(pid)))


def test_sync_all_notifies_once(monkeypatch):
    pid = _pkg()
    monkeypatch.setattr(clips, "list_raw", lambda token=None: FILES)
    msgs = clips.sync_all()
    assert len(msgs) == 1 and "Gói 18" in msgs[0]
    assert db.query_one("SELECT * FROM jobs WHERE kind='clips'")["link"] == f"/packages/{pid}#clips"
    assert clips.sync_all() == []


def test_ghep_letter_and_request(monkeypatch):
    pid = _pkg()
    p = packages.get(pid)
    cl, _ = clips.sync(p, FILES)
    for k in cl:
        cl[k]["status"] = "dat"
    code, md = clips.ghep_letter(p, cl)
    assert code.startswith("GHEP-") and code.endswith("GOI-18") and "GIỮ NGUYÊN dấu nhận diện AI" in md
    assert "A" * 33 in md and "Hook 18" in md and "file_video_final_drive" in md
    rid = gr.create_ghep("18", code, "Ghép video Gói 18", md)
    pushed = {}
    monkeypatch.setattr(gr, "_token", lambda *a: "t")
    monkeypatch.setattr(gr, "_create_file", lambda *a: (_ for _ in ()).throw(RuntimeError("403")))
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "DOC")
    monkeypatch.setattr("app.notebooklm.push_drive", lambda doc, text: pushed.update(text=text))
    gr.send(rid)
    assert code in pushed["text"] and gr.get(rid)["status"] == "sent"
