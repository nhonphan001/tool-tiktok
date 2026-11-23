"""Đọc thư của Claude và Gemini trong hộp thư → ghi nhận đánh giá + cập nhật cấu hình tool.

1. Mỗi 10 phút (cùng lượt dò thư): đọc thư MỚI hoặc VỪA SỬA trong GUI_GEMINI và GUI_CLAUDE,
   trừ phiếu gói (SANXUAT-/BAOCAO-, đã có luồng riêng), Doc hộp thư đi và Doc tóm tắt của tool.
2. Ghi nhận: người gửi (tu:), mã thư, loại (đánh giá / chốt / xác nhận / phản hồi / khác), tiêu đề, đoạn trích.
3. Cập nhật: thư có khối
       cap_nhat_tool:
         posting_slots: "11:00,12:00,19:00"
         kpi_target_1: 1650
   → tool kiểm tra từng khoá theo DANH SÁCH TRẮNG + kiểm tra giá trị.
   - Khoá "an toàn" (giờ đăng, KPI) được TỰ ÁP DỤNG khi bật Cài đặt → "Tự áp dụng cập nhật an toàn".
   - Khoá văn bản dài (quy tắc nội dung, bối cảnh kênh, hồ sơ giọng) LUÔN chờ anh Nhơn bấm Áp dụng.
   - Khoá ngoài danh sách (API key, ID thư mục, ngân sách, model…) bị TỪ CHỐI và ghi lý do.
   Mọi thay đổi ghi nhật ký (giá trị cũ → mới, thư nguồn) và hoàn tác được.
"""
import json
import logging
import re
from datetime import date

from . import db
from .config import EDITABLE_KEYS, apply_overrides, settings

log = logging.getLogger(__name__)

SKIP_PREFIX = ("SANXUAT-", "BAOCAO-", "TOM_TAT_TU_DONG", "HOP_THU_TOOL")
KINDS = [("xac_nhan", r"XACNHAN|xac_nhan"), ("danh_gia", r"^DANHGIA|ĐÁNH GIÁ|danh_gia"), ("chot", r"^CHOT|^DONGTHUAN"),
         ("phan_hoi", r"^PHANHOI|^TRALOI|__TRALOI"), ("cap_nhat", r"^CAPNHAT"), ("bao_cao", r"^BAOCAO|^TUANTHU")]
KIND_LABELS = {"danh_gia": "Đánh giá", "chot": "Chốt", "xac_nhan": "Xác nhận", "phan_hoi": "Phản hồi",
               "cap_nhat": "Cập nhật", "bao_cao": "Báo cáo", "khac": "Khác"}
STATUS = {"none": "Chỉ ghi nhận", "pending": "Chờ duyệt", "applied": "Đã áp dụng", "partial": "Áp dụng một phần",
          "rejected": "Đã bỏ qua"}


def _slots(v: str) -> str:
    parts = [p.strip() for p in str(v).split(",") if p.strip()]
    if not parts or len(parts) > 6:
        raise ValueError("cần 1–6 khung giờ")
    out = []
    for p in parts:
        m = re.fullmatch(r"(\d{1,2})[:h](\d{2})", p)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ValueError(f"giờ không hợp lệ: {p}")
        out.append(f"{int(m.group(1)):02d}:{m.group(2)}")
    return ",".join(out)


def _int_range(lo, hi):
    def f(v):
        n = int(float(str(v).replace(".", "").replace(",", ""))) if re.fullmatch(r"[\d.,]+", str(v)) else int(v)
        if not lo <= n <= hi:
            raise ValueError(f"ngoài khoảng {lo}–{hi}")
        return str(n)
    return f


def _float_range(lo, hi):
    def f(v):
        n = float(str(v).replace(",", ".").rstrip("%"))
        if not lo <= n <= hi:
            raise ValueError(f"ngoài khoảng {lo}–{hi}")
        return str(n)
    return f


def _date(v):
    s = str(v).strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    d = date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else date.fromisoformat(s)
    return d.isoformat()


def _text(maxlen):
    def f(v):
        s = str(v).strip()
        if len(s) < 20 or len(s) > maxlen:
            raise ValueError(f"độ dài phải 20–{maxlen} ký tự")
        return s
    return f


