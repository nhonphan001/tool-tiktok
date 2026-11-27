"""Lấy ảnh cảnh / video thành phẩm của gói từ Google Drive qua service account (để xem + tải ngay trên tool).

Chỉ phục vụ các file ID đang gắn với một gói (image1..4, final_video, clean_video) — không phải proxy Drive tuỳ ý.
Có bộ nhớ đệm trên đĩa: data/media_cache/<id>.
"""
import io
import json
import os
import re
import zipfile

import httpx

from .config import settings

DRIVE = "https://www.googleapis.com/drive/v3/files/{id}"
MAX_BYTES = 200 * 1024 * 1024  # 200 MB / file


class MediaError(RuntimeError):
    pass


def cache_dir() -> str:
    base = os.path.dirname(os.path.abspath(settings.database_path)) if settings.database_path != ":memory:" else "/tmp"
    d = os.path.join(base, "media_cache")
    os.makedirs(d, exist_ok=True)
    return d


def file_id_for(p: dict, kind: str) -> str:
    m = re.fullmatch(r"clip([1-8])", kind)
    if m:
        try:
            v = (json.loads(p.get("clips_json") or "{}").get(m.group(1)) or {}).get("id") or ""
        except ValueError:
            v = ""
        return v if re.fullmatch(r"[A-Za-z0-9_-]{20,80}", v) else ""
    if re.fullmatch(r"image[1-8]", kind) or kind in ("cover_image", "final_video", "clean_video"):
        v = (p.get(kind) or "").strip()
        if re.fullmatch(r"[A-Za-z0-9_-]{20,80}", v):
            return v
    return ""


def fetch(file_id: str) -> tuple[str, dict]:
    """Trả về (đường dẫn file đã lưu đệm, {name, mimeType})."""
    d = cache_dir()
    path, meta_path = os.path.join(d, file_id), os.path.join(d, file_id + ".json")
    if os.path.exists(path) and os.path.exists(meta_path):
        with open(meta_path, encoding="utf-8") as f:
            return path, json.load(f)
    from .notebooklm import _credentials

    token = _credentials(["https://www.googleapis.com/auth/drive.readonly"]).token
    h = {"Authorization": f"Bearer {token}"}
    r = httpx.get(DRIVE.format(id=file_id), headers=h, timeout=30,
                  params={"fields": "name,mimeType,size", "supportsAllDrives": "true"})
    if r.status_code in (403, 404):
        raise MediaError("Service account chưa được xem file này: chia sẻ thư mục 01_KICH_BAN_VA_ANH_AI và "
                         "04_VIDEO_DA_DUYET_SAN_SANG_DANG (quyền Người xem) cho service account")
    if r.status_code != 200:
        raise MediaError(f"Drive lỗi {r.status_code}")
    meta = r.json()
    if int(meta.get("size") or 0) > MAX_BYTES:
        raise MediaError("File quá lớn để tải qua tool, hãy mở trên Drive")
    tmp = path + ".part"
    with httpx.stream("GET", DRIVE.format(id=file_id), headers=h, timeout=120,
                      params={"alt": "media", "supportsAllDrives": "true"}) as resp:
        if resp.status_code != 200:
            raise MediaError(f"Drive lỗi {resp.status_code} khi tải file")
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    os.replace(tmp, path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"name": meta.get("name") or file_id, "mimeType": meta.get("mimeType") or "application/octet-stream"}, f)
    return path, {"name": meta.get("name") or file_id, "mimeType": meta.get("mimeType") or "application/octet-stream"}


def images_zip(p: dict) -> tuple[bytes, list[str]]:
    buf, errors = io.BytesIO(), []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        cov = file_id_for(p, "cover_image")
        if cov:
            try:
                path, meta = fetch(cov)
                z.write(path, f"00_anh_bia_hook__{meta['name']}")
            except MediaError as e:
                errors.append(f"Ảnh bìa: {e}")
        for i in range(1, 9):
            fid = file_id_for(p, f"image{i}")
            if not fid:
                continue
            try:
                path, meta = fetch(fid)
            except MediaError as e:
                errors.append(f"Cảnh {i}: {e}")
                continue
            z.write(path, f"canh_{i}__{meta['name']}")
    return buf.getvalue(), errors
