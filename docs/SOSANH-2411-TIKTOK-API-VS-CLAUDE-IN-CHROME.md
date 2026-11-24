# So sánh hai nguồn số liệu: TikTok Manager (TikTok API) và Claude in Chrome (TikTok Studio)

**Ngày:** 24/11/2026.
**Căn cứ:**
- code TikTok Manager (`app/tiktok.py`, `app/scanner.py`, `app/scheduler.py`);
- 4 báo cáo Claude in Chrome (kênh, Gói 24/26, Gói 27, Gói 17, Quảng bá);
- lần cập nhật Gói 17 lúc 21:42.

## 1. Mỗi nguồn lấy được gì

TikTok Manager dùng **TikTok Display API v2**. Quyền được cấp gồm `user.info.basic`, `user.info.profile`, `user.info.stats` và `video.list`. Tool tự quét **4 lần/ngày** (05:00, 11:00, 17:00, 23:00) và lưu ảnh chụp số liệu sau mỗi lần quét.

| Số liệu | TikTok API (tool) | Claude in Chrome (Studio) |
|---|---|---|
| View, thích, bình luận, chia sẻ của từng video | ✅ **số chính xác** | ✅ nhưng hay bị làm tròn ("10K", "11K") |
| Follower, tổng thích, số video của kênh | ✅ chính xác | ✅ |
| Lịch sử theo thời gian (view từng video sau mỗi lần quét) | ✅ **tự lưu, 4 mốc/ngày** | ⚠️ chỉ đọc được biểu đồ theo ngày/giờ, ước lượng "~" |
| Lưu (save) | ❌ | ✅ |
| Người xem duy nhất, người xem mới / quay lại | ❌ | ✅ |
| **Follower mới do từng video** | ❌ | ✅ |
| **Giữ chân từng giây**, thời gian xem trung bình, tỷ lệ xem hết | ❌ | ✅ |
| **Nguồn view** (Đề xuất / Đã follow / Tìm kiếm) và **từ khoá tìm kiếm** | ❌ | ✅ |
| Tuổi, giới tính, vùng người xem | ❌ | ✅ |
| Giờ follower hoạt động | ❌ | ✅ |
| **Trả phí / tự nhiên** (trang Quảng bá) | ❌ | ✅ **chỉ nguồn này có** |
| Nội dung bình luận | ❌ (anh dán tay vào trang Lá số) | ✅ (đã bỏ tên người viết) |
| Video thật: khung 0, chữ hook, câu kêu gọi ở giây mấy | ❌ | ✅ |
| Gắn video với gói và kịch bản | ✅ (tự khớp caption) | ✅ đọc qua trang ngữ cảnh của tool |

## 2. Điểm mạnh và điểm yếu

### TikTok API
**Mạnh:**
- Tự động, không tốn token.
- Không cần máy anh bật.
- Số tổng chính xác, lặp lại được.
- Có **chuỗi lịch sử** để tính tốc độ view/ngày và tiến độ KPI.

**Yếu:**
- **Nông.** Không có giữ chân, nguồn view, follower theo video.
- **Không phân biệt được view trả phí.** Đây là lý do chiến lược 15–24/11 kết luận sai: "trà sáng 11h viral", "đêm không có view", "kênh tăng ~227 follower/ngày". Số API của Gói 17 là thật, nhưng 95% là view mua.
- Quét 4 lần/ngày thì chỉ biết view tăng theo từng khoảng 6 giờ.

### Claude in Chrome
**Mạnh:**
- Đọc được đúng những gì quyết định chất lượng nội dung: giữ chân giây 2, follower theo video, nguồn view, từ khoá.
- **Tách được trả phí / tự nhiên.**
- Xem video thật để chấm hook.
- Đối chiếu được với kịch bản.

**Yếu:**
- **Sai số khi đọc biểu đồ.** Ví dụ giữ chân của Gói 27 ở giây 2 ghi "~51%".
- **Số bị làm tròn:** Gói 17 hiển thị "10K" lúc 16:45 và "11K" lúc 21:42.
- **Các trang lệch giờ cập nhật.** Trong 20 phút, trang Quảng bá thêm 40 view, còn Studio gần như đứng yên. Vì vậy phần tự nhiên chỉ ước được trong khoảng ~400–450 view.
- **Tốn token:** ước tính 50.000–100.000 token mỗi lần quét đầy đủ. Mất 15–25 phút.
- Cần máy bật, Chrome mở, đã đăng nhập. Giao diện TikTok đổi thì có thể đọc nhầm chỗ.
- Mỗi lần chạy có thể khác nhau một chút, vì đây là AI đọc màn hình chứ không phải API.

