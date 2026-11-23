"""Gói sản xuất: lời thoại 4 cảnh, chữ trên hình, caption, bình luận ghim, lá số, SKU.

Kiểm tra trước khi dựng video (0 token): B.1 (dẫn ra ngoài), B.4 (bói toán/bùa), quy tắc 2 loại video,
đối chiếu SKU với bảng quản trị, đối chiếu Nhật chủ/tứ trụ ghi trong kịch bản với lá số tính được,
số âm tiết mỗi cảnh, CTA. Sinh khối nhan_video và phiếu gói (Markdown) cho Gemini.
"""
from __future__ import annotations

import difflib
import json
import re
import unicodedata

from . import analytics, battu, compliance, db, products, tags
from .products import real_link

MAX_SCENES = 8  # 4 cảnh (~32–40 giây) hoặc 7 cảnh (video trên 60 giây), tối đa 8
SCENES = tuple(f"scene{i}" for i in range(1, MAX_SCENES + 1))
FIELDS = ("goi", "title", "loai", "content_group", "sku", "product_name", "on_screen", "caption", "pinned", "note",
          *SCENES, "ads_plan")
PROMPTS = tuple(f"prompt{i}" for i in range(1, MAX_SCENES + 1))   # prompt video (Veo / Flow) từng cảnh
IMAGES = tuple(f"image{i}" for i in range(1, MAX_SCENES + 1))     # ID ảnh Drive từng cảnh
VIDEOS = ("final_video", "clean_video")                  # ID video thành phẩm (có phụ đề) / bản sạch
LOAI = {1: "Video giải mã lá số (không giỏ hàng, không quảng cáo)", 2: "Video sản phẩm (giỏ hàng; quảng cáo chỉ khi tool báo được)",
        3: "Video tăng follow (không giỏ hàng; được quảng cáo nếu sạch bói toán)"}
LOAI_SHORT = {1: "Lá số", 2: "Sản phẩm", 3: "Tăng follow"}
STATUS = {"nhap": "Nháp", "san_sang": "Sẵn sàng dựng", "len_lich": "Đã lên lịch đăng", "da_dang": "Đã đăng"}
SYLLABLE_MIN, SYLLABLE_MAX = 24, 28  # mặc định cũ (clip 8 giây); dùng syllable_range() theo Cài đặt


def n_scenes(p: dict) -> int:
    """Số cảnh của gói: cảnh cuối cùng có lời thoại / prompt / ảnh (ít nhất 4)."""
    n = 4
    for i in range(1, MAX_SCENES + 1):
        if any(str(p.get(f"{k}{i}") or "").strip() for k in ("scene", "prompt", "image")):
            n = max(n, i)
    return n


def clip_seconds() -> int:
    from .config import settings

    s = int(settings.clip_seconds or 10)
    return s if 6 <= s <= 15 else 10


def syllable_range() -> tuple[int, int]:
    """Số âm tiết/cảnh theo độ dài clip: giọng 3,8–4,0 âm tiết/giây, chừa ~0,7 giây vào/ra giọng.
    8 giây → 24–28 · 10 giây → 24–34."""
    s = clip_seconds()
    return SYLLABLE_MIN, int(round(s * 3.45))

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
# So CÓ DẤU (chữ thường) để không bắt nhầm "đất dày kiên nhẫn" (= "đặt … nhẫn" khi bỏ dấu)
_W = r"[\wÀ-ỹ]"
ITEM_ADVICE = re.compile(rf"(?<!{_W})(mang|đeo|đặt|dùng|treo|chưng|sắm|mua)(?!{_W}).{{0,30}}?(?<!{_W})(vòng|đá|trầm|ấm|đèn|chuông|"
                         rf"vật\s*phẩm|sản\s*phẩm|lắc|nhẫn|dây\s*chuyền|tượng|hồ\s*lô|tỳ\s*hưu|thạch\s*anh)(?!{_W})")
