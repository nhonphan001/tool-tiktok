# Khuôn báo cáo (bắt buộc đúng thứ tự)

```
# Quét kênh <hằng ngày|hằng tuần> dd/mm/yyyy      (hoặc: # Đánh giá video <ID> dd/mm/yyyy)

> Nguồn: TikTok Studio, trang Quảng bá, hồ sơ, TikTok Manager /danh-gia/ngu-canh · lấy lúc HH:MM (giờ VN) · chế độ chỉ đọc

## 1. Tóm tắt
(5 dòng: follower, video tốt nhất/kém nhất (số tự nhiên), phát hiện quan trọng nhất, có quảng bá không, việc cần làm ngay)

## 2. Tổng quan kênh          (checklist A)
## 3. Từng video              (checklist B + C + D; mỗi video 1 tiểu mục "### Gói <n> · <ID>")
## 4. Quảng bá                (checklist E; hằng ngày: ghi "không kiểm" nếu bỏ qua)
## 5. Đối chiếu TikTok Manager (checklist F)
## 6. So sánh nhóm và kết luận
## 7. Dữ liệu còn thiếu
## 8. Dữ liệu thô (JSON)
```

## Chỉ số dẫn xuất (tự tính, ghi "(tự tính)")

| Chỉ số | Công thức |
|---|---|
| follow_rate | follower mới ÷ lượt xem × 100 |
| follow_rate_unique | follower mới ÷ người xem duy nhất × 100 |
| like_rate | thích ÷ lượt xem × 100 |
| save_rate | lưu ÷ lượt xem × 100 |
| comments_per_1k | bình luận ÷ lượt xem × 1000 |
| rewatch | lượt xem ÷ người xem duy nhất |
| watch_pct | thời gian xem TB ÷ độ dài × 100 |
| organic_views / organic_followers | tổng − trả phí (nếu có quảng bá) |
| h_score | số quy tắc H1–H6 đạt (0–6) |

## Khối JSON (cuối file, trong ```json … ```, đúng tên khoá)

```json
{
  "schema": "tiktok-studio-quet/v1",
  "mode": "hang_ngay|hang_tuan|video",
  "snapshot_at": "2026-11-25T16:30+07:00",
  "channel": {
    "followers": 0, "followers_net_7d": 0, "followers_by_day": {"2026-11-25": 0},
    "views_7d": 0, "profile_views_7d": 0, "likes_7d": 0, "comments_7d": 0, "shares_7d": 0,
    "follower_active_hours": {"0": 0, "12": 0, "19": 0}, "follower_active_days": {"T2": 0},
    "audience_age_pct": {}, "audience_gender_pct": {}, "pinned": [], "bio": ""
  },
  "videos": [
    {
      "video_id": "", "goi": "", "loai": 0, "scenes": 0, "posted_at": "", "duration_s": 0,
      "promoted": false, "promo": {"spent": 0, "views": 0, "followers": 0, "likes": 0},
      "metrics": {"views": 0, "unique_viewers": 0, "likes": 0, "comments": 0, "shares": 0, "saves": 0,
                  "new_followers": 0, "avg_watch_s": 0, "completion_rate": 0},
      "organic": {"views": 0, "followers": 0},
      "derived": {"follow_rate": 0, "like_rate": 0, "save_rate": 0, "comments_per_1k": 0, "rewatch": 0, "watch_pct": 0},
      "retention_pct": {"1": 0, "2": 0, "3": 0, "5": 0, "8": 0, "10": 0, "15": 0, "20": 0, "30": 0},
      "likes_peak_second": null,
      "traffic_source_pct": {"for_you": 0, "following": 0, "profile": 0, "search": 0, "sound": 0, "other": 0},
      "search_queries": [{"q": "", "pct": 0}],
      "views_by_hour_72h_peak": "", "views_by_day": {},
      "viewer_type_pct": {"new": 0, "returning": 0, "follower": 0, "non_follower": 0},
      "audience_age_pct": {}, "audience_gender_pct": {},
      "hook": {"h1_bright_motion": null, "h1_speech_at_s": null, "h2_text": "", "h2_chars": 0, "h3_cta_second": null,
               "h3_cta_form": "", "h4_caption_chars": 0, "h5_time_words": false, "h6_consistent": null, "h_score": 0},
      "script_mismatch": [],
      "labels": {"ai_generated": null, "commercial": null},
      "comments": {"total": 0, "with_birth": 0, "unanswered_birth": 0, "samples": []},
      "api_vs_studio_diff_pct": {"views": 0, "likes": 0}
    }
  ],
  "promote": {"spent_7d": 0, "orders": [], "active": []},
  "manager_mismatch": {"videos_without_package": [], "packages_missing_video": []},
  "groups": {"loai1_vs_loai3": "", "slot_11_vs_1230_vs_19": "", "scenes_4_vs_7": "", "dip_vs_evergreen": "", "h_pass_vs_fail": ""},
  "working": [], "drop": [], "next_changes": []
}
```

Một video chỉ có số tổng (chưa vào được trang phân tích) thì vẫn ghi vào `videos`, các trường còn lại để `null`.
