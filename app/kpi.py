"""KPI kênh: tiến độ follower theo mốc, tỷ lệ tim/view, hiệu quả khung giờ đăng."""
from datetime import date, datetime, timedelta, timezone
from statistics import mean

from . import analytics, db
from .config import settings


def _parse_date(s: str) -> date | None:
    try:
        return date.fromisoformat((s or "").strip())
    except ValueError:
        return None


def follower_pace(open_id: str, days: int = 7) -> tuple[float, int | None]:
    """Số follower tăng trung bình mỗi ngày trong `days` ngày gần nhất."""
    snaps = db.query(
        "SELECT taken_at, follower_count FROM account_snapshots WHERE open_id=? AND follower_count IS NOT NULL"
        " ORDER BY taken_at",
        (open_id,),
    )
    if len(snaps) < 2:
        return 0.0, (snaps[-1]["follower_count"] if snaps else None)
    latest = snaps[-1]
    t_latest = datetime.fromisoformat(latest["taken_at"])
    base = analytics.snapshot_at_or_before(snaps, t_latest - timedelta(days=days)) or snaps[0]
    span = (t_latest - datetime.fromisoformat(base["taken_at"])).total_seconds() / 86400
    if span < 0.5:
        return 0.0, latest["follower_count"]
    return (latest["follower_count"] - base["follower_count"]) / span, latest["follower_count"]


def targets(open_id: str) -> list[dict]:
    pace, current = follower_pace(open_id)
    today = datetime.now(analytics._tz()).date()
    out = []
    for target, deadline in (
        (settings.kpi_target_1, settings.kpi_deadline_1),
        (settings.kpi_target_2, settings.kpi_deadline_2),
    ):
        if not target:
            continue
        dl = _parse_date(deadline)
        cur = current or 0
        remaining = max(target - cur, 0)
        days_left = (dl - today).days if dl else None
        need = remaining / days_left if days_left and days_left > 0 else None
        eta = today + timedelta(days=remaining / pace) if pace > 0 and remaining else (today if not remaining else None)
        out.append({
            "target": target,
            "deadline": dl.strftime("%d/%m/%Y") if dl else "—",
            "current": cur,
            "remaining": remaining,
            "pct": min(round(cur / target * 100, 1), 100) if target else 0,
            "days_left": days_left,
            "need_per_day": round(need, 1) if need is not None else None,
            "pace": round(pace, 1),
            "eta": eta.strftime("%d/%m/%Y") if eta else "chưa ước tính được",
            "on_track": remaining == 0 or (need is not None and pace >= need),
        })
    return out


def like_view(open_id: str, days: int = 30) -> dict:
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    vids = db.query(
        "SELECT view_count, like_count FROM videos WHERE open_id=? AND create_time>=?", (open_id, since)
    )
    views = sum(v["view_count"] or 0 for v in vids)
    likes = sum(v["like_count"] or 0 for v in vids)
    rate = round(likes / views * 100, 2) if views else 0
    below = sum(1 for v in vids if v["view_count"] and v["like_count"] / v["view_count"] * 100 < settings.kpi_like_view_min)
    return {"rate": rate, "min": settings.kpi_like_view_min, "ok": rate >= settings.kpi_like_view_min,
            "videos": len(vids), "below": below, "days": days}


def _slots() -> list[tuple[str, int]]:
    out = []
    for s in (settings.posting_slots or "").split(","):
        s = s.strip()
        try:
            h, m = s.split(":")
            out.append((f"{int(h):02d}:{int(m):02d}", int(h) * 60 + int(m)))
        except ValueError:
            continue
    return out


def slot_performance(open_id: str, window_min: int = 60) -> list[dict]:
    """So sánh video đăng trong ±window_min phút quanh mỗi khung giờ đã lên lịch và ngoài khung."""
    slots = _slots()
    groups: dict[str, list] = {f"Khung {s}": [] for s, _ in slots}
    groups["Ngoài khung"] = []
    for v in analytics.get_videos(open_id):
        if not v["posted_local"]:
            continue
        mins = v["posted_local"].hour * 60 + v["posted_local"].minute
        best = min(slots, key=lambda s: abs(s[1] - mins), default=None)
        if best and abs(best[1] - mins) <= window_min:
            groups[f"Khung {best[0]}"].append(v)
        else:
            groups["Ngoài khung"].append(v)
    rows = []
    for label, vs in groups.items():
        views = sum(x["view_count"] or 0 for x in vs)
        likes = sum(x["like_count"] or 0 for x in vs)
        rows.append({
            "label": label,
            "count": len(vs),
            "avg_views": round(mean(x["view_count"] or 0 for x in vs)) if vs else 0,
            "like_view": round(likes / views * 100, 2) if views else 0,
        })
    return rows


def summary(open_id: str) -> dict:
    return {"targets": targets(open_id), "like_view": like_view(open_id), "slots": slot_performance(open_id)}
