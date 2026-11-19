"""Gợi ý thiết lập khi đăng TikTok + Quảng bá cho một gói (người dùng sửa được, lưu trong packages.post_plan_json).

Nguồn gợi ý, theo thứ tự ưu tiên: giá trị đã lưu > kế hoạch quảng cáo Gemini (ads_plan) > yêu cầu gửi Gemini
(loại, mục tiêu, số ngày, giờ đăng) > quy tắc của tool (Loại 1 không quảng cáo, chỉ quảng cáo khi tool báo Được).
"""
import json
import re

from .compliance import normalize

FIELDS = [  # (khoá, nhãn)
    ("gio_dang", "Giờ đăng"),
    ("gio_hang", "Gắn sản phẩm (giỏ hàng)"),
    ("quang_cao", "Chạy quảng cáo (Quảng bá)"),
    ("muc_tieu_qc", "Mục tiêu quảng cáo"),
    ("so_ngay_qc", "Thời gian chạy"),
    ("bat_qc_luc", "Bật quảng cáo lúc"),
    ("gioi_tinh", "Giới tính"),
    ("do_tuoi", "Độ tuổi"),
    ("khu_vuc", "Khu vực"),
    ("so_thich", "Sở thích"),
    ("ngan_sach", "Ngân sách/ngày"),
    ("nhan_ai", "Nhãn nội dung AI"),
    ("ghi_chu_dang", "Lưu ý khi đăng"),
]
KEYS = [k for k, _ in FIELDS]
RULE_KEYS = ("gio_hang", "quang_cao", "nhan_ai")  # luôn tính lại theo loại video + kết quả kiểm tra, không lưu
GOAL_LABEL = {"follow": "Người theo dõi (More followers)", "view": "Lượt xem video", "comment": "Tương tác (bình luận)",
              "sale": "Mua hàng / truy cập sản phẩm"}
LOAI_GOAL = {1: "comment", 2: "sale", 3: "follow"}


def _grab(text: str, label_rx: str) -> str:
    """Lấy giá trị sau nhãn trong kế hoạch Gemini, vd 'Độ tuổi: 25 – 44 tuổi (…)' → '25 – 44 tuổi'."""
    m = re.search(rf"(?:{label_rx})[^:：]*[:：]\s*(.+?)(?=\s+-\s+\S[^:：]{{0,40}}[:：]|$)", text, re.I)
    if not m:
        return ""
    v = m.group(1).strip(" .;-")
    v = re.sub(r"\s*\([^)]*\)", "", v).strip(" .;-")  # bỏ phần giải thích trong ngoặc
    return v[:120]


def from_ads_plan(text: str) -> dict:
    t = (text or "").replace("**", "")
    out = {}
    for key, rx in (("gioi_tinh", r"Giới tính"), ("do_tuoi", r"Độ tuổi"), ("khu_vuc", r"Khu vực"),
                    ("so_thich", r"Sở thích")):
        v = _grab(t, rx)
        if v:
            out[key] = v
    m = re.search(r"(\d{1,2})\s*ngày", t)
    if m:
        out["so_ngay_qc"] = f"{m.group(1)} ngày liên tục"
    for m in re.finditer(r"bật([^.]{0,60}?)(\d{1,2}[:h]\d{2}\s*[–-]\s*\d{1,2}[:h]\d{2}|\d{1,2}[:h]\d{2})", t, re.I):
        if "dang" in normalize(m.group(1)):  # "Giờ bật …: - Đăng video lúc 07:00" → giờ đăng, không phải giờ bật
            continue
        out["bat_qc_luc"] = m.group(2).replace("h", ":")
        break
    n = normalize(t)
    if "theo doi" in n or "follower" in n:
        out["muc_tieu_qc"] = GOAL_LABEL["follow"]
    return out


def suggest(p: dict, chk: dict, req: dict | None = None, best_slot: str = "") -> dict:
    """Trả về {khoá: (giá_trị, nguồn)} để hiển thị; giá trị đã lưu luôn thắng."""
    loai = int(p.get("loai") or 1)
    opts = (req or {}).get("opts") or {}
    saved = json.loads(p.get("post_plan_json") or "{}") if isinstance(p.get("post_plan_json"), str) else {}
    gem = from_ads_plan(p.get("ads_plan") or "")
    ads_wanted = bool(opts.get("ads")) if opts else loai in (2, 3) and bool(p.get("ads_plan"))
    ads = ads_wanted and loai != 1  # có ý định quảng cáo → hiện gợi ý; được chạy hay không do kết quả kiểm tra
    out = {}

    def put(k, v, src):
        if v:
            out.setdefault(k, (v, src))

    for k, v in saved.items():
        if k not in RULE_KEYS:
            put(k, v, "đã lưu")
    put("gio_dang", opts.get("publish") or best_slot, "yêu cầu" if opts.get("publish") else "khung tốt nhất")
    sku = (p.get("sku") or "").strip()
    put("gio_hang", f"Có – {sku}" if loai == 2 and sku else "Không", "quy tắc")
    if loai == 1:
        put("quang_cao", "Không (video lá số không chạy quảng cáo)", "quy tắc")
    elif not chk.get("ads_ok"):
        put("quang_cao", "Không – tool chưa cho phép (xem mục Kiểm tra)", "quy tắc")
    else:
        put("quang_cao", "Có" if ads else "Không (yêu cầu không chạy)", "yêu cầu" if opts else "Gemini")
    if ads:
        for k, v in gem.items():
            put(k, v, "Gemini")
        put("muc_tieu_qc", GOAL_LABEL.get(opts.get("goal") or LOAI_GOAL.get(loai, "")), "yêu cầu")
        put("so_ngay_qc", f"{opts['ads_days']} ngày liên tục" if opts.get("ads_days") else "", "yêu cầu")
        put("bat_qc_luc", "Sau khi video lên kênh 1–2 giờ, đã được duyệt tự nhiên", "quy tắc")
        put("khu_vuc", "Việt Nam", "mặc định")
        put("ngan_sach", "", "")
    # Quy tắc luôn thắng giá trị đã lưu khi tool không cho phép quảng cáo
    if loai == 1:
        out["quang_cao"] = ("Không (video lá số không chạy quảng cáo)", "quy tắc")
    elif not p.get("id"):
        out["quang_cao"] = ("Chờ “Lưu & kiểm tra” để tool xác nhận", "quy tắc")
    elif not chk.get("ads_ok"):
        out["quang_cao"] = ("Không – tool chưa cho phép (xem mục Kiểm tra)", "quy tắc")
    if loai != 2:
        out["gio_hang"] = ("Không", "quy tắc")
    put("nhan_ai", "Bật “Nội dung do AI tạo”", "quy tắc C.10a")
    notes = {1: "Ghim bình luận mời để lại ngày sinh; không gắn giỏ hàng.",
             2: "Chèn ảnh/clip sản phẩm thật (C.9); chép đúng caption để tool tự gắn gói.",
             3: "Không gắn giỏ hàng; chép đúng caption để tool tự gắn gói."}
    put("ghi_chu_dang", notes.get(loai, ""), "quy tắc")
    return out


def from_form(form) -> str:
    return json.dumps({k: str(form.get(f"plan_{k}") or "").strip() for k in KEYS
                       if k not in RULE_KEYS and str(form.get(f"plan_{k}") or "").strip()}, ensure_ascii=False)
