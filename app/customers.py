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


def missing_fields(c: dict, ch: dict | None) -> list[str]:
    """Liệt kê thông tin còn thiếu để lập trọn vẹn Tứ Trụ + Đại vận."""
    if not ch:
        return ["ngày tháng năm sinh", "giờ sinh", "dương/âm lịch", "giới tính"]
    miss = []
    if not (ch.get("tru") and len(ch["tru"]) >= 4 and ch["tru"][3]):
        miss.append("giờ sinh")
    if not (c.get("gioi") or "").strip():
        miss.append("giới tính")
    return miss


def _curiosity_hook(ch: dict, facts: list[str]) -> str:
    """Chọn móc câu tò mò ngắn (≤28 ký tự), sát lá số thật, không hù dọa, không hứa hẹn."""
    joined = " ".join(facts)
    if "được tiếp sức" in joined or "đúng Dụng thần" in joined:
        return "có 1 điểm tiếp sức rất hay"
    if "lục xung" in joined or "Kỵ thần" in joined:
        return "có 1 nút thắt cần gỡ khéo"
    if "Sắp đổi đại vận" in joined:
        return "sắp bước vào nhịp chuyển mới"
    return "có bước chuyển rất đáng xem"


def templates(message: str, c: dict, ch: dict | None) -> dict:
    x = _xung(c)
    msg = (message or "").lower()
    asks_health = bool(re.search(r"sức\s*khỏe|bệnh|đau|xương|khớp|mệt|ốm", msg))
    miss = missing_fields(c, ch)
    if not ch:
        public = (f"Cô Kim chào {x} 🍵 {x.capitalize()} bình luận thêm ngày giờ sinh (đủ ngày, tháng, năm, giờ & dương/âm) "
                  f"để Cô Kim soi điểm chuyển năm {YEAR_NEXT} cho {x} nha!")
        private = "\n".join([
            f"Cô Kim chào {x}. Cô Kim đọc lời nhắn của {x} rồi nha 🍵",
            f"Để lập trọn vẹn lá số Bát Tự 4 trụ và xem kỹ nhịp chuyển năm Đinh Mùi {YEAR_NEXT}, {x} nhắn giúp Cô Kim đủ 4 thông tin này nha:",
            "- Ngày, tháng, năm sinh (ghi rõ Dương lịch hay Âm lịch)",
            "- Giờ sinh (nếu không nhớ chính xác phút thì ước chừng sáng, trưa, chiều hay tối cũng được ạ)",
            "- Giới tính (để Cô Kim xem luôn chu kỳ Đại vận 10 năm)",
            f"Khi đủ 4 trụ, Cô Kim sẽ gửi riêng phần giải mã chi tiết Nhật chủ, điểm đáng lưu ý năm {YEAR_NEXT} và hướng màu sắc hài hòa cho {x} nha!",
        ])
        return {"public": public[:150], "private": private, "facts": [], "missing": miss}

    yr = battu.name(battu.ganzhi(YEAR_NEXT - 4))
    facts = year_facts(ch)
    col = colors(ch)
    nc_lbl = f"{ch['nhat_chu']} {ch['nhat_chu_hanh']}"
    hook = _curiosity_hook(ch, facts)
    no_hour = "giờ sinh" in miss
    no_gender = "giới tính" in miss

    if no_hour:
        ask_extra = "giờ sinh & giới tính" if no_gender else "giờ sinh"
        if asks_health:
            public = (f"Thương {x}, nhớ đi khám bác sĩ nha. Lá số {nc_lbl} năm {YEAR_NEXT} {hook} — "
                      f"bình luận thêm {ask_extra} để Cô Kim chốt 4 trụ gửi hộp thư!")
        else:
            public = (f"Lá số {nc_lbl} của {x} năm {YEAR_NEXT} {hook} 🍵 "
                      f"Bình luận thêm {ask_extra} để Cô Kim chốt đủ 4 trụ rồi nhắn hộp thư nha!")
    else:
        if asks_health:
            public = (f"Thương {x}, chuyện sức khỏe nhớ đi khám bác sĩ nha. Lá số {nc_lbl} năm {YEAR_NEXT} {hook}, "
                      f"Cô Kim nhắn riêng trong hộp thư rồi nha!")
        else:
            public = (f"Lá số {nc_lbl} của {x} năm {YEAR_NEXT} {hook} 🍵 "
                      f"Cô Kim vừa soi đủ 4 trụ và nhắn riêng trong hộp thư, {x} vào xem nha!")

    lines = [f"Cô Kim chào {x}. Cô Kim đọc tin nhắn mà thương {x} lắm.",
             f"Lá số của {x}: {ch['tu_tru']}, Nhật chủ {ch['nhat_chu']} ({ch['nhat_chu_ta']}), {ch['trang_thai'].lower()}."]
    if no_hour:
        lines.append(f"Lưu ý nhỏ: hiện Cô Kim mới nhận được 3 trụ (chưa có giờ sinh nên thiếu Trụ Giờ — trụ quyết định độ chuẩn của Dụng thần và hậu vận). "
                     f"Nếu {x} nhớ khoảng giờ sinh (dù chỉ nhớ sáng, trưa, chiều hay tối, kèm dương hay âm lịch), {x} nhắn thêm cho Cô Kim để chốt lại đủ 4 trụ thật tròn vẹn nha!")
    if no_gender:
        lines.append(f"Ngoài ra, nếu {x} nhắn thêm giới tính, Cô Kim sẽ tính luôn chu kỳ Đại vận 10 năm cho {x} nha.")
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
    return {"public": public[:150], "private": "\n".join(lines), "facts": facts, "missing": miss}


