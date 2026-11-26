"""Bộ phận Kiểm toán Quy trình & Tổng duyệt Đầu cuối (/tong-duyet).

Thay anh Nhơn tự kiểm tra từng khâu:
- Tự động quét 6 chốt kiểm toán trên toàn hệ thống (0 token AI):
  1. Sức khoẻ TikTok Display API (VPS — Tầng 1, 4 lần/ngày)
  2. Nhịp quét TikTok Studio & chống trùng lặp (An — Tầng 2/3)
  3. Chất lượng Gói SX & tuân thủ Bộ quy tắc Bản 2 + chống trùng chủ đề
  4. Chăm sóc khách & bình luận xin lá số chưa trả lời (`/binh-luan`)
  5. Hộp thư cập nhật cấu hình chờ duyệt (`/hop-thu`)
  6. Chi phí AI Studio (Gemini API) & hiệu suất hạn mức quét
- Gom thành 1 Bản tin Tổng duyệt Xanh / Vàng / Đỏ kèm lô Ý tưởng đầu vào chờ duyệt.
- Lưu lịch sử các lần kiểm toán & mốc anh Nhơn ký duyệt (`audit_logs`).
"""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from . import chrome_reports, comment_stats, consensus, db, ideation
from .config import settings

VN = timezone(timedelta(hours=7))

LEVEL_LABELS = {
    "ok": "🟢 Ổn định",
    "warn": "🟡 Cần lưu ý",
    "error": "🔴 Cần xử lý",
}


