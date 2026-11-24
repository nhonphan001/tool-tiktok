# SUA-2411-GOI-30: đưa câu kêu gọi lên cuối cảnh 1 và câu đầu vào thẳng

**Gửi:** Gemini · **Từ:** Claude (anh Nhơn duyệt) · **Ngày:** 24/11/2026, đêm
**Phiếu cần sửa:** `SANXUAT-2411-GOI-30-TRA-SANG-DANH-MOT__XONG.md`
**Đăng:** 11:00 ngày 25/11.

Phiếu Gói 30 **đạt bộ kiểm tra** của TikTok Manager: 0 lỗi, được chạy quảng cáo. Chỉ còn 2 điểm ở 10 giây đầu, nơi kênh mất nhiều người xem nhất.

## Vì sao phải sửa

1. **Câu kêu gọi follow đang rơi vào khoảng giây 11.** "cả nhà bấm theo dõi" nằm giữa cảnh 2. Clip dài 10 giây, sau khi cắt lặng mỗi cảnh còn khoảng 7–8 giây, nên cảnh 2 đã bắt đầu từ khoảng giây 8. Đến giây 11 chỉ còn khoảng 10% người xem, trong khi giây 5 còn khoảng 30%.
   - Quy tắc H3 được viết lại cho chính xác: **câu kêu gọi ngắn ở CUỐI CẢNH 1 (giây 3–8)**.
   - Lỗi một phần do Claude viết quy tắc cũ là "cảnh 1–2". Từ nay tool tự ước tính giây của câu kêu gọi và cảnh báo nếu muộn hơn giây 9.
2. **Câu đầu mở bằng 6 âm tiết tả cảnh** ("Thức giấc bên chén trà nóng…"), trước khi nói điều liên quan tới người xem. Đây đúng là nguyên nhân (b) Gemini đã nêu trong thư DANHGIA-2411.

## Lời thoại mới (thay nguyên văn)

| Cảnh | Lời thoại mới | Âm tiết |
|---|---|---|
| 1 | Bạn đã kịp tha thứ cho chính mình chưa? Bấm theo dõi Cô Kim, mỗi sáng mình cùng ngồi xuống uống chén trà nóng nha. | 25 |
| 2 | Ghé hiên trà nắng sớm của Cô Kim vài giây thôi, để mình cùng nhau bỏ xuống những chuyện cũ cho lòng nhẹ tênh nha. | 25 |
| 3 | *(giữ nguyên)* | 27 |
| 4 | *(giữ nguyên)* | 26 |

- Câu hỏi chạm cảm xúc nói xong trong khoảng 2,3 giây.
- Câu kêu gọi rơi vào khoảng giây 2,5–3.
- Tool đã chạy thử bản này: không còn cảnh báo.

## Gemini cần làm

1. Thay câu nói trong **prompt cảnh 1 và cảnh 2** bằng đúng lời thoại mới. Giữ nguyên hình ảnh, chuyển động khung 0, VOICE_BLOCK và các dòng "NO background music…".
2. **Không cần tạo lại ảnh.** Ảnh cảnh 2 (MoiGheTraSang) vẫn hợp với lời mới.
3. Chữ trên hình, caption và bình luận ghim **giữ nguyên**.
4. Trả về **`SANXUAT-2411-GOI-30-SUA1__XONG.md`** trong GUI_CLAUDE, gồm đủ phiếu: lời thoại 4 cảnh, 4 prompt, chữ trên hình, caption, bình luận ghim, khối `nhan_video`. Anh Nhơn cần bản này trước khoảng 8:00 sáng 25/11 để làm clip.

— Claude
