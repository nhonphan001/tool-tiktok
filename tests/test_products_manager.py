"""Kiểm tra trang Quản lý Sản phẩm Affiliate cục bộ trên TikTok Manager (/products)."""
from fastapi.testclient import TestClient

from app import db, main, products


def _login(client: TestClient):
    client.post("/login", data={"password": main.settings.app_password})


def test_auto_score_separates_keepers_and_off_niche(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.database_path", str(tmp_path / "prod_mgr.db"))
    db.reset_connection()
    products.init()

    sc_good, dec_good, _ = products.auto_score({
        "name": "Bộ Ấm Trà Tử Sa Cao Cấp Kèm 6 Ly Giữ Hương Trà",
        "price": "196.515₫",
        "commission": "14,2%",
    })
    assert dec_good == "giu" and sc_good >= 80

    sc_off, dec_off, _ = products.auto_score({
        "name": "Khăn giấy vệ sinh treo tường 1000 tờ",
        "price": "101.100₫",
        "commission": "10,2%",
    })
    assert dec_off == "loai_bo" and sc_off < 55

    sc_b4, dec_b4, _ = products.auto_score({
        "name": "Vòng Tay Chu Sa Ngũ Lộ Thần Tài Chiêu Tài May Mắn",
        "price": "168.000₫",
        "commission": "55%",
    })
    assert dec_b4 == "loai_bo"


def test_products_local_crud_decision_sales_and_api(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.database_path", str(tmp_path / "prod_crud.db"))
    monkeypatch.setattr("app.config.settings.api_token", "tok-prod-123")
    db.reset_connection()
    products.init()

    client = TestClient(main.app)
    _login(client)

    # 1. Thêm sản phẩm trực tiếp trên web
    r = client.post("/products/local/save", data={
        "code": "SC-AM-01",
        "decision": "giu",
        "score": "94",
        "element": "Thổ",
        "source": "showcase",
        "name": "Bộ Ấm Trà Tử Sa Cao Cấp Kèm 6 Ly",
        "video_name": "Bộ ấm trà tử sa 6 ly",
        "shop_name": "Choviet",
        "price": "196.515₫",
        "commission": "14,2%",
        "est_commission": "27.926₫",
        "showcase_id": "1738196162712405710",
        "stock_info": "In stock (20)",
    }, follow_redirects=True)
    assert r.status_code == 200
    assert "SC-AM-01" in r.text
    assert "Choviet" in r.text

    # 2. Đổi quyết định & cập nhật doanh số thực
    r2 = client.post("/products/SC-AM-01/decision", data={"decision": "thu_nghiem", "back": "/products"}, follow_redirects=False)
    assert r2.status_code == 303
    assert products.get("SC-AM-01")["decision"] == "thu_nghiem"

    r3 = client.post("/products/SC-AM-01/sales", data={"orders": "5", "gmv": "982575", "revenue_vnd": "139630"}, follow_redirects=False)
    assert r3.status_code == 303
    p = products.get("SC-AM-01")
    assert p["orders"] == 5 and p["revenue_vnd"] == 139630

    # 3. Đẩy danh sách qua API Studio cho Bộ phận Affiliate
    r_api = client.post(
        "/api/public/studio/products",
        headers={"x-api-token": "tok-prod-123"},
        json={"items": [
            {"code": "DX-TRA-01", "name": "Trà Hoa Cúc Táo Đỏ Dưỡng Tâm", "video_name": "Trà hoa cúc táo đỏ",
             "decision": "de_xuat", "score": 95, "source": "ai_proposal", "price": "165.000₫", "commission": "20%"},
        ]},
    )
    assert r_api.status_code == 200
    assert r_api.json()["saved"] == 1
    assert products.get("DX-TRA-01")["decision"] == "de_xuat"

    # 4. Xoá sản phẩm
    r_del = client.post("/products/DX-TRA-01/delete", follow_redirects=False)
    assert r_del.status_code == 303
    assert products.get("DX-TRA-01") is None