CAN_RX = "|".join(battu.CAN)
CHI_RX = "|".join(battu.CHI)
PILLAR = rf"(?:{CAN_RX})\s+(?:{CHI_RX})"
FOUR_PILLARS = re.compile(rf"({PILLAR})\s*[–\-,·]\s*({PILLAR})\s*[–\-,·]\s*({PILLAR})(?:\s*[–\-,·]\s*({PILLAR}))?")
NHAT_CHU_CLAIM = re.compile(rf"[Nn]hật\s+chủ\s+(?:là\s+)?({CAN_RX})")
DUNG_THAN_CLAIM = re.compile(r"[Dd]ụng\s+thần\s+(?:là\s+)?(Mộc|Hỏa|Thổ|Kim|Thủy)")


def init() -> None:
    with db.tx() as c:
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(packages)").fetchall()}
        for col in ("ads_plan", "prompts_json", "images_json", "final_video", "clean_video", "post_plan_json", "clips_json",
                    *[f"scene{i}" for i in range(5, MAX_SCENES + 1)]):
            if col not in cols:
                c.execute(f"ALTER TABLE packages ADD COLUMN {col} TEXT DEFAULT ''")


def _expand(p: dict) -> dict:
    """prompts_json / images_json -> prompt1..8 / image1..8 để form và kiểm tra dùng chung."""
    pr = json.loads(p.get("prompts_json") or "{}")
    im = json.loads(p.get("images_json") or "{}")
    for i in range(1, MAX_SCENES + 1):
        p[f"prompt{i}"] = pr.get(str(i), "")
        p[f"image{i}"] = im.get(str(i), "")
    return p


# --------------------------------------------------------------------------- lưu / đọc
def get(pid: int) -> dict | None:
    init()
    p = db.query_one("SELECT * FROM packages WHERE id=?", (pid,))
    if p:
        p["birth"] = json.loads(p["birth_json"] or "{}")
        _expand(p)
    return p


def all_packages() -> list[dict]:
    init()
    rows = db.query("SELECT * FROM packages ORDER BY id DESC")
    for p in rows:
        p["birth"] = json.loads(p["birth_json"] or "{}")
        _expand(p)
    return rows


def save(data: dict, pid: int | None = None) -> int:
    init()
    row = {k: (str(data.get(k) or "").strip()) for k in FIELDS}
    row["loai"] = int(row["loai"] or 1)
    row["content_group"] = int(row["content_group"]) if row["content_group"] else None
    row["sku"] = row["sku"].upper()
    birth = {k: str(data.get(k) or "").strip() for k in ("dd", "mm", "yy", "t", "lich", "nhuan", "gioi")}
    row["birth_json"] = json.dumps(birth if birth["dd"] and birth["mm"] and birth["yy"] else {}, ensure_ascii=False)
    row["prompts_json"] = json.dumps({str(i): str(data.get(f"prompt{i}") or "").strip() for i in range(1, MAX_SCENES + 1)
                                      if str(data.get(f"prompt{i}") or "").strip()}, ensure_ascii=False)
    for k in VIDEOS:
        row[k] = _drive_id(str(data.get(k) or ""))
    if "post_plan_json" in data:
        row["post_plan_json"] = data["post_plan_json"]
    row["images_json"] = json.dumps({str(i): _drive_id(str(data.get(f"image{i}") or "")) for i in range(1, MAX_SCENES + 1)
                                     if str(data.get(f"image{i}") or "").strip()}, ensure_ascii=False)
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


def _drive_id(v: str) -> str:
    """Nhận ID hoặc link Drive, trả về ID."""
    v = v.strip()
    m = re.search(r"/d/([A-Za-z0-9_-]{20,})|[?&]id=([A-Za-z0-9_-]{20,})", v)
    return (m.group(1) or m.group(2)) if m else v


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


_NUMWORDS = {"khong", "mot", "hai", "ba", "bon", "nam", "sau", "bay", "tam", "chin", "muoi", "moi", "tu", "lam", "le",
             "linh", "tram", "nghin", "ngan", "gio", "phut", "h"}


def _no_numbers(norm: str) -> str:
    return " ".join(w for w in norm.split() if not w.isdigit() and w not in _NUMWORDS and not re.fullmatch(r"\d+h\d*", w))


