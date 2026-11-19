import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

import pytest  # noqa: E402

from app import db, gemini_requests as gr, mailbox, packages  # noqa: E402
from app.config import settings  # noqa: E402

BRIEF = ("Tôi muốn có một kịch bản cho sáng ngày mai, kịch bản không gắn sản phẩm, mục tiêu tăng follow, "
         "có chạy quảng cáo liên tục 7 ngày")
OPTS = {"loai": 3, "goal": "follow", "ads": True, "ads_days": 7, "publish": "Sáng 19/11, 07:00"}


def _reset():
    db.get_conn()
    gr.init()
    packages.init()
    with db.tx() as c:
        c.execute("DELETE FROM gemini_requests")
        c.execute("DELETE FROM packages")
        c.execute("DELETE FROM jobs")
    packages.save({"goi": "16", "title": "x", "loai": 2, "scene1": "a"})


def test_create_reserves_next_goi_and_letter_rules():
    _reset()
    rid = gr.create(BRIEF, "Trà sáng tăng follow", OPTS)
    r = gr.get(rid)
    assert r["goi"] == "17" and r["code"].startswith("SANXUAT-") and "-GOI-17-TRA-SANG-TANG-FOLLOW" in r["code"]
    L = r["letter_md"]
    assert BRIEF in L and "không xem lá số" in L and "bấm theo dõi Cô Kim" in L and "7 ngày" in L
    assert f"{r['code']}__XONG.md" in L and "# Phiếu gói 17" in L
    assert gr.next_goi() == 18  # số đã giữ không bị cấp lại


def test_send_falls_back_to_outbox(monkeypatch):
    _reset()
    rid = gr.create(BRIEF, "", OPTS)
    pushed = {}
    monkeypatch.setattr(gr, "_token", lambda *a: "t")
    monkeypatch.setattr(gr, "_create_file", lambda *a: (_ for _ in ()).throw(RuntimeError("HTTP 403 storageQuotaExceeded")))
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "")
    with pytest.raises(RuntimeError):
        gr.send(rid)
    assert gr.get(rid)["status"] == "error"
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "DOC")
    monkeypatch.setattr("app.notebooklm.push_drive", lambda doc, text: pushed.update(doc=doc, text=text))
    msg = gr.send(rid)
    assert "hộp thư đi" in msg and pushed["doc"] == "DOC" and "GOI-17" in pushed["text"]
    r = gr.get(rid)
    assert r["status"] == "sent" and r["channel"] == "outbox"


def test_check_replies_notifies(monkeypatch):
    _reset()
    rid = gr.create(BRIEF, "", OPTS)
    with db.tx() as c:
        c.execute("UPDATE gemini_requests SET status='sent', sent_at='2026-11-18T17:00:00+00:00' WHERE id=?", (rid,))
    files = [{"id": "old", "name": "SANXUAT-1811-GOI-17-X__XONG.md", "modifiedTime": "2026-11-18T16:00:00Z"},
             {"id": "f170", "name": "SANXUAT-1911-GOI-170__XONG.md", "modifiedTime": "2026-11-18T18:00:00Z"},
             {"id": "new", "name": "SANXUAT-1911-GOI-17-TRA-SANG__XONG.md", "modifiedTime": "2026-11-18T18:30:00Z"}]
    monkeypatch.setattr(gr, "_token", lambda *a: "t")
    monkeypatch.setattr(mailbox, "folder_ids", lambda: ["A"])
    monkeypatch.setattr(mailbox, "_list_files", lambda token, folder: files)
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "")
    done = gr.check_replies()
    assert [d["answer_name"] for d in done] == ["SANXUAT-1911-GOI-17-TRA-SANG__XONG.md"]
    job = db.query_one("SELECT * FROM jobs WHERE kind='mailbox'")
    assert job["link"] == "/packages/import/17" and job["notified"] == 0
    assert gr.check_replies() == []  # không báo lại
    gr.mark_imported("17")
    assert gr.get(rid)["status"] == "imported"


def test_loai3_package_rules():
    base = {"goi": "17", "loai": 3, "title": "Trà sáng",
            "scene1": "Sáng nay Cô Kim pha một ấm trà ô long, hơi ấm lan nhẹ trong căn phòng nhỏ, cả nhà đã dậy chưa nè?",
            "caption": "Một ấm trà sáng cho cả nhà 🍵 Bấm theo dõi Cô Kim nha #TiemTraGiaiMa", "pinned": ""}
    chk = packages.check(base)
    assert chk["errors"] == 0 and chk["ads_ok"]
    bad = packages.check({**base, "scene2": "Ai muốn Cô Kim giải mã lá số thì để lại ngày sinh dưới bình luận nha"})
    assert bad["errors"] and not bad["ads_ok"] and any(i["rule"] == "Quảng cáo" for i in bad["items"])
    assert not packages.check({**base, "sku": "SP-TET-01"})["ads_ok"]
    assert not packages.check({**base, "caption": "Xem thêm ở link bio nha. Bấm theo dõi Cô Kim"})["ads_ok"]


