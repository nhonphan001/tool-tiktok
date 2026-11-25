"""Khách hàng thân thiết + công cụ soạn trả lời (bình luận công khai / tin nhắn riêng).

- Khách chỉ được lưu khi anh Nhơn bấm "Lưu khách" (dữ liệu cá nhân: ngày sinh). Không đồng bộ lên Drive, không gửi cho
  Gemini/Claude trong báo cáo, không có trong bản tóm tắt. Có nút xoá khách (xoá cả lịch sử).
- Lá số do bộ battu của tool tính. Màu sắc lấy theo Dụng thần + Hỷ thần (màu hợp) và Kỵ thần (màu nên dùng ít).
- Mẫu trả lời luôn có sẵn (không tốn token). Bấm "Viết bằng AI" thì Gemini viết lại theo tin nhắn, có kiểm tra tuân thủ.
- Khi gửi AI: tin nhắn đã ẩn tên (comment_reply.anonymize), không gửi tên/nick khách.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from . import battu, compliance, db

VN = timezone(timedelta(hours=7))
TIERS = {"moi": "Mới", "quen": "Quen", "than_thiet": "Thân thiết"}
CHANNELS = {"binh_luan": "Bình luận", "tin_nhan": "Tin nhắn riêng"}
HANH_MAU = {"Mộc": "xanh lá, xanh lục", "Hỏa": "đỏ, hồng, cam, tím", "Thổ": "vàng đất, nâu, be",
            "Kim": "trắng, xám, bạc, ánh kim", "Thủy": "đen, xanh dương đậm, xanh navy"}
YEAR_NEXT = 2027  # năm Đinh Mùi
THAN_THIET_AFTER = 3  # ≥ 3 lần trao đổi → tự lên "Thân thiết"


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, alias TEXT, tiktok TEXT DEFAULT '', gioi TEXT DEFAULT '',
            dd INTEGER, mm INTEGER, yy INTEGER, t TEXT DEFAULT '', lich TEXT DEFAULT 'duong', nhuan INTEGER DEFAULT 0,
            tier TEXT DEFAULT 'moi', tags TEXT DEFAULT '', note TEXT DEFAULT '', created_at TEXT, updated_at TEXT,
            last_contact TEXT DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS customer_msgs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER, at TEXT, channel TEXT, direction TEXT,
            text TEXT, goi TEXT DEFAULT '')""")


# --------------------------------------------------------------------------- lá số + dữ kiện
def chart(c: dict) -> dict | None:
    if not (c.get("dd") and c.get("mm") and c.get("yy")):
        return None
    t = (c.get("t") or "").strip()
    try:
        h, mi = (int(t.split(":")[0]), int(t.split(":")[1])) if t else (None, 0)
        return battu.lap_la_so(int(c["dd"]), int(c["mm"]), int(c["yy"]), h, mi, c.get("gioi") or None,
                               c.get("lich") or "duong", bool(c.get("nhuan")))
    except (ValueError, IndexError):
        return None


def colors(ch: dict) -> dict:
    hop = [ch["dung_than"], ch["hy_than"]]
    it = [k for k in ch.get("ky_than") or [] if k not in hop]
    return {"hop": [(h, HANH_MAU[h]) for h in hop], "it": [(h, HANH_MAU[h]) for h in it],
            "sat_nguong": any("sát ngưỡng" in w for w in ch.get("canh_bao") or [])}


def _p(name: str) -> dict:
    can, chi = name.split(" ")
    return {"can": battu.CAN.index(can), "chi": battu.CHI.index(chi)}


