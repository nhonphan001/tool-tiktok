# TikTok Manager — quét dữ liệu, thống kê, lên chiến lược, đồng bộ NotebookLM

Công cụ tự host để quản lý kênh TikTok của bạn:

- **Liên kết kênh** qua TikTok Login Kit (OAuth chính thức) — không cần mật khẩu TikTok, không scrape.
- **Quét định kỳ** (mặc định 6 giờ/lần, chỉnh trên web): follower, lượt thích, số video, và view/like/comment/share của từng video. Mỗi lần quét lưu một "ảnh chụp" nên có lịch sử tăng trưởng.
- **Thống kê**: tăng trưởng 24h/7/30 ngày, tỉ lệ tương tác, view/ngày, video đang tăng mạnh, hiệu quả theo ngày/giờ đăng (bản đồ nhiệt), độ dài video, hashtag, tần suất đăng.
- **Lên chiến lược** bằng Gemini: chẩn đoán, lịch đăng 7 ngày, 10 ý tưởng + hook, KPI 30 ngày, A/B test; có hỏi đáp tự do về số liệu. Không có API key thì dùng chiến lược dựa trên quy tắc.
- **Lưu lên NotebookLM**: báo cáo + lịch sử chiến lược được đẩy thành nguồn cho notebook (3 cách, xem bên dưới).
- **Web app** quản lý (có mật khẩu): Tổng quan · Video · Phân tích · Chiến lược · Báo cáo · Cài đặt.

## Tính năng cho kênh Tiệm Trà Giải Mã

- **Định vị kênh & quy tắc nội dung** (`app/defaults/`): được gửi kèm MỌI yêu cầu Gemini. Ô trong Cài đặt để trống = dùng mặc định.
- **Tuân thủ TikTok Shop** (trang *Tuân thủ*): tự dò caption mọi video sau mỗi lần quét (web, Bio, tiểu sử, tên miền, Zalo, Shopee, Lazada, link, cả chữ không dấu và viết né như `l.i.n.k`) + lời hứa quá đà. Có ô dán thử caption / bình luận ghim / lời thoại trước khi đăng. Cảnh báo hiện ngay trên Tổng quan.
- **KPI**: tiến độ mốc 5.000 / 10.000 follower, số cần tăng mỗi ngày, tốc độ 7 ngày, ngày dự kiến đạt; tim/view so với mốc 4%; hiệu quả các khung giờ đăng 7:00 / 12:00 / 19:30.
- **Nhãn video**: Gói, mã sản phẩm, hành Dụng Thần, nhóm nội dung (1–6), có giỏ hàng. Gemini phân loại tự động (chạy nền, không ghi đè nhãn tay). Trang Phân tích thống kê theo nhãn.
- **Bảng sản phẩm** (trang *Sản phẩm*): đọc bảng quản trị (Sheets API hoặc CSV xuất bản) — chỉ đọc, không bao giờ ghi.
- **Báo cáo** ghi rõ số liệu chính xác từ TikTok API, kèm KPI, tuân thủ, nhãn — dùng cho báo cáo ca 06h của Gemini.
- **API chỉ-đọc** `GET /api/public/summary` và `/api/public/report.md` (header `x-api-token` hoặc `?token=`, cần `API_TOKEN`) cho bảng điều hành khác hoặc Gemini đọc.

- **Lá số** (trang *Lá số*): lõi tính Bát Tự giống web tra lá số (đã so khớp 0 sai lệch trên 5.240 ca). Dán bình luận xin xem lá số → tool tự tách ngày giờ sinh (dương/âm lịch, giờ can chi, giới tính) và lập lá số; bình luận không được lưu. API `GET /api/public/laso?dd=&mm=&yy=&t=&lich=&gioi=`.
- **Gói sản xuất** (trang *Gói SX*): lời thoại 4 cảnh, chữ trên hình, caption, bình luận ghim, lá số, SKU → kiểm tra B.1/B.2/B.3/B.4 + 2 loại video + âm tiết + CTA, sinh khối `nhan_video` và phiếu `.md` cho Gemini; tự gắn gói vào video sau khi đăng (khớp caption) và ghi nhãn.
- **Lịch quét giờ cố định** (mặc định 05:00, 11:00, 17:00, 23:00 giờ Việt Nam).
- **Tệp dựng sẵn cho Bảng điều hành**: `GET /api/public/dashboard/<tiktok_kenh|tiktok_kpi|tiktok_khung_gio|tiktok_video|tiktok_tuan_thu>.json`.

## Ghi báo cáo vào Google Drive (thư mục 06_SO_LIEU_TU_DONG)

1. Google Cloud → project của service account (vd. `nangtam-gemini`) → **APIs & Services → Library**: bật **Google Drive API** (và **Google Sheets API** nếu đọc bảng sản phẩm bằng ID).
2. **IAM & Admin → Service Accounts** → chọn service account → **Keys → Add key → Create new key → JSON** → tải file về, đổi tên `service-account.json`, chép lên VPS vào `~/tool-tiktok/secrets/`.
3. Trên Google Drive: mở 2 Doc `BAO_CAO_TIKTOK_MANAGER` và `CHIEN_LUOC_TIKTOK_MANAGER` → **Chia sẻ** → thêm email service account với quyền **Người chỉnh sửa**.
4. Web app → **Cài đặt**: chế độ đồng bộ `drive,local`, điền 2 Google Doc ID → **Lưu** → bấm **Kiểm tra kết nối Google Drive & ghi thử**.
Sau đó tool tự ghi đè 2 Doc sau mỗi lần quét.

## Chạy nhanh

