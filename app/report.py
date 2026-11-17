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
            f"- Dữ liệu theo dõi từ: {ov['first_snapshot']} ({ov['snapshot_count']} lần quét)",
        ]
    else:
        lines.append("Chưa có dữ liệu quét.")

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
    return "\n".join(lines) + "\n"


def build_strategy_doc(open_id: str, limit: int = 10) -> str:
    rows = db.query("SELECT * FROM strategies WHERE open_id=? ORDER BY created_at DESC LIMIT ?", (open_id, limit))
    lines = ["# Lịch sử chiến lược kênh TikTok", ""]
    if not rows:
        lines.append("Chưa có chiến lược nào.")
    for r in rows:
        lines += [
            f"---\n\n## Chiến lược ngày {r['created_at']} ({r['source']}{' · ' + r['model'] if r['model'] else ''})",
            f"**Mục tiêu:** {r['goal'] or '—'}",
            "",
            r["content_md"] or "",
            "",
        ]
    return "\n".join(lines)