def year_facts(ch: dict, year: int = YEAR_NEXT) -> list[str]:
    """Dữ kiện tool tính cho năm tới: Thập thần của can năm, hợp/xung/hình/hại với từng trụ, đại vận đang/sắp đi."""
    yp = battu.ganzhi(year - 4)
    yname = battu.name(yp)
    nc = battu.CAN.index(ch["nhat_chu"])
    out = [f"Năm {year} là {yname}; can {battu.CAN[yp['can']]} với Nhật chủ {ch['nhat_chu']} là "
           f"{battu.thap_than(nc, yp['can'])}."]
    hanh_can = battu.HANH[battu.CAN_HANH[yp["can"]]]
    if hanh_can == ch["dung_than"] or hanh_can == ch["hy_than"]:
        out.append(f"Hành của can năm ({hanh_can}) là {'Dụng' if hanh_can == ch['dung_than'] else 'Hỷ'} thần: năm được tiếp sức.")
    elif hanh_can in (ch.get("ky_than") or []):
        out.append(f"Hành của can năm ({hanh_can}) là Kỵ thần: năm dễ hao sức hơn.")
    for i, nm in enumerate(ch["tru"]):
        if not nm:
            continue
        np_ = _p(nm)
        for q in battu.quan_he([np_, yp]):
            out.append(f"Trụ {battu.TEN_VT[i]} ({nm}) gặp năm {yname}: {q['ten']}.")
        for grp in battu.TAM_HOP:  # bán tam hợp: 2 trong 3 chi của một cục (quan_he chỉ báo lục hợp / tam hợp đủ)
            if np_["chi"] != yp["chi"] and np_["chi"] in grp[:3] and yp["chi"] in grp[:3]:
                out.append(f"Trụ {battu.TEN_VT[i]} ({nm}) gặp năm {yname}: {battu.CHI[np_['chi']]} – {battu.CHI[yp['chi']]} "
                           f"bán hợp {battu.HANH[grp[3]]}"
                           + (" (đúng Dụng thần)." if battu.HANH[grp[3]] == ch["dung_than"] else "."))
    for v in ch.get("dai_van") or []:
        if v["nam"] <= year < v["nam"] + 10:
            out.append(f"Đại vận năm {year}: {v['tru']} (từ khoảng năm {v['nam']}, tuổi {v['tu_tuoi']}).")
        elif year < v["nam"] <= year + 1:
            out.append(f"Sắp đổi đại vận: {v['tru']} từ khoảng năm {v['nam']}.")
    return out


# --------------------------------------------------------------------------- mẫu trả lời (không tốn token)
def _xung(c: dict) -> str:
    g = (c.get("gioi") or "").lower()
    return {"nu": "chị", "nam": "anh"}.get(g, "mình")


def templates(message: str, c: dict, ch: dict | None) -> dict:
    x = _xung(c)
    msg = (message or "").lower()
    asks_health = bool(re.search(r"sức\s*khỏe|bệnh|đau|xương|khớp|mệt|ốm", msg))
    if not ch:
        public = (f"Cảm ơn {x} đã tin Cô Kim. {x.capitalize()} để lại ngày giờ sinh dương lịch (giờ, ngày, tháng, năm) để Cô Kim "
                  "giải mã kỹ hơn nha.")
        return {"public": public[:150], "private": public, "facts": []}
    yr = battu.name(battu.ganzhi(YEAR_NEXT - 4))
    public = (f"Thương {x} nhiều. Năm {yr} {YEAR_NEXT} Cô Kim thấy có điểm tiếp sức cho {x}. Cô Kim nhắn riêng chi tiết "
              f"cho {x} trong hộp thư nha.")
    if asks_health:
        public = (f"Thương {x} nhiều. Chuyện sức khỏe {x} đi khám bác sĩ cho kỹ nha. Phần lá số năm {YEAR_NEXT}, "
                  f"Cô Kim nhắn riêng cho {x} trong hộp thư nha.")
    facts = year_facts(ch)
    col = colors(ch)
    lines = [f"Cô Kim chào {x}. Cô Kim đọc tin nhắn mà thương {x} lắm.",
             f"Lá số của {x}: {ch['tu_tru']}, Nhật chủ {ch['nhat_chu']} ({ch['nhat_chu_ta']}), {ch['trang_thai'].lower()}."]
    lines.append(f"Năm {yr} {YEAR_NEXT} (dữ kiện tool tính, anh Nhơn diễn giải lại cho mềm trước khi gửi):")
    lines += [f"- {f}" for f in facts]
    if asks_health:
        lines.append(f"Chuyện sức khỏe thì Cô Kim không xem bệnh được, {x} đi khám bác sĩ cho kỹ nha. Lá số chỉ "
                     f"nhắc {x} năm tới phải chừa thời gian nghỉ ngơi, đừng ôm hết việc một mình.")
    # màu sắc luôn có trong tin nhắn riêng (khách hay hỏi)
    hop = "; ".join(f"{m} (hành {h})" for h, m in col["hop"])
    it = "; ".join(f"{m} (hành {h})" for h, m in col["it"])
    lines.append(f"Về màu sắc: màu hợp với {x} là {hop}. Màu nên dùng ít hơn: {it}."
                     + (" Lá số của " + x + " ở sát ngưỡng vượng nhược nên đây là hướng gợi ý, không cần kiêng tuyệt đối."
                        if col["sat_nguong"] else " Đây là hướng gợi ý cho dễ chịu, không phải kiêng tuyệt đối."))
    lines.append(f"Cô Kim chúc {x} giữ sức, nhẹ lòng. Có gì {x} cứ nhắn Cô Kim nha.")
    return {"public": public[:150], "private": "\n".join(lines), "facts": facts}


