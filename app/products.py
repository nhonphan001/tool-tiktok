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
SHEET_COLUMNS = {"code": 0, "element": 1, "name": 2, "category": 3, "material": 4, "benefit": 5, "cta": 6, "price": 7,
                 "commission": 8, "link": 9, "status": 12, "note": 13, "video_name": 14}
# Cột O (thêm mới): "Tên dùng trong video" — tên ngắn, sạch quy tắc B.4, dùng trong lời thoại/caption
PLACEHOLDER_LINK = re.compile(r"^https?://(www\.)?(tiktok\.com/@[\w.]+|shopee\.vn|lazada\.vn)/?$", re.I)


def real_link(url: str) -> bool:
    """Link TikTok Shop thật (không phải link tạm trỏ về trang kênh / trang chủ sàn)."""
    u = (url or "").strip()
    return u.startswith("http") and not PLACEHOLDER_LINK.match(u)
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
        row = row + [""] * (15 - len(row))
        out.append({k: (row[i] or "").strip() for k, i in SHEET_COLUMNS.items()})
    return out


HEADER_KEYS = [  # (trường, điều kiện trên tiêu đề đã bỏ dấu) — thứ tự quan trọng
    ("video_name", lambda h: "trong video" in h or h.startswith("ten video")),
    ("cta", lambda h: "loi thoai" in h or "cta" in h),
    ("benefit", lambda h: "cong nang" in h),
    ("category", lambda h: "phan loai" in h),
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
                " synced_at, video_name, benefit, cta, category) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    it["code"].upper(), normalize_element(it.get("element", "")), it.get("name", ""),
                    it.get("material", ""), it.get("price", ""), it.get("commission", ""), it.get("link", ""),
                    it.get("status", ""), it.get("note", ""), ts, it.get("video_name", ""), it.get("benefit", ""),
                    it.get("cta", ""), it.get("category", ""),
                ),
            )
    missing = sum(1 for it in items if not real_link(it.get("link", "")))
    no_vname = sum(1 for it in items if not it.get("video_name"))
    msg = f"Đã đọc {len(items)} sản phẩm từ {src}; {missing} mã chưa có link TikTok Shop thật"
    if no_vname:
        msg += f"; {no_vname} mã chưa có “Tên dùng trong video”"
    return msg, None


def audit(p: dict) -> list[dict]:
    """Rà B.4 trên tên, tên dùng trong video, công năng và lời thoại gợi ý của 1 SKU trong bảng."""
    from . import compliance

    out = []
    for field, label in (("name", "Tên trong bảng"), ("category", "Phân loại"), ("video_name", "Tên dùng trong video"),
                         ("benefit", "Công năng"),
                         ("cta", "Lời thoại gợi ý")):
        t = p.get(field) or ""
        if not t:
            continue
        r = compliance.check(t, True)
        found = r["offsite"] + r["promise"]
        if found:
            out.append({"field": label, "found": ", ".join(f"{x['label']} (“{x['match']}”)" for x in found)})
    return out


def all_products() -> list[dict]:
    return db.query("SELECT * FROM products ORDER BY code")


def by_code() -> dict[str, dict]:
    return {p["code"]: p for p in all_products()}


# ---------- Ghi bảng: CHỈ THÊM DÒNG MỚI (không sửa, không xoá dòng có sẵn) ----------
APPEND_URL = ("https://sheets.googleapis.com/v4/spreadsheets/{id}/values/{range}:append"
              "?valueInputOption=RAW&insertDataOption=INSERT_ROWS")
NEW_FIELDS = ("code", "element", "name", "category", "material", "benefit", "cta", "price", "commission",
              "link", "status", "note", "video_name")
# Ô được kiểm tra B.4 trước khi ghi: có từ cấm là KHÔNG ghi (Phân loại chỉ cảnh báo — phải mô tả đúng bản chất hàng)
BLOCK_FIELDS = {"video_name": "Tên dùng trong video", "benefit": "Công năng", "cta": "Lời thoại gợi ý"}


