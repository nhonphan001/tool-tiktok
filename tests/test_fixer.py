import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

from app import fixer, strategy  # noqa: E402
from app.config import settings  # noqa: E402

CASES = [
    "Càng về những ngày cuối năm bận rộn, khi lá số Bát Tự thiếu hụt nguồn năng lượng Hỏa, mang lại may mắn, phong thủy bình an",
    "Đông sang khí Thủy vượng, người có lá số Bát Tự thiếu Hỏa hoặc Thổ rất dễ mệt",
    "Mệnh Nạp Âm và Dụng Thần khi chọn bùa hộ mệnh",
    "Hữu duyên giải mã, thu hút tài lộc cho năm mới",
    "Em bé mệnh Kỷ Thổ, dự đoán chính xác: chắc chắn sẽ hiểu chuyện",
    "lá số khuyet thuy nen deo vong (viết không dấu)",
]


def test_quick_fix_cleans_fortune_cases():
    for t in CASES:
        r = fixer.sua_nhanh(t)
        assert r["before"]["level"] != "ok", t
        assert r["after"]["level"] == "ok", (t, r["text"], r["after"])
        assert r["changes"]


def test_offsite_and_cart():
    r = fixer.sua_nhanh("Xem thêm ở Link Bio hoặc nangtamchatluongsong.vn nhé https://abc.vn/x")
    assert "nangtam" not in r["text"] and "http" not in r["text"] and "trang cá nhân của Cô Kim" in r["text"]
    assert r["after_nocart"]["level"] in ("ok", "warning") and r["notes"]
    r2 = fixer.sua_nhanh("Lá bồ đề đón lộc, xem link nhé", True)
    assert r2["after"]["level"] == "ok" and "giỏ hàng" in r2["text"]


def test_keeps_clean_text_and_hashtags():
    t = "Một ấm trà sáng cho cả nhà 🍵 Bấm theo dõi Cô Kim nha #TiemTraGiaiMa #CoKim"
    r = fixer.sua_nhanh(t)
    assert r["text"] == t and not r["changes"]


def test_gemini_rewrite_retries(monkeypatch):
    answers = ['{"caption": "Năm mới rước lộc về nhà #CoKim", "giai_thich": "x"}',
               '{"caption": "Năm mới nhẹ lòng, cả nhà nhớ pha một ấm trà nhé #CoKim", "giai_thich": "bỏ rước lộc"}']
    calls = []
    usage = {"total_tokens": 50, "cost_usd": 0.0001, "input_tokens": 30, "output_tokens": 20, "thinking_tokens": 0}

    def fake(prompt, system="", json_mode=False):
        calls.append(prompt)
        return answers[len(calls) - 1], dict(usage)

    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(strategy, "call_gemini", fake)
    monkeypatch.setattr(strategy, "record_usage", lambda *a: None)
    r = fixer.viet_lai_gemini("Năm mới rước lộc, mang lại may mắn #CoKim")
    assert len(calls) == 2 and "ruoc loc" in calls[1] and r["after"]["level"] == "ok" and r["usage"]["total_tokens"] == 100


def test_item_advice_accent_aware():
    from app import packages
    assert not packages.ITEM_ADVICE.search("giống như đất dày kiên nhẫn nuôi dưỡng viên ngọc")
    assert packages.ITEM_ADVICE.search("nên đeo vòng đá thạch anh hồng")
