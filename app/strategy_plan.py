"""Tách bảng "Lịch đăng đề xuất 7 ngày" trong chiến lược (Markdown) → từng dòng có thể tạo gói nhanh.

- Đoán Loại video: cột "Loại" nếu có; không thì theo từ khoá (giỏ hàng → 2; lá số/Bát Tự/tuổi/trả lời bình luận → 1; còn lại 3).
- Soát nhanh rủi ro trước khi tạo gói: video giỏ hàng kèm CTA/hashtag bói toán (B.4.1), từ "thỉnh", hứa hẹn (B.4),
  quá 2 video giỏ hàng/tuần, video giỏ hàng chiếm khung 11:00–12:00 (khung kéo follow tốt nhất).
- prefill(): điền sẵn form Yêu cầu Gemini; anh Nhơn xem lại rồi bấm gửi.
"""
import re

from . import compliance

CART_RX = re.compile(r"có giỏ hàng|giỏ hàng|gói 16|sp-[a-z]{3}-\d+|khăn lau|ấm tử sa|đèn đá muối", re.I)
FORTUNE_RX = re.compile(r"lá số|bát tự|nhật chủ|nhật can|can chi|tứ trụ|dụng thần|trả lời bình luận|giải mã (?:lá số|tuổi|ngày sinh)|"
                        r"tuổi\s|\b(?:giáp|ất|bính|đinh|mậu|kỷ|canh|tân|nhâm|quý)\s+(?:tý|sửu|dần|mão|thìn|tỵ|ngọ|mùi|thân|dậu|tuất|hợi)\b|"
                        r"\b19[5-9]\d\b|\b20[0-2]\d\b", re.I)
FORTUNE_TAG_RX = re.compile(r"#(?:battu|tutru|dungthan|tuvi\w*|phongthuy|xemboi|laso)", re.I)
GROUP_HINTS = [(4, r"trả lời bình luận"), (2, r"tuổi|con giáp|19[5-9]\d|20[0-2]\d"),
               (3, r"nhân duyên|gia đạo|vợ chồng|hôn nhân|mẫu tử"), (6, r"kiến thức|nhập môn|dụng thần"),
               (1, r"lá số|nhật chủ|nhật can|nuôi dạy con|em bé|đứa trẻ")]


def _clean(c: str) -> str:
    c = c.replace("\\", "")
    c = re.sub(r"\*+", "", c)
    c = re.sub(r"\s+", " ", c)
    return c.strip().strip('"“”').strip()


def _cells(line: str) -> list[str]:
    line = line.strip()
    if not line.startswith("|"):
        return []
    return [_clean(x) for x in line.strip("|").split("|")]


def parse_schedule(md: str) -> list[dict]:
    """Trả về [{ngay, gio, chu_de, dinh_dang, do_dai, hook, hashtag, loai, warnings}]."""
    if not md:
        return []
    m = re.search(r"^#{1,4}[^\n]*Lịch đăng[^\n]*$", md, re.M | re.I)
    if not m:
        return []
    body = md[m.end():]
    nxt = re.search(r"^#{1,4}\s", body, re.M)
    body = body[:nxt.start()] if nxt else body
    rows, header = [], None
    for line in body.splitlines():
        cells = _cells(line)
        if not cells or all(re.fullmatch(r":?-{2,}:?|", c) for c in cells):
            continue
        low = [c.lower() for c in cells]
        if header is None and any(c.startswith("ngày") for c in low) and any("giờ" in c for c in low):
            header = low
            continue
        if header is None or len(cells) < 3:
            continue

        def col(*names):
            for i, h in enumerate(header):
                if any(h.startswith(n) for n in names) and i < len(cells):
                    return cells[i]
            return ""

        r = {"ngay": col("ngày"), "gio": col("giờ"), "chu_de": col("chủ đề", "ý tưởng"), "dinh_dang": col("định dạng"),
             "do_dai": col("độ dài"), "hook": col("hook"), "hashtag": col("hashtag"), "loai_col": col("loại")}
        if not r["chu_de"]:
            continue
        rows.append(_classify(r))
    _week_checks(rows)
    for i, r in enumerate(rows):
        r["idx"] = i
    return rows


