"""Dữ liệu DEMO giả lập để thử giao diện khi chưa có TikTok API. Không phải dữ liệu thật."""
import random
import time
from datetime import datetime, timedelta, timezone

from . import db, scanner

DEMO_ID = "demo_open_id"
TOPICS = [
    ("Mẹo nấu ăn nhanh 5 phút", "#meonauan #nauan #learnontiktok"),
    ("Review quán ăn vỉa hè Sài Gòn", "#review #anvat #saigon"),
    ("Một ngày làm việc của tôi", "#vlog #dailyvlog #congviec"),
    ("3 sai lầm khi tiết kiệm tiền", "#taichinh #tietkiem #learnontiktok"),
    ("Thử thách 30 ngày tập thể dục", "#fitness #thuthach #suckhoe"),
    ("Công thức trà sữa tại nhà", "#nauan #trasua #meonauan"),
    ("Đồ dùng nhà bếp đáng mua", "#review #nhabep #shopee"),
]


def _video_stats(age_days: float, quality: float) -> dict:
    views = int(quality * 8000 * (1 - 0.6 ** (age_days + 0.3)) + random.randint(50, 400))
    return {
        "view_count": views,
        "like_count": int(views * random.uniform(0.04, 0.12)),
        "comment_count": int(views * random.uniform(0.003, 0.015)),
        "share_count": int(views * random.uniform(0.002, 0.02)),
    }


def seed(days: int = 30, n_videos: int = 40) -> None:
    random.seed(42)
    db.upsert_account(
        {
            "open_id": DEMO_ID,
            "username": "kenh_demo",
            "display_name": "Kênh Demo",
            "avatar_url": "",
            "bio": "Dữ liệu giả lập để thử giao diện",
            "profile_link": "",
            "access_token": "",
            "refresh_token": "",
            "token_expires_at": 0,
            "refresh_expires_at": 0,
            "scope": "",
            "is_demo": 1,
            "connected_at": db.now_iso(),
        }
    )
    now = datetime.now(timezone.utc)
    videos = []
    for i in range(n_videos):
        posted = now - timedelta(days=random.uniform(0.5, days + 30))
        local_hour = random.choice([7, 11, 12, 18, 19, 20, 21, 22])
        posted = posted.replace(hour=(local_hour - 7) % 24, minute=random.randint(0, 59))
        topic, tags = random.choice(TOPICS)
        quality = random.lognormvariate(0, 0.9) * (1.6 if local_hour in (19, 20, 21) else 1.0)
        quality *= 1.4 if "#meonauan" in tags else 1.0
        videos.append(
            {
                "id": f"demo{i:03d}",
                "title": f"{topic} (phần {i % 5 + 1})",
                "video_description": f"{topic} {tags}",
                "create_time": int(posted.timestamp()),
                "cover_image_url": "",
                "share_url": "",
                "duration": random.choice([9, 14, 22, 28, 35, 45, 58, 75, 120, 200]),
                "_quality": quality,
            }
        )
    followers = 12000
    for step in range(days * 2, -1, -1):  # 2 lần quét/ngày
        t = now - timedelta(hours=12 * step)
        visible = []
        for v in videos:
            age = (t.timestamp() - v["create_time"]) / 86400
            if age > 0:
                visible.append({**v, **_video_stats(age, v["_quality"])})
        followers += random.randint(20, 160)
        user = {
            "follower_count": followers,
            "following_count": 180,
            "likes_count": sum(x["like_count"] for x in visible) + 50000,
            "video_count": len(visible),
        }
        scanner.save_scan_data(DEMO_ID, user, visible)
        with db.tx() as c:  # đặt lại thời điểm chụp theo t
            iso = t.replace(microsecond=0).isoformat()
            c.execute("UPDATE account_snapshots SET taken_at=? WHERE id=(SELECT MAX(id) FROM account_snapshots)", (iso,))
            c.execute(
                "UPDATE video_snapshots SET taken_at=? WHERE taken_at=(SELECT taken_at FROM video_snapshots ORDER BY id DESC LIMIT 1)",
                (iso,),
            )


def simulate_fetch(open_id: str) -> tuple[dict, list[dict]]:
    last = db.query_one("SELECT * FROM account_snapshots WHERE open_id=? ORDER BY taken_at DESC LIMIT 1", (open_id,)) or {}
    vids = db.query("SELECT * FROM videos WHERE open_id=?", (open_id,))
    now = time.time()
    out = []
    for v in vids:
        age = max((now - (v["create_time"] or now)) / 86400, 0.1)
        g = 1 + random.uniform(0.0, 0.08) / age
        out.append(
            {
                "id": v["id"],
                "title": v["title"],
                "video_description": v["description"],
                "create_time": v["create_time"],
                "cover_image_url": v["cover_url"],
                "share_url": v["share_url"],
                "duration": v["duration"],
                "view_count": int(v["view_count"] * g),
                "like_count": int(v["like_count"] * g),
                "comment_count": int(v["comment_count"] * g),
                "share_count": int(v["share_count"] * g),
            }
        )
    user = {
        "follower_count": (last.get("follower_count") or 10000) + random.randint(5, 80),
        "following_count": last.get("following_count") or 180,
        "likes_count": (last.get("likes_count") or 0) + random.randint(50, 500),
        "video_count": len(out),
    }
    return user, out


if __name__ == "__main__":
    seed()
    print("Đã tạo dữ liệu demo.")
