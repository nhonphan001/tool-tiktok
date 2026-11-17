"""Đọc danh sách sản phẩm từ bảng quản trị (nguồn đúng duy nhất) — CHỈ ĐỌC, không bao giờ ghi vào bảng."""
import csv
import io
import re

import httpx

from . import db
from .compliance import normalize
from .config import settings

SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets/{id}/values/{range}"
ELEMENTS = ["Kim", "Mộc", "Thủy", "Hỏa", "Thổ"]
# Cột theo tài liệu bàn giao: A mã, B hành, C tên, E màu sắc & chất liệu, H giá, I hoa hồng, J link, M trạng thái, N ghi chú
SHEET_COLUMNS = {"code": 0, "element": 1, "name": 2, "material": 4, "price": 7, "commission": 8, "link": 9,
                 "status": 12, "note": 13}
CODE_RE = re.compile(r"^SP-[A-Z]+-\d+", re.I)


def normalize_element(v: str) -> str:
    n = normalize(v)
    for e in ELEMENTS:
        if normalize(e) in n:
            return e
    return (v or "").strip()


def _rows_from_sheets_api() -> list[dict]:
    from .notebooklm import _credentials

    creds = _credentials(["https://www.googleapis.com/auth/spreadsheets.readonly"])
    r = httpx.get(
        SHEETS_URL.format(id=settings.product_sheet_id, range=settings.product_sheet_range),
        headers={"Authorization": f"Bearer {creds.token}"},
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Google Sheets lỗi {r.status_code}: {r.text[:300]}")
    out = []
    for row in r.json().get("values", []):
        row = row + [""] * (14 - len(row))
        out.append({k: (row[i] or "").strip() for k, i in SHEET_COLUMNS.items()})
    return out


HEADER_KEYS = [  # (trường, điều kiện trên tiêu đề đã bỏ dấu)
    ("code", lambda h: h.startswith("ma") or "code" in h),
    ("element", lambda h: "hanh" in h),
    ("name", lambda h: h.startswith("ten") or "name" in h),
    ("material", lambda h: "chat lieu" in h or "mau sac" in h),
    ("price", lambda h: h.startswith("gia") or "price" in h),
    ("commission", lambda h: "hoa hong" in h),
    ("link", lambda h: "link" in h or "url" in h),
    ("status", lambda h: "trang thai" in h or "status" in h),
    ("note", lambda h: "ghi chu" in h or "note" in h),
]


def _rows_from_csv() -> list[dict]:
    r = httpx.get(settings.product_csv_url, timeout=60, follow_redirects=True)
    if r.status_code != 200:
        raise RuntimeError(f"Không tải được CSV (HTTP {r.status_code})")
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    # Tìm dòng tiêu đề: dòng đầu tiên có cột "mã" và "tên"
    for hi, row in enumerate(rows):
        heads = [normalize(c).strip() for c in row]
        if any(h.startswith("ma") for h in heads) and any(h.startswith("ten") for h in heads):
            break
    else:
        raise RuntimeError("CSV không có dòng tiêu đề chứa cột 'Mã' và 'Tên'")
    colmap = {}
    for idx, h in enumerate(heads):
        for key, cond in HEADER_KEYS:
            if key not in colmap and cond(h):
                colmap[key] = idx
                break
    out = []
    for row in rows[hi + 1:]:
        out.append({k: (row[i].strip() if i < len(row) else "") for k, i in colmap.items()})
    return out


def sync() -> tuple[str, None]:
    """Đọc bảng sản phẩm và lưu bản sao vào DB của app. Trả về (thông điệp, None) cho jobs."""
    if settings.product_csv_url:
        rows, src = _rows_from_csv(), "CSV xuất bản"
    elif settings.product_sheet_id:
        rows, src = _rows_from_sheets_api(), "Google Sheets API"
    else:
        raise RuntimeError("Chưa cấu hình ID bảng sản phẩm hoặc link CSV trong Cài đặt")
    items = [r for r in rows if CODE_RE.match(r.get("code", ""))]
    if not items:
        raise RuntimeError("Không đọc được mã sản phẩm nào (mã phải có dạng SP-HANH-01)")
    ts = db.now_iso()
    with db.tx() as c:
        c.execute("DELETE FROM products")
        for it in items:
            c.execute(
                "INSERT OR REPLACE INTO products(code, element, name, material, price, commission, link, status, note,"
                " synced_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    it["code"].upper(), normalize_element(it.get("element", "")), it.get("name", ""),
                    it.get("material", ""), it.get("price", ""), it.get("commission", ""), it.get("link", ""),
                    it.get("status", ""), it.get("note", ""), ts,
                ),
            )
    missing = sum(1 for it in items if not it.get("link", "").startswith("http"))
    return f"Đã đọc {len(items)} sản phẩm từ {src}; {missing} mã chưa có link TikTok Shop", None


def all_products() -> list[dict]:
    return db.query("SELECT * FROM products ORDER BY code")


def by_code() -> dict[str, dict]:
    return {p["code"]: p for p in all_products()}
