---
ma_bao_cao: BAOCAO-1911-CLAUDE-TONG-QUAN-NHIEM-VU
tu: Claude (Claude Code – phụ trách TikTok Manager)
gui: Gemini, TikTok Manager, Chủ kênh (anh Nhơn)
ngay: 2026-11-19 (GMT+7)
kem_theo: DONGTHUAN-1911-QUY-TRINH-V1__YEUCAU.md
---

# Báo cáo tổng quan nhiệm vụ của Claude

**Phạm vi:** những việc Claude đang giữ để TikTok Manager, Gemini và anh Nhơn làm việc chung theo một quy trình.
**Số liệu kênh lúc viết** (TikTok API, lần quét 05:00 ngày 19/11):
- 1.187 follower;
- 62 video;
- trung bình 589 view/video;
- 24h qua: +0 follower, +5 tim, +1 video.

## 1. Nhiệm vụ và mức độ hoàn thiện

| # | Nhiệm vụ của Claude | Hoàn thiện | Đã kiểm chứng | Còn mở |
|---|---|---|---|---|
| C1 | **Xây và vận hành TikTok Manager**: quét 4 lần/ngày, KPI, phân tích, chiến lược Gemini, báo cáo Drive 06 → NotebookLM | 100% | Anh Nhơn chạy thử bước 1–7 ngày 18/11: đạt | — |
| C2 | **Bảng sản phẩm**: đọc 18 SKU, rà B.4, cột O, **thêm SKU từ link** (Gemini API tự điền, chỉ thêm dòng) | 100% | SP-TET-01 được ghi vào bảng thật | Giá SP-TET-01; các SKU còn link tạm hoặc từ cấm (xem cột "Rà B.4") |
| C3 | **Cổng tuân thủ**: B.1–B.4, video Loại 1/2/3, quy tắc hình ảnh C.7–C.10, chặn quảng cáo khi có nội dung bói toán | 100% | Gói 16 và 17 thật: 0 lỗi | Chờ TikTok duyệt quảng cáo Gói 17 (chưa bật) |
| C4 | **Gói SX**: phiếu gói, lá số tự tính, `nhan_video`, tự gắn video sau khi đăng | 100% | Gói 16, 17 đạt | Tự gắn video Gói 17 sau khi đăng (bước P11) |
| C5 | **Hộp thư Claude ↔ Gemini ↔ Tool**: yêu cầu gửi từ tool, Doc hộp thư đi, dò thư trả lời/thư sửa/thư BAOCAO mỗi 10 phút | 100% | Gói 17 đi trọn vòng: yêu cầu → XONG → sửa → BAOCAO có video | Chờ Gemini xác nhận thư DANH-SACH-VIEC (mục 3) |
| C6 | **Bộ đăng TikTok**: prompt video 4 cảnh, ảnh, video thành phẩm, nút Chép/Tải | 100% | Chạy với dữ liệu Gói 17 thật | — |
| C7 | **Kiểm duyệt nội dung và ảnh** (Cô Kim v3.1 → v3.3, Gói 15/16/17) | Liên tục | 3 bộ ảnh đã duyệt; định vị kênh đã chuyển sang v3.3 | Bao bì Gói 16 chưa đồng nhất; cần quyết việc xoá logo AI |
| C8 | **Dashboard Claude 05:17 mỗi ngày** (tác vụ đã lên lịch) | 90% | Đã tạo, lần chạy thật đầu tiên là 19/11 | Claude chưa kiểm tra kết quả lần chạy 19/11 |
| C9 | **Giao diện điện thoại** (menu ☰, bảng cuộn, ô nhập 16px, CSS tự làm mới) | 100% | Anh Nhơn đã dùng trên điện thoại | — |
| C10 | **Tài liệu**: PDF quy trình 9 trang, thư VIEC/SANXUAT, hướng dẫn | 100% | — | Cập nhật PDF sau khi chốt đồng thuận |
| C11 | **Sao lưu toàn hệ thống** (mã nguồn, VPS, Drive, cuộc trò chuyện) | 90% | Đã tạo gói sao lưu ngày 19/11 | Anh Nhơn chạy `scripts/backup.sh` trên VPS và bật lịch hằng ngày |

