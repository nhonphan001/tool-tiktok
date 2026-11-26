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
