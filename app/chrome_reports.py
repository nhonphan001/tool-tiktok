"""Đánh giá chuyên sâu bằng Claude in Chrome (TikTok Studio / Promote).

Vòng lặp:
1. Tool soạn yêu cầu cho 1 gói đã đăng (video_request) hoặc cho cả tuần (week_request).
2. Anh Nhơn dán vào Claude in Chrome. Claude in Chrome đọc Studio ở chế độ chỉ đọc và trả về file .md có khối JSON.
3. Anh tải file .md lên tool (add). Báo cáo được lưu theo gói và đưa vào dữ liệu lập chiến lược (recent_for_prompt).
Không gọi AI, không tốn token.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from . import db
from .config import settings

VN = timezone(timedelta(hours=7))
MAX_BODY = 200_000

SAFETY = """## Quy tắc an toàn (bắt buộc)
- **Chỉ đọc.** Không bấm: Quảng bá, tạo/tạm dừng/gia hạn chiến dịch, nạp tiền, xoá/sửa video, đổi quyền riêng tư, trả lời bình luận.
- Không chép số thẻ, số dư ví, email, số điện thoại, tên tài khoản của người bình luận (chỉ ghi nội dung bình luận đã ẩn danh).
- Nếu trang hỏi đăng nhập, xác minh hoặc cấp quyền: dừng lại và báo anh Nhơn.
- Số đọc từ biểu đồ ghi "~". Số không có ghi "không có", **không đoán**.
- Ghi rõ **[Dữ kiện]** (số thấy trên trang) và **[Giả thuyết]** (suy luận)."""


def init() -> None:
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS chrome_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, pid INTEGER, video_id TEXT DEFAULT '',
            title TEXT, body TEXT)""")
        cols = {r[1] for r in c.execute("PRAGMA table_info(chrome_reports)").fetchall()}
        for col, typ in (("run_started", "TEXT DEFAULT ''"), ("run_finished", "TEXT DEFAULT ''"),
                         ("duration_min", "REAL"), ("tokens_est", "INTEGER"), ("tokens_exact", "INTEGER"),
                         ("mode", "TEXT DEFAULT ''")):
            if col not in cols:
                c.execute(f"ALTER TABLE chrome_reports ADD COLUMN {col} {typ}")


def _now() -> str:
    return datetime.now(VN).strftime("%d/%m/%Y %H:%M")


def clock_text() -> str:
    """Giờ máy chủ cho skill ghi mốc bắt đầu/kết thúc (trang /danh-gia/gio)."""
    n = datetime.now(VN)
    return f"TikTok Manager · giờ Việt Nam: {n:%d/%m/%Y %H:%M:%S}\nISO: {n.isoformat(timespec='seconds')}\n"


def _video(video_id: str) -> dict:
    if not video_id:
        return {}
    return db.query_one("SELECT * FROM videos WHERE id=?", (video_id,)) or {}


def _ads_line() -> str:
    if settings.ads_paused:
        return ("Kênh đang trong **tuần thử nghiệm KHÔNG quảng bá** (từ 25/11/2026). Vì vậy video này phải là **số tự nhiên**. "
                "Vào trang https://www.tiktok.com/promote/web/dashboard → Lịch sử đặt lệnh, xác nhận video **không** nằm trong lệnh nào. "
                "Nếu có lệnh thì ghi lại số trả phí và tách phần tự nhiên.")
    return ("Kiểm tra trang https://www.tiktok.com/promote/web/dashboard xem video có nằm trong lệnh Quảng bá không. "
            "Nếu có thì ghi số trả phí (view, follower, đã chi) và tách phần tự nhiên = tổng − trả phí.")