# khoá → (nhãn, hàm kiểm tra, tự áp dụng được?)
WHITELIST = {
    "posting_slots": ("Khung giờ đăng", _slots, True),
    "kpi_target_1": ("KPI follower mốc 1", _int_range(100, 10_000_000), True),
    "kpi_deadline_1": ("Hạn KPI mốc 1", _date, True),
    "kpi_target_2": ("KPI follower mốc 2", _int_range(100, 10_000_000), True),
    "kpi_deadline_2": ("Hạn KPI mốc 2", _date, True),
    "kpi_like_view_min": ("Mốc tim/view tối thiểu (%)", _float_range(0.5, 30), True),
    "content_rules": ("Quy tắc nội dung bắt buộc", _text(20000), False),
    "channel_context": ("Bối cảnh kênh", _text(20000), False),
    "tts_style": ("Hồ sơ giọng Cô Kim", _text(6000), False),
}


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS mail_notes (
            file_id TEXT PRIMARY KEY, name TEXT, folder TEXT, sender TEXT, modified TEXT, kind TEXT, title TEXT,
            excerpt TEXT, updates_json TEXT DEFAULT '[]', status TEXT DEFAULT 'none', read_at TEXT)""")
        cols = {r[1] for r in c.execute("PRAGMA table_info(mail_notes)").fetchall()}
        if "body" not in cols:
            c.execute("ALTER TABLE mail_notes ADD COLUMN body TEXT DEFAULT ''")
        c.execute("""CREATE TABLE IF NOT EXISTS setting_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, key TEXT, old_value TEXT, new_value TEXT,
            source TEXT, mode TEXT, reverted_at TEXT)""")


# ---------------------------------------------------------------- tách thư
def _clean(text: str) -> str:
    from .mailbox import _unescape

    t = _unescape(text or "")
    return t.replace("**", "")


def sender_of(text: str, folder_is_claude_inbox: bool) -> str:
    t = _clean(text)
    m = re.search(r"^\W*(?:tu|từ)\W*[:|]\s*\|?\s*([^\n|]+)", t, re.M | re.I)
    who = (m.group(1) if m else "").lower()
    if "claude" in who and "gemini" not in who.split("claude")[0]:
        return "Claude"
    if "gemini" in who:
        return "Gemini"
    if "tool" in who or "tiktok manager" in who:
        return "Tool"
    return "Gemini" if folder_is_claude_inbox else "Claude"  # GUI_CLAUDE chứa thư Gemini gửi Claude và ngược lại


def kind_of(name: str, text: str) -> str:
    for k, rx in KINDS:
        if re.search(rx, name, re.I):
            return k
    m = re.search(r"^\W*loai\W*[:|]\s*([^\n|]+)", _clean(text), re.M | re.I)
    if m:
        for k, rx in KINDS:
            if re.search(rx, m.group(1), re.I):
                return k
    return "khac"


def title_of(text: str, name: str) -> str:
    m = re.search(r"^#{1,3}\s*(.+)$", _clean(text), re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip()[:160] if m else name


def excerpt_of(text: str) -> str:
    t = _clean(text)
    t = re.sub(r"^---.*?^---\s*", "", t, flags=re.S | re.M)
    t = re.sub(r"^\|.*$", "", t, flags=re.M)
    t = re.sub(r"\n{2,}", "\n", t).strip()
    return t[:700]


def parse_updates(text: str) -> list[dict]:
    """Khối cap_nhat_tool: key: value (giá trị 1 dòng; văn bản nhiều dòng dùng key: | rồi các dòng thụt vào)."""
    t = _clean(text)
    m = re.search(r"^\s*[-*]?\s*`?cap_nhat_tool`?\s*:\s*$", t, re.M)
    if not m:
        return []
    lines = t[m.end():].splitlines()
    out, cur = [], None
    for ln in lines:
        if not ln.strip():
            if cur and cur.get("multi"):
                cur["value"] += "\n"
            continue
        if ln.strip().startswith("```"):
            if out or cur:
                break
            continue
        mm = re.match(r"^\s{1,8}[-*]?\s*([a-z_0-9]+)\s*:\s*(.*)$", ln)
        if mm and (not cur or not cur.get("multi") or len(ln) - len(ln.lstrip()) <= cur["indent"]):
            if cur:
                out.append(cur)
            val = mm.group(2).strip()
            cur = {"key": mm.group(1), "value": "" if val in ("|", ">") else val.strip('"').strip("'"),
                   "multi": val in ("|", ">"), "indent": len(ln) - len(ln.lstrip())}
            continue
        if cur and cur.get("multi") and len(ln) - len(ln.lstrip()) > cur["indent"]:
            cur["value"] += ln.strip() + "\n"
            continue
        break
    if cur:
        out.append(cur)
    res = []
    for u in out:
        u["value"] = u["value"].strip()
        u.pop("multi", None)
        u.pop("indent", None)
        res.append(validate(u["key"], u["value"]))
    return res


def validate(key: str, value: str) -> dict:
    if key not in WHITELIST:
        why = "khoá không được phép cập nhật qua thư" + (" (chỉ sửa trong Cài đặt)" if key in EDITABLE_KEYS else "")
        return {"key": key, "value": value[:200], "ok": False, "why": why, "auto": False, "label": key}
    label, check, auto = WHITELIST[key]
    try:
        norm = check(value)
    except (ValueError, TypeError) as e:
        return {"key": key, "value": value[:200], "ok": False, "why": f"giá trị không hợp lệ: {e}", "auto": False,
                "label": label}
    cur = str(getattr(settings, key, "") or "")
    return {"key": key, "value": norm, "ok": True, "why": "", "auto": auto, "label": label,
            "same": cur.strip() == norm.strip(), "status": "pending"}


# ---------------------------------------------------------------- áp dụng / hoàn tác
def _set(key: str, value: str, source: str, mode: str) -> None:
    old = str(getattr(settings, key, "") or "")
    db.save_setting(key, value)
    apply_overrides(db.load_settings())
    with db.tx() as c:
        c.execute("INSERT INTO setting_changes(created_at, key, old_value, new_value, source, mode) VALUES(?,?,?,?,?,?)",
                  (db.now_iso(), key, old, value, source, mode))


def _save_updates(file_id: str, ups: list[dict]) -> str:
    valid = [u for u in ups if u["ok"]]
    done = [u for u in valid if u.get("status") in ("applied", "same")]
    rej = [u for u in valid if u.get("status") == "rejected"]
    if not valid:
        status = "none" if not ups else "rejected"
    elif len(done) == len(valid):
        status = "applied"
    elif len(done) + len(rej) == len(valid):
        status = "partial" if done else "rejected"
    else:
        status = "pending" if not done else "partial"
    with db.tx() as c:
        c.execute("UPDATE mail_notes SET updates_json=?, status=? WHERE file_id=?",
                  (json.dumps(ups, ensure_ascii=False), status, file_id))
    return status


def decide(file_id: str, key: str, action: str) -> str:
    """action: apply | reject. Trả về thông báo."""
    n = get(file_id)
    if not n:
        raise ValueError("Không có thư")
    ups = n["updates"]
    for u in ups:
        if u["key"] == key and u["ok"] and u.get("status") == "pending":
            if action == "apply":
                fresh = validate(key, u["value"])  # kiểm tra lại trước khi ghi
                if not fresh["ok"]:
                    raise ValueError(fresh["why"])
                _set(key, fresh["value"], n["name"], "duyet_tay")
                u["status"] = "applied"
            else:
                u["status"] = "rejected"
            _save_updates(file_id, ups)
            return f"{u['label']}: {'đã áp dụng' if action == 'apply' else 'đã bỏ qua'}"
    raise ValueError("Mục này không còn chờ duyệt")


def revert(change_id: int) -> str:
    ch = db.query_one("SELECT * FROM setting_changes WHERE id=?", (change_id,))
    if not ch or ch.get("reverted_at"):
        raise ValueError("Không hoàn tác được")
    db.save_setting(ch["key"], ch["old_value"] or "")
    apply_overrides(db.load_settings())
    with db.tx() as c:
        c.execute("UPDATE setting_changes SET reverted_at=? WHERE id=?", (db.now_iso(), change_id))
        c.execute("INSERT INTO setting_changes(created_at, key, old_value, new_value, source, mode) VALUES(?,?,?,?,?,?)",
                  (db.now_iso(), ch["key"], ch["new_value"], ch["old_value"], f"hoàn tác #{change_id}", "hoan_tac"))
    return f"Đã hoàn tác {WHITELIST.get(ch['key'], (ch['key'],))[0]}"


_BACKFILLED: list[str] = []


# ---------------------------------------------------------------- đọc hộp thư
def ingest(file: dict, text: str, folder: str, first_run: bool = False) -> dict | None:
    """Ghi nhận 1 thư (đã đọc nội dung). Trả về bản ghi nếu là thư mới/vừa sửa.
    first_run: lần đọc đầu tiên (nạp thư cũ) → không tự áp dụng, không bắn thông báo."""
    init()
    old = db.query_one("SELECT modified, status, body FROM mail_notes WHERE file_id=?", (file["id"],))
    if old and (old["modified"] or "") >= (file.get("modifiedTime") or ""):
        if not old.get("body"):  # thư đã đọc trước bản cập nhật: chỉ bổ sung nội dung, không xử lý lại cap_nhat_tool
            with db.tx() as c:
                c.execute("UPDATE mail_notes SET body=? WHERE file_id=?", (_clean(text)[:20000], file["id"]))
            _BACKFILLED.append(file["id"])
        return None
    claude_inbox = folder == (settings.mailbox_folder_ids or "").split(",")[-1].strip()
    ups = parse_updates(text)
    for u in ups:
        if not u["ok"]:
            continue
        if u.get("same"):
            u["status"] = "same"
        elif u["auto"] and settings.auto_apply_updates and not first_run:
            _set(u["key"], u["value"], file["name"], "tu_dong")
            u["status"] = "applied"
    sender = sender_of(text, claude_inbox)
    with db.tx() as c:
        c.execute("INSERT INTO mail_notes(file_id, name, folder, sender, modified, kind, title, excerpt, read_at, body)"
                  " VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(file_id) DO UPDATE SET name=excluded.name,"
                  " modified=excluded.modified, kind=excluded.kind, title=excluded.title, excerpt=excluded.excerpt,"
                  " sender=excluded.sender, read_at=excluded.read_at, body=excluded.body",
                  (file["id"], file["name"], folder, sender, file.get("modifiedTime") or "", kind_of(file["name"], text),
                   title_of(text, file["name"]), excerpt_of(text), db.now_iso(), _clean(text)[:20000]))
    status = _save_updates(file["id"], ups)
    n = get(file["id"])
    applied = [u for u in ups if u.get("status") == "applied"]
    pending = [u for u in ups if u.get("status") == "pending"]
    if not first_run and (old is None or applied or pending):
        msg = f"Thư mới từ {sender}: {file['name']}"
        if applied:
            msg += " · đã tự áp dụng " + ", ".join(u["label"] for u in applied)
        if pending:
            msg += " · " + str(len(pending)) + " cập nhật chờ duyệt"
        with db.tx() as c:
            c.execute("INSERT INTO jobs(kind, status, message, created_at, finished_at, notified, link)"
                      " VALUES('mail_note','done',?,?,?,0,?)", (msg, db.now_iso(), db.now_iso(), "/hop-thu"))
    n["status"] = status
    return n


def scan() -> list[dict]:
    """Đọc thư mới/vừa sửa ở mọi thư mục hộp thư. Gọi từ lượt dò thư 10 phút."""
    from . import mailbox
    from .notebooklm import _credentials

    init()
    import httpx

    folders = mailbox.folder_ids()
    if not folders:
        return []
    token = _credentials(["https://www.googleapis.com/auth/drive.readonly"]).token
    known = {r["file_id"]: r["modified"] for r in db.query("SELECT file_id, modified FROM mail_notes")}
    no_body = {r["file_id"] for r in db.query("SELECT file_id FROM mail_notes WHERE COALESCE(body,'')=''")}
    first_run = not known
    out = []
    for folder in folders:
        r = httpx.get(mailbox.DRIVE, headers={"Authorization": f"Bearer {token}"}, timeout=30, params={
            "q": f"'{folder}' in parents and trashed=false and (mimeType='{mailbox.GDOC}' or name contains '.md')",
            "fields": "files(id,name,mimeType,modifiedTime)", "pageSize": 200, "orderBy": "modifiedTime desc",
            "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
        if r.status_code != 200:
            log.warning("mail_notes list %s: %s", folder, r.status_code)
            continue
        for f in r.json().get("files", []):
            if f["name"].upper().startswith(SKIP_PREFIX) or f["id"] == settings.mailbox_outbox_doc_id:
                continue
            if known.get(f["id"], "") >= (f.get("modifiedTime") or "") and f["id"] in known and f["id"] not in no_body:
                continue
            try:
                text = mailbox._read(token, f)
            except httpx.HTTPError:
                continue
            n = ingest(f, text, folder, first_run)
            if n:
                out.append(n)
    backfilled = bool(_BACKFILLED)
    _BACKFILLED.clear()
    if backfilled or any(n.get("sender") == "Claude" and n.get("folder") == (folders[0] if folders else "") for n in out):
        refresh_outbox()  # thư mới của Claude → chép vào Doc hộp thư đi Gemini đang đọc
    return out


# ---------------------------------------------------------------- thư Claude → Doc hộp thư đi
CLAUDE_WINDOW_HOURS = 72


def claude_letters_for_gemini(limit: int = 6) -> list[dict]:
    """Thư Claude gửi Gemini (thư mục GUI_GEMINI) trong 72 giờ qua mà Gemini CHƯA gửi thư __XACNHAN / trả lời."""
    from datetime import datetime, timedelta, timezone

    init()
    folders = [x.strip() for x in (settings.mailbox_folder_ids or "").split(",") if x.strip()]
    if not folders:
        return []
    since = (datetime.now(timezone.utc) - timedelta(hours=CLAUDE_WINDOW_HOURS)).strftime("%Y-%m-%dT%H:%M:%S")
    rows = db.query("SELECT * FROM mail_notes WHERE sender='Claude' AND folder=? AND substr(modified,1,19) >= ?"
                    " ORDER BY modified DESC", (folders[0], since))
    names = [r["name"].upper() for r in db.query("SELECT name FROM mail_notes WHERE folder!=?", (folders[0],))]
    out = []
    for r in rows:
        code = re.sub(r"__.*$", "", r["name"]).replace(".MD", "").replace(".md", "").upper()
        if any(n.startswith(code) and re.search(r"XACNHAN|TRALOI|DANHGIA", n) for n in names):
            continue  # Gemini đã xác nhận / trả lời thư này
        tail = code.split("-", 1)[-1]  # "SOSANH-2311-GOI-19" → trả lời "DANHGIA-2311-SOSANH-GOI-19…"
        if any("DANHGIA" in n and code.split("-")[0] in n and tail.split("-", 1)[-1] in n for n in names):
            continue
        out.append(r)
    return out[:limit]


def refresh_outbox() -> bool:
    """Ghi lại Doc HOP_THU_TOOL__YEUCAU (yêu cầu của tool + thư Claude đang chờ Gemini)."""
    if not settings.mailbox_outbox_doc_id:
        return False
    try:
        from .gemini_requests import outbox_text
        from .notebooklm import push_drive

        push_drive(settings.mailbox_outbox_doc_id, outbox_text())
        return True
    except Exception:  # noqa: BLE001
        log.exception("refresh outbox (Claude letters)")
        return False


def all_notes(limit: int = 100) -> list[dict]:
    init()
    rows = db.query("SELECT * FROM mail_notes ORDER BY modified DESC LIMIT ?", (limit,))
    for r in rows:
        r["updates"] = json.loads(r.get("updates_json") or "[]")
    return rows


def get(file_id: str) -> dict | None:
    init()
    r = db.query_one("SELECT * FROM mail_notes WHERE file_id=?", (file_id,))
    if r:
        r["updates"] = json.loads(r.get("updates_json") or "[]")
    return r


def changes(limit: int = 50) -> list[dict]:
    init()
    return db.query("SELECT * FROM setting_changes ORDER BY id DESC LIMIT ?", (limit,))


def pending_count() -> int:
    init()
    return sum(1 for n in all_notes(200) for u in n["updates"] if u.get("status") == "pending")
