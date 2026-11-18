"""Tách ngày giờ sinh từ bình luận "xin xem lá số" và lập lá số.

Bình luận chỉ được xử lý trong bộ nhớ, KHÔNG lưu vào cơ sở dữ liệu (ngày sinh của người xem là dữ liệu cá nhân).
"""
from __future__ import annotations

import re
from datetime import datetime

from . import battu

# Tên chi có dấu -> chỉ số; không dấu "ty" mơ hồ (Tý/Tỵ) nên xử lý riêng
CHI_DAU = {"tý": 0, "sửu": 1, "dần": 2, "mão": 3, "mẹo": 3, "thìn": 4, "tỵ": 5, "tị": 5, "ngọ": 6, "mùi": 7,
           "thân": 8, "dậu": 9, "tuất": 10, "hợi": 11}
CHI_KHONG_DAU = {"suu": 1, "dan": 2, "mao": 3, "meo": 3, "thin": 4, "ngo": 6, "mui": 7, "than": 8, "dau": 9,
                 "tuat": 10, "hoi": 11}

DATE_NUM = re.compile(r"(?<![\d/.\-])(\d{1,2})\s*[/\-.]\s*(\d{1,2})\s*[/\-.]\s*(\d{4}|\d{2})(?![\d/.\-])")
DATE_TXT = re.compile(r"(?:ngày|ngay|ng)\s*(\d{1,2})\s*(?:tháng|thang|th)\s*(\d{1,2})\s*(?:năm|nam|n)?\s*(\d{4}|\d{2})\b",
                      re.IGNORECASE)
YEAR_ONLY = re.compile(r"(?:sn|sinh năm|sinh nam|năm sinh|nam sinh|năm|nam|tuổi|tuoi)\s*(19\d{2}|20\d{2})\b", re.IGNORECASE)
TIME_HM = re.compile(r"(?<!\d)(\d{1,2})\s*(?::|h|g|giờ|gio)\s*(\d{2})(?:\s*(?:p|phút|phut))?(?!\d)", re.IGNORECASE)
TIME_H = re.compile(r"(?<![\d/.\-])(\d{1,2})\s*(?:h|g|giờ|gio)\b(?!\s*\d)", re.IGNORECASE)
GIO_CHI = re.compile(r"giờ\s+(tý|sửu|dần|mão|mẹo|thìn|tỵ|tị|ngọ|mùi|thân|dậu|tuất|hợi)\b", re.IGNORECASE)
GIO_CHI_KD = re.compile(r"gio\s+(ty|suu|dan|mao|meo|thin|ngo|mui|than|dau|tuat|hoi)\b", re.IGNORECASE)


def _year(y: str) -> int:
    v = int(y)
    if v < 100:
        cur = datetime.now().year % 100
        v = 2000 + v if v <= cur else 1900 + v
    return v


def _time(seg: str) -> tuple[int | None, int, str | None]:
    """Trả về (giờ, phút, ghi chú). Giờ None nếu không thấy."""
    low = seg.lower()
    m = GIO_CHI.search(low)
    if m:
        chi = CHI_DAU[m.group(1)]
        return battu.GIO_CHI_GIUA[chi], 0, f"giờ {m.group(1).capitalize()} → lấy giữa canh"
    m = GIO_CHI_KD.search(low)
    if m:
        w = m.group(1)
        if w == "ty":
            return None, 0, "ghi \"giờ ty\" không dấu: không rõ Tý hay Tỵ"
        return battu.GIO_CHI_GIUA[CHI_KHONG_DAU[w]], 0, f"giờ {w} → lấy giữa canh"
    h = mi = None
    m = TIME_HM.search(low)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
    else:
        m = TIME_H.search(low)
        if m:
            h, mi = int(m.group(1)), 0
    if h is None:
        return None, 0, None
    note = None
    if h <= 12:
        if re.search(r"\b(chiều|chieu|pm)\b", low) and h < 12:
            h += 12
            note = "buổi chiều → +12h"
        elif re.search(r"\b(tối|toi)\b", low) and 5 <= h < 12:
            h += 12
            note = "buổi tối → +12h"
        elif re.search(r"\b(trưa|trua)\b", low) and h <= 2:
            h += 12
            note = "buổi trưa → +12h"
        elif re.search(r"\b(đêm|dem)\b", low) and 9 <= h < 12:
            h += 12
            note = "ban đêm → +12h"
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        return None, 0, "giờ không hợp lệ"
    return h, mi, note


