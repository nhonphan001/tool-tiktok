"""Lên chiến lược nội dung bằng Gemini (có phương án dự phòng dựa trên quy tắc)."""
import logging
import threading
import time
from datetime import datetime, timezone

import httpx

from . import analytics, db, report
from .config import settings

log = logging.getLogger(__name__)
GEMINI_URLS = {
    # Gemini API qua AI Studio (generativelanguage.googleapis.com)
    "aistudio": "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
    # Gemini qua Vertex AI / Agent Platform, tính tiền theo Google Cloud Billing (dùng được tín dụng Cloud)
    "vertex": "https://aiplatform.googleapis.com/v1/publishers/google/models/{model}:generateContent",
}

SYSTEM_PROMPT = """Bạn là chuyên gia tăng trưởng kênh TikTok tại Việt Nam.
Dựa HOÀN TOÀN trên số liệu được cung cấp, hãy phân tích và lập chiến lược cụ thể, có thể hành động ngay.
Trả lời bằng tiếng Việt, định dạng Markdown, gồm các mục:
1. Chẩn đoán nhanh (điểm mạnh, điểm yếu, cơ hội — dẫn chứng bằng số liệu)
2. Mô thức nội dung thắng (video nào/vì sao hiệu quả, nên lặp lại yếu tố gì)
3. Lịch đăng đề xuất 7 ngày tới (bảng: ngày, giờ đăng, chủ đề/ý tưởng, định dạng, độ dài, hook gợi ý, hashtag)
4. 10 ý tưởng video mới kèm hook 3 giây đầu
5. Tối ưu caption, hashtag, CTA
6. KPI mục tiêu 30 ngày (follower, view TB, tỉ lệ tương tác) và cách đo
7. Thử nghiệm A/B nên chạy
Không bịa số liệu không có trong dữ liệu; nếu dữ liệu còn ít, hãy nói rõ mức độ tin cậy."""


class StrategyError(Exception):
    pass


def estimate_cost(input_tokens: int, output_tokens: int, thinking_tokens: int) -> float:
    """Chi phí ước tính (USD). Token suy luận (thinking) được tính giá như output."""
    return (
        input_tokens * settings.gemini_price_input + (output_tokens + thinking_tokens) * settings.gemini_price_output
    ) / 1_000_000


def _usage(body: dict) -> dict:
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
        "cost_usd": estimate_cost(inp, out, think),
    }


def record_usage(kind: str, ref_id: int | None, usage: dict) -> None:
    with db.tx() as c:
        c.execute(
            "INSERT INTO ai_usage(created_at, kind, ref_id, backend, model, input_tokens, output_tokens,"
            " thinking_tokens, total_tokens, cost_usd) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                db.now_iso(), kind, ref_id, settings.gemini_backend, settings.gemini_model,
                usage["input_tokens"], usage["output_tokens"], usage["thinking_tokens"],
                usage["total_tokens"], usage["cost_usd"],
            ),
        )


def call_gemini(prompt: str, system: str = SYSTEM_PROMPT) -> tuple[str, dict]:
    """Gọi Gemini, trả về (nội dung, thông tin token/chi phí)."""
    if not settings.gemini_api_key:
        raise StrategyError("Chưa cấu hình GEMINI_API_KEY")
    r = httpx.post(
        GEMINI_URLS.get(settings.gemini_backend, GEMINI_URLS["aistudio"]).format(model=settings.gemini_model),
        headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7},
        },
        timeout=300,
    )
    try:
        body = r.json()
    except ValueError:
        raise StrategyError(f"Gemini trả về lỗi HTTP {r.status_code}")
    if isinstance(body, list) and body:
        body = body[0]
    if r.status_code != 200:
        err = body.get("error", {}) if isinstance(body, dict) else {}
        raise StrategyError(f"Gemini ({settings.gemini_backend}) lỗi: {err.get('message', body)}")
    try:
        parts = body["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
    except (KeyError, IndexError):
        raise StrategyError(f"Gemini không trả về nội dung: {body.get('promptFeedback') or body}")
    return text, _usage(body)


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


EMPTY_USAGE = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}


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
            "INSERT INTO strategies(open_id, created_at, source, model, goal, content_md, status, notified)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (open_id, db.now_iso(), "pending", settings.gemini_model, goal, "", "pending", 0),
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
            source, model, usage = "rule", "", EMPTY_USAGE
        status = "done"
    except Exception as e:  # noqa: BLE001
        log.exception("Strategy generation failed")
        content, source, model, usage, status = f"Lỗi khi tạo chiến lược: {e}", "error", "", EMPTY_USAGE, "error"
    with db.tx() as c:
        c.execute(
            "UPDATE strategies SET content_md=?, source=?, model=?, status=?, notified=0, input_tokens=?,"
            " output_tokens=?, thinking_tokens=?, total_tokens=?, cost_usd=?, duration_sec=? WHERE id=?",
            (
                content, source, model, status, usage["input_tokens"], usage["output_tokens"],
                usage["thinking_tokens"], usage["total_tokens"], usage["cost_usd"],
                round(time.monotonic() - t0, 1), sid,
            ),
        )
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