```bash
cp .env.example .env        # rồi sửa các giá trị
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Hoặc bằng Docker:

```bash
docker compose up -d --build
```

Mở `http://localhost:8000`, đăng nhập bằng `APP_PASSWORD`. Chưa có TikTok API? Bấm **"Xem thử với dữ liệu demo"** để xem giao diện với dữ liệu giả lập.

## 1. Kết nối TikTok

1. Vào <https://developers.tiktok.com> → **Manage apps** → tạo app.
2. Thêm sản phẩm **Login Kit** và **Display API** (hoặc các scope tương ứng):
   `user.info.basic`, `user.info.profile`, `user.info.stats`, `video.list`.
3. Ở Login Kit, khai báo **Redirect URI**: `BASE_URL/auth/tiktok/callback`
   (ví dụ `https://tiktok.tenmien.com/auth/tiktok/callback`). TikTok yêu cầu HTTPS cho môi trường thật — dùng domain + reverse proxy (Caddy/Nginx) hoặc Cloudflare Tunnel.
4. Điền `TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `BASE_URL` vào `.env`.
5. Khi app còn ở chế độ **Sandbox**, thêm tài khoản TikTok của bạn vào *Target users*; muốn dùng lâu dài thì gửi app review.
6. Web app → **Cài đặt** → **Kết nối kênh TikTok**. Token được tự làm mới (refresh token ~365 ngày).

> Display API chỉ trả về số liệu công khai (follower, like, view, comment, share). Các chỉ số sâu như thời gian xem, nguồn traffic, nhân khẩu học khán giả không có trong API cho tài khoản cá nhân.

## 2. Gemini (lên chiến lược)

Lấy API key tại <https://aistudio.google.com/apikey> → `GEMINI_API_KEY`. Model mặc định `gemini-3.8-flash` (đổi được trên web). Bật **"Tự tạo chiến lược sau mỗi lần quét"** nếu muốn chiến lược luôn mới.

## 3. Lưu dữ liệu lên NotebookLM

NotebookLM bản thường **không có API công khai**, nên tool hỗ trợ 3 cách (đặt `NOTEBOOKLM_MODE`, kết hợp được, ví dụ `drive,local`):

| Chế độ | Cách hoạt động | Phù hợp |
|---|---|---|
| `drive` (khuyên dùng) | Tool ghi đè nội dung 2 Google Docs (Báo cáo, Chiến lược) sau mỗi lần quét. Bạn thêm 2 Docs này làm nguồn trong NotebookLM **một lần**; khi có dữ liệu mới, mở nguồn và bấm *"Nhấp để đồng bộ với Google Drive"*. | NotebookLM cá nhân |
| `enterprise` | Đẩy trực tiếp nguồn văn bản vào notebook qua **NotebookLM Enterprise API** (Google Cloud). Mỗi lần đồng bộ thêm 1 nguồn mới có ghi thời gian. | Tổ chức có Google Cloud / Agentspace |
| `local` | Ghi file `exports/tiktok_report_latest.md` và `tiktok_strategy_latest.md` (+ bản có ngày). Tải lên NotebookLM thủ công, hoặc để thư mục này trong Google Drive Desktop. | Đơn giản, không cần Google Cloud |

### Cài chế độ `drive`
1. Google Cloud Console → tạo project → bật **Google Drive API** → tạo **Service Account** → tạo key JSON → lưu thành `secrets/service-account.json`.
2. Tạo 2 Google Docs trống (vd: *TikTok – Báo cáo*, *TikTok – Chiến lược*), **Chia sẻ quyền Editor** cho email service account (hiện trong trang Cài đặt).
3. Copy ID từ URL `docs.google.com/document/d/<ID>/edit` → dán vào Cài đặt (hoặc `GOOGLE_DOC_ID_REPORT`, `GOOGLE_DOC_ID_STRATEGY`).
4. Trong NotebookLM: **Thêm nguồn → Google Drive** → chọn 2 Docs.

### Cài chế độ `enterprise`
Cần NotebookLM Enterprise. Cấp cho service account role *Discovery Engine User* (hoặc tương đương), điền `NOTEBOOKLM_PROJECT_NUMBER`, `NOTEBOOKLM_LOCATION` (`global`/`us`/`eu`), `NOTEBOOKLM_NOTEBOOK_ID` (lấy từ URL notebook).

## Cấu trúc

```
app/
  main.py        Web app (FastAPI) + đăng nhập + OAuth TikTok
  tiktok.py      Client TikTok API v2 (token, user info, video list)
  scanner.py     Quét & lưu ảnh chụp số liệu
  scheduler.py   Quét định kỳ (APScheduler)
  analytics.py   Thống kê & nhận định tự động
  strategy.py    Chiến lược bằng Gemini (+ dự phòng theo quy tắc)
  report.py      Báo cáo Markdown (ngữ cảnh cho Gemini, nguồn cho NotebookLM)
  notebooklm.py  Đồng bộ local / Google Drive / NotebookLM Enterprise
  demo.py        Dữ liệu giả lập để thử giao diện
data/tiktok.db   SQLite (tự tạo)
```

JSON API (cần đăng nhập): `GET /api/overview`, `GET /api/videos`. Kiểm tra sống: `GET /healthz`.

## Test

```bash
pip install pytest && python -m pytest -q
```

## Bảo mật
- Đổi `APP_PASSWORD` và `SECRET_KEY` trước khi đưa lên internet; chạy sau HTTPS.
- `.env`, `data/`, `secrets/`, `exports/` đã nằm trong `.gitignore` — đừng commit token.