def init() -> None:
    ideation.init()
    with db.tx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            kind TEXT DEFAULT 'hang_ngay',
            agent TEXT DEFAULT 'system',
            overall TEXT DEFAULT 'ok',
            summary_md TEXT DEFAULT '',
            snapshot_json TEXT DEFAULT '',
            approved_at TEXT DEFAULT '',
            decision_note TEXT DEFAULT ''
        )""")


def _hours_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        t = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if not t.tzinfo:
            t = t.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - t).total_seconds() / 3600, 1)
    except ValueError:
        return None


def _check_display_api() -> dict:
    last = db.query_one("SELECT started_at, finished_at, status, message, videos_count FROM scans ORDER BY id DESC LIMIT 1")
    since_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).replace(microsecond=0).isoformat()
    errs = (db.query_one("SELECT COUNT(*) AS n FROM scans WHERE status='error' AND started_at>=?", (since_24h,)) or {}).get("n", 0)
    if not last:
        return {
            "code": "display_api", "name": "Tầng 1 · Display API (VPS 4 lần/ngày)",
            "level": "warn", "headline": "Chưa có lượt quét API nào",
            "detail": "Kết nối kênh TikTok ở mục Cài đặt hoặc bấm Quét ngay để lấy dữ liệu gốc.",
            "action_label": "Mở Cài đặt", "action_url": "/settings",
        }
    hrs = _hours_since(last.get("finished_at") or last.get("started_at"))
    if last.get("status") != "ok":
        return {
            "code": "display_api", "name": "Tầng 1 · Display API (VPS 4 lần/ngày)",
            "level": "error", "headline": f"Lần quét gần nhất bị lỗi ({errs} lỗi/24h)",
            "detail": str(last.get("message") or "Lỗi không xác định")[:180],
            "action_label": "Xem nhật ký", "action_url": "/settings",
        }
    if hrs is not None and hrs > 8.5:
        return {
            "code": "display_api", "name": "Tầng 1 · Display API (VPS 4 lần/ngày)",
            "level": "warn", "headline": f"Đã {hrs} giờ chưa có lượt quét mới",
            "detail": f"Lần gần nhất: {last.get('videos_count') or 0} video ({last.get('message')}). Kiểm tra scheduler trên VPS.",
            "action_label": "Xem Cài đặt", "action_url": "/settings",
        }
    return {
        "code": "display_api", "name": "Tầng 1 · Display API (VPS 4 lần/ngày)",
        "level": "ok", "headline": f"Ổn định · cách đây {hrs if hrs is not None else '—'} giờ ({last.get('videos_count') or 0} video)",
        "detail": f"Chạy tự động 0 token (05:00, 11:00, 17:00, 23:00). Lỗi 24h qua: {errs}.",
        "action_label": "Xem Tổng quan", "action_url": "/",
    }


def _check_studio_layer() -> dict:
    reps = chrome_reports.list_reports(limit=5)
    if not reps:
        return {
            "code": "studio_scan", "name": "Tầng 2/3 · Quét Studio & Chống trùng lặp (An)",
            "level": "warn", "headline": "Chưa có báo cáo TikTok Studio nào",
            "detail": "Chạy An quét nhanh Tầng 2 để tách số tự nhiên và cập nhật Báo cáo đồng thuận.",
            "action_label": "Mở Đánh giá", "action_url": "/danh-gia",
        }
    latest = reps[0]
    hrs = _hours_since(latest.get("created_at"))
    dur = latest.get("duration_min")
    warns = []
    if hrs is not None and hrs > 36:
        warns.append(f"Báo cáo gần nhất đã cách {hrs} giờ (>36h)")
    if dur and latest.get("mode") == "hang_ngay" and float(dur) > 15:
        warns.append(f"Thời lượng quét hằng ngày {dur} phút (>15 phút — kiểm tra tránh quét lặp video cũ)")
    diffs = consensus.diffs()
    big_diff = [d for d in diffs if isinstance(d.get("views_pct"), (int, float)) and abs(d["views_pct"]) > 25]
    if big_diff:
        warns.append(f"{len(big_diff)} video lệch view API ↔ Studio > 25% (thường do video mới <24h hoặc Studio làm tròn)")

    if warns:
        return {
            "code": "studio_scan", "name": "Tầng 2/3 · Quét Studio & Chống trùng lặp (An)",
            "level": "warn", "headline": warns[0],
            "detail": " · ".join(warns),
            "action_label": "Xem Đồng thuận", "action_url": "/dong-thuan",
        }
    dur_txt = f" · {dur} phút" if dur else ""
    return {
        "code": "studio_scan", "name": "Tầng 2/3 · Quét Studio & Chống trùng lặp (An)",
        "level": "ok", "headline": f"Đúng nhịp · {latest.get('title', '')[:52]} ({hrs}h trước{dur_txt})",
        "detail": f"Đã đồng bộ {len(diffs)} video với Báo cáo đồng thuận. Cổng API cho An: {'đã bật' if settings.api_token else 'chưa đặt API_TOKEN'}.",
        "action_label": "Xem Đồng thuận", "action_url": "/dong-thuan",
    }


def _check_packages_qa() -> tuple[dict, list[dict]]:
    from . import packages

    packages.init()
    all_pkgs = packages.all_packages()
    active_pkgs = [p for p in all_pkgs if p.get("status") != "da_dang"]
    ready_to_post = [p for p in active_pkgs if p.get("status") == "da_dung"]

    flagged: list[dict] = []
    err_count = 0
    warn_count = 0
    year_counter: Counter[str] = Counter()
    for p in active_pkgs:
        chk = packages.check(p)
        errs = [i["msg"] for i in chk["items"] if i["level"] == "error"]
        warns = [i["msg"] for i in chk["items"] if i["level"] == "warn"]
        if errs:
            err_count += 1
        if warns:
            warn_count += 1
        # Dò trùng năm sinh trong các gói chưa đăng (Loại 1)
        if int(p.get("loai") or 0) == 1:
            m = re.search(r"\b(19[5-9]\d|200\d)\b", f"{p.get('title') or ''} {p.get('caption') or ''}")
            if m:
                year_counter[m.group(1)] += 1
        if errs or warns or p.get("status") == "da_dung":
            flagged.append({
                "id": p["id"],
                "goi": p.get("goi") or p["id"],
                "title": (p.get("title") or "(Chưa đặt tiêu đề)")[:65],
                "loai": p.get("loai"),
                "status": packages.STATUS.get(p.get("status") or "", p.get("status") or ""),
                "is_ready": p.get("status") == "da_dung",
                "errors": errs[:3],
                "warns": warns[:3],
            })

    dup_years = [y for y, cnt in year_counter.items() if cnt >= 2]
    if err_count > 0:
        level = "error"
        headline = f"{err_count} gói chưa đăng có lỗi đỏ · {len(ready_to_post)} gói sẵn sàng đăng"
    elif warn_count > 0 or dup_years:
        level = "warn"
        parts = []
        if warn_count:
            parts.append(f"{warn_count} gói có cảnh báo Bộ quy tắc V2")
        if dup_years:
            parts.append(f"trùng năm sinh chưa đăng: {', '.join(dup_years)}")
        if ready_to_post:
            parts.append(f"{len(ready_to_post)} gói chờ đăng")
        headline = " · ".join(parts)
    else:
        level = "ok"
        headline = f"Sạch quy tắc · {len(ready_to_post)} gói sẵn sàng đăng / {len(active_pkgs)} gói đang xử lý"

    detail = (
        f"Đã kiểm toán {len(active_pkgs)} gói chưa đăng (tuân thủ B.1–B.4, đọc đủ 4 số năm sinh, dùng 'bình luận', H1–H6)."
        + (f" Phát hiện trùng năm sinh ở gói chờ: {', '.join(dup_years)}." if dup_years else "")
    )
    check = {
        "code": "packages_qa", "name": "QA Kịch bản & Gói sản xuất (Bộ quy tắc V2)",
        "level": level, "headline": headline, "detail": detail,
        "action_label": "Mở Gói SX", "action_url": "/packages",
    }
    return check, flagged[:12]


def _check_comments() -> dict:
    d = comment_stats.dashboard_data(role="all")
    k = d["kpi"]
    if k["total"] == 0:
        return {
            "code": "comments", "name": "Chăm sóc khách & Bình luận (/binh-luan)",
            "level": "warn", "headline": "Chưa có dữ liệu bình luận trong tool",
            "detail": "Chạy An quét tiktokstudio/comment để tự động lọc ca xin lá số chưa trả lời.",
            "action_label": "Mở Bình luận", "action_url": "/binh-luan",
        }
    unrep_ask = int(k.get("xin_la_so_unreplied") or 0)
    if unrep_ask >= 4:
        level = "error"
    elif unrep_ask >= 1:
        level = "warn"
    else:
        level = "ok"
    return {
        "code": "comments", "name": "Chăm sóc khách & Bình luận (/binh-luan)",
        "level": level,
        "headline": f"{unrep_ask} ca xin lá số chưa trả lời · tỷ lệ TL {k['reply_rate_pct']}% ({k['replied']}/{k['viewer_total']})",
        "detail": f"Tổng {k['total']} bình luận trên {k['video_count']} video. Ưu tiên trả lời trước các ca có đủ ngày sinh.",
        "action_label": f"Xử lý {unrep_ask} ca ngay" if unrep_ask else "Xem Bình luận",
        "action_url": "/binh-luan?role=viewer&status=unreplied&cat=xin_la_so#chi-tiet" if unrep_ask else "/binh-luan",
    }


def _check_mailbox() -> dict:
    try:
        from . import mail_notes

        mail_notes.init()
        pend = int(mail_notes.pending_count() or 0)
    except Exception:  # noqa: BLE001
        pend = 0
    if pend > 0:
        return {
            "code": "mailbox", "name": "Hộp thư cập nhật cấu hình (/hop-thu)",
            "level": "warn", "headline": f"{pend} đề xuất cập nhật từ Gemini/Claude đang chờ duyệt",
            "detail": "Kiểm tra các mục chờ áp dụng hoặc bỏ qua để hộp thư sạch.",
            "action_label": "Mở Hộp thư", "action_url": "/hop-thu",
        }
    return {
        "code": "mailbox", "name": "Hộp thư cập nhật cấu hình (/hop-thu)",
        "level": "ok", "headline": "Không có đề xuất cấu hình bị tồn đọng",
        "detail": "Mọi thư đánh giá & cập nhật đã được xử lý gọn.",
        "action_label": "Xem Hộp thư", "action_url": "/hop-thu",
    }


def _check_cost_efficiency() -> dict:
    since_7d = (datetime.now(timezone.utc) - timedelta(days=7)).replace(microsecond=0).isoformat()
    row = db.query_one(
        "SELECT COUNT(*) AS calls, COALESCE(SUM(total_tokens), 0) AS tokens, COALESCE(SUM(cost_usd), 0) AS cost"
        " FROM ai_usage WHERE created_at>=?",
        (since_7d,),
    ) or {"calls": 0, "tokens": 0, "cost": 0.0}
    cost_usd = float(row.get("cost") or 0.0)
    cost_vnd = round(cost_usd * settings.usd_vnd_rate)
    level = "warn" if cost_usd >= 5.0 else "ok"
    return {
        "code": "cost_ai", "name": "Chi phí AI Studio (Gemini API · 7 ngày)",
        "level": level,
        "headline": f"≈ {cost_vnd:,} ₫ (${cost_usd:.3f}) · {row['calls']} lượt gọi".replace(",", "."),
        "detail": f"Tổng {int(row['tokens']):,} token trong 7 ngày qua. Mẫu trả lời nhanh /khach-hang và kiểm toán đều chạy 0 token.".replace(",", "."),
        "action_label": "Xem Chiến lược", "action_url": "/strategy",
    }


def run_audit() -> dict:
    """Chạy toàn bộ 6 chốt kiểm toán theo thời gian thực (0 token) cho trang `/tong-duyet`."""
    init()
    c1 = _check_display_api()
    c2 = _check_studio_layer()
    c3, flagged_pkgs = _check_packages_qa()
    c4 = _check_comments()
    c5 = _check_mailbox()
    c6 = _check_cost_efficiency()
    checks = [c1, c2, c3, c4, c5, c6]

    n_err = sum(1 for c in checks if c["level"] == "error")
    n_warn = sum(1 for c in checks if c["level"] == "warn")
    n_ok = sum(1 for c in checks if c["level"] == "ok")
    overall = "error" if n_err else ("warn" if n_warn else "ok")

    pending_ideas = ideation.list_ideas("pending", limit=8)
    logs = db.query("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 10")
    latest_an_note = next((x for x in logs if x.get("agent") == "antigravity"), None)
    last_approved = next((x for x in logs if x.get("approved_at")), None)

    return {
        "generated_at": datetime.now(VN).strftime("%d/%m/%Y %H:%M"),
        "overall": overall,
        "overall_label": LEVEL_LABELS[overall],
        "counts": {"error": n_err, "warn": n_warn, "ok": n_ok, "total": len(checks)},
        "checks": checks,
        "flagged_pkgs": flagged_pkgs,
        "pending_ideas": pending_ideas,
        "logs": logs,
        "latest_an_note": latest_an_note,
        "last_approved": last_approved,
    }


def record_log(kind: str, agent: str, overall: str, summary_md: str,
               snapshot: dict | None = None, approve: bool = False, decision_note: str = "") -> int:
    init()
    now = db.now_iso()
    with db.tx() as c:
        cur = c.execute(
            """INSERT INTO audit_logs (created_at, kind, agent, overall, summary_md, snapshot_json, approved_at, decision_note)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                now,
                kind if kind in ("hang_ngay", "hang_tuan") else "hang_ngay",
                (agent or "system")[:40],
                overall if overall in ("ok", "warn", "error") else "ok",
                (summary_md or "")[:20000],
                json.dumps(snapshot or {}, ensure_ascii=False)[:10000],
                now if approve else "",
                (decision_note or "")[:500],
            ),
        )
        return cur.lastrowid