def test_check_replies_detects_updated_answer(monkeypatch):
    _reset()
    rid = gr.create(BRIEF, "", OPTS)
    with db.tx() as c:
        c.execute("UPDATE gemini_requests SET status='imported', sent_at='2026-11-18T17:00:00+00:00',"
                  " answered_at='2026-11-18T17:54:59+00:00', answer_modified='' WHERE id=?", (rid,))
    f = {"id": "x", "name": "SANXUAT-1911-GOI-17-TOI__XONG.md", "modifiedTime": "2026-11-18T17:53:58Z"}
    monkeypatch.setattr(gr, "_token", lambda *a: "t")
    monkeypatch.setattr(mailbox, "folder_ids", lambda: ["A"])
    monkeypatch.setattr(mailbox, "_list_files", lambda token, folder: [f])
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "")
    assert gr.check_replies() == []          # chưa sửa sau lần nhận
    f["modifiedTime"] = "2026-11-18T23:35:27.568Z"
    done = gr.check_replies()
    assert done and done[0]["updated"] and gr.get(rid)["status"] == "updated"
    assert db.query_one("SELECT * FROM jobs WHERE kind='mailbox' AND message LIKE '%cập nhật%'")
    assert gr.check_replies() == []          # không báo lại cùng một lần sửa
    gr.mark_imported("17")
    assert gr.get(rid)["status"] == "imported"


def test_real_goi17_v33_prompts():
    from pathlib import Path
    from app import mailbox as mb
    t = (Path(__file__).parent / "fixtures" / "goi17_v33_real.md").read_text()
    m = mb.merge([mb.parse(t, "SANXUAT-1911-GOI-17-TOI-MUON-CO-MOT__XONG.md")])
    assert m["image1"] == "1R-eg5lKwn_8rHbMNXGPnmf3na-4K0njV" and m["prompt4"].endswith("NO soundtrack.")
    d = {k: m.get(k, "") for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES)}
    d["loai"] = 3
    chk = packages.check(packages.get(packages.save(d)))
    assert chk["errors"] == 0 and chk["warns"] == 0 and chk["ads_ok"]


def test_check_replies_notifies_final_video(monkeypatch):
    from pathlib import Path
    _reset()
    rid = gr.create(BRIEF, "", OPTS)
    with db.tx() as c:
        c.execute("UPDATE gemini_requests SET status='imported', sent_at='2026-11-18T17:00:00+00:00',"
                  " answered_at='2026-11-18T23:40:00+00:00', answer_modified='2026-11-18T23:35:27Z' WHERE id=?", (rid,))
    files = [{"id": "x", "name": "SANXUAT-1911-GOI-17-TOI__XONG.md", "modifiedTime": "2026-11-18T23:35:27Z"},
             {"id": "rep", "name": "BAOCAO-1911-HOAN-TAT-GOI-17-VA-TOKEN__GUI_CLAUDE.md",
              "modifiedTime": "2026-11-19T01:57:08.703Z"}]
    report = (Path(__file__).parent / "fixtures" / "goi17_baocao.md").read_text()
    monkeypatch.setattr(gr, "_token", lambda *a: "t")
    monkeypatch.setattr(mailbox, "folder_ids", lambda: ["A"])
    monkeypatch.setattr(mailbox, "_list_files", lambda token, folder: files)
    monkeypatch.setattr(mailbox, "_read", lambda token, f: report)
    monkeypatch.setattr(settings, "mailbox_outbox_doc_id", "")
    done = gr.check_replies()
    assert [d.get("video") for d in done] == ["1FqS8hLpQsIyPyIpvn3JhcXTZ49rEbqJB"]
    assert db.query_one("SELECT * FROM jobs WHERE message LIKE '%video thành phẩm Gói 17%'")
    assert gr.check_replies() == []  # không báo lại


def test_loai1_letter_includes_tool_chart():
    _reset()
    opts = {"loai": 1, "goal": "comment", "ads": False, "ads_days": 7, "publish": "19:30",
            "birth": {"dd": "12", "mm": "3", "yy": "1995", "t": "08:00", "lich": "duong", "gioi": "nu"}}
    r = gr.get(gr.create("Giải mã lá số nữ 1995", "Lá số Ất Hợi", opts))
    L = r["letter_md"]
    assert "Ất Hợi – Kỷ Mão – Nhâm Dần – Giáp Thìn" in L and "Nhật chủ Nhâm Thủy" in L
    assert "không tự tính can chi" in L and "quang_cao: khong" in L
