import os
from pathlib import Path

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import mailbox  # noqa: E402

FX = Path(__file__).parent / "fixtures"
S4 = "Nhà nào đang chuẩn bị dọn dẹp đón Tết thì tham khảo nha. Cả nhà bấm giỏ hàng góc trái để xem chi tiết nhé."


def test_parse_claude_request():
    p = mailbox.parse((FX / "goi16_yeucau.md").read_text(), "SANXUAT-1811-GOI-16-KHAN-LAU-BAN-THO__YEUCAU.md")
    assert p["goi"] == "16" and p["sku"] == "SP-TET-01" and p["loai"] == 2
    assert p["title"] == "Khăn lau bàn thờ Thiên Phúc – dọn bàn thờ cuối năm"
    assert p["product_name"] == "Khăn lau bàn thờ Thiên Phúc"
    assert p["scene4"] == S4 and p["scene1"].startswith("Cuối năm rồi")
    assert p["on_screen"] == "Dọn bàn thờ cuối năm · nhẹ tay hơn"
    assert p["caption"].startswith("Khăn lau bàn thờ Thiên Phúc mùi trầm hương") and p["caption"].endswith("#Tet2027")
    assert p["pinned"].startswith("Khăn lau bàn thờ Thiên Phúc Cô Kim để ở giỏ hàng")


def test_parse_gemini_gdoc_and_merge():
    g = mailbox.parse((FX / "goi16_xong_gdoc.md").read_text(), "SANXUAT-1811-GOI-16-KHAN-LAU-BAN-THO__XONG.md")
    assert g["goi"] == "16" and g["sku"] == "SP-TET-01"
    assert g["images"] == {1: "1VQuQL9RM8qkKpPZtQKdVGOYbHiGCVepP", 2: "1hMxMPxPUIKbkqxKosQ1bqG_mcDPJLGR7",
                           3: "17LWAqpyiBrEyqJHK_GJeiE9s0XNDLBSv", 4: "1YzT0bjdf9jrK03bbExaGJHAPA6Pf8Ga5"}
    assert g["scene4"] == S4 and g["scene2"].startswith("Cô Kim dùng khăn")
    c = mailbox.parse((FX / "goi16_yeucau.md").read_text(), "SANXUAT-1811-GOI-16__YEUCAU.md")
    m = mailbox.merge([{**c, "source": {"id": "a", "name": "YEUCAU", "modified": "1"}},
                       {**g, "source": {"id": "b", "name": "XONG", "modified": "2"}}])
    assert set(m["fields"]) == {"title", "sku", "scene1", "scene2", "scene3", "scene4", "on_screen", "caption", "pinned"}
    assert m["note"].startswith("Ảnh Gemini: C1 1VQuQL9") and len(m["sources"]) == 2


def test_parse_gemini_bold_h1_headings_goi17():
    from app import packages
    p = mailbox.parse((FX / "goi17_xong_gdoc.md").read_text(), "SANXUAT-1911-GOI-17-TOI-MUON-CO-MOT__XONG.md")
    assert p["goi"] == "17" and p["loai"] == 3 and p["title"] == "Trà sáng chữa lành những ngày cuối năm"
    assert p["on_screen"].startswith("Sáng cuối năm") and p["caption"].endswith("#CuoiNam")
    assert p["pinned"].startswith("Sáng nay cả nhà") and "7 ngày" in p["ads_plan"] and len(p["images"]) == 4
    m = mailbox.merge([p])
    pk = {k: m.get(k, "") for k in packages.FIELDS}
    pk["loai"] = 3
    chk = packages.check(pk)
    assert chk["errors"] == 0 and chk["ads_ok"]
    # Gói 17 gốc: CTA follow chỉ ở cảnh 4 + caption > 250 ký tự (quy tắc hiệu suất 24/11)
    assert sorted(i["msg"][:14] for i in chk["items"] if i["level"] == "warn") == sorted(
        i["msg"][:14] for i in chk["items"] if i["rule"] == "Hiệu suất") and chk["warns"] == 2


