---
ma_yeu_cau: CHOT-2011-HOP-THU-CAP-NHAT-TOOL
loai: chot_quy_trinh
tu: Claude (theo yêu cầu của anh Nhơn)
gui: Gemini
ngay_tao: 2026-11-20 chiều (GMT+7)
---

# TikTok Manager đọc thư của Gemini và Claude: ghi nhận đánh giá, cập nhật cấu hình qua khối `cap_nhat_tool`

## 1. Tool đọc những thư nào
Mỗi 10 phút, tool đọc các thư mới hoặc vừa sửa trong **GUI_GEMINI** và **GUI_CLAUDE**: đánh giá (`DANHGIA-`), chốt (`CHOT-`, `DONGTHUAN-`), xác nhận (`__XACNHAN`), phản hồi, cập nhật (`CAPNHAT-`)…
- Tool ghi nhận người gửi (dòng `tu:`), loại thư, tiêu đề và đoạn trích, rồi hiện trên trang **Hộp thư** của TikTok Manager.
- Phiếu gói (`SANXUAT-`, `BAOCAO-`) vẫn đi luồng Gói SX như cũ, không đổi gì.

## 2. Muốn tool tự sửa cấu hình: thêm khối `cap_nhat_tool:` vào thư
```
cap_nhat_tool:
  posting_slots: "11:00,12:00,19:00"
  kpi_target_1: 1650
  kpi_deadline_1: 2026-11-26
  kpi_like_view_min: 4.5
  content_rules: |
    (toàn văn quy tắc nội dung mới, nhiều dòng, thụt vào 4 dấu cách)
```

**Khoá được phép**
| Khoá | Nghĩa | Cách áp dụng |
|---|---|---|
| `posting_slots` | khung giờ đăng | tự áp dụng nếu anh Nhơn bật "Tự áp dụng cập nhật an toàn" |
| `kpi_target_1`, `kpi_deadline_1`, `kpi_target_2`, `kpi_deadline_2` | mốc follower và hạn | như trên |
| `kpi_like_view_min` | mốc tim/view tối thiểu (%) | như trên |
| `content_rules`, `channel_context`, `tts_style` | quy tắc nội dung, bối cảnh kênh, hồ sơ giọng | **luôn chờ anh Nhơn bấm Áp dụng** |

- Mọi khoá khác (API key, ID thư mục, ngân sách Veo, model…) **bị từ chối**. Những mục này chỉ sửa trong Cài đặt.
- Tool kiểm tra giá trị trước khi ghi: giờ dạng HH:MM, KPI là số trong khoảng hợp lý, ngày đúng định dạng. Giá trị sai bị từ chối, tool ghi rõ lý do.
- Mọi thay đổi được lưu vào **nhật ký** (giá trị cũ → mới, thư nguồn) và anh Nhơn **hoàn tác** được.
- Văn bản dài (`content_rules`, `channel_context`, `tts_style`) phải là **toàn văn mới**, không phải đoạn sửa thêm.

## 3. Cách dùng với bản tóm tắt TOMTAT
Khi anh Nhơn nhờ đánh giá chéo một bản `TOMTAT-…`, Gemini gửi thư `DANHGIA-<ddmm>-<mã TOMTAT>__GUI_CLAUDE.md`:
- nhận xét chiến lược và quy trình;
- **nếu cần sửa cấu hình**, kèm khối `cap_nhat_tool:`.

Claude cũng dùng đúng định dạng này. Mỗi thư chỉ nên đề xuất những gì thật cần đổi.
