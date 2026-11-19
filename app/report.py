"""Tạo báo cáo Markdown từ số liệu — dùng làm ngữ cảnh cho Gemini và làm nguồn cho NotebookLM."""
from datetime import datetime

from . import analytics, db
from .config import settings


def _n(x) -> str:
    return f"{x:,}".replace(",", ".") if isinstance(x, (int, float)) else "—"


def _d(x) -> str:
    if x is None:
        return "—"
    return ("+" if x >= 0 else "") + _n(x)


def build_report(open_id: str, max_videos: int = 50) -> str:
    acc = db.query_one("SELECT * FROM accounts WHERE open_id=?", (open_id,)) or {}
    ov = analytics.overview(open_id)
    an = analytics.deep_analysis(open_id)
    tz = analytics._tz()
    now = datetime.now(tz).strftime("%d/%m/%Y %H:%M")
    lines = [
        f"# Báo cáo kênh TikTok @{acc.get('username') or acc.get('display_name') or open_id}",
        f"_Cập nhật: {now} ({tz.key})_",
        "",
        "> Số liệu lấy trực tiếp từ TikTok API tại thời điểm quét. Khi báo cáo, ghi ĐÚNG con số, "
        "không làm tròn lên thành \"đã đạt mốc\".",
        "",
    ]
    if settings.channel_context:
        lines += ["## Thông tin kênh", settings.channel_context, ""]
    lines += ["## 1. Tổng quan kênh"]
    latest = ov.get("latest")
    if latest:
        d = ov["deltas"]
        lines += [
            f"- Người theo dõi: **{_n(latest['follower_count'])}** (24h: {_d((d['24h'] or {}).get('follower_count'))}, "
            f"7 ngày: {_d((d['7d'] or {}).get('follower_count'))}, 30 ngày: {_d((d['30d'] or {}).get('follower_count'))})",
            f"- Tổng lượt thích kênh: **{_n(latest['likes_count'])}** (7 ngày: {_d((d['7d'] or {}).get('likes_count'))})",
            f"- Số video: **{_n(latest['video_count'])}**, đang theo dõi {ov['video_tracked']} video",
            f"- Tổng lượt xem các video theo dõi: {_n(ov['total_views'])}",
            f"- Lượt xem trung bình / trung vị mỗi video: {_n(ov['avg_views'])} / {_n(ov['median_views'])}",
            f"- Tỉ lệ tương tác trung bình (like+comment+share / view): {ov['avg_engagement']}%",
            f"- Dữ liệu theo dõi từ: {analytics.localtime(ov['first_snapshot'])} ({ov['snapshot_count']} lần quét)",
        ]
    else:
        lines.append("Chưa có dữ liệu quét.")

    lines += _kpi_section(open_id)
    lines += _compliance_section(open_id)
    lines += _tag_section(open_id)
    lines += _package_section()

    lines += ["", "## 2. Nhận định tự động"] + [f"- {i}" for i in an["insights"]]

    lines += ["", "## 3. Hiệu quả theo ngày đăng", "| Ngày | Số video | View TB | Tương tác TB |", "|---|---|---|---|"]
    lines += [f"| {s['label']} | {s['count']} | {_n(s['avg_views'])} | {s['avg_engagement']}% |" for s in an["weekday"]]

    lines += ["", "## 4. Hiệu quả theo giờ đăng", "| Giờ | Số video | View TB | Tương tác TB |", "|---|---|---|---|"]
    lines += [
        f"| {s['label']} | {s['count']} | {_n(s['avg_views'])} | {s['avg_engagement']}% |" for s in an["hour"] if s["count"]
    ]

    lines += ["", "## 5. Hiệu quả theo độ dài video", "| Độ dài | Số video | View TB | Tương tác TB |", "|---|---|---|---|"]
    lines += [f"| {s['label']} | {s['count']} | {_n(s['avg_views'])} | {s['avg_engagement']}% |" for s in an["duration"]]

    lines += ["", "## 6. Hashtag", "| Hashtag | Số video | View TB | Tương tác TB |", "|---|---|---|---|"]
    lines += [f"| #{s['key']} | {s['count']} | {_n(s['avg_views'])} | {s['avg_engagement']}% |" for s in an["hashtags"]]

    lines += ["", "## 7. Tần suất đăng theo tuần", "| Tuần bắt đầu | Số video | View TB |", "|---|---|---|"]
    lines += [f"| {w['label']} | {w['count']} | {_n(w['avg_views'])} |" for w in an["weeks"]]

    if an["trending"]:
        lines += ["", "## 8. Video đang tăng trưởng mạnh (giữa 2 lần quét gần nhất)"]
        lines += [f"- {v['label']} — +{_n(v['gain'])} view ({v['share_url'] or ''})" for v in an["trending"]]

    lines += [
        "",
        f"## 9. Chi tiết {max_videos} video gần nhất",
        "| Ngày đăng | Tiêu đề | Thời lượng | View | Like | Comment | Share | Tương tác | View/ngày |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for v in analytics.get_videos(open_id)[:max_videos]:
        title = (v["label"] or "").replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {v['posted_str']} | {title} | {v.get('duration') or 0}s | {_n(v['view_count'])} | {_n(v['like_count'])} |"
            f" {_n(v['comment_count'])} | {_n(v['share_count'])} | {v['engagement']}% | {_n(v['views_per_day'])} |"
        )
    try:  # Phụ lục: báo cáo tự động của tool (để Gemini/Claude đối chiếu quy trình)
        from . import system_report

        lines += ["", "## 10. Tình trạng hệ thống (TikTok Manager tự báo cáo)", "",
                  system_report.to_markdown().split("\n", 2)[2]]
    except Exception:  # noqa: BLE001
        pass
    return "\n".join(lines) + "\n"


