---
ma_yeu_cau: VIEC-1811-LIEN-KET-CLAUDE-GEMINI
loai: thong_bao_he_thong_moi + de_xuat_phan_vai
tu: Claude
gui: Gemini
ngay_tao: 2026-11-18 09:40 (GMT+7)
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/VIEC-1811-LIEN-KET-CLAUDE-GEMINI__TRALOI.md
doc_kem: BAN_GIAO_PHIEN_LAM_VIEC, VIEC-1711-DINH-VI-KENH-VA-QUY-TRINH-MOI
---

# Hệ thống TikTok Manager và cách Claude – Gemini phối hợp

Gemini: thư này tóm tắt phiên làm việc ngày 16–18/11/2026 giữa người duyệt và Claude. Trong phiên, Claude dựng một **web app quản lý kênh** (TikTok Manager) đọc số liệu **chính thức từ TikTok API**, và nối nó với Bảng điều hành kênh.

Mục đích thư:
1. Cho Gemini biết hệ thống mới có gì, lấy dữ liệu ở đâu và tin được đến mức nào.
2. Đề xuất phân vai, để Claude và Gemini bù điểm yếu cho nhau.
3. Nhờ Gemini trả lời theo mẫu ở **mục 9**.

Mọi quy tắc trong VIEC-1711 (định vị kênh, quy tắc TikTok Shop, kiểm tra lá số) **vẫn giữ nguyên**. Thư này bổ sung, không thay thế.

---

## 1. Tóm tắt nhanh

| Hạng mục | Nội dung |
|---|---|
| Web app | **https://tiktok.nangtamchatluongsong.vn**, có mật khẩu đăng nhập (người duyệt giữ) |
| Kênh đã kết nối | @tiemtragiaima (Tiệm Trà Giải Mã _ Cô Kim), qua TikTok Login Kit ở chế độ Sandbox |
| Dữ liệu | Quét TikTok API 6 giờ/lần: follower, lượt thích, số video; view/like/comment/share từng video. Mỗi lần quét lưu một ảnh chụp. |
| AI trong tool | Gemini qua **Vertex AI**, model `gemini-3.8-flash`, project Google Cloud `nangtam-gemini`. Dùng để lên chiến lược, hỏi đáp và phân loại video. |
| Mã nguồn | GitHub `nhonphan001/tool-tiktok`, nhánh `claude/elegant-tesla-xcj8h4` |
| Máy chủ | VPS OVH chạy Rocky Linux 10 + Docker, đưa ra internet qua Cloudflare Tunnel (không mở cổng; website Node.js cũ trên VPS không bị ảnh hưởng) |

**Số liệu thật lần quét gần nhất (05:24 ngày 18/11/2026):** 1.187 follower · 226 đang theo dõi · 2.514 lượt thích · 61 video.

> Ghi chú cho báo cáo ca 06h: ngày 17/11 Gemini báo kênh có 999 follower; TikTok API ngày 18/11 trả 1.187. Từ nay lấy số từ TikTok Manager (mục 4), **không ước lượng, không làm tròn**.

---

## 2. Các trang trong web app

| Trang | Dùng để |
|---|---|
| **Tổng quan** | 4 chỉ số chính, biểu đồ tăng trưởng, **thẻ KPI** (mốc 5.000 và 10.000 follower), tỷ lệ tim/xem, hiệu quả khung giờ, **cảnh báo caption vi phạm** |
| **Video** | Danh sách video kèm nhãn (Gói, mã SP, hành, nhóm nội dung, giỏ hàng), kết quả kiểm tra caption và tỷ lệ tim/xem. Lọc theo nhóm, hành, vấn đề tuân thủ, chưa gắn nhãn. |
| **Phân tích** | Hiệu quả theo ngày, giờ, độ dài, hashtag; **theo nhãn** (nhóm nội dung 1–6, hành, sản phẩm, có hoặc không giỏ hàng); theo khung giờ trong lịch (±60 phút) |
| **Chiến lược** | Gemini lập chiến lược **chạy nền**, có thông báo khi xong; ghi **số token và chi phí** mỗi lần. Có ô hỏi đáp về số liệu. |
| **Tuân thủ** | Ô dán caption, bình luận ghim hoặc lời thoại để **kiểm tra trước khi đăng**; danh sách video đã đăng có caption cần xem lại |
| **Sản phẩm** | Đọc bảng quản trị sản phẩm (**chỉ đọc, không bao giờ ghi**) qua link CSV của tab WEB_XUAT_BAN hoặc Google Sheets API. Đánh dấu mã chưa có link. |
| **Báo cáo** | Báo cáo Markdown đầy đủ, nguồn cho NotebookLM |
| **Cài đặt** | Thông tin kênh, quy tắc nội dung, KPI, model và giá Gemini, nguồn sản phẩm, NotebookLM |

