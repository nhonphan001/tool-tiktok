"""Trả lời nhanh bình luận / tin nhắn xin xem lá số bằng Gemini API + tạo gói sản xuất từ tin nhắn.

- Lá số do TOOL tính (battu) — Gemini chỉ viết lời, không tự tính can chi.
- Câu trả lời ngắn kiểu bình luận TikTok, giọng Cô Kim; kiểm tra tuân thủ (B.1/B.4), lỗi thì cho viết lại 1 lần.
- Không lưu tin nhắn của khách (giống trang Lá số).
"""
import json
import re

from . import battu, compliance

REPLY_SYSTEM = """Bạn là Cô Kim của kênh TikTok "Tiệm Trà Giải Mã" (@tiemtragiaima): người pha trà kể chuyện, giải mã Bát Tự
nhẹ nhàng, giọng miền Nam ấm áp, xưng "Cô Kim", gọi khách là "con" hoặc "chị/anh" theo cách khách xưng hô.
Viết 1 câu TRẢ LỜI BÌNH LUẬN TikTok (120–280 ký tự, tối đa 2 emoji trà/hoa) cho tin nhắn của khách.

BẮT BUỘC:
- Chỉ dùng đúng lá số TikTok Manager tính sẵn (không tự tính can chi, không đổi Nhật chủ).
- Kênh chỉ giải mã BÁT TỰ. Nếu khách xin gieo quẻ / Kinh Dịch / tử vi khác: cảm ơn, nói khéo là Cô Kim xem theo Bát Tự
  ngày giờ sinh, và sẽ trả lời trong video (KHÔNG hứa gieo quẻ).
- Không hứa trước kết quả, không phán chắc chắn, không hù dọa; không hứa may mắn, tài lộc, bình an, chữa bệnh.
- Không nhắc link, bio, web, Zalo, inbox, giá tiền, dịch vụ trả phí; không khuyên mua/đeo vật phẩm.
- Không ghi họ tên khách; không lặp lại ngày sinh đầy đủ công khai (chỉ nói năm hoặc can chi năm).
- Có 1 câu gợi tò mò về lá số (nhẹ nhàng, tích cực) và hẹn: "Cô Kim sẽ giải mã kỹ trong video tối nay/sắp tới nha".
Trả về JSON: {"tra_loi": "...", "goi_y_video": "1 câu gợi ý chủ đề video trả lời bình luận này", "ghi_chu": "..."}"""


def chart_brief(c: dict) -> str:
    return (f"{battu.mo_ta_ngan(c)}; Hỷ thần {c.get('hy_than', '')}; Kỵ thần {', '.join(c.get('ky_than') or [])}; "
            f"âm lịch {c.get('am_lich', '')}")


def anonymize(text: str) -> str:
    """Bỏ tên riêng sau danh xưng: 'Chị Ngọc' → 'một chị', '@nick' → '(nick)'."""
    t = re.sub(r"@[\w.]+", "(nick)", text or "")
    t = re.sub(r"\b(Chị|chị|Anh|anh|Cô|cô|Em|em|Bé|bé|Chú|chú|Bác|bác)\s+(?!Kim\b)[A-ZĐ][a-zà-ỹ]+(?:\s+(?!Kim\b)[A-ZĐ][a-zà-ỹ]+)?",
               lambda m: "một " + m.group(1).lower(), t)
    return t


def draft_reply(message: str, chart: dict) -> dict:
    from . import strategy

    def ask(extra: str = ""):
        prompt = (f"Tin nhắn của khách (đã ẩn tên):\n{anonymize(message)[:1500]}\n\n"
                  f"Lá số TikTok Manager tính:\n{chart_brief(chart)}")
        if extra:
            prompt += f"\n\nBản trước vi phạm quy tắc, tránh: {extra}"
        out, usage = strategy.call_gemini(prompt, system=REPLY_SYSTEM, json_mode=True)
        strategy.record_usage("reply", None, usage)
        try:
            d = json.loads(out[out.find("{"): out.rfind("}") + 1])
        except ValueError:
            d = {"tra_loi": out.strip()}
        return d, usage

    d, usage = ask()
    reply = str(d.get("tra_loi") or "").strip()
    chk = compliance.check(reply, False)
    if chk["offsite"] or chk["promise"]:
        bad = ", ".join(f"“{x['match']}”" for x in chk["offsite"] + chk["promise"])
        d, u2 = ask(bad)
        reply = str(d.get("tra_loi") or "").strip()
        chk = compliance.check(reply, False)
        usage = {**usage, "cost_usd": (usage.get("cost_usd") or 0) + (u2.get("cost_usd") or 0)}
    return {"reply": reply, "idea": str(d.get("goi_y_video") or ""), "note": str(d.get("ghi_chu") or ""),
            "level": chk["level"], "issues": [x["match"] for x in chk["offsite"] + chk["promise"]],
            "cost_usd": round(float(usage.get("cost_usd") or 0), 5)}


def package_prefill(message: str, row: dict) -> dict:
    """Giá trị điền sẵn form Yêu cầu Gemini (Loại 1, nhóm 4) từ 1 tin nhắn đã lập được lá số."""
    c = row["chart"]
    year_can_chi = (c.get("tu_tru") or "").split(" – ")[0]
    who = {"nu": "một chị", "nam": "một anh"}.get(row.get("gioi") or "", "một vị khách")
    msg = anonymize(message).strip()
    asks_iching = bool(re.search(r"kinh\s*d[iị]ch|gieo\s*qu[ẻe]|qu[ẻe]", message or "", re.I))
    brief = (f"Nhóm 4 – trả lời tin nhắn/bình luận thật của {who} sinh năm {row.get('y')} ({year_can_chi}). "
             f"Nội dung khách gửi (đã ẩn tên): \"{msg[:600]}\". "
             f"Dùng NGUYÊN VĂN lá số tool tính: {battu.mo_ta_ngan(c)}. "
             + ("Khách hỏi gieo quẻ Kinh Dịch: KHÔNG gieo quẻ, chỉ giải mã Bát Tự cho năm mới 2027 (Đinh Mùi) theo lá số. "
                if asks_iching else "")
             + "Không ghi tên người hỏi, không đọc đủ ngày sinh trong lời thoại. Hook mạnh ở giây 0. Kết bằng "
             "“để lại ngày sinh dưới bình luận để Cô Kim giải mã”.")
    return {
        "brief": brief, "title": f"Trả lời {who} {year_can_chi} {row.get('y')}"[:60], "loai": 1, "goal": "comment",
        "publish": "19:00 hôm nay",
        "dd": row.get("d"), "mm": row.get("m"), "yy": row.get("y"),
        "t": f"{row['h']:02d}:{row['mi']:02d}" if row.get("h") is not None else "",
        "lich": "am" if row.get("lunar") else "duong", "gioi": row.get("gioi") or "",
    }