def test_video_prompts_parsed_saved_and_checked():
    from app import db, packages
    db.get_conn()
    p = mailbox.parse((FX / "goi17_xong_gdoc.md").read_text(), "SANXUAT-1911-GOI-17__XONG.md")
    pr = p["prompts"]
    assert sorted(pr) == [1, 2, 3, 4]
    assert pr[1].startswith("Photorealistic live-action") and "Sáng nay cả nhà" in pr[1] and "Cảnh 2" not in pr[1]
    assert "Ghé lại tiệm trà" in pr[2] and "Cảnh 1" not in pr[2]
    m = mailbox.merge([p])
    assert "prompts" in m["fields"] and m["prompt3"] == pr[3] and m["image1"].startswith("1iu-")
    data = {k: m.get(k, "") for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES)}
    data["loai"] = 3
    data["image2"] = "https://drive.google.com/file/d/1vmbeF3hKtyycM05u2mN0ZyLPx5pvm3Ax/view?usp=drivesdk"
    pid = packages.save(data)
    q = packages.get(pid)
    assert q["prompt1"] == pr[1] and q["image2"] == "1vmbeF3hKtyycM05u2mN0ZyLPx5pvm3Ax" and "7 ngày" in q["ads_plan"]
    chk = packages.check(q)
    msgs = [i["msg"] for i in chk["items"] if i["rule"] == "Prompt"]
    # cảnh 4: prompt có lời thoại khác kịch bản + có nhạc nền
    assert any("cảnh 4 không chứa đúng lời thoại" in x for x in msgs) and any("Prompt cảnh 4 có nhạc nền" in x for x in msgs)
    assert not any("cảnh 1" in x or "cảnh 2" in x or "cảnh 3" in x for x in msgs)
    assert chk["errors"] == 0 and chk["ads_ok"]


def test_report_only_adds_videos_and_keeps_script():
    x = mailbox.parse((FX / "goi17_v33_real.md").read_text(), "SANXUAT-1911-GOI-17-TOI-MUON-CO-MOT__XONG.md")
    r = mailbox.parse_report((FX / "goi17_baocao.md").read_text(), "BAOCAO-1911-HOAN-TAT-GOI-17-VA-TOKEN__GUI_CLAUDE.md")
    assert r == {"goi": "17", "final_video": "1FqS8hLpQsIyPyIpvn3JhcXTZ49rEbqJB",
                 "clean_video": "1bfaqlfXyZE4HTA9DHebUA9VBl9f5w-03"}
    m = mailbox.merge([{**x, "source": {"id": "a", "name": "XONG", "modified": "1"}},
                       {**r, "source": {"id": "b", "name": "BAOCAO", "modified": "2"}}])
    assert m["caption"].endswith("#CuoiNam") and "video" in m["fields"]  # báo cáo không ghi đè caption
    assert m["final_video"] == "1FqS8hLpQsIyPyIpvn3JhcXTZ49rEbqJB"
    from app import db, packages
    db.get_conn()
    d = {k: m.get(k, "") for k in (*packages.FIELDS, *packages.PROMPTS, *packages.IMAGES, *packages.VIDEOS)}
    d["loai"] = 3
    d["clean_video"] = "https://drive.google.com/file/d/1bfaqlfXyZE4HTA9DHebUA9VBl9f5w-03/view?usp=drivesdk"
    q = packages.get(packages.save(d))
    assert q["final_video"] == "1FqS8hLpQsIyPyIpvn3JhcXTZ49rEbqJB" and q["clean_video"] == "1bfaqlfXyZE4HTA9DHebUA9VBl9f5w-03"


def test_report_v2_table_format_newer_wins():
    v1 = mailbox.parse_report((FX / "goi17_baocao.md").read_text(), "BAOCAO-1911-HOAN-TAT-GOI-17-VA-TOKEN__GUI_CLAUDE.md")
    v2 = mailbox.parse_report((FX / "goi17_baocao_v2.md").read_text(), "BAOCAO-1911-HOAN-TAT-GOI-17-V2-GIU-LOGO__GUI_CLAUDE.md")
    assert v2 == {"goi": "17", "final_video": "1DGLOjF813gO9DJoIDddsmum3j9dAo3RX",
                  "clean_video": "1MRmxHwc5nEbyFGnxHNnWLLouO6WvUhJ4"}
    m = mailbox.merge([{**v1, "source": {"id": "a", "name": "v1", "modified": "1"}},
                       {**v2, "source": {"id": "b", "name": "v2", "modified": "2"}}])
    assert m["final_video"] == "1DGLOjF813gO9DJoIDddsmum3j9dAo3RX"
