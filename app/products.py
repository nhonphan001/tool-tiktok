"""Đọc danh sách sản phẩm từ bảng quản trị (nguồn đúng duy nhất) — CHỈ ĐỌC, không bao giờ ghi vào bảng."""
import csv
import io
import re

import httpx

from . import db
from .compliance import normalize
from .config import settings

SHEETS_URL = "https://sheets.googleapis.com/v4/spreadsheets/{id}/values/{range}"
SHOWCASE_URL = "https://shop.tiktok.com/streamer/showcase/product/list"
ELEMENTS = ["Kim", "Mộc", "Thủy", "Hỏa", "Thổ"]
DECISIONS = {
    "giu": "⭐ Giữ mũi nhọn",
    "thu_nghiem": "🧪 Thử nghiệm",
    "de_xuat": "💡 Đề xuất thêm",
    "cho_duyet": "Chờ đánh giá",
    "loai_bo": "✕ Loại bỏ",
}
SOURCES = {
    "showcase": "Showcase TikTok",
    "sheet": "Google Sheets",
    "manual": "Thêm trực tiếp",
    "ai_proposal": "Đề xuất Affiliate",
}
_EXTRA_COLS = (
    ("decision", "TEXT DEFAULT 'cho_duyet'"),
    ("score", "INTEGER DEFAULT 0"),
    ("source", "TEXT DEFAULT 'sheet'"),
    ("showcase_id", "TEXT DEFAULT ''"),
    ("shop_name", "TEXT DEFAULT ''"),
    ("stock_info", "TEXT DEFAULT ''"),
    ("est_commission", "TEXT DEFAULT ''"),
    ("orders", "INTEGER DEFAULT 0"),
    ("gmv", "INTEGER DEFAULT 0"),
    ("revenue_vnd", "INTEGER DEFAULT 0"),
    ("updated_at", "TEXT DEFAULT ''"),
)


def init() -> None:
    """Bảo đảm bảng products có đủ các cột quản trị Affiliate cục bộ trên TikTok Manager."""
    with db.tx() as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(products)").fetchall()}
        for col, spec in _EXTRA_COLS:
            if col not in cols:
                c.execute(f"ALTER TABLE products ADD COLUMN {col} {spec}")


def _parse_money(text: str) -> int:
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else 0


def _parse_pct(text: str) -> float:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", str(text or ""))
    return float(m.group(1).replace(",", ".")) if m else 0.0


