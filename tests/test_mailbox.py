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
    assert chk["errors"] == 0 and chk["warns"] == 0 and chk["ads_ok"]
