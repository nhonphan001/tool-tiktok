"""Gói sản xuất: lời thoại 4 cảnh, chữ trên hình, caption, bình luận ghim, lá số, SKU.

Kiểm tra trước khi dựng video (0 token): B.1 (dẫn ra ngoài), B.4 (bói toán/bùa), quy tắc 2 loại video,
đối chiếu SKU với bảng quản trị, đối chiếu Nhật chủ/tứ trụ ghi trong kịch bản với lá số tính được,
số âm tiết mỗi cảnh, CTA. Sinh khối nhan_video và phiếu gói (Markdown) cho Gemini.
"""
from __future__ import annotations

import difflib
import json
import re

from . import analytics, battu, compliance, db, products, tags

SCENES = ("scene1", "scene2", "scene3", "scene4")
FIELDS = ("goi", "title", "loai", "content_group", "sku", "product_name", "on_screen", "caption", "pinned", "note",
          *SCENES)
LOAI = {1: "Video giải mã lá số (không giỏ hàng, không quảng cáo)", 2: "Video sản phẩm (giỏ hàng, được quảng cáo)"}
STATUS = {"nhap": "Nháp", "san_sang": "Sẵn sàng dựng", "da_dang": "Đã đăng"}
SYLLABLE_MIN, SYLLABLE_MAX = 24, 28  # 24–28 âm tiết / cảnh 8 giây (chuẩn của quy trình v2.5)

SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goi TEXT, title TEXT, loai INTEGER, content_group INTEGER, sku TEXT, product_name TEXT,
    birth_json TEXT, scene1 TEXT, scene2 TEXT, scene3 TEXT, scene4 TEXT, on_screen TEXT,
    caption TEXT, pinned TEXT, note TEXT, status TEXT DEFAULT 'nhap', video_id TEXT, link_source TEXT,
    created_at TEXT, updated_at TEXT
);
"""

LA_SO_TERMS = re.compile(r"la\s*so|bat\s*tu|nhat\s*chu|tu\s*tru|dung\s*than|hy\s*than|can\s*chi"
                         r"|thieu\s*(hut\s*)?(kim|moc|thuy|hoa|tho)\b|menh\s*(kim|moc|thuy|hoa|tho)\b")
ITEM_ADVICE = re.compile(r"\b(mang|deo|dat|dung|treo|chung|sam|mua)\b.{0,30}\b(vong|da|tram|am|den|chuong|vat\s*pham"
                         r"|san\s*pham|lac|nhan|day\s*chuyen|tuong|ho\s*lo|ty\s*huu|thach\s*anh)\b")
CAN_RX = "|".join(battu.CAN)
CHI_RX = "|".join(battu.CHI)
PILLAR = rf"(?:{CAN_RX})\s+(?:{CHI_RX})"
FOUR_PILLARS = re.compile(rf"({PILLAR})\s*[–\-,·]\s*({PILLAR})\s*[–\-,·]\s*({PILLAR})(?:\s*[–\-,·]\s*({PILLAR}))?")
NHAT_CHU_CLAIM = re.compile(rf"[Nn]hật\s+chủ\s+(?:là\s+)?({CAN_RX})")
DUNG_THAN_CLAIM = re.compile(r"[Dd]ụng\s+thần\s+(?:là\s+)?(Mộc|Hỏa|Thổ|Kim|Thủy)")


def init() -> None:
    with db.tx() as c:
        c.executescript(SCHEMA)


# --------------------------------------------------------------------------- lưu / đọc
def get(pid: int) -> dict | None:
    init()
    p = db.query_one("SELECT * FROM packages WHERE id=?", (pid,))
    if p:
        p["birth"] = json.loads(p["birth_json"] or "{}")
    return p


def all_packages() -> list[dict]:
    init()
    rows = db.query("SELECT * FROM packages ORDER BY id DESC")
    for p in rows:
        p["birth"] = json.loads(p["birth_json"] or "{}")
    return rows


def save(data: dict, pid: int | None = None) -> int:
    init()
    row = {k: (str(data.get(k) or "").strip()) for k in FIELDS}
    row["loai"] = int(row["loai"] or 1)
    row["content_group"] = int(row["content_group"]) if row["content_group"] else None
    row["sku"] = row["sku"].upper()
    birth = {k: str(data.get(k) or "").strip() for k in ("dd", "mm", "yy", "t", "lich", "nhuan", "gioi")}
    row["birth_json"] = json.dumps(birth if birth["dd"] and birth["mm"] and birth["yy"] else {}, ensure_ascii=False)
    status = data.get("status") or None
    now = db.now_iso()
    with db.tx() as c:
        if pid:
            sets = ", ".join(f"{k}=?" for k in row) + ", updated_at=?" + (", status=?" if status else "")
            c.execute(f"UPDATE packages SET {sets} WHERE id=?",
                      (*row.values(), now, *([status] if status else []), pid))
            return pid
        cols = ", ".join(row) + ", status, created_at, updated_at"
        return c.execute(f"INSERT INTO packages({cols}) VALUES({','.join('?' * (len(row) + 3))})",
                         (*row.values(), status or "nhap", now, now)).lastrowid


def delete(pid: int) -> None:
    with db.tx() as c:
        c.execute("DELETE FROM packages WHERE id=?", (pid,))


# --------------------------------------------------------------------------- kiểm tra
def chart_of(p: dict) -> tuple[dict | None, str | None]:
    b = p.get("birth") or {}
    if not (b.get("dd") and b.get("mm") and b.get("yy")):
        return None, None
    try:
        t = (b.get("t") or "").strip()
        h, mi = (int(t.split(":")[0]), int(t.split(":")[1])) if t else (None, 0)
        return battu.lap_la_so(int(b["dd"]), int(b["mm"]), int(b["yy"]), h, mi, b.get("gioi") or None,
                               b.get("lich") or "duong", bool(b.get("nhuan"))), None
    except (ValueError, IndexError) as e:
        return None, str(e)


def syllables(text: str) -> int:
    return len(re.findall(r"[^\W\d_]+", text or ""))


def all_text(p: dict) -> str:
    return "\n".join(p.get(k) or "" for k in (*SCENES, "on_screen", "caption", "pinned"))


def check(p: dict) -> dict:
    """Trả về {items: [{level: error|warn|ok, rule, msg}], errors, warns, ads_ok, chart, hanh, product}."""
    items: list[dict] = []

    def add(level, rule, msg):
        items.append({"level": level, "rule": rule, "msg": msg})

    loai = int(p.get("loai") or 1)
    has_cart = loai == 2
    text = all_text(p)
    norm = compliance.normalize(text)

    if not (p.get("goi") or "").strip():
        add("warn", "Thông tin", "Chưa ghi số Gói.")
    if not any((p.get(s) or "").strip() for s in SCENES) and not (p.get("caption") or "").strip():
        add("error", "Thông tin", "Chưa có lời thoại hoặc caption để kiểm tra.")

    # B.1 + lời hứa + B.4: kiểm từng phần để báo đúng chỗ
    parts = [("Cảnh " + str(i + 1), p.get(s) or "") for i, s in enumerate(SCENES)] + \
            [("Chữ trên hình", p.get("on_screen") or ""), ("Caption", p.get("caption") or ""),
             ("Bình luận ghim", p.get("pinned") or "")]
    fortune_any = False
    for label, t in parts:
        if not t.strip():
            continue
        r = compliance.check(t, has_cart)
        for x in r["offsite"]:
            if has_cart:
                add("error", "B.1", f"{label}: mời ra ngoài TikTok — {x['label']} (“{x['match']}”).")
            elif x["code"] in ("domain", "url"):
                add("error", "B.1", f"{label}: không ghi tên miền/đường link, chỉ nói chung “xem trang cá nhân của Cô Kim”"
                                    f" (“{x['match']}”).")
            elif x["code"] != "trang_ca_nhan":
                add("warn", "B.1", f"{label}: nên thay “{x['match']}” bằng “xem trang cá nhân của Cô Kim”.")
        fortune_codes = {f["code"] for f in r["fortune"]}
        for x in r["promise"]:
            if x["code"] in fortune_codes:
                continue
            add("error", "Hứa hẹn", f"{label}: {x['label']} (“{x['match']}”).")
        for x in r["fortune"]:
            if loai == 1 and x["code"] == "bu_khuyet_la_so":
                continue  # nói lá số thiếu hành là nội dung bình thường của video lá số
            fortune_any = True
            add("error" if has_cart else "warn", "B.4", f"{label}: {x['label']} (“{x['match']}”)"
                + ("" if has_cart else " — video lá số vẫn nên tránh, và không chạy quảng cáo."))

    # Quy tắc 2 loại video
    if loai == 1:
        m = ITEM_ADVICE.search(norm)
        if m:
            add("warn", "B.4.1", f"Video lá số đang khuyên dùng vật phẩm (“{m.group(0)}”): không nối lá số với vật phẩm.")
    product = None
    sku = (p.get("sku") or "").strip().upper()
    if loai == 1 and sku:
        add("error", "B.4.3", "Video giải mã lá số không gắn giỏ hàng / SKU.")
    if loai == 2:
        if not sku:
            add("error", "B.4.3", "Video sản phẩm cần chọn SKU.")
        cleaned = norm
        for cta in compliance.ALLOWED_CTA:
            cleaned = cleaned.replace(compliance.normalize(cta), " ")
        cleaned = re.sub(r"de\s*lai\s*ngay\s*(gio\s*)?sinh[^.\n]*", " ", cleaned)
        m = LA_SO_TERMS.search(cleaned)
        if m:
            add("error", "B.4.3", f"Video sản phẩm không xem lá số (“{m.group(0)}”). Chỉ mô tả vật phẩm: chất liệu, màu sắc, "
                                  "cách dùng.")

    # SKU ↔ bảng quản trị
    if sku:
        prods = products.by_code()
        if not prods:
            add("warn", "B.3", "Chưa đồng bộ bảng sản phẩm: chưa đối chiếu được SKU (trang Sản phẩm → Đọc lại bảng).")
        elif sku not in prods:
            add("error", "B.3", f"SKU {sku} không có trong bảng quản trị sản phẩm.")
        else:
            product = prods[sku]
            name = (p.get("product_name") or "").strip()
            if not name:
                add("warn", "B.3", f"Chưa ghi tên sản phẩm trong kịch bản. Tên đúng theo bảng: “{product['name']}”.")
            elif compliance.normalize(name).strip() != compliance.normalize(product["name"]).strip():
                add("error", "B.3", f"Tên sản phẩm phải chép đúng bảng: “{product['name']}” (đang ghi “{name}”).")
            if not (product.get("link") or "").startswith("http"):
                add("warn", "B.3", f"{sku} chưa có link TikTok Shop thật trong bảng.")
            if loai == 2 and compliance.normalize(product["name"]).strip() not in norm:
                add("warn", "B.3", "Lời thoại/caption chưa nhắc tên sản phẩm đúng như bảng.")
            if re.search(r"ngung|het\s*hang|tam\s*dung", compliance.normalize(product.get("status") or "")):
                add("warn", "B.3", f"Trạng thái {sku} trong bảng: “{product['status']}”.")

    # Lá số
    chart, chart_err = chart_of(p)
    if chart_err:
        add("error", "B.2", f"Ngày giờ sinh không hợp lệ: {chart_err}")
    if loai == 1 and not chart and not chart_err:
        add("warn", "B.2", "Ghi rõ ngày giờ sinh dương lịch của lá số để tool tính và đối chiếu (B.2).")
    if chart:
        for m in NHAT_CHU_CLAIM.finditer(text):
            if m.group(1) != chart["nhat_chu"]:
                add("error", "B.2", f"Kịch bản ghi “Nhật chủ {m.group(1)}” nhưng lá số tính được Nhật chủ là "
                                    f"{chart['nhat_chu']} (can trụ Ngày).")
        for m in FOUR_PILLARS.finditer(text):
            claimed = [x for x in m.groups() if x]
            actual = [x for x in chart["tru"] if x]
            if [re.sub(r"\s+", " ", x) for x in claimed] != actual[:len(claimed)]:
                add("error", "B.2", f"Tứ trụ trong kịch bản “{' – '.join(claimed)}” khác lá số tính được "
                                    f"“{chart['tu_tru']}”.")
        for m in DUNG_THAN_CLAIM.finditer(text):
            if m.group(1) != chart["dung_than"]:
                add("warn", "B.2", f"Kịch bản ghi Dụng thần {m.group(1)}, bộ tính gợi ý {chart['dung_than']} "
                                   "(Dụng thần mang tính luận giải — Claude xác nhận).")
        for cb in chart["canh_bao"]:
            add("warn", "B.2", "Lá số: " + cb)

    # Âm tiết mỗi cảnh
    for i, s in enumerate(SCENES):
        t = (p.get(s) or "").strip()
        if not t:
            continue
        n = syllables(t)
        if not SYLLABLE_MIN <= n <= SYLLABLE_MAX:
            add("warn", "Nhịp 8s", f"Cảnh {i + 1}: {n} âm tiết (chuẩn {SYLLABLE_MIN}–{SYLLABLE_MAX} cho 8 giây).")

    # CTA
    cap_norm = compliance.normalize((p.get("caption") or "") + " " + (p.get("pinned") or "") + " " + (p.get("scene4") or ""))
    if loai == 2 and "gio hang" not in cap_norm:
        add("warn", "CTA", "Thêm CTA được phép: “bấm giỏ hàng góc trái”.")
    if loai == 1 and "ngay sinh" not in cap_norm and "ngay gio sinh" not in cap_norm:
        add("warn", "CTA", "Gợi ý CTA: “để lại ngày sinh dưới bình luận để Cô Kim giải mã”.")

    errors = sum(1 for i in items if i["level"] == "error")
    warns = sum(1 for i in items if i["level"] == "warn")
    if not items:
        add("ok", "Tổng", "Không phát hiện vấn đề.")
    hanh = chart["dung_than"] if (loai == 1 and chart) else (product["element"] if product else "")
    return {"items": items, "errors": errors, "warns": warns, "ads_ok": loai == 2 and errors == 0 and not fortune_any,
            "chart": chart, "hanh": hanh, "product": product}


# --------------------------------------------------------------------------- xuất
def nhan_video_block(p: dict, chk: dict) -> str:
    chart = chk["chart"]
    lines = [
        "nhan_video:",
        f"  goi: {p.get('goi') or ''}",
        f"  loai: {p.get('loai')}  # {LOAI.get(int(p.get('loai') or 1), '')}",
        f"  nhom_noi_dung: {p.get('content_group') or ''}",
        f"  ma_san_pham: {p.get('sku') or ''}",
        f"  ten_san_pham: {(chk['product'] or {}).get('name') or p.get('product_name') or ''}",
        f"  hanh_dung_than: {chk['hanh'] or ''}",
        f"  co_gio_hang: {'co' if int(p.get('loai') or 1) == 2 else 'khong'}",
        f"  duoc_chay_quang_cao: {'true' if chk['ads_ok'] else 'false'}",
        f"  la_so: {battu.mo_ta_ngan(chart) if chart else ''}",
        f"  caption_de_xuat: {json.dumps(p.get('caption') or '', ensure_ascii=False)}",
        f"  kiem_tra_tool: {'dat' if chk['errors'] == 0 else 'chua_dat'} ({chk['errors']} lỗi, {chk['warns']} cảnh báo)",
    ]
    return "\n".join(lines)


def to_markdown(p: dict, chk: dict) -> str:
    out = [f"# Phiếu gói {p.get('goi') or p.get('id')} — {p.get('title') or ''}", "",
           f"- Loại: {LOAI.get(int(p.get('loai') or 1))}",
           f"- Nhóm nội dung: {p.get('content_group') or '—'} {tags.CONTENT_GROUPS.get(p.get('content_group') or 0, '')}",
           f"- SKU: {p.get('sku') or '—'} {('· ' + chk['product']['name']) if chk['product'] else ''}",
           f"- Trạng thái: {STATUS.get(p.get('status') or 'nhap')}", ""]
    if chk["chart"]:
        c = chk["chart"]
        out += ["## Lá số (TikTok Manager tính, Nhật chủ = can trụ Ngày)", f"- {battu.mo_ta_ngan(c)}",
                f"- Âm lịch: {c['am_lich']}"] + [f"- ⚠ {x}" for x in c["canh_bao"]] + [""]
    out.append("## Lời thoại 4 cảnh × 8 giây")
    for i, s in enumerate(SCENES):
        t = (p.get(s) or "").strip()
        out.append(f"{i + 1}. ({syllables(t)} âm tiết) {t or '—'}")
    out += ["", "## Chữ trên hình", p.get("on_screen") or "—", "", "## Caption", p.get("caption") or "—", "",
            "## Bình luận ghim", p.get("pinned") or "—", "", "## Kết quả kiểm tra của TikTok Manager"]
    out += [f"- [{i['level'].upper()}] {i['rule']}: {i['msg']}" for i in chk["items"]]
    out += ["", "```yaml", nhan_video_block(p, chk), "```", ""]
    if p.get("note"):
        out += ["## Ghi chú", p["note"], ""]
    return "\n".join(out)


# --------------------------------------------------------------------------- liên kết với video đã đăng
def link_video(pid: int, video_id: str, source: str = "manual") -> None:
    p = get(pid)
    if not p:
        return
    chk = check(p)
    with db.tx() as c:
        c.execute("UPDATE packages SET video_id=?, link_source=?, status='da_dang', updated_at=? WHERE id=?",
                  (video_id, source, db.now_iso(), pid))
    tags.save(video_id, {"goi": p.get("goi") or "", "product_code": p.get("sku") or "", "element": chk["hanh"] or "",
                         "content_group": p.get("content_group"), "has_cart": int(p.get("loai") or 1) == 2,
                         "note": f"Gói {p.get('goi') or pid}"}, source="package")


def _sim(a: str, b: str) -> float:
    a, b = compliance.normalize(a)[:220].strip(), compliance.normalize(b)[:220].strip()
    if not a or not b:
        return 0.0
    if a[:60] and a[:60] in b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def auto_link(open_id: str, threshold: float = 0.8) -> list[tuple[int, str]]:
    """Sau mỗi lần quét: gói chưa gắn video + caption giống video mới đăng → tự gắn và gắn nhãn."""
    init()
    linked = []
    pending = db.query("SELECT * FROM packages WHERE (video_id IS NULL OR video_id='') AND caption != ''")
    if not pending:
        return linked
    used = {r["video_id"] for r in db.query("SELECT video_id FROM packages WHERE video_id != ''")}
    videos = [v for v in analytics.get_videos(open_id) if v["id"] not in used]
    from datetime import datetime, timedelta

    for p in pending:
        try:
            since = int((datetime.fromisoformat(p["created_at"]) - timedelta(days=2)).timestamp())
        except (TypeError, ValueError):
            since = 0
        scored = []
        for v in videos:
            sc = _sim(p["caption"], f"{v.get('description') or ''} {v.get('title') or ''}")
            if sc >= threshold:
                # ưu tiên: giống nhất → đăng sau khi soạn gói → mới nhất
                scored.append((round(sc, 3), (v.get("create_time") or 0) >= since, v.get("create_time") or 0, v))
        best = max(scored, key=lambda x: x[:3])[3] if scored else None
        if best:
            link_video(p["id"], best["id"], source="auto")
            used.add(best["id"])
            videos = [v for v in videos if v["id"] != best["id"]]
            linked.append((p["id"], best["id"]))
    return linked