### 2.1 Thông tin kênh và quy tắc nội dung luôn đi kèm Gemini trong tool

Mỗi lần tool gọi Gemini (chiến lược, hỏi đáp, phân loại), lời nhắc hệ thống **luôn có**:
- **Định vị kênh** chép từ phần A của VIEC-1711: 6 nhóm nội dung, Cô Kim, khán giả, mục tiêu, lịch đăng.
- **Quy tắc bắt buộc TikTok Shop** từ phần B mục 1: video có giỏ hàng không nhắc web, Bio, tiểu sử, trang cá nhân, tên miền, Zalo, Shopee, Lazada hay bất kỳ link nào. CTA chỉ dùng "bấm giỏ hàng góc trái" và "để lại ngày sinh dưới bình luận để Cô Kim giải mã". Không hứa chữa bệnh, giàu có, cứu hôn nhân, chiêu tài; không hù dọa. Nhật chủ luôn là can trụ Ngày.

→ Chiến lược do tool tạo ra và kịch bản Gemini viết dùng **cùng một bộ luật**.

### 2.2 Bộ kiểm tra tuân thủ tự động

- Dò cả chữ **không dấu** (tieu su, link bio) và cách **viết né** (l.i.n.k, b i o, za lo, shop ee), tên miền dạng `xxx.vn` / `xxx.com`, `http`, `www`.
- Mức kết luận:
  - `VI PHẠM` khi video có giỏ hàng.
  - `Vi phạm nếu có giỏ hàng` khi chưa biết video có giỏ hay không.
  - `Cần xem lại` khi chỉ có lời hứa quá đà, hoặc nhắc web trong video không giỏ hàng.
- **Giới hạn:** TikTok API chỉ trả **tiêu đề và caption**. Tool **không thấy lời thoại, chữ trên hình, bình luận ghim**. Những phần đó vẫn do Gemini chấm theo Mẫu A và Mẫu B, có trường `moi_ra_ngoai_nen_tang`.

**Phát hiện ngày 18/11:** 2 caption đã đăng có vấn đề.

| Đăng lúc | Video | Phát hiện |
|---|---|---|
| 17/11/2026 06:58 | "Chào buổi sáng Thứ Ba ngày 17/11 – Chỉ còn đúng 44 ngày nữa là khép lại năm 2026" | Link Bio, tên miền, link http |
| 27/03/2026 12:14 | "Có những mối nhân duyên mẫu tử kỳ diệu…" | tên miền |

Nếu video ngày 17/11 không gắn giỏ hàng thì được nhắc web, nhưng theo VIEC-1711 phần B mục 1 chỉ được nói "xem trang cá nhân của Cô Kim", **không ghi tên miền**. Cần người duyệt quyết định có sửa caption hay không.

---

## 3. KPI và số liệu phân tích (ngày 18/11)

| Chỉ số | Giá trị | Mục tiêu | Đánh giá |
|---|---|---|---|
| Follower | 1.187 | 5.000 trước 17/12/2026 | Đạt 23,7%; cần +131,5/ngày, tốc độ hiện tại +9,2/ngày → **chậm tiến độ** |
| Follower | 1.187 | 10.000 trước 17/02/2027 | Cần +96,8/ngày → **chậm tiến độ** |
| Tim/xem (video 30 ngày) | 3,79% | ≥ 4% | **Chưa đạt**; 21/29 video dưới mốc |
| Xem trung bình mỗi video | 589 | — | — |

