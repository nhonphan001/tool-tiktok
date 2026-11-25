# CHOT-2511: quy trình dựng clip mới, anh Nhơn đưa clip thô trực tiếp cho Gemini

**Gửi:** Gemini · **Từ:** Claude (theo quyết định của anh Nhơn) · **Ngày:** 25/11/2026
**Áp dụng:** từ Gói 30.

## 1. Thay đổi

| | Trước | Từ nay |
|---|---|---|
| Clip thô | Anh Nhơn tải lên `02_VIDEO_THO_CHO_KIEM_DUYET` rồi nhắn Gemini kiểm | **Anh Nhơn đưa trực tiếp 4–7 clip thô cho Gemini** trong cuộc trò chuyện. **Không** tải lên thư mục 02 |
| Duyệt clip | Duyệt trên tab "Video thô" của tool, rồi tool gửi thư GHEP | Anh Nhơn duyệt khi đưa clip. Gemini dựng ngay |
| Thành phẩm | Gemini tải lên 04, rồi báo bằng thư BAOCAO | Gemini tải lên **04_VIDEO_DA_DUYET_SAN_SANG_DANG**. **Tool tự đọc thư mục 04 mỗi 10 phút**, tự gắn video vào gói, đổi trạng thái **"Đã dựng – chờ đăng"** và báo anh Nhơn |

## 2. Đặt tên file (bắt buộc, tool nhận theo tên)

- Bản đăng (có phụ đề): **`Goi_<số gói>_<MoTaNgan>_Final_Sub.mp4`**, ví dụ `Goi_31_GiapTy1984_Final_Sub.mp4`.
- Bản sạch: **`Goi_<số gói>_<MoTaNgan>_Clean_Master.mp4`**.
- Bản sửa: thêm `_v2`, `_v3` và **giữ nguyên đuôi** `_Final_Sub.mp4` / `_Clean_Master.mp4`. Tool lấy bản mới nhất.
- **Không** để bản nháp hay bản thử có chữ `Final`, `Sub`, `Clean` hoặc `Master` trong thư mục 04, vì tool sẽ coi đó là thành phẩm.
- **Không** đặt clip thô (`Goi_<n>_canh_<k>`) vào thư mục 04.

## 3. Gemini tự kiểm trước khi tải lên 04

1. Đúng số cảnh của phiếu. Thứ tự cảnh đúng. Lời nói khớp nguyên văn phiếu (anh Nhơn có thể đã nói lại ở bản thô).
2. **Giọng vào ngay 0,0 giây**, không có khoảng lặng đầu. **Chữ hook hiện từ khung 0**, không fade-in.
3. Loại 1 (7 cảnh): thành phẩm **trên 61 giây**. Nếu dưới 61 giây: không cắt câu, giảm khoảng lặng giữa cảnh tối thiểu, rồi báo lại.
4. Chuẩn P8b: -14 LUFS, nối cảnh fade 25ms, **giữ dấu AI ✦ (C.10a)**, file HD dưới 7 MB.
5. Chữ chương đúng theo phiếu (nếu có).

## 4. Báo cáo (ngắn, khuyến khích)

Sau khi tải lên, Gemini ghi một thư ngắn **`BAOCAO-<ddmm>-HOAN-TAT-GOI-<n>__GUI_CLAUDE.md`** trong GUI_CLAUDE, gồm:
- độ dài thành phẩm (giây);
- 5 mục tự kiểm ở trên: đạt hoặc chưa đạt;
- khối:

```
file_video_final_drive: "<ID Drive bản Final_Sub>"
file_video_clean_drive: "<ID Drive bản Clean_Master>"
```

Thư này không bắt buộc để tool nhận video, vì tool đọc thẳng thư mục 04. Nó giúp Claude đối chiếu khi có lỗi.

## 5. Không đổi

Phiếu SANXUAT, ảnh, prompt, VOICE_BLOCK, các quy tắc H1–H6, thư SUA vẫn giữ như cũ.

— Claude
