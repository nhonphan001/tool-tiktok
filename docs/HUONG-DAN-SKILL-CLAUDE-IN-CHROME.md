# Hướng dẫn cài skill `tiktok-studio-quet` cho Claude in Chrome và chạy theo lịch

## Skill làm gì

Claude in Chrome dùng **chính trình duyệt của anh** (đã đăng nhập TikTok và TikTok Manager) để:

1. **Đọc ngữ cảnh từ TikTok Manager** ở trang `https://tiktok.nangtamchatluongsong.vn/danh-gia/ngu-canh`:
   - video nào thuộc gói nào, Loại, số cảnh;
   - kịch bản gốc;
   - số view lấy qua API;
   - bối cảnh quảng bá.
2. **Quét TikTok Studio** ở chế độ chỉ đọc:
   - tổng quan kênh;
   - giờ follower hoạt động;
   - từng video: giữ chân từng giây, nguồn view, từ khoá tìm kiếm, view theo giờ, bình luận đã ẩn danh;
   - mở video thật để chấm 6 quy tắc hiệu suất H1–H6.
3. **Kiểm tra trang Quảng bá** để tách số tự nhiên và số trả phí.
4. **Đối chiếu TikTok Manager với Studio:** số chênh lệch, video chưa gắn gói.
5. **Dán báo cáo .md** (có khối JSON chuẩn `tiktok-studio-quet/v1`) vào trang **Đánh giá** của TikTok Manager. Lần lập chiến lược sau, tool tự dùng 5 báo cáo mới nhất.

**Ba chế độ:**

| Chế độ | Phạm vi |
|---|---|
| **hằng ngày** | Tổng quan kênh 7 ngày, cộng các video đăng 24–96 giờ trước |
| **hằng tuần** (Thứ Hai) | Mọi video 7 ngày, trang Quảng bá, so sánh nhóm, đề xuất tuần sau |
| **video `<ID>`** | Chỉ một video |

## Bước 1: Cập nhật TikTok Manager trên VPS

Chạy lệnh quen thuộc:

```bash
cd /root/tool-tiktok && git pull && docker compose up -d --build
```

Sau đó vào trang **Đánh giá** trên thanh menu, sẽ thấy nút **"Tải skill (.zip)"** và **"Xem trang ngữ cảnh"**.

## Bước 2: Cài skill

1. Tải `tiktok-studio-quet.zip`. Lấy ở trang Đánh giá, hoặc file `docs/tiktok-studio-quet.zip` trong repo.
2. Mở **claude.ai → Settings (Cài đặt) → Capabilities → Skills**, chọn **Upload skill**, chọn file .zip.
3. Bật skill. Claude in Chrome dùng các skill đã bật trong tài khoản Claude của anh.
   - Nếu bản Claude in Chrome của anh chưa hỗ trợ skill: mở `SKILL.md` trong file zip, chép toàn bộ nội dung làm lời nhắn mở đầu. Hai file trong `references/` dán kèm phía dưới.

## Bước 3: Đặt lịch chạy trong Claude in Chrome

Trong Claude in Chrome, tạo **tác vụ định kỳ** (Scheduled task / Shortcut có lịch). Tên mục có thể khác tuỳ phiên bản.

| Tác vụ | Lịch | Lời nhắn |
|---|---|---|
| Quét hằng ngày | Mỗi ngày **16:30** | `Chạy skill tiktok-studio-quet, chế độ hằng ngày.` |
| Quét hằng tuần | **Thứ Hai 09:00** | `Chạy skill tiktok-studio-quet, chế độ hằng tuần.` |

**Điều kiện để chạy được:**
- Máy tính đang bật, Chrome đang mở.
- Vẫn đăng nhập **TikTok** và **TikTok Manager**. Phiên TikTok Manager hết hạn thì skill sẽ dừng và báo.

**Vì sao chọn 16:30:** video 11:00 hôm trước đã qua khoảng 30 giờ, video 19:00 hôm trước đã qua khoảng 22 giờ. Đủ để có đường giữ chân và nguồn view.

## Bước 4: Lần đầu, chạy tay để kiểm tra

1. Mở Claude in Chrome, gõ: `Chạy skill tiktok-studio-quet, chế độ hằng ngày.`
2. Cho phép Claude in Chrome truy cập 2 trang web: `tiktok.com` và `tiktok.nangtamchatluongsong.vn`.
3. Chạy xong, vào **TikTok Manager → Đánh giá**. Báo cáo mới phải nằm ở đầu mục "Đã lưu".

## An toàn

- Trên TikTok, skill **chỉ đọc**. Skill không bấm Quảng bá, nạp tiền, sửa/xoá video, trả lời bình luận.
- Trên TikTok Manager, skill chỉ đọc trang và bấm **"Lưu báo cáo"** ở trang Đánh giá. Không bấm Gửi Gemini, Quét, Xoá hay Lưu cài đặt.
- Báo cáo **không ghi tên người bình luận**, số thẻ, số dư ví, email, số điện thoại.
