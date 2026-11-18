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
          "error": "Lỗi gửi"}
GOALS = {"follow": "Tăng người theo dõi", "view": "Tăng lượt xem", "sale": "Bán hàng (giỏ hàng)",
         "comment": "Tăng bình luận"}
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true&fields=id,name"


def init() -> None:
    with db.tx() as c:
        c.executescript(SCHEMA)


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
def _rules_for(loai: int, ads: bool) -> list[str]:
    common = [
        "Định dạng: 4 cảnh × 8 giây, dọc 9:16, mỗi cảnh 24–28 âm tiết, hook ngay giây 0; Cô Kim v3.1 "
        "(ảnh tham chiếu Drive 16ThuI9d2DGwL_8AvFyB26Sv2guOoWPZS, chỉ khóa gương mặt/trang phục/phòng trà).",
        "Không nhắc web, Link Bio, tên miền, Zalo, Shopee, Lazada, link (B.1).",
        "Không hứa may mắn, tài lộc, rước lộc, bình an, phù hộ; không hù dọa; không hứa chữa bệnh, giàu có (B.4).",
        "Hình ảnh: không lửa, hào quang, linh vật phát sáng; không chắp tay khấn vái, nhang, mâm cúng (C.7, C.8).",
        "Bật nhãn “Nội dung do AI tạo” khi đăng.",
    ]
    if loai == 3:
        return [
            "**Loại 3 – Video tăng follow, KHÔNG gắn giỏ hàng, KHÔNG SKU.**",
            "Vì video sẽ chạy **Quảng bá trả phí** nên tuyệt đối **không xem lá số, không bói toán, không Bát Tự/can chi/"
            "Nhật chủ/Dụng thần, không mời “để lại ngày sinh”** (TikTok cấm quảng cáo dịch vụ bói toán tại VN — "
            "lý do bị từ chối ngày 18/11).",
            "Nội dung nên chọn: trà sáng chữa lành, lời chúc buổi sáng, đếm ngược cuối năm, câu chuyện đời thường ấm áp, "
            "mẹo trà. Cô Kim là người pha trà, không phải thầy bói.",
            "CTA duy nhất: “bấm theo dõi Cô Kim” (có thể kèm “mỗi sáng Cô Kim pha một ấm trà cho cả nhà”).",
            *common,
        ] + (["Nội dung phải giữ được 7 ngày chạy quảng cáo: tránh mốc ngày cụ thể trong lời thoại (vd “thứ Ba 17/11”), "
              "dùng “sáng nay”, “những ngày cuối năm”."] if ads else [])
    if loai == 2:
        return ["**Loại 2 – Video sản phẩm (giỏ hàng).** Chỉ mô tả vật phẩm: chất liệu, màu, cách dùng, làm quà; không xem "
                "lá số. Tên sản phẩm đúng cột “Tên dùng trong video”. CTA: “bấm giỏ hàng góc trái”. Chèn ảnh sản phẩm thật "
                "(C.9).", *common]
    return ["**Loại 1 – Video giải mã lá số (không giỏ hàng, KHÔNG chạy quảng cáo).** Lá số lấy từ trang Lá số của "
            "TikTok Manager, không tự tính can chi. Không nối lá số với vật phẩm. CTA: “để lại ngày sinh dưới bình luận "
            "để Cô Kim giải mã”.", *common]


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


def build_letter(req: dict) -> str:
    o = req["opts"]
    loai = int(o.get("loai") or 3)
    ads = bool(o.get("ads"))
    goi = req["goi"]
    answer = f"{req['code']}__XONG.md"
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
        *[f"- {r}" for r in _rules_for(loai, ads)], "",
    ]
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
        "anh_4_canh:",
        '  canh_1_0_8s: "<ID ảnh Drive>"',
        '  canh_2_8_16s: "<ID ảnh Drive>"',
        '  canh_3_16_24s: "<ID ảnh Drive>"',
        '  canh_4_24_32s: "<ID ảnh Drive>"',
        "",
        f"# Phiếu gói {goi} — <tiêu đề>",
        "",
        "## Lời thoại 4 cảnh × 8 giây",
        "1. (26 âm tiết) <lời thoại cảnh 1>",
        "2. (27 âm tiết) <lời thoại cảnh 2>",
        "3. (26 âm tiết) <lời thoại cảnh 3>",
        "4. (25 âm tiết) <lời thoại cảnh 4>",
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
        "## Prompt tạo video 8 giây (Veo / Flow)",
        "1. **Cảnh 1 (0–8s | ảnh …)**: <prompt tiếng Anh; chứa NGUYÊN VĂN lời thoại cảnh 1 trong ngoặc kép; giọng nữ miền Nam vào ngay giây 0; NO background music>",
        "2. **Cảnh 2 (8–16s | ảnh …)**: <prompt cảnh 2>",
        "3. **Cảnh 3 (16–24s | ảnh …)**: <prompt cảnh 3>",
        "4. **Cảnh 4 (24–32s | ảnh …)**: <prompt cảnh 4>",
        "",
        "nhan_video:",
        f"  goi: {goi}",
        f"  loai: {loai}",
        "```", "",
        "Sau khi trả lời, TikTok Manager sẽ tự phát hiện thư (tối đa 10 phút) và báo anh Nhơn nhập vào Gói SX để kiểm tra.",
    ]
    return "\n".join(x for x in lines if x is not None)


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
    return "\n".join(head + (body or ["(Không có yêu cầu nào đang chờ.)"]))


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
    pend = db.query("SELECT * FROM gemini_requests WHERE status='sent'")
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
        sent = r["sent_at"] or r["created_at"]
        hits = [f for f in files if rx.search(f["name"]) and re.search(r"__(XONG|TRALOI)", f["name"], re.I)
                and (f.get("modifiedTime") or "") >= sent[:19]]
        if not hits:
            continue
        f = max(hits, key=lambda x: x.get("modifiedTime") or "")
        with db.tx() as c:
            c.execute("UPDATE gemini_requests SET status='answered', answered_at=?, answer_file_id=?, answer_name=?"
                      " WHERE id=?", (db.now_iso(), f["id"], f["name"], r["id"]))
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
        c.execute("UPDATE gemini_requests SET status='imported' WHERE goi=? AND status IN ('answered','sent')", (str(goi),))
