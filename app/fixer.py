"""Gợi ý sửa caption bị bộ kiểm tra tuân thủ bắt lỗi.

1. sua_nhanh(): thay cụm từ cấm bằng cách nói an toàn theo quy tắc (0 token), rồi kiểm tra lại.
2. viet_lai_gemini(): Gemini viết lại giữ ý + hashtag; kiểm tra lại, còn lỗi thì cho viết lại 1 lần.
Khớp không phân biệt dấu: "bình an", "binh an", "BÌNH AN" đều bắt được.
"""
import json
import re
import unicodedata

from . import compliance

_VARIANTS: dict[str, str] = {}
for base, chars in {
    "a": "aàáảãạăằắẳẵặâầấẩẫậ", "e": "eèéẻẽẹêềếểễệ", "i": "iìíỉĩị", "o": "oòóỏõọôồốổỗộơờớởỡợ",
    "u": "uùúủũụưừứửữự", "y": "yỳýỷỹỵ", "d": "dđ",
}.items():
    _VARIANTS[base] = chars + chars.upper()


def vi_rx(phrase: str) -> str:
    """'binh an' → regex khớp mọi cách bỏ/thêm dấu, chữ hoa/thường, khoảng trắng linh hoạt."""
    out = []
    for ch in phrase:
        if ch == " ":
            out.append(r"\s+")
        elif ch.lower() in _VARIANTS:
            out.append(f"[{_VARIANTS[ch.lower()]}]")
        elif ch.isalpha():
            out.append(f"[{ch.lower()}{ch.upper()}]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


W = r"[\wÀ-ỹ]"  # ký tự chữ tiếng Việt (để không cắt giữa từ)


def _w(phrase: str) -> str:
    return rf"(?<!{W}){vi_rx(phrase)}(?!{W})"


# (regex, thay bằng, lý do) — thứ tự quan trọng: cụm dài trước
RULES: list[tuple[str, str, str]] = [
    # B.1 – dẫn ra ngoài TikTok
    (r"https?://\S+|www\.\S+", "", "Bỏ đường link (B.1)"),
    (rf"(?<!{W})[a-z0-9-]{{2,}}\s*(?:\.|chấm)\s*(?:vn|com|net|org|me|io|info|site|online|shop|link)\b", "",
     "Bỏ tên miền (B.1)"),
    (_w("link o bio") + "|" + _w("link trong bio") + "|" + _w("link tai bio") + "|" + _w("link bio"),
     "trang cá nhân của Cô Kim", "“Link Bio” → nói chung “trang cá nhân” (chỉ video không giỏ hàng)"),
    (_w("tieu su"), "trang cá nhân", "“tiểu sử” → “trang cá nhân”"),
    (_w("website") + "|" + _w("web site") + "|" + _w("trang web"), "trang cá nhân của Cô Kim", "Không nhắc website"),
    (_w("zalo") + "|" + _w("shopee") + "|" + _w("lazada"), "", "Không nhắc sàn/kênh khác"),
    (_w("bio"), "trang cá nhân", "“bio” → “trang cá nhân”"),
    (_w("link"), "giỏ hàng", "Từ “link” → “giỏ hàng” (hoặc bỏ)"),
    # B.4 – bói toán / vật phẩm / hứa hẹn
    (_w("phong thuy binh an"), "nhẹ lòng an yên", "Không hứa bình an"),
    (_w("cau binh an") + "|" + _w("uoc nguyen binh an") + "|" + _w("giu binh an") + "|" + _w("giu gin binh an"),
     "mong một ngày an yên", "Không hứa bình an"),
    (_w("mang lai binh an") + "|" + _w("mang den binh an"), "giúp lòng nhẹ nhàng hơn", "Không hứa bình an"),
    (r"(?:" + "|".join(_w(x) for x in ("thu hut", "hut", "don", "mang lai", "mang den", "kich", "kich hoat")) + r")\s+(?:"
     + "|".join(vi_rx(x) for x in ("tai loc", "may man", "dieu lanh", "loc la", "vuong khi")) + ")",
     "thêm niềm vui", "Không hứa may mắn / tài lộc"),
    (_w("ruoc loc") + "|" + _w("don loc") + "|" + _w("phu ho"), "đón năm mới nhẹ lòng", "Không hứa lộc / phù hộ"),
    (_w("bua ho menh") + "|" + _w("bua") + "|" + _w("ho menh") + "|" + _w("ho than"), "vật phẩm", "Không gọi là bùa / hộ mệnh"),
    (_w("tran trach") + "|" + _w("tru ta") + "|" + _w("giai han") + "|" + _w("hoa giai") + "|" + _w("khai quang")
     + "|" + _w("linh khi") + "|" + _w("tich ta"), "", "Bỏ công dụng tâm linh"),
    (_w("bo sung nguon nang luong") + "|" + _w("bo sung nang luong") + "|" + _w("bo sung hanh"),
     "cân bằng nhịp sống", "Không nối lá số với vật phẩm"),
    (r"(?<!" + W + r")" + vi_rx("thieu") + r"(?:\s+" + vi_rx("hut") + r")?(?:\s+" + vi_rx("nguon") + r")?\s+" + vi_rx("nang luong")
     + r"\s+(" + "|".join(vi_rx(x) for x in ("kim", "moc", "thuy", "hoa", "tho")) + r")(?!" + W + ")",
     r"ít hành \1", "“thiếu năng lượng X” → “ít hành X” (không nối lá số – vật phẩm)"),
    (r"(?:" + _w("thieu hut nguon nang luong") + "|" + _w("thieu hut nang luong") + "|" + _w("thieu nang luong") + ")",
     "nghiêng về một hành", "Không nói “thiếu năng lượng” (nối lá số – vật phẩm)"),
    (r"(?<!" + W + r")(?:" + vi_rx("khuyet") + "|" + vi_rx("thieu") + r")(?:\s+" + vi_rx("hut") + r")?(?:\s+" + vi_rx("hanh")
     + r")?\s+(" + "|".join(vi_rx(x) for x in ("kim", "moc", "thuy", "hoa", "tho")) + r")(?!" + W + ")",
     r"ít hành \1", "“khuyết/thiếu X” → “ít hành X” (không gợi ý mua vật phẩm bù)"),
    (_w("hop menh nen"), "ai thích thì có thể", "Không “hợp mệnh nên dùng”"),
    (_w("du doan chinh xac"), "gợi ý tham khảo", "Không khẳng định dự đoán chính xác"),
    (_w("chac chan se") + "|" + _w("dam bao se"), "có thể sẽ", "Không khẳng định chắc chắn"),
    (_w("linh nghiem"), "", "Bỏ “linh nghiệm”"),
    (r"100\s*%\s*(?:" + vi_rx("chinh xac") + "|" + vi_rx("linh") + ")", "", "Bỏ “100% chính xác”"),
    (_w("chieu tai"), "", "Bỏ “chiêu tài”"),
    (_w("chua khoi benh") + "|" + _w("chua benh") + "|" + _w("het benh") + "|" + _w("khoi benh"), "", "Không hứa chữa bệnh"),
]
_COMPILED = [(re.compile(rx), rep, why) for rx, rep, why in RULES]


def _tidy(t: str) -> str:
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(rf"\s+(?:{vi_rx('hoac')}|{vi_rx('tai')}|{vi_rx('o')}|{vi_rx('qua')})(?=\s*(?:{vi_rx('nhe')}|{vi_rx('nha')}|[.,!?]|$))",
               "", t)
    t = re.sub(r"\s+([,.!?;:])", r"\1", t)
    t = re.sub(r"([,.;:])\1+", r"\1", t)
    t = re.sub(r"\(\s*\)|\[\s*\]", "", t)
    t = re.sub(r"(?<!\S)#(?=\s|$)", "", t)  # hashtag bị xoá còn lại dấu # đứng một mình
    t = re.sub(r"[ \t]{2,}", " ", t)
    return "\n".join(x.strip() for x in t.splitlines()).strip()


def sua_nhanh(text: str, has_cart: bool | None = None) -> dict:
    """Trả về {text, changes: [(cũ, mới, lý do)], before, after}."""
    out, changes = text or "", []
    for rx, rep, why in _COMPILED:
        def _sub(m):
            new = m.expand(rep) if "\\" in rep else rep
            reason = why
            if has_cart and why.startswith("“Link Bio”"):
                new, reason = "giỏ hàng góc trái", "“Link Bio” → “giỏ hàng góc trái” (video có giỏ hàng)"
            changes.append((m.group(0), new, reason))
            return new
        out = rx.sub(_sub, out)
    out = _tidy(out)
    from .packages import ITEM_ADVICE

    notes = []
    m = ITEM_ADVICE.search(unicodedata.normalize("NFC", out).lower())
    if m:
        notes.append(f"Câu còn khuyên dùng vật phẩm (“{m.group(0)}”): nếu video nói về lá số, nên bỏ câu này (B.4.1).")
    after = compliance.check(out, has_cart)
    if after["offsite"] and not has_cart:
        notes.append("“trang cá nhân của Cô Kim” chỉ hợp lệ với video KHÔNG gắn giỏ hàng; video có giỏ hàng thì bỏ hẳn câu đó.")
        after_nocart = compliance.check(out, False)
    else:
        after_nocart = after
    return {"text": out, "changes": changes, "before": compliance.check(text, has_cart), "after": after,
            "after_nocart": after_nocart, "notes": notes}


FIX_SYSTEM = """Bạn sửa caption TikTok của kênh "Tiệm Trà Giải Mã – Cô Kim" để tuân thủ chính sách TikTok.
Giữ nguyên ý chính, giọng ấm áp, emoji và hashtag (bỏ hashtag nào chứa từ cấm). Độ dài tương đương bản gốc.
TUYỆT ĐỐI không dùng: link, bio, web, tên miền, Zalo, Shopee, Lazada; may mắn, tài lộc, rước lộc, bình an (khi hứa hẹn),
phù hộ, bùa, hộ mệnh, hộ thân, trấn trạch, giải hạn, hóa giải, khai quang; "khuyết/thiếu hành X", "bổ sung năng lượng",
"hợp mệnh nên dùng"; "chắc chắn sẽ", "dự đoán chính xác", "linh nghiệm"; hứa chữa bệnh, giàu có.
Video lá số được nói về ngũ hành của lá số nhưng không khuyên dùng vật phẩm.
CTA được phép: "bấm giỏ hàng góc trái" (chỉ khi có giỏ hàng), "để lại ngày sinh dưới bình luận để Cô Kim giải mã",
"bấm theo dõi Cô Kim". Trả về JSON: {"caption": "...", "giai_thich": "1 câu nói đã sửa gì"}"""


def viet_lai_gemini(text: str, has_cart: bool | None = None) -> dict:
    from . import strategy

    def ask(extra=""):
        prompt = f"Caption gốc (video {'có' if has_cart else 'không'} gắn giỏ hàng):\n{text}"
        if extra:
            prompt += f"\n\nBản trước vẫn còn lỗi, tránh: {extra}"
        out, usage = strategy.call_gemini(prompt, system=FIX_SYSTEM, json_mode=True)
        strategy.record_usage("fix_caption", None, usage)
        try:
            d = json.loads(out[out.find("{"): out.rfind("}") + 1])
        except ValueError:
            d = {"caption": out.strip(), "giai_thich": ""}
        return str(d.get("caption") or "").strip(), str(d.get("giai_thich") or ""), usage

    cap, why, usage = ask()
    after = compliance.check(cap, has_cart)
    if after["level"] not in ("ok", "warning"):
        bad = ", ".join(f"“{x['match']}”" for x in after["offsite"] + after["promise"])
        cap, why, u2 = ask(bad)
        usage = {k: (usage.get(k, 0) or 0) + (u2.get(k, 0) or 0) if isinstance(u2.get(k), (int, float)) else u2.get(k)
                 for k in u2}
        after = compliance.check(cap, has_cart)
    return {"text": cap, "why": why, "after": after, "usage": usage}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
