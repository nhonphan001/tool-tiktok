# Yêu cầu cho Claude in Chrome: kiểm 2 video tháng 3 có được Quảng bá hay không

**Kênh:** @tiemtragiaima · anh Nhơn đã đăng nhập TikTok, TikTok Studio, trang Quảng bá và TikTok Manager.
**Mục đích:** Gemini cho rằng 2 video dưới đây "có dấu hiệu trả phí dù không còn lịch sử lệnh". Claude chưa đồng ý, vì chưa có bằng chứng.
- Nếu 2 video này **tự nhiên**: đây là bằng chứng video lá số theo năm sinh cụ thể từng vượt xa mức khoảng 300 view tự nhiên của kênh.
- Nếu **có quảng bá**: phải loại 2 video này khỏi mức nền tự nhiên.

| # | Video ID | Đăng | Tiêu đề | View (API) | Thích | Follower mới (Studio) |
|---|---|---|---|---|---|---|
| A | **7618812733210856724** | 19/03/2026 11:04 | Nữ Giáp Tý 1984 (Hải Trung Kim) chuẩn bị gì cho năm 2026 Bính Ngọ… | 4.344 | 822 (18,9%) | 81 |
| B | **7618442082620820756** | 18/03/2026 11:06 | Thanh Kiếm Mùa Đông & Chén Trà Sưởi Ấm… cô gái Nhâm Thân 1993 | 3.431 | 492 (14,3%) | 56 |

Đối chứng: video **7621167920202173717** (25/03/2026 19:24, "Kỷ Thổ mùa đông", 3.616 view, chỉ 1,2% thích) **đã xác nhận có quảng bá**: lệnh 25/03, mục tiêu "Mua sản phẩm", 3.200 view trả phí.

## Quy tắc an toàn (bắt buộc)

- **Chỉ đọc.** Không bấm Quảng bá, Quảng bá lại, Tạo, Gia hạn, Nạp tiền, Khiếu nại, Xoá.
- Không chép số thẻ, số dư, mã hoá đơn đầy đủ (chỉ ghi ngày và số tiền), email, số điện thoại.
- Trang hỏi đăng nhập hoặc xác minh: dừng lại và báo.
- Ghi **[Dữ kiện]** hoặc **[Giả thuyết]** cho mỗi nhận định. Số đọc từ biểu đồ ghi "~". Không đoán.

## Việc cần làm

0. Mở `https://tiktok.nangtamchatluongsong.vn/danh-gia/gio`, ghi dòng `ISO:` làm `started_at`.
1. **Lịch sử lệnh Quảng bá** (`https://www.tiktok.com/promote/web/dashboard` → Lịch sử đặt lệnh):
   - Chọn bộ lọc **Tất cả trạng thái**, khoảng thời gian **dài nhất có thể**, hoặc từ 01/03/2026 nếu chọn được.
   - Cuộn hết danh sách. Liệt kê **mọi lệnh từ 01/03 đến 10/04/2026**: ngày đặt, trạng thái, mục tiêu, video (thời lượng + caption đầu), đã chi, view.
   - Có lệnh nào chứa video A hoặc B không?
2. **Lịch sử thanh toán / giao dịch** (nếu trang Quảng bá có mục Thanh toán, Giao dịch hoặc Hoá đơn):
   - Có khoản chi nào trong **17/03–22/03/2026** không? Ghi ngày và số tiền.
3. **Trong TikTok Studio, với từng video A, B:**
   - Danh sách Nội dung: video có nhãn "Đã quảng bá" hoặc biểu tượng quảng cáo không?
   - Trang phân tích video: có mục, tab hay ghi chú nào về **quảng cáo hoặc lượt xem trả phí** không?
   - **View theo ngày 7 ngày đầu** (rê chuột biểu đồ):
     - Video có quảng bá thường **phẳng đều theo ngày ngân sách**, rồi rơi gần 0 khi hết lệnh. Đối chứng: Gói 17 khoảng 1.900/ngày đều 5 ngày.
     - Video tự nhiên thường **tăng vọt 1–2 ngày đầu rồi giảm dần**.
   - Ghi bảng view từng ngày.
   - **Nhân khẩu**: video có quảng bá của kênh từng lệch hẳn sang nam, 55+. Ghi tuổi và giới tính.
   - **Nguồn lưu lượng**: Đề xuất, Đã follow, Hồ sơ, Tìm kiếm (%).
4. Làm bước 3 **với video đối chứng 7621167920202173717** để so cách đường view của video có quảng bá trông như thế nào.
5. **Kết luận** cho từng video A, B, mỗi video một trong ba mức:
   - **TỰ NHIÊN**: không có lệnh, không có khoản chi, đường view tự nhiên;
   - **CÓ QUẢNG BÁ**: tìm thấy lệnh hoặc khoản chi;
   - **CHƯA KẾT LUẬN ĐƯỢC**: kèm lý do.

## Cách trả kết quả

1. Mở lại `/danh-gia/gio`, ghi `finished_at`.
2. Viết báo cáo:
   - tiêu đề `# Kiểm quảng bá tháng 3 dd/mm/yyyy`;
   - dòng "Chạy skill" và dòng "Token (ước tính)" như khuôn của skill tiktok-studio-quet;
   - các bảng của bước 1–4, kết luận bước 5;
   - cuối file là khối JSON:

```json
{"schema": "tiktok-studio-quet/v1", "mode": "video",
 "run": {"started_at": "", "finished_at": "", "tokens_est": {"input": 0, "output": 0, "total": 0}, "exact_tokens": null},
 "videos": [
  {"video_id": "7618812733210856724", "promoted": null, "promo": {"spent": 0, "views": 0, "followers": 0},
   "views_by_day": {}, "audience_age_pct": {}, "audience_gender_pct": {}, "traffic_source_pct": {}, "verdict": "tu_nhien|co_quang_ba|chua_ket_luan", "evidence": ""},
  {"video_id": "7618442082620820756", "promoted": null, "promo": {"spent": 0, "views": 0, "followers": 0},
   "views_by_day": {}, "audience_age_pct": {}, "audience_gender_pct": {}, "traffic_source_pct": {}, "verdict": "", "evidence": ""}
 ],
 "march_orders": [{"date": "", "status": "", "objective": "", "video": "", "spent": 0, "views": 0}],
 "march_payments": [{"date": "", "amount": 0}]}
```

   **Chỉ đặt `promoted` là `true` hoặc `false` khi đã kết luận được**, không thì để `null`.
3. Dán báo cáo vào `https://tiktok.nangtamchatluongsong.vn/danh-gia` → **Lưu báo cáo**. Kết luận sẽ tự vào báo cáo đồng thuận gửi Gemini.