def to_markdown(data: dict | None = None) -> str:
    """Xuất Bản tin Tổng duyệt 1 trang (ẩn danh 100%, không PII) để lưu hoặc gửi báo cáo."""
    d = data or run_audit()
    lines = [
        f"# BẢN TIN TỔNG DUYỆT QUY TRÌNH · {d['generated_at']}",
        "",
        f"**Trạng thái chung:** {d['overall_label']} · Đỏ: **{d['counts']['error']}** · Vàng: **{d['counts']['warn']}** · Xanh: **{d['counts']['ok']}**",
        "",
        "## A. Kết quả 6 chốt kiểm toán [Dữ kiện]",
        "| Chốt kiểm toán | Trạng thái | Tóm tắt | Chi tiết |",
        "|---|---|---|---|",
    ]
    for c in d["checks"]:
        lines.append(f"| {c['name']} | {LEVEL_LABELS[c['level']]} | {c['headline'].replace('|', '/')} | {c['detail'].replace('|', '/')} |")

    if d["pending_ideas"]:
        lines += [
            "",
            f"## B. Ý tưởng đầu vào chờ anh Nhơn duyệt ({len(d['pending_ideas'])} mục)",
            "| Điểm | Loại | Tiêu đề | Nguồn | Cảnh báo trùng |",
            "|---:|---|---|---|---|",
        ]
        for it in d["pending_ideas"]:
            lines.append(
                f"| {it['score']} | L{it['loai']} ({it['scenes']}c) | {it['title'].replace('|', '/')} | "
                f"{it['source_label']} | {(it.get('dup_warning') or 'Sạch').replace('|', '/')} |"
            )

    if d["flagged_pkgs"]:
        lines += ["", "## C. Gói SX chờ đăng / có cảnh báo cần chú ý"]
        for p in d["flagged_pkgs"]:
            tag = "✅ Sẵn sàng đăng" if p["is_ready"] else p["status"]
            iss = "; ".join(p["errors"] + p["warns"]) or "Không có cảnh báo"
            lines.append(f"- **Gói {p['goi']}** (L{p['loai']} · {tag}): {p['title']} — {iss}")

    return "\n".join(lines) + "\n"
