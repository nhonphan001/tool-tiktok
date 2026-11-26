# Ghi chú cuối của Claude gửi An (Antigravity)

**Ngày:** 26/11/2026 · **Từ:** Claude · **Qua:** anh Nhơn

## 1. Kết quả bài kiểm tra bàn giao: ĐẠT (khoảng 24/25, câu 26 xuất sắc)

Phần **An toàn** đúng hết. Phần **Thực hành** chạy thật, có dẫn nguồn. Câu 21 tìm ra **nhiều lỗi tool bỏ sót hơn cả đáp án**. Câu 26 tự nhận ra **3 kết luận quá tay trong chính Phụ lục C của mình**. Từ đây An nhận toàn bộ nhiệm vụ trong `docs/HANDOVER-ANTIGRAVITY.md`.

Hai chỗ cần hiểu lại:
- **Câu 5:** báo cáo đồng thuận được ghi đè Doc gửi Gemini trong **2 trường hợp**:
  - (a) tự động sau mỗi báo cáo Claude in Chrome được lưu (`consensus.after_report`);
  - (b) khi anh Nhơn bấm **"Gửi Gemini ngay"** ở trang `/dong-thuan` (`consensus.ingest_all()` + `push()`).
- **Câu 10:** `script_ai.draft_and_store()` chỉ soạn và lưu. Nhưng khi tạo yêu cầu (hoặc bấm "Soạn lại kịch bản AI"), tool chạy nền `_script_bg()` trong `app/main.py`: **soạn → kiểm → tự gửi thư cho Gemini** (`gemini_requests.send`). Gói 35+ được gửi đi **mà không cần ai bấm Gửi**. Vì vậy phải kiểm 1–2 thư đầu **sau khi** chúng đã nằm trong GUI_GEMINI. Nếu thư có lỗi, gửi thư `SUA-…` cho Gemini, không đợi.

## 2. Việc làm ngay

1. **Sửa Phụ lục C** trong `docs/HANDOVER-ANTIGRAVITY.md`: hạ 3 điểm ở câu 26 xuống **[Giả thuyết]**.
   - nhân khẩu học "60% nữ" (n = 1 video, 175 view);
   - so sánh giữ chân Gói 30 (lệch mốc 5 giờ so với hơn 24 giờ; Gói 17 có trả phí);
   - 5 từ khoá tìm kiếm (khoảng 1 lượt mỗi từ).
   - Ghi chú: chờ Gói 31–33 rồi mới kết luận lại.
2. **Gói 32:** Gemini đã trả phiếu `SANXUAT-2511-GOI-32-ROT-TRA-NGUOI-THUONG__XONG.md` (26/11 10:37) và báo dựng xong `BAOCAO-2611-HOAN-TAT-GOI-32__GUI_CLAUDE.md` (10:56). Kiểm lại, dù đã đăng:
   - phiếu có giữ nguyên văn lời thoại không;
   - tool đã chuyển gói sang "Đã dựng – chờ đăng" từ thư mục 04 chưa.
3. **Gói 33** (12:30 hôm nay): phiếu `SANXUAT-2511-GOI-33-NU-CANH-NGO-1990__XONG.md` (10:36) đã về. Kiểm ngay:
   - lời thoại nguyên văn;
   - 7 ảnh cùng bối cảnh sáng;
   - `o_phep_thu` là "12:30 × kiểu B";
   - thành phẩm dài trên 61 giây khi Gemini báo dựng xong.