def video_request(p: dict) -> str:
    """Yêu cầu đánh giá 1 video đã đăng (gói có video_id)."""
    from . import packages

    ns = packages.n_scenes(p)
    v = _video(p.get("video_id") or "")
    link = v.get("share_url") or (f"https://www.tiktok.com/@{_username()}/video/{p['video_id']}" if p.get("video_id") else
                                  "(chưa gắn video: tìm theo caption bên dưới)")
    posted = (datetime.fromtimestamp(v["create_time"], VN).strftime("%d/%m/%Y %H:%M") if v.get("create_time") else "không rõ")
    loai = int(p.get("loai") or 1)
    loai_txt = {1: "Loại 1: giải mã lá số (không quảng cáo)", 2: "Loại 2: giỏ hàng", 3: "Loại 3: trà sáng / chữa lành"}[loai]
    scenes = "\n".join(f"{i}. {(p.get(f'scene{i}') or '').strip()}" for i in range(1, ns + 1) if (p.get(f"scene{i}") or "").strip())
    goi = p.get("goi") or p["id"]
    return f"""# Yêu cầu cho Claude in Chrome: đánh giá chuyên sâu Gói {goi}

**Video:** {link}
**Đăng lúc:** {posted} · **{loai_txt}** · {ns} cảnh × {packages.clip_seconds()} giây
**Kênh:** @{_username()} (Tiệm Trà Giải Mã _ Cô Kim). Anh Nhơn đã đăng nhập sẵn TikTok Studio.
**Thời điểm yêu cầu:** {_now()}

{SAFETY}

## Kịch bản gốc (để đối chiếu với video thật)
- Chữ trên hình: {(p.get('on_screen') or '—').strip()}
- Caption: {(p.get('caption') or '—').strip()}
- Bình luận ghim: {(p.get('pinned') or '—').strip()}
- Lời thoại:
{scenes or '—'}

## Phần 1: Quảng bá
{_ads_line()}

## Phần 2: Số liệu TikTok Studio (Phân tích → video này)
1. Lượt xem, **người xem duy nhất**, thích, bình luận, chia sẻ, lưu, **follower mới**, tổng thời gian phát, thời gian xem trung bình, tỷ lệ xem hết.
2. **Đường giữ chân:** % còn xem ở 0:01, 0:02, 0:03, 0:05, 0:08, 0:10, 0:15, 0:20, 0:30, 0:45, 0:60 (những mốc có trong độ dài video); giây nhiều lượt thích nhất; ghi chú TikTok ("hầu hết người xem dừng ở…").
3. **Nguồn lưu lượng (%):** Đề xuất, Đã follow, Hồ sơ, Tìm kiếm (kèm **các từ khoá tìm kiếm**), Âm thanh, Khác.
4. **Lượt xem theo giờ và theo ngày** (rê chuột biểu đồ): giờ đạt đỉnh, giờ gần 0.
5. Người xem mới / quay lại; follower / không follower; tuổi; giới tính; vùng.
6. **Bình luận:** số lượng, nội dung (ẩn danh), có ai để lại năm sinh/ngày sinh/con giáp không, có câu hỏi nào lặp lại không.

## Phần 3: Xem video thật (mở link video)
1. **Khung hình 0–2 giây:** mô tả đúng những gì thấy (ánh sáng, chuyển động, có chữ lớn giữa màn hình không, câu đầu tiên nói gì, nói ngay giây 0 hay có khoảng lặng).
2. **Câu kêu gọi** (follow / comment năm sinh / giỏ hàng) xuất hiện ở giây thứ mấy, bằng lời nói hay chữ.
3. Video có khớp kịch bản gốc không (lời thoại, chữ trên hình); có lỗi hình (mặt Cô Kim đổi giữa cảnh, ánh sáng khác nhau giữa cảnh, chữ sai chính tả, tiếng lặng dài) không.
4. Có nhãn "Nội dung do AI tạo" không; có nhãn "nội dung thương mại" không.

## Phần 4: Đánh giá và đề xuất
1. Video mất người xem ở đâu và vì sao (dẫn số giữ chân + mô tả khung hình ở thời điểm đó).
2. So với 3 video gần nhất cùng Loại trên kênh (lượt xem, giữ chân giây 2, follow / view, bình luận / 1.000 view).
3. **3 thay đổi cụ thể** cho video cùng dạng tiếp theo (khung hình 0, câu đầu, vị trí câu kêu gọi, caption, giờ đăng).

## Cách trả kết quả
Một file Markdown tên `danh-gia-goi-{goi}-<ngày>.md` gồm: tóm tắt 5 dòng; các bảng Phần 1–3; Phần 4; mục "Dữ liệu còn thiếu"; cuối file là khối JSON:

```json
{{"snapshot_at": "", "goi": "{goi}", "video_id": "{p.get('video_id') or ''}", "posted_at": "", "duration_s": 0, "loai": {loai},
  "promoted": false, "promo": {{"spent": 0, "views": 0, "followers": 0}},
  "metrics": {{"views": 0, "unique_viewers": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0, "new_followers": 0,
              "avg_watch_s": 0, "completion_rate": 0}},
  "retention_pct": {{"1": 0, "2": 0, "3": 0, "5": 0, "10": 0}},
  "traffic_source_pct": {{"for_you": 0, "following": 0, "profile": 0, "search": 0}}, "search_queries": [],
  "views_by_hour_peak": "", "audience_age_pct": {{}}, "audience_gender_pct": {{}},
  "hook": {{"first_line": "", "speech_at_0s": null, "big_center_text": null, "bright_motion": null}},
  "cta_second": null, "comments_with_birth_year": 0, "top_3_changes": []}}
```
"""


