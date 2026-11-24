# Checklist số liệu cần lấy

Ghi "~" với số đọc từ biểu đồ, `null` với số không có. Kỳ mặc định: 7 ngày; chế độ hằng tuần lấy thêm 28 ngày.

## A. Tổng quan kênh (TikTok Studio → Phân tích)

### A1. Tổng quan (7 ngày; tuần: thêm 28 ngày)
- Lượt xem video, lượt xem hồ sơ, thích, bình luận, chia sẻ.
- **Follower thực tăng**, follower mới, follower mất (nếu có).
- Biểu đồ theo ngày: view và follower từng ngày (rê chuột từng điểm).

### A2. Nội dung
- Danh sách video trong kỳ: ID, ngày giờ đăng, thời lượng, view, thích, bình luận.
- Video được TikTok đánh dấu "xu hướng" / top.

### A3. Người xem
- Tổng người xem, người xem mới / quay lại.
- Tuổi, giới tính, vị trí.
- **Thời điểm người xem hoạt động** (giờ trong ngày, ngày trong tuần), nếu có.

### A4. Người theo dõi
- Tổng follower, tăng ròng theo ngày.
- Giới tính, tuổi, vị trí top 5.
- **Giờ follower hoạt động nhiều nhất** (biểu đồ theo giờ: ghi 24 giá trị nếu đọc được) và **ngày hoạt động nhiều nhất**.

### A5. Hồ sơ công khai (`https://www.tiktok.com/@tiemtragiaima`)
- Follower, tổng thích, số video, 3 video ghim (tiêu đề + view), bio (chép nguyên văn).

## B. Từng video (TikTok Studio → phân tích video)

### B1. Chỉ số
Lượt xem, **người xem duy nhất**, thích, bình luận, chia sẻ, lưu, **follower mới từ video**, tổng thời gian phát, **thời gian xem trung bình**, **tỷ lệ xem hết**.

### B2. Đường giữ chân
- **% còn xem** ở 0:01, 0:02, 0:03, 0:05, 0:08, 0:10, 0:15, 0:20, 0:30, 0:45, 0:60 (mốc nào nằm trong độ dài video).
- Ghi chú TikTok ("hầu hết người xem dừng ở…").
- **Giây có nhiều lượt thích nhất** (biểu đồ thích theo thời điểm nếu có).

### B3. Nguồn lưu lượng (%)
- Đề xuất (For You), Đã follow, Hồ sơ, Tìm kiếm, Âm thanh, Tin nhắn, Khác.
- **Từ khoá tìm kiếm** dẫn tới video (kèm %).

### B4. Thời gian
- **View theo giờ trong 72 giờ đầu** (giờ đạt đỉnh, giờ gần 0) và view theo ngày.

### B5. Người xem
- Mới / quay lại; follower / không follower; tuổi; giới tính; vị trí.

## C. Xem video thật: chấm quy tắc hiệu suất

| Mã | Câu hỏi | Ghi |
|---|---|---|
| H1 | Khung 0–1 giây: sáng hay tối? Có chuyển động (hơi trà, rót, máy đẩy)? Cô Kim nói ngay giây 0 hay có khoảng lặng (bao nhiêu giây)? | mô tả + đạt/không |
| H2 | Có chữ hook lớn giữa màn hình từ khung 0 không? Chép nguyên văn, đếm ký tự. Chữ có fade-in chậm không? | đạt/không |
| H3 | Câu kêu gọi (follow / comment năm sinh / con giáp / giỏ hàng) xuất hiện **giây thứ mấy**, bằng lời nói hay chữ? | giây + dạng |
| H4 | Caption bao nhiêu ký tự? Dòng đầu nói gì? | số + nguyên văn dòng đầu |
| H5 | Có chữ chỉ giờ ("tối nay", "19h"…) trong caption / chữ trên hình / lời thoại? | có/không |
| H6 | Các cảnh có cùng bối cảnh, cùng ánh sáng không? Mặt Cô Kim có đổi giữa các cảnh không? | đạt/không + giây lỗi |
| — | Video khớp kịch bản gói (lời thoại, chữ trên hình) không? Lỗi chính tả phụ đề? Tiếng lặng dài giữa cảnh? | liệt kê |
| — | Nhãn "Nội dung do AI tạo" có không? Nhãn "nội dung thương mại" có không? | có/không |

## D. Bình luận (ẩn danh, không ghi tên)
- Tổng số bình luận; số bình luận có **năm sinh / ngày sinh / con giáp**.
- Nội dung từng bình luận (bỏ tên). Đánh dấu loại: xin xem lá số / khen / hỏi sản phẩm / khác.
- Câu hỏi lặp lại nhiều lần.
- Có bình luận nào chưa được trả lời mà xin xem lá số không (số lượng).

## E. Quảng bá (`https://www.tiktok.com/promote/web/dashboard`)
- Bảng thông tin 7 / 28 ngày: đã chi, view, follower.
- Từng lệnh trong kỳ:
  - ngày giờ đặt, trạng thái (lý do từ chối nguyên văn), mục tiêu;
  - video (thời lượng + caption đầu), thời lượng lệnh;
  - ngân sách, **đã chi**, đối tượng;
  - view / follower / thích từ quảng bá;
  - chi phí mỗi follower.
- Lệnh **đang chạy** (còn bao lâu).
- **Không mở màn hình tạo lệnh.**

## F. Đối chiếu TikTok Manager (trang `/danh-gia/ngu-canh`)
- Chênh lệch view / thích / bình luận / chia sẻ giữa API của tool và Studio, từng video.
- Video chưa gắn gói; gói gắn sai video (caption trên TikTok khác caption của gói).
- Follower theo API so với Studio.
