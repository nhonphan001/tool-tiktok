"""Gemini API của TikTok Manager tự soạn kịch bản theo Bộ quy tắc (settings.script_rules) rồi tự kiểm, tự sửa.

Mục tiêu: giảm việc Claude phải soạn tay. Luồng:
1. Lá số / dữ kiện năm sinh do bộ battu tính (không để AI tự tính can chi).
2. Gemini API soạn: N câu thoại, chữ hook, chữ chương, caption, bình luận ghim, gợi ý hành động từng cảnh (JSON).
3. Tool chạy packages.check(); còn lỗi/cảnh báo về hiệu suất, nhịp, độ dài, CTA, B.1/B.4 → gửi lại cho Gemini sửa (tối đa 2 lần).
4. Kết quả lưu trong opts["kich_ban"] của yêu cầu; thư SANXUAT kèm mục "Lời thoại SOẠN SẴN — GIỮ NGUYÊN VĂN".
"""
import json
import re

from . import battu, packages
from .config import settings

FIX_RULES = {"Hiệu suất", "Nhịp cảnh", "Độ dài", "CTA", "B.1", "B.4", "B.4.1", "Hứa hẹn", "Số cảnh", "Quảng cáo", "Prompt"}
MAX_FIX = 2

SYSTEM = """Bạn là biên kịch của kênh TikTok "Tiệm Trà Giải Mã" (@tiemtragiaima), nhân vật Cô Kim (25–30 tuổi, giọng miền Nam,
xưng "Cô Kim"). Viết kịch bản đúng TỪNG ĐIỀU trong BỘ QUY TẮC KỊCH BẢN bên dưới. Lời thoại tự nhiên như đang nói, câu ngắn,
không liệt kê thuật ngữ khô; mỗi câu thuật ngữ Bát Tự đi kèm một hình ảnh dễ hiểu. Đếm âm tiết theo cách đọc (năm viết bằng chữ).
Chỉ dùng dữ kiện lá số được cung cấp. Trả về đúng JSON theo khuôn, không thêm chữ nào ngoài JSON."""

SCHEMA = """{"tieu_de": "...", "canh": ["lời cảnh 1", "..."], "chu_tren_hinh": "hook ≤70 ký tự",
 "chu_chuong": {"2": "1. Tính cách", "...": "..."}, "caption": "≤250 ký tự, có hashtag",
 "binh_luan_ghim": "1 câu hỏi dễ trả lời", "goi_y_hinh": ["hành động cảnh 1", "..."]}"""


def year_facts(year: int) -> list[str]:
    """Dữ kiện theo NĂM SINH (video lá số theo năm, không có ngày sinh cụ thể)."""
    g = battu.ganzhi(year - 4)
    nm = battu.name(g)
    can = battu.CAN[g["can"]]
    out = [f"Năm sinh {year}: {nm} — can {can} ({battu.NHAT_CHU_TA.get(can, '')}), chi {battu.CHI[g['chi']]}; "
           f"nạp âm {battu.nap_am(g)}."]
    for y in (year, year + 1):
        jd = battu.find_sun_longitude(315, battu.instant_jd(1, 2, y, 0, 0, 7), 1)
        j = jd + 7 / 24 + 0.5
        d = int(j)
        dd, mm, yy = battu.jd_to_date(d)
        h = (j - d) * 24
        out.append(f"Lập Xuân {yy}: {dd:02d}/{mm:02d}/{yy} khoảng {int(h):02d}:{int((h % 1) * 60):02d} (giờ VN).")
    prev = battu.name(battu.ganzhi(year - 5))
    out.append(f"Sinh trước Lập Xuân {year} thì Bát Tự tính là {prev}; sinh tháng 1/{year + 1} (trước Lập Xuân {year + 1}) "
               f"vẫn là {nm}.")
    for y in (2026, 2027):
        yp = battu.ganzhi(y - 4)
        rel = "; ".join(q["ten"] for q in battu.quan_he([g, yp])) or "không có hợp/xung/hình/hại trực tiếp"
        out.append(f"Năm {y} {battu.name(yp)} ({battu.nap_am(yp)}): {rel}; can {battu.CAN[yp['can']]} với can năm sinh "
                   f"{can} là {battu.thap_than(g['can'], yp['can'])}.")
    return out


def _year_from(text: str) -> int | None:
    m = re.search(r"\b(19[4-9]\d|200\d)\b", text or "")
    return int(m.group(1)) if m else None


def facts_for(opts: dict, brief: str, title: str) -> tuple[list[str], str]:
    """(dữ kiện, mô tả nguồn). Loại 1 có ngày sinh → lá số đầy đủ; chỉ có năm → dữ kiện theo năm."""
    if int(opts.get("loai") or 3) != 1:
        return [], ""
    b = opts.get("birth") or {}
    if b.get("dd") and b.get("mm") and b.get("yy"):
        chart, _err = packages.chart_of({"birth": b})
        if chart:
            from . import customers

            fs = [f"Lá số: {battu.mo_ta_ngan(chart)}; Hỷ thần {chart['hy_than']}; Kỵ thần {', '.join(chart['ky_than'])}.",
                  f"Quan hệ trong lá số: {', '.join(chart['quan_he']) or 'không'}."]
            fs += customers.year_facts(chart)
            fs += [f"Cảnh báo lá số: {w}" for w in chart.get("canh_bao") or []]
            return fs, "lá số đầy đủ"
    y = _year_from(f"{title} {brief}")
    return (year_facts(y), f"theo năm sinh {y}") if y else ([], "")


