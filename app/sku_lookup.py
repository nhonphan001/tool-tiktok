"""Dán link TikTok Shop -> tự điền form "Thêm SKU mới" (người dùng duyệt rồi mới ghi vào bảng).

1. Mở link rút gọn (chỉ tên miền tiktok.com), lấy tên + ảnh + mã sản phẩm từ tham số og_info
   của địa chỉ chuyển hướng (trang sản phẩm chặn máy chủ nên không đọc được giá).
2. Gemini viết các ô còn lại theo quy tắc B.4; nếu còn từ cấm thì cho Gemini sửa lại 1 lần.
3. Tự cấp mã kế tiếp (SP-<NHÓM>-<số>).
"""
import json
import re
import urllib.parse as up

import httpx

from . import products, strategy
from .compliance import normalize
from .config import settings

ALLOWED_HOSTS = re.compile(r"(^|\.)tiktok\.com$", re.I)
GROUP_OF = {"Kim": "KIM", "Mộc": "MOC", "Thủy": "THUY", "Hỏa": "HOA", "Thổ": "THO"}
UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36"

SYSTEM = """Bạn điền 1 dòng SKU cho bảng quản trị sản phẩm affiliate của kênh TikTok "Tiệm Trà Giải Mã – Cô Kim".
Chỉ trả về 1 đối tượng JSON với các khóa:
- "element": một trong "Kim","Mộc","Thủy","Hỏa","Thổ" nếu sản phẩm rõ ràng thuộc nhóm vật phẩm ngũ hành của kênh (đá, vòng, trầm, ấm trà…), ngược lại "" (hàng gia dụng, hàng mùa vụ).
- "group": nếu element rỗng, mã nhóm 3–5 chữ in hoa không dấu (vd "TET" cho hàng Tết, "GIA" cho gia dụng); nếu có element thì để "".
- "video_name": tên ngắn 3–7 từ để đọc trong lời thoại, viết hoa chữ cái đầu và tên riêng, bỏ ngoặc, bỏ số lượng gói, bỏ chữ quảng cáo.
- "category": phân loại mô tả ĐÚNG bản chất hàng (vd "Khăn lau vệ sinh bàn thờ", "Vòng tay đá tự nhiên").
- "material": chất liệu / quy cách lấy từ tên (số tờ, số gói, kích thước…).
- "benefit": 1 câu công dụng thực tế (làm sạch, mùi hương, dùng để làm gì, làm quà).
- "cta": 1–2 câu lời thoại mô tả để đọc trong video, kết thúc đúng bằng "Bấm giỏ hàng góc trái để xem chi tiết."
QUY TẮC BẮT BUỘC (TikTok đã từ chối quảng cáo vì vi phạm):
- Không hứa tâm linh/may mắn: không "may mắn, tài lộc, rước lộc, đón lộc, bình an, phù hộ, hộ mệnh, hộ thân, bùa, trấn trạch, trừ tà, giải hạn, hóa giải, khai quang, chiêu tài, thần tài, linh khí, vượng khí".
- Không nối với lá số/mệnh: không "khuyết, thiếu hành, bổ sung năng lượng, hợp mệnh".
- Không nhắc link, bio, web, Zalo, Shopee, Lazada. Không hứa chữa bệnh, giàu có.
- Chỉ dùng thông tin có trong tên sản phẩm; không bịa giá, thành phần, xuất xứ."""


def _check_host(url: str) -> None:
    u = up.urlparse(url)
    if u.scheme not in ("http", "https") or not ALLOWED_HOSTS.search(u.hostname or ""):
        raise ValueError("Chỉ nhận link TikTok (vt.tiktok.com, www.tiktok.com, shop.tiktok.com…)")


def _from_url(url: str) -> dict:
    u = up.urlparse(url)
    q = up.parse_qs(u.query)
    out = {}
    m = re.search(r"/product/(\d{8,})", u.path)
    if m:
        out["product_id"] = m.group(1)
    if "og_info" in q:
        try:
            og = json.loads(q["og_info"][0])
            out["title"] = (og.get("title") or "").strip()
            out["image"] = og.get("image") or ""
        except ValueError:
            pass
    return out


