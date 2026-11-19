---
ma_yeu_cau: VIEC-1911-KE-HOACH-2011-VA-7-NGAY
loai: danh_gia_hieu_suat + ke_hoach (20/11 – 26/11/2026)
tu: Claude
gui: Gemini, Chủ kênh (anh Nhơn)
ngay_tao: 2026-11-19 tối (GMT+7)
tham_chieu: QA-1911-VEO-GIONG-DOC__TRALOI · BAOCAO-1911-HOAN-TAT-GOI-18 · báo cáo tự động TikTok Manager 21:41 19/11
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/VIEC-1911-KE-HOACH-2011-VA-7-NGAY__XACNHAN.md
---

# Đánh giá hiệu suất quy trình và kế hoạch 20/11 – 26/11

## 1. Số liệu kênh (TikTok API, lần quét 17:00 ngày 19/11)
| Chỉ số | Giá trị | Nhận xét |
|---|---|---|
| Follower | **1.222** (24 giờ qua **+35**, 7 ngày +41) | 24 giờ qua tăng gần gấp 8 tốc độ cũ (4,5 follower/ngày) |
| Tốc độ 7 ngày | 19,2 follower/ngày | Mốc 5.000 trước 17/12 cần **135/ngày**: chưa đạt |
| Tim/view 30 ngày | 3,76% (mục tiêu ≥ 4%) | 21/31 video dưới mốc |
| Khung 12:00 · 07:00 · 19:30 | 990 · 393 · 715 view TB; tim/view 11,1% · 5,7% · **2,3%** | 11h–12h tốt nhất; khung 19:30 có view nhưng ít tim |

**Gói 17 (Loại 3, trà sáng, đăng 11:45):** 780 view, 59 tim (**7,6%**), 1 bình luận sau khoảng 5 giờ. Tốc độ **1.883 view/ngày**, cao nhất kênh, và trùng với 24 giờ tăng +35 follower.

**So sánh nhóm nội dung (50 video gần nhất):**
- Video **trà sáng / đếm ngược / chữa lành**: tim/view **5–8%**.
- Video **giải mã lá số**: thường **0,3–2%**, dù có video tới 1.761 view.

→ Lá số kéo view, còn trà sáng kéo **tim và follow**.

## 2. Hiệu suất quy trình (đo trên Gói 17 và Gói 18)
| Bước | Gói 17 | Gói 18 | Đánh giá |
|---|---|---|---|
| P3→P5 (yêu cầu → Gemini trả kịch bản, ảnh, prompt) | **28 phút** (00:25 → 00:53) | khoảng 30–45 phút (XONG lúc 11:17) | ✅ nhanh |
| Sửa ảnh lên v3.3 | 06:35 | — | chỉ tốn 1 lần |
| **P8a (clip thô)** | sáng 19/11 | clip xong **17:01–17:05**, lên Drive 17:14 | ⚠️ **chậm nhất**: khoảng 5–6 giờ chờ, có lúc thử Veo |
| P8b (Gemini cắt ghép, hook, phụ đề) | 08:55 (v1), 10:11 (v2 giữ logo) | **8 phút** (17:14 → 17:22) | ✅ rất nhanh |
| P6/P9 (tool dò thư, nhận video) | tự động | tự động | ✅ |
| P11 (tool gắn video vào gói) | ✅ Gói 17 đã gắn | chờ lần quét 23:00 | ✅ |

**Kết luận:** toàn bộ quy trình đã chạy được từ đầu tới cuối. **P8a là điểm nghẽn duy nhất**: tạo clip tay mất nhiều giờ và bị giới hạn hạn mức 5 giờ của app Gemini.

**Veo API:** theo QA của Gemini, hình ảnh "rất đẹp", nhưng giọng nhảy Bắc/Nam, lệch độ to 3,2 LUFS, tự chèn nhạc nền và đọc sai 2 từ. Gemini và Claude cùng chọn **phương án B**: Veo không tiếng + một giọng TTS cố định.

**Chi phí Gemini API tháng 11 (tool đo):** 19 lần gọi, 250.672 token, **$2,86**. Số này đã gồm khoảng $2,40 cho 3 clip Veo thử.

## 3. Kế hoạch ngày mai – Thứ Năm 20/11 (Ngày Nhà giáo Việt Nam)
| Giờ | Việc | Ai làm |
|---|---|---|
| 07:30 | Tạo 2 yêu cầu trên trang **Yêu cầu Gemini** (Gói 19 và Gói 20, nội dung bên dưới), nhắc Gemini "kiểm tra hộp thư" | Anh Nhơn |
| 08:30 | Gemini trả XONG cho Gói 19 và 20 → Nhập từ hộp thư → Lưu & kiểm tra | Gemini → anh Nhơn |
| 09:00–11:00 | **P8a Gói 19**: 4 clip trên app Gemini → thư mục 02 → duyệt Đạt/Làm lại ở tab Video thô → Gửi Gemini ghép | Anh Nhơn |
| 11:00–11:30 | **P8b Gói 19** → BAOCAO | Gemini |
| **11:45** | **Đăng Gói 19** (Loại 3, có thể bật Quảng bá theo tool) | Anh Nhơn |
| 13:00–17:00 | **P8a + P8b Gói 20** | Anh Nhơn → Gemini |
| **19:30** | **Đăng Gói 20** (Loại 1, không quảng cáo) | Anh Nhơn |
| Trong ngày | Claude làm trang **"Nghe thử giọng Cô Kim"** (3–4 giọng TTS mẫu 8 giây) để anh Nhơn chọn 1 giọng thương hiệu | Claude |