def validate_new(data: dict) -> tuple[dict, list[str], list[str]]:
    """Chuẩn hoá + kiểm tra 1 SKU mới. Trả về (dữ liệu, lỗi chặn ghi, cảnh báo)."""
    from . import compliance

    d = {k: re.sub(r"\s+", " ", (data.get(k) or "")).strip() for k in NEW_FIELDS}
    d["code"] = d["code"].upper()
    d["element"] = normalize_element(d["element"]) if d["element"] else ""
    d["status"] = d["status"] or "Đang Bật"
    errors, warns = [], []
    if not re.fullmatch(r"SP-[A-Z]+-\d+", d["code"]):
        errors.append("Mã phải có dạng SP-NHOM-01 (vd. SP-TET-01)")
    elif d["code"] in by_code():
        errors.append(f"Mã {d['code']} đã có trong bảng — tool chỉ thêm dòng mới, không sửa dòng cũ")
    for k, label in (("name", "Tên"), ("video_name", "Tên dùng trong video")):
        if not d[k]:
            errors.append(f"Thiếu {label}")
    if d["link"] and not d["link"].startswith("http"):
        errors.append("Link phải bắt đầu bằng http")
    for k, v in d.items():
        if v.startswith(("=", "+", "@")):
            errors.append(f"Ô {k} không được bắt đầu bằng ký tự công thức (= + - @)")
    for k, label in BLOCK_FIELDS.items():
        if d[k]:
            r = compliance.check(d[k], True)
            found = r["offsite"] + r["promise"]
            if found:
                errors.append(f"{label} có từ cấm: " + ", ".join(f"“{x['match']}”" for x in found))
    for k, label in (("name", "Tên"), ("category", "Phân loại")):
        r = compliance.check(d[k], True)
        if r["fortune"]:
            warns.append(f"{label} mang tính tâm linh ({', '.join(x['label'] for x in r['fortune'])}) "
                         "→ SKU sẽ bị gắn cờ không chạy quảng cáo")
    if not real_link(d["link"]):
        warns.append("Chưa có link TikTok Shop thật (sẽ báo 'link tạm')")
    return d, errors, warns


def append_row(data: dict) -> str:
    """Thêm 1 dòng SKU vào cuối bảng quản trị (Google Sheets API, service account cần quyền Chỉnh sửa)."""
    if settings.product_csv_url or not settings.product_sheet_id:
        raise RuntimeError("Chỉ thêm được khi nguồn là ID Google Sheet (không áp dụng cho link CSV)")
    d, errors, _ = validate_new(data)
    if errors:
        raise ValueError("; ".join(errors))
    # Đọc lại bảng ngay trước khi ghi để chắc chắn mã chưa có (bảng có thể vừa được sửa tay)
    if any((r.get("code") or "").strip().upper() == d["code"] for r in _rows_from_sheets_api()):
        raise ValueError(f"Mã {d['code']} đã có trong bảng")
    row = [""] * 15
    for k, i in SHEET_COLUMNS.items():
        row[i] = d.get(k, "")
    from .notebooklm import _credentials

    creds = _credentials(["https://www.googleapis.com/auth/spreadsheets"])
    r = httpx.post(
        APPEND_URL.format(id=settings.product_sheet_id, range=settings.product_sheet_range),
        headers={"Authorization": f"Bearer {creds.token}"},
        json={"values": [row]}, timeout=60,
    )
    if r.status_code == 403:
        raise RuntimeError("Google từ chối ghi (403): chia sẻ bảng cho service account với quyền Người chỉnh sửa")
    if r.status_code != 200:
        raise RuntimeError(f"Google Sheets lỗi {r.status_code}: {r.text[:300]}")
    where = (r.json().get("updates") or {}).get("updatedRange", "")
    db.log_sync("product_sheet", "ok", f"Thêm {d['code']} vào {where}")
    msg, _ = sync()
    return f"Đã thêm {d['code']} vào bảng ({where}). {msg}"