**Kiểm thử:** 52 test tự động đều đạt; mã nguồn ở GitHub, nhánh `claude/elegant-tesla-xcj8h4`.

## 2. Cách Claude giao tiếp với từng bộ phận

| Với | Kênh | Claude làm gì |
|---|---|---|
| **TikTok Manager** | Mã nguồn + API công khai `/api/public/*` (có khoá) | Sửa và nâng cấp tool, đọc số liệu thật qua API, đọc báo cáo tự động `/api/public/system.md` |
| **Gemini** | Hộp thư Drive 05: GUI_GEMINI (Claude gửi) / GUI_CLAUDE (Gemini gửi) | Viết thư VIEC-/SANXUAT-/DONGTHUAN-, đọc XONG/BAOCAO/XACNHAN, kiểm duyệt ảnh, kịch bản, prompt |
| **Anh Nhơn** | Cuộc trò chuyện Claude Code | Nhận yêu cầu, báo kết quả, hướng dẫn cập nhật VPS |

## 3. Thư Claude đã gửi Gemini và tình trạng xác nhận

| Thư | Xác nhận của Gemini |
|---|---|
| DE-XUAT-1811-KIEN-TRUC-V25 (TRALOI) | ✅ DE-XUAT-1811-KIEN-TRUC-V25__XACNHAN |
| VIEC-1811-CAP-NHAT-NHAN-VAT-CO-KIM-V31 | ✅ …__XACNHAN |
| SANXUAT-1811-GOI-16-KHAN-LAU-BAN-THO | ✅ …__XONG (4 ảnh) |
| SANXUAT-1911-GOI-17 (yêu cầu từ tool) | ✅ …__XONG + BAOCAO-1911-HOAN-TAT-GOI-17 |
| VIEC-1811-LIEN-KET-CLAUDE-GEMINI | ✅ …__TRALOI |
| VIEC-1811-CHINH-SACH-QUANG-CAO-BOI-TOAN | ✅ …__TRALOI |
| SANXUAT-1811-GOI-15-LA-BO-DE | ✅ …__XONG |
| VIEC-1811-DANH-SACH-VIEC-GEMINI | ⏳ Claude chưa thấy XACNHAN |

## 4. Rủi ro và việc cần quyết

1. **Xoá logo ✦ của công cụ AI bằng FFmpeg (Gói 17):** cần đối chiếu điều khoản của Google. Dù chọn cách nào, luôn bật nhãn "Nội dung do AI tạo" khi đăng.
2. **Quảng cáo Gói 17:** nội dung đã sạch. Rủi ro còn lại là phong cách nhân vật (khăn voan tím), từng nằm trong lý do bị từ chối ngày 18/11. Theo dõi kết quả duyệt.
3. **Số token Gemini báo** (khoảng 40–51 nghìn token cho Gói 17) là số Gemini **tự ước**, tool không đo được. Chỉ token gọi qua Gemini API trong tool mới được đo chính xác (trang Chiến lược → Chi phí Gemini).
4. **Ô "Thông tin kênh" trong Cài đặt:** nếu từng bấm Lưu thì tool vẫn dùng mô tả v3.1 cũ. Cần xoá trống ô đó để tool dùng mô tả v3.3.

## 5. Đề nghị
Mỗi bộ phận gửi báo cáo cùng mẫu (thư **DONGTHUAN-1911-QUY-TRINH-V1** kèm theo), đối chiếu bảng quy trình P1–P13, lặp lại cho tới khi cả ba bên ghi **dong_y** và anh Nhơn **chốt**.
