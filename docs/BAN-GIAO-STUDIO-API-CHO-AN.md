# Biên bản bàn giao công đoạn lấy dữ liệu TikTok Studio sang cho An (Antigravity)

- **Ngày hiệu lực:** 26/11/2026
- **Người duyệt:** Anh Nhơn (`@tiemtragiaima`)
- **Bên bàn giao:** TikTok Manager (`tool-tiktok`, trước đây dùng quy trình dán tay với Claude in Chrome)
- **Bên tiếp nhận:** **An (Antigravity)**

---

## 1. Phân định ranh giới 2 luồng dữ liệu

| Luồng dữ liệu | Phụ trách | Tần suất / Cơ chế | Dữ liệu thu về |
|---|---|---|---|
| **TikTok Display API** (`app/tiktok.py`, `app/scanner.py`) | **TikTok Manager (VPS)** — GIỮ NGUYÊN | Tự động 4 lần/ngày (`05:00, 11:00, 17:00, 23:00` VN) qua APScheduler, **0 token AI**, chạy 24/7 | Follower tổng, lượt thích tổng, danh sách video, `view_count`, `like_count`, `comment_count`, `share_count`, `create_time`, `share_url`, `duration` (chính xác, không làm tròn) |
| **TikTok Studio + Quảng bá + Bình luận** (`tiktokstudio/*`, `promote/web/dashboard`) | **An (Antigravity)** — TIẾP QUẢN | Chế độ **chỉ đọc 100%** trên trình duyệt đã đăng nhập; giao tiếp thẳng với TikTok Manager qua cổng `/api/public/studio/*` | Đường giữ chân (2s/10s), thời gian xem TB, tỷ lệ xem hết, nguồn lưu lượng + từ khoá tìm kiếm, follower mới theo video, đơn Quảng bá (tách tự nhiên vs trả phí), toàn bộ bình luận `tiktokstudio/comment` |

> **Lý do giữ VPS chạy Display API:** Display API chạy ngầm 24/7 trên VPS không phụ thuộc máy tính của anh Nhơn bật hay tắt và không tốn token AI. An chỉ tập trung vào những dữ liệu mà Display API không có (Studio, Quảng bá, Bình luận) rồi ghép cùng số API trong **Báo cáo đồng thuận**.

---

## 2. Bộ API bàn giao trên TikTok Manager (`/api/public/studio/*`)

Tất cả endpoint đều yêu cầu xác thực bằng **`API_TOKEN`** (gửi qua header `x-api-token: <API_TOKEN>` hoặc `?token=<API_TOKEN>`). Thiếu hoặc sai token trả về HTTP `401`.

| Method | Endpoint | Mục đích |
|---|---|---|
| `GET` | `/api/public/studio/status` | Kiểm tra trạng thái bàn giao, lần quét API gần nhất, 5 báo cáo Studio gần nhất và KPI bình luận (ẩn danh) |
| `GET` | `/api/public/studio/clock` | Lấy mốc giờ máy chủ Việt Nam (ghi `run.started_at` / `run.finished_at`) |
| `GET` | `/api/public/studio/context?days=14` | Đọc ngữ cảnh gói ↔ video, kịch bản gốc, video nghi Quảng bá |
| `GET` | `/api/public/studio/full-scan?batch=10` | Lấy danh sách video chưa có số Studio (chế độ quét toàn bộ) |
| `POST` | `/api/public/studio/report` | An đẩy trực tiếp báo cáo Studio `.md` (chứa khối JSON `tiktok-studio-quet/v1`) → tự lưu `/danh-gia`, tách số liệu vào `chrome_video_metrics` và đẩy Báo cáo đồng thuận (`BAO_CAO_DONG_THUAN__GUI_GEMINI.md`) |
| `POST` | `/api/public/studio/comments` | An đẩy mảng JSON bình luận từ `tiktokstudio/comment` vào SQLite nội bộ (`studio_comments`) → trả về chỉ số KPI ẩn danh (**0% PII**) |
| `POST` | `/api/public/studio/consensus/push` | Tách lại toàn bộ số liệu Studio và ghi đè Báo cáo đồng thuận gửi Gemini |

