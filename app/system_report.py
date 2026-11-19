"""Báo cáo tự động của TikTok Manager: tình trạng từng mắt xích quy trình (để đối chiếu đồng thuận với Claude/Gemini).

Chỉ đọc DB + cấu hình, không gọi Gemini, không ghi gì ra ngoài.
"""
import os
from datetime import datetime, timezone

from . import db, packages, products
from .config import settings

PROCESS = [  # (mã, bước, ai làm) — bảng quy trình chung dùng trong thư DONGTHUAN
    ("P1", "Quét số liệu TikTok 05:00 · 11:00 · 17:00 · 23:00", "Tool"),
    ("P2", "Ghi báo cáo lên Drive 06 → NotebookLM", "Tool"),
    ("P3", "Anh Nhơn tạo yêu cầu trên trang Yêu cầu Gemini (tool giữ số gói, soạn thư)", "Anh Nhơn + Tool"),
    ("P4", "Tool ghi thư vào Doc HOP_THU_TOOL__YEUCAU (GUI_GEMINI)", "Tool"),
    ("P5", "Gemini viết kịch bản + 4 ảnh v3.3 + 4 prompt video → SANXUAT-…__XONG trong GUI_CLAUDE", "Gemini"),
    ("P6", "Tool dò thư trả lời / thư sửa mỗi 10 phút và thông báo", "Tool"),
    ("P7", "Nhập từ hộp thư → Lưu & kiểm tra (B.1–B.4, Loại 1/2/3, prompt khớp lời thoại)", "Anh Nhơn + Tool"),
    ("P8", "Gemini dựng video (Veo/Flow + FFmpeg), QA, gửi BAOCAO-…GOI-n với link video", "Gemini"),
    ("P9", "Tool lấy link video vào gói, Bộ đăng TikTok (Chép / Tải)", "Tool"),
    ("P10", "Anh Nhơn đăng (đúng caption, nhãn AI, giỏ hàng nếu Loại 2) + bật Quảng bá nếu tool báo Được", "Anh Nhơn"),
    ("P11", "Tool tự gắn video vào gói ở lần quét kế tiếp, tính KPI theo gói", "Tool"),
    ("P12", "SKU mới: dán link → tự điền (Gemini API) → duyệt → thêm dòng vào bảng sản phẩm", "Anh Nhơn + Tool"),
    ("P13", "Claude: sửa/nâng cấp tool, kiểm duyệt, viết thư VIEC/DONGTHUAN, dashboard 05:17", "Claude"),
]


def _one(sql: str, params: tuple = ()) -> dict:
    return db.query_one(sql, params) or {}


def collect() -> dict:
    packages.init()
    from . import gemini_requests, scheduler

    gemini_requests.init()
    acc = db.get_active_account() or {}
    last_scan = _one("SELECT * FROM scans ORDER BY id DESC LIMIT 1")
    scan_err = _one("SELECT COUNT(*) AS n FROM scans WHERE status!='ok' AND started_at >= datetime('now','-1 day')")
    drive = _one("SELECT * FROM sync_log WHERE target LIKE 'drive%' OR target LIKE 'notebook%' ORDER BY id DESC LIMIT 1")
    prods = products.all_products()
    pk = packages.all_packages()
    reqs = gemini_requests.all_requests()
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage = _one("SELECT COUNT(*) AS n, COALESCE(SUM(total_tokens),0) AS tok, COALESCE(SUM(cost_usd),0) AS usd"
                 " FROM ai_usage WHERE substr(created_at,1,7)=?", (month,))
    nxt = scheduler.next_run()
    return {
        "generated_at": db.now_iso(),
        "channel": acc.get("username") or "", "demo": bool(acc.get("is_demo")),
        "last_scan": last_scan, "scan_errors_24h": scan_err.get("n", 0),
        "next_scan": nxt.isoformat() if nxt else "", "scan_times": settings.scan_times,
        "drive_last": drive,
        "service_account": os.path.exists(settings.google_service_account_file or ""),
        "products": len(prods), "products_synced": prods[0]["synced_at"] if prods else "",
        "products_temp_link": sum(1 for p in prods if not products.real_link(p.get("link") or "")),
        "products_b4": sum(1 for p in prods if products.audit(p)),
        "packages": len(pk),
        "packages_by_status": {s: sum(1 for p in pk if (p.get("status") or "nhap") == s) for s in packages.STATUS},
        "packages_linked": sum(1 for p in pk if p.get("video_id")),
        "packages_with_video": sum(1 for p in pk if p.get("final_video")),
        "packages_with_prompts": sum(1 for p in pk if p.get("prompt1")),
        "requests": [{"goi": r["goi"], "code": r["code"], "status": r["status"]} for r in reqs[:10]],
        "requests_waiting": sum(1 for r in reqs if r["status"] == "sent"),
        "mailbox_folders": len([x for x in (settings.mailbox_folder_ids or "").split(",") if x.strip()]),
        "outbox_doc": bool(settings.mailbox_outbox_doc_id),
        "gemini_ready": bool(settings.gemini_api_key), "gemini_model": settings.gemini_model,
        "gemini_month": usage,
        "api_token": bool(settings.api_token),
    }