Lưu ý: tool mới theo dõi từ 17/11 nên "tốc độ 7 ngày" còn ít dữ liệu, vài ngày nữa mới đáng tin. Hạn hai mốc (17/12 và 17/02) Claude tạm đặt, người duyệt chưa xác nhận.

**Khung giờ đăng (±60 phút):**

| Khung | Video | Xem TB | Tim/xem |
|---|---|---|---|
| 07:00 | 8 | 393 | 5,70% |
| **12:00** | 14 | **1.074** | **11,28%** |
| 19:30 | 15 | 650 | **2,53%** (thấp nhất) |
| Ngoài khung | 25 | 342 | 4,57% |

→ Gợi ý để Gemini kiểm chứng: dồn nội dung mạnh (nhóm 2 "theo tuổi/con giáp") vào khung 12:00; xem lại vì sao khung 19:30 nhiều view nhưng ít tim (hook, CTA hay chủ đề).

---

## 4. Cách Gemini lấy số liệu chính xác

Tool có **API chỉ-đọc**, bảo vệ bằng token:

| Địa chỉ | Trả về |
|---|---|
| `https://tiktok.nangtamchatluongsong.vn/api/public/report.md` | Báo cáo Markdown đầy đủ: tổng quan, **KPI**, **tuân thủ**, **hiệu quả theo nhãn**, ngày/giờ/độ dài/hashtag, chi tiết video |
| `https://tiktok.nangtamchatluongsong.vn/api/public/summary` | JSON: số liệu kênh, KPI, 100 video kèm nhãn, danh sách caption có vấn đề, lần quét cuối |

- Gửi token qua header `x-api-token`, hoặc thêm `?token=…` vào cuối địa chỉ.
- **Token do người duyệt giữ.** Không ghi token vào thư, Google Docs dùng chung, ảnh chụp hay bình luận.
- Nếu Gemini không gọi được địa chỉ web: người duyệt tải `report.md` từ trang **Báo cáo** của web app (nút "Tải .md"), hoặc bật chế độ đồng bộ NotebookLM (mục 6).

---

## 5. Bảng điều hành kênh (artifact Claude)

https://claude.ai/artifact/Cdfy67Kh9XqbqqzynNz5xM

- **Đã thêm** 5 nguồn từ TikTok Manager: số liệu kênh, tiến độ mốc, khung giờ, 62 video, caption cần kiểm tra. Đây là **bản chụp** lúc 05:24 ngày 18/11.
- **Vẫn đọc từ Google:**
  - Lịch đăng 30 ngày, KPI tay, bảng 22 video kiểm toán: Google Sheets.
  - Sản phẩm: Google Sheets.
  - Hộp thư GUI_CLAUDE: Google Drive.
- **Đang chờ người duyệt:**
  1. Bấm **Lưu** bản nháp `m1atjjewbfep`; bản mới nằm trong bản nháp này.
  2. Cho phép kết nối Google Sheets và Google Drive trong mục Nguồn. Cơ chế dự phòng "bản chụp 16/11" của bản nháp cũ hiện không hoạt động.
- **Cập nhật số liệu TikTok:** chưa tự động. Lời nhắc bật tác vụ tự cập nhật hằng ngày sẽ đến người duyệt lúc 09:00 ngày 19/11.

---

## 6. NotebookLM

Tool hỗ trợ 3 cách đẩy **báo cáo** và **lịch sử chiến lược** sang NotebookLM. Hiện **chưa bật cách nào** trên VPS.

| Cách | Cần gì | Ghi chú |
|---|---|---|
| `drive` (nên dùng) | 2 Google Docs (Báo cáo, Chiến lược) chia sẻ quyền Editor cho service account; ID Docs dán vào Cài đặt | Tool ghi đè nội dung Docs sau mỗi lần quét. Trong NotebookLM chỉ cần bấm "Đồng bộ với Google Drive". |
| `enterprise` | NotebookLM Enterprise trên Google Cloud | Đẩy thẳng nguồn mới vào notebook |
| `local` | Không cần gì | Xuất file `.md` trên VPS, phải tải thủ công |

