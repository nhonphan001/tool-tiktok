"""Đọc kịch bản gói sản xuất từ hộp thư Drive Claude ↔ Gemini (05_HOP_THU_CLAUDE_GEMINI).

Tìm file tên bắt đầu bằng SANXUAT- trong GUI_GEMINI và GUI_CLAUDE, tách các trường của phiếu gói
(số gói, tiêu đề, loại, SKU, 4 cảnh, chữ trên hình, caption, bình luận ghim, ID ảnh cảnh) rồi gộp theo số gói.
Chỉ ĐỌC Drive; dữ liệu chỉ được lưu khi người dùng bấm “Lưu & kiểm tra” trên trang Gói SX.
"""
import re

import httpx

from .config import settings

DRIVE = "https://www.googleapis.com/drive/v3/files"
GDOC = "application/vnd.google-apps.document"
SKU_RX = r"SP-[A-Z]+-\d+"


def _unescape(t: str) -> str:
    """Bỏ ký tự thoát của bản xuất Markdown từ Google Docs (\\_ \\* \\[ …) và **đậm**."""
    t = re.sub(r"\\+([_*\[\]()#!|.\-+`>~])", r"\1", t or "")
    t = t.replace("\u00a0", " ")
    return t


def _clean(s: str) -> str:
    s = re.sub(r"\*\*|__", "", s or "")
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)  # [chữ](link) -> chữ
    return " ".join(s.split()).strip(" \"'|")


def _section(text: str, heading: str) -> str:
    """Nội dung ngay sau một tiêu đề markdown (## / ### Heading) tới tiêu đề kế tiếp."""
    m = re.search(rf"^#{{1,4}}\s*{heading}\s*:?\s*$\n+(.*?)(?=^#{{1,4}}\s|^nhan_video:|\Z)", text, re.M | re.S | re.I)
    if not m:
        return ""
    lines = [ln for ln in m.group(1).strip().splitlines() if ln.strip() and not ln.strip().startswith("```")]
    return _clean(" ".join(lines))


def parse(text: str, name: str = "") -> dict:
    """Tách các trường phiếu gói từ 1 file (Markdown gốc hoặc Google Doc xuất Markdown)."""
    t = _unescape(text)
    # Tiêu đề Google Docs hay bị in đậm / sai cấp: "# **Caption**" -> "## Caption"
    t = re.sub(r"^(#{1,4})\s*\*{2,}\s*(.*?)\s*\*{0,}\s*$", lambda m: "## " + m.group(2).replace("**", "").strip(), t, flags=re.M)
    t = re.sub(r"^#\s+(?=\S)", "## ", t, flags=re.M)
    out: dict = {}
    m = re.search(r"GOI[-_ ]?(\d+)", name, re.I) or re.search(r"Phiếu gói\s*(\d+)", t) \
        or re.search(r"^\s*goi:\s*(\d+)", t, re.M) or re.search(r"Gói\s+(\d+)\s*[—–-]", t)
    if m:
        out["goi"] = m.group(1)
    m = re.search(r"^#+\s*(?:\d+\.\s*)?Phiếu gói\s*\d+\s*[—–-]\s*(.+)$", t, re.M) \
        or re.search(r"^#+\s*Yêu cầu sản xuất Gói\s*\d+\s*[—–-]\s*(.+)$", t, re.M)
    if m:
        out["title"] = _clean(re.sub(r"\s*\([^()]*\)\s*\**\s*$", "", m.group(1).replace("**", "")))
    m = re.search(r"^\s*loai(?:_video)?:\s*([123])\b", t, re.M)
    if m:
        out["loai"] = int(m.group(1))
    elif re.search(r"Loại\s*2|Video sản phẩm", t):
        out["loai"] = 2
    m = re.search(rf"ma_san_pham:\s*({SKU_RX})", t) or re.search(rf"SKU:\s*({SKU_RX})", t) \
        or re.search(rf"san_pham:\s*({SKU_RX})", t) or re.search(rf"\b({SKU_RX})\b", t)
    if m:
        out["sku"] = m.group(1).upper()
    m = re.search(r"ten_san_pham:\s*(.+)$", t, re.M)
    if m:
        out["product_name"] = _clean(m.group(1))
    # 4 cảnh: "1. (26 âm tiết) …" hoặc hàng bảng "| Cảnh 1 … | … | (26 âm tiết) … |"
    for m in re.finditer(r"^\s*([1-4])\.\s*\(\d+\s*âm tiết\)\s*(.+)$", t, re.M):
        out[f"scene{m.group(1)}"] = _clean(m.group(2))
    for m in re.finditer(r"Cảnh\s*([1-4])\b[^|\n]*\|(?:[^|\n]*\|)*?\s*\(\d+\s*âm tiết\)\s*([^|\n]+)", t):
        out.setdefault(f"scene{m.group(1)}", _clean(m.group(2)))
    for key, head in (("on_screen", r"Chữ trên hình"), ("caption", r"Caption(?:\s*\+\s*hashtag)?"),
                      ("pinned", r"Bình luận ghim")):
        v = _section(t, head)
        if v:
            out[key] = v
    plan = _section(t, r"Kế hoạch quảng cáo(?: 7 ngày)?")
    if plan:
        out["ads_plan"] = plan
    if "caption" not in out:
        m = re.search(r'caption_de_xuat:\s*"(.+?)"\s*$', t, re.M)
        if m:
            out["caption"] = _clean(m.group(1))
    imgs = {}
    for m in re.finditer(r"canh_([1-4])_[\d_]*s?\s*:\s*\"?\s*([A-Za-z0-9_-]{25,60})", t):
        imgs[int(m.group(1))] = m.group(2)
    if imgs:
        out["images"] = imgs
    return out


