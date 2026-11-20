"""Lên chiến lược nội dung bằng Gemini (có phương án dự phòng dựa trên quy tắc)."""
import logging
import threading
import time
from datetime import datetime, timezone

import httpx

from . import analytics, db, pricing, report
from .config import settings

log = logging.getLogger(__name__)
GEMINI_URLS = {
    # Gemini API qua AI Studio (generativelanguage.googleapis.com)
    "aistudio": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    # Gemini qua Vertex AI / Agent Platform, tính tiền theo Google Cloud Billing (dùng được tín dụng Cloud)
    "vertex": "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent",
    # Vertex endpoint global (cần mã project): rẻ hơn ~9%, ít lỗi 429, không chọn được nơi xử lý
    "vertex_global": "https://aiplatform.googleapis.com/v1/projects/{project}/locations/global/publishers/google/"
                     "models/{model}:generateContent",
}
ENDPOINT_LABELS = {
    "aistudio": "AI Studio (Gemini API)",
    "vertex": "Vertex AI · theo vùng (Google chọn vùng, thường là đa vùng EU)",
    "vertex_global": "Vertex AI · global",
}


def planned_endpoint() -> str:
    """Endpoint sẽ dùng theo Cài đặt: aistudio | vertex | vertex_global."""
    if settings.gemini_backend != "vertex":
        return "aistudio"
    if settings.gemini_vertex_location == "global" and settings.gemini_vertex_project:
        return "vertex_global"
    return "vertex"

SYSTEM_PROMPT = """Bạn là chuyên gia tăng trưởng kênh TikTok tại Việt Nam.
Dựa HOÀN TOÀN trên số liệu được cung cấp, hãy phân tích và lập chiến lược cụ thể, có thể hành động ngay.
Trả lời bằng tiếng Việt, định dạng Markdown, gồm các mục:
1. Chẩn đoán nhanh (điểm mạnh, điểm yếu, cơ hội — dẫn chứng bằng số liệu)
2. Mô thức nội dung thắng (video nào/vì sao hiệu quả, nên lặp lại yếu tố gì)
3. Lịch đăng đề xuất 7 ngày tới (bảng: ngày, giờ đăng, loại (1/2/3), chủ đề/ý tưởng, định dạng, độ dài, hook gợi ý, hashtag).
   Ràng buộc đã chốt với chủ kênh: nhịp 2 video/ngày — 11:00 Loại 3 (trà sáng/chữa lành, kéo tim + follow),
   19:00 Loại 1 (lá số; ưu tiên nhóm 4 trả lời bình luận thật). Loại 2 (giỏ hàng) TỐI ĐA 2 video/tuần, đăng 12:00,
   chỉ dùng sản phẩm đã sẵn sàng; video Loại 2 KHÔNG nhắc lá số/tuổi/Bát Tự, KHÔNG hashtag #battu #tutru #phongthuy #tuvi…,
   không dùng từ "thỉnh"; CTA duy nhất "bấm giỏ hàng góc trái". Mỗi video 4 cảnh × 8 giây (~32s).
4. 10 ý tưởng video mới kèm hook 3 giây đầu
5. Tối ưu caption, hashtag, CTA (CTA chỉ dùng các câu được phép trong QUY TẮC NỘI DUNG BẮT BUỘC bên dưới)
6. KPI mục tiêu 7 ngày và 30 ngày (follower, view TB, tim/view, bình luận/video) — đặt theo tốc độ thực tế, nói rõ mốc nào khả thi
7. Thử nghiệm A/B nên chạy
Không bịa số liệu không có trong dữ liệu; nếu dữ liệu còn ít, hãy nói rõ mức độ tin cậy."""


class StrategyError(Exception):
    pass


def estimate_cost(input_tokens: int, output_tokens: int, thinking_tokens: int, model: str | None = None,
                  backend: str | None = None, when=None) -> float:
    """Chi phí ước tính (USD) theo bảng giá của model/cổng gọi tại thời điểm gọi."""
    return pricing.cost(input_tokens, output_tokens, thinking_tokens, model or settings.gemini_model,
                        backend or settings.gemini_backend, when)