def _classify(r: dict) -> dict:
    text = f"{r['chu_de']} {r['hook']}"
    lc = r.pop("loai_col", "")
    m = re.search(r"[123]", lc)
    if m:
        loai = int(m.group(0))
    elif CART_RX.search(text):
        loai = 2
    elif FORTUNE_RX.search(text):
        loai = 1
    else:
        loai = 3
    r["loai"] = loai
    r["nhom"] = 5 if loai == 3 else next((g for g, rx in GROUP_HINTS if re.search(rx, text, re.I)), 0)
    w = []
    if loai == 2:
        if FORTUNE_RX.search(text):
            w.append("Video giỏ hàng nhắc lá số/tuổi/Bát Tự → vi phạm B.4.1 (không nối lá số với sản phẩm).")
        if FORTUNE_TAG_RX.search(r["hashtag"]):
            w.append(f"Video giỏ hàng có hashtag bói toán ({', '.join(FORTUNE_TAG_RX.findall(r['hashtag']))}) → bỏ.")
        if re.search(r"\b(?:11|12):\d\d", r["gio"]) and re.match(r"11", r["gio"]):
            w.append("Video giỏ hàng chiếm khung 11:00 (khung kéo follow tốt nhất) → nên dời 12:00.")
    if loai == 1 and re.match(r"\s*1[01]:", r["gio"]):
        w.append("Khung 11:00 nên dành cho Loại 3 (trà sáng kéo tim/follow, tim/view 11–14%); lá số nên dời 19:00.")
    if loai == 3 and FORTUNE_RX.search(text):
        w.append("Loại 3 (được quảng cáo) không được nhắc lá số/tuổi.")
    if re.search(r"\bthỉnh\b", text, re.I):
        w.append("Từ “thỉnh” coi sản phẩm như vật tâm linh → dùng “xem khăn”/“chọn khăn”.")
    chk = compliance.check(f"{r['hook']} {r['chu_de']}", loai == 2)
    for x in chk.get("promise", []) + chk.get("offsite", []):
        w.append(f"Cụm “{x['match']}”: {x['label']}.")
    r["warnings"] = w
    return r


def _week_checks(rows: list[dict]) -> None:
    carts = [r for r in rows if r["loai"] == 2]
    if len(carts) > 2:
        for r in carts[2:]:
            r["warnings"].append(f"Tuần này đã có {len(carts)} video giỏ hàng (kế hoạch chốt: tối đa 2/tuần) → đổi sang Loại 3.")


def prefill(r: dict) -> dict:
    """Giá trị điền sẵn cho form Yêu cầu Gemini."""
    parts = [f"Theo lịch chiến lược: {r['ngay']} lúc {r['gio']}. Chủ đề: {r['chu_de']}."]
    if r.get("hook"):
        parts.append(f"Hook gợi ý (3 giây đầu): \"{r['hook']}\".")
    if r.get("dinh_dang") or r.get("do_dai"):
        parts.append(f"Định dạng: {r.get('dinh_dang') or '—'}, độ dài {r.get('do_dai') or '32s'} (4 cảnh × 8 giây).")
    tags = FORTUNE_TAG_RX.sub("", r.get("hashtag") or "") if r["loai"] == 2 else (r.get("hashtag") or "")
    if tags.strip():
        parts.append(f"Hashtag gợi ý: {' '.join(tags.split())}.")
    if r.get("nhom"):
        parts.append(f"Nhóm nội dung {r['nhom']}.")
    if r["loai"] == 1 and r.get("nhom") == 4:
        parts.append("Trả lời một bình luận thật xin xem lá số (không ghi tên người hỏi); kết bằng “để lại ngày sinh dưới bình luận để Cô Kim giải mã”.")
    if r["loai"] == 2:
        parts.append("Video giỏ hàng: KHÔNG nhắc lá số, tuổi, Bát Tự; CTA duy nhất “bấm giỏ hàng góc trái”.")
    if r["warnings"]:
        parts.append("Lưu ý khi viết: " + " ".join(r["warnings"]))
    goal = {1: "comment", 2: "sale", 3: "follow"}[r["loai"]]
    title = re.sub(r"^\[?Có giỏ hàng\]?\s*", "", r["chu_de"], flags=re.I)
    return {"brief": " ".join(parts), "title": title[:60], "loai": r["loai"], "goal": goal, "ads": False,
            "publish": f"{r['ngay']}, {r['gio']}"}
