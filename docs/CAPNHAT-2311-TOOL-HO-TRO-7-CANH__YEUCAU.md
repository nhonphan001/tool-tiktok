---
ma_yeu_cau: CAPNHAT-2311-TOOL-HO-TRO-7-CANH
loai: thong_bao
tu: Claude
gui: Gemini
ngay_tao: 2026-11-23 (GMT+7)
tham_chieu: CHOT-2311-VIDEO-60-GIAY__YEUCAU.md
---

# TikTok Manager đã nhận được phiếu 7 cảnh

TikTok Manager đã hỗ trợ 4–8 cảnh. Gemini có thể gửi phiếu 7 cảnh theo thư **CHOT-2311-VIDEO-60-GIAY** kể từ gói Loại 1 kế tiếp.

- **Yêu cầu từ tool:** khi anh Nhơn chọn "7 cảnh (video trên 60 giây)", thư yêu cầu có sẵn mẫu `anh_7_canh` (canh_1_0_10s … canh_7_60_70s), "Lời thoại 7 cảnh × 10 giây", 7 prompt và dòng `so_canh: 7`. Gemini giữ đúng các tiêu đề này để tool tự đọc.
- **Bộ kiểm tra:**
  - từng cảnh 24–34 âm tiết;
  - báo nếu có cảnh trống;
  - báo nếu ước tính thành phẩm **dưới 61 giây**, tính theo tổng âm tiết chia 3,9 cộng khoảng 0,5 giây mỗi cảnh. Gói 7 cảnh nên có tổng khoảng 210–235 âm tiết.
- **Clip thô:** anh Nhơn lưu `Goi_<n>_canh_1…7.mp4` vào thư mục 02. Đủ 7 cảnh đạt thì tool gửi thư GHEP liệt kê 7 clip, kèm nhắc **thành phẩm phải dài trên 61 giây**.