def syllables(text: str) -> int:
    """Đếm theo cách đọc: '20/11' = 'hai mươi tháng mười một' (4 âm tiết)."""
    from .tts import speakable

    return len(re.findall(r"[^\W\d_]+", speakable(text or "", year_digits=True)))


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
            elif loai == 3:
                add("error", "B.1", f"{label}: video chạy quảng cáo không mời ra ngoài TikTok (“{x['match']}”).")
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
            add("error" if loai in (2, 3) else "warn", "B.4", f"{label}: {x['label']} (“{x['match']}”)"
                + ("" if loai in (2, 3) else " — video lá số vẫn nên tránh, và không chạy quảng cáo."))

    # Quy tắc 2 loại video
    if loai == 1:
        m = ITEM_ADVICE.search(unicodedata.normalize("NFC", text).lower())
        if m:
            add("warn", "B.4.1", f"Video lá số đang khuyên dùng vật phẩm (“{m.group(0)}”): không nối lá số với vật phẩm.")
    product = None
    product_no_ads = False
    sku = (p.get("sku") or "").strip().upper()
    if loai == 1 and sku:
        add("error", "B.4.3", "Video giải mã lá số không gắn giỏ hàng / SKU.")
    if loai == 3:
        if sku:
            add("error", "B.4.3", "Video tăng follow không gắn giỏ hàng / SKU.")
        m = LA_SO_TERMS.search(norm) or re.search(r"de\s*lai\s*ngay\s*(gio\s*)?sinh|giai\s*ma\s*(la\s*so|van\s*menh)|xem\s*(tuoi|menh|boi)", norm)
        if m:
            fortune_any = True
            add("error", "Quảng cáo", f"Video chạy quảng cáo không được xem lá số / bói toán / mời để lại ngày sinh "
                                      f"(“{m.group(0)}”) — TikTok cấm quảng cáo dịch vụ bói toán tại VN.")
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
            vname = (product.get("video_name") or "").strip()
            # Tên đúng để dùng trong video: cột "Tên dùng trong video" (sạch B.4); chưa có thì dùng tên trong bảng
            ref = vname or product["name"]
            if not vname:
                bad_name = compliance.check(product["name"], True)
                if bad_name["promise"] or bad_name["offsite"]:
                    add("error", "B.3/B.4", f"Tên {sku} trong bảng có từ cấm B.4 "
                        f"({', '.join(x['match'] for x in bad_name['promise'] + bad_name['offsite'])}). "
                        "Cần điền cột “Tên dùng trong video” trong bảng quản trị rồi đọc lại bảng.")
                else:
                    add("warn", "B.3", f"{sku} chưa có cột “Tên dùng trong video” trong bảng — tạm đối chiếu theo tên đầy đủ.")
            if not name:
                add("warn", "B.3", f"Chưa ghi tên sản phẩm trong kịch bản. Tên dùng trong video: “{ref}”.")
            elif compliance.normalize(name).strip() not in (compliance.normalize(ref).strip(),
                                                              compliance.normalize(product["name"]).strip()):
                add("error", "B.3", f"Tên sản phẩm phải đúng bảng: “{ref}” (đang ghi “{name}”).")
            if not real_link(product.get("link") or ""):
                add("warn", "B.3", f"{sku} chưa có link TikTok Shop thật trong bảng (đang là link tạm hoặc trống).")
            if loai == 2 and compliance.normalize(ref).strip() not in norm:
                add("warn", "B.3", f"Lời thoại/caption chưa nhắc tên sản phẩm “{ref}”.")
            for a in products.audit(product):
                if a["field"] in ("Tên trong bảng", "Phân loại"):
                    product_no_ads = True
                    add("warn", "B.4", f"{sku}: {a['field']} trong bảng mang tính tâm linh ({a['found']}) — TikTok có thể "
                                       "xếp sản phẩm vào nhóm bùa hộ mệnh: KHÔNG chạy Quảng bá/GMV Max cho SKU này.")
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

    # Prompt video phải chứa đúng lời thoại của cảnh (Veo đọc theo câu trong prompt)
    for i, s in enumerate(SCENES, 1):
        scene, prompt = (p.get(s) or "").strip(), (p.get(f"prompt{i}") or "").strip()
        if not scene or not prompt:
            continue
        from .tts import speakable

        np_ = re.sub(r"[^a-z0-9]+", " ", compliance.normalize(prompt))
        forms = {re.sub(r"[^a-z0-9]+", " ", compliance.normalize(x)).strip()
                 for x in (scene, speakable(scene), speakable(scene, year_digits=True))}
        # so lỏng: bỏ số và chữ số đọc ("1987" / "một chín tám bảy" / "mười chín tám mươi bảy" đều khớp)
        loose = _no_numbers(" ".join(sorted(forms, key=len)[:1])) if forms else ""
        if all(f and f not in np_ for f in forms) and not (loose and loose in _no_numbers(np_)):
            add("warn", "Prompt", f"Prompt video cảnh {i} không chứa đúng lời thoại cảnh {i} — sửa cho khớp để giọng đọc đúng kịch bản.")
        if re.search(r"\bmusic\b", prompt, re.I) and not re.search(r"no\s+(background\s+)?music", prompt, re.I):
            add("warn", "Prompt", f"Prompt cảnh {i} có nhạc nền — định dạng kênh là không nhạc nền.")

    # Cảnh trống giữa chừng + độ dài video
    ns = n_scenes(p)
    missing = [str(i) for i in range(1, ns + 1) if not str(p.get(f"scene{i}") or "").strip()]
    if missing and any(str(p.get(f"scene{i}") or "").strip() for i in range(1, ns + 1)):
        add("warn", "Số cảnh", f"Gói {ns} cảnh nhưng cảnh {', '.join(missing)} chưa có lời thoại.")
    if ns >= 6:
        total = sum(syllables(p.get(f"scene{i}") or "") for i in range(1, ns + 1))
        est = total / 3.9 + ns * 0.5  # giọng 3,9 âm tiết/giây + ~0,5 giây ngắt giữa cảnh sau khi cắt lặng
        if est < 61:
            add("warn", "Độ dài", f"{ns} cảnh, {total} âm tiết ≈ {est:.0f} giây — dưới 61 giây (cần trên 1 phút); "
                                  "thêm âm tiết cho các cảnh (tối đa mỗi cảnh theo độ dài clip).")

    # Âm tiết mỗi cảnh
    for i, s in enumerate(SCENES):
        t = (p.get(s) or "").strip()
        if not t:
            continue
        n = syllables(t)
        lo, hi = syllable_range()
        if not lo <= n <= hi:
            add("warn", "Nhịp cảnh", f"Cảnh {i + 1}: {n} âm tiết (chuẩn {lo}–{hi} cho clip {clip_seconds()} giây).")

    # CTA
    cap_norm = compliance.normalize((p.get("caption") or "") + " " + (p.get("pinned") or "") + " " + (p.get("scene4") or ""))
    if loai == 2 and "gio hang" not in cap_norm:
        add("warn", "CTA", "Thêm CTA được phép: “bấm giỏ hàng góc trái”.")
    if loai == 3 and "theo doi" not in cap_norm and "follow" not in cap_norm:
        add("warn", "CTA", "Thêm CTA tăng follow: “bấm theo dõi Cô Kim”.")
    if loai == 1 and "ngay sinh" not in cap_norm and "ngay gio sinh" not in cap_norm:
        add("warn", "CTA", "Gợi ý CTA: “để lại ngày sinh dưới bình luận để Cô Kim giải mã”.")

    errors = sum(1 for i in items if i["level"] == "error")
    warns = sum(1 for i in items if i["level"] == "warn")
    if not items:
        add("ok", "Tổng", "Không phát hiện vấn đề.")
    hanh = chart["dung_than"] if (loai == 1 and chart) else (product["element"] if product else "")
    return {"items": items, "errors": errors, "warns": warns, "ads_ok": loai in (2, 3) and errors == 0 and not fortune_any and not product_no_ads,
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
        f"  ten_san_pham: {(chk['product'] or {}).get('video_name') or (chk['product'] or {}).get('name') or p.get('product_name') or ''}",
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
    out.append(f"## Lời thoại {n_scenes(p)} cảnh × {clip_seconds()} giây")
    for i, s in enumerate(SCENES[:n_scenes(p)]):
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
