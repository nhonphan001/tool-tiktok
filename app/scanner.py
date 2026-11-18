"""Quét dữ liệu kênh: làm mới token, lấy thông tin kênh + video, lưu ảnh chụp số liệu."""
import logging
import threading
import time

from . import db, tiktok
from .config import settings

log = logging.getLogger(__name__)
_scan_lock = threading.Lock()


def ensure_token(account: dict) -> str:
    if account.get("token_expires_at") and account["token_expires_at"] - 300 > time.time():
        return account["access_token"]
    if not account.get("refresh_token"):
        raise tiktok.TikTokError("Token hết hạn và không có refresh token. Hãy kết nối lại TikTok.")
    tok = tiktok.refresh(account["refresh_token"])
    db.upsert_account({"open_id": account["open_id"], **{k: v for k, v in tok.items() if k != "open_id"}})
    return tok["access_token"]


def save_scan_data(open_id: str, user: dict, videos: list[dict]) -> None:
    ts = db.now_iso()
    with db.tx() as c:
        c.execute(
            "UPDATE accounts SET username=COALESCE(?,username), display_name=COALESCE(?,display_name), "
            "avatar_url=COALESCE(?,avatar_url), bio=COALESCE(?,bio), profile_link=COALESCE(?,profile_link) "
            "WHERE open_id=?",
            (
                user.get("username"),
                user.get("display_name"),
                user.get("avatar_url"),
                user.get("bio_description"),
                user.get("profile_deep_link"),
                open_id,
            ),
        )
        c.execute(
            "INSERT INTO account_snapshots(open_id, taken_at, follower_count, following_count, likes_count, video_count)"
            " VALUES(?,?,?,?,?,?)",
            (
                open_id,
                ts,
                user.get("follower_count"),
                user.get("following_count"),
                user.get("likes_count"),
                user.get("video_count"),
            ),
        )
        for v in videos:
            stats = (
                int(v.get("view_count") or 0),
                int(v.get("like_count") or 0),
                int(v.get("comment_count") or 0),
                int(v.get("share_count") or 0),
            )
            c.execute(
                "INSERT INTO videos(id, open_id, title, description, create_time, cover_url, share_url, duration,"
                " view_count, like_count, comment_count, share_count, first_seen, last_seen)"
                " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
                " ON CONFLICT(id) DO UPDATE SET title=excluded.title, description=excluded.description,"
                " cover_url=excluded.cover_url, share_url=excluded.share_url, duration=excluded.duration,"
                " view_count=excluded.view_count, like_count=excluded.like_count,"
                " comment_count=excluded.comment_count, share_count=excluded.share_count, last_seen=excluded.last_seen",
                (
                    str(v["id"]),
                    open_id,
                    v.get("title"),
                    v.get("video_description"),
                    v.get("create_time"),
                    v.get("cover_image_url"),
                    v.get("share_url"),
                    v.get("duration"),
                    *stats,
                    ts,
                    ts,
                ),
            )
            c.execute(
                "INSERT INTO video_snapshots(video_id, taken_at, view_count, like_count, comment_count, share_count)"
                " VALUES(?,?,?,?,?,?)",
                (str(v["id"]), ts, *stats),
            )


def run_scan(trigger: str = "schedule") -> dict:
    """Chạy 1 lần quét cho tài khoản đang kết nối. Trả về bản ghi scan."""
    if not _scan_lock.acquire(blocking=False):
        return {"status": "skipped", "message": "Đang có một lần quét khác chạy"}
    try:
        account = db.get_active_account()
        if not account:
            return {"status": "skipped", "message": "Chưa kết nối kênh TikTok"}
        with db.tx() as c:
            cur = c.execute(
                "INSERT INTO scans(open_id, started_at, status, message) VALUES(?,?,?,?)",
                (account["open_id"], db.now_iso(), "running", trigger),
            )
            scan_id = cur.lastrowid
        try:
            if account.get("is_demo"):
                from . import demo

                user, videos = demo.simulate_fetch(account["open_id"])
            else:
                token = ensure_token(account)
                user = tiktok.get_user_info(token)
                videos = tiktok.list_videos(token, settings.max_videos_per_scan)
            save_scan_data(account["open_id"], user, videos)
            status, message = "ok", f"Đã quét {len(videos)} video ({trigger})"
        except Exception as e:  # noqa: BLE001
            log.exception("Scan failed")
            status, message, videos = "error", str(e), []
        with db.tx() as c:
            c.execute(
                "UPDATE scans SET finished_at=?, status=?, message=?, videos_count=? WHERE id=?",
                (db.now_iso(), status, message, len(videos), scan_id),
            )
        result = {"id": scan_id, "status": status, "message": message}
    finally:
        _scan_lock.release()

    if result["status"] == "ok":
        _post_scan(account["open_id"])
    return result


def _post_scan(open_id: str) -> None:
    from . import notebooklm, strategy

    try:
        from . import packages

        linked = packages.auto_link(open_id)
        if linked:
            log.info("Auto-linked packages to videos: %s", linked)
    except Exception:  # noqa: BLE001
        log.exception("Auto-link packages failed")
    try:
        if settings.auto_strategy:
            strategy.generate(open_id)
        notebooklm.sync_all(open_id)
    except Exception:  # noqa: BLE001
        log.exception("Post-scan tasks failed")
