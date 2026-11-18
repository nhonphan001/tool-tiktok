import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

import pytest  # noqa: E402

from app import db, products, sku_lookup, strategy  # noqa: E402
from app.config import settings  # noqa: E402

TITLE = ("[Tết 2027] 10 Gói hoặc 5 Gói [30 tờ ] khăn lau bàn thờ THIÊN PHÚC Có mùi trầm hương và mùi quế "
         "Làm Sạch - Hương thơm nhẹ nhàng dễ chịu")
REDIRECT = ("https://www.tiktok.com/view/product/1731716027864942634?og_info="
            "%7B%22title%22%3A%22Kh%C4%83n%20lau%22%2C%22image%22%3A%22https%3A%5C%2F%5C%2Fimg%22%7D")


def _seed():
    db.get_conn()
    with db.tx() as c:
        c.execute("DELETE FROM products")
        c.execute("INSERT INTO products(code, name) VALUES('SP-TET-01','x')")
        c.execute("INSERT INTO products(code, name) VALUES('SP-KIM-04','y')")


def test_from_url_and_host_guard():
    i = sku_lookup._from_url(REDIRECT)
    assert i == {"product_id": "1731716027864942634", "title": "Khăn lau", "image": "https://img"}
    for bad in ("http://169.254.169.254/", "https://tiktok.com.evil.io/a", "file:///etc/passwd"):
        with pytest.raises(ValueError):
            sku_lookup.resolve(bad)


def test_next_code_and_heuristic():
    _seed()
    assert sku_lookup.next_code("TET") == "SP-TET-02"
    assert sku_lookup.next_code("Mộc") == "SP-MOC-01"
    h = sku_lookup._heuristic(TITLE)
    assert h["video_name"].lower() == "khăn lau bàn thờ thiên phúc"


def test_suggest_retries_when_gemini_writes_forbidden_words(monkeypatch):
    _seed()
    calls = []
    answers = [
        '{"element":"","group":"TET","video_name":"Khăn lau bàn thờ Thiên Phúc","category":"Khăn lau vệ sinh bàn thờ",'
        '"material":"30 tờ/gói","benefit":"Lau bàn thờ đón Tết rước lộc","cta":"Bấm giỏ hàng góc trái để xem chi tiết."}',
        '{"element":"","group":"TET","video_name":"Khăn lau bàn thờ Thiên Phúc","category":"Khăn lau vệ sinh bàn thờ",'
        '"material":"30 tờ/gói","benefit":"Lau sạch bụi mặt gỗ, mùi trầm và quế","cta":"Rút một tờ lau. Bấm giỏ hàng góc trái để xem chi tiết."}',
    ]
    usage = {"total_tokens": 100, "cost_usd": 0.001, "input_tokens": 60, "output_tokens": 40, "thinking_tokens": 0,
             "endpoint": "vertex_global"}

    def fake_call(prompt, system="", json_mode=False):
        calls.append(prompt)
        return answers[len(calls) - 1], dict(usage)

    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(strategy, "call_gemini", fake_call)
    monkeypatch.setattr(strategy, "record_usage", lambda *a: None)
    out = sku_lookup.suggest(link="https://vt.tiktok.com/x/", title=TITLE)
    assert len(calls) == 2 and "từ cấm" in calls[1]
    assert out["code"] == "SP-TET-02" and "rước" not in out["benefit"] and out["_auto"] == "Gemini"
    _, errors, _ = products.validate_new(out)
    assert not errors
