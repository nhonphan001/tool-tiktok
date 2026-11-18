import os

os.environ.setdefault("DATABASE_PATH", ":memory:")
os.environ.setdefault("DISABLE_SCHEDULER", "1")

import pytest  # noqa: E402

from app import db, products  # noqa: E402
from app.config import settings  # noqa: E402

GOOD = {"code": "sp-tet-01", "name": "[Tết 2027] Khăn lau bàn thờ THIÊN PHÚC 30 tờ", "video_name": "Khăn lau bàn thờ Thiên Phúc",
        "category": "Khăn lau vệ sinh bàn thờ", "benefit": "Lau sạch bụi mặt gỗ, chân đèn; mùi trầm hương và quế nhẹ",
        "cta": "Rút một tờ lau mặt gỗ, xong bỏ đi. Bấm giỏ hàng góc trái để xem chi tiết.",
        "link": "https://vt.tiktok.com/ZS9PJRjjcdrH4-5gWBm/"}


def _seed():
    db.get_conn()
    with db.tx() as c:
        c.execute("DELETE FROM products")
        c.execute("INSERT INTO products(code, name) VALUES('SP-KIM-04','Lá bồ đề')")


def test_validate_ok_and_blocks():
    _seed()
    d, err, warn = products.validate_new(GOOD)
    assert d["code"] == "SP-TET-01" and d["status"] == "Đang Bật" and not err
    _, err, _ = products.validate_new({**GOOD, "cta": "Lau bàn thờ để rước lộc đầu năm"})
    assert any("Lời thoại gợi ý" in e for e in err)
    _, err, _ = products.validate_new({**GOOD, "code": "SP-KIM-04"})
    assert any("đã có" in e for e in err)
    _, err, _ = products.validate_new({**GOOD, "note": "=IMPORTXML(\"x\")"})
    assert any("công thức" in e for e in err)
    _, err, _ = products.validate_new({**GOOD, "video_name": "Xem link bio"})
    assert err
    _, _, warn = products.validate_new({**GOOD, "category": "Vật phẩm hộ mệnh"})
    assert any("không chạy quảng cáo" in w for w in warn)


def test_append_row_writes_only_append(monkeypatch):
    _seed()
    sent = {}

    class Creds:
        token = "t"

    class Resp:
        status_code = 200

        def json(self):
            return {"updates": {"updatedRange": "San_Pham_Affiliate_5_Hanh!A27:O27"}}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent["url"], sent["values"] = url, json["values"]
        return Resp()

    monkeypatch.setattr(settings, "product_sheet_id", "SHEET")
    monkeypatch.setattr(settings, "product_csv_url", "")
    monkeypatch.setattr("app.notebooklm._credentials", lambda scopes: Creds())
    monkeypatch.setattr(products, "_rows_from_sheets_api", lambda: [{"code": "SP-KIM-04"}])
    monkeypatch.setattr(products.httpx, "post", fake_post)
    monkeypatch.setattr(products, "sync", lambda: ("ok", None))
    msg = products.append_row(GOOD)
    assert ":append" in sent["url"] and "valueInputOption=RAW" in sent["url"]
    row = sent["values"][0]
    assert len(row) == 15 and row[0] == "SP-TET-01" and row[14] == "Khăn lau bàn thờ Thiên Phúc" and row[12] == "Đang Bật"
    assert "A27" in msg
    # mã đã có trên bảng thật (vừa thêm tay) -> không ghi
    monkeypatch.setattr(products, "_rows_from_sheets_api", lambda: [{"code": "SP-TET-01"}])
    sent.clear()
    with pytest.raises(ValueError):
        products.append_row(GOOD)
    assert not sent