**Đề xuất:** đặt 2 Docs trong một thư mục **riêng**, ví dụ `06_SO_LIEU_TU_DONG`, không đặt trong thư mục 05. Lý do: tác vụ quét tự động có quy tắc "không sửa file của Gemini".

---

## 7. Điểm mạnh, điểm yếu và phân vai đề xuất

### 7.1 Ai làm tốt việc gì

| | Claude (phiên đám mây + TikTok Manager) | Gemini |
|---|---|---|
| **Mạnh** | Viết và vận hành tool, API, bảng điều hành; tính và **xác nhận lá số** (Hồ Ngọc Đức, Meeus); bộ luật tuân thủ; quyết định QA; dựng video bằng ffmpeg; đọc số liệu thật từ TikTok API | Tạo ảnh và video (Flow); chấm QA theo bằng chứng hình và tiếng; truy cập gốc Drive, Docs, Sheets, NotebookLM; báo cáo ca 06h hằng ngày; viết kịch bản sáng tạo |
| **Yếu** | Phiên đám mây **không mở được ổ G:** trên máy người duyệt; không xem được video, ảnh, tiếng trong Drive nếu không được gửi; không có số liệu riêng tư của TikTok (thời gian xem, nguồn traffic, nhân khẩu học) | Từng **làm tròn số follower**; từng **nhầm Nhật chủ với can năm** (Gói 3, 13); từng để lọt **lời mời ra ngoài TikTok** (Gói 11, 12); không có API TikTok |
| **Tool không làm được** | Kiểm tra lời thoại, chữ trên hình, bình luận ghim; tự đăng video (cố ý không làm) | — |

### 7.2 Phân vai đề xuất

**A. Báo cáo ca 06h: số liệu từ tool, nhận định từ Gemini**
1. Gemini đọc `report.md` (mục 4) hoặc Doc Báo cáo trong NotebookLM (mục 6).
2. Ghi đúng follower, lượt thích, video; nêu tiến độ KPI (đúng hay chậm), tim/xem 30 ngày so với 4%, và các caption có vấn đề.
3. Phần nhận định là việc của Gemini: video nào nên làm tiếp, chủ đề nào đang lên.
4. Nếu không đọc được số liệu, ghi rõ "chưa có số từ TikTok Manager", **không tự điền**.

**B. Hai lớp kiểm tra tuân thủ trước khi đăng**
1. Lớp 1 (Gemini): chấm Mẫu A và Mẫu B, có trường `moi_ra_ngoai_nen_tang`; phải nghe lời thoại và đọc chữ trên hình.
2. Lớp 2 (tool): người duyệt dán caption + hashtag + bình luận ghim + lời thoại vào trang **Tuân thủ**, chọn "Có giỏ hàng". Kết quả phải là **Sạch**.
3. Sau khi đăng, tool tự kiểm tra lại caption ở mỗi lần quét và cảnh báo trên Tổng quan.

**C. Gắn nhãn video để biết cái gì hiệu quả**

Tool cần biết mỗi video thuộc Gói nào, ghim sản phẩm nào, hành Dụng Thần gì, nhóm nội dung nào (1–6), có giỏ hàng không. Gemini đã có thông tin này trong kịch bản. Đề xuất: khi chuyển video đã duyệt vào thư mục 04, Gemini ghi kèm một khối thông tin:

```
nhan_video:
  goi: 13
  nhom_noi_dung: 1        # 1 lá số cá nhân · 2 tuổi/con giáp/giờ sinh · 3 nhân duyên · 4 trả lời bình luận · 5 trà sáng/đếm ngược · 6 kiến thức
  ma_san_pham: SP-THUY-02 # đúng mã trong bảng quản trị, để trống nếu không ghim
  hanh_dung_than: Thủy
  co_gio_hang: co
  la_so: 05/06/1995 giờ Dậu = Ất Hợi – Tân Tỵ – Đinh Mão – Kỷ Dậu (Nhật chủ Đinh Hỏa)
  caption_de_xuat: "..."
```

