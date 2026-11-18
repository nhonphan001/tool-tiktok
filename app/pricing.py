"""Bảng giá Gemini (USD / 1 triệu token) để ước tính chi phí.

Nguồn (đọc ngày 18/11/2026):
- https://aistudio.google.com/docs/pricing  (Gemini API / AI Studio, Paid tier)
- https://cloud.google.com/vertex-ai/generative-ai/pricing  (Vertex AI / Agent Platform)
Token suy luận (thinking) tính theo giá output. Giá có thể thay đổi — kiểm tra lại định kỳ.
"""
from datetime import date, datetime, timezone

# model -> danh sách (áp dụng từ ngày, {cổng: (giá input, giá output)}), sắp theo ngày tăng dần
# "vertex" = endpoint theo vùng (non-global, vd. europe-west1); "vertex_global" = vùng global.
_FLASH_3X = [
    (date(2000, 1, 1), {"aistudio": (0.75, 3.75), "vertex_global": (0.75, 3.75), "vertex": (0.825, 4.125)}),
    (date(2027, 1, 1), {"aistudio": (1.50, 7.50), "vertex_global": (1.50, 7.50), "vertex": (1.65, 8.25)}),
]
PRICE_TABLE = {
    "gemini-3.8-flash": _FLASH_3X,
    "gemini-3.7-flash": _FLASH_3X,
    "gemini-3.6-flash": _FLASH_3X,
}


def _as_date(when) -> date:
    if when is None:
        return datetime.now(timezone.utc).date()
    if isinstance(when, datetime):
        return when.date()
    if isinstance(when, date):
        return when
    try:
        return datetime.fromisoformat(str(when)).date()
    except ValueError:
        return datetime.now(timezone.utc).date()


def table_price(model: str, backend: str, when=None) -> tuple[float, float] | None:
    periods = PRICE_TABLE.get((model or "").strip())
    if not periods:
        return None
    d = _as_date(when)
    chosen = None
    for start, prices in periods:
        if d >= start:
            chosen = prices
    if not chosen:
        return None
    return chosen.get(backend) or chosen.get("aistudio")


def price_for(model: str, backend: str, when=None) -> tuple[float, float, str]:
    """Giá (input, output, nguồn). Giá nhập tay trong Cài đặt (> 0) được ưu tiên."""
    from .config import settings

    if settings.gemini_price_input > 0 and settings.gemini_price_output > 0:
        return settings.gemini_price_input, settings.gemini_price_output, "nhập tay trong Cài đặt"
    p = table_price(model, backend, when)
    if p:
        return p[0], p[1], "bảng giá Google"
    return 0.0, 0.0, "chưa có giá cho model này — nhập tay trong Cài đặt"


def cost(input_tokens: int, output_tokens: int, thinking_tokens: int, model: str, backend: str, when=None) -> float:
    p_in, p_out, _ = price_for(model, backend, when)
    return ((input_tokens or 0) * p_in + ((output_tokens or 0) + (thinking_tokens or 0)) * p_out) / 1_000_000