def auto_score(p: dict) -> tuple[int, str, str]:
    """Chấm điểm sơ bộ 0–100 theo chuẩn Bộ phận Affiliate & Phân tích Thị trường (Nữ 35–54 · bàn trà Cô Kim)."""
    name_norm = normalize(f"{p.get('name', '')} {p.get('video_name', '')} {p.get('category', '')} {p.get('material', '')}")
    aud = audit(p)
    score = 50
    reasons = []

    # 1. Phù hợp tệp Nữ 35–54 & định vị Tiệm Trà Giải Mã
    core_kw = ("tra ", "am tra", "tu sa", "tram huong", "nu tram", "nhang", "lu xong", "den da muoi", "nen thom", "khan lau ban tho", "ngoc am", "cay ")
    off_kw = ("ve sinh", "giay an", "but chi", "ao polo", "son ", "banh quy", "dau den", "khan tam", "sat bao", "tay trang")
    if any(k in name_norm for k in core_kw):
        score += 24
        reasons.append("khớp định vị trà/thư giãn/gia đạo Nữ 35–54")
    elif any(k in name_norm for k in off_kw):
        score -= 35
        reasons.append("lệch định vị Tiệm Trà Cô Kim")

    # 2. Rà tuân thủ B.4 (rất quan trọng với TikTok Shop & Ads)
    b4_heavy = ("than tai", "phat ban menh", "ho menh", "xin loc", "chua tai", "chieu tai", "ty huu", "thiem thu", "bo de", "kinh phat", "tu linh", "hu tien")
    if aud or any(k in name_norm for k in b4_heavy):
        score -= 30
        reasons.append("dính từ khóa tâm linh/B.4 rủi ro cao")
    else:
        score += 10
        reasons.append("sạch B.4")

    # 3. Vùng giá ngọt (90k–550k) & Hoa hồng
    price = _parse_money(p.get("price", ""))
    pct = _parse_pct(p.get("commission", ""))
    if 80_000 <= price <= 550_000:
        score += 10
    elif 0 < price < 50_000 or price > 700_000:
        score -= 8
    if pct >= 12:
        score += 10
        reasons.append(f"hoa hồng tốt ({pct:g}%)")
    elif 0 < pct < 8:
        score -= 8
        reasons.append(f"hoa hồng mỏng ({pct:g}%)")

    # 4. Link / tồn kho
    if "out of stock" in str(p.get("stock_info") or "").lower():
        score -= 20
        reasons.append("hết hàng")

    score = max(5, min(98, score))
    if score >= 78:
        dec = "giu"
    elif score >= 55:
        dec = "thu_nghiem"
    else:
        dec = "loai_bo"
    return score, dec, "; ".join(reasons)
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
    init()
    ts = db.now_iso()
    existing = by_code()
    with db.tx() as c:
        # Giữ nguyên các sản phẩm thêm trực tiếp / Showcase / Đề xuất AI; chỉ cập nhật các dòng từ Google Sheets
        c.execute("DELETE FROM products WHERE COALESCE(source, 'sheet') = 'sheet'")
        for it in items:
            code = it["code"].upper()
            prev = existing.get(code) or {}
            sc = int(prev.get("score") or 0)
            dec = prev.get("decision") or "cho_duyet"
            if not sc:
                sc, dec_auto, _ = auto_score(it)
                if dec == "cho_duyet":
                    dec = dec_auto
            c.execute(
                "INSERT OR REPLACE INTO products(code, element, name, material, price, commission, link, status, note,"
                " synced_at, video_name, benefit, cta, category, decision, score, source, showcase_id, shop_name,"
                " stock_info, est_commission, orders, gmv, revenue_vnd, updated_at)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    code, normalize_element(it.get("element", "")), it.get("name", ""),
                    it.get("material", ""), it.get("price", ""), it.get("commission", ""), it.get("link", ""),
                    it.get("status", ""), it.get("note", ""), ts, it.get("video_name", ""), it.get("benefit", ""),
                    it.get("cta", ""), it.get("category", ""),
                    dec, sc, "sheet",
                    prev.get("showcase_id") or "", prev.get("shop_name") or "", prev.get("stock_info") or "",
                    prev.get("est_commission") or "", int(prev.get("orders") or 0), int(prev.get("gmv") or 0),
                    int(prev.get("revenue_vnd") or 0), ts,
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


def all_products(decision: str = "all", q: str = "") -> list[dict]:
    init()
    rows = db.query(
        "SELECT * FROM products ORDER BY "
        "CASE COALESCE(decision, 'cho_duyet') WHEN 'giu' THEN 0 WHEN 'thu_nghiem' THEN 1 "
        "WHEN 'de_xuat' THEN 2 WHEN 'cho_duyet' THEN 3 ELSE 4 END, "
        "COALESCE(score, 0) DESC, code ASC"
    )
    if decision and decision != "all":
        rows = [r for r in rows if (r.get("decision") or "cho_duyet") == decision]
    if q:
        ql = normalize(q)
        rows = [
            r for r in rows
            if ql in normalize(f"{r.get('code','')} {r.get('name','')} {r.get('video_name','')} {r.get('shop_name','')} {r.get('note','')} {r.get('element','')}")
        ]
    return rows


def by_code() -> dict[str, dict]:
    init()
    return {p["code"]: p for p in db.query("SELECT * FROM products")}


def get(code: str) -> dict | None:
    init()
    return db.query_one("SELECT * FROM products WHERE code=?", ((code or "").strip().upper(),))


def decision_counts() -> dict[str, int]:
    init()
    rows = db.query("SELECT COALESCE(NULLIF(decision,''), 'cho_duyet') AS d, COUNT(*) AS n FROM products GROUP BY d")
    out = {k: 0 for k in DECISIONS}
    for r in rows:
        if r["d"] in out:
            out[r["d"]] = int(r["n"])
    out["all"] = sum(out.values())
    return out


def sales_totals() -> dict[str, int]:
    init()
    row = db.query_one("SELECT COALESCE(SUM(orders),0) AS orders, COALESCE(SUM(gmv),0) AS gmv, COALESCE(SUM(revenue_vnd),0) AS rev FROM products")
    return {
        "orders": int((row or {}).get("orders") or 0),
        "gmv": int((row or {}).get("gmv") or 0),
        "revenue_vnd": int((row or {}).get("revenue_vnd") or 0),
    }


def save_local(data: dict, old_code: str | None = None) -> str:
    """Thêm mới hoặc cập nhật sản phẩm trực tiếp trong TikTok Manager (không cần sửa Google Sheets)."""
    init()
    code = re.sub(r"\s+", "-", str(data.get("code") or "").strip().upper())
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("Thiếu tên sản phẩm.")
    if not code:
        prefix = "SC" if data.get("showcase_id") else ("DX" if data.get("decision") == "de_xuat" else "SP-TM")
        existing = by_code()
        n = 1
        while f"{prefix}-{n:02d}" in existing:
            n += 1
        code = f"{prefix}-{n:02d}"

    prev = get(old_code or code) or {}
    decision = str(data.get("decision") or prev.get("decision") or "cho_duyet").strip()
    if decision not in DECISIONS:
        decision = "cho_duyet"
    source = str(data.get("source") or prev.get("source") or "manual").strip()
    if source not in SOURCES:
        source = "manual"
    row_dict = {
        "code": code,
        "element": normalize_element(data.get("element", "")) if data.get("element") else "",
        "name": name[:300],
        "video_name": str(data.get("video_name") or "").strip()[:160],
        "category": str(data.get("category") or "").strip()[:120],
        "material": str(data.get("material") or "").strip()[:200],
        "benefit": str(data.get("benefit") or "").strip()[:400],
        "cta": str(data.get("cta") or "").strip()[:400],
        "price": str(data.get("price") or "").strip()[:60],
        "commission": str(data.get("commission") or "").strip()[:60],
        "est_commission": str(data.get("est_commission") or "").strip()[:60],
        "link": str(data.get("link") or "").strip()[:500],
        "status": str(data.get("status") or "Đang Bật").strip()[:60],
        "note": str(data.get("note") or "").strip()[:600],
        "showcase_id": str(data.get("showcase_id") or prev.get("showcase_id") or "").strip()[:60],
        "shop_name": str(data.get("shop_name") or prev.get("shop_name") or "").strip()[:120],
        "stock_info": str(data.get("stock_info") or prev.get("stock_info") or "").strip()[:80],
        "orders": int(data.get("orders") if str(data.get("orders") or "").strip().isdigit() else (prev.get("orders") or 0)),
        "gmv": int(data.get("gmv") if str(data.get("gmv") or "").strip().isdigit() else (prev.get("gmv") or 0)),
        "revenue_vnd": int(data.get("revenue_vnd") if str(data.get("revenue_vnd") or "").strip().isdigit() else (prev.get("revenue_vnd") or 0)),
    }
    raw_score = str(data.get("score") or "").strip()
    if raw_score.isdigit():
        score = max(0, min(100, int(raw_score)))
    else:
        score, dec_auto, _ = auto_score(row_dict)
        if not data.get("decision") and not prev.get("decision"):
            decision = dec_auto

    ts = db.now_iso()
    with db.tx() as c:
        if old_code and old_code.strip().upper() != code:
            c.execute("DELETE FROM products WHERE code=?", (old_code.strip().upper(),))
        c.execute(
            """INSERT OR REPLACE INTO products(
                code, element, name, material, price, commission, link, status, note, synced_at,
                video_name, benefit, cta, category, decision, score, source, showcase_id, shop_name,
                stock_info, est_commission, orders, gmv, revenue_vnd, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row_dict["code"], row_dict["element"], row_dict["name"], row_dict["material"],
                row_dict["price"], row_dict["commission"], row_dict["link"], row_dict["status"],
                row_dict["note"], prev.get("synced_at") or ts, row_dict["video_name"], row_dict["benefit"],
                row_dict["cta"], row_dict["category"], decision, score, source, row_dict["showcase_id"],
                row_dict["shop_name"], row_dict["stock_info"], row_dict["est_commission"],
                row_dict["orders"], row_dict["gmv"], row_dict["revenue_vnd"], ts,
            ),
        )
    return code


def set_decision(code: str, decision: str, score: int | None = None, note: str | None = None) -> None:
    init()
    c_up = (code or "").strip().upper()
    if decision not in DECISIONS:
        raise ValueError("Quyết định không hợp lệ.")
    ts = db.now_iso()
    with db.tx() as c:
        if score is not None and note is not None:
            c.execute("UPDATE products SET decision=?, score=?, note=?, updated_at=? WHERE code=?",
                      (decision, max(0, min(100, int(score))), note.strip()[:600], ts, c_up))
        elif score is not None:
            c.execute("UPDATE products SET decision=?, score=?, updated_at=? WHERE code=?",
                      (decision, max(0, min(100, int(score))), ts, c_up))
        else:
            c.execute("UPDATE products SET decision=?, updated_at=? WHERE code=?", (decision, ts, c_up))


def update_sales(code: str, orders: int, gmv: int, revenue_vnd: int) -> None:
    init()
    with db.tx() as c:
        c.execute(
            "UPDATE products SET orders=?, gmv=?, revenue_vnd=?, updated_at=? WHERE code=?",
            (max(0, int(orders)), max(0, int(gmv)), max(0, int(revenue_vnd)), db.now_iso(), (code or "").strip().upper()),
        )


def delete_local(code: str) -> None:
    init()
    with db.tx() as c:
        c.execute("DELETE FROM products WHERE code=?", ((code or "").strip().upper(),))


def import_showcase(items: list[dict]) -> dict:
    """Nạp danh sách sản phẩm từ Showcase TikTok Shop hoặc Đề xuất Affiliate vào bảng quản lý cục bộ."""
    init()
    saved = 0
    for it in items:
        if not isinstance(it, dict) or not str(it.get("name") or "").strip():
            continue
        save_local({
            "code": it.get("code") or "",
            "element": it.get("element") or "",
            "name": it.get("name") or "",
            "video_name": it.get("video_name") or "",
            "category": it.get("category") or "",
            "material": it.get("material") or "",
            "benefit": it.get("benefit") or "",
            "cta": it.get("cta") or "",
            "price": it.get("price") or "",
            "commission": it.get("commission") or "",
            "est_commission": it.get("est_commission") or "",
            "link": it.get("link") or "",
            "status": it.get("status") or "Live",
            "note": it.get("note") or "",
            "decision": it.get("decision") or "",
            "score": it.get("score") if it.get("score") is not None else "",
            "source": it.get("source") or "showcase",
            "showcase_id": it.get("showcase_id") or "",
            "shop_name": it.get("shop_name") or "",
            "stock_info": it.get("stock_info") or "",
        })
        saved += 1
    return {"saved": saved, "counts": decision_counts()}


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
