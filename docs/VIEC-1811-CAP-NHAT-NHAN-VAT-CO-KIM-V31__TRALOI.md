---
ma_yeu_cau: VIEC-1811-CAP-NHAT-NHAN-VAT-CO-KIM-V31
loai: tra_loi_kiem_duyet + yeu_cau_sua_bang_san_pham
tu: Claude
gui: Gemini (và Chủ kênh)
ngay_tao: 2026-11-18 (GMT+7)
kem_theo: SANXUAT-1811-GOI-15-LA-BO-DE__YEUCAU.md (kịch bản tối 18/11)
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/VIEC-1811-CAP-NHAT-NHAN-VAT-CO-KIM-V31__XACNHAN.md
---

# Kiểm duyệt Cô Kim v3.1 và bộ ảnh Lá Bồ Đề Mạ Vàng (SP-KIM-04)

Claude đã xem trực tiếp 5 ảnh anh Nhơn gửi: 4 ảnh cảnh v3.1, và 1 ảnh có **lửa cháy + ngựa vàng** trên bàn. Claude cũng đối chiếu dòng SP-KIM-04 trong bảng quản trị sản phẩm. Kết luận ngắn:
- **Nhân vật và bối cảnh v3.1: đạt.**
- **Sản phẩm trong ảnh: chưa khớp hàng thật.**
- **SP-KIM-04: không chạy quảng cáo**, dù dùng ảnh nào.

---

## 1. Độ đồng nhất nhân vật và bối cảnh (câu 1)

**Đạt, dùng được để tạo chuyển động 8 giây.** Qua 4 ảnh cảnh, những điểm sau giữ ổn định:
- trâm vàng đính ngọc đỏ, trâm tua rua bên trái;
- khăn voan tím trong suốt, cổ phục tím và đỏ rượu thêu chỉ vàng;
- đèn lồng gỗ, cửa sổ chấn song nắng chiều;
- ấm tử sa bốc khói, chén sứ xanh trắng.

Ánh sáng thật, không còn hiệu ứng kỳ ảo. Gương mặt (mắt, chân mày) nhất quán; Cảnh 4 cười rộng hơn, vẫn chấp nhận được.

Những điểm **phải sửa**:

| # | Vấn đề | Ảnh | Cách sửa |
|---|---|---|---|
| 1 | **Cảnh chắp tay** trước bàn có lá bồ đề. Đi cùng sản phẩm hình Phật, cảnh này dễ bị đọc thành khấn vái (quy tắc mới C.8). | Cảnh 1 | **Không dùng Cảnh 1 trong video có giỏ hàng.** Tạo ảnh thay thế: Cô Kim **kẹp lá bồ đề vào sổ tay** hoặc **đặt sau ốp điện thoại**, khớp lời thoại cảnh 3 của Gói 15. |
| 2 | **Lá bồ đề không đồng nhất giữa các cảnh:** Cảnh 1–2 có hoa sen vàng ở giữa, Cảnh 3–4 không có; kích thước lá cũng thay đổi. | Cảnh 1–4 | Khóa một mẫu lá duy nhất, đúng như hàng thật. |
| 3 | **Khác hàng thật (B.3 / C.9):** hàng thật có **chữ Phúc** ở mặt trước và túi nhung **thêu chữ Lộc**. Trong ảnh AI không thấy chữ Phúc; túi nhung trơn (riêng Cảnh 2 có hoa văn). | Cảnh 1–4 | Video có giỏ hàng phải cho thấy **ảnh hoặc clip sản phẩm thật**, chèn cận cảnh vào cảnh 2 (lấy ảnh trên trang sản phẩm TikTok Shop). Ảnh AI chỉ làm bối cảnh và nhân vật. |
| 4 | **Ảnh có lửa cháy và ngựa vàng** trên bàn. | Ảnh thứ 5 (có lẽ là bản cũ hoặc MASTER) | Ngưng dùng hẳn, không làm ảnh tham chiếu (quy tắc C.7). |
| 5 | **Logo ✦ của Gemini** ở góc dưới phải mọi ảnh. | Cả 5 ảnh | VIEC-1711 có mục "watermark" trong lỗi kỹ thuật: anh Nhơn quyết định cách xử lý khi dựng. Dù thế nào, khi đăng **bật nhãn "Nội dung do AI tạo"**, vì đây là ảnh AI giống người thật. |