# --------------------------------------------------------------------------- AI
AI_SYSTEM = """Bạn là Cô Kim của kênh TikTok "Tiệm Trà Giải Mã": người pha trà, giải mã Bát Tự nhẹ nhàng, giọng miền Nam ấm,
xưng "Cô Kim", gọi khách theo cách khách xưng hô (chị/anh/con). Viết 2 bản trả lời cho tin nhắn của khách:

1. "binh_luan": trả lời BÌNH LUẬN CÔNG KHAI, tối đa 150 ký tự.
   - KHÔNG viết chung chung kiểu "cảm ơn đã quan tâm". Phải cài 1 chi tiết GÂY TÒ MÒ tự nhiên từ đúng Nhật chủ hoặc điểm chuyển năm 2027
     (ví dụ: có điểm tiếp sức bất ngờ, có 1 nút thắt cần gỡ khéo, sắp bước sang nhịp mới) để khách muốn bình luận tiếp hoặc mở hộp thư ngay.
   - Nếu khách THIẾU GIỜ SINH (mới có 3 trụ) hoặc thiếu dương/âm lịch / giới tính: BẮT BUỘC gợi ý khéo để khách bình luận bổ sung
     đủ thông tin để Cô Kim chốt đủ 4 trụ Bát Tự hoàn chỉnh rồi nhắn hộp thư.
   - Không lặp ngày sinh, không nêu tên khách, không nêu chi tiết sức khỏe hay chuyện riêng, không nêu màu sắc. Dùng từ "bình luận" (không dùng "comment").
2. "tin_nhan": TIN NHẮN RIÊNG trong hộp thư TikTok, 500–1.000 ký tự, chia 4–6 đoạn ngắn: đồng cảm → lá số (nếu thiếu giờ sinh thì nhắc khéo
   bổ sung khoảng giờ sinh sáng/trưa/chiều/tối để hoàn thiện Trụ Giờ & Dụng thần) → năm tới (cả mặt thuận và mặt cần lưu ý) → trả lời đúng câu khách hỏi → lời chúc.

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
    miss = missing_fields(c, ch)
    miss_note = (f"\nThông tin CÒN THIẾU của khách: {', '.join(miss)} (BẮT BUỘC gợi ý khách bình luận/nhắn bổ sung để chốt đủ 4 trụ Bát Tự hoàn chỉnh)."
                 if miss else "\nKhách đã cung cấp ĐỦ 4 trụ (có giờ sinh) và giới tính — gợi tò mò để khách mở hộp thư đọc ngay.")

    def ask(extra: str = ""):
        prompt = (f"Tin nhắn của khách (đã ẩn tên), xưng hô gợi ý: {_xung(c)}\n{comment_reply.anonymize(message)[:2000]}\n\n"
                  f"Lá số TikTok Manager tính: {comment_reply.chart_brief(ch)}{miss_note}\n"
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
            "missing": miss, "cost_usd": round(float(usage.get("cost_usd") or 0), 5)}


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


def studio_sync_status() -> dict:
    """Tổng hợp trạng thái đồng bộ TikTok API + Bình luận Studio và lọc khách xin lá số mới chưa lưu."""
    from . import comment_stats

    init()
    comment_stats.init()
    last_scan = db.query_one("SELECT started_at, status, message FROM scans ORDER BY id DESC LIMIT 1")
    last_imp = db.query_one("SELECT imported_at, source, total_rows, note FROM studio_comment_imports ORDER BY id DESC LIMIT 1")

    acc = db.get_active_account()
    api_comments_total = 0
    if acc:
        row = db.query_one(
            """SELECT COALESCE(SUM(vs.comment_count), 0) AS n
               FROM video_snapshots vs
               INNER JOIN (
                   SELECT video_id, MAX(id) AS max_id FROM video_snapshots GROUP BY video_id
               ) latest ON latest.max_id = vs.id
               INNER JOIN videos v ON v.id = vs.video_id
               WHERE v.open_id = ?""",
            (acc["open_id"],),
        )
        api_comments_total = int((row or {}).get("n") or 0)

    studio_total_row = db.query_one("SELECT COUNT(*) AS n FROM studio_comments")
    studio_comments_total = int((studio_total_row or {}).get("n") or 0)
    comment_delta = max(0, api_comments_total - studio_comments_total)

    existing = all_customers()
    saved_handles = {(c.get("tiktok") or "").strip().lstrip("@").lower() for c in existing if (c.get("tiktok") or "").strip()}
    saved_births = {
        (int(c["dd"]), int(c["mm"]), int(c["yy"]))
        for c in existing
        if c.get("dd") and c.get("mm") and c.get("yy")
    }

    cdata = comment_stats.dashboard_data(role="viewer", cat="xin_la_so")
    leads = []
    for r in cdata.get("rows") or []:
        handle = (r.get("author_display") or "").strip().lstrip("@")
        b = r.get("birth") or {}
        bkey = (int(b["dd"]), int(b["mm"]), int(b["yy"])) if (b.get("dd") and b.get("mm") and b.get("yy")) else None
        if handle and handle.lower() in saved_handles:
            continue
        if bkey and bkey in saved_births:
            continue
        leads.append({
            "sc_id": r["id"],
            "author_display": handle,
            "masked": r.get("author_masked") or comment_stats.mask_handle(handle),
            "text": r.get("text") or "",
            "time_text": r.get("time_text") or "",
            "birth_summary": r.get("birth_summary") or "",
            "birth": b,
            "replied": bool(r.get("is_replied")),
            "video_caption": (r.get("video_caption") or "")[:70],
        })
    # Ưu tiên khách chưa trả lời và có đủ ngày sinh lên đầu
    leads.sort(key=lambda x: (1 if x["replied"] else 0, 0 if (x["birth"] or {}).get("has_full_date") else 1, -x["sc_id"]))

    return {
        "last_api_scan": last_scan,
        "last_studio_import": last_imp,
        "api_comments_total": api_comments_total,
        "studio_comments_total": studio_comments_total,
        "comment_delta": comment_delta,
        "studio_leads": leads[:25],
        "studio_leads_total": len(leads),
    }


def import_from_studio_comment(sc_id: int) -> int:
    """Chuyển 1 bình luận xin lá số từ `/binh-luan` thành hồ sơ khách hàng trong `/khach-hang`."""
    from . import comment_stats

    init()
    comment_stats.init()
    r = db.query_one("SELECT * FROM studio_comments WHERE id=?", (sc_id,))
    if not r:
        raise ValueError("Không tìm thấy bình luận trong dữ liệu Studio.")
    try:
        b = json.loads(r.get("birth_json") or "{}")
    except ValueError:
        b = {}
    handle = (r.get("author_display") or "").strip().lstrip("@")
    cc = (r.get("can_chi_tags") or "").split(",")[0].strip()
    yy = b.get("yy") or ""
    alias = handle or (f"Khách {cc} {yy}".strip() if (cc or yy) else f"Khách Studio #{sc_id}")
    cid = save({
        "alias": alias,
        "tiktok": handle,
        "gioi": b.get("gioi") or "",
        "dd": b.get("dd") or "",
        "mm": b.get("mm") or "",
        "yy": yy,
        "t": b.get("t") or "",
        "lich": b.get("lich") or "duong",
        "tier": "moi",
        "tags": "từ bình luận Studio" + (f", {cc}" if cc else ""),
        "note": f"Nguồn: bình luận video '{(r.get('video_caption') or '')[:80]}' ({r.get('time_text') or ''})".strip(),
    })
    add_message(cid, "binh_luan", "khach", r.get("text") or "")
    return cid