def week_request(days: int = 7) -> str:
    """Yêu cầu tổng hợp cả kênh trong N ngày qua (so sánh các video tự nhiên)."""
    from . import packages

    since = int((datetime.now(VN) - timedelta(days=days)).timestamp())
    rows = []
    for p in packages.all_packages():
        v = _video(p.get("video_id") or "")
        if v and (v.get("create_time") or 0) >= since:
            t = datetime.fromtimestamp(v["create_time"], VN).strftime("%d/%m %H:%M")
            rows.append(f"| {p.get('goi') or p['id']} | {t} | Loại {p.get('loai')} | {packages.n_scenes(p)} cảnh | "
                        f"{(p.get('title') or '')[:50]} | {v.get('share_url') or p['video_id']} |")
    table = ("| Gói | Đăng | Loại | Cảnh | Tiêu đề | Link |\n|---|---|---|---|---|---|\n" + "\n".join(rows)) if rows else \
        "(Tool chưa gắn video nào trong khoảng này: lấy tất cả video đăng trong " + str(days) + " ngày qua trên Studio.)"
    return f"""# Yêu cầu cho Claude in Chrome: đánh giá tuần ({days} ngày qua) kênh @{_username()}

**Thời điểm yêu cầu:** {_now()}. Anh Nhơn đã đăng nhập TikTok Studio và trang Promote.
{"**Đây là tuần thử nghiệm KHÔNG quảng bá** — mục tiêu là đo sức lan toả tự nhiên của nội dung." if settings.ads_paused else ""}

{SAFETY}

## Video cần đánh giá
{table}

## Việc cần làm
1. Trang Promote → Lịch sử đặt lệnh: liệt kê mọi lệnh trong {days} ngày qua (video, đã chi, view, follower). Đánh dấu video nào **tự nhiên 100%**.
2. Với **từng video**: lượt xem, người xem duy nhất, follower mới, thích, bình luận, lưu, chia sẻ, giữ chân giây 2 và giây 10, thời gian xem trung bình, tỷ lệ xem hết, nguồn lưu lượng (Đề xuất / Đã follow / Tìm kiếm + từ khoá), giờ đạt đỉnh view.
3. Trang tổng quan Studio: follower đầu kỳ / cuối kỳ, follower mới theo ngày, giờ follower online nhiều nhất (Phân tích → Người theo dõi).
4. So sánh theo nhóm: **Loại 1 vs Loại 3**; **đăng 11:00 vs 12:30 vs 19:00**; **4 cảnh vs 7 cảnh**; **video gắn dịp vs thường xanh**.
5. Bình luận: tổng số, số bình luận có năm sinh/con giáp, câu hỏi lặp lại (ẩn danh).
6. Kết luận: 3 mô thức thắng **tự nhiên**, 3 điều nên bỏ, đề xuất giờ đăng và dạng video cho tuần sau.

## Cách trả kết quả
File `danh-gia-tuan-<ngày>.md`: tóm tắt 5 dòng; bảng từng video; bảng so sánh nhóm; kết luận; "Dữ liệu còn thiếu"; cuối file khối JSON
`{{"snapshot_at": "", "followers_start": 0, "followers_end": 0, "videos": [{{"goi": "", "video_id": "", "posted_at": "", "loai": 0, "scenes": 0, "promoted": false, "views": 0, "unique_viewers": 0, "new_followers": 0, "likes": 0, "comments": 0, "saves": 0, "retention_2s": 0, "retention_10s": 0, "avg_watch_s": 0, "peak_hour": ""}}], "winners": [], "drop": [], "next_week": ""}}`.
"""


def _username() -> str:
    acc = db.get_active_account() or {}
    return acc.get("username") or "tiemtragiaima"