GENDER_RX = re.compile(
    r"\b(nữ|nu|con gái|con gai|bé gái|be gai|vợ|chị|em gái|nam|con trai|bé trai|be trai|chồng|anh)\b(?!\s*\d)",
    re.IGNORECASE)
FEMALE = {"nữ", "nu", "con gái", "con gai", "bé gái", "be gai", "vợ", "chị", "em gái"}


def _gender(seg: str, closest: str) -> str | None:
    """Từ chỉ giới tính gần ngày sinh nhất: closest='last' cho đoạn trước ngày, 'first' cho đoạn sau."""
    ms = list(GENDER_RX.finditer(seg.lower()))
    if not ms:
        return None
    w = (ms[-1] if closest == "last" else ms[0]).group(1)
    return "nu" if w in FEMALE else "nam"


def _lunar(seg: str) -> tuple[bool, bool]:
    low = seg.lower()
    lunar = bool(re.search(r"âm lịch|am lich|\bâl\b|\bal\b|\(âm\)|\bâm\b", low)) and \
        not re.search(r"dương lịch|duong lich|\bdl\b", low)
    leap = bool(re.search(r"nhuận|nhuan", low))
    return lunar, leap


def parse_line(line: str) -> list[dict]:
    """Tìm các ngày sinh trong 1 bình luận. Mỗi kết quả kèm đoạn ngữ cảnh để đọc giờ/giới tính/âm lịch."""
    found = []
    for rx, kind in ((DATE_TXT, "txt"), (DATE_NUM, "num")):
        for m in rx.finditer(line):
            if any(m.start() < f["end"] and f["start"] < m.end() for f in found):
                continue
            found.append({"start": m.start(), "end": m.end(), "d": int(m.group(1)), "m": int(m.group(2)),
                          "y": _year(m.group(3)), "raw": m.group(0)})
    found.sort(key=lambda f: f["start"])
    out = []
    for i, f in enumerate(found):
        prev_end = found[i - 1]["end"] if i else 0
        next_start = found[i + 1]["start"] if i + 1 < len(found) else len(line)
        before = line[prev_end:f["start"]]
        after = line[f["end"]:next_start]
        lunar, leap = _lunar(after) if _lunar(after)[0] else _lunar(before)
        h, mi, tnote = _time(after)
        if h is None and not tnote:
            h, mi, tnote = _time(before)
        gioi = _gender(before, "last") or _gender(after, "first")
        out.append({"raw": f["raw"].strip(), "d": f["d"], "m": f["m"], "y": f["y"], "lunar": lunar, "leap": leap,
                    "h": h, "mi": mi, "time_note": tnote, "gioi": gioi})
    if not out:
        for m in YEAR_ONLY.finditer(line):
            out.append({"raw": m.group(0), "year_only": int(m.group(1))})
    return out


def analyze(text: str, max_lines: int = 200) -> list[dict]:
    """Phân tích nhiều bình luận (mỗi dòng 1 bình luận). Không lưu gì."""
    results = []
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()][:max_lines]
    for no, line in enumerate(lines, 1):
        items = parse_line(line)
        if not items:
            results.append({"line": no, "comment": line[:160], "error": "Không thấy ngày sinh đầy đủ (ngày/tháng/năm)"})
            continue
        for it in items:
            row = {"line": no, "comment": line[:160], **it}
            if "year_only" in it:
                row["error"] = f"Chỉ có năm sinh {it['year_only']}: cần thêm ngày, tháng (và giờ) để lập tứ trụ"
                results.append(row)
                continue
            try:
                row["chart"] = battu.lap_la_so(it["d"], it["m"], it["y"], it["h"], it["mi"], it["gioi"],
                                               "am" if it["lunar"] else "duong", it["leap"])
            except ValueError as e:
                row["error"] = str(e)
            results.append(row)
    return results
