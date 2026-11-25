"""Theo dõi thư mục 04_VIDEO_DA_DUYET_SAN_SANG_DANG: Gemini dựng xong → tool tự gắn video vào gói + đổi trạng thái + thông báo.

Quy trình từ 25/11/2026: anh Nhơn đưa 4–7 clip thô trực tiếp cho Gemini (không tải lên 02_VIDEO_THO). Gemini dựng P8b rồi
tải `Goi_<n>_<mô tả>_Final_Sub.mp4` (bản đăng, có phụ đề) và `Goi_<n>_<mô tả>_Clean_Master.mp4` (bản sạch) vào thư mục 04.
Mỗi 10 phút (cùng nhịp hộp thư) tool đọc thư mục 04:
- gói chưa có video thành phẩm (hoặc có bản mới hơn) → ghi final_video / clean_video, trạng thái "Đã dựng – chờ đăng";
- tạo thông báo (toast) + chấm đỏ ở menu Gói SX;
- chưa có gói số đó trong tool (vd phiếu chưa nhập) → thông báo mời nhập phiếu; gắn video ngay khi gói được tạo.
"""
import logging
import re

import httpx

from . import db
from .config import settings

log = logging.getLogger(__name__)
DRIVE = "https://www.googleapis.com/drive/v3/files"
GOI_RX = re.compile(r"(?:^|[^A-Za-z0-9])Goi[_\- ]?(\d{1,4})(?!\d)", re.I)


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS finals_seen (
            file_id TEXT PRIMARY KEY, name TEXT, goi TEXT, kind TEXT, modified TEXT, seen_at TEXT, attached_pid INTEGER)""")


def kind_of(name: str) -> str | None:
    n = name.lower()
    if re.search(r"clean|master|sach", n):
        return "clean"
    if re.search(r"final|sub|phu[_\- ]?de|dang", n):
        return "final"
    return None


def parse(name: str) -> tuple[str, str] | None:
    m = GOI_RX.search(name)
    k = kind_of(name)
    return (str(int(m.group(1))), k) if m and k else None


def list_finals(token: str | None = None) -> list[dict]:
    if not settings.final_video_folder_id:
        return []
    if token is None:
        from .notebooklm import _credentials

        token = _credentials(["https://www.googleapis.com/auth/drive.readonly"]).token
    out, page = [], None
    while True:
        params = {"q": f"'{settings.final_video_folder_id}' in parents and trashed=false and mimeType contains 'video/'",
                  "fields": "nextPageToken,files(id,name,modifiedTime,size)", "pageSize": 200, "orderBy": "modifiedTime",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if page:
            params["pageToken"] = page
        r = httpx.get(DRIVE, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=30)
        if r.status_code == 404:
            raise RuntimeError("Service account chưa được xem thư mục 04_VIDEO_DA_DUYET_SAN_SANG_DANG")
        r.raise_for_status()
        j = r.json()
        out += j.get("files", [])
        page = j.get("nextPageToken")
        if not page:
            return out


def _notify(msg: str, link: str) -> None:
    with db.tx() as c:
        c.execute("INSERT INTO jobs(kind, status, message, created_at, finished_at, notified, link)"
                  " VALUES('finals','done',?,?,?,0,?)", (msg, db.now_iso(), db.now_iso(), link))


def sync(files: list[dict] | None = None) -> list[str]:
    """Đọc thư mục 04, gắn video vào gói. Trả về danh sách thông báo đã tạo."""
    from . import packages

    init()
    packages.init()
    if files is None:
        files = list_finals()
    newest: dict[tuple[str, str], dict] = {}
    for f in files:
        pk = parse(f.get("name") or "")
        if not pk:
            continue
        if pk not in newest or (f.get("modifiedTime") or "") > (newest[pk].get("modifiedTime") or ""):
            newest[pk] = f
    by_goi = {}
    for p in packages.all_packages():
        g = str(p.get("goi") or "").strip()
        if g.isdigit():
            by_goi.setdefault(str(int(g)), p)  # all_packages: mới nhất trước
    msgs = []
    for (goi, kind), f in sorted(newest.items(), key=lambda x: (int(x[0][0]), x[0][1])):
        seen = db.query_one("SELECT * FROM finals_seen WHERE file_id=?", (f["id"],))
        p = by_goi.get(goi)
        col = "final_video" if kind == "final" else "clean_video"
        if p and (p.get(col) or "") != f["id"]:
            new_status = p.get("status") or "nhap"
            if new_status in ("nhap", "san_sang"):
                new_status = "cho_dang"
            with db.tx() as c:
                c.execute(f"UPDATE packages SET {col}=?, status=?, updated_at=? WHERE id=?",
                          (f["id"], new_status, db.now_iso(), p["id"]))
            if kind == "final":
                msg = f"🎬 Gemini đã dựng xong Gói {goi} ({f['name']}) — trạng thái: Đã dựng, chờ đăng."
                _notify(msg, f"/packages/{p['id']}#kit")
                msgs.append(msg)
        elif not p and not seen and kind == "final":
            msg = f"🎬 Có video thành phẩm Gói {goi} ({f['name']}) nhưng tool chưa có gói này — bấm để nhập phiếu từ hộp thư."
            _notify(msg, f"/packages/import/{goi}")
            msgs.append(msg)
        with db.tx() as c:
            c.execute("INSERT INTO finals_seen(file_id, name, goi, kind, modified, seen_at, attached_pid) VALUES(?,?,?,?,?,?,?)"
                      " ON CONFLICT(file_id) DO UPDATE SET attached_pid=excluded.attached_pid, modified=excluded.modified",
                      (f["id"], f.get("name"), goi, kind, f.get("modifiedTime") or "",
                       (seen or {}).get("seen_at") or db.now_iso(), p["id"] if p else None))
    return msgs


def for_goi(goi: str) -> list[dict]:
    init()
    return db.query("SELECT * FROM finals_seen WHERE goi=? ORDER BY modified DESC", (str(int(goi)) if str(goi).isdigit() else goi,))
