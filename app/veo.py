"""Tạo clip thô 8 giây bằng Veo trên Vertex AI (cách tự động hợp lệ cho P8a).

- Ảnh cảnh (Drive) + prompt video của gói → predictLongRunning → chờ fetchPredictOperation → lưu .mp4 trên VPS.
- Clip đưa vào tab "Video thô" (trạng thái Chờ duyệt) như clip anh Nhơn tự tạo.
- Chặn chi phí: phải bật trong Cài đặt, mỗi lần chạy phải xác nhận (hiện giá), có trần ngân sách/tháng,
  mọi lần gọi ghi vào ai_usage (kind='veo').
Giá (Vertex AI, có âm thanh, theo bảng giá Google tra ngày 19/11/2026): Veo 3.1 $0.40/giây;
Veo 3.1 Fast $0.10/giây (720p), $0.12/giây (1080p). Model chỉ có ở us-central1.
"""
import base64
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone

import httpx

from . import db, packages
from .config import settings

log = logging.getLogger(__name__)
LOCATION = "us-central1"
SECONDS = 8
MODELS = {  # khoá: (model id, nhãn, {độ phân giải: USD/giây có âm thanh})
    "fast": ("veo-3.1-fast-generate-001", "Veo 3.1 Fast", {"720p": 0.10, "1080p": 0.12}),
    "standard": ("veo-3.1-generate-001", "Veo 3.1", {"720p": 0.40, "1080p": 0.40}),
}
NEGATIVE = "background music, soundtrack, singing, on-screen text, captions, subtitles, logo, distorted face, extra fingers"
URL = "https://{loc}-aiplatform.googleapis.com/v1/projects/{proj}/locations/{loc}/publishers/google/models/{model}:{verb}"


class VeoError(RuntimeError):
    pass


def model_key() -> str:
    return settings.veo_model if settings.veo_model in MODELS else "fast"


def resolution() -> str:
    return settings.veo_resolution if settings.veo_resolution in ("720p", "1080p") else "720p"


def price_per_clip() -> float:
    return round(MODELS[model_key()][2][resolution()] * SECONDS, 4)


def month_spent() -> float:
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    r = db.query_one("SELECT COALESCE(SUM(cost_usd),0) AS c FROM ai_usage WHERE kind='veo' AND created_at>=?", (start,))
    return float((r or {}).get("c") or 0)


def estimate(n_clips: int) -> dict:
    usd = round(price_per_clip() * n_clips, 2)
    spent = month_spent()
    budget = float(settings.veo_budget_usd or 0)
    return {"clips": n_clips, "usd": usd, "vnd": round(usd * settings.usd_vnd_rate), "model": MODELS[model_key()][1],
            "resolution": resolution(), "per_clip": price_per_clip(), "spent": round(spent, 2), "budget": budget,
            "over_budget": bool(budget) and spent + usd > budget}


def ready() -> tuple[bool, str]:
    if not settings.veo_enabled:
        return False, "Chưa bật Veo trong Cài đặt"
    if not settings.gemini_vertex_project:
        return False, "Chưa có ID project Vertex (Cài đặt → Gemini)"
    if not os.path.exists(settings.google_service_account_file or ""):
        return False, "Thiếu file service account"
    return True, ""


def _token() -> str:
    from .notebooklm import _credentials

    return _credentials(["https://www.googleapis.com/auth/cloud-platform"]).token


def _url(verb: str) -> str:
    return URL.format(loc=LOCATION, proj=settings.gemini_vertex_project, model=MODELS[model_key()][0], verb=verb)


def build_request(prompt: str, image_bytes: bytes, mime: str) -> dict:
    return {
        "instances": [{"prompt": prompt, "image": {"bytesBase64Encoded": base64.b64encode(image_bytes).decode(),
                                                   "mimeType": mime}}],
        "parameters": {"aspectRatio": "9:16", "durationSeconds": SECONDS, "resolution": resolution(),
                       "generateAudio": True, "sampleCount": 1, "personGeneration": "allow_adult",
                       "resizeMode": "crop", "negativePrompt": NEGATIVE},
    }


def _extract_video(resp: dict) -> bytes:
    r = resp.get("response") or {}
    if r.get("raiMediaFilteredCount"):
        raise VeoError("Veo chặn nội dung theo bộ lọc an toàn: " + "; ".join(r.get("raiMediaFilteredReasons") or []))
    vids = r.get("videos") or []
    if not vids:
        raise VeoError("Veo không trả video")
    v = vids[0]
    if v.get("bytesBase64Encoded"):
        return base64.b64decode(v["bytesBase64Encoded"])
    raise VeoError("Veo trả về link Cloud Storage (gcsUri) — tool chỉ hỗ trợ nhận video trực tiếp")