def merge(parts: list[dict]) -> dict:
    """Gộp nhiều file của cùng 1 gói; file mới hơn (đứng sau) ghi đè trường đã có."""
    out: dict = {"sources": []}
    for p in parts:
        for k, v in p.items():
            if k == "images":
                out.setdefault("images", {}).update(v)
            elif k not in ("source",) and v not in ("", None):
                out[k] = v
        if p.get("source"):
            out["sources"].append(p["source"])
    imgs = out.get("images") or {}
    notes = []
    if imgs:
        notes.append("Ảnh Gemini: " + " · ".join(f"C{i} {imgs[i]}" for i in sorted(imgs)))
    if out.get("ads_plan"):
        notes.append("QC: " + out["ads_plan"][:300])
    if notes:
        out["note"] = " | ".join(notes)
    out["fields"] = [k for k in ("title", "sku", "scene1", "scene2", "scene3", "scene4", "on_screen", "caption", "pinned")
                     if out.get(k)]
    return out


# ---------------------------------------------------------------- Drive
def folder_ids() -> list[str]:
    return [x.strip() for x in (settings.mailbox_folder_ids or "").split(",") if x.strip()]


def _list_files(token: str, folder: str) -> list[dict]:
    r = httpx.get(DRIVE, headers={"Authorization": f"Bearer {token}"}, timeout=30, params={
        "q": f"'{folder}' in parents and name contains 'SANXUAT-' and trashed=false",
        "fields": "files(id,name,mimeType,modifiedTime)", "pageSize": 100, "orderBy": "modifiedTime",
        "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"})
    if r.status_code == 404:
        raise RuntimeError(f"Service account chưa được xem thư mục {folder}: chia sẻ thư mục hộp thư với quyền Người xem")
    if r.status_code != 200:
        raise RuntimeError(f"Drive lỗi {r.status_code}: {r.text[:200]}")
    return r.json().get("files", [])


def _read(token: str, f: dict) -> str:
    h = {"Authorization": f"Bearer {token}"}
    if f["mimeType"] == GDOC:
        r = httpx.get(f"{DRIVE}/{f['id']}/export", params={"mimeType": "text/markdown"}, headers=h, timeout=30)
        if r.status_code != 200:
            r = httpx.get(f"{DRIVE}/{f['id']}/export", params={"mimeType": "text/plain"}, headers=h, timeout=30)
    else:
        r = httpx.get(f"{DRIVE}/{f['id']}", params={"alt": "media", "supportsAllDrives": "true"}, headers=h, timeout=30)
    r.raise_for_status()
    return r.content.decode("utf-8-sig", errors="replace")


def scan() -> list[dict]:
    """Liệt kê các gói tìm thấy trong hộp thư (mới nhất trước)."""
    from .notebooklm import _credentials

    folders = folder_ids()
    if not folders:
        raise RuntimeError("Chưa cấu hình ID thư mục hộp thư trong Cài đặt")
    token = _credentials(["https://www.googleapis.com/auth/drive.readonly"]).token
    files = []
    for folder in folders:
        files += _list_files(token, folder)
    files.sort(key=lambda f: f.get("modifiedTime") or "")
    groups: dict[str, list[dict]] = {}
    for f in files:
        try:
            p = parse(_read(token, f), f["name"])
        except httpx.HTTPError:
            continue
        if not p.get("goi"):
            continue
        p["source"] = {"id": f["id"], "name": f["name"], "modified": f.get("modifiedTime", "")}
        groups.setdefault(p["goi"], []).append(p)
    out = [merge(v) for v in groups.values()]
    out.sort(key=lambda g: max(s["modified"] for s in g["sources"]), reverse=True)
    return out


def get(goi: str) -> dict | None:
    for g in scan():
        if g.get("goi") == str(goi):
            return g
    return None
