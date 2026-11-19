---
ma: QUY_TRINH_CHOT_V2
hieu_luc_tu: 2026-11-19 10:15 (GMT+7)
dong_thuan:
  claude: dong_y (DONGTHUAN-1911-QUY-TRINH-V1 + V2)
  gemini: dong_y (DONGTHUAN-1911-QUY-TRINH-V1__TRALOI 09:33 · V2__TRALOI 10:11)
  tiktok_manager: báo cáo tự động /system (bảng P1–P13 khớp bản này)
  chu_kenh: "đồng ý P8a, chốt" (19/11/2026)
thay_doi_so_voi_v1: tách P8 thành P8a + P8b; thêm quy tắc C.10a (giữ dấu nhận diện AI)
---

# Quy trình sản xuất đã chốt – V2

Muốn đổi quy trình này phải mở một vòng **DONGTHUAN** mới. Không bên nào tự đổi.

| Mã | Bước | Ai làm |
|---|---|---|
| P1 | Quét số liệu TikTok lúc 05:00 · 11:00 · 17:00 · 23:00 | Tool |
| P2 | Ghi báo cáo lên Drive 06 → NotebookLM (kèm mục 10 "Tình trạng hệ thống") | Tool |
| P3 | Tạo yêu cầu ở trang **Yêu cầu Gemini**. Tool giữ số gói và soạn thư gồm quy tắc, số liệu kênh, mẫu trả lời | Anh Nhơn + Tool |
| P4 | Tool ghi thư vào Doc **HOP_THU_TOOL__YEUCAU** (GUI_GEMINI) | Tool |
| P5 | Gemini viết kịch bản, 4 ảnh **Cô Kim v3.3** (MASTER `1R-eg5lKwn_8rHbMNXGPnmf3na-4K0njV`) và 4 prompt video 8 giây, gửi thư `SANXUAT-…__XONG` vào GUI_CLAUDE | Gemini |
| P6 | Tool dò thư trả lời, thư sửa và thư BAOCAO mỗi 10 phút, rồi thông báo | Tool |
| P7 | **Nhập từ hộp thư → Lưu & kiểm tra.** Tool kiểm tra B.1–B.4, Loại 1/2/3, prompt khớp lời thoại, không nhạc nền | Anh Nhơn + Tool |
| **P8a** | Tạo 4 clip thô 8 giây trên Veo/Flow bằng 4 prompt trong **Bộ đăng TikTok**, đưa lên `02_VIDEO_THO_CHO_KIEM_DUYET` | **Anh Nhơn** |
| **P8b** | Gemini kiểm tra (QA) clip thô, dùng FFmpeg cắt, ghép, gắn hook và phụ đề, **giữ dấu nhận diện AI**, lưu vào `04_VIDEO_DA_DUYET_SAN_SANG_DANG`, gửi thư `BAOCAO-…-GOI-n-…` có `file_video_final_drive` và `file_video_clean_khong_sub`. Clip lỗi chuyển sang `03_VIDEO_CAN_CHINH_SUA` | **Gemini** |
| P9 | Tool lấy link video vào gói và hiện **Bộ đăng TikTok** (Chép / Xem / Tải) | Tool |
| P10 | Đăng bài: chép đúng caption trong phiếu, bật nhãn "Nội dung do AI tạo", chỉ gắn giỏ hàng với Loại 2. Chỉ bật Quảng bá khi tool báo **Được chạy quảng cáo** | Anh Nhơn |
| P11 | Tool tự gắn video vào gói ở lần quét kế tiếp và tính KPI theo gói | Tool |
| P12 | SKU mới: dán link → tool tự điền bằng Gemini API → duyệt, điền giá → tool thêm dòng vào bảng sản phẩm | Anh Nhơn + Tool |
| P13 | Claude sửa và nâng cấp tool, kiểm duyệt nội dung, viết thư VIEC/DONGTHUAN, cập nhật dashboard lúc 05:17 | Claude |

## Quy tắc đi kèm (đã có trong TikTok Manager)
- **Ba loại video:**
  - Loại 1 – Lá số: không giỏ hàng, **không quảng cáo**.
  - Loại 2 – Sản phẩm: có giỏ hàng; chỉ quảng cáo khi tool báo được.
  - Loại 3 – Tăng follow: không giỏ hàng; quảng cáo được nếu **không có nội dung bói toán hay lá số**; CTA "bấm theo dõi Cô Kim".
- **C.10a:** không xoá, che hay làm mờ dấu nhận diện AI (logo ✦). Luôn bật nhãn "Nội dung do AI tạo".
- **C.7–C.10:** không lửa, không hào quang, không chắp tay khấn vái; sản phẩm thật chèn vào Cảnh 2.
- **B.1–B.4:** không dẫn ra ngoài TikTok, không hứa may mắn, bình an hay tài lộc, không nối lá số với vật phẩm.
- **Mã thư:** VIEC-, SANXUAT-, QA-, BAOCAO-, DONGTHUAN-, DULIEU-, TUANTHU-. Hậu tố: __YEUCAU, __TRALOI, __XONG, __XACNHAN, __GUI_CLAUDE.

## Thư mục Drive
| Thư mục | Dùng cho |
|---|---|
| 01_KICH_BAN_VA_ANH_AI | ảnh cảnh do Gemini tạo |
| 02_VIDEO_THO_CHO_KIEM_DUYET | clip thô anh Nhơn tạo (P8a) |
| 03_VIDEO_CAN_CHINH_SUA | clip lỗi cần làm lại |
| 04_VIDEO_DA_DUYET_SAN_SANG_DANG | video thành phẩm (P8b) |
| 05_HOP_THU_CLAUDE_GEMINI | GUI_GEMINI · GUI_CLAUDE · HOP_THU_TOOL__YEUCAU |
| 06_SO_LIEU_TU_DONG | báo cáo tool ghi sau mỗi lần quét |
| 07_SAO_LUU_HE_THONG | bản sao lưu mã nguồn, cuộc trò chuyện, tài liệu |
