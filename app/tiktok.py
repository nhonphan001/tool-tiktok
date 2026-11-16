"""Client TikTok chính thức: Login Kit (OAuth v2) + Display API (user info, video list).

Tài liệu: https://developers.tiktok.com/doc/login-kit-web
          https://developers.tiktok.com/doc/display-api-get-started
"""
import secrets
import time
from urllib.parse import urlencode

import httpx

from .config import settings

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
REVOKE_URL = "https://open.tiktokapis.com/v2/oauth/revoke/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"
VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"

SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list"

USER_FIELDS = (
    "open_id,union_id,avatar_url,display_name,username,bio_description,profile_deep_link,"
    "follower_count,following_count,likes_count,video_count"
)
VIDEO_FIELDS = (
    "id,title,video_description,create_time,cover_image_url,share_url,duration,"
    "view_count,like_count,comment_count,share_count"
)


class TikTokError(Exception):
    pass


def build_auth_url() -> tuple[str, str]:
    state = secrets.token_urlsafe(24)
    params = {
        "client_key": settings.tiktok_client_key,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": settings.tiktok_redirect_uri,
        "state": state,
    }
    return f"{AUTH_URL}?{urlencode(params)}", state


def _token_request(data: dict) -> dict:
    data = {"client_key": settings.tiktok_client_key, "client_secret": settings.tiktok_client_secret, **data}
    r = httpx.post(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded", "Cache-Control": "no-cache"},
        timeout=30,
    )
    body = r.json()
    if r.status_code != 200 or "access_token" not in body:
        raise TikTokError(f"Lỗi token TikTok: {body.get('error_description') or body.get('error') or body}")
    now = int(time.time())
    return {
        "open_id": body["open_id"],
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token"),
        "token_expires_at": now + int(body.get("expires_in", 86400)),
        "refresh_expires_at": now + int(body.get("refresh_expires_in", 31536000)),
        "scope": body.get("scope", ""),
    }


def exchange_code(code: str) -> dict:
    return _token_request(
        {"code": code, "grant_type": "authorization_code", "redirect_uri": settings.tiktok_redirect_uri}
    )


def refresh(refresh_token: str) -> dict:
    return _token_request({"grant_type": "refresh_token", "refresh_token": refresh_token})


def revoke(access_token: str) -> None:
    try:
        httpx.post(
            REVOKE_URL,
            data={
                "client_key": settings.tiktok_client_key,
                "client_secret": settings.tiktok_client_secret,
                "token": access_token,
            },
            timeout=15,
        )
    except httpx.HTTPError:
        pass


def _check(r: httpx.Response) -> dict:
    try:
        body = r.json()
    except ValueError:
        raise TikTokError(f"TikTok trả về dữ liệu không hợp lệ (HTTP {r.status_code})")
    err = body.get("error") or {}
    if r.status_code != 200 or (err.get("code") not in (None, "", "ok")):
        raise TikTokError(f"TikTok API lỗi: {err.get('code')} - {err.get('message')} (HTTP {r.status_code})")
    return body.get("data") or {}


def get_user_info(access_token: str) -> dict:
    r = httpx.get(
        USER_INFO_URL,
        params={"fields": USER_FIELDS},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    return _check(r).get("user", {})


def list_videos(access_token: str, max_videos: int = 200) -> list[dict]:
    """Lấy danh sách video (phân trang bằng cursor, tối đa 20/trang)."""
    videos: list[dict] = []
    cursor = None
    while len(videos) < max_videos:
        payload = {"max_count": 20}
        if cursor is not None:
            payload["cursor"] = cursor
        r = httpx.post(
            VIDEO_LIST_URL,
            params={"fields": VIDEO_FIELDS},
            json=payload,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=30,
        )
        data = _check(r)
        videos.extend(data.get("videos") or [])
        if not data.get("has_more"):
            break
        cursor = data.get("cursor")
        time.sleep(0.3)
    return videos[:max_videos]
