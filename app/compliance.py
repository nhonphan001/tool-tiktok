"""Kiểm tra nội dung theo quy tắc TikTok Shop của kênh.

- violation: lời mời ra ngoài nền tảng (web, Bio, tiểu sử, tên miền, Zalo, Shopee, Lazada, link).
  Với video CÓ giỏ hàng là vi phạm (bị loại); video không giỏ hàng thì là cảnh báo.
- warning: lời hứa hẹn quá đà / hù dọa.
"""
import re
import unicodedata

# (mã, mô tả, regex trên văn bản đã bỏ dấu + chữ thường)
OFFSITE_RULES = [
    ("link_bio", "Link Bio / bio", r"\blink\s*(o|tai|trong)?\s*bio\b|\bbio\b"),
    ("tieu_su", "trang tiểu sử", r"tieu\s*su"),
    ("trang_ca_nhan", "trang cá nhân", r"trang\s*ca\s*nhan"),
    ("website", "website / trang web", r"\bweb\s*site\b|\bweb\b|trang\s*web"),
    ("domain", "tên miền", r"\b[a-z0-9-]{2,}\s*(\.|\s*cham\s*)\s*(vn|com|net|org|me|io|info|site|online|shop|link)\b"),
    ("url", "đường link http/www", r"https?\s*:\s*/|www\s*\."),
    ("link", "từ 'link'", r"\blink\b"),
    ("zalo", "Zalo", r"\bzalo\b|\bza\s*lo\b"),
    ("shopee", "Shopee", r"shop\s*ee|\bsh0pee\b"),
    ("lazada", "Lazada", r"laz\s*ada"),
]

PROMISE_RULES = [
    ("chua_benh", "hứa chữa bệnh", r"chua\s*(khoi\s*)?benh|het\s*benh|khoi\s*benh"),
    ("dam_bao_giau", "đảm bảo giàu có / tiền về", r"(dam\s*bao|chac\s*chan|cam\s*ket|100\s*%)\s*.{0,20}(giau|tien\s*ve|phat\s*tai|trung\s*so)"),
    ("cuu_hon_nhan", "cứu hôn nhân", r"cuu\s*(van\s*)?hon\s*nhan|giu\s*chong\s*chac\s*chan"),
    ("chieu_tai", "hứa chiêu tài", r"chieu\s*tai"),
    ("hu_doa", "hù dọa (đại họa, xui tận mạng...)", r"dai\s*hoa|tan\s*mang|chet\s*choc|tai\s*hoa\s*ap\s*toi|xui\s*xeo\s*ca\s*doi"),
]

ALLOWED_CTA = ["bấm giỏ hàng góc trái", "để lại ngày sinh dưới bình luận để Cô Kim giải mã"]


def normalize(text: str) -> str:
    """Bỏ dấu tiếng Việt, chữ thường, gộp ký tự né kiểm duyệt (l.i.n.k, b i o)."""
    t = (text or "").replace("đ", "d").replace("Đ", "D")
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()
    # gộp chữ đơn bị tách bởi dấu chấm/gạch/khoảng trắng: "l.i.n.k" -> "link", "b i o" -> "bio"
    t = re.sub(r"\b(?:[a-z][.\-_* ]){2,}[a-z]\b", lambda m: re.sub(r"[.\-_* ]", "", m.group(0)), t)
    return t


def _scan(text: str, rules, norm: str | None = None) -> list[dict]:
    norm = normalize(text) if norm is None else norm
    found = []
    for code, label, pattern in rules:
        m = re.search(pattern, norm)
        if m:
            found.append({"code": code, "label": label, "match": m.group(0).strip()})
    return found


def check(text: str, has_cart: bool | None = True) -> dict:
    """Kiểm tra 1 đoạn nội dung. has_cart=None nghĩa là chưa biết video có giỏ hàng không."""
    norm = normalize(text)
    offsite = _scan(text, OFFSITE_RULES, norm)
    promise = _scan(text, PROMISE_RULES, norm)
    if offsite and has_cart:
        level = "violation"
    elif offsite and has_cart is None:
        level = "violation_if_cart"
    elif offsite or promise:
        level = "warning"
    else:
        level = "ok"
    return {"level": level, "offsite": offsite, "promise": promise}


LEVEL_LABELS = {
    "violation": "VI PHẠM (video có giỏ hàng)",
    "violation_if_cart": "Vi phạm nếu video có giỏ hàng",
    "warning": "Cần xem lại",
    "ok": "Sạch",
}
