# CHOT-2611: Bộ quy tắc kịch bản bản 2 và điều chỉnh lịch 27/11–02/12

**Gửi:** Gemini · **Từ:** Antigravity (theo chỉ đạo của anh Nhơn ngày 26/11/2026)  
**Áp dụng ngay:** từ **Gói 34 và Gói 35+** trở đi (bản Bộ quy tắc đã cập nhật trong `app/defaults/script_rules.md` và bộ kiểm tra tự động `app/packages.py`).

## 1. Hai bổ sung bắt buộc trong Bộ quy tắc kịch bản (bản 2)

1. **Đọc ĐỦ 4 SỐ năm sinh bằng chữ (sửa quy tắc B4):**
   - Trong lời thoại và prompt video, **luôn đọc đủ 4 số năm sinh bằng chữ**: ví dụ `"một chín chín mươi"` (1990), `"một chín tám tư"` (1984), `"một chín tám sáu"` (1986), `"một chín bảy ba"` (1973).
   - **Không đọc tắt 2 số cuối** (`"chín mươi"`, `"tám tư"`, `"bảy ba"`, `"chín mốt"`). Năm dạng chữ số (`1990`) chỉ để trên chữ hook khung 0 và caption.
2. **Dùng từ thuần Việt `"bình luận"` thay cho `"comment"` (sửa quy tắc B3, C4, E1, E3):**
   - Không dùng từ `"comment"` trong lời thoại, caption hay bình luận ghim.
   - CTA chuẩn mới: `"bình luận năm sinh để Cô Kim xem giúp"`, `"bình luận con giáp của cả nhà"`, `"để lại ngày sinh dưới bình luận để Cô Kim giải mã"`.

*(Cả 2 quy tắc trên đã được đưa vào `packages.check()` để Gemini API tự kiểm và tự sửa khi soạn Gói 35+.)*

## 2. Điều chỉnh lịch tuần thử nghiệm KHÔNG quảng bá (`26/11 – 02/12/2026`)

Do **Gói 33** (*Nữ Canh Ngọ 1990*) hoàn tất lúc `15:18` và được anh Nhơn đăng vào **`19:00` tối `26/11`** (ô `19:00 × Kiểu B`), lịch các ngày còn lại điều chỉnh nhẹ để giữ cân bằng **3 video `12:30` vs 3 video `19:00`** và **3 Kiểu A vs 3 Kiểu B**, đồng thời loại bỏ lỗi trùng Canh Ngọ 1990 từ bảng Chiến lược ID 50:

| Ngày | 11:00 Loại 3 (4 cảnh, ~30s) | Loại 1 (7 cảnh, > 61s) | Ô phép thử | Gói |
| :--- | :--- | :--- | :---: | :---: |
| T5 26/11 | Gói 32 "Rót chén trà cho người thương" *(đã đăng)* | **19:00** Gói 33 Nữ Canh Ngọ 1990 *(đăng tối nay)* | `19:00 × B` | 32, 33 |
| **T6 27/11** | Giữa ngày săn sale, chậm lại bên ấm trà | **12:30** Nữ Bính Dần 1986 · Năm Đinh Mùi 2027 | **`12:30 × B`** *(đổi từ 19:00 để cân bằng phép thử)* | **35, 36** |
| **T7 28/11** | Buông chuyện ngoài tầm với | **12:30** Nữ Mậu Thìn 1988 · Năm Đinh Mùi 2027 | `12:30 × A` | 37, 38 |
| **CN 29/11** | Một ngày nghỉ trọn vẹn | **19:00** **Gói 34** Trả lời 1 bình luận thật mới *(chọn tuổi khác, KHÔNG lặp Quý Sửu 1973 đã đăng ở Gói 27)* | ngoài phép thử | 39, **34** |
| **T2 30/11** | Đầu tuần nhẹ nhàng *(KHÔNG dùng "an lành" / "an yên")* | **12:30** Nữ Tân Mùi 1991 · Năm Đinh Mùi 2027 | `12:30 × B` | 40, 41 |
| **T3 01/12** | Mốc 01/12: "Còn đúng 30 ngày khép lại 2026" | **19:00** Nữ Quý Dậu 1993 · Năm Đinh Mùi 2027 | `19:00 × A` | 42, 43 |
| **T4 02/12** | Mỉm cười với chuyện chưa trọn | **19:00** Kiến thức nền: "Dụng Thần là gì?" | ngoài phép thử | 44, 45 |

- **Gói 25** (trạng thái `Sẵn sàng dựng` trên tool, mốc "Còn 38 ngày"): **bỏ, không đăng** (đã quá ngày `23/11` và trùng chủ đề tha thứ của Gói 30).
- **Gói 16** (Loại 2 — Khăn lau bàn thờ Thiên Phúc): tạm giữ sang cuối tháng 12 (gần dịp Ông Táo/Tết) và chỉ dựng khi có ảnh/clip sản phẩm thật (`C.9`). Tương tự, các đề xuất Loại 2 (Ấm tử sa / Chén sứ) ở Chiến lược ID 50 chỉ đưa vào khung `12:00` khi sẵn ảnh/clip thật.

— Antigravity
