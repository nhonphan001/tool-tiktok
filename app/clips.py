"""Duyệt clip thô (P8a) trên TikTok Manager trước khi gửi Gemini ghép (P8b).

- Tool đọc thư mục 02_VIDEO_THO_CHO_KIEM_DUYET, nhận clip theo tên `Goi_<n>_canh_<k>…` (không phân biệt hoa thường,
  chấp nhận `_v2`, `-lam-lai`…). Mỗi cảnh lấy file MỚI NHẤT.
- Trạng thái mỗi cảnh: cho_duyet → dat | lam_lai. Có file mới cho cảnh đang "lam_lai" (hoặc file khác bản đã duyệt)
  thì tự quay về "cho_duyet".
- Đủ mọi cảnh (4–8) "dat" → gửi thư GHEP-…-GOI-n__YEUCAU vào hộp thư đi (Gemini ghép, hook, phụ đề, giữ dấu AI).
Không xoá, không sửa file nào trên Drive.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from . import db, packages
from .config import settings

log = logging.getLogger(__name__)
STATUS = {"chua_co": "Chưa có clip", "cho_duyet": "Chờ duyệt", "dat": "Đạt", "lam_lai": "Làm lại"}
DRIVE = "https://www.googleapis.com/drive/v3/files"


def _rx(goi: str) -> re.Pattern:
    return re.compile(rf"GOI[\s_-]?0*{re.escape(str(goi))}(?!\d).*?CANH[\s_-]?([1-8])(?!\d)", re.I)


def load(p: dict) -> dict:
    try:
        d = json.loads(p.get("clips_json") or "{}")
    except ValueError:
        d = {}
    n = max(packages.n_scenes(p), max([int(k) for k in d if str(k).isdigit()] or [0]))
    return {str(k): d.get(str(k)) or {"status": "chua_co"} for k in range(1, n + 1)}


def save(pid: int, clips: dict) -> None:
    with db.tx() as c:
        c.execute("UPDATE packages SET clips_json=? WHERE id=?", (json.dumps(clips, ensure_ascii=False), pid))


def list_raw(token: str | None = None) -> list[dict]:
    if not settings.raw_video_folder_id:
        return []
    if token is None:
        from .notebooklm import _credentials

        token = _credentials(["https://www.googleapis.com/auth/drive.readonly"]).token
    out, page = [], None
    while True:
        params = {"q": f"'{settings.raw_video_folder_id}' in parents and trashed=false and mimeType contains 'video/'",
                  "fields": "nextPageToken,files(id,name,modifiedTime,size)", "pageSize": 200, "orderBy": "modifiedTime",
                  "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
        if page:
            params["pageToken"] = page
        r = httpx.get(DRIVE, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=30)
        if r.status_code == 404:
            raise RuntimeError("Service account chưa được xem thư mục 02_VIDEO_THO_CHO_KIEM_DUYET")
        r.raise_for_status()
        j = r.json()
        out += j.get("files", [])
        page = j.get("nextPageToken")
        if not page:
            return out


def match(p: dict, files: list[dict]) -> dict:
    """{cảnh: file mới nhất} cho gói p."""
    goi = str(p.get("goi") or "").strip()
    if not goi:
        return {}
    rx, best = _rx(goi), {}
    for f in files:
        m = rx.search(f["name"])
        if m:
            k = m.group(1)
            if k not in best or (f.get("modifiedTime") or "") > (best[k].get("modifiedTime") or ""):
                best[k] = f
    return best


def sync(p: dict, files: list[dict]) -> tuple[dict, list[str]]:
    """Cập nhật trạng thái clip của gói theo file trên Drive. Trả về (clips, các cảnh vừa có file mới)."""
    clips, found, new = load(p), match(p, files), []
    for k, f in found.items():
        cur = clips.get(k) or {}
        if str(cur.get("id") or "").startswith("veo:"):
            if f["name"] == cur.get("name"):
                # anh Nhơn đã thả đúng clip Veo vào thư mục 02 → dùng bản trên Drive, GIỮ trạng thái duyệt
                clips[k] = {**cur, "id": f["id"], "veo_local": cur["id"]}
                new.append(k) if cur.get("status") == "cho_duyet" else None
                continue
            if (f.get("modifiedTime") or "") <= (cur.get("modified") or ""):
                continue  # clip Veo mới hơn file trên Drive → giữ clip Veo
        if cur.get("id") != f["id"]:
            clips[k] = {"id": f["id"], "name": f["name"], "modified": f.get("modifiedTime", ""), "status": "cho_duyet",
                        "note": cur.get("note", "") if cur.get("status") == "lam_lai" else "",
                        "rounds": int(cur.get("rounds") or 0) + (1 if cur.get("id") else 0)}
            new.append(k)
    return clips, new


def sync_all() -> list[str]:
    """Chạy định kỳ: đồng bộ clip thô cho các gói chưa đăng; thông báo khi có clip mới."""
    packages.init()
    pend = [p for p in packages.all_packages() if (p.get("status") or "nhap") not in ("da_dang",) and p.get("goi")]
    if not pend or not settings.raw_video_folder_id:
        return []
    files = list_raw()
    msgs = []
    for p in pend:
        clips, new = sync(p, files)
        if not new:
            continue
        save(p["id"], clips)
        msg = f"Có {len(new)} clip thô mới cho Gói {p['goi']} (cảnh {', '.join(sorted(new))}) — vào tab Video thô để duyệt."
        msgs.append(msg)
        with db.tx() as c:
            c.execute("INSERT INTO jobs(kind, status, message, created_at, finished_at, notified, link)"
                      " VALUES('clips','done',?,?,?,0,?)", (msg, db.now_iso(), db.now_iso(), f"/packages/{p['id']}#clips"))
    return msgs


def set_status(pid: int, scene: str, status: str, note: str = "") -> dict:
    p = packages.get(pid)
    clips = load(p)
    cur = clips.get(scene) or {}
    if not cur.get("id"):
        raise ValueError("Cảnh này chưa có clip")
    if status not in ("dat", "lam_lai", "cho_duyet"):
        raise ValueError("Trạng thái không hợp lệ")
    cur.update(status=status, note=note.strip()[:500], reviewed_at=db.now_iso())
    clips[scene] = cur
    save(pid, clips)
    return clips


def local_only(clips: dict) -> list[str]:
    """Các cảnh còn là clip Veo chỉ nằm trên VPS (Gemini chưa đọc được)."""
    return [k for k in sorted(clips) if str((clips.get(k) or {}).get("id") or "").startswith("veo:")]


def all_ok(clips: dict) -> bool:
    return bool(clips) and all((c or {}).get("status") == "dat" for c in clips.values())


def ghep_letter(p: dict, clips: dict) -> tuple[str, str]:
    vn = datetime.now(timezone.utc) + timedelta(hours=7)
    goi = p.get("goi")
    code = f"GHEP-{vn:%d%m}-GOI-{goi}"
    n = len(clips)
    ks = range(1, n + 1)
    rows = "\n".join(f"| Cảnh {k} | {clips[str(k)]['name']} | `{clips[str(k)]['id']}` |" for k in ks)
    from . import tts

    silent = any(clips[str(k)].get("audio") is False or "khongtieng" in str(clips[str(k)].get("name", "")).lower()
                 for k in ks)
    vinfo = tts.scene_info(p)
    voice = ""
    if silent or vinfo:
        vk = tts.voice_key()
        vrows = "\n".join(f"| Cảnh {k} | {vinfo[str(k)]['name']} | {vinfo[str(k)]['seconds']}s · {vinfo[str(k)]['sps']} âm tiết/giây |"
                          if str(k) in vinfo else f"| Cảnh {k} | (chưa có) | |" for k in ks)
        voice = f"""