def recompute_costs() -> int:
    """Tính lại chi phí mọi lần gọi đã lưu theo bảng giá hiện tại. Trả về số bản ghi đã cập nhật."""
    n = 0
    rows = db.query("SELECT * FROM ai_usage")
    backend_by_strategy = {}
    with db.tx() as c:
        for r in rows:
            cst = estimate_cost(r["input_tokens"], r["output_tokens"], r["thinking_tokens"], r["model"],
                                r["backend"], r["created_at"])
            c.execute("UPDATE ai_usage SET cost_usd=? WHERE id=?", (cst, r["id"]))
            if r["kind"] == "strategy" and r["ref_id"]:
                backend_by_strategy[r["ref_id"]] = r["backend"]
            n += 1
        srows = c.execute(
            "SELECT id, model, created_at, input_tokens, output_tokens, thinking_tokens, endpoint FROM strategies"
            " WHERE total_tokens > 0"
        ).fetchall()
        for st in srows:
            cst = estimate_cost(st["input_tokens"], st["output_tokens"], st["thinking_tokens"], st["model"],
                                backend_by_strategy.get(st["id"]) or st["endpoint"] or None, st["created_at"])
            c.execute("UPDATE strategies SET cost_usd=? WHERE id=?", (cst, st["id"]))
            n += 1
    return n


def _usage(body: dict, endpoint: str | None = None) -> dict:
    um = body.get("usageMetadata") or {}
    inp = int(um.get("promptTokenCount") or 0)
    out = int(um.get("candidatesTokenCount") or 0)
    think = int(um.get("thoughtsTokenCount") or 0)
    total = int(um.get("totalTokenCount") or (inp + out + think))
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "thinking_tokens": think,
        "total_tokens": total,
        "cost_usd": estimate_cost(inp, out, think, backend=endpoint),
        "endpoint": endpoint or planned_endpoint(),
    }


def record_usage(kind: str, ref_id: int | None, usage: dict) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO ai_usage(created_at, kind, ref_id, backend, model, input_tokens, output_tokens,"
            " thinking_tokens, total_tokens, cost_usd) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                db.now_iso(), kind, ref_id, usage.get("endpoint") or planned_endpoint(), settings.gemini_model,
                usage["input_tokens"], usage["output_tokens"], usage["thinking_tokens"],
                usage["total_tokens"], usage["cost_usd"],
            ),
        )


def full_system_prompt(base: str = "") -> str:
    """Lời nhắc hệ thống luôn kèm quy tắc nội dung bắt buộc của kênh."""
    base = base or SYSTEM_PROMPT
    if settings.content_rules:
        base += "\n\n" + settings.content_rules
    return base


def _post(endpoint: str, payload: dict) -> tuple[int, dict]:
    url = GEMINI_URLS[endpoint].format(model=settings.gemini_model, project=settings.gemini_vertex_project)
    r = httpx.post(
        url,
        headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )
    try:
        body = r.json()
    except ValueError:
        body = {"error": {"message": f"HTTP {r.status_code}, phản hồi không phải JSON"}}
    if isinstance(body, list) and body:
        body = body[0]
    return r.status_code, body if isinstance(body, dict) else {"error": {"message": str(body)}}


def _err(body: dict) -> str:
    return str((body.get("error") or {}).get("message") or body)[:500]