def _ok(cond: bool, warn: bool = False) -> str:
    return "✅" if cond else ("⚠️" if warn else "❌")


def to_markdown(d: dict | None = None) -> str:
    d = d or collect()
    ls = d["last_scan"] or {}
    st = d["packages_by_status"]
    rows = [
        ("P1", _ok(ls.get("status") == "ok" and not d["scan_errors_24h"], warn=bool(ls)),
         f"lần quét gần nhất {ls.get('started_at', '—')} ({ls.get('status', '—')}); lỗi 24h: {d['scan_errors_24h']}; "
         f"lịch {d['scan_times'] or 'theo chu kỳ'}; lần kế {d['next_scan'] or '—'}"),
        ("P2", _ok((d["drive_last"] or {}).get("status") == "ok", warn=True),
         f"đồng bộ gần nhất: {(d['drive_last'] or {}).get('created_at', '—')} {(d['drive_last'] or {}).get('status', '')}"),
        ("P3–P4", _ok(d["mailbox_folders"] >= 2 and d["outbox_doc"]),
         f"{d['mailbox_folders']} thư mục hộp thư; Doc hộp thư đi: {'có' if d['outbox_doc'] else 'chưa'}; "
         f"yêu cầu đang chờ Gemini: {d['requests_waiting']}"),
        ("P6", _ok(d["service_account"]), "dò hộp thư mỗi 10 phút (cần service account đọc thư mục 05)"),
        ("P7", _ok(d["packages"] > 0, warn=True),
         f"{d['packages']} gói — " + ", ".join(f"{packages.STATUS[k]} {v}" for k, v in st.items())),
        ("P8–P9", _ok(d["packages_with_video"] > 0, warn=True),
         f"gói có video thành phẩm: {d['packages_with_video']}; có prompt video: {d['packages_with_prompts']}"),
        ("P11", _ok(d["packages_linked"] > 0, warn=True), f"gói đã gắn video đăng: {d['packages_linked']}"),
        ("P12", _ok(d["products"] > 0 and d["gemini_ready"]),
         f"{d['products']} SKU (đọc {d['products_synced'] or '—'}); link tạm {d['products_temp_link']}; "
         f"SKU còn từ cấm trong bảng {d['products_b4']}"),
    ]
    u = d["gemini_month"] or {}
    out = [
        "# BÁO CÁO TỰ ĐỘNG – TIKTOK MANAGER", "",
        f"- Thời điểm: {d['generated_at']} (UTC) · kênh @{d['channel']}{' (DEMO)' if d['demo'] else ''}",
        f"- Gemini API: {'có key' if d['gemini_ready'] else 'chưa có key'} · model {d['gemini_model']} · tháng này "
        f"{u.get('n', 0)} lần gọi, {u.get('tok', 0)} token, ${float(u.get('usd') or 0):.4f}",
        f"- Service account Drive/Sheets: {'có' if d['service_account'] else 'THIẾU'} · API công khai: "
        f"{'bật' if d['api_token'] else 'tắt'}", "",
        "## Tình trạng từng bước quy trình", "", "| Bước | Trạng thái | Chi tiết |", "|---|---|---|",
        *[f"| {a} | {b} | {c} |" for a, b, c in rows], "",
        "## Yêu cầu Gemini gần nhất", "",
        *([f"- Gói {r['goi']} · {r['code']} · {r['status']}" for r in d["requests"]] or ["- (chưa có)"]), "",
        "## Bảng quy trình chung (để đồng thuận)", "", "| Mã | Bước | Ai làm |", "|---|---|---|",
        *[f"| {a} | {b} | {c} |" for a, b, c in PROCESS], "",
        "_✅ chạy tốt · ⚠️ chưa có dữ liệu/chưa dùng tới · ❌ thiếu cấu hình. Báo cáo do tool tự sinh, không tốn token._",
    ]
    return "\n".join(out)