def _prompt(req: dict, facts: list[str], src: str, issues: list[str] | None = None, prev: dict | None = None) -> str:
    o = req["opts"]
    loai = int(o.get("loai") or 3)
    n = int(o.get("scenes") or 4)
    lo, hi = packages.syllable_range()
    parts = [f"VIẾT KỊCH BẢN GÓI {req['goi']} — {req['title']}",
             f"Loại {loai} ({packages.LOAI.get(loai, '')}), {n} cảnh × {packages.clip_seconds()} giây, mỗi cảnh {lo}–{hi} âm tiết"
             + (f", tổng ≥ 232 âm tiết (thành phẩm > 61 giây)" if n >= 6 else "") + ".",
             f"Đăng: {o.get('publish') or 'chưa rõ'}. Yêu cầu của anh Nhơn: {req['brief'].strip()}"]
    if o.get("o_phep_thu"):
        parts.append(f"Ô phép thử: {o['o_phep_thu']}.")
    if facts:
        parts.append(f"DỮ KIỆN LÁ SỐ ({src}, TikTok Manager tính — dùng đúng, không tự tính thêm):\n- " + "\n- ".join(facts))
    if issues and prev:
        parts.append("BẢN TRƯỚC:\n" + json.dumps(prev, ensure_ascii=False) +
                     "\nBỘ KIỂM TRA BÁO CÁC LỖI SAU — sửa hết, giữ ý hay của bản trước:\n- " + "\n- ".join(issues))
    parts.append("KHUÔN JSON:\n" + SCHEMA)
    return "\n\n".join(parts)


def _parse(out: str) -> dict:
    try:
        d = json.loads(out[out.find("{"): out.rfind("}") + 1])
    except ValueError:
        return {}
    d["canh"] = [str(x).strip() for x in d.get("canh") or [] if str(x).strip()]
    d["chu_chuong"] = {str(k): str(v) for k, v in (d.get("chu_chuong") or {}).items()} if isinstance(d.get("chu_chuong"), dict) else {}
    return d


def _check(req: dict, d: dict) -> tuple[list[str], dict]:
    o = req["opts"]
    p = {"goi": req["goi"], "loai": int(o.get("loai") or 3), "on_screen": d.get("chu_tren_hinh") or "",
         "caption": d.get("caption") or "", "pinned": d.get("binh_luan_ghim") or "", "birth": o.get("birth") or {}}
    for i, s in enumerate(d.get("canh") or [], 1):
        p[f"scene{i}"] = s
    chk = packages.check(p)
    n = int(o.get("scenes") or 4)
    issues = [f"[{i['rule']}] {i['msg']}" for i in chk["items"] if i["level"] == "error" or i["rule"] in FIX_RULES]
    if len(d.get("canh") or []) != n:
        issues.append(f"[Số cảnh] Cần đúng {n} câu thoại, đang có {len(d.get('canh') or [])}.")
    return issues, chk


def draft(req: dict, call=None) -> dict:
    """Soạn + tự sửa. Trả về kich_ban (đã kèm check_note, cost_usd, tries)."""
    from . import strategy

    call = call or strategy.call_gemini
    o = req["opts"]
    facts, src = facts_for(o, req["brief"], req["title"])
    system = SYSTEM + "\n\n" + (settings.script_rules or "")
    cost, d, issues = 0.0, {}, []
    for t in range(MAX_FIX + 1):
        out, usage = call(_prompt(req, facts, src, issues if t else None, d if t else None), system=system, json_mode=True)
        strategy.record_usage("script", req.get("id"), usage)
        cost += float(usage.get("cost_usd") or 0)
        nd = _parse(out)
        if nd.get("canh"):
            d = nd
        issues, chk = _check(req, d)
        if not issues:
            break
    note = ("0 lỗi, 0 cảnh báo cần sửa" if not issues else f"còn {len(issues)} điểm: " + "; ".join(issues)[:400])
    return {**d, "check_note": note, "issues": issues, "cost_usd": round(cost, 5), "tries": t + 1, "facts_src": src}


def draft_and_store(rid: int) -> str:
    """Chạy nền: soạn kịch bản cho yêu cầu rid, lưu vào opts, dựng lại thư (chưa gửi)."""
    from . import db, gemini_requests

    req = gemini_requests.get(rid)
    if not req:
        return "Không tìm thấy yêu cầu"
    kb = draft(req)
    if not kb.get("canh"):
        return f"Gói {req['goi']}: Gemini API chưa trả kịch bản hợp lệ"
    opts = {**req["opts"], "kich_ban": kb}
    letter = gemini_requests.build_letter({**req, "opts": opts})
    with db.tx() as c:
        c.execute("UPDATE gemini_requests SET opts_json=?, letter_md=? WHERE id=?",
                  (json.dumps(opts, ensure_ascii=False), letter, rid))
    return (f"Gói {req['goi']}: đã soạn kịch bản ({kb['tries']} lượt, {kb['check_note']}, ≈ ${kb['cost_usd']:.4f})")