def call_gemini(prompt: str, system: str = SYSTEM_PROMPT, json_mode: bool = False) -> tuple[str, dict]:
    """Gọi Gemini, trả về (nội dung, thông tin token/chi phí/endpoint).

    Nếu bật Vertex global mà lỗi, tự gọi lại endpoint theo vùng và ghi chú lý do trong usage["endpoint_note"].
    """
    if not settings.gemini_api_key:
        raise StrategyError("Chưa cấu hình GEMINI_API_KEY")
    payload = {
        "systemInstruction": {"parts": [{"text": full_system_prompt(system)}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": (
            {"temperature": 0.2, "responseMimeType": "application/json"} if json_mode else {"temperature": 0.7}
        ),
    }
    endpoint = planned_endpoint()
    note = ""
    status, body = _post(endpoint, payload)
    if status != 200 and endpoint == "vertex_global":
        log.warning("Vertex global failed (%s), falling back to regional: %s", status, _err(body))
        note = f"global lỗi (HTTP {status}: {_err(body)[:160]}) → đã tự chuyển sang theo vùng"
        endpoint = "vertex"
        status, body = _post(endpoint, payload)
    if status != 200:
        raise StrategyError(f"Gemini ({ENDPOINT_LABELS[endpoint]}) lỗi: {_err(body)}" + (f" [{note}]" if note else ""))
    try:
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (KeyError, IndexError):
        raise StrategyError(f"Gemini không trả về nội dung: {body.get('promptFeedback') or body}")
    usage = _usage(body, endpoint)
    usage["endpoint_note"] = note
    return text, usage


def rule_based(open_id: str, goal: str) -> str:
    an = analytics.deep_analysis(open_id)
    lines = [
        "## Chiến lược tự động (dựa trên quy tắc)",
        *([] if settings.gemini_api_key else ["_Cấu hình GEMINI_API_KEY để nhận chiến lược chi tiết bằng AI._", ""]),
        f"**Mục tiêu:** {goal or 'Tăng trưởng follower và lượt xem'}",
        "",
        "### Nhận định",
        *[f"- {i}" for i in an["insights"]],
        "",
        "### Hành động đề xuất",
    ]
    best_hours = sorted([h for h in an["hour"] if h["count"]], key=lambda h: h["avg_views"], reverse=True)[:2]
    best_days = sorted([d for d in an["weekday"] if d["count"]], key=lambda d: d["avg_views"], reverse=True)[:3]
    if best_days and best_hours:
        lines.append(
            "- Ưu tiên đăng vào " + ", ".join(d["label"] for d in best_days)
            + " lúc " + " hoặc ".join(h["label"] for h in best_hours) + "."
        )
    if an["top"]:
        lines.append("- Làm lại / làm phần tiếp theo cho các video top: " + "; ".join(v["label"][:50] for v in an["top"][:3]) + ".")
    if an["trending"]:
        lines.append("- Video đang lên, nên ghim / trả lời bình luận / làm video phản hồi: " + "; ".join(v["label"][:50] for v in an["trending"][:3]) + ".")
    best_dur = max((d for d in an["duration"] if d["count"]), key=lambda d: d["avg_views"], default=None)
    if best_dur:
        lines.append(f"- Giữ phần lớn video trong khoảng {best_dur['label']}.")
    tags = [t for t in an["hashtags"] if t["count"] >= 2][:5]
    if tags:
        lines.append("- Dùng lại bộ hashtag: " + " ".join(f"#{t['key']}" for t in tags) + ".")
    lines += [
        "- Hook 3 giây đầu: nêu kết quả/xung đột ngay, chữ lớn trên màn hình.",
        "- Mỗi video kết thúc bằng 1 câu hỏi để tăng bình luận.",
        "- Đăng đều tối thiểu 1 video/ngày trong 2 tuần để thử nghiệm khung giờ.",
    ]
    return "\n".join(lines)


EMPTY_USAGE = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "total_tokens": 0, "cost_usd": 0.0,
               "endpoint": "", "endpoint_note": ""}


def _build_prompt(open_id: str, goal: str) -> str:
    data_md = report.build_report(open_id)
    prev = db.query_one(
        "SELECT content_md, created_at FROM strategies WHERE open_id=? AND status='done'"
        " ORDER BY created_at DESC LIMIT 1",
        (open_id,),
    )
    prompt = ""
    if settings.channel_context:
        prompt += f"=== THÔNG TIN KÊNH (do chủ kênh mô tả) ===\n{settings.channel_context}\n\n"
    prompt += f"Mục tiêu của chủ kênh: {goal or 'Tăng trưởng follower, lượt xem và tương tác bền vững'}\n\n"
    prompt += "=== SỐ LIỆU KÊNH ===\n" + data_md
    if prev:
        prompt += f"\n=== CHIẾN LƯỢC TRƯỚC ĐÓ ({analytics.localtime(prev['created_at'])}) — đánh giá xem đã hiệu quả chưa ===\n"
        prompt += (prev["content_md"] or "")[:6000]
    return prompt


def start(open_id: str, goal: str = "") -> int:
    """Tạo bản ghi chiến lược ở trạng thái 'pending' (đang tạo)."""
    with db.tx() as c:
        cur = c.execute(
            "INSERT INTO strategies(open_id, created_at, source, model, goal, content_md, status, notified, endpoint)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (open_id, db.now_iso(), "pending", settings.gemini_model, goal, "", "pending", 0, planned_endpoint()),
        )
        return cur.lastrowid