def generate(prompt: str, image_bytes: bytes, mime: str, poll_every: float = 10, timeout: float = 600) -> bytes:
    h = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json"}
    r = httpx.post(_url("predictLongRunning"), headers=h, json=build_request(prompt, image_bytes, mime), timeout=60)
    if r.status_code != 200:
        raise VeoError(f"Veo lỗi {r.status_code}: {r.text[:300]}")
    op = r.json().get("name")
    if not op:
        raise VeoError(f"Veo không trả mã tác vụ: {r.text[:200]}")
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(poll_every)
        q = httpx.post(_url("fetchPredictOperation"), headers=h, json={"operationName": op}, timeout=120)
        if q.status_code != 200:
            raise VeoError(f"Veo lỗi khi chờ kết quả {q.status_code}: {q.text[:200]}")
        j = q.json()
        if j.get("error"):
            raise VeoError(f"Veo lỗi: {j['error'].get('message', j['error'])}")
        if j.get("done"):
            return _extract_video(j)
    raise VeoError("Veo quá 10 phút chưa xong")


def veo_dir() -> str:
    from .media import cache_dir

    d = os.path.join(cache_dir(), "veo")
    os.makedirs(d, exist_ok=True)
    return d


def local_path(clip_id: str) -> str:
    name = clip_id.split(":", 1)[1] if clip_id.startswith("veo:") else ""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+\.mp4", name):
        return ""
    return os.path.join(veo_dir(), name)


def _run_scene(pid: int, scene: str) -> float:
    """Tạo 1 cảnh; trả về chi phí USD (0 nếu lỗi trước khi Veo chạy)."""
    from . import clips, media, strategy

    p = packages.get(pid)
    prompt = (p.get(f"prompt{scene}") or "").strip()
    img_id = media.file_id_for(p, f"image{scene}")
    if not prompt or not img_id:
        raise VeoError(f"Cảnh {scene} thiếu prompt hoặc ảnh")
    path, meta = media.fetch(img_id)
    with open(path, "rb") as f:
        img = f.read()
    mime = meta.get("mimeType") if meta.get("mimeType") in ("image/jpeg", "image/png") else "image/jpeg"
    video = generate(prompt, img, mime)
    cost = price_per_clip()
    strategy.record_usage("veo", pid, {"endpoint": "vertex_veo", "input_tokens": 0, "output_tokens": 0,
                                       "thinking_tokens": 0, "total_tokens": 0, "cost_usd": cost})
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    name = f"Goi_{p.get('goi')}_canh_{scene}_veo_{stamp}.mp4"
    with open(os.path.join(veo_dir(), name), "wb") as f:
        f.write(video)
    cl = clips.load(packages.get(pid))
    cur = cl.get(scene) or {}
    cl[scene] = {"id": f"veo:{name}", "name": name, "modified": db.now_iso(), "status": "cho_duyet",
                 "note": cur.get("note", "") if cur.get("status") == "lam_lai" else "", "source": "veo",
                 "model": MODELS[model_key()][1] + " " + resolution(), "cost_usd": cost,
                 "rounds": int(cur.get("rounds") or 0) + (1 if cur.get("id") else 0)}
    clips.save(pid, cl)
    return cost


def start(pid: int, scenes: list[str]) -> int:
    """Chạy nền; thông báo qua jobs khi xong."""
    ok, why = ready()
    if not ok:
        raise VeoError(why)
    est = estimate(len(scenes))
    if est["over_budget"]:
        raise VeoError(f"Vượt trần ngân sách Veo tháng này (${est['spent']} + ${est['usd']} > ${est['budget']})")
    p = packages.get(pid)
    with db.tx() as c:
        jid = c.execute("INSERT INTO jobs(kind, status, message, created_at, notified, link) VALUES('veo','pending',?,?,0,?)",
                        (f"Veo đang tạo cảnh {', '.join(scenes)} Gói {p.get('goi')}", db.now_iso(),
                         f"/packages/{pid}#clips")).lastrowid

    def _job():
        done, errs, cost = [], [], 0.0
        for s in scenes:
            try:
                cost += _run_scene(pid, s)
                done.append(s)
            except Exception as e:  # noqa: BLE001
                log.exception("veo scene %s", s)
                errs.append(f"cảnh {s}: {str(e)[:160]}")
        msg = (f"Veo đã tạo cảnh {', '.join(done)} Gói {p.get('goi')} — vào tab Video thô để duyệt." if done else "Veo chưa tạo được clip.")
        if errs:
            msg += " Lỗi: " + " · ".join(errs)
        with db.tx() as c:
            c.execute("UPDATE jobs SET status=?, message=?, finished_at=?, cost_usd=?, notified=0 WHERE id=?",
                      ("done" if done else "error", msg[:2000], db.now_iso(), cost, jid))

    threading.Thread(target=_job, daemon=True).start()
    return jid


def running(pid: int) -> bool:
    return bool(db.query_one("SELECT id FROM jobs WHERE kind='veo' AND status='pending' AND link=?", (f"/packages/{pid}#clips",)))


def debug_request_json(prompt: str) -> str:
    """Dùng cho test/hiển thị: body request (ảnh rút gọn)."""
    body = build_request(prompt, b"x", "image/jpeg")
    body["instances"][0]["image"]["bytesBase64Encoded"] = "<ảnh base64>"
    return json.dumps(body, ensure_ascii=False, indent=1)
