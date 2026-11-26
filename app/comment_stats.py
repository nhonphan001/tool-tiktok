"""Thống kê & quản lý bình luận tổng hợp từ TikTok Studio (tiktokstudio/comment).

Quyền riêng tư (bắt buộc):
- Dữ liệu chỉ lưu nội bộ trong SQLite của TikTok Manager (`studio_comments`, `studio_comment_imports`).
- KHÔNG đồng bộ lên Google Drive, KHÔNG lộ qua `/api/public/*`, KHÔNG gửi nick/tên riêng cho Gemini/Claude.
- Bản xuất báo cáo Markdown (`to_markdown`) ẩn danh 100% (bỏ nick, lọc tên riêng bằng `comment_reply.anonymize`).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

from . import battu, comment_reply, comments, db

VN = timezone(timedelta(hours=7))

CATEGORIES = {
    "xin_la_so": "Xin lá số / Ngày sinh",
    "tam_su_cau_an": "Tâm sự / Cầu an / Xin vía",
    "cam_on_don_nhan": "Cảm ơn / Đón nhận / Khen",
    "emoji_khac": "Emoji / Sticker / Khác",
    "kenh": "Bình luận của kênh",
}

CAT_ORDER = ("xin_la_so", "tam_su_cau_an", "cam_on_don_nhan", "emoji_khac", "kenh")

# Bảng tra nhanh Can Chi (không dấu -> (Tên chuẩn, năm sinh tiêu biểu trong thế kỷ 20/21))
_CAN_NORM = ["giap", "at", "binh", "dinh", "mau", "ky", "canh", "tan", "nham", "quy"]
_CHI_NORM = ["ty", "suu", "dan", "mao", "thin", "ti", "ngo", "mui", "than", "dau", "tuat", "hoi"]

_VI_MAP = str.maketrans(
    "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    "ÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈÌÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ",
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd",
)


def _strip_accents(s: str) -> str:
    return (s or "").translate(_VI_MAP).lower()


def _build_ganzhi_lookup() -> dict[str, tuple[str, int]]:
    """Ánh xạ 'quy suu' -> ('Quý Sửu', 1973), ưu tiên năm sinh 1954–2013."""
    out: dict[str, tuple[str, int]] = {}
    for year in range(1954, 2014):
        idx = (year - 4) % 60
        can_i, chi_i = idx % 10, idx % 12
        proper = f"{battu.CAN[can_i]} {battu.CHI[chi_i]}"
        key = f"{_CAN_NORM[can_i]} {_CHI_NORM[chi_i]}"
        out[key] = (proper, year)
        # Biến thể chính tả phổ biến: Quí -> Quý, Mẹo -> Mão, Tỵ -> Tị
        if can_i == 9:
            out[f"qui {_CHI_NORM[chi_i]}"] = (proper, year)
        if chi_i == 3:
            out[f"{_CAN_NORM[can_i]} meo"] = (proper, year)
        if chi_i == 5:
            out[f"{_CAN_NORM[can_i]} ty"] = (proper, year)  # chú ý: Tý ưu tiên nếu trùng
    # Đảm bảo can dương + ty là Tý, can âm + ty là Tỵ
    for year in range(1954, 2014):
        idx = (year - 4) % 60
        can_i, chi_i = idx % 10, idx % 12
        if chi_i in (0, 5):
            proper = f"{battu.CAN[can_i]} {battu.CHI[chi_i]}"
            out[f"{_CAN_NORM[can_i]} ty"] = (proper, year)
            if can_i == 9 and chi_i == 5:
                out["qui ty"] = (proper, year)
    return out


GANZHI_LOOKUP = _build_ganzhi_lookup()
_GANZHI_RX = re.compile(
    r"\b(" + "|".join(sorted(GANZHI_LOOKUP.keys(), key=len, reverse=True)) + r")\b"
)

_SPACED_YEAR_RX = re.compile(r"\b(1)\s*(9)\s*(\d)\s*(\d)\b")
_SPACED_20_RX = re.compile(r"\b(2)\s*(0)\s*([01])\s*(\d)\b")
_DM_UNDER_RX = re.compile(r"(?<!\d)(\d{1,2})\s*[_/\-.]\s*(\d{1,2})(?!\s*[_/\-.]\s*\d)")
_DM_TXT_NO_YEAR_RX = re.compile(
    r"(?:ngày|ngay|ng)?\s*(\d{1,2})\s*(?:tháng|thang|th)\s*(\d{1,2})\b", re.IGNORECASE
)
_STANDALONE_YEAR_RX = re.compile(r"(?<!\d)(19[4-9]\d|200\d|201\d)(?!\d)")

_ASK_CHART_RX = re.compile(
    r"(giải\s*mã\s*giúp|xem\s*giúp|xem\s*giùm|xem\s*hộ|lá\s*số|hữu\s*duyên.*(cho|giúp|xem)|coi\s*giúp)",
    re.IGNORECASE,
)
_PRAY_MOOD_RX = re.compile(
    r"(khổ\s*lắm|khó\s*lắm|khổ\s*tận|mệt\s*mỏi|bình\s*an|mạnh\s*khỏe|sức\s*khỏe|"
    r"a\s*\.?\s*(?:di|đi)\s*đà\s*ph[aậ]t|a\s*di\s*da\s*phat|"
    r"xin\s*(?:vía|l[oộọ]c)|sin\s*l[oọ]c|cầu\s*mong|chỉ\s*(?:cần|mong)|manifest|"
    r"thành\s*tâm|may\s*mắn|mai\s*mắn|như\s*ý)",
    re.IGNORECASE,
)
_THANKS_RX = re.compile(
    r"(c[aảá]m\s*[oơ]n|cam\s*on|đón\s*nh[aậ]n|đón\s*nhan|đóng\s*nhận|rất\s*đúng|hay\s*quá|tuyệt\s*vời|nghỉ\s*ngơi)",
    re.IGNORECASE,
)


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS studio_comment_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imported_at TEXT,
            source TEXT DEFAULT 'tiktok_studio',
            total_rows INTEGER DEFAULT 0,
            inserted_rows INTEGER DEFAULT 0,
            updated_rows INTEGER DEFAULT 0,
            note TEXT DEFAULT ''
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS studio_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dedup_key TEXT UNIQUE,
            author_display TEXT DEFAULT '',
            is_creator INTEGER DEFAULT 0,
            text TEXT DEFAULT '',
            time_text TEXT DEFAULT '',
            likes INTEGER DEFAULT 0,
            reply_count INTEGER DEFAULT 0,
            replied_by_creator INTEGER DEFAULT 0,
            manual_replied INTEGER DEFAULT 0,
            video_id TEXT DEFAULT '',
            video_caption TEXT DEFAULT '',
            category TEXT DEFAULT 'khac',
            birth_summary TEXT DEFAULT '',
            birth_json TEXT DEFAULT '',
            can_chi_tags TEXT DEFAULT '',
            first_seen TEXT,
            last_seen TEXT,
            sort_order INTEGER DEFAULT 0
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_studio_comments_cat ON studio_comments(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_studio_comments_creator ON studio_comments(is_creator)")


def mask_handle(handle: str) -> str:
    """Che nick người bình luận để hiển thị an toàn: 'tothuy193' -> 't***3'."""
    h = (handle or "").strip().lstrip("@")
    if not h:
        return "(ẩn)"
    if len(h) <= 2:
        return h[0] + "*"
    if len(h) <= 5:
        return h[0] + "***" + h[-1]
    return h[:2] + "***" + h[-2:]


def _norm_birth_text(text: str) -> str:
    """Chuẩn hoá các kiểu gõ ngày/năm sinh phổ biến trong bình luận TikTok."""
    t = text or ""
    # 'ạ.18/04/1993' -> 'ạ. 18/04/1993' để không dính dấu chấm vào ngày
    t = re.sub(r"(?<=[^\d\s/.\-])\.(?=\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})", ". ", t)
    # '1 9 84' -> '1984'
    t = _SPACED_YEAR_RX.sub(r"\1\2\3\4", t)
    t = _SPACED_20_RX.sub(r"\1\2\3\4", t)
    # '17 tháng 4 1984' -> 'ngày 17 tháng 4 năm 1984' (nếu thiếu từ 'ngày')
    t = re.sub(
        r"(?<!ngày\s)(?<!ngay\s)(?<!\d)(\d{1,2})\s*(?:tháng|thang)\s*(\d{1,2})\s*(?:năm|nam)?\s*(19\d{2}|20\d{2})\b",
        r"ngày \1 tháng \2 năm \3",
        t,
        flags=re.IGNORECASE,
    )
    return t


def extract_birth_info(text: str) -> dict:
    """Nhận diện ngày/tháng/năm sinh, giờ sinh, giới tính và Can Chi nhắc tới trong 1 bình luận."""
    raw = (text or "").strip()
    norm = _norm_birth_text(raw)
    ascii_low = _strip_accents(norm)

    # 1. Tìm tất cả Can Chi được nhắc tới
    cc_found: list[tuple[str, int]] = []
    seen_cc: set[str] = set()
    for m in _GANZHI_RX.finditer(ascii_low):
        proper, yr = GANZHI_LOOKUP[m.group(1)]
        if proper not in seen_cc:
            seen_cc.add(proper)
            cc_found.append((proper, yr))

    # 2. Tách ngày sinh bằng bộ comments.parse_line (dùng lõi battu.lap_la_so)
    items = comments.parse_line(norm)
    best: dict | None = None
    chart: dict | None = None
    for it in items:
        if "d" in it and "m" in it and "y" in it:
            try:
                ch = battu.lap_la_so(
                    it["d"], it["m"], it["y"], it.get("h"), it.get("mi", 0),
                    it.get("gioi"), "am" if it.get("lunar") else "duong", bool(it.get("leap")),
                )
                best = dict(it)
                chart = ch
                break
            except ValueError:
                continue

    # 3. Trường hợp '4_10 quý sửu' hoặc '4/10 quý sửu' (có ngày+tháng + Can Chi, không ghi 4 số năm)
    if not best and cc_found:
        m_dm = _DM_UNDER_RX.search(raw) or _DM_TXT_NO_YEAR_RX.search(raw)
        if m_dm:
            dd, mm = int(m_dm.group(1)), int(m_dm.group(2))
            proper_cc, yr = cc_found[0]
            if 1 <= dd <= 31 and 1 <= mm <= 12:
                try:
                    lunar = bool(re.search(r"âm|am lich|\bal\b", ascii_low))
                    ch = battu.lap_la_so(dd, mm, yr, None, 0, None, "am" if lunar else "duong", False)
                    best = {"d": dd, "m": mm, "y": yr, "h": None, "mi": 0, "lunar": lunar, "leap": False,
                            "gioi": None, "inferred_from_canchi": proper_cc}
                    chart = ch
                except ValueError:
                    pass

    # 4. Trường hợp chỉ có năm sinh 4 chữ số (vd '1972' đứng độc lập hoặc 'sn 1984')
    year_only: int | None = None
    if not best:
        for it in items:
            if "year_only" in it:
                year_only = int(it["year_only"])
                break
        if year_only is None:
            m_yr = _STANDALONE_YEAR_RX.search(norm)
            if m_yr:
                year_only = int(m_yr.group(1))

    summary = ""
    if best and chart:
        lich_s = " AL" if best.get("lunar") else ""
        gio_s = f" {best['h']:02d}:{best['mi']:02d}" if best.get("h") is not None else ""
        cc_s = f" (suy từ {best['inferred_from_canchi']})" if best.get("inferred_from_canchi") else ""
        summary = f"{best['d']:02d}/{best['m']:02d}/{best['y']}{lich_s}{gio_s}{cc_s}"
    elif year_only:
        cc_y = battu.name(battu.ganzhi(year_only - 4))
        summary = f"Năm {year_only} ({cc_y})"
    elif cc_found:
        summary = ", ".join(f"{p} ({y})" for p, y in cc_found[:2])

    payload = {
        "has_full_date": bool(best and chart),
        "has_birth_year": bool((best and chart) or year_only is not None),
        "dd": best["d"] if best else None,
        "mm": best["m"] if best else None,
        "yy": best["y"] if best else year_only,
        "t": f"{best['h']:02d}:{best['mi']:02d}" if best and best.get("h") is not None else "",
        "lich": "am" if (best and best.get("lunar")) else "duong",
        "nhuan": 1 if (best and best.get("leap")) else 0,
        "gioi": (best.get("gioi") or "") if best else "",
        "tu_tru": chart.get("tu_tru", "") if chart else "",
        "nhat_chu": f"{chart.get('nhat_chu', '')} {chart.get('nhat_chu_hanh', '')}".strip() if chart else "",
        "dung_than": chart.get("dung_than", "") if chart else "",
        "can_chi_mentioned": [p for p, _ in cc_found],
    }
    return {
        "summary": summary,
        "can_chi_tags": ", ".join(p for p, _ in cc_found),
        "payload": payload,
    }


def classify_comment(text: str, is_creator: bool, birth_info: dict | None = None) -> str:
    """Phân loại 1 bình luận vào 5 nhóm rõ ràng."""
    if is_creator:
        return "kenh"
    b = birth_info if birth_info is not None else extract_birth_info(text)
    pl = b.get("payload") or {}
    t = (text or "").strip()
    if pl.get("has_full_date") or pl.get("has_birth_year") or _ASK_CHART_RX.search(t):
        return "xin_la_so"
    if _PRAY_MOOD_RX.search(t):
        return "tam_su_cau_an"
    if _THANKS_RX.search(t):
        return "cam_on_don_nhan"
    return "emoji_khac"


def _norm_caption(s: str) -> str:
    s = re.sub(r"#\S+", " ", s or "")
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _dedup_key(author: str, video_caption: str, text: str, occ: int = 1) -> str:
    raw = f"{(author or '').strip().lower()}|{_norm_caption(video_caption)[:120]}|{re.sub(r'\s+', ' ', (text or '').strip()).lower()}|#{occ}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def parse_import_payload(raw_text: str) -> list[dict]:
    """Đọc JSON mảng bình luận (hoặc object có khóa 'comments') hoặc khối ```json trong Markdown."""
    s = (raw_text or "").strip()
    if not s:
        return []
    blocks = re.findall(r"```json\s*(.*?)```", s, re.S)
    candidates = blocks if blocks else [s]
    for cand in reversed(candidates):
        try:
            obj = json.loads(cand)
        except ValueError:
            continue
        if isinstance(obj, list):
            return [x for x in obj if isinstance(x, dict)]
        if isinstance(obj, dict):
            for key in ("comments", "items", "data", "rows"):
                if isinstance(obj.get(key), list):
                    return [x for x in obj[key] if isinstance(x, dict)]
    raise ValueError("Không đọc được danh sách JSON bình luận. Cần mảng JSON [...] hoặc khối ```json ... ```.")


def import_comments(items: list[dict], source: str = "tiktok_studio", note: str = "") -> dict:
    """Nhập danh sách bình luận vào SQLite (chống trùng lặp, cập nhật lượt thích & trạng thái trả lời)."""
    init()
    now = db.now_iso()
    inserted = 0
    updated = 0
    occ_counter: Counter[tuple[str, str, str]] = Counter()

    with db.tx() as c:
        for idx, it in enumerate(items, 1):
            author = str(it.get("author_display") or it.get("author") or it.get("username") or "").strip()
            is_creator = 1 if (it.get("is_creator") or author.lower().lstrip("@") == "tiemtragiaima") else 0
            text = str(it.get("text") if it.get("text") is not None else (it.get("comment") or "")).strip()
            time_text = str(it.get("time_text") or it.get("time") or "").strip()
            likes = int(it.get("likes") or 0)
            reply_count = int(it.get("reply_count") or 0)
            replied = 1 if it.get("replied_by_creator") else 0
            video_id = str(it.get("video_id") or "").strip()
            video_caption = str(it.get("video_caption") or it.get("video") or "").strip()
            sort_order = int(it.get("idx") or idx)

            sig = (author.lower(), _norm_caption(video_caption)[:120], re.sub(r"\s+", " ", text).lower())
            occ_counter[sig] += 1
            dkey = _dedup_key(author, video_caption, text, occ_counter[sig])

            binfo = extract_birth_info(text) if not is_creator else {"summary": "", "can_chi_tags": "", "payload": {}}
            cat = classify_comment(text, bool(is_creator), binfo)
            bjson = json.dumps(binfo["payload"], ensure_ascii=False)

            exists = c.execute("SELECT id, manual_replied FROM studio_comments WHERE dedup_key=?", (dkey,)).fetchone()
            if exists:
                c.execute(
                    """UPDATE studio_comments SET
                        author_display=?, is_creator=?, time_text=?, likes=?, reply_count=?,
                        replied_by_creator=?, video_id=CASE WHEN ?!='' THEN ? ELSE video_id END,
                        video_caption=CASE WHEN ?!='' THEN ? ELSE video_caption END,
                        category=?, birth_summary=?, birth_json=?, can_chi_tags=?, last_seen=?, sort_order=?
                       WHERE id=?""",
                    (author, is_creator, time_text, likes, reply_count, replied,
                     video_id, video_id, video_caption, video_caption,
                     cat, binfo["summary"], bjson, binfo["can_chi_tags"], now, sort_order, exists["id"]),
                )
                updated += 1
            else:
                c.execute(
                    """INSERT INTO studio_comments (
                        dedup_key, author_display, is_creator, text, time_text, likes, reply_count,
                        replied_by_creator, manual_replied, video_id, video_caption, category,
                        birth_summary, birth_json, can_chi_tags, first_seen, last_seen, sort_order
                    ) VALUES (?,?,?,?,?,?,?,?,0,?,?,?,?,?,?,?,?,?)""",
                    (dkey, author, is_creator, text, time_text, likes, reply_count, replied,
                     video_id, video_caption, cat, binfo["summary"], bjson, binfo["can_chi_tags"],
                     now, now, sort_order),
                )
                inserted += 1

        c.execute(
            "INSERT INTO studio_comment_imports (imported_at, source, total_rows, inserted_rows, updated_rows, note)"
            " VALUES (?,?,?,?,?,?)",
            (now, source, len(items), inserted, updated, (note or "")[:300]),
        )
    return {"total": len(items), "inserted": inserted, "updated": updated}


def set_manual_replied(cid: int, val: bool) -> None:
    init()
    with db.tx() as c:
        c.execute("UPDATE studio_comments SET manual_replied=? WHERE id=?", (1 if val else 0, cid))


def clear_all() -> int:
    init()
    with db.tx() as c:
        n = c.execute("SELECT COUNT(*) FROM studio_comments").fetchone()[0]
        c.execute("DELETE FROM studio_comments")
        c.execute("DELETE FROM studio_comment_imports")
    return int(n or 0)


def _match_package_and_video(caption: str, video_id: str, videos: list[dict], pkgs: list[dict]) -> dict:
    """Khớp bình luận với bảng videos và packages trong TikTok Manager."""
    v_match = None
    p_match = None
    if video_id:
        v_match = next((v for v in videos if v.get("id") == video_id), None)
        p_match = next((p for p in pkgs if p.get("video_id") == video_id), None)

    nc = _norm_caption(caption)
    prefix = nc[:48]
    if not p_match and prefix:
        for p in pkgs:
            pc = _norm_caption(p.get("caption") or "")
            if pc and (prefix in pc or pc[:48] in nc):
                p_match = p
                break
    if not v_match and prefix:
        for v in videos:
            vc = _norm_caption((v.get("description") or "") + " " + (v.get("title") or ""))
            if vc and (prefix in vc or vc[:48] in nc):
                v_match = v
                break
    if v_match and not p_match:
        p_match = next((p for p in pkgs if p.get("video_id") == v_match.get("id")), None)
    if p_match and not v_match and p_match.get("video_id"):
        v_match = next((v for v in videos if v.get("id") == p_match.get("video_id")), None)

    short = re.sub(r"\s+", " ", (caption or "").strip())
    short = (short[:82] + "…") if len(short) > 85 else (short or "(Không rõ tiêu đề video)")
    return {
        "video_id": (v_match or {}).get("id") or video_id or "",
        "video_views": (v_match or {}).get("view_count"),
        "goi": str((p_match or {}).get("goi") or ""),
        "pkg_id": (p_match or {}).get("id"),
        "loai": (p_match or {}).get("loai"),
        "short_caption": short,
    }


def _enrich_rows() -> tuple[list[dict], list[dict]]:
    """Đọc toàn bộ bình luận từ SQLite, gắn thêm thông tin lá số & khớp video/gói."""
    from . import packages

    init()
    raw_rows = db.query("SELECT * FROM studio_comments ORDER BY sort_order ASC, id ASC")
    acc = db.get_active_account()
    videos = db.query("SELECT id, title, description, view_count, like_count, comment_count FROM videos WHERE open_id=?",
                      (acc["open_id"],)) if acc else []
    try:
        pkgs = packages.all_packages()
    except Exception:  # noqa: BLE001
        pkgs = []

    match_cache: dict[tuple[str, str], dict] = {}
    out = []
    for r in raw_rows:
        key = (r.get("video_id") or "", r.get("video_caption") or "")
        if key not in match_cache:
            match_cache[key] = _match_package_and_video(r.get("video_caption") or "", r.get("video_id") or "", videos, pkgs)
        m = match_cache[key]
        try:
            birth = json.loads(r.get("birth_json") or "{}") if r.get("birth_json") else {}
        except ValueError:
            birth = {}
        eff_replied = bool(r.get("replied_by_creator") or r.get("manual_replied"))
        vkey = hashlib.md5(_norm_caption(r.get("video_caption") or r.get("video_id") or "").encode("utf-8")).hexdigest()[:10]
        out.append({
            **r,
            **m,
            "vkey": vkey,
            "author_masked": "Tiệm Trà Giải Mã" if r.get("is_creator") else mask_handle(r.get("author_display") or ""),
            "birth": birth,
            "is_replied": eff_replied,
            "cat_label": CATEGORIES.get(r.get("category") or "emoji_khac", "Khác"),
            "text_display": r.get("text") or "(Sticker / không có chữ trên web)",
        })
    imports = db.query("SELECT * FROM studio_comment_imports ORDER BY id DESC LIMIT 10")
    return out, imports


def dashboard_data(role: str = "viewer", status: str = "all", cat: str = "all",
                   vkey: str = "", q: str = "") -> dict:
    """Tổng hợp toàn bộ bảng thống kê + danh sách đã lọc cho trang /binh-luan."""
    rows, imports = _enrich_rows()
    viewers = [r for r in rows if not r["is_creator"]]
    creators = [r for r in rows if r["is_creator"]]

    v_replied = sum(1 for r in viewers if r["is_replied"])
    v_unreplied = len(viewers) - v_replied
    birth_rows = [r for r in viewers if r["category"] == "xin_la_so"]
    birth_full = sum(1 for r in birth_rows if (r.get("birth") or {}).get("has_full_date"))
    birth_unreplied = sum(1 for r in birth_rows if not r["is_replied"])
    total_likes = sum(int(r.get("likes") or 0) for r in rows)
    viewer_likes = sum(int(r.get("likes") or 0) for r in viewers)

    # 1. Thống kê theo nhóm phân loại
    cat_stats = []
    for k in CAT_ORDER:
        grp = [r for r in rows if r["category"] == k]
        n = len(grp)
        rep = sum(1 for r in grp if r["is_replied"])
        denom = len(viewers) if k != "kenh" else len(rows)
        cat_stats.append({
            "key": k,
            "label": CATEGORIES[k],
            "count": n,
            "pct": round(n * 100 / denom, 1) if denom else 0.0,
            "replied": rep,
            "unreplied": n - rep if k != "kenh" else 0,
            "likes": sum(int(r.get("likes") or 0) for r in grp),
        })

    # 2. Thống kê theo Can Chi / Tuổi được khách nhắc tới
    cc_map: dict[str, dict] = {}
    for r in viewers:
        tags_list = [t.strip() for t in (r.get("can_chi_tags") or "").split(",") if t.strip()]
        # Nếu có năm sinh mà chưa có trong can_chi_tags, thêm Can Chi của năm sinh đó
        b = r.get("birth") or {}
        if b.get("yy"):
            cc_y = battu.name(battu.ganzhi(int(b["yy"]) - 4))
            if cc_y not in tags_list:
                tags_list.append(cc_y)
        for cc in tags_list:
            e = cc_map.setdefault(cc, {"can_chi": cc, "count": 0, "full_date": 0, "unreplied": 0})
            e["count"] += 1
            if b.get("has_full_date"):
                e["full_date"] += 1
            if not r["is_replied"]:
                e["unreplied"] += 1
    canchi_stats = sorted(cc_map.values(), key=lambda x: (-x["count"], -x["full_date"], x["can_chi"]))

    # 3. Thống kê theo từng Video / Gói SX
    vmap: dict[str, dict] = {}
    for r in rows:
        vk = r["vkey"]
        e = vmap.setdefault(vk, {
            "vkey": vk,
            "video_id": r["video_id"],
            "goi": r["goi"],
            "pkg_id": r["pkg_id"],
            "loai": r["loai"],
            "short_caption": r["short_caption"],
            "video_views": r["video_views"],
            "total": 0,
            "viewer": 0,
            "creator": 0,
            "xin_la_so": 0,
            "replied": 0,
            "unreplied": 0,
            "likes": 0,
            "latest_time": r["time_text"],
            "min_order": r["sort_order"],
        })
        e["total"] += 1
        e["likes"] += int(r.get("likes") or 0)
        if r["is_creator"]:
            e["creator"] += 1
        else:
            e["viewer"] += 1
            if r["category"] == "xin_la_so":
                e["xin_la_so"] += 1
            if r["is_replied"]:
                e["replied"] += 1
            else:
                e["unreplied"] += 1
        if r["sort_order"] < e["min_order"]:
            e["min_order"] = r["sort_order"]
            e["latest_time"] = r["time_text"]

    video_stats = sorted(vmap.values(), key=lambda x: (-x["viewer"], -x["xin_la_so"], x["min_order"]))

    # 4. Lọc danh sách chi tiết
    filtered = list(rows)
    if role == "viewer":
        filtered = [r for r in filtered if not r["is_creator"]]
    elif role == "creator":
        filtered = [r for r in filtered if r["is_creator"]]
    if status == "unreplied":
        filtered = [r for r in filtered if not r["is_creator"] and not r["is_replied"]]
    elif status == "replied":
        filtered = [r for r in filtered if not r["is_creator"] and r["is_replied"]]
    if cat and cat != "all":
        filtered = [r for r in filtered if r["category"] == cat]
    if vkey:
        filtered = [r for r in filtered if r["vkey"] == vkey]
    if q:
        ql = q.strip().lower()
        filtered = [
            r for r in filtered
            if ql in (r.get("text") or "").lower()
            or ql in (r.get("video_caption") or "").lower()
            or ql in (r.get("birth_summary") or "").lower()
            or ql in (r.get("can_chi_tags") or "").lower()
            or ql in (r.get("goi") or "").lower()
        ]

    # 5. Dữ liệu biểu đồ Chart.js
    viewer_cats = [c for c in cat_stats if c["key"] != "kenh"]
    top_vids = [v for v in video_stats if v["viewer"] > 0][:8]
    charts = {
        "cat_labels": [c["label"] for c in viewer_cats],
        "cat_values": [c["count"] for c in viewer_cats],
        "vid_labels": [(f"Gói {v['goi']} · " if v["goi"] else "") + v["short_caption"][:28] for v in top_vids],
        "vid_replied": [v["replied"] for v in top_vids],
        "vid_unreplied": [v["unreplied"] for v in top_vids],
    }

    kpi = {
        "total": len(rows),
        "viewer_total": len(viewers),
        "creator_total": len(creators),
        "replied": v_replied,
        "unreplied": v_unreplied,
        "reply_rate_pct": round(v_replied * 100 / len(viewers), 1) if viewers else 0.0,
        "xin_la_so": len(birth_rows),
        "xin_la_so_full": birth_full,
        "xin_la_so_unreplied": birth_unreplied,
        "video_count": len(video_stats),
        "video_with_viewer": sum(1 for v in video_stats if v["viewer"] > 0),
        "total_likes": total_likes,
        "viewer_likes": viewer_likes,
        "canchi_total": sum(x["count"] for x in canchi_stats),
        "last_import": imports[0]["imported_at"] if imports else "",
    }
    return {
        "kpi": kpi,
        "cat_stats": cat_stats,
        "canchi_stats": canchi_stats,
        "video_stats": video_stats,
        "rows": filtered,
        "imports": imports,
        "charts": charts,
        "categories": CATEGORIES,
    }


def to_markdown(data: dict | None = None) -> str:
    """Xuất báo cáo thống kê bình luận ẨN DANH 100% (không nick, không tên riêng) để lưu /danh-gia hoặc gửi Gemini."""
    d = data or dashboard_data(role="all", status="all", cat="all")
    k = d["kpi"]
    now_vn = datetime.now(VN).strftime("%d/%m/%Y %H:%M")
    lines = [
        f"# Thống kê bình luận TikTok Studio ({now_vn})",
        "",
        "> **Quyền riêng tư:** Báo cáo đã ẩn danh 100% — không chứa tên tài khoản/nick người bình luận và đã ẩn tên riêng trong nội dung.",
        "",
        "## 1. Tổng quan [Dữ kiện]",
        f"- **Tổng bình luận gốc thu được:** {k['total']} (Khách: **{k['viewer_total']}** · Kênh `@tiemtragiaima`: **{k['creator_total']}**)",
        f"- **Trạng thái trả lời (bình luận khách):** Đã trả lời **{k['replied']}** ({k['reply_rate_pct']}%) · Chưa trả lời **{k['unreplied']}**",
        f"- **Nhóm xin xem lá số / để lại ngày-năm sinh:** **{k['xin_la_so']}** bình luận (đủ ngày/tháng/năm: **{k['xin_la_so_full']}** · chưa trả lời: **{k['xin_la_so_unreplied']}**)",
        f"- **Độ phủ video:** {k['video_count']} video có bình luận ({k['video_with_viewer']} video có bình luận khách) · Tổng lượt thích bình luận: **{k['total_likes']}**",
        "",
        "## 2. Phân bổ theo nhóm bình luận [Dữ kiện]",
        "| Nhóm | Số lượng | Tỷ lệ | Đã trả lời | Chưa trả lời | Tổng thích |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for c in d["cat_stats"]:
        lines.append(f"| {c['label']} | {c['count']} | {c['pct']}% | {c['replied']} | {c['unreplied']} | {c['likes']} |")

    if d["canchi_stats"]:
        lines += [
            "",
            "## 3. Tuổi / Can Chi được khách nhắc nhiều nhất [Dữ kiện]",
            "| Can Chi | Số bình luận khách | Có đủ ngày sinh | Chưa trả lời |",
            "|---|---:|---:|---:|",
        ]
        for cc in d["canchi_stats"][:15]:
            lines.append(f"| {cc['can_chi']} | {cc['count']} | {cc['full_date']} | {cc['unreplied']} |")

    lines += [
        "",
        "## 4. Thống kê theo từng Video / Gói SX [Dữ kiện]",
        "| Gói | Video (caption rút gọn) | BL khách | BL kênh | Xin lá số | Đã TL | Chưa TL | Thích BL | Gần nhất |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for v in d["video_stats"]:
        goi = f"Gói {v['goi']}" if v["goi"] else "—"
        cap = comment_reply.anonymize(v["short_caption"]).replace("|", "/")
        lines.append(f"| {goi} | {cap} | {v['viewer']} | {v['creator']} | {v['xin_la_so']} | {v['replied']} | {v['unreplied']} | {v['likes']} | {v['latest_time']} |")

    ask_rows = [r for r in d["rows"] if not r["is_creator"] and r["category"] == "xin_la_so"]
    if ask_rows:
        lines += [
            "",
            "## 5. Danh sách bình luận xin xem lá số / có ngày-năm sinh (đã ẩn danh) [Dữ kiện]",
            "| # | Thời gian | Trạng thái | Nhận diện | Tứ trụ (tool tính) | Nội dung (ẩn danh) | Video |",
            "|---:|---|---|---|---|---|---|",
        ]
        for i, r in enumerate(ask_rows, 1):
            st = "Đã TL" if r["is_replied"] else "**Chưa TL**"
            tt = (r.get("birth") or {}).get("tu_tru") or "—"
            anon_txt = comment_reply.anonymize(r.get("text") or "").replace("\n", " ").replace("|", "/")[:120]
            vid = comment_reply.anonymize(f"Gói {r['goi']}" if r["goi"] else r["short_caption"][:35]).replace("|", "/")
            lines.append(f"| {i} | {r['time_text']} | {st} | {r['birth_summary'] or '—'} | {tt} | {anon_txt} | {vid} |")

    return "\n".join(lines) + "\n"
