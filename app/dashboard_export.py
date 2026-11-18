"""Dựng 5 tệp số liệu {rows, meta} cho Bảng điều hành kênh từ /api/public/summary."""
NAMES = ("tiktok_kenh", "tiktok_kpi", "tiktok_khung_gio", "tiktok_video", "tiktok_tuan_thu")
LEVELS = {"violation": "Vi phạm (có giỏ hàng)", "violation_if_cart": "Vi phạm nếu có giỏ hàng",
          "fortune_risk": "Rủi ro bói toán/bùa – không quảng cáo", "warning": "Cần xem lại"}


def build(d: dict) -> dict[str, dict]:
    latest = d.get("latest") or {}
    deltas = d.get("deltas") or {}
    kpi = d.get("kpi") or {}
    lv = kpi.get("like_view") or {}
    at = latest.get("taken_at") or d.get("updated_at") or ""
    meta = [
        {"label": "Nguồn", "value": "TikTok Manager · /api/public/summary (số lấy từ TikTok API, không làm tròn)"},
        {"label": "Lần quét", "value": at},
    ]
    files = {
        "tiktok_kenh": [{
            "follower": latest.get("follower_count"),
            "dang_theo_doi": latest.get("following_count"),
            "tong_thich": latest.get("likes_count"),
            "so_video": latest.get("video_count"),
            "follower_24h": (deltas.get("24h") or {}).get("follower_count"),
            "follower_7d": (deltas.get("7d") or {}).get("follower_count"),
            "xem_tb": d.get("avg_views"),
            "tuong_tac_tb": (d.get("avg_engagement") or 0) / 100,
            "tim_xem_30": (lv.get("rate") or 0) / 100,
            "tim_xem_muc_tieu": (lv.get("min") or 0) / 100,
            "video_30_ngay": lv.get("videos"),
            "video_duoi_muc": lv.get("below"),
            "cap_nhat": at,
        }],
        "tiktok_kpi": [{
            "moc": t["target"], "han": t["deadline"], "hien_tai": t["current"], "con_thieu": t["remaining"],
            "phan_tram": (t["pct"] or 0) / 100, "con_ngay": t["days_left"], "can_moi_ngay": t["need_per_day"],
            "toc_do_7_ngay": t["pace"], "du_kien": t["eta"],
            "dung_tien_do": "Đúng tiến độ" if t["on_track"] else "Chậm tiến độ",
        } for t in kpi.get("targets", [])],
        "tiktok_khung_gio": [{
            "khung": s["label"], "so_video": s["count"], "xem_tb": s["avg_views"], "tim_xem": (s["like_view"] or 0) / 100,
        } for s in kpi.get("slots", [])],
        "tiktok_video": [{
            "id": str(v["id"]), "ngay": v.get("posted") or "", "tieu_de": v.get("title") or "",
            "xem": v.get("views"), "thich": v.get("likes"), "binh_luan": v.get("comments"),
            "chia_se": v.get("shares"), "tim_xem": (v.get("like_view") or 0) / 100, "link": v.get("share_url") or "",
        } for v in d.get("videos", [])],
        "tiktok_tuan_thu": [{
            "id": str(v["id"]), "ngay": v.get("posted") or "", "tieu_de": v.get("title") or "",
            "muc": LEVELS.get(v.get("level"), v.get("level")), "phat_hien": ", ".join(v.get("found") or []),
        } for v in d.get("compliance_issues", [])],
    }
    return {k: {"rows": rows, "meta": meta} for k, rows in files.items()}