def resolve(link: str) -> dict:
    """Theo dõi chuyển hướng (tối đa 6, chỉ trong tiktok.com) để lấy tên, ảnh, mã sản phẩm."""
    link = (link or "").strip()
    _check_host(link)
    url, info = link, {}
    with httpx.Client(timeout=20, follow_redirects=False, headers={"User-Agent": UA}) as c:
        for _ in range(6):
            info.update({k: v for k, v in _from_url(url).items() if v})
            if info.get("title"):
                break
            r = c.get(url)
            loc = r.headers.get("location")
            if r.is_redirect and loc:
                url = up.urljoin(url, loc)
                _check_host(url)
                continue
            m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', r.text or "")
            if m and "security" not in m.group(1).lower():
                info["title"] = m.group(1).strip()
            break
    if not info.get("title"):
        raise RuntimeError("Không đọc được tên sản phẩm từ link (TikTok chặn). Dán tên sản phẩm vào ô “Tên” rồi bấm Tự điền lại.")
    info["link"] = link
    return info


def next_code(group: str) -> str:
    group = re.sub(r"[^A-Z]", "", normalize(group).upper())[:6] or "MOI"
    nums = [int(m.group(1)) for code in products.by_code()
            if (m := re.fullmatch(rf"SP-{group}-(\d+)", code))]
    return f"SP-{group}-{(max(nums) + 1 if nums else 1):02d}"


def _heuristic(title: str) -> dict:
    name = re.sub(r"\[[^\]]*\]|\([^)]*\)", " ", title)
    name = re.sub(r"\b\d+\s*(gói|tờ|cái|chiếc|hộp|set)\b", " ", name, flags=re.I)
    name = re.sub(r"\b(hoặc|combo|freeship|sale|hot)\b", " ", name, flags=re.I)
    name = re.split(r"\s[-–|,]\s|\s(?:có|làm|giúp|dành|cho)\s", " ".join(name.split()), maxsplit=1, flags=re.I)[0]
    words = name.split()[:7]
    return {"element": "", "group": "MOI", "video_name": " ".join(words).strip(" -–"), "category": "", "material": "",
            "benefit": "", "cta": "Bấm giỏ hàng góc trái để xem chi tiết."}


def _ask_gemini(title: str, feedback: str = "") -> tuple[dict, dict]:
    prompt = f"Tên sản phẩm trên TikTok Shop:\n{title}"
    if feedback:
        prompt += f"\n\nLần trước bạn viết có từ cấm, hãy viết lại và tránh: {feedback}"
    text, usage = strategy.call_gemini(prompt, system=SYSTEM, json_mode=True)
    strategy.record_usage("sku_lookup", None, usage)
    try:
        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except ValueError:
        raise RuntimeError(f"Gemini trả về không phải JSON: {text[:160]}")
    return {k: str(data.get(k) or "").strip() for k in ("element", "group", "video_name", "category", "material",
                                                         "benefit", "cta")}, usage


def suggest(link: str = "", title: str = "") -> dict:
    """Trả về dữ liệu điền sẵn cho form Thêm SKU (chưa ghi gì vào bảng)."""
    info = {"link": link.strip()}
    if not title:
        info = resolve(link)
        title = info["title"]
    note, usage = [], None
    if settings.gemini_api_key:
        try:
            data, usage = _ask_gemini(title)
            _, errors, _ = products.validate_new({**data, "code": "SP-X-1", "name": title})
            bad = [e for e in errors if "từ cấm" in e]
            if bad:
                data, usage2 = _ask_gemini(title, "; ".join(bad))
                usage = {k: (usage.get(k, 0) + usage2.get(k, 0)) if isinstance(usage.get(k), (int, float)) else usage2.get(k)
                         for k in usage2}
        except Exception as e:  # noqa: BLE001 — Gemini lỗi thì vẫn điền phần cơ bản
            data = _heuristic(title)
            note.append(f"Gemini lỗi ({str(e)[:120]}), chỉ điền phần cơ bản")
    else:
        data = _heuristic(title)
        note.append("Chưa có GEMINI_API_KEY, chỉ điền phần cơ bản")
    elem = products.normalize_element(data.get("element", ""))
    elem = elem if elem in GROUP_OF else ""
    out = {
        "code": next_code(GROUP_OF[elem] if elem else (data.get("group") or "MOI")),
        "element": elem, "name": title, "video_name": data.get("video_name", ""),
        "category": data.get("category", ""), "material": data.get("material", ""),
        "benefit": data.get("benefit", ""), "cta": data.get("cta", ""),
        "link": info.get("link") or link, "status": "Đang Bật",
        "note": f"TikTok product_id {info['product_id']}" if info.get("product_id") else "",
        "_image": info.get("image", ""),
        "_auto": "Gemini" if usage else "cơ bản",
    }
    if usage:
        note.append(f"Gemini: {usage.get('total_tokens', 0)} token · ${usage.get('cost_usd', 0):.4f}")
    out["_note"] = " · ".join(note)
    return out