def _kpi_section(open_id: str) -> list[str]:
    from . import kpi

    k = kpi.summary(open_id)
    lines = ["", "## KPI"]
    for t in k["targets"]:
        lines.append(
            f"- Mốc {_n(t['target'])} follower trước {t['deadline']}: hiện {_n(t['current'])} ({t['pct']}%), "
            f"còn {_n(t['remaining'])}; cần {t['need_per_day'] if t['need_per_day'] is not None else '—'}/ngày, "
            f"tốc độ 7 ngày qua {t['pace']}/ngày → dự kiến đạt {t['eta']} "
            f"({'ĐÚNG TIẾN ĐỘ' if t['on_track'] else 'CHẬM TIẾN ĐỘ'})"
        )
    lv = k["like_view"]
    lines.append(
        f"- Tỷ lệ tim/view {lv['days']} ngày: {lv['rate']}% (mục tiêu ≥ {lv['min']}%, "
        f"{'đạt' if lv['ok'] else 'CHƯA ĐẠT'}); {lv['below']}/{lv['videos']} video dưới mốc"
    )
    lines += ["", "| Khung giờ đăng | Số video | View TB | Tim/view |", "|---|---|---|---|"]
    lines += [f"| {s['label']} | {s['count']} | {_n(s['avg_views'])} | {s['like_view']}% |" for s in k["slots"]]
    return lines


def _compliance_section(open_id: str) -> list[str]:
    from . import compliance, tags

    issues = tags.compliance_issues(open_id)
    lines = ["", "## Kiểm tra tuân thủ caption (quy tắc TikTok Shop)"]
    if not issues:
        return lines + ["- Tất cả caption đã quét đều sạch (không có lời mời ra ngoài nền tảng / hứa hẹn quá đà)."]
    for v in issues:
        c = v["compliance"]
        what = ", ".join(f"{x['label']} (\"{x['match']}\")" for x in c["offsite"] + c["promise"])
        lines.append(f"- [{compliance.LEVEL_LABELS[c['level']]}] {v['posted_str']} – {v['label'][:60]}: {what}")
    lines.append("- Lưu ý: chỉ kiểm tra được caption/tiêu đề; lời thoại và bình luận ghim phải kiểm theo Mẫu A/B.")
    return lines


def _tag_section(open_id: str) -> list[str]:
    from . import tags

    t = tags.tag_analysis(open_id)
    lines = ["", f"## Hiệu quả theo nhãn ({t['tagged']}/{t['total']} video đã gắn nhãn)"]
    for title, rows in (("Nhóm nội dung", t["by_group"]), ("Hành", t["by_element"]),
                        ("Sản phẩm", t["by_product"]), ("Giỏ hàng", t["by_cart"])):
        if not rows:
            continue
        lines += ["", f"| {title} | Số video | View TB | Tương tác TB | Tim/view |", "|---|---|---|---|---|"]
        lines += [f"| {r['label']} | {r['count']} | {_n(r['avg_views'])} | {r['avg_engagement']}% | {r['like_view']}% |"
                  for r in rows]
    return lines


def _package_section(limit: int = 12) -> list[str]:
    from . import packages

    items = packages.all_packages()[:limit]
    lines = ["", "## Gói sản xuất gần đây (kiểm tra tự động của TikTok Manager)"]
    if not items:
        return lines + ["- Chưa có gói nào được soạn trong tool."]
    lines += ["| Gói | Tiêu đề | Loại | SKU | Kiểm tra | Quảng cáo | Trạng thái | Video |", "|---|---|---|---|---|---|---|---|"]
    for p in items:
        chk = packages.check(p)
        lines.append(
            f"| {p.get('goi') or p['id']} | {(p.get('title') or '').replace('|', '/')} | {'Lá số' if p['loai'] == 1 else 'Sản phẩm'}"
            f" | {p.get('sku') or '—'} | {'đạt' if not chk['errors'] else str(chk['errors']) + ' lỗi'}"
            f" | {'được' if chk['ads_ok'] else 'không'} | {packages.STATUS.get(p.get('status') or 'nhap')}"
            f" | {p.get('video_id') or '—'} |")
    return lines


def build_strategy_doc(open_id: str, limit: int = 10) -> str:
    rows = db.query("SELECT * FROM strategies WHERE open_id=? AND status='done' ORDER BY created_at DESC LIMIT ?", (open_id, limit))
    lines = ["# Lịch sử chiến lược kênh TikTok", ""]
    if not rows:
        lines.append("Chưa có chiến lược nào.")
    for r in rows:
        lines += [
            f"---\n\n## Chiến lược ngày {analytics.localtime(r['created_at'])} ({r['source']}{' · ' + r['model'] if r['model'] else ''})",
            f"**Mục tiêu:** {r['goal'] or '—'}",
            "",
            r["content_md"] or "",
            "",
        ]
    return "\n".join(lines)