def add(body: str, title: str = "", pid: int | None = None, video_id: str = "") -> int:
    init()
    body = (body or "")[:MAX_BODY]
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        title = (m.group(1).strip() if m else "Đánh giá Claude in Chrome")[:200]
    if not video_id:
        m = re.search(r'"video_id"\s*:\s*"(\d{8,})"', body)
        video_id = m.group(1) if m else ""
    run = run_info(body)
    with db.tx() as c:
        cur = c.execute("INSERT INTO chrome_reports (created_at, pid, video_id, title, body, run_started, run_finished,"
                        " duration_min, tokens_est, tokens_exact, mode) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (db.now_iso(), pid, video_id, title, body, run["started_at"], run["finished_at"],
                         run["duration_min"], run["tokens_est"], run["tokens_exact"], run["mode"]))
        return cur.lastrowid


def _int(x) -> int | None:
    try:
        return int(float(str(x).replace(".", "").replace(",", ""))) if x not in (None, "") else None
    except ValueError:
        return None


def run_info(body: str) -> dict:
    """Thông tin lần chạy skill: giờ bắt đầu/kết thúc, thời lượng, token (khối "run" trong JSON).
    Thiếu số token của skill → ước tính phần báo cáo (đầu ra) theo độ dài: ~1 token / 3 ký tự tiếng Việt."""
    data = extract_json(body) or {}
    r = data.get("run") or {}
    tok = r.get("tokens_est") or {}
    total = _int(tok.get("total")) if isinstance(tok, dict) else _int(tok)
    started, finished = str(r.get("started_at") or ""), str(r.get("finished_at") or "")
    dur = r.get("duration_min")
    if dur in (None, "") and started and finished:
        try:
            a, b = datetime.fromisoformat(started), datetime.fromisoformat(finished)
            dur = round((b - a).total_seconds() / 60, 1)
        except ValueError:
            dur = None
    try:
        dur = float(dur) if dur not in (None, "") else None
    except (TypeError, ValueError):
        dur = None
    return {"started_at": started, "finished_at": finished, "duration_min": dur,
            "tokens_est": total if total else round(len(body or "") / 3), "tokens_exact": _int(r.get("exact_tokens")),
            "tokens_from_skill": bool(total), "mode": str(data.get("mode") or "")}


_LIST_COLS = "id, created_at, pid, video_id, title, run_started, run_finished, duration_min, tokens_est, tokens_exact, mode"


def list_reports(pid: int | None = None, limit: int = 50) -> list[dict]:
    init()
    if pid:
        return db.query(f"SELECT {_LIST_COLS} FROM chrome_reports WHERE pid=? ORDER BY id DESC LIMIT ?", (pid, limit))
    return db.query(f"SELECT {_LIST_COLS} FROM chrome_reports ORDER BY id DESC LIMIT ?", (limit,))


def get(rid: int) -> dict | None:
    init()
    return db.query_one("SELECT * FROM chrome_reports WHERE id=?", (rid,))


def delete(rid: int) -> None:
    with db.tx() as c:
        c.execute("DELETE FROM chrome_reports WHERE id=?", (rid,))


def extract_json(body: str) -> dict | None:
    """Khối ```json cuối cùng trong báo cáo (nếu đọc được)."""
    blocks = re.findall(r"```json\s*(.*?)```", body or "", re.S)
    for b in reversed(blocks):
        try:
            return json.loads(b)
        except ValueError:
            continue
    return None


def _summary_part(body: str, limit: int) -> str:
    m = re.search(r"^#{1,3}[^\n]*(?:Tóm tắt|Tóm tắt nhanh)[^\n]*$", body, re.M | re.I)
    if not m:
        return body[:limit]
    rest = body[m.end():]
    nxt = re.search(r"^#{1,3}\s", rest, re.M)
    return (rest[:nxt.start()] if nxt else rest).strip()[:limit]