def run(sid: int) -> dict:
    """Chạy tạo chiến lược cho bản ghi sid (dùng trong luồng chạy ngầm)."""
    row = db.query_one("SELECT open_id, goal FROM strategies WHERE id=?", (sid,))
    if not row:
        return {}
    t0 = time.monotonic()
    try:
        prompt = _build_prompt(row["open_id"], row["goal"] or "")
        try:
            content, usage = call_gemini(prompt)
            source, model = "gemini", settings.gemini_model
            record_usage("strategy", sid, usage)
        except StrategyError as e:
            log.warning("Gemini unavailable, fallback rule-based: %s", e)
            content = rule_based(row["open_id"], row["goal"] or "") + f"\n\n> Ghi chú: {e}"
            source, model, usage = "rule", "", dict(EMPTY_USAGE, endpoint=planned_endpoint())
        status = "done"
    except Exception as e:  # noqa: BLE001
        log.exception("Strategy generation failed")
        content, source, model, status = f"Lỗi khi tạo chiến lược: {e}", "error", "", "error"
        usage = dict(EMPTY_USAGE, endpoint=planned_endpoint())
    with db.tx() as c:
        c.execute(
            "UPDATE strategies SET content_md=?, source=?, model=?, status=?, notified=0, input_tokens=?,"
            " output_tokens=?, thinking_tokens=?, total_tokens=?, cost_usd=?, duration_sec=?, endpoint=?,"
            " endpoint_note=? WHERE id=?",
            (
                content, source, model, status, usage["input_tokens"], usage["output_tokens"],
                usage["thinking_tokens"], usage["total_tokens"], usage["cost_usd"],
                round(time.monotonic() - t0, 1), usage.get("endpoint") or "", usage.get("endpoint_note") or "", sid,
            ),
        )
    if status == "done" and source == "gemini":
        from . import cycle_summary  # gửi bản tóm tắt vào hộp thư Gemini + Claude (đánh giá chéo)

        cycle_summary.after_strategy(sid)
    return {"id": sid, "source": source, "status": status, "content_md": content, **usage}


def start_background(open_id: str, goal: str = "", on_done=None) -> int:
    sid = start(open_id, goal)

    def _job():
        run(sid)
        if on_done:
            try:
                on_done(open_id)
            except Exception:  # noqa: BLE001
                log.exception("on_done failed")

    threading.Thread(target=_job, daemon=True).start()
    return sid


def generate(open_id: str, goal: str = "") -> dict:
    """Tạo chiến lược đồng bộ (dùng cho quét tự động và test)."""
    res = run(start(open_id, goal))
    with db.tx() as c:  # tạo tự động: không cần hiện thông báo
        c.execute("UPDATE strategies SET notified=1 WHERE id=?", (res["id"],))
    return res


def usage_summary() -> dict:
    """Tổng token & chi phí: tháng này và toàn bộ (theo giờ địa phương)."""
    tz = analytics._tz()
    month_start = datetime.now(tz).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_iso = month_start.astimezone(timezone.utc).isoformat()
    q = "SELECT COUNT(*) AS calls, COALESCE(SUM(total_tokens),0) AS tokens, COALESCE(SUM(cost_usd),0) AS cost FROM ai_usage"
    month = db.query_one(q + " WHERE created_at >= ?", (month_iso,))
    total = db.query_one(q)
    for d in (month, total):
        d["cost_vnd"] = round(d["cost"] * settings.usd_vnd_rate)
    return {"month": month, "total": total}


def ask(open_id: str, question: str) -> str:
    """Hỏi đáp tự do về số liệu kênh."""
    data_md = report.build_report(open_id)
    system = "Bạn là chuyên gia phân tích TikTok. Trả lời ngắn gọn bằng tiếng Việt, dựa trên số liệu được cung cấp."
    ctx = f"=== THÔNG TIN KÊNH ===\n{settings.channel_context}\n\n" if settings.channel_context else ""
    text, usage = call_gemini(f"{ctx}=== SỐ LIỆU KÊNH ===\n{data_md}\n\n=== CÂU HỎI ===\n{question}", system=system)
    record_usage("ask", None, usage)
    return text, usage