**Gói 19 – Loại 3, tăng follow, 11:45**
- Chủ đề: *"Ngày 20/11 – một chén trà tri ân thầy cô"* (nhóm 5).
- CTA: "bấm theo dõi Cô Kim".
- Không nhắc ngày cụ thể trong lời thoại, để video **vẫn dùng được** nếu chạy quảng cáo nhiều ngày. Ngày 20/11 chỉ đưa vào caption hoặc chữ trên hình.

**Gói 20 – Loại 1, giải mã lá số, 19:30**
- Nhóm 4: **trả lời một bình luận thật** xin xem lá số. Lấy ngày sinh qua **Lá số → Đọc bình luận**, không ghi tên người hỏi.
- Hook mạnh ở giây 0. Kết bằng "để lại ngày sinh dưới bình luận để Cô Kim giải mã" để kéo bình luận.

## 4. Kế hoạch 7 ngày (20/11 – 26/11)
**Nhịp cố định: 2 video/ngày.**
- **11:45 – Loại 3** (trà sáng, chữa lành, cuối năm): kéo tim và follow, có thể chạy quảng cáo.
- **19:30 – Loại 1 nhóm 4** (trả lời bình luận): kéo bình luận, không quảng cáo.
- **Thêm 2 video Loại 2** trong tuần, đăng lúc 12:00 ngày 22/11 và 25/11, chọn SKU **được chạy quảng cáo**:
  - **Gói 16 – khăn lau bàn thờ SP-TET-01:** làm lại ảnh v3.3, chèn ảnh bao bì thật, điền giá.
  - **Ấm tử sa (SP-THO-03)** hoặc **đèn đá muối (SP-HOA-03)**.

| Ngày | 11:45 | 19:30 | Việc thêm |
|---|---|---|---|
| T5 20/11 | Gói 19 – tri ân 20/11 | Gói 20 – trả lời bình luận | Claude: trang nghe thử giọng TTS |
| T6 21/11 | Trà sáng cuối tuần | Lá số theo tuổi (nhóm 2) | **Đọc kết quả Quảng bá Gói 17 sau 48 giờ** (chi phí mỗi follow, tỷ lệ xem hết) → quyết giữ hay tăng ngân sách |
| T7 22/11 | **Loại 2: khăn lau Tết (Gói 16)** | Trả lời bình luận | Anh Nhơn chốt giọng TTS → **DONGTHUAN V3** |
| CN 23/11 | Trà đêm / "Đêm Trà Giải Mã" | Nhân duyên gia đạo (nhóm 3) | Thử Veo **phương án B** cho 1 gói (≈ $2,56) |
| T2 24/11 | Trà sáng đầu tuần | Trả lời bình luận | Nếu B đạt: P8a chuyển sang Veo |
| T3 25/11 | **Loại 2: ấm tử sa / đèn đá muối** | Kiến thức Bát Tự (nhóm 6) | — |
| T4 26/11 | Trà sáng | Trả lời bình luận | **TUANTHU-2611** (tổng kết tuần, mã thư mới) |

## 5. Mục tiêu 7 ngày (đo bằng TikTok Manager)
| Chỉ số | Hiện tại | Mục tiêu 26/11 |
|---|---|---|
| Follower | 1.222 | **≥ 1.430** (khoảng +30/ngày) |
| Tim/view 30 ngày | 3,76% | **≥ 4,0%** |
| Bình luận trung bình video Loại 1 | khoảng 0–1 | **≥ 5** |
| Thời gian P8a mỗi gói | 5–6 giờ | **≤ 2 giờ** (tay); ≤ 30 phút nếu Veo phương án B đạt |

**Nói thẳng về mốc 5.000 follower trước 17/12:** cần 135 follower/ngày. Với tốc độ tự nhiên hiện nay thì **không đạt**. Đề nghị anh Nhơn quyết sau khi xem kết quả Quảng bá Gói 17 ngày 21/11:
- (a) tăng ngân sách quảng cáo cho các video Loại 3 hoặc Loại 2 được chạy quảng cáo; hoặc
- (b) dời mốc 5.000 sang cuối tháng 1/2027.

## 6. Việc của Gemini
1. Ngày 20/11: làm Gói 19 và Gói 20 theo thư yêu cầu từ tool, gồm kịch bản, 4 ảnh v3.3 và 4 prompt. P8b ngay sau khi tool gửi thư GHEP.
2. Phương án B: khi Claude có 3–4 giọng TTS mẫu, chấm từng giọng: giọng miền Nam, độ ấm, đọc đúng dấu, tốc độ khoảng 3,5–3,8 âm tiết/giây.
3. Chuẩn bị thư mẫu **TUANTHU-** (tổng kết tuần) cho ngày 26/11. Số liệu lấy từ Doc BAO_CAO trong thư mục 06.

## Mẫu xác nhận
```
ma_yeu_cau: VIEC-1911-KE-HOACH-2011-VA-7-NGAY
dong_y_ke_hoach_7_ngay: co | sua: …
goi_19_20_ngay_2011: san_sang | vuong: …
de_xuat_chu_de_them: […]
```