## 3. Đối chiếu thực tế trên Gói 17

| Chỉ số | API (tool) | Studio (Chrome) | Quảng bá (Chrome) | Nhận xét |
|---|---|---|---|---|
| Tổng view | số chính xác (trang hồ sơ 10,2K) | "10K" → "11K" | 9.491 → 9.889 trả phí | Lấy **API** làm tổng, **Quảng bá** làm phần trả phí |
| Follower do video | không có | 695 → 722 | 674 → 702 | Chỉ Chrome có. Phần tự nhiên ~20–21 |
| Giữ chân giây 2 | không có | 53% | 54,5% (chỉ số nội dung của lệnh) | Hai trang khớp nhau ±2 điểm |
| Thích | 964 | 964 → 993 | 954 → 985 | Khớp |

**Kết luận:** về số tổng, hai nguồn **khớp nhau**. Lệch chỉ do làm tròn và giờ cập nhật. Phần **giá trị nhất** (trả phí / tự nhiên, giữ chân, follower theo video) **chỉ Claude in Chrome có**.

## 4. Nguồn chuẩn cho từng loại số

| Loại số | Nguồn chuẩn | Nguồn phụ |
|---|---|---|
| Tổng view / thích / bình luận / chia sẻ, follower kênh | **API** | Chrome (đối chiếu) |
| Tốc độ view theo thời gian, KPI | **API** (chuỗi lịch sử) | – |
| Trả phí / tự nhiên | **Chrome (trang Quảng bá)** | – |
| Giữ chân, xem trung bình, xem hết | **Chrome (Studio)** | – |
| Follower do video, nguồn view, từ khoá | **Chrome (Studio)** | – |
| Chất lượng hook (H1–H6), khớp kịch bản | **Chrome (xem video)** | Bộ kiểm tra gói của tool (trên kịch bản) |
| Giờ đăng tốt nhất | **Chrome (giờ follower hoạt động)** + **API** (view theo mốc quét) | – |

## 5. Đề xuất phối hợp

1. **Giữ API làm xương sống.** Quét 4 lần/ngày, miễn phí, chính xác. Không thay được và không cần thay.
2. **Chrome làm lớp chiều sâu, chạy có chọn lọc để tiết kiệm token:**
   - **hằng ngày 16:30**: chỉ các video 24–96 giờ tuổi;
   - **hằng tuần Thứ Hai**: thêm trang Quảng bá và so sánh nhóm.
   - Không quét lại video cũ đã có báo cáo, trừ khi có lý do (như Gói 17 sau khi lệnh quảng bá kết thúc).
3. **Quy tắc ghép số (skill đã áp dụng):**
   - tổng = API;
   - trả phí = trang Quảng bá;
   - tự nhiên = tổng − trả phí, ghi dạng khoảng.
4. **Việc nên làm tiếp trong tool (chưa làm):**
   - **(a)** Đọc khối JSON của báo cáo Chrome thành **bảng số liệu theo video**: giữ chân giây 2, follower mới, trả phí/tự nhiên, điểm H. Hiện báo cáo mới chỉ được đưa nguyên văn vào lời dặn chiến lược. Có bảng này thì trang Phân tích và KPI dùng được số tự nhiên.
   - **(b)** **Tự cảnh báo nghi quảng bá:** khi view một video tăng đều ~1.500–2.000 mỗi ngày nhiều ngày liền, hoặc tăng vọt ngay sau khi đăng, tool đánh dấu "cần Chrome kiểm tra trang Quảng bá".
   - **(c)** Bảng "**chênh lệch API ↔ Studio**" theo video, để biết khi nào số API bị trễ.
5. **Bảo vệ dữ liệu:**
   - API không lấy bình luận.
   - Chrome chỉ ghi bình luận đã bỏ tên.
   - Ngày sinh trong bình luận vẫn chỉ xử lý ở trang Lá số, không lưu vào cơ sở dữ liệu.
