"""Thống kê & phân tích số liệu kênh."""
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean, median
from zoneinfo import ZoneInfo

from . import db
from .config import settings

WEEKDAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
DURATION_BUCKETS = [(0, 15, "<15s"), (15, 30, "15–30s"), (30, 60, "30–60s"), (60, 180, "1–3 phút"), (180, 10**9, ">3 phút")]
HASHTAG_RE = re.compile(r"#([\wÀ-ỹ]+)", re.UNICODE)


def _f(x) -> str:
    return f"{x:,}".replace(",", ".")


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.timezone)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def engagement(v: dict) -> float:
    views = v.get("view_count") or 0
    if views <= 0:
        return 0.0
    return ((v.get("like_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0)) / views


def snapshot_at_or_before(snaps: list[dict], when: datetime) -> dict | None:
    best = None
    for s in snaps:
        if _parse(s["taken_at"]) <= when:
            best = s
        else:
            break
    return best


def overview(open_id: str) -> dict:
    snaps = db.query("SELECT * FROM account_snapshots WHERE open_id=? ORDER BY taken_at", (open_id,))
    if not snaps:
        return {"latest": None}
    latest = snaps[-1]
    now = _parse(latest["taken_at"])
    deltas = {}
    for label, delta in (("24h", timedelta(hours=24)), ("7d", timedelta(days=7)), ("30d", timedelta(days=30))):
        prev = snapshot_at_or_before(snaps, now - delta)
        if prev is None:
            prev = snaps[0] if snaps[0] is not latest else None
        deltas[label] = (
            {k: (latest[k] or 0) - (prev[k] or 0) for k in ("follower_count", "likes_count", "video_count")}
            if prev
            else None
        )
    videos = get_videos(open_id)
    total_views = sum(v["view_count"] or 0 for v in videos)
    engs = [engagement(v) for v in videos if (v["view_count"] or 0) > 0]
    views_list = [v["view_count"] or 0 for v in videos]
    return {
        "latest": latest,
        "deltas": deltas,
        "snapshot_count": len(snaps),
        "first_snapshot": snaps[0]["taken_at"],
        "total_views": total_views,
        "video_tracked": len(videos),
        "avg_views": round(mean(views_list)) if views_list else 0,
        "median_views": round(median(views_list)) if views_list else 0,
        "avg_engagement": round(mean(engs) * 100, 2) if engs else 0,
    }


def account_series(open_id: str) -> dict:
    snaps = db.query("SELECT * FROM account_snapshots WHERE open_id=? ORDER BY taken_at", (open_id,))
    tz = _tz()
    return {
        "labels": [_parse(s["taken_at"]).astimezone(tz).strftime("%d/%m %H:%M") for s in snaps],
        "followers": [s["follower_count"] for s in snaps],
        "likes": [s["likes_count"] for s in snaps],
        "videos": [s["video_count"] for s in snaps],
    }


def views_series(open_id: str) -> dict:
    """Tổng lượt xem các video theo từng lần quét."""
    rows = db.query(
        "SELECT vs.taken_at, SUM(vs.view_count) AS views, SUM(vs.like_count) AS likes FROM video_snapshots vs"
        " JOIN videos v ON v.id = vs.video_id WHERE v.open_id=? GROUP BY vs.taken_at ORDER BY vs.taken_at",
        (open_id,),
    )
    tz = _tz()
    return {
        "labels": [_parse(r["taken_at"]).astimezone(tz).strftime("%d/%m %H:%M") for r in rows],
        "views": [r["views"] for r in rows],
        "likes": [r["likes"] for r in rows],
    }


def get_videos(open_id: str) -> list[dict]:
    rows = db.query("SELECT * FROM videos WHERE open_id=? ORDER BY create_time DESC", (open_id,))
    tz = _tz()
    now = datetime.now(timezone.utc)
    for v in rows:
        v["engagement"] = round(engagement(v) * 100, 2)
        ct = v.get("create_time")
        if ct:
            dt = datetime.fromtimestamp(ct, tz=timezone.utc)
            v["posted_local"] = dt.astimezone(tz)
            v["posted_str"] = v["posted_local"].strftime("%d/%m/%Y %H:%M")
            age_days = max((now - dt).total_seconds() / 86400, 1 / 24)
            v["age_days"] = round(age_days, 1)
            v["views_per_day"] = round((v["view_count"] or 0) / age_days)
        else:
            v["posted_local"] = None
            v["posted_str"] = ""
            v["age_days"] = None
            v["views_per_day"] = 0
        v["hashtags"] = [h.lower() for h in HASHTAG_RE.findall(f"{v.get('title') or ''} {v.get('description') or ''}")]
        v["label"] = (v.get("title") or v.get("description") or v["id"])[:80]
    return rows


def video_history(video_id: str) -> dict:
    rows = db.query("SELECT * FROM video_snapshots WHERE video_id=? ORDER BY taken_at", (video_id,))
    tz = _tz()
    return {
        "labels": [_parse(r["taken_at"]).astimezone(tz).strftime("%d/%m %H:%M") for r in rows],
        "views": [r["view_count"] for r in rows],
        "likes": [r["like_count"] for r in rows],
        "comments": [r["comment_count"] for r in rows],
        "shares": [r["share_count"] for r in rows],
    }


def recent_velocity(open_id: str) -> dict[str, int]:
    """Lượt xem tăng giữa 2 lần quét gần nhất của mỗi video."""
    times = db.query(
        "SELECT DISTINCT vs.taken_at FROM video_snapshots vs JOIN videos v ON v.id=vs.video_id"
        " WHERE v.open_id=? ORDER BY vs.taken_at DESC LIMIT 2",
        (open_id,),
    )
    if len(times) < 2:
        return {}
    t_new, t_old = times[0]["taken_at"], times[1]["taken_at"]
    rows = db.query(
        "SELECT a.video_id, a.view_count - COALESCE(b.view_count, 0) AS gain FROM video_snapshots a"
        " LEFT JOIN video_snapshots b ON b.video_id=a.video_id AND b.taken_at=? WHERE a.taken_at=?",
        (t_old, t_new),
    )
    return {r["video_id"]: r["gain"] for r in rows}


def _group_stats(groups: dict, order: list | None = None) -> list[dict]:
    keys = order if order is not None else sorted(groups.keys())
    out = []
    for k in keys:
        vs = groups.get(k, [])
        out.append(
            {
                "key": k,
                "count": len(vs),
                "avg_views": round(mean(v["view_count"] or 0 for v in vs)) if vs else 0,
                "avg_engagement": round(mean(v["engagement"] for v in vs), 2) if vs else 0,
            }
        )
    return out


def deep_analysis(open_id: str) -> dict:
    videos = get_videos(open_id)
    dated = [v for v in videos if v["posted_local"]]

    by_weekday = defaultdict(list)
    by_hour = defaultdict(list)
    heat = defaultdict(list)
    for v in dated:
        wd, hr = v["posted_local"].weekday(), v["posted_local"].hour
        by_weekday[wd].append(v)
        by_hour[hr].append(v)
        heat[(wd, hr // 3)].append(v["view_count"] or 0)

    weekday_stats = _group_stats(by_weekday, list(range(7)))
    for s in weekday_stats:
        s["label"] = WEEKDAYS[s["key"]]
    hour_stats = _group_stats(by_hour, list(range(24)))
    for s in hour_stats:
        s["label"] = f"{s['key']:02d}h"
    heatmap = [[round(mean(heat[(d, b)])) if heat.get((d, b)) else None for b in range(8)] for d in range(7)]

    dur_groups = defaultdict(list)
    for v in videos:
        d = v.get("duration") or 0
        for lo, hi, label in DURATION_BUCKETS:
            if lo <= d < hi:
                dur_groups[label].append(v)
                break
    duration_stats = _group_stats(dur_groups, [b[2] for b in DURATION_BUCKETS])
    for s in duration_stats:
        s["label"] = s["key"]

    tag_groups = defaultdict(list)
    for v in videos:
        for t in set(v["hashtags"]):
            tag_groups[t].append(v)
    hashtag_stats = sorted(_group_stats(tag_groups), key=lambda s: (s["count"] >= 2, s["avg_views"]), reverse=True)

    # Tần suất đăng theo tuần (8 tuần gần nhất)
    tz = _tz()
    now = datetime.now(tz)
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    weeks = []
    for i in range(7, -1, -1):
        start = week_start - timedelta(weeks=i)
        end = start + timedelta(weeks=1)
        vs = [v for v in dated if start <= v["posted_local"] < end]
        weeks.append(
            {
                "label": start.strftime("%d/%m"),
                "count": len(vs),
                "avg_views": round(mean(v["view_count"] or 0 for v in vs)) if vs else 0,
            }
        )

    by_views = sorted(videos, key=lambda v: v["view_count"] or 0, reverse=True)
    velocity = recent_velocity(open_id)
    trending = sorted(
        [dict(v, gain=velocity.get(v["id"], 0)) for v in videos], key=lambda v: v["gain"], reverse=True
    )[:5]

    return {
        "video_count": len(videos),
        "weekday": weekday_stats,
        "hour": hour_stats,
        "heatmap": heatmap,
        "heatmap_cols": [f"{b*3:02d}–{b*3+3:02d}h" for b in range(8)],
        "weekdays": WEEKDAYS,
        "duration": duration_stats,
        "hashtags": hashtag_stats[:20],
        "weeks": weeks,
        "top": by_views[:5],
        "bottom": [v for v in reversed(by_views) if v["age_days"] and v["age_days"] >= 3][:5],
        "trending": [t for t in trending if t["gain"] > 0],
        "insights": insights(weekday_stats, hour_stats, duration_stats, hashtag_stats, weeks, videos),
    }


def insights(weekday_stats, hour_stats, duration_stats, hashtag_stats, weeks, videos) -> list[str]:
    """Nhận định tự động dựa trên quy tắc (không cần AI)."""
    out: list[str] = []
    if len(videos) < 3:
        return ["Cần ít nhất 3 video để có nhận định đáng tin cậy."]
    min_n = 2 if len(videos) >= 10 else 1
    wd = [s for s in weekday_stats if s["count"] >= min_n]
    if wd:
        best = max(wd, key=lambda s: s["avg_views"])
        out.append(f"Ngày đăng hiệu quả nhất: {best['label']} (TB {_f(best['avg_views'])} view/video, {best['count']} video).")
    hr = [s for s in hour_stats if s["count"] >= min_n]
    if hr:
        top_hours = sorted(hr, key=lambda s: s["avg_views"], reverse=True)[:3]
        out.append("Khung giờ đăng tốt nhất: " + ", ".join(f"{s['label']} ({_f(s['avg_views'])} view)" for s in top_hours) + ".")
    du = [s for s in duration_stats if s["count"] >= min_n]
    if du:
        best = max(du, key=lambda s: s["avg_views"])
        best_eng = max(du, key=lambda s: s["avg_engagement"])
        out.append(f"Độ dài video cho nhiều view nhất: {best['label']}; tương tác cao nhất: {best_eng['label']} ({best_eng['avg_engagement']}%).")
    tags = [s for s in hashtag_stats if s["count"] >= 2][:5]
    if tags:
        out.append("Hashtag hiệu quả: " + ", ".join(f"#{s['key']}" for s in tags) + ".")
    recent = weeks[-4:]
    avg_per_week = mean(w["count"] for w in recent)
    out.append(f"Tần suất đăng 4 tuần gần đây: {avg_per_week:.1f} video/tuần.")
    if avg_per_week < 3:
        out.append("Tần suất đăng thấp — nên tăng lên tối thiểu 3–5 video/tuần để thuật toán phân phối đều hơn.")
    engs = [v["engagement"] for v in videos if v["view_count"]]
    if engs:
        avg = mean(engs)
        if avg < 4:
            out.append(f"Tỉ lệ tương tác TB {avg:.2f}% (thấp). Thử CTA rõ ràng hơn, đặt câu hỏi ở caption/cuối video.")
        elif avg > 10:
            out.append(f"Tỉ lệ tương tác TB {avg:.2f}% (rất tốt) — nội dung đang gắn kết khán giả, nên tăng sản lượng.")
    return out
