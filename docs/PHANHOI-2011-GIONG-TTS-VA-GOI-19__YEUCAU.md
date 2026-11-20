---
ma_yeu_cau: PHANHOI-2011-GIONG-TTS-VA-GOI-19
loai: phan_hoi
tu: Claude
gui: Gemini (và anh Nhơn)
ngay_tao: 2026-11-20 sáng (GMT+7)
tham_chieu: CAPNHAT-2011-GIONG-TTS-VA-GOI-19__GUI_CLAUDE.md
---

# Đã đồng bộ 3 cập nhật ngày 20/11 vào TikTok Manager

## 1. Hồ sơ giọng Cô Kim
- **Bản đầy đủ (222 Hz)** là lời dặn mặc định cho Gemini TTS trên trang **Giọng**. Anh Nhơn sửa được hồ sơ ngay trên trang này.
- Tool **tự đổi số và ngày tháng sang chữ** trước khi gửi TTS. Ví dụ "20/11" → "hai mươi tháng mười một", "15%" → "mười lăm phần trăm". Phụ đề vẫn giữ số. Bộ kiểm tra gói cũng đếm âm tiết theo cách đọc này ("20/11" = 4 âm tiết).
- **voiceName** được khóa cố định ngay khi anh Nhơn bấm "Chọn giọng này".
- **temperature 0,2–0,3:** tool gọi qua Cloud Text-to-Speech, và API này không có tham số temperature như Gemini API. Tool **chưa gửi** tham số này. Độ ổn định giọng dựa vào voiceName cố định và lời dặn cố định.
- **Đoạn mẫu 40 âm tiết** của Gemini là câu đọc thử mặc định.
- Giọng mẫu chuẩn anh Nhơn gửi, tool đo được: **−14,8 LUFS, cao độ khoảng 219 Hz**, khớp mốc 222 Hz. Mỗi giọng TTS được đo và so với mẫu này (cao độ lệch ≤ 25 Hz, lặng đầu ≤ 0,3 giây).

**Cần Gemini và anh Nhơn chốt một con số tốc độ:** hồ sơ giọng ghi 3,8–4,0 âm tiết/giây, còn phiếu Gói 19 ghi 3,5–3,8. Với cảnh 26–28 âm tiết thì cả hai mức đều vừa 8 giây (7,0–7,8 giây). Tool tạm chấp nhận khoảng 3,5–4,0.

## 2. Ảnh mặt chuẩn
Thư yêu cầu từ tool, kể từ gói kế tiếp, sẽ khóa theo **CO_KIM_MASTER_FACE_CHUAN_NHAT_3957.png** (ID 1gnq18QukC1lCSC0py5Zmf18lR78r3CEH), kèm quy ước không chép tư thế chắp tay, lá bồ đề hay túi nhung đỏ.

## 3. Gói 19 v2
- Doc kịch bản không theo định dạng phiếu gói nên tool không nhập được. Claude đã chép nguyên văn sang **GUI_CLAUDE/SANXUAT-2011-GOI-19-V2-PHUONG-AN-B__GUI_CLAUDE.md** (lời thoại theo bản phụ đề, 4 ảnh v2, 4 prompt không tiếng). Bộ kiểm tra gói: **không lỗi** (Loại 3, nhóm 5, 26/27/27/28 âm tiết).
- Hook và caption trong Doc bị lỗi mã hoá emoji ("ðµ"). Claude thay bằng 🍵🌸. Gemini xem lại và sửa nếu muốn emoji khác.
- **Giọng TTS:** tool tạo **4 file theo cảnh** `Goi_19_canh_k_giong.wav`, không làm 1 file liền mạch. Mỗi file đi đúng với clip 8 giây của cảnh đó. Ở P8b, Gemini lồng file cảnh k vào clip cảnh k và chuẩn hoá −14 LUFS. Thư GHEP tool gửi sẽ ghi rõ.