---

## 3. Quy tắc an toàn & quyền riêng tư (bắt buộc)

1. **TikTok / TikTok Studio / Quảng bá luôn chỉ đọc 100%:** An tuyệt đối không bấm trả lời, thích, xoá, ẩn, ghim bình luận hay thao tác tạo/sửa/gia hạn lệnh Quảng bá.
2. **Không lộ dữ liệu cá nhân (PII) qua API công khai:**
   - `/api/public/studio/comments` **chỉ hỗ trợ `POST`** (ghi vào SQLite cục bộ phía sau màn hình đăng nhập `/binh-luan`), **không** mở `GET` trả danh sách nick/ngày sinh ra ngoài.
   - Mọi báo cáo lưu `/danh-gia` hoặc đẩy sang Google Drive (`BAO_CAO_DONG_THUAN__GUI_GEMINI.md`) đều ẩn danh 100%.
3. **Cách kích hoạt trên VPS:**
   - Đảm bảo trong `/root/tool-tiktok/.env` đã có biến `API_TOKEN=<chuỗi ngẫu nhiên dài>`.
   - Cập nhật VPS: `cd /root/tool-tiktok && git pull && docker compose up -d --build`.

---

## 4. Phương án vận hành 4 tầng chống trùng lặp (CHỐT 26/11/2026)

Đã được anh Nhơn chốt ngày **26/11/2026** để tối ưu hạn mức, tránh trùng lặp giữa **Display API**, **An (Studio + Bình luận)** và **Google AI Studio (Gemini API)**:

| Tầng | Phụ trách | Tần suất | Phạm vi chính xác (KHÔNG dẫm chân tầng khác) |
|---|---|---|---|
| **Tầng 1 · Số tổng 24/7** | **VPS · TikTok Display API** (`app/scanner.py`) | Tự động 4 lần/ngày (`05:00, 11:00, 17:00, 23:00`) · **0 token** | Follower tổng, view/thích/BL/chia sẻ từng video, lịch sử theo giờ, tự gắn Gói SX ↔ Video, dò `promo_suspects`. Là nguồn chuẩn cho mọi số tổng. |
| **Tầng 2 · Quét nhanh hằng ngày** | **An (Antigravity)** | 1 lần/ngày (chỉ đọc phần API không có) | ① `tiktokstudio/comment` → đẩy `/binh-luan` (`POST /api/public/studio/comments`) để xử lý ngay ca **Xin lá số chưa trả lời**; ② Chi tiết Studio (giữ chân 2s/10s, xem TB, xem hết, nguồn view, follower mới, lượt lưu) **chỉ cho video mới đăng 24–48 giờ**; ③ Xác nhận nhanh 1 lần trên `promote/web/dashboard` có lệnh mới không. |
| **Tầng 3 · Tổng hợp sâu hằng tuần** | **An (Antigravity)** | 1 lần/tuần (Thứ Hai) | Tổng hợp đủ 7 ngày: so sánh nhóm tự nhiên (Loại 1/3, khung giờ, số cảnh), nguồn lưu lượng & từ khoá tìm kiếm, nhân khẩu học tự nhiên, chênh lệch API ↔ Studio, top tuổi/Can Chi từ `/binh-luan` → đẩy `/danh-gia` & Báo cáo đồng thuận. |
| **Tầng 4 · Sáng tạo & Tư vấn đầu ra** | **Google AI Studio (Gemini API)** | Theo nhu cầu / sau Báo cáo đồng thuận tuần | Lập Chiến lược tuần trên dữ liệu sạch, soạn kịch bản Gói SX theo Bộ quy tắc Bản 2, chỉ gọi `✨ Viết bằng AI` trên `/khach-hang` khi cần cá nhân hoá sâu (bình thường dùng mẫu nhanh 0 token). |