# --------------------------------------------------------------------------- AI
AI_SYSTEM = """Bạn là Cô Kim của kênh TikTok "Tiệm Trà Giải Mã": người pha trà, giải mã Bát Tự nhẹ nhàng, giọng miền Nam ấm,
xưng "Cô Kim", gọi khách theo cách khách xưng hô (chị/anh/con). Viết 2 bản trả lời cho tin nhắn của khách:

1. "binh_luan": trả lời BÌNH LUẬN CÔNG KHAI, tối đa 150 ký tự. Không lặp ngày sinh, không nêu chi tiết sức khỏe hay
   chuyện riêng của khách, không nêu màu sắc. Cảm ơn + 1 ý ấm áp + hẹn "Cô Kim nhắn riêng cho chị trong hộp thư nha".
2. "tin_nhan": TIN NHẮN RIÊNG trong hộp thư TikTok, 500–1.000 ký tự, chia 4–6 đoạn ngắn: đồng cảm → lá số → năm tới (cả
   mặt thuận và mặt cần lưu ý) → trả lời đúng câu khách hỏi → lời chúc.

BẮT BUỘC:
- Chỉ dùng đúng lá số và DỮ KIỆN NĂM TỚI do TikTok Manager tính. Không tự tính thêm can chi, không đổi Nhật chủ/Dụng thần.
- Màu sắc: chỉ dùng đúng danh sách "màu hợp" và "màu nên dùng ít" được cung cấp; nói là hướng gợi ý, KHÔNG hù dọa, KHÔNG
  nói "kiêng kẻo xui".
- Sức khỏe: KHÔNG đoán bệnh, KHÔNG hứa khỏi; khuyên đi khám bác sĩ; lá số chỉ nói về nhịp nghỉ ngơi, giữ sức.
- Không hứa may mắn, tài lộc, bình an, chắc chắn; không khuyên mua/đeo vật phẩm; không nhắc giá, link, Zalo, web.
- Kênh chỉ giải mã Bát Tự: khách xin gieo quẻ → nói khéo là Cô Kim xem theo Bát Tự.
Trả về JSON: {"binh_luan": "...", "tin_nhan": "...", "goi_y_video": "1 câu nếu tin nhắn đáng làm video trả lời, không thì rỗng"}"""


def draft_ai(message: str, c: dict, ch: dict) -> dict:
    from . import comment_reply, strategy

    col = colors(ch)
    facts = year_facts(ch)

    def ask(extra: str = ""):
        prompt = (f"Tin nhắn của khách (đã ẩn tên), xưng hô gợi ý: {_xung(c)}\n{comment_reply.anonymize(message)[:2000]}\n\n"
                  f"Lá số TikTok Manager tính: {comment_reply.chart_brief(ch)}\n"
                  f"Dữ kiện năm {YEAR_NEXT}:\n- " + "\n- ".join(facts) + "\n"
                  f"Màu hợp: {'; '.join(f'{m} (hành {h})' for h, m in col['hop'])}\n"
                  f"Màu nên dùng ít: {'; '.join(f'{m} (hành {h})' for h, m in col['it'])}"
                  + ("\nLưu ý: vượng nhược sát ngưỡng, Dụng thần chỉ là hướng gợi ý." if col["sat_nguong"] else ""))
        if extra:
            prompt += f"\n\nBản trước vi phạm quy tắc, tránh: {extra}"
        out, usage = strategy.call_gemini(prompt, system=AI_SYSTEM, json_mode=True)
        strategy.record_usage("reply", None, usage)
        try:
            d = json.loads(out[out.find("{"): out.rfind("}") + 1])
        except ValueError:
            d = {"tin_nhan": out.strip()}
        return d, usage

    d, usage = ask()
    pub, pri = str(d.get("binh_luan") or "").strip(), str(d.get("tin_nhan") or "").strip()
    bad = _issues(pub) + _issues(pri)
    if bad:
        d, u2 = ask(", ".join(f"“{b}”" for b in bad))
        pub, pri = str(d.get("binh_luan") or "").strip(), str(d.get("tin_nhan") or "").strip()
        bad = _issues(pub) + _issues(pri)
        usage = {**usage, "cost_usd": (usage.get("cost_usd") or 0) + (u2.get("cost_usd") or 0)}
    return {"public": pub[:150], "private": pri, "idea": str(d.get("goi_y_video") or ""), "issues": bad,
            "cost_usd": round(float(usage.get("cost_usd") or 0), 5)}


