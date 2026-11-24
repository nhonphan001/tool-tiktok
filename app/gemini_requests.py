"""Yêu cầu sản xuất gửi Gemini qua hộp thư Drive và tự theo dõi thư trả lời.

Luồng:
  1. Anh Nhơn nhập yêu cầu trên tool → tool giữ số gói kế tiếp, soạn thư SANXUAT-<ddmm>-GOI-<n>-<SLUG>__YEUCAU
     kèm quy tắc bắt buộc theo loại video + số liệu kênh + mẫu trả lời mà tool đọc được.
  2. Gửi thư: tạo file trong GUI_GEMINI; nếu service account không tạo được file (Drive không cấp dung lượng cho
     service account) thì ghi vào Doc "hộp thư đi" cố định do anh Nhơn tạo (HOP_THU_TOOL__YEUCAU).
  3. Mỗi 10 phút (và sau mỗi lần quét) tool liệt kê file trong hộp thư; có file …GOI-<n>…__XONG mới hơn thư gửi
     → đánh dấu đã trả lời + thông báo trên web, bấm để nhập vào Gói SX.
Không tốn token Gemini.
"""
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import httpx

from . import compliance, db, mailbox, packages
from .config import settings

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS gemini_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    goi TEXT, code TEXT, title TEXT, brief TEXT, opts_json TEXT, letter_md TEXT,
    status TEXT DEFAULT 'draft', channel TEXT, drive_file_id TEXT, error TEXT,
    created_at TEXT, sent_at TEXT, answered_at TEXT, answer_file_id TEXT, answer_name TEXT
);
"""
STATUS = {"draft": "Nháp", "sent": "Đã gửi – chờ Gemini", "answered": "Gemini đã trả lời", "imported": "Đã nhập Gói SX",
          "updated": "Gemini đã cập nhật – nhập lại", "error": "Lỗi gửi"}
GOALS = {"follow": "Tăng người theo dõi", "view": "Tăng lượt xem", "sale": "Bán hàng (giỏ hàng)",
         "comment": "Tăng bình luận"}
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=id,name"


def init() -> None:
    with db.tx() as c:
        c.executescript(SCHEMA)
        cols = {r[1] for r in c.execute("PRAGMA table_info(gemini_requests)").fetchall()}
        if "answer_modified" not in cols:
            c.execute("ALTER TABLE gemini_requests ADD COLUMN answer_modified TEXT DEFAULT ''")
        if "video_seen" not in cols:
            c.execute("ALTER TABLE gemini_requests ADD COLUMN video_seen TEXT DEFAULT ''")


def _slug(text: str, n: int = 4) -> str:
    words = re.findall(r"[a-z0-9]+", compliance.normalize(text))
    return "-".join(words[:n]).upper() or "YEU-CAU"


def next_goi() -> int:
    """Số gói kế tiếp: lớn hơn mọi gói trong tool và mọi yêu cầu đã giữ số."""
    init()
    nums = [int(p["goi"]) for p in packages.all_packages() if str(p.get("goi") or "").isdigit()]
    nums += [int(r["goi"]) for r in db.query("SELECT goi FROM gemini_requests") if str(r["goi"] or "").isdigit()]
    return (max(nums) + 1) if nums else 1


def all_requests() -> list[dict]:
    init()
    rows = db.query("SELECT * FROM gemini_requests ORDER BY id DESC")
    for r in rows:
        r["opts"] = json.loads(r["opts_json"] or "{}")
    return rows


def get(rid: int) -> dict | None:
    init()
    r = db.query_one("SELECT * FROM gemini_requests WHERE id=?", (rid,))
    if r:
        r["opts"] = json.loads(r["opts_json"] or "{}")
    return r


# ----------------------------------------------------------------- soạn thư
# Khối giọng dán NGUYÊN VĂN vào cuối mọi prompt video (P8a thủ công có giọng, chốt 20/11)
VOICE_BLOCK = ("Voice (identical in every scene): a 26-year-old Southern Vietnamese woman (polite Saigon accent, never Northern "
               "or Central), warm mezzo-soprano around 222Hz, calm and soothing with a gentle smile in her voice, steady pace of "
               "about 4 syllables per second, crisp Vietnamese tones, even volume. She starts speaking right at 0.0s. Dry "
               "close-mic voice only: NO background music, NO ambient sound, NO sound effects.")


def _rules_for(loai: int, ads: bool, n: int = 4) -> list[str]:
    cs = packages.clip_seconds()
    lo, hi = packages.syllable_range()
    common = [
        f"Định dạng: {n} cảnh × {cs} giây (clip Gemini/Flow {cs} giây), dọc 9:16, mỗi cảnh {lo if n < 6 else 26}–{hi} âm tiết (giọng đọc 3,8–4,0 âm tiết/giây "
        f"≈ {lo / 4:.0f}–{hi / 3.9:.1f} giây, chừa khoảng 0,7 giây vào/ra giọng), hook ngay giây 0; Cô Kim v3.3 (25–30 tuổi; "
        "ảnh mặt chuẩn nhất CO_KIM_MASTER_FACE_CHUAN_NHAT_3957.png, ID Drive 1gnq18QukC1lCSC0py5Zmf18lR78r3CEH (từ Gói 19): "
        "khóa mặt trái xoan, mắt hạnh nhân, cười khép môi sau voan tím (không hở răng), trâm vàng ngọc đỏ + trâm tua rua trái; "
        f"KHÔNG chép tư thế chắp tay, lá bồ đề, túi nhung đỏ). Kèm prompt video {cs} giây cho từng cảnh.",
        "Không nhắc web, Link Bio, tên miền, Zalo, Shopee, Lazada, link (B.1).",
        "Không hứa may mắn, tài lộc, rước lộc, bình an, phù hộ; không hù dọa; không hứa chữa bệnh, giàu có (B.4).",
        "Hình ảnh: không lửa, hào quang, linh vật phát sáng; không chắp tay khấn vái, nhang, mâm cúng (C.7, C.8).",
        f"{n} cảnh cùng 1 gói phải THỐNG NHẤT bối cảnh, ánh sáng và thời điểm trong ngày (không để 1 cảnh sáng hơn/khác giờ "
        "so với các cảnh còn lại) — quy tắc anh Nhơn chốt 20/11.",
        "Bật nhãn “Nội dung do AI tạo” khi đăng.",
        "**Hiệu suất (số liệu Studio 24/11: mọi video mất ~50% người xem ở giây 2, chỉ 2–6% xem tới cảnh cuối):** khung hình 0 "
        "sáng, có chuyển động (hơi trà, rót trà, ánh nắng), Cô Kim nói NGAY giây 0; ô “Chữ trên hình” là chữ hook lớn giữa màn "
        "hình ≤ 70 ký tự; 1 câu kêu gọi ngắn ở CUỐI CẢNH 1 (giây 3–8; clip 10 giây nên cảnh 2 đã là giây 10+), không chỉ ở cảnh cuối; caption ≤ 250 ký tự, dòng đầu là lý "
        "do để follow/comment; không ghi giờ (“tối nay”, “19h”) trong caption, chữ trên hình và lời thoại.",
    ]
    if n >= 6:
        common.append(f"**Video trên 60 giây ({n} cảnh, thư CHOT-2311-VIDEO-60-GIAY):** thành phẩm phải dài TRÊN 61 giây; "
                      "mỗi cảnh một hành động khác nhau; chữ trên hình đánh dấu chương; câu móc giữa video (~giây 35–40); "
                      "Loại 1 theo bố cục hook → lá số bằng hình ảnh → tính cách → tình cảm/gia đạo → móc giữa video → "
                      "năm tới (cả hai mặt) → lời khuyên + CTA.")
    if loai == 3:
        return [
            "**Loại 3 – Video tăng follow, KHÔNG gắn giỏ hàng, KHÔNG SKU.**",
            "Giữ video **đủ điều kiện Quảng bá** (kể cả tuần không quảng bá) nên tuyệt đối **không xem lá số, không bói toán, không Bát Tự/can chi/"
            "Nhật chủ/Dụng thần, không mời “để lại ngày sinh”** (TikTok cấm quảng cáo dịch vụ bói toán tại VN — "
            "lý do bị từ chối ngày 18/11).",
            "Nội dung nên chọn: trà sáng chữa lành, lời chúc buổi sáng, đếm ngược cuối năm, câu chuyện đời thường ấm áp, "
            "mẹo trà. Cô Kim là người pha trà, không phải thầy bói.",
            "CTA: “bấm theo dõi Cô Kim” kèm lời hứa “mỗi sáng Cô Kim pha một ấm trà cho cả nhà” — nói ở cuối cảnh 1 (giây 3–8) và lặp ở dòng "
            "đầu caption; bình luận ghim là 1 câu hỏi đời thường dễ trả lời (vd “Sáng nay cả nhà uống trà gì?”), không kiểu "
            "“comment ‘trà’ để nhận…”.",
            *common,
        ] + (["Nội dung phải giữ được 7 ngày chạy quảng cáo: tránh mốc ngày cụ thể trong lời thoại (vd “thứ Ba 17/11”), "
              "dùng “sáng nay”, “những ngày cuối năm”."] if ads else [])
    if loai == 2:
        return ["**Loại 2 – Video sản phẩm (giỏ hàng).** Chỉ mô tả vật phẩm: chất liệu, màu, cách dùng, làm quà; không xem "
                "lá số. Tên sản phẩm đúng cột “Tên dùng trong video”. CTA: “bấm giỏ hàng góc trái”. Chèn ảnh sản phẩm thật "
                "(C.9).", *common]
    return ["**Loại 1 – Video giải mã lá số (không giỏ hàng, KHÔNG chạy quảng cáo).** Dùng NGUYÊN VĂN lá số trong mục "
            "“Lá số (TikTok Manager tính)” của thư này, không tự tính can chi / Nhật chủ / Dụng thần. Không nối lá số với vật phẩm. CTA sớm ở cuối cảnh 1 (giây 3–8): “comment năm sinh để Cô Kim xem giúp”; "
            "CTA cuối: “để lại ngày sinh dưới bình luận để Cô Kim giải mã”. Ưu tiên lá số theo NĂM SINH cụ thể (vd “Nữ Đinh Mùi "
            "1967 bước vào năm 2027”), 7 cảnh.", *common]


def _n(x) -> str:
    return f"{x:,}".replace(",", ".") if isinstance(x, (int, float)) else str(x)


def _channel_facts() -> list[str]:
    from . import analytics, kpi

    acc = db.get_active_account()
    if not acc:
        return []
    out = []
    try:
        k = kpi.summary(acc["open_id"])
        for t in k.get("targets", []):
            out.append(f"Mốc {_n(t['target'])} follower trước {t['deadline']}: đang {_n(t['current'])} ({t['pct']}%), "
                       f"cần {t['need_per_day']}/ngày, tốc độ 7 ngày {t['pace']}/ngày.")
        slots = sorted(k.get("slots", []), key=lambda s: s.get("avg_views") or 0, reverse=True)
        if slots:
            out.append("Khung giờ: " + "; ".join(f"{s['label']} {_n(s['avg_views'])} view TB, tim/view {s['like_view']}%"
                                                  for s in slots[:3]) + ".")
    except Exception:  # noqa: BLE001
        log.exception("kpi for letter")
    try:
        vids = sorted(analytics.get_videos(acc["open_id"]), key=lambda v: v.get("view_count") or 0, reverse=True)[:3]
        for v in vids:
            out.append(f"Video nhiều view: “{(v.get('title') or v.get('description') or '')[:80]}” — "
                       f"{_n(v.get('view_count', 0))} view, {_n(v.get('like_count', 0))} tim.")
    except Exception:  # noqa: BLE001
        log.exception("videos for letter")
    return out


def chart_lines(birth: dict) -> list[str]:
    """Lá số do tool tính (cho video Loại 1) để Gemini dùng nguyên văn."""
    from . import battu

    if not birth or not (birth.get("dd") and birth.get("mm") and birth.get("yy")):
        return []
    c, err = packages.chart_of({"birth": birth})
    if err or not c:
        return [f"- ⚠ Ngày giờ sinh không hợp lệ: {err}"]
    diem = ", ".join(f"{k} {v}" for k, v in (c.get("ngu_hanh_diem") or {}).items())
    out = [f"- **Tứ trụ:** {battu.mo_ta_ngan(c)}",
           f"- **Âm lịch:** {c.get('am_lich', '')} · giới tính: {birth.get('gioi') or 'không rõ'}",
           f"- **Điểm ngũ hành:** {diem}",
           f"- **Hỷ thần:** {c.get('hy_than', '')} · **Kỵ thần:** {', '.join(c.get('ky_than') or [])}",
           f"- **Nạp âm 4 trụ:** {', '.join(c.get('nap_am') or [])}"]
    out += [f"- ⚠ {x}" for x in c.get("canh_bao") or []]
    return out


def build_letter(req: dict) -> str:
    o = req["opts"]
    loai = int(o.get("loai") or 3)
    ads = bool(o.get("ads")) and not settings.ads_paused  # tuần thử nghiệm không quảng bá → không xin kế hoạch quảng cáo
    goi = req["goi"]
    answer = f"{req['code']}__XONG.md"
    n = int(o.get("scenes") or 4)
    cs = packages.clip_seconds()
    lo, hi = packages.syllable_range()
    lines = [
        "---",
        f"ma_yeu_cau: {req['code']}",
        "loai: yeu_cau_san_xuat",
        "tu: TikTok Manager (anh Nhơn yêu cầu trên tool)",
        "gui: Gemini",
        f"goi: {goi}",
        f"loai_video: {loai}  # {packages.LOAI.get(loai, '')}",
        f"muc_tieu: {GOALS.get(o.get('goal'), o.get('goal') or '')}",
        f"quang_cao: {'co, ' + str(o.get('ads_days') or 7) + ' ngày liên tục' if ads else 'khong'}",
        f"ngay_dang: {o.get('publish') or ''}",
        f"ngay_tao: {(datetime.fromisoformat(req['created_at'][:19]) + timedelta(hours=7)):%d/%m/%Y %H:%M} (giờ VN)",
        f"file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/{answer}",
        "---", "",
        f"# Yêu cầu sản xuất Gói {goi} — {req['title']}", "",
        "## Yêu cầu của anh Nhơn", "", f"> {req['brief'].strip()}", "",
        "## Bắt buộc", "",
        *[f"- {r}" for r in _rules_for(loai, ads, n)], "",
    ]
    chart = chart_lines(o.get("birth") or {}) if loai == 1 else []
    if chart:
        lines += ["## Lá số (TikTok Manager tính – dùng nguyên văn, Nhật chủ = can trụ Ngày)", "", *chart, ""]
    elif loai == 1:
        lines += ["## Lá số", "", "- ⚠ Chưa có ngày giờ sinh: Gemini chọn chủ đề theo tuổi/con giáp chung, KHÔNG ghi tứ trụ "
                  "cụ thể (bộ kiểm tra B.2 sẽ không đối chiếu được).", ""]
    facts = _channel_facts()
    if facts:
        lines += ["## Số liệu kênh (TikTok Manager, số chính xác)", "", *[f"- {f}" for f in facts], ""]
    if ads:
        lines += ["## Kế hoạch quảng cáo cần đề xuất", "",
                  f"- Quảng bá (Promote) mục tiêu **{'Người theo dõi' if o.get('goal') == 'follow' else GOALS.get(o.get('goal'), '')}**, "
                  f"chạy {o.get('ads_days') or 7} ngày liên tục; ngân sách/ngày do anh Nhơn chọn.",
                  "- Đề xuất đối tượng (tuổi, giới tính, sở thích) và giờ bật quảng cáo; video phải qua bộ kiểm tra của tool "
                  "với kết quả “Được chạy quảng cáo” trước khi bật.", ""]
    lines += [
        "## Mẫu trả lời (giữ đúng tiêu đề để TikTok Manager tự đọc)", "",
        f"Tạo file **{answer}** trong GUI_CLAUDE với nội dung:", "",
        "```",
        f"ma_yeu_cau: {req['code']}",
        f"anh_{n}_canh:",
        *[f'  canh_{k}_{(k - 1) * cs}_{k * cs}s: "<ID ảnh Drive>"' for k in range(1, n + 1)],
        "",
        f"# Phiếu gói {goi} — <tiêu đề>",
        "",
        f"## Lời thoại {n} cảnh × {cs} giây",
        *[f"{k}. ({lo + 3} âm tiết) <lời thoại cảnh {k}>" for k in range(1, n + 1)],
        "",
        "## Chữ trên hình",
        "<hook ngắn>",
        "",
        "## Caption",
        "<caption + hashtag>",
        "",
        "## Bình luận ghim",
        "<bình luận ghim>",
        "",
        "## Kế hoạch quảng cáo" if ads else "",
        "<mục tiêu, đối tượng, giờ bật, số ngày>" if ads else "",
        "",
        f"## Prompt tạo video {packages.clip_seconds()} giây (Veo / Flow)",
        "Clip tạo TAY trên app Gemini/Flow, CÓ GIỌNG ĐỌC (anh Nhơn chốt 20/11). Mỗi prompt = hình + câu thoại + KHỐI GIỌNG giống hệt nhau từng chữ ở cả {n} cảnh:",
        f"> {VOICE_BLOCK}",
        "Lời thoại trong prompt viết số/ngày bằng chữ (vd. “hai mươi tháng mười một”), đặt trong ngoặc kép, nguyên văn phiếu gói.",
        f"1. **Cảnh 1 (0–{cs}s | ảnh …)**: <hình + chuyển động; She speaks softly in Vietnamese through her veil: \"<lời cảnh 1>\" + KHỐI GIỌNG>",
        *[f"{k}. **Cảnh {k} ({(k - 1) * cs}–{k * cs}s | ảnh …)**: <prompt cảnh {k}>" for k in range(2, n + 1)],
        "",
        "nhan_video:",
        f"  goi: {goi}",
        f"  loai: {loai}",
        f"  so_canh: {n}",
        "```", "",
        "Sau khi trả lời, TikTok Manager sẽ tự phát hiện thư (tối đa 10 phút) và báo anh Nhơn nhập vào Gói SX để kiểm tra.",
        "",
        f"Video (P8a/P8b): anh Nhơn tạo {n} clip thô trên Veo/Flow theo {n} prompt → 02_VIDEO_THO_CHO_KIEM_DUYET; Gemini QA, "
        "FFmpeg cắt/ghép/phụ đề, **KHÔNG xoá dấu nhận diện AI (logo ✦)**, lưu 04_VIDEO_DA_DUYET_SAN_SANG_DANG.",
        f"Khi dựng xong video, gửi thư **BAOCAO-<ddmm>-…-GOI-{goi}-…__GUI_CLAUDE.md** trong GUI_CLAUDE, đầu thư có 2 dòng "
        "(tool tự lấy link video vào Gói SX):",
        "```",
        f"goi: {goi}",
        'file_video_final_drive: "<ID Drive bản đăng có phụ đề>"',
        'file_video_clean_khong_sub: "<ID Drive bản sạch>"',
        "```",
    ]
    return "\n".join(x for x in lines if x is not None)


def create_ghep(goi: str, code: str, title: str, letter: str) -> int:
    """Yêu cầu ghép video (P8b) sau khi anh Nhơn duyệt đạt 4 clip thô."""
    init()
    now = db.now_iso()
    with db.tx() as c:
        return c.execute(
            "INSERT INTO gemini_requests(goi, code, title, brief, opts_json, letter_md, status, created_at, video_seen)"
            " VALUES(?,?,?,?,?,?, 'draft', ?, ?)",
            (str(goi), code, title, "Ghép 4 clip thô đã duyệt, chèn hook + phụ đề (P8b)",
             json.dumps({"kind": "ghep", "loai": 0}, ensure_ascii=False), letter, now, now),
        ).lastrowid


def build_sua(p: dict, chk: dict, note: str = "", n: int = 1) -> tuple[str, str]:
    """Thư nhờ Gemini sửa phiếu gói theo kết quả kiểm tra của tool (nút “Gửi Gemini sửa”)."""
    vn = datetime.now(timezone.utc) + timedelta(hours=7)
    goi = p.get("goi")
    code = f"SUA-{vn:%d%m}-GOI-{goi}-L{n}"
    answer = f"SANXUAT-{vn:%d%m}-GOI-{goi}-SUA{n}__XONG.md"
    items = [i for i in chk.get("items") or [] if i.get("level") in ("error", "warn")]
    issues = "\n".join(f"{k}. **{'LỖI' if i['level'] == 'error' else 'Cảnh báo'} · {i['rule']}**: {i['msg']}"
                       for k, i in enumerate(items, 1)) or "(không có)"
    scenes = []
    for k in range(1, packages.n_scenes(p) + 1):
        t = (p.get(f"scene{k}") or "").strip()
        scenes.append(f"{k}. ({packages.syllables(t)} âm tiết) {t or '—'}")
    bad_prompts = sorted({int(m) for i in items if i["rule"] == "Prompt" for m in re.findall(r"cảnh (\d)", i["msg"])})
    prompts = "\n\n".join(f"**Cảnh {k} (hiện tại):** {p.get(f'prompt{k}') or '—'}" for k in bad_prompts)
    birth = p.get("birth") or {}
    chart = chart_lines(birth)
    hints = []
    rules = {i["rule"] for i in items}
    if "Nhịp cảnh" in rules or "Nhịp 8s" in rules:
        lo, hi = packages.syllable_range()
        hints.append(f"Mỗi cảnh **{lo}–{hi} âm tiết** (clip {packages.clip_seconds()} giây, giọng 3,8–4,0 âm tiết/giây). "
                     "Số và ngày được tính theo cách đọc (“20/11” = 4 âm tiết).")
    if "Prompt" in rules:
        hints.append("Prompt video của mỗi cảnh phải chứa **nguyên văn** lời thoại cảnh đó trong ngoặc kép (số/ngày có thể "
                     f"viết bằng chữ), kết thúc bằng khối giọng cố định:\n> {VOICE_BLOCK}")
    if "B.2" in rules:
        hints.append("Video lá số: ghi rõ ở đầu phiếu `la_so: <ngày>/<tháng>/<năm dương lịch> <giờ nếu có>, <giới tính>` "
                     "và dùng **đúng** tứ trụ tool tính (bên dưới, nếu có). Không tự tính can chi.")
    letter = "\n".join([
        "---", f"ma_yeu_cau: {code}", "loai: yeu_cau_sua_phieu_goi", "tu: TikTok Manager (anh Nhơn bấm “Gửi Gemini sửa”)",
        "gui: Gemini", f"goi: {goi}", f"ngay_tao: {vn:%Y-%m-%d %H:%M} (GMT+7)",
        f"file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/{answer}", "---", "",
        f"# Sửa phiếu Gói {goi} theo kết quả kiểm tra của TikTok Manager", "",
        f"Anh Nhơn chọn **{len(items)} mục** cần sửa{' và ghi chú thêm' if note.strip() else ''}. Nhờ Gemini sửa đúng các mục dưới, "
        "**giữ nguyên** những phần không bị nêu (ảnh, hook, caption… nếu không có lỗi).", "",
        "## Các mục cần sửa", issues, "",
        *(["## Ghi chú thêm của anh Nhơn", note.strip(), ""] if note.strip() else []),
        "## Yêu cầu khi sửa", *[f"- {h}" for h in hints], "",
        "## Lời thoại hiện tại", *scenes, "",
        *(["## Prompt video đang lệch lời thoại", prompts, ""] if prompts else []),
        *(["## Lá số do tool tính (dùng nguyên văn)", *chart, ""] if chart else []),
        "## Trả lời",
        f"Tạo **{answer}** trong GUI_CLAUDE với **toàn bộ phiếu gói đã sửa**, đúng định dạng phiếu gói (lời thoại 4 cảnh "
        "“1. (NN âm tiết) …”, chữ trên hình, caption, bình luận ghim, ảnh từng cảnh, “## Prompt tạo video … giây”, khối "
        "nhan_video). Tool tự phát hiện thư, anh Nhơn bấm Nhập lại → Lưu & kiểm tra.",
    ])
    return code, letter


def create_sua(p: dict, chk: dict, note: str = "") -> int:
    init()
    n = 1 + (db.query_one("SELECT COUNT(*) AS c FROM gemini_requests WHERE goi=? AND code LIKE 'SUA-%'",
                          (str(p.get("goi")),)) or {}).get("c", 0)
    code, letter = build_sua(p, chk, note, n)
    now = db.now_iso()
    with db.tx() as c:
        return c.execute(
            "INSERT INTO gemini_requests(goi, code, title, brief, opts_json, letter_md, status, created_at)"
            " VALUES(?,?,?,?,?,?, 'draft', ?)",
            (str(p.get("goi")), code, f"Sửa phiếu Gói {p.get('goi')} (lần {n})",
             f"Sửa {chk.get('errors', 0)} lỗi, {chk.get('warns', 0)} cảnh báo theo bộ kiểm tra",
             json.dumps({"kind": "sua", "loai": int(p.get("loai") or 0)}, ensure_ascii=False), letter, now),
        ).lastrowid


def create(brief: str, title: str, opts: dict) -> int:
    init()
    goi = str(next_goi())
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    vn = now + timedelta(hours=7)
    title = (title or "").strip() or (
        f"{packages.LOAI_SHORT.get(int(opts.get('loai') or 3), '')} – {GOALS.get(opts.get('goal'), '')}".strip(" –")
        if opts.get("loai") == 3 or opts.get("goal") else brief.strip().split("\n")[0][:60])
    code = f"SANXUAT-{vn:%d%m}-GOI-{goi}-{_slug(title)}"
    req = {"goi": goi, "code": code, "title": title, "brief": brief, "opts": opts, "created_at": now.isoformat()}
    letter = build_letter(req)
    with db.tx() as c:
        return c.execute(
            "INSERT INTO gemini_requests(goi, code, title, brief, opts_json, letter_md, status, created_at)"
            " VALUES(?,?,?,?,?,?, 'draft', ?)",
            (goi, code, title, brief, json.dumps(opts, ensure_ascii=False), letter, now.isoformat()),
        ).lastrowid


# ----------------------------------------------------------------- gửi
def _token(scope: str = "https://www.googleapis.com/auth/drive") -> str:
    from .notebooklm import _credentials

    return _credentials([scope]).token


def _create_file(token: str, folder: str, name: str, content: str) -> str:
    meta = {"name": name, "parents": [folder], "mimeType": "application/vnd.google-apps.document"}
    boundary = "tiktokmanager"
    body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
            f"--{boundary}\r\nContent-Type: text/markdown; charset=UTF-8\r\n\r\n{content}\r\n--{boundary}--").encode()
    r = httpx.post(UPLOAD, content=body, timeout=60,
                   headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/related; boundary={boundary}"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["id"]


def outbox_text() -> str:
    """Nội dung Doc “hộp thư đi”: mọi yêu cầu đang chờ Gemini (mới nhất trước)."""
    pend = [r for r in all_requests() if r["status"] in ("sent", "draft", "error")]
    head = ["# HỘP THƯ ĐI CỦA TIKTOK MANAGER → GEMINI", "",
            "Doc này do TikTok Manager tự ghi đè. Gemini đọc từng yêu cầu bên dưới, làm xong thì tạo file trả lời "
            "trong **GUI_CLAUDE** đúng tên ở dòng `file_tra_loi`. Không sửa Doc này.", "",
            f"Số yêu cầu đang chờ: **{len(pend)}**", ""]
    body = []
    for r in pend:
        body += ["---", "", r["letter_md"], ""]
    out = head + (body or ["(Không có yêu cầu nào đang chờ.)"])
    try:
        from . import mail_notes

        letters = mail_notes.claude_letters_for_gemini()
    except Exception:  # noqa: BLE001
        letters = []
    if letters:
        out += ["", "---", "", f"# THƯ CỦA CLAUDE ĐANG CHỜ GEMINI ({len(letters)})", "",
                "Bản chép từ thư Claude trong GUI_GEMINI (72 giờ qua, chưa có thư xác nhận/trả lời). Làm theo từng thư; "
                "trả lời đúng tên ở dòng file_tra_loi trong thư (nếu có), hoặc tạo <MÃ THƯ>__XACNHAN.md trong GUI_CLAUDE.", ""]
        for r in letters:
            out += ["---", "", f"## ✉ {r['name']} · https://docs.google.com/document/d/{r['file_id']}/edit", "",
                    (r.get("body") or r.get("excerpt") or "").strip(), ""]
    return "\n".join(out)


def send(rid: int) -> str:
    r = get(rid)
    if not r:
        raise ValueError("Không tìm thấy yêu cầu")
    folders = mailbox.folder_ids()
    if not folders:
        raise RuntimeError("Chưa cấu hình ID thư mục hộp thư trong Cài đặt")
    token, msg, file_id, channel, err = _token(), "", None, "", ""
    try:
        file_id = _create_file(token, folders[0], f"{r['code']}__YEUCAU.md", r["letter_md"])
        channel, msg = "file", f"Đã tạo thư {r['code']}__YEUCAU.md trong GUI_GEMINI"
    except Exception as e:  # noqa: BLE001
        err = str(e)
    if not file_id:
        if not settings.mailbox_outbox_doc_id:
            with db.tx() as c:
                c.execute("UPDATE gemini_requests SET status='error', error=? WHERE id=?", (err[:500], rid))
            raise RuntimeError("Không tạo được file trong GUI_GEMINI (" + err[:160] + "). Tạo 1 Google Doc tên "
                               "HOP_THU_TOOL__YEUCAU trong GUI_GEMINI, chia sẻ Người chỉnh sửa cho service account và "
                               "dán ID vào Cài đặt → “Doc hộp thư đi”.")
        with db.tx() as c:
            c.execute("UPDATE gemini_requests SET status='sent', sent_at=? WHERE id=?", (db.now_iso(), rid))
        from .notebooklm import push_drive

        try:
            push_drive(settings.mailbox_outbox_doc_id, outbox_text())
        except Exception as e:  # noqa: BLE001
            with db.tx() as c:
                c.execute("UPDATE gemini_requests SET status='error', error=? WHERE id=?", (str(e)[:500], rid))
            raise
        channel, file_id = "outbox", settings.mailbox_outbox_doc_id
        msg = "Đã ghi yêu cầu vào Doc hộp thư đi HOP_THU_TOOL__YEUCAU (GUI_GEMINI)"
    with db.tx() as c:
        c.execute("UPDATE gemini_requests SET status='sent', sent_at=COALESCE(sent_at, ?), channel=?, drive_file_id=?,"
                  " error='' WHERE id=?", (db.now_iso(), channel, file_id, rid))
    db.log_sync("gemini_request", "ok", f"{r['code']}: {msg}")
    return msg + f". Tool sẽ tự kiểm tra thư trả lời mỗi 10 phút."


# ----------------------------------------------------------------- theo dõi trả lời
def check_replies() -> list[dict]:
    """Tìm thư trả lời …GOI-<n>…__XONG mới hơn thư gửi. Trả về các yêu cầu vừa được trả lời."""
    init()
    pend = db.query("SELECT * FROM gemini_requests WHERE status IN ('sent','answered','imported','updated')")
    if not pend or not mailbox.folder_ids():
        return []
    token = _token("https://www.googleapis.com/auth/drive.readonly")
    files = []
    for folder in mailbox.folder_ids():
        try:
            files += mailbox._list_files(token, folder)
        except Exception:  # noqa: BLE001
            log.exception("list mailbox %s", folder)
    done = []
    for r in pend:
        rx = re.compile(rf"GOI[-_]?{re.escape(str(r['goi']))}(?!\d)", re.I)
        # Thư BAOCAO-… có video thành phẩm mới
        seen = r.get("video_seen") or ""
        reports = [f for f in files if rx.search(f["name"]) and f["name"].upper().startswith("BAOCAO-")
                   and (f.get("modifiedTime") or "")[:19] > seen[:19]]
        if reports:
            f = max(reports, key=lambda x: x.get("modifiedTime") or "")
            try:
                vids = mailbox.parse_videos(mailbox._read(token, f))
            except Exception:  # noqa: BLE001
                log.exception("read report %s", f["name"])
                vids = {}
            with db.tx() as c:
                c.execute("UPDATE gemini_requests SET video_seen=? WHERE id=?", (f.get("modifiedTime") or "", r["id"]))
                if vids.get("final_video"):
                    c.execute("INSERT INTO jobs(kind, status, message, created_at, finished_at, notified, link)"
                              " VALUES('mailbox','done',?,?,?,0,?)",
                              (f"Gemini đã gửi video thành phẩm Gói {r['goi']} ({f['name']}). Bấm để nhập link video vào gói.",
                               db.now_iso(), db.now_iso(), f"/packages/import/{r['goi']}"))
            if vids.get("final_video"):
                if '"ghep"' in (r.get("opts_json") or "") and r["status"] == "sent":
                    with db.tx() as c:
                        c.execute("UPDATE gemini_requests SET status='answered', answered_at=?, answer_file_id=?,"
                                  " answer_name=? WHERE id=?", (db.now_iso(), f["id"], f["name"], r["id"]))
                done.append({**r, "answer_name": f["name"], "video": vids["final_video"]})
        sent = r["sent_at"] or r["created_at"]
        hits = [f for f in files if rx.search(f["name"]) and re.search(r"__(XONG|TRALOI)", f["name"], re.I)
                and (f.get("modifiedTime") or "") >= sent[:19]]
        if not hits:
            continue
        f = max(hits, key=lambda x: x.get("modifiedTime") or "")
        mod = f.get("modifiedTime") or ""
        try:  # Gemini hay tạo file trước rồi mới dán nội dung → file rỗng chưa phải là thư trả lời
            body = mailbox._read(token, f)
        except Exception:  # noqa: BLE001
            body = "x" * 500
        if len(re.sub(r"\s+", "", body)) < 200:
            log.info("Thư trả lời %s còn rỗng — chờ Gemini dán nội dung", f["name"])
            continue
        if r["status"] != "sent":
            # Thư đã trả lời trước đó: chỉ báo khi Gemini SỬA file sau lần ghi nhận trước
            seen = r.get("answer_modified") or r.get("answered_at") or ""
            if not mod or mod[:19] <= seen[:19]:
                continue
            with db.tx() as c:
                c.execute("UPDATE gemini_requests SET status='updated', answer_modified=?, answer_file_id=?, answer_name=?"
                          " WHERE id=?", (mod, f["id"], f["name"], r["id"]))
                c.execute("INSERT INTO jobs(kind, status, message, created_at, finished_at, notified, link)"
                          " VALUES('mailbox','done',?,?,?,0,?)",
                          (f"Gemini đã cập nhật thư Gói {r['goi']} ({f['name']}). Bấm để nhập lại và kiểm tra.",
                           db.now_iso(), db.now_iso(), f"/packages/import/{r['goi']}"))
            done.append({**r, "answer_name": f["name"], "updated": True})
            continue
        with db.tx() as c:
            c.execute("UPDATE gemini_requests SET status='answered', answered_at=?, answer_file_id=?, answer_name=?,"
                      " answer_modified=? WHERE id=?", (db.now_iso(), f["id"], f["name"], mod, r["id"]))
            c.execute("INSERT INTO jobs(kind, status, message, created_at, finished_at, notified, link)"
                      " VALUES('mailbox','done',?,?,?,0,?)",
                      (f"Gemini đã trả lời Gói {r['goi']} ({f['name']}). Bấm để nhập vào Gói SX và kiểm tra.",
                       db.now_iso(), db.now_iso(), f"/packages/import/{r['goi']}"))
        done.append({**r, "answer_name": f["name"]})
    if done and settings.mailbox_outbox_doc_id:
        try:
            from .notebooklm import push_drive

            push_drive(settings.mailbox_outbox_doc_id, outbox_text())
        except Exception:  # noqa: BLE001
            log.exception("refresh outbox")
    return done


def mark_imported(goi: str) -> None:
    init()
    with db.tx() as c:
        c.execute("UPDATE gemini_requests SET status='imported' WHERE goi=? AND status IN ('answered','sent','updated')",
                  (str(goi),))
