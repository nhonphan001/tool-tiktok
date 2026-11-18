"""Chuyển /api/public/summary của TikTok Manager thành các tệp JSON {rows, meta} cho Bảng điều hành kênh.

Cách dùng: python3 scripts/export_dashboard.py <summary.json> <thư_mục_ra>
Chỉ đọc tệp đầu vào và ghi tệp JSON vào thư mục ra; không gọi mạng.
"""
import json
import os
import sys


def main(src: str, out: str) -> None:
    d = json.load(open(src, encoding="utf-8"))
    os.makedirs(out, exist_ok=True)
    latest = d.get("latest") or {}
    deltas = d.get("deltas") or {}
    kpi = d.get("kpi") or {}
    lv = kpi.get("like_view") or {}
    at = latest.get("taken_at") or d.get("updated_at") or ""
    meta = [
        {"label": "Nguồn", "value": "TikTok Manager · /api/public/summary (số lấy từ TikTok API, không làm tròn)"},
        {"label": "Lần quét", "value": at},
    ]

    def dump(name, rows):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump({"rows": rows, "meta": meta}, f, ensure_ascii=False, indent=1)

    dump("tiktok_kenh.json", [{
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
    }])
    dump("tiktok_kpi.json", [{
        "moc": t["target"],
        "han": t["deadline"],
        "hien_tai": t["current"],
        "con_thieu": t["remaining"],
        "phan_tram": (t["pct"] or 0) / 100,
        "con_ngay": t["days_left"],
        "can_moi_ngay": t["need_per_day"],
        "toc_do_7_ngay": t["pace"],
        "du_kien": t["eta"],
        "dung_tien_do": "Đúng tiến độ" if t["on_track"] else "Chậm tiến độ",
    } for t in kpi.get("targets", [])])
    dump("tiktok_khung_gio.json", [{
        "khung": s["label"], "so_video": s["count"], "xem_tb": s["avg_views"], "tim_xem": (s["like_view"] or 0) / 100,
    } for s in kpi.get("slots", [])])
    dump("tiktok_video.json", [{
        "id": str(v["id"]),
        "ngay": v.get("posted") or "",
        "tieu_de": v.get("title") or "",
        "xem": v.get("views"),
        "thich": v.get("likes"),
        "binh_luan": v.get("comments"),
        "chia_se": v.get("shares"),
        "tim_xem": (v.get("like_view") or 0) / 100,
        "link": v.get("share_url") or "",
    } for v in d.get("videos", [])])
    levels = {"violation": "Vi phạm (có giỏ hàng)", "violation_if_cart": "Vi phạm nếu có giỏ hàng", "fortune_risk": "Rủi ro bói toán/bùa – không quảng cáo", "warning": "Cần xem lại"}
    dump("tiktok_tuan_thu.json", [{
        "id": str(v["id"]), "ngay": v.get("posted") or "", "tieu_de": v.get("title") or "",
        "muc": levels.get(v.get("level"), v.get("level")), "phat_hien": ", ".join(v.get("found") or []),
    } for v in d.get("compliance_issues", [])])
    print("OK", at)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