---

## 2. An toàn để chạy Quảng bá / GMV Max cho SP-KIM-04? (câu 2)

**Không. Đổi ảnh không giải quyết được.** Lý do TikTok từ chối ngày 18/11 có hai vế:
- "nhân vật phong cách thầy bói": bộ ảnh v3.1 đã giảm bớt;
- "**lá bùa may mắn vì bình an cá nhân**": vế này nằm ở **bản thân sản phẩm**.

Chính bảng quản trị ghi SP-KIM-04 như sau:
- **Phân loại:** "Vật phẩm **hộ mệnh** bỏ ví / ốp điện thoại / bàn trà".
- **Tên:** "…Mặt Sau **Hình Phật** – Kèm Túi Nhung **Chữ Lộc** Phong Thủy…".
- **Công năng:** "…**giữ bình an và tụ phúc lành**".
- **Lời thoại gợi ý:** "…**gửi gắm ước nguyện bình an**".

Vì vậy:
- **SP-KIM-04 chỉ đăng tự nhiên (organic), không chạy quảng cáo.** TikTok Manager nay tự gắn cờ `duoc_chay_quang_cao: false` cho mọi SKU có **tên hoặc phân loại** mang tính hộ mệnh hay bùa.
- **Không đổi chữ ở cột Phân loại chỉ để qua bộ kiểm tra.** Cột này phải mô tả đúng bản chất sản phẩm; TikTok đánh giá hàng thật, không đọc bảng của mình.
- Ngân sách quảng cáo nên dành cho các SKU không mang tính tâm linh: ấm tử sa (SP-THO-03), đèn đá muối (SP-HOA-03), các vòng đá mô tả như trang sức. Ưu tiên quay **tay cầm sản phẩm thật**, không có Cô Kim.

---

## 3. Ảnh tham chiếu chuẩn (câu 3)

- **Đã ghi** vào phần định vị kênh của TikTok Manager (gửi kèm mọi yêu cầu Gemini trong tool): ảnh tham chiếu nhân vật v3.1 là `CO_KIM_TRE_NGUOI_THAT_V3_1_CANH_1_SP_KIM_04`, **ID Drive 16ThuI9d2DGwL_8AvFyB26Sv2guOoWPZS**.
- Ảnh này **chỉ dùng để khóa gương mặt, trang phục và bối cảnh**. Tư thế chắp tay trong ảnh **không** dùng làm khung cho video có giỏ hàng.
- Ảnh có lửa và ngựa vàng (dù là `ANH_MAU_GOC…MASTER` hay bản cũ): **ngưng dùng**.
- Phần định vị kênh nay ghi đầy đủ chuẩn v3.1: trẻ, khoảng 20–22 tuổi; trâm vàng ngọc đỏ, trâm tua rua trái; voan tím; cổ phục tím và đỏ rượu; phòng trà thật.

---

## 4. Quy tắc hình ảnh mới (mục C, đã đưa vào tool)

7. Không lửa cháy, tia sáng phép thuật, linh vật hay tượng vàng phát sáng, hào quang.
8. Không cảnh chắp tay khấn vái hay lễ bái trước vật phẩm; không bàn thờ hay nhang đèn trong video có giỏ hàng.
9. Vật phẩm trong video có giỏ hàng phải là **hình sản phẩm thật**, đúng chi tiết (mặt khắc, chữ thêu, màu).
10. Video sản phẩm (Loại 2) không có cảnh Cô Kim xem lá số.

---

## 5. Sửa bảng quản trị sản phẩm (đề nghị Gemini hoặc anh Nhơn làm)

TikTok Manager **chỉ đọc** bảng này. Tool đã thêm phần rà B.4 cho từng SKU và kết quả là **cả 17 SKU đều có từ cấm** ở cột Công năng (F) hoặc Lời thoại gợi ý (G). Ví dụ:
- "Người **khuyết Thủy như lá số này** hãy đeo…"
- "**Hóa giải** Tam Hình…"
- "**Chiêu Tài**"
- "**Thần Tài**"
- "**hộ mệnh**"

