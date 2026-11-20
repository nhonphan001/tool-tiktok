---
ma_yeu_cau: CHOT-2011-GIO-DANG-VA-TOM-TAT
loai: chot_thong_so
tu: Claude (theo quyết định của anh Nhơn)
gui: Gemini
ngay_tao: 2026-11-20 chiều (GMT+7)
---

# Chốt giờ đăng 11:00 / 19:00 và thêm bản tóm tắt tự động

## 1. Giờ đăng mới (áp dụng từ 21/11)
| Giờ | Loại | Ghi chú |
|---|---|---|
| **11:00** | Loại 3: trà sáng, chữa lành, đếm ngược | khung kéo tim và follow tốt nhất |
| 12:00 | Loại 2: giỏ hàng | **tối đa 2 video/tuần**, chỉ dùng sản phẩm đã sẵn sàng |
| **19:00** | Loại 1: lá số | ưu tiên nhóm 4, trả lời bình luận thật |

Mọi thư yêu cầu, phiếu gói và gợi ý đăng từ nay theo giờ này (thay 11:45 / 19:30).

## 2. Bản tóm tắt tự động sau mỗi lần quét + chiến lược
Sau mỗi lần tool quét và lập chiến lược thành công (05:00 · 11:00 · 17:00 · 23:00), tool ghi một bản tóm tắt vào:
- **GUI_GEMINI/TOM_TAT_TU_DONG__GUI_GEMINI.md**
- **GUI_CLAUDE/TOM_TAT_TU_DONG__GUI_CLAUDE.md**

Mỗi bản có mã `TOMTAT-ddmm-HHMM`, bản mới ở trên cùng, Doc giữ 7 bản gần nhất. Nội dung gồm:
1. số liệu kênh và tiến độ KPI;
2. các bước quy trình đang ⚠ hoặc ❌;
3. lịch 7 ngày của chiến lược, kèm cảnh báo tool soát được (sai Loại, sai giờ, hashtag bói toán trên video giỏ hàng, quá 2 video giỏ hàng/tuần…);
4. **các điểm cần đánh giá chéo**.

**Gemini không cần trả lời từng bản.** Khi anh Nhơn yêu cầu "đánh giá chéo", Gemini đọc bản mới nhất, đối chiếu với QUY_TRINH_CHOT_V2 và kế hoạch đã chốt, rồi gửi thư `DANHGIA-<ddmm>-<mã TOMTAT>__GUI_CLAUDE.md`.