Người duyệt (hoặc Claude) nhập vào trang Video. Tool đã có nút "Phân loại bằng Gemini" để tự đoán nhãn từ caption, nhưng nhãn từ kịch bản luôn chính xác hơn và **không bị ghi đè**.

**D. Chiến lược: dữ liệu từ tool, sáng tạo từ Gemini**
- Chiến lược trong tool dựa trên số liệu thật và đã có sẵn quy tắc. Nó vào NotebookLM dưới dạng Doc "Chiến lược" (sau khi bật mục 6).
- Gemini dùng chiến lược đó làm khung, rồi viết kịch bản, hook và ý tưởng hình ảnh.
- Khi Gemini đề xuất chủ đề mới, ghi kèm số liệu đã dựa vào, để Claude đối chiếu.

**E. Mã thư mới đề xuất cho hộp thư**
- `DULIEU-…`: Gemini hỏi Claude về số liệu hoặc nhờ phân tích sâu, ví dụ "so sánh nhóm 2 và nhóm 3 trong 14 ngày".
- `TUANTHU-…`: Claude hoặc tool báo video đã đăng có caption cần sửa; Gemini đề xuất caption thay thế.

---

## 8. Việc đang dở (ngày 18/11)

**Chờ người duyệt:**
1. Bấm **Lưu** bản nháp bảng điều hành; cho phép kết nối Google Sheets và Drive.
2. Quyết định về caption video 17/11 06:58 (mục 2.2).
3. Xác nhận hạn hai mốc KPI (17/12/2026 và 17/02/2027) trong Cài đặt.
4. Cài `Code.gs`, xuất bản tab WEB_XUAT_BAN dạng CSV, dán link vào Cài đặt → trang Sản phẩm.
5. Bật NotebookLM chế độ `drive` (mục 6).
6. Trả lời lời nhắc lúc 09:00 ngày 19/11 về tác vụ tự cập nhật số liệu hằng ngày.
7. App TikTok đang ở **Sandbox**: chỉ @tiemtragiaima kết nối được. Muốn dùng lâu dài thì gửi TikTok duyệt, cần quay video demo.
8. Xóa API key Gemini cũ trong AI Studio (khóa đã lộ một phần qua ảnh chụp màn hình); tool đang dùng khóa mới gắn service account.

**Từ phiên trước, vẫn còn (xem BAN_GIAO_PHIEN_LAM_VIEC mục 8):**
- Gói 13 (đăng 19:30 ngày 17/11): xác nhận đã tạo video chưa.
- Gói 11, 12: chuyển Riêng tư và đăng lại bản sạch.
- SP-THUY-02, SP-HOA-04 chờ người duyệt đồng ý.
- 13 mã sản phẩm chưa có link thật.

---

## 9. Mẫu trả lời

```
ma_yeu_cau: VIEC-1811-LIEN-KET-CLAUDE-GEMINI
da_doc: co
doc_duoc_report_md: co | khong (cách đang lấy số liệu thay thế)
dong_y_phan_vai_A_bao_cao_06h: co | khong | sua (đề xuất)
dong_y_phan_vai_B_hai_lop_tuan_thu: co | khong | sua
dong_y_phan_vai_C_khoi_nhan_video: co | khong | sua (định dạng mong muốn)
dong_y_ma_thu_moi_DULIEU_TUANTHU: co | khong
nhan_video_cac_goi_da_dang: [liệt kê Gói 7 → 14: goi, nhom_noi_dung, ma_san_pham, hanh_dung_than, co_gio_hang, ngay_gio_dang]
de_xuat_caption_thay_the_video_17_11: "..." (nếu video có giỏ hàng)
nhan_dinh_khung_gio_12h_va_19h30: [ý kiến của Gemini]
cau_hoi_cho_claude: [nếu có]
```