def recent_for_prompt(n: int = 5, per: int = 2500, total: int = 10000) -> str:
    """Tóm tắt + JSON của N báo cáo gần nhất để đưa vào dữ liệu lập chiến lược."""
    init()
    out, size = [], 0
    for r in db.query("SELECT * FROM chrome_reports ORDER BY id DESC LIMIT ?", (n,)):
        data = extract_json(r["body"])
        part = f"--- {r['title']} (tải lên {r['created_at'][:16]}) ---\n" + _summary_part(r["body"], per // 2)
        if data is not None:
            part += "\nJSON: " + json.dumps(data, ensure_ascii=False)[:per]
        if size + len(part) > total:
            break
        out.append(part)
        size += len(part)
    return "\n\n".join(out)


def context_md(days: int = 14) -> str:
    """Trang ngữ cảnh cho Claude in Chrome (skill tiktok-studio-quet): gói ↔ video, kịch bản, số API của tool, quy tắc."""
    from . import analytics, packages

    acc = db.get_active_account() or {}
    oid = acc.get("open_id") or ""
    snap = db.query_one("SELECT taken_at, follower_count, likes_count, video_count FROM account_snapshots WHERE open_id=?"
                        " AND follower_count IS NOT NULL ORDER BY taken_at DESC LIMIT 1", (oid,)) or {}
    since = datetime.now(VN) - timedelta(days=days)
    vids = [v for v in (analytics.get_videos(oid) if oid else []) if v.get("posted_local") and v["posted_local"] >= since]
    by_vid = {p.get("video_id"): p for p in packages.all_packages() if p.get("video_id")}
    out = [f"# TikTok Manager: ngữ cảnh cho Claude in Chrome ({_now()})", "",
           f"- Kênh: @{acc.get('username') or 'tiemtragiaima'} · follower theo API lần quét gần nhất: "
           f"{snap.get('follower_count', 'không rõ')} ({str(snap.get('taken_at') or '')[:16]})",
           f"- Trạng thái quảng bá: {'TUẦN THỬ NGHIỆM KHÔNG QUẢNG BÁ' if settings.ads_paused else 'có thể có Quảng bá'}",
           f"- Khoảng xem: {days} ngày qua · {len(vids)} video", "",
           "## Bối cảnh quảng bá", settings.ads_context.strip() or "(trống)", "",
           "## Video và gói tương ứng",
           "| Video ID | Đăng | Gói | Loại | Cảnh | View (API) | Thích | BL | Chia sẻ | Tiêu đề |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for v in vids:
        p = by_vid.get(v["id"]) or {}
        out.append(f"| {v['id']} | {v['posted_str']} | {p.get('goi') or '—'} | {p.get('loai') or '—'} | "
                   f"{packages.n_scenes(p) if p else '—'} | {v.get('view_count') or 0} | {v.get('like_count') or 0} | "
                   f"{v.get('comment_count') or 0} | {v.get('share_count') or 0} | {(v.get('label') or '').replace('|', '/')[:60]} |")
    out += ["", "## Kịch bản các gói đã gắn video"]
    for v in vids:
        p = by_vid.get(v["id"])
        if not p:
            continue
        ns = packages.n_scenes(p)
        out += [f"### Gói {p.get('goi')} · video {v['id']} · Loại {p.get('loai')} · {ns} cảnh",
                f"- Link: {v.get('share_url') or ''}",
                f"- Chữ trên hình: {(p.get('on_screen') or '—').strip()}",
                f"- Caption ({len((p.get('caption') or '').strip())} ký tự): {(p.get('caption') or '—').strip()}",
                f"- Bình luận ghim: {(p.get('pinned') or '—').strip()}"]
        out += [f"  {i}. {(p.get(f'scene{i}') or '').strip()}" for i in range(1, ns + 1) if (p.get(f"scene{i}") or "").strip()]
        out.append("")
    try:
        from . import consensus

        sus = consensus.promo_suspects(oid)
    except Exception:  # noqa: BLE001
        sus = []
    out += ["## Video nghi được Quảng bá (từ chuỗi API) — BẮT BUỘC kiểm trang Quảng bá cho các video này"] + \
           [f"- {s['video_id']} · {s['posted']} · {'; '.join(s['reasons'])}" for s in sus] + ([] if sus else ["- (không có)"]) + [""]
    rows = list_reports(limit=5)
    out += ["## Báo cáo Claude in Chrome đã lưu (5 gần nhất)"] + \
           [f"- {r['created_at'][:16]} · {r['title']}" for r in rows] + ([] if rows else ["- (chưa có)"])
    out += ["", "## Quy tắc hiệu suất để đối chiếu video thật",
            "H1 khung 0 sáng, có chuyển động, nói ngay giây 0 · H2 chữ hook lớn ≤ 70 ký tự · H3 câu kêu gọi ở cuối cảnh 1 (giây 3–8) · "
            "H4 caption ≤ 250 ký tự · H5 không chữ chỉ giờ · H6 cùng bối cảnh/ánh sáng mọi cảnh."]
    return "\n".join(out)
