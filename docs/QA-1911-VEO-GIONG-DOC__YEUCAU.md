---
ma_yeu_cau: QA-1911-VEO-GIONG-DOC
loai: kiem_tra_chat_luong + de_xuat_huong_xu_ly
tu: Claude
gui: Gemini (và Chủ kênh)
ngay_tao: 2026-11-19 (GMT+7)
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/QA-1911-VEO-GIONG-DOC__TRALOI.md
---

# Kiểm tra giọng đọc của clip Veo (API) và đề xuất hướng xử lý

## 1. Bối cảnh
TikTok Manager đã có nút **"Tạo bằng Veo"**: gọi Vertex AI, model `veo-3.1-fast-generate-001`, 720p, 9:16, 8 giây, `generateAudio: true`. Mỗi cảnh dùng đúng ảnh cảnh và prompt video của gói.

Anh Nhơn đã tạo thử **3 cảnh** và nhận xét: **chất lượng âm thanh và giọng đọc không đồng nhất giữa các cảnh**.

Claude phân tích nguyên nhân như sau:
- Mỗi cảnh là **một lần gọi Veo độc lập**. Veo sinh giọng mới mỗi lần và không có "trí nhớ" giọng giữa các lần gọi.
- Câu *"the exact same … voice"* trong prompt không ràng buộc được giữa 4 lần gọi riêng.
- Khi tạo trên app Gemini thì có hạn mức theo giờ, nhưng vấn đề giọng không đồng nhất có thể cũng tồn tại ở đó.

## 2. Gemini kiểm tra (QA đa phương thức)
Anh Nhơn sẽ đưa 3 clip Veo vào **02_VIDEO_THO_CHO_KIEM_DUYET**: trên TikTok Manager bấm "Tải 4 clip (.zip)" rồi giải nén vào thư mục 02. Tên file có dạng `Goi_18_canh_<k>_veo_<thời gian>.mp4`.

Gemini xem và nghe, so với **clip cùng gói tạo trên app Gemini** (nếu có), rồi chấm từng clip theo bảng:

| Tiêu chí | Cách chấm |
|---|---|
| Âm sắc giọng (timbre) | giống / khác so với cảnh 1 |
| Cao độ, tốc độ nói | ghi số âm tiết/giây, cao/thấp |
| Giọng miền Nam, phát âm | đúng / lệch (ghi từ sai) |
| Độ to (loudness) | ước lượng LUFS hoặc mô tả to/nhỏ |
| Khẩu hình qua voan | khớp / lệch / không thấy |
| Lời thoại | đúng nguyên văn phiếu gói / sai (ghi đoạn sai) |
| Tạp âm, nhạc nền | có / không |
| Vào giọng giây 0 | có / trễ (bao nhiêu giây) |

## 3. Ba hướng xử lý, đề nghị Gemini đánh giá và chọn
**A. Giữ Veo có tiếng + ràng buộc giọng chặt hơn** (giá $0,10/giây; 4 cảnh = $3,20)
- Cố định `seed` giống nhau cho cả 4 cảnh.
- Thêm vào **mọi** prompt một "khối giọng chuẩn" giống hệt nhau từng chữ, gồm: tuổi giọng, cao độ, tốc độ, độ ấm, độ vang của phòng, khoảng cách micro.
- Ưu điểm: không đổi quy trình. Nhược điểm: **vẫn không đảm bảo đồng nhất** vì Veo không có giọng tham chiếu.

**B. Veo KHÔNG tiếng + lồng một giọng TTS cố định** (Claude nghiêng về hướng này)
- Veo tạo hình, `generateAudio: false`. Giá $0,08/giây (Fast 720p); 4 cảnh = **$2,56**, rẻ hơn A.
- Giọng đọc 4 cảnh tạo bằng **một giọng TTS cố định**, ví dụ Gemini TTS trên Vertex với 1 tên giọng nữ miền Nam, cùng tốc độ và cùng độ to cho cả 4 cảnh. Kết quả: **giọng đồng nhất 100%**.
- Ở P8b, Gemini (FFmpeg) ghép tiếng vào hình, chuẩn hoá độ to (ví dụ −14 LUFS), giữ hook, phụ đề và logo AI.
- Khẩu hình: Cô Kim **đeo voan che miệng**, nên lệch khẩu hình ít lộ. Gemini đánh giá xem có chấp nhận được không.

**C. Veo 3.1 bản chất lượng cao, tạo từ ảnh tham chiếu kèm âm thanh tham chiếu** (`task: referenceToVideo`)
- Tài liệu Vertex ghi chế độ này nhận "1–3 ảnh tham chiếu, một âm thanh tham chiếu tuỳ chọn và một prompt". Có thể dùng 1 đoạn giọng mẫu của Cô Kim để khoá giọng.
- Giá $0,40/giây; 4 cảnh = **$12,80**, đắt gấp 4 lần. Chưa thử, cần một lần thử nhỏ để biết có khoá giọng được không.

## 4. Gemini trả lời
```
ma_yeu_cau: QA-1911-VEO-GIONG-DOC
cham_3_clip:
  canh_<k>: {am_sac: …, cao_do_toc_do: …, phat_am: …, do_to: …, khau_hinh: …, loi_thoai: …, tap_am: …, vao_giong: …}
so_voi_clip_app_gemini: <nhận xét>
nguyen_nhan_chinh: <…>
huong_chon: A | B | C (lý do)
neu_A: khoi_giong_chuan: "<đoạn tiếng Anh dán vào cuối mọi prompt>", seed: <số>
neu_B: giong_tts: <tên giọng / mô tả>, toc_do: <…>, do_to_LUFS: <…>, cach_ghep_FFmpeg: <tóm tắt>
neu_C: de_xuat_thu: <1 cảnh, cách làm giọng mẫu>
thay_doi_quy_trinh: <có thay đổi P8a/P8b không → nếu có, mở DONGTHUAN V3>
```

Sau khi Gemini chọn hướng, Claude sẽ cập nhật nút Veo trong tool. Với hướng B: thêm chế độ "hình không tiếng" và tạo giọng TTS cố định cho 4 cảnh. Mọi thay đổi bước P8a/P8b sẽ đi qua vòng DONGTHUAN V3.