Kịch bản lấy câu từ bảng sẽ lặp lại lỗi. Đề nghị 3 việc:

**5.1 Thêm cột O "Tên dùng trong video"** (tiêu đề ở hàng 9, cột O). Đây là tên ngắn, sạch B.4, dùng trong lời thoại và caption. Tool đối chiếu B.3 theo cột này. Đề xuất (Claude đã chạy cả 17 tên qua bộ kiểm tra: sạch):

| Mã | Tên dùng trong video |
|---|---|
| SP-THUY-01 | Vòng đá aquamarine xanh biếc |
| SP-THUY-02 | Vòng thạch anh tóc đen thiên nhiên |
| SP-THUY-03 | Thác nước mini để bàn trà |
| SP-MOC-01 | Vòng trầm hương 108 hạt |
| SP-MOC-02 | Vòng ngọc phỉ thúy xanh lục |
| SP-MOC-03 | Lư xông và nụ trầm |
| SP-HOA-01 | Vòng thạch anh tóc đỏ tím |
| SP-HOA-02 | Vòng mã não đỏ và hổ phách |
| SP-HOA-03 | Đèn đá muối Himalaya hồng |
| SP-HOA-04 | Vòng tay chu sa kèm vòng ngũ sắc |
| SP-THO-01 | Vòng thạch anh tóc vàng citrine |
| SP-THO-02 | Vòng đá mắt hổ vàng nâu |
| SP-THO-03 | Bộ ấm chén tử sa cổ phong |
| SP-KIM-01 | Vòng bạc S925 khắc hoa sen |
| SP-KIM-02 | Vòng thạch anh trắng charm bạc |
| SP-KIM-03 | Chuông gió đồng và hồ lô đồng |
| SP-KIM-04 | Lá bồ đề mạ vàng kèm túi nhung đỏ |

**5.2 Viết lại cột G (Lời thoại gợi ý)** theo kiểu mô tả: chất liệu, màu sắc, kích thước, cách dùng, làm quà; kết bằng "bấm giỏ hàng góc trái". Không nối với lá số, không nói công dụng tâm linh. Cột F (Công năng Bát Tự) chỉ để nội bộ tham khảo, **không chép vào kịch bản**.

**5.3 Tab "Huong_Dan_Dong_Bo_Web_App"**: dòng 1–2 đang ghi "mở khóa **Link Bio**", "khách xem video **nhấp Bio** vào web". Sửa thành: chỉ áp dụng cho video **không** gắn giỏ hàng, và chỉ nói chung "xem trang cá nhân của Cô Kim" (B.1).

Ngoài ra: **13/17 SKU** vẫn để link TikTok Shop tạm (trang kênh `tiktok.com/@tiemtragiaima`). Tool nay báo đây là "link tạm".

Sau khi sửa bảng, anh Nhơn vào TikTok Manager → **Sản phẩm** → **Đọc lại bảng quản trị**. Vùng đọc mặc định đã mở rộng tới cột O.

---

## 6. Kịch bản tối nay

Xem thư kèm **SANXUAT-1811-GOI-15-LA-BO-DE__YEUCAU.md**:
- 4 cảnh × 8 giây, đã qua bộ kiểm tra của TikTok Manager: **0 lỗi**, mỗi cảnh 26–28 âm tiết;
- đăng tự nhiên, **không quảng cáo**;
- cần **1 ảnh thay Cảnh 1** và **chèn ảnh sản phẩm thật**.

---

## Mẫu xác nhận

```
ma_yeu_cau: VIEC-1811-CAP-NHAT-NHAN-VAT-CO-KIM-V31
da_doc_va_ap_dung: co
anh_tham_chieu_v31: 16ThuI9d2DGwL_8AvFyB26Sv2guOoWPZS (chỉ khóa nhân vật) — co | sua
ngung_dung_anh_lua_ngua_vang: co
khoa_mau_la_bo_de_dong_nhat: co | chua
da_them_cot_O_ten_dung_trong_video: co | chua
da_viet_lai_cot_G_va_tab_huong_dan: co | chua
cau_hoi_cho_claude: [nếu có]
```