## Phương án B — clip không tiếng + giọng TTS cố định
Giọng thương hiệu: **{tts.VOICES[vk][2] if vk else '(chưa chọn)'}**. File giọng nằm cùng thư mục 02:

| Cảnh | File giọng | Độ dài · tốc độ |
|---|---|---|
{vrows}

- Lồng file giọng cảnh k vào clip cảnh k (bỏ tiếng gốc của clip nếu có), bắt đầu từ giây 0.
- Chuẩn hoá độ to **−14 LUFS** (loudnorm), cùng mức cho cả {n} cảnh; không thêm nhạc nền.
- Giọng dài hơn 8 giây: tăng tốc tối đa 1,08× (atempo), không cắt chữ. Ngắn hơn: để lặng cuối cảnh.
- Ghi vào BAOCAO nhận xét khẩu hình qua voan (khớp / lệch chấp nhận được / lệch rõ).
"""
    long_note = (" **Video {n} cảnh phải dài TRÊN 61 giây** sau khi ghép: nếu thiếu, giữ khoảng nghỉ thở tự nhiên "
                 "0,2–0,4 giây giữa các cảnh, không làm chậm giọng." if n >= 6 else "")
    long_note = long_note.replace("{n}", str(n))
    md = f"""---
ma_yeu_cau: {code}
loai: yeu_cau_ghep_video (P8b)
tu: TikTok Manager (anh Nhơn đã duyệt {n} clip thô)
gui: Gemini
goi: {goi}
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/BAOCAO-{vn:%d%m}-GHEP-GOI-{goi}__GUI_CLAUDE.md
---

# Ghép video Gói {goi} — {p.get('title') or ''}

Anh Nhơn đã duyệt **ĐẠT cả {n} clip thô** trên TikTok Manager. Gemini làm P8b:

| Cảnh | File trong 02_VIDEO_THO_CHO_KIEM_DUYET | ID Drive |
|---|---|---|
{rows}
{voice}
1. Cắt khoảng lặng đầu/cuối và tạp âm thừa, ghép {n} cảnh theo thứ tự 1→{n}, fade âm 20–30 ms ở điểm nối.{long_note}
2. Gắn hook đầu video: **{p.get('on_screen') or '(chữ trên hình trong phiếu gói)'}** (5–6 giây đầu).
3. Phụ đề tiếng Việt khớp từng giây theo đúng lời thoại phiếu gói.
4. **GIỮ NGUYÊN dấu nhận diện AI (logo ✦) — quy tắc C.10a, không dùng delogo.**
5. Lưu `Goi_{goi}_..._Final_Sub.mp4` và `..._Clean_Master.mp4` vào 04_VIDEO_DA_DUYET_SAN_SANG_DANG.
6. Gửi thư BAOCAO (tên ở dòng file_tra_loi) có 2 dòng đầu thư:
```
goi: {goi}
file_video_final_drive: "<ID bản có phụ đề>"
file_video_clean_khong_sub: "<ID bản sạch>"
```
Tool sẽ tự lấy link video vào Gói {goi}.
"""
    return code, md