def _issues(text: str) -> list[str]:
    r = compliance.check(text, False)
    return [x["match"] for x in r["offsite"] + r["promise"] if x.get("code") not in ("trang_ca_nhan",)]


# --------------------------------------------------------------------------- lưu / đọc
def save(data: dict, cid: int | None = None) -> int:
    init()
    cols = ["alias", "tiktok", "gioi", "dd", "mm", "yy", "t", "lich", "nhuan", "tier", "tags", "note"]
    vals = {k: data.get(k) for k in cols}
    for k in ("dd", "mm", "yy"):
        vals[k] = int(vals[k]) if str(vals.get(k) or "").strip().isdigit() else None
    vals["nhuan"] = 1 if str(vals.get("nhuan") or "").lower() in ("1", "true", "on") else 0
    vals["tier"] = vals.get("tier") if vals.get("tier") in TIERS else "moi"
    vals["alias"] = (vals.get("alias") or "").strip() or "Khách chưa đặt tên"
    for k in ("tiktok", "gioi", "t", "lich", "tags", "note"):
        vals[k] = (vals.get(k) or "").strip()
    vals["lich"] = vals["lich"] or "duong"
    now = db.now_iso()
    with db.tx() as c:
        if cid:
            c.execute(f"UPDATE customers SET {', '.join(f'{k}=?' for k in cols)}, updated_at=? WHERE id=?",
                      (*[vals[k] for k in cols], now, cid))
            return cid
        return c.execute(f"INSERT INTO customers ({', '.join(cols)}, created_at, updated_at) VALUES ({', '.join('?' * len(cols))},?,?)",
                         (*[vals[k] for k in cols], now, now)).lastrowid


def get(cid: int) -> dict | None:
    init()
    return db.query_one("SELECT * FROM customers WHERE id=?", (cid,))


def all_customers(q: str = "", tier: str = "") -> list[dict]:
    init()
    rows = db.query("SELECT c.*, (SELECT COUNT(*) FROM customer_msgs m WHERE m.customer_id=c.id) AS n_msgs FROM customers c"
                    " ORDER BY CASE c.tier WHEN 'than_thiet' THEN 0 WHEN 'quen' THEN 1 ELSE 2 END,"
                    " COALESCE(NULLIF(c.last_contact,''), c.created_at) DESC")
    if tier:
        rows = [r for r in rows if r["tier"] == tier]
    if q:
        ql = q.lower()
        rows = [r for r in rows if ql in f"{r['alias']} {r['tiktok']} {r['tags']} {r['note']} {r['yy'] or ''}".lower()]
    return rows


def messages(cid: int) -> list[dict]:
    init()
    return db.query("SELECT * FROM customer_msgs WHERE customer_id=? ORDER BY at DESC, id DESC", (cid,))


def add_message(cid: int, channel: str, direction: str, text: str, goi: str = "") -> None:
    init()
    text = (text or "").strip()
    if not text:
        return
    now = db.now_iso()
    with db.tx() as c:
        c.execute("INSERT INTO customer_msgs(customer_id, at, channel, direction, text, goi) VALUES(?,?,?,?,?,?)",
                  (cid, now, channel if channel in CHANNELS else "tin_nhan", "cokim" if direction == "cokim" else "khach",
                   text[:5000], goi))
        c.execute("UPDATE customers SET last_contact=?, updated_at=? WHERE id=?", (now, now, cid))
        n = c.execute("SELECT COUNT(*) FROM customer_msgs WHERE customer_id=? AND direction='khach'", (cid,)).fetchone()[0]
        if n >= THAN_THIET_AFTER:
            c.execute("UPDATE customers SET tier='than_thiet' WHERE id=? AND tier!='than_thiet'", (cid,))
        elif n >= 2:
            c.execute("UPDATE customers SET tier='quen' WHERE id=? AND tier='moi'", (cid,))


def delete(cid: int) -> None:
    init()
    with db.tx() as c:
        c.execute("DELETE FROM customer_msgs WHERE customer_id=?", (cid,))
        c.execute("DELETE FROM customers WHERE id=?", (cid,))


def counts() -> dict:
    init()
    rows = db.query("SELECT tier, COUNT(*) AS n FROM customers GROUP BY tier")
    return {r["tier"]: r["n"] for r in rows}
