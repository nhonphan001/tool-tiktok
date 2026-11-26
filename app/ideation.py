"""Bộ phận Ý tưởng (Đầu vào quy trình — /y-tuong).

Tổng hợp dữ liệu thật từ 4 nguồn trong TikTok Manager (0 token AI):
1. Bình luận xin lá số / tuổi Can Chi được hỏi nhiều từ `/binh-luan` (`studio_comments`).
2. Mô thức thắng tự nhiên từ Báo cáo đồng thuận (`consensus.merged`).
3. Lịch tiết khí & mốc thời gian Việt Nam (cuối năm, Rằm/Mùng 1, Đại Tuyết, Đông Chí…).
4. Đối chiếu `packages` để chống trùng tuổi / chủ đề với các gói đã làm gần đây.

Anh Nhơn chỉ cần xem điểm ưu tiên & bấm "✓ Duyệt → Tạo Gói SX" để điền sẵn form `/requests#moi`.
Quyền riêng tư: KHÔNG lưu nick hay tên thật người bình luận trong bảng `ideas`.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone

from . import battu, comment_reply, comment_stats, db

VN = timezone(timedelta(hours=7))

STATUS_LABELS = {
    "pending": "Chờ duyệt",
    "approved": "Đã duyệt",
    "rejected": "Đã bỏ qua",
}

SOURCE_LABELS = {
    "comment_demand": "Từ bình luận thật",
    "organic_winner": "Mô thức thắng tự nhiên",
    "seasonal": "Tiết khí / Mốc thời gian",
    "antigravity": "Đề xuất từ An",
    "manual": "Tự thêm",
}


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS ideas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            title TEXT,
            loai INTEGER DEFAULT 1,
            scenes INTEGER DEFAULT 7,
            goal TEXT DEFAULT 'comment',
            publish_slot TEXT DEFAULT '19:00',
            source TEXT DEFAULT 'manual',
            score INTEGER DEFAULT 70,
            hook_idea TEXT DEFAULT '',
            rationale TEXT DEFAULT '',
            brief TEXT DEFAULT '',
            birth_json TEXT DEFAULT '',
            dup_warning TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            approved_at TEXT DEFAULT '',
            note TEXT DEFAULT ''
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status)")


def _year_to_words(y: int) -> str:
    """Đổi năm 4 chữ số sang cách đọc đủ 4 chữ số theo Bộ quy tắc Bản 2: 1984 -> 'một chín tám tư'."""
    d = {0: "không", 1: "một", 2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy", 8: "tám", 9: "chín"}
    s = str(int(y))
    if len(s) != 4:
        return s
    parts = [d[int(ch)] for ch in s]
    if s[2:] == "90":
        return f"{parts[0]} {parts[1]} chín mươi"
    if s[2] == "0" and s[3] != "0":
        return f"{parts[0]} {parts[1]} linh {parts[3]}"
    if s[3] == "4" and s[2] not in ("0", "1"):
        parts[3] = "tư"
    return " ".join(parts)


def _recent_package_fingerprints(limit: int = 25) -> list[dict]:
    from . import packages

    try:
        pkgs = packages.all_packages()[:limit]
    except Exception:  # noqa: BLE001
        return []
    out = []
    for p in pkgs:
        blob = " ".join(
            str(p.get(k) or "") for k in ("title", "caption", "on_screen", "scene1", "scene2")
        ).lower()
        out.append({"goi": str(p.get("goi") or p.get("id") or ""), "loai": p.get("loai"), "blob": blob})
    return out


def find_duplicate_package(keywords: list[str], recent: list[dict] | None = None) -> str:
    """Kiểm tra xem danh sách từ khoá (vd ['giáp tý', '1984']) có trùng gói nào đã làm gần đây không."""
    recs = recent if recent is not None else _recent_package_fingerprints()
    kws = [k.strip().lower() for k in keywords if k and len(k.strip()) >= 3]
    if not kws:
        return ""
    for p in recs:
        if any(k in p["blob"] for k in kws):
            return f"Gói {p['goi']} đã khai thác chủ đề gần giống ({kws[0]}) — cân nhắc góc nhìn mới hoặc đổi tuổi khác."
    return ""


def save_idea(data: dict) -> int:
    init()
    now = db.now_iso()
    title = str(data.get("title") or "").strip()[:120]
    if not title:
        raise ValueError("Thiếu tiêu đề ý tưởng")
    loai = int(data.get("loai") or 1)
    if loai not in (1, 2, 3):
        loai = 1
    scenes = int(data.get("scenes") or (7 if loai == 1 else 4))
    scenes = max(4, min(scenes, 8))
    goal = str(data.get("goal") or ("comment" if loai == 1 else "follow")).strip()
    slot = str(data.get("publish_slot") or ("19:00" if loai == 1 else "11:00")).strip()[:30]
    source = str(data.get("source") or "manual").strip()
    if source not in SOURCE_LABELS:
        source = "manual"
    score = max(1, min(int(data.get("score") or 70), 100))
    birth = data.get("birth") if isinstance(data.get("birth"), dict) else {}
    birth_json = json.dumps(birth, ensure_ascii=False) if birth else str(data.get("birth_json") or "")

    with db.tx() as c:
        cur = c.execute(
            """INSERT INTO ideas (
                created_at, updated_at, title, loai, scenes, goal, publish_slot, source, score,
                hook_idea, rationale, brief, birth_json, dup_warning, status, note
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'pending',?)""",
            (
                now, now, title, loai, scenes, goal, slot, source, score,
                str(data.get("hook_idea") or "").strip()[:300],
                str(data.get("rationale") or "").strip()[:500],
                str(data.get("brief") or "").strip()[:2000],
                birth_json[:1000],
                str(data.get("dup_warning") or "").strip()[:300],
                str(data.get("note") or "").strip()[:300],
            ),
        )
        return cur.lastrowid


def list_ideas(status: str = "all", limit: int = 50) -> list[dict]:
    init()
    sql = "SELECT * FROM ideas"
    params: tuple = ()
    if status and status != "all":
        sql += " WHERE status=?"
        params = (status,)
    sql += " ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, score DESC, id DESC LIMIT ?"
    rows = db.query(sql, (*params, limit))
    for r in rows:
        r["status_label"] = STATUS_LABELS.get(r["status"], r["status"])
        r["source_label"] = SOURCE_LABELS.get(r["source"], r["source"])
        try:
            r["birth"] = json.loads(r["birth_json"]) if r.get("birth_json") else {}
        except ValueError:
            r["birth"] = {}
    return rows


def get(iid: int) -> dict | None:
    init()
    r = db.query_one("SELECT * FROM ideas WHERE id=?", (iid,))
    if not r:
        return None
    try:
        r["birth"] = json.loads(r["birth_json"]) if r.get("birth_json") else {}
    except ValueError:
        r["birth"] = {}
    return r


def set_status(iid: int, status: str, note: str = "") -> None:
    init()
    if status not in STATUS_LABELS:
        return
    now = db.now_iso()
    with db.tx() as c:
        if status == "approved":
            c.execute("UPDATE ideas SET status=?, approved_at=?, updated_at=?, note=CASE WHEN ?!='' THEN ? ELSE note END WHERE id=?",
                      (status, now, now, note, note, iid))
        else:
            c.execute("UPDATE ideas SET status=?, updated_at=?, note=CASE WHEN ?!='' THEN ? ELSE note END WHERE id=?",
                      (status, now, note, note, iid))


def delete(iid: int) -> None:
    init()
    with db.tx() as c:
        c.execute("DELETE FROM ideas WHERE id=?", (iid,))


def prefill_request(idea: dict) -> dict:
    """Chuyển 1 ý tưởng đã duyệt thành payload điền sẵn cho form `/requests#moi`."""
    b = idea.get("birth") or {}
    out = {
        "title": (idea.get("title") or "")[:60],
        "loai": int(idea.get("loai") or 1),
        "scenes": int(idea.get("scenes") or (7 if int(idea.get("loai") or 1) == 1 else 4)),
        "goal": idea.get("goal") or ("comment" if int(idea.get("loai") or 1) == 1 else "follow"),
        "publish": f"{idea.get('publish_slot') or '19:00'} sắp tới",
        "brief": idea.get("brief") or f"{idea.get('title')}\nHook gợi ý: {idea.get('hook_idea')}",
    }
    if b.get("dd") and b.get("mm") and b.get("yy"):
        out.update({
            "dd": b.get("dd"),
            "mm": b.get("mm"),
            "yy": b.get("yy"),
            "t": b.get("t") or "",
            "lich": b.get("lich") or "duong",
            "gioi": b.get("gioi") or "",
        })
    return out


def _upcoming_seasonal(today: date) -> list[dict]:
    """Các mốc tiết khí & thời điểm thực tế gần ngày hiện tại (giờ VN)."""
    year_end_left = (date(today.year, 12, 31) - today).days
    out = []
    # Tiết khí nổi bật cuối năm / đầu năm
    milestones = [
        (date(today.year, 12, 7), "Tiết Đại Tuyết (07/12)", "khí Thủy lạnh cực vượng, giữ ấm thân tâm & tiết chế lo âu cuối năm"),
        (date(today.year, 12, 21), "Tiết Đông Chí (21/12)", "đêm dài nhất năm, Nhất Dương sinh — bước ngoặt gom năng lượng đón năm mới"),
        (date(today.year, 1, 5), "Tiết Tiểu Hàn (05/01)", "lạnh sâu cuối đông, sống chậm giữ sức cho chặng giao mùa"),
        (date(today.year, 2, 4), "Tiết Lập Xuân (04/02)", "mở đầu năm Bát Tự mới, chuyển khí sang mùa Xuân"),
    ]
    for dt, name, theme in milestones:
        diff = (dt - today).days
        if 0 <= diff <= 14:
            out.append({
                "title": f"Trà sáng {name}: giữ ấm lòng trước nhịp chuyển mùa",
                "loai": 3,
                "scenes": 4,
                "goal": "follow",
                "publish_slot": "11:00",
                "source": "seasonal",
                "score": 82,
                "hook_idea": f"Chữ trên hình: {name} · Chậm lại một nhịp bên chén trà ấm",
                "rationale": f"[Dữ kiện] Còn {diff} ngày tới {name}. Nội dung gắn tiết khí hợp định vị Tiệm Trà Giải Mã.",
                "brief": (
                    f"Loại 3 (4 cảnh × 8 giây, đăng 11:00). Chủ đề {name}: {theme}. "
                    "Không gắn từ chỉ giờ giấc (không 'sáng nay/tối nay' nếu muốn evergreen hoặc giữ đúng dịp). "
                    "Đọc rõ ràng, dùng 'bình luận' (không dùng 'comment'), câu kêu gọi bấm theo dõi ở cuối cảnh 1."
                ),
            })
    if 5 <= year_end_left <= 45:
        out.append({
            "title": f"Trà ấm cuối năm: buông 3 nỗi lo để bước nhẹ sang {today.year + 1}",
            "loai": 3,
            "scenes": 4,
            "goal": "follow",
            "publish_slot": "11:00",
            "source": "organic_winner",
            "score": 84,
            "hook_idea": "Chữ trên hình: Cuối năm rồi · Đừng ôm hết việc một mình nữa",
            "rationale": "[Dữ kiện] Video Loại 3 chủ đề sống chậm cuối năm (Gói 30 & Gói 32) đạt tỷ lệ follow/view tự nhiên 2,78%–2,82%, khán giả 61%–64% Nữ.",
            "brief": (
                f"Loại 3 (4 cảnh × 8 giây, đăng 11:00, thường xanh không ghi mốc giờ). "
                f"Còn {year_end_left} ngày khép lại năm {today.year}: Cô Kim rót chén trà ấm ngoài vườn nắng, "
                "khuyên chị em buông bớt áp lực ôm đồm, tự thương mình trước khi bước sang Đinh Mùi 2027. "
                "Bám sát Bộ quy tắc Bản 2: câu kêu gọi theo dõi ở cuối cảnh 1, dùng từ 'bình luận'."
            ),
        })
    return out


def generate_batch() -> dict:
    """Bộ phận Ý tưởng tự sinh lô 5–7 ý tưởng ưu tiên từ dữ liệu thật (0 token, tự chống trùng)."""
    init()
    existing_pending = {r["title"].strip().lower() for r in list_ideas("pending", limit=100)}
    recent_pkgs = _recent_package_fingerprints()
    candidates: list[dict] = []

    # 1. Ý tưởng Loại 1 từ bình luận thật có ngày sinh chưa trả lời (ưu tiên cao nhất!)
    cdata = comment_stats.dashboard_data(role="viewer", status="unreplied", cat="xin_la_so")
    seen_years: set[int] = set()
    for r in cdata["rows"]:
        b = r.get("birth") or {}
        if not b.get("has_full_date") or not b.get("yy"):
            continue
        yy = int(b["yy"])
        if yy in seen_years:
            continue
        seen_years.add(yy)
        cc_year = battu.name(battu.ganzhi(yy - 4))
        dup = find_duplicate_package([cc_year, str(yy)], recent_pkgs)
        score = 94 - (18 if dup else 0)
        anon_msg = comment_reply.anonymize(r.get("text") or "").replace("\n", " ")[:140]
        yr_words = _year_to_words(yy)
        candidates.append({
            "title": f"Giải mã lá số thật tuổi {cc_year} {yy} cho năm Đinh Mùi 2027",
            "loai": 1,
            "scenes": 7,
            "goal": "comment",
            "publish_slot": "19:00",
            "source": "comment_demand",
            "score": score,
            "hook_idea": f"Nữ {cc_year} {yy} · Bước vào Đinh Mùi 2027 cần giữ gì?",
            "rationale": f"[Dữ kiện] Khách để lại ngày sinh thật ({r.get('birth_summary')}) đang chưa trả lời; Nhật chủ {b.get('nhat_chu')}, Dụng thần {b.get('dung_than')}.",
            "brief": (
                f"Nhóm 4 – trả lời bình luận thật (đã ẩn danh: \"{anon_msg}\") tuổi {cc_year} {yy}. "
                f"Dùng NGUYÊN VĂN Tứ trụ tool tính: {b.get('tu_tru')} (Nhật chủ {b.get('nhat_chu')}, Dụng thần {b.get('dung_than')}). "
                f"Bộ quy tắc Bản 2 BẮT BUỘC: đọc đủ 4 chữ số năm sinh '{yr_words}' (không đọc tắt 2 số cuối), "
                "dùng 'bình luận' (không dùng 'comment'), 7 cảnh × 8 giây, đăng 19:00, không lộ ngày sinh đầy đủ hay tên khách."
            ),
            "birth": {k: b.get(k) for k in ("dd", "mm", "yy", "t", "lich", "gioi")},
            "dup_warning": dup,
        })
        if len(candidates) >= 3:
            break

    # 2. Ý tưởng Loại 1 từ bảng Can Chi khách nhắc nhiều nhất (những tuổi chưa có trong candidates)
    all_cdata = comment_stats.dashboard_data(role="all")
    for cc in all_cdata.get("canchi_stats") or []:
        cc_name = cc["can_chi"]
        dup = find_duplicate_package([cc_name], recent_pkgs)
        # Bỏ qua nếu đã có trong candidates theo cùng Can Chi
        if any(cc_name.lower() in c["title"].lower() for c in candidates):
            continue
        score = 86 + min(cc["count"] * 2, 10) - (20 if dup else 0)
        candidates.append({
            "title": f"Góc nhìn Bát Tự tuổi {cc_name} trước thềm Đinh Mùi 2027",
            "loai": 1,
            "scenes": 7,
            "goal": "comment",
            "publish_slot": "19:00",
            "source": "comment_demand",
            "score": score,
            "hook_idea": f"Tuổi {cc_name} · Một điểm chuyển đáng chú ý năm 2027",
            "rationale": f"[Dữ kiện] Có {cc['count']} bình luận khách nhắc tuổi {cc_name} ({cc['unreplied']} chưa trả lời) trên /binh-luan.",
            "brief": (
                f"Loại 1 (7 cảnh × 8 giây, đăng 19:00) theo nhu cầu cao từ bình luận tuổi {cc_name}. "
                "Phân tích đặc trưng khí năm + nhắc rõ tuổi chỉ là 1/4 trụ, mời để lại đủ ngày tháng năm + giờ sinh dưới bình luận. "
                "Bộ quy tắc Bản 2: đọc đủ 4 chữ số năm sinh, dùng từ 'bình luận'."
            ),
            "dup_warning": dup,
        })
        if len(candidates) >= 5:
            break

    # 3. Ý tưởng Loại 3 theo tiết khí / mô thức thắng tự nhiên
    today_vn = datetime.now(VN).date()
    for s in _upcoming_seasonal(today_vn):
        dup = find_duplicate_package([s["title"][:25]], recent_pkgs)
        s["dup_warning"] = dup
        candidates.append(s)

    # Nếu chưa có đủ (vd DB mới trống bình luận), thêm 1 ý tưởng Loại 1 thường xanh cho nhóm nữ 35–44
    if len(candidates) < 4:
        dup = find_duplicate_package(["ất sửu", "1985"], recent_pkgs)
        candidates.append({
            "title": "Nữ Ất Sửu 1985 · Nhịp chậm lại để giữ sức năm Đinh Mùi 2027",
            "loai": 1,
            "scenes": 7,
            "goal": "comment",
            "publish_slot": "19:00",
            "source": "organic_winner",
            "score": 82 - (18 if dup else 0),
            "hook_idea": "Nữ Ất Sửu 1985 · Năm Đinh Mùi 2027 nên tiến hay giữ nhịp?",
            "rationale": "[Dữ kiện] Nhóm tuổi nữ 35–44 chiếm 49% lượt xem tự nhiên trên Gói 31 (Loại 1 tốt nhất tuần).",
            "brief": (
                "Loại 1 (7 cảnh × 8 giây, đăng 19:00) dành cho nữ tuổi Ất Sửu một chín tám lăm. "
                "Đọc đủ 4 chữ số năm sinh, dùng 'bình luận' thay cho 'comment', hook mạnh ở giây 0."
            ),
            "dup_warning": dup,
        })

    created = 0
    skipped = 0
    for c in sorted(candidates, key=lambda x: -int(x.get("score") or 0))[:7]:
        if c["title"].strip().lower() in existing_pending:
            skipped += 1
            continue
        save_idea(c)
        existing_pending.add(c["title"].strip().lower())
        created += 1
    return {"created": created, "skipped": skipped, "total_pending": len(list_ideas("pending"))}