4. **Gói 34** (CN 29/11, 19:00): dùng bản cảnh 7 An đã viết lại (232 âm tiết, đã qua bộ kiểm tra). Trình anh Nhơn duyệt rồi gửi `SANXUAT-ddmm-GOI-34-TRA-LOI-QUY-SUU-1973__YEUCAU.md`.
   - Thư theo khuôn Gói 31/33: lá số do tool tính, lời thoại giữ nguyên văn, Gemini chỉ làm ảnh + prompt, có VOICE_BLOCK.
   - Phần lá số dùng **ngày giờ sinh đầy đủ 20/02/1973 19:00, nữ**. Ghi kèm 2 cảnh báo B.2: giờ sinh sát ranh giới canh giờ, vượng nhược sát ngưỡng.
   - Video dùng tính năng **"Trả lời bằng video"** để bình luận của chị hiện trên màn hình. **Không nêu tên khách** trong lời thoại hay caption.

## 3. Lưu ý vận hành

1. **Google Drive for Desktop:** hỏi anh Nhơn đã cài chưa.
   - Chưa cài: An không tự đọc hay gửi thư trong hộp thư được. Mỗi lần "check thư" phải nhờ anh Nhơn tải file về, và tải thư lên GUI_GEMINI hộ.
   - Đã cài: thư mục hộp thư hiện như thư mục thường. **Chỉ thêm và đọc file, không xoá, không di chuyển.**
2. **Thư mục làm việc:** repo đang ở `…\.gemini\antigravity\scratch\tool-tiktok`, thư mục "scratch" có thể bị dọn.
   - Chuyển sang một thư mục cố định, ví dụ `C:\Users\<user>\Projects\tool-tiktok`.
   - Xong mỗi việc thì commit và push.
   - **Không để `.env` hay `secrets/` trong thư mục đồng bộ Drive.**
3. **Một người push:** từ nay **chỉ An push** lên nhánh `claude/elegant-tesla-xcj8h4`. Claude dừng push.
   - Trước khi push luôn chạy `git fetch` + `git merge`. **Không** `--force`.
   - Hỏi anh Nhơn trước khi gộp vào nhánh chính hay đổi nhánh mà VPS đang `git pull`.
4. **Sau mỗi lần sửa code:** chạy `python -m pytest -q` (hiện có 117 test, phải xanh), rồi nhắc anh Nhơn cập nhật VPS:
   ```bash
   cd /root/tool-tiktok && git pull && docker compose up -d --build
   ```
5. **Hai lỗi bộ kiểm tra An phát hiện ở câu 21** nên sửa sớm, kèm test:
   - (a) `compliance.py` chưa bắt "may mắn / tài lộc" đứng riêng, không có động từ dẫn ("muốn may mắn tài lộc");
   - (b) `packages.check()` chưa cảnh báo khi **Loại 1 có dưới 7 cảnh**, và chưa liệt kê đủ mọi chữ chỉ giờ (đang dừng ở lỗi đầu tiên).
   - Đây là việc của Gói 35+: Gemini API tự sửa theo bộ kiểm tra, nên bộ kiểm tra càng chặt thì kịch bản tự soạn càng sạch.
6. **Kết quả kiểm quảng bá tháng 3** (`docs/YEUCAU-2511-CLAUDE-IN-CHROME-KIEM-QUANG-BA-THANG-3.md`): khi Claude in Chrome lưu báo cáo, đọc kết luận từng video.
   - Nếu 2 video là **tự nhiên**: báo Gemini, và đưa "lá số năm sinh cụ thể từng đạt 3–4 nghìn view tự nhiên" vào tổng kết 02/12.
7. **Nguyên tắc giữ nguyên:**
   - lá số chỉ tính bằng `battu.py`;
   - mọi kịch bản qua `packages.check()`;
   - quy tắc mới chỉ thêm vào `app/defaults/script_rules.md`;
   - kết luận luôn ghi **[Dữ kiện] / [Giả thuyết]**;
   - việc tốn tiền chỉ làm khi anh Nhơn xác nhận;
   - không xoá thư;
   - dữ liệu khách không ra khỏi tool.

Chúc An làm tốt. Tài liệu đầy đủ nằm ở `docs/HANDOVER-ANTIGRAVITY.md` và `AGENTS.md`.

— Claude
