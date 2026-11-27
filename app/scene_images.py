"""Theo dõi thư mục 01_KICH_BAN_VA_ANH_AI: Gemini/An xuất ảnh cảnh + ảnh bìa thương hiệu → tool tự gắn vào gói.

Quy ước tên file trong thư mục 01_KICH_BAN_VA_ANH_AI:
- Ảnh cảnh: `GOI_<n>_..._CANH_<1..8>...(.jpg|.png|.webp)` (không phân biệt hoa/thường, kể cả `Goi_36_canh_1.jpg`)
- Ảnh bìa thương hiệu (Hook): `GOI_<n>_ANH_BIA...(.png|.jpg|.webp)` hoặc `GOI_<n>_COVER...`
  (ưu tiên bản gốc không mang hậu tố trùng lặp ` (1)`, ` (2)` nếu cùng tồn tại).
"""
import json
import logging
import re

import httpx

from . import db
from .config import settings

log = logging.getLogger(__name__)
DRIVE = "https://www.googleapis.com/drive/v3/files"
GOI_RX = re.compile(r"(?:^|[^A-Za-z0-9])Goi[_\- ]?(\d{1,4})(?!\d)", re.I)
CANH_RX = re.compile(r"(?:^|[^A-Za-z0-9])canh[_\- ]?([1-8])(?!\d)", re.I)
COVER_RX = re.compile(r"(?:^|[^A-Za-z0-9])(anh[_\- ]?bia|cover)(?:[^A-Za-z0-9]|$)", re.I)
DUP_SUFFIX_RX = re.compile(r"\s*\(\d+\)\s*\.[A-Za-z0-9]+$")


def parse_image(name: str) -> tuple[str, str] | None:
    """Tên file ảnh trong thư mục 01 → (số gói chuẩn, 'image1'..'image8' hoặc 'cover_image')."""
    if not name:
        return None
    mg = GOI_RX.search(name)
    if not mg:
        return None
    goi = str(int(mg.group(1)))
    if COVER_RX.search(name):
        return goi, "cover_image"
    mc = CANH_RX.search(name)
    if mc:
        return goi, f"image{mc.group(1)}"
    return None


def _rank(kind: str, f: dict) -> tuple[int, str]:
    """Xếp hạng bản tốt nhất cho cùng 1 (goi, kind): với ảnh bìa ưu tiên file sạch không có '(1)'."""
    name = f.get("name") or ""
    clean = 1 if (kind == "cover_image" and not DUP_SUFFIX_RX.search(name)) else 0
    return clean, f.get("modifiedTime") or ""


def list_images(token: str | None = None) -> list[dict]:
    if not settings.scene_images_folder_id:
        return []
    if token is None:
        from .notebooklm import _credentials

        token = _credentials(["https://www.googleapis.com/auth/drive.readonly"]).token
    out, page = [], None
    while True:
        params = {
            "q": f"'{settings.scene_images_folder_id}' in parents and trashed=false and mimeType contains 'image/'",
            "fields": "nextPageToken,files(id,name,modifiedTime,size)",
            "pageSize": 200,
            "orderBy": "modifiedTime",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if page:
            params["pageToken"] = page
        r = httpx.get(DRIVE, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=30)
        if r.status_code == 404:
            raise RuntimeError("Service account chưa được xem thư mục 01_KICH_BAN_VA_ANH_AI")
        r.raise_for_status()
        j = r.json()
        out += j.get("files", [])
        page = j.get("nextPageToken")
        if not page:
            return out


def index_by_goi(files: list[dict]) -> dict[str, dict[str, dict]]:
    """Nhóm file ảnh theo số gói → {'image1': file, ..., 'cover_image': file} (chọn bản tốt nhất)."""
    best: dict[str, dict[str, dict]] = {}
    for f in files:
        pk = parse_image(f.get("name") or "")
        if not pk:
            continue
        goi, kind = pk
        cur = best.setdefault(goi, {}).get(kind)
        if cur is None or _rank(kind, f) > _rank(kind, cur):
            best[goi][kind] = f
    return best


def for_goi(goi: str, files: list[dict] | None = None) -> dict[str, str]:
    """Trả về {'image1': file_id, ..., 'cover_image': file_id} cho 1 gói cụ thể."""
    g = str(goi or "").strip()
    if not g.isdigit():
        return {}
    key = str(int(g))
    if files is None:
        files = list_images()
    found = index_by_goi(files).get(key) or {}
    return {k: v["id"] for k, v in found.items() if v.get("id")}


def sync(files: list[dict] | None = None, only_goi: str | None = None) -> list[str]:
    """Đọc thư mục 01, tự gắn ảnh cảnh (image1..8) và ảnh bìa thương hiệu (cover_image) vào gói."""
    from . import packages

    packages.init()
    if files is None:
        files = list_images()
    idx = index_by_goi(files)
    target = str(int(only_goi)) if only_goi and str(only_goi).strip().isdigit() else None
    msgs: list[str] = []
    for p in packages.all_packages():
        g = str(p.get("goi") or "").strip()
        if not g.isdigit():
            continue
        key = str(int(g))
        if target and key != target:
            continue
        found = idx.get(key)
        if not found:
            continue
        im = json.loads(p.get("images_json") or "{}")
        changed = False
        added_scenes = 0
        for i in range(1, packages.MAX_SCENES + 1):
            f = found.get(f"image{i}")
            if f and f.get("id") and im.get(str(i)) != f["id"]:
                im[str(i)] = f["id"]
                changed = True
                added_scenes += 1
        cov = found.get("cover_image")
        new_cov = cov["id"] if (cov and cov.get("id")) else (p.get("cover_image") or "")
        cov_changed = bool(cov and cov.get("id") and (p.get("cover_image") or "") != cov["id"])
        if changed or cov_changed:
            with db.tx() as c:
                c.execute(
                    "UPDATE packages SET images_json=?, cover_image=?, updated_at=? WHERE id=?",
                    (json.dumps(im, ensure_ascii=False), new_cov, db.now_iso(), p["id"]),
                )
            parts = []
            if added_scenes:
                parts.append(f"{added_scenes} ảnh cảnh")
            if cov_changed:
                parts.append("ảnh bìa thương hiệu")
            msgs.append(f"Gói {key}: đã gắn {' + '.join(parts)} từ thư mục 01.")
    return msgs
