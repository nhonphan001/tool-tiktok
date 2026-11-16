"""Lên chiến lược nội dung bằng Gemini (có phương án dự phòng dựa trên quy tắc)."""
import logging

import httpx

from . import analytics, db, report
from .config import settings

log = logging.getLogger(__name__)
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

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


def call_gemini(prompt: str, system: str = SYSTEM_PROMPT) -> str:
    if not settings.gemini_api_key:
        raise StrategyError("Chưa cấu hình GEMINI_API_KEY")
    r = httpx.post(
        GEMINI_URL.format(model=settings.gemini_model),
        headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7},
        },
        timeout=180,
    )
    try:
        body = r.json()
    except ValueError:
        raise StrategyError(f"Gemini trả về lỗi HTTP {r.status_code}")
    if r.status_code != 200:
        raise StrategyError(f"Gemini lỗi: {body.get('error', {}).get('message', body)}")
    try:
        parts = body["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError):
        raise StrategyError(f"Gemini không trả về nội dung: {body.get('promptFeedback') or body}")


def rule_based(open_id: str, goal: str) -> str:
    an = analytics.deep_analysis(open_id)
    lines = [
        "## Chiến lược tự động (dựa trên quy tắc)",
        "_Cấu hình GEMINI_API_KEY để nhận chiến lược chi tiết bằng AI._",
        "",
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


def generate(open_id: str, goal: str = "") -> dict:
    data_md = report.build_report(open_id)
    prev = db.query_one(
        "SELECT content_md, created_at FROM strategies WHERE open_id=? ORDER BY created_at DESC LIMIT 1", (open_id,)
    )
    prompt = f"Mục tiêu của chủ kênh: {goal or 'Tăng trưởng follower, lượt xem và tương tác bền vững'}\n\n"
    prompt += "=== SỐ LIỆU KÊNH ===\n" + data_md
    if prev:
        prompt += f"\n=== CHIẾN LƯỢC TRƯỚC ĐÓ ({prev['created_at']}) — đánh giá xem đã hiệu quả chưa ===\n"
        prompt += (prev["content_md"] or "")[:6000]
    try:
        content, source, model = call_gemini(prompt), "gemini", settings.gemini_model
    except StrategyError as e:
        log.warning("Gemini unavailable, fallback rule-based: %s", e)
        content, source, model = rule_based(open_id, goal) + f"\n\n> Ghi chú: {e}", "rule", ""
    with db.tx() as c:
        cur = c.execute(
            "INSERT INTO strategies(open_id, created_at, source, model, goal, content_md) VALUES(?,?,?,?,?,?)",
            (open_id, db.now_iso(), source, model, goal, content),
        )
        sid = cur.lastrowid
    return {"id": sid, "source": source, "content_md": content}


def ask(open_id: str, question: str) -> str:
    """Hỏi đáp tự do về số liệu kênh."""
    data_md = report.build_report(open_id)
    system = "Bạn là chuyên gia phân tích TikTok. Trả lời ngắn gọn bằng tiếng Việt, dựa trên số liệu được cung cấp."
    return call_gemini(f"=== SỐ LIỆU KÊNH ===\n{data_md}\n\n=== CÂU HỎI ===\n{question}", system=system)
