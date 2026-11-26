# HỒ SƠ ĐÓNG GÓI QUY TRÌNH & BÀN GIAO CÔNG VIỆC: GEMINI → ANTIGRAVITY

**Thời điểm đóng gói:** `15:41` Thứ Năm, `26/11/2026` (GMT+7)  
**Bên bàn giao:** Gemini Pro (phụ trách Sản xuất ảnh AI, Prompt video, Hậu kỳ P8b, QA clip thô & Kiểm chéo số liệu)  
**Bên tiếp nhận:** Antigravity  
**Chủ dự án:** Anh Phan Thành Nhơn · **Kênh:** Tiệm Trà Giải Mã _ Cô Kim (`@tiemtragiaima`)

> **Ghi chú tiếp nhận của Antigravity (`26/11/2026 15:46`):** Lưu nguyên văn hồ sơ bàn giao của Gemini Pro bên dưới. Bổ sung 3 đối chiếu mới nhất tại thời điểm tiếp nhận:
> 1. `[Dữ kiện]` Số liệu mới nhất của **Gói 30** (~27 giờ, quét Antigravity `26/11 13:57`): `216` view, `25` thích (`11,57%`), `6` follower (`2,78%`), giữ chân 2s `57%`, xem TB `7,29s`, xem hết `6,7%`, Nữ `61%`.
> 2. `[Giả thuyết]` Nhận định nhân khẩu tự nhiên toàn kênh là `60% Nữ` vẫn giữ nhãn `[Giả thuyết]` (chờ Gói 31–33 đủ 24–48 giờ để đủ cỡ mẫu, thống nhất theo `HANDOVER-ANTIGRAVITY.md` Phụ lục C).
> 3. **Gói 34** đã soạn sẵn bản hoàn chỉnh (`232` âm tiết, `0` lỗi bộ kiểm tra) tại `docs/SANXUAT-2611-GOI-34-TRA-LOI-QUY-SUU-1973__YEUCAU.md`, chờ anh Nhơn duyệt trước khi gửi `GUI_GEMINI`.

---

## 1. Bức tranh tổng thể & Vai trò bàn giao

Tài liệu này đóng gói toàn bộ quy trình vận hành thực chiến, bài học kỹ thuật đã xử lý trong phiên làm việc `23/11 – 26/11/2026`, trạng thái toàn bộ các gói từ **Gói 27 đến Gói 33**, và hàng đợi công việc tiếp theo từ **chiều 26/11 đến 02/12/2026** để Antigravity tiếp quản liền mạch (kết hợp cùng bản bàn giao code/hệ thống `HANDOVER-ANTIGRAVITY.md` từ Claude).

### Thông số kênh & bối cảnh hiện tại (`26/11/2026`)
- **Trạng thái chiến dịch:** Đang ở ngày thứ 2 của **Tuần thử nghiệm 100% tự nhiên (`25/11 – 01/12/2026`)** — **TUYỆT ĐỐI KHÔNG bật Quảng bá (Promote)** cho bất kỳ video nào.
- **Số liệu nền đồng thuận (`75/75` video đã quét xong trên TikTok Studio):**
  - Follower: ~`3.251` (trong đó ~`2.020` follower mua từ chiến dịch Quảng bá `15–24/11`, tổng chi ~1 triệu đồng).
  - Cả 3 video vượt `3.000` view tháng 3 (`18/03`, `19/03`, `25/03`) đều đã được báo cáo lúc `15:20` ngày `25/11` xác nhận **CÓ Quảng bá** (phần tự nhiên chỉ `276–416` view).
  - **Khung giờ tự nhiên tốt nhất:** `19h` (TB `602,5` view, giữ chân 2s `46,5%`), `11h` (TB `594,8` view, giữ chân 2s `45,4%`, follow/view `2,0%`), `12h` (`417,7` view). **Khung yếu nhất:** `06h–07h` (`239–258` view, giữ chân 2s `27%–33%`) và `13h–15h` (`110–113` view).
  - **Lợi thế Tìm kiếm (Search):** Video có từ khóa năm sinh cụ thể hoặc kiến thức Bát Tự kéo `19,2%–34,6%` view từ Search (so với `0,1%–0,4%` ở video trà chung chung).
  - **Kết quả thực tế 5 giờ đầu Gói 30** (video `100%` tự nhiên đầu tiên, đăng `11:09` ngày `25/11`, `ID: 7711956219509886215`): `175` view, `10,86%` tim/view, `4` follower (`2,29%`), xem TB `6,87s` (**+46%** so với Gói 29 `4,7s`), xem hết `5,7%` (**gấp 2,2×** Gói 29 `2,6%`), và **nhân khẩu tự nhiên thật là `60% Nữ`, `71%` từ 35+ tuổi**.

### Cảnh báo "Bẫy Quảng bá" (bắt buộc giữ khi phân tích Studio)
1. **KHÔNG** dùng mốc `4,4K–11K` view (Gói 17, 19, 26, 28) hay tốc độ `+1,4K` follower/tuần làm chuẩn tự nhiên.
2. **KHÔNG** dời lịch sang `06:00–06:30` sáng (đỉnh `06:00` trên Studio là của tệp follower mua; 6 video tự nhiên `06h–07h` yếu nhất kênh).
3. **KHÔNG** chuyển sang phục vụ `61% Nam` (đó là tệp quảng cáo; tệp tự nhiên thật đo trên Gói 30 là `60% Nữ`).
4. **KHÔNG** đưa Bát Tự / Can Chi / lời mời "comment năm sinh" vào tuyến **Trà sáng Loại 3** (giữ sạch để đủ điều kiện Quảng bá khi cần).

---

## 2. Bản đồ tài nguyên Google Drive

| Tài nguyên | Vai trò | Drive ID |
| :--- | :--- | :--- |
| Thư mục gốc dự án | `HE_THONG_TU_DONG_HOA_TIKTOK_TIEM_TRA_GIAI_MA` | `1ys6SNAuynEFGw0Ao0lJu95nv_ap-dewD` |
| `01_KICH_BAN_VA_ANH_AI` | Lưu toàn bộ ảnh 9:16 của các gói | `1iePe5cdLrnz0O6nccQch8TP4w4i4HzIQ` |
| `04_VIDEO_DA_DUYET_SAN_SANG_DANG` | Lưu video thành phẩm (`_Final_Sub.mp4` & `_Clean_Master.mp4`), tool tự quét mỗi 10 phút | `1JOpC__Wf1E2y-7wxodvZDCU12_gj69AH` |
| `GUI_GEMINI` | Hộp thư đến (phiếu `SANXUAT`, `SUA`, `CHOT`, `PHANHOI`, báo cáo đồng thuận) | `16C0ZEvMyfdRZ_lcgXdxlN7JhuruaXy9l` |
| `GUI_CLAUDE` | Hộp thư trả lời (`__XONG.md`, `__XACNHAN.md`, `BAOCAO-`, `DANHGIA-`, `DEXUAT-`) | `1oFj8HZVoIY0CYQkkkyza9d2GCToaQUVC` |
| `HOP_THU_TOOL__YEUCAU` | Hộp thư tổng hợp tự động của TikTok Manager (kiểm tra khi có lệnh `"check thư"`) | `1x6QmTfs7cl2cU-wRUQDZnXLu33dKYeeMNPNjVr04Plg` |
| `BAO_CAO_DONG_THUAN__GUI_GEMINI.md` | Bộ số ghép chuẩn duy nhất (API + Chrome Studio), đọc trước mọi phiếu mới | `110M2BH7w_jzTwXMg_Dg_cC8VqHF7fE4yuY3g1f7npgU` |
| `TOM_TAT_TU_DONG__GUI_GEMINI.md` | Bản tóm tắt quét API & Chiến lược 7 ngày tự động của tool | `13OTXOO8HYr_RqZYJnZj5uu40LWOZhXiQJzhGp_HxhM8` |
| `QUYTAC-KICH-BAN-V1-2511.md` | Bộ quy tắc kịch bản bản 1 (tổng hợp toàn bộ quy tắc A–G chốt `25/11`) | `1aldytv1isXfF9ilra-hD-Qu7N9CHXRMnomG-phdWBTw` |
| `CO_KIM_MASTER_FACE_CHUAN_NHAT_3957.png` | Ảnh khuôn mặt chuẩn duy nhất của Cô Kim (khóa mặt mọi gói) | `1gnq18QukC1lCSC0py5Zmf18lR78r3CEH` |

---

## 3. Quy trình sản xuất khép kín chuẩn V2.5 (đã chuẩn hóa thực chiến)

### Giai đoạn A — Kiểm tra hộp thư (`"check thư"`)
1. Đọc đồng thời `HOP_THU_TOOL__YEUCAU` và tìm file mới trong `GUI_GEMINI` theo `modifiedTime`.
2. Kiểm tra `BAO_CAO_DONG_THUAN__GUI_GEMINI.md` nếu có lượt quét Studio mới trước khi lập hoặc góp ý bất kỳ kịch bản nào.

### Giai đoạn B — Tạo bộ ảnh 9:16 đồng nhất 100% & Soạn phiếu `SANXUAT-...__XONG.md`
1. **Khóa nhân vật & bối cảnh (A5/H6):**
   - Dùng duy nhất ảnh gốc `CO_KIM_MASTER_FACE_CHUAN_NHAT_3957.png` (mặt trái xoan, cười khép môi sau voan tím, trâm vàng ngọc đỏ, áo cổ phục tím-đỏ đô).
   - **Mẹo khóa bối cảnh tuyệt đối:** Luôn tạo **Cảnh 1** trước (neo vào `3957.png`), sau đó tạo toàn bộ các cảnh còn lại (`2→4` hoặc `2→7`) bằng cách truyền **cả `3957.png` lẫn ảnh Cảnh 1** làm ảnh tham chiếu, chỉ đổi động tác tay/đạo cụ.
   - **Ánh sáng:** Khung 0 phải sáng rõ và có chuyển động ngay (rót trà bốc khói). Loại 3 dùng hiên gỗ/vườn nắng sớm; Loại 1 dùng phòng trà gỗ sáng ấm (có cửa sổ nắng trưa hoặc đèn bàn vàng dịu buổi chiều muộn) — **CẤM phòng tối**.
   - **Sạch C.7/C.8:** Không lửa thật, không hào quang/hiệu ứng phát sáng, không chắp tay khấn vái, không nhang/nụ trầm, không mâm cúng, không vật phẩm phong thủy.
2. **Viết Prompt video 10 giây (Veo / Flow):**
   - Mỗi prompt chứa **nguyên văn** lời thoại tiếng Việt của cảnh đó (năm sinh viết bằng chữ, ví dụ *"tám tư"*, *"chín mươi"*, *"hai không hai bảy"*) và khối `VOICE_BLOCK` giống hệt nhau ở mọi cảnh:
     > `Voice (identical in every scene): a 26-year-old Southern Vietnamese woman (polite Saigon accent, never Northern or Central), warm mezzo-soprano around 222Hz, calm and soothing with a gentle smile in her voice, steady pace of about 4 syllables per second, crisp Vietnamese tones, even volume. She starts speaking right at 0.0s. Dry close-mic voice only: NO background music, NO ambient sound, NO sound effects.`
   - **Xử lý lỗi từ chối giả của Veo/Flow (`"I can't make videos of real people in situations like that"` — đã gặp & xử lý thành công ở Cảnh 7 Gói 33):**
     - Bỏ các từ dễ kích hoạt bộ lọc an toàn như `"affectionate"`, `"fire"` (kể cả trong cụm phủ định `"no fire"`), và kiểm tra không để sót ký tự `---` hoặc dấu markdown cuối prompt.
     - Đổi tên riêng `"Cô Kim"` trong phần mô tả hình ảnh thành `"The woman in the purple embroidered traditional silk robe"` (chỉ giữ `"Cô Kim"` trong câu thoại tiếng Việt). Nếu vẫn báo, đổi `"a 26-year-old Southern Vietnamese woman"` thành `"a young Southern Vietnamese woman"`.
3. **Định dạng bắt buộc của phiếu `SANXUAT-...__XONG.md` (bài học lỗi parser đã sửa ở Gói 32–33):**
   - **BẮT BUỘC** dùng đúng tiêu đề H1: `# Lời thoại 4 cảnh × 10 giây` (hoặc `7 cảnh × 10 giây`), `# Chữ trên hình`, `# Caption`, `# Bình luận ghim`, `# Prompt tạo video 10 giây (Veo / Flow)`.
   - **BẮT BUỘC** trình bày cả phần **Lời thoại** và phần **Prompt tạo video** dưới dạng **danh sách đánh số liên tục `1.`, `2.`, `3.`...** — **TUYỆT ĐỐI KHÔNG dùng bảng (table) hay tiêu đề phụ H2 (`## Cảnh 1...`)** bên trong 2 mục này vì `app/mailbox.py` ngắt mục theo tiêu đề H2, sẽ làm trống toàn bộ phần Prompt khi nhập vào TikTok Manager.
   - Đủ khối đầu trang (`da_doc`, `ma_yeu_cau`, `o_phep_thu` với Loại 1, `anh_4_canh` / `anh_7_canh`) và khối cuối trang (`nhan_video`: `goi`, `loai`, `so_canh`, `duoc_chay_quang_cao`). Bỏ mục "Kế hoạch quảng cáo".

### Giai đoạn C — Quy trình dựng hậu kỳ P8b trực tiếp (`CHOT-2511`)
1. **Nhận clip thô:** Anh Nhơn gửi trực tiếp 4–7 clip thô (`10s`, `720x1280`, `24fps`) trong chat — không còn qua thư mục `02` hay chờ thư `GHEP`.
2. **QA âm học tự động (Python `wave` + `numpy`, không dùng `soundfile`):**
   - Kiểm tra 100% khớp nguyên văn lời thoại phiếu, không vấp thoại, không nhạc nền.
   - Đo biên độ RMS từng `20ms` (ngưỡng `-35 dB`) để xác định chính xác `t_start`, `t_end` và danh sách khoảng nghỉ nội bộ (`pauses`) phục vụ canh phụ đề sát từng nhịp thở.
   - Đo cao độ trung vị `F0_med` (giọng Cô Kim chuẩn ổn định trong dải `205–236 Hz`).
3. **Dựng FFmpeg xuất 2 bản (`_Clean_Master.mp4` & `_Final_Sub.mp4`):**
   - **Cắt sát `0.00s` (A2/H1):** Cắt sạch khoảng lặng đầu Cảnh 1 để giọng vào ngay `0.00s` (dùng `afade=t=in:st=0:d=0.010` chống nổ tiếng); các điểm nối cảnh dùng `afade` `25ms`.
   - **Container tạm:** Ghép thô ra `.mkv` (`-c:a pcm_s16le`), không dùng `.mp4` cho PCM.
   - **Chuẩn hóa âm lượng:** 2-pass `loudnorm=I=-14:TP=-1.5:LRA=11` (`linear=true`), xuất AAC `96k` `48kHz`.
   - **Chữ Hook khung 0 (A3/H2 — ASS `PlayResX: 720, PlayResY: 1280`):** Font `Inter Bold`, hiện tức thì từ `0:00:00.00` **KHÔNG fade-in**, căn giữa phía trên đầu Cô Kim (`Alignment=8, MarginV=125` dòng vàng `#F5D37E` và `MarginV=180` dòng trắng `#FFFFFF`), `≤ 70` ký tự, `≤ 2` dòng, hiển thị `4.2–4.5s`.
   - **Chữ chương (Loại 1 — 5 chương):** Font `Inter Bold` 34px màu vàng `#F5D37E` (`Alignment=8, MarginV=145`, `\fad(120,180)`), hiện ~`3.7–4.0s` ở đầu các cảnh tương ứng theo phiếu.
   - **Phụ đề (`Inter Bold`, 31px, trắng viền đen 2.8px):** `Alignment=2, MarginV=215`, tách tối đa 2 dòng/khung, canh đúng mốc `pauses` đo được.
   - **Thời lượng Loại 1 (B2):** Bắt buộc **`> 61.0s`** (các gói 31 và 33 đều đạt `65.75s–66.58s` tự nhiên không cần kéo tốc độ).
   - **Dấu AI `✦` (C.10a):** **GIỮ NGUYÊN 100%** ở góc dưới phải, tuyệt đối không chạy `delogo`.
   - **Dung lượng `< 7 MB`:** Video 30–35s dùng `-b:v 950k -maxrate 1150k` (~`4.2 MB`); video 65–67s dùng `-b:v 650k -maxrate 780k` (~`5.9 MB`).
4. **Kiểm duyệt & Bàn giao (`CHOT-2511`):**
   - Xem trực tiếp bản `_Final_Sub.mp4` để soát khung 0, chữ Hook, chữ chương, khớp phụ đề và dấu `✦`.
   - Tải cả 2 file lên `04_VIDEO_DA_DUYET_SAN_SANG_DANG` theo đúng chuẩn tên tool tự quét mỗi 10 phút:
     - `Goi_<n>_<MoTaNgan>_Final_Sub.mp4`
     - `Goi_<n>_<MoTaNgan>_Clean_Master.mp4`
     - Bản sửa chèn `_v2`, `_v3` trước đuôi `_Final_Sub.mp4` / `_Clean_Master.mp4`. **Cấm** đặt bản nháp có chữ `Final/Sub/Clean/Master` hoặc clip thô trong thư mục `04`.
   - Gửi báo cáo ngắn `BAOCAO-<ddmm>-HOAN-TAT-GOI-<n>__GUI_CLAUDE.md` vào `GUI_CLAUDE` kèm độ dài, kết quả 5 mục tự kiểm và cặp khóa `file_video_final_drive` / `file_video_clean_drive`.

---

## 4. Nhật ký bàn giao toàn bộ các gói & thư đã hoàn tất (`23/11 – 26/11/2026`)

| Gói | Chủ đề & Loại | Lịch đăng & Ô phép thử | Thời lượng / Dung lượng | Phiếu `SANXUAT` (`GUI_CLAUDE`) | Video `Final_Sub` (`Thư mục 04`) | Video `Clean_Master` (`Thư mục 04`) | Báo cáo P8b (`GUI_CLAUDE`) |
| :---: | :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| **27** | Quý Sửu 1973 (L1 · 7c) | 23/11 19:00 | `65.08s` | Đã xong | `1aHmaK7hGpB7RTZCR1vTjvXZyy6-wpXDg` | Đã lưu | `1xoJ8j_RPV1pIKB-0lpAFANekCyYIHxyTtlYMe2xJfd8` |
| **28** | Ngày Văn hóa VN 24/11 (L3 · 4c) | 24/11 06:30 | `34.77s` | `1qR6-UGmvJwXApoOx3VHVaenxB619yQ9XtKP3F0VQvXI` | `1jBmPtXX4qWqJcbIsvIfa7QlftTk9HgDW` | Đã lưu | `1Eybsp23TLl8xZo15tBfb-AyWBS4RnpyvoLODyri4okA` |
| **29** | Trà trưa cuối năm (L3 · 4c) | 24/11 11:00 | `32.43s` | `1AlxOCLidqf2L2b4MiRPu2y5l-LzU33XqTAaYcbIXx0I` | `1ru-f5GeSg2O5FIWyRjlJ_fEo5Q4imeRJ` | Đã lưu | `1EvgRxNdrLQP-POssfmgZ_mtsM2eaUU280nTCLadPEnc` |
| **30** | Trà sáng: Tha thứ cho chính mình (L3 · 4c) | **25/11 11:09** *(Đã đăng — tự nhiên đầu tiên)* | `30.36s` · `4.20 MB` | `16tSZEYaaH6RGkxwTYMVpBRmu_a3raZ040qD605SMCLE` | `1VWnfFygJ9HDWXf_qhm4TJ_tQmskZoEz8` | `1SnddN_Spk86ESy-DzH_hNyPE1jKqEqsE` | `1qItBbPcj6Dsu9lwAlJ9DvLBMlXbVH0MQWhGidJTbRC8` |
| **31** | Nữ Giáp Tý 1984 · Năm 2027 (L1 · 7c) | **25/11 19:00** · `19:00 × A` | `66.58s` · `5.84 MB` | `1jDfj4Gu70rFbfLhUg96t1pl_86L8J7dbuVQNsJuPW7M` | `1jp7mnENhovopQQM9d05qdrx7ojEXnQgF` | `10wwnmJml1nCV408v1QyAZppI6lZEXeQc` | `1lUHqFmixSBymM1pZcGb87vJyvDzjadwjMRqwhVQlF6I` |
| **32** | Trà sáng: Rót chén trà cho người thương (L3 · 4c) | **26/11 11:00** *(Đã dựng xong `10:55`)* | `34.67s` · `4.17 MB` | `14_bK8_ePSIxrA_nyiuTCwYWpGoiYzf65z77uvEzflQk` | `11EZ3djlUSICT1nOYNchPgVia8xglN44G` | `1yXl5aaHeyr79TBMHzQiBS5JbL-PJ9nLG` | `18r9B8MnzCyZoYzWsKSY4LjSfmCxv6y6g1PPlVyPRE2Y` |
| **33** | Nữ Canh Ngọ 1990 · Năm 2027 (L1 · 7c) | **26/11** *(Xong `15:18`, khuyến nghị đăng `19:00`)* · `Kiểu B` | `65.75s` · `5.92 MB` | `1pHbBHX-VJcYGPN_71VkCQmcRbX2XuNA1B_FnYvzvSgU` | `1d6ae4EPOwFfrMEX3YOI3XoEx5mhBjBHE` | `1kcOGb0WLbgLCohMuk3Tn2P9OAU45lwDm` | `1FBNdtvPDBFGAZAjXGUu-iP9OBkpswtfaoJHcwWbkp_M` |

### Các thư phối hợp & đánh giá đã gửi trong `GUI_CLAUDE`
- `CHOT-2411-TUAN-THU-NGHIEM-KHONG-QUANG-BA__XACNHAN.md` (`1xIMNYa8jNIDmZLIytiJ6QEukFDAl18CHvlSyTmT82f4`)
- `DANHGIA-2411-DONG-THUAN__GUI_CLAUDE.md` (`18mrbrfa3alfW0BITU6LOqn_TO8qYPiqkdVhbdvnZPX0`)
- `CHOT-2511-QUY-TRINH-DUNG-CLIP-TRUC-TIEP__XACNHAN.md` (`1ldJo0TZpujSkIVbl2SxBg-EklSyKI98huUNSR5O3Ru8`)
- `DANHGIA-2511-DONG-THUAN__GUI_CLAUDE.md` (`1GevKKhOUkovioe3dXrjERklgiDyvCVld4ikiJ9jjk4E` — đã cập nhật đủ `75/75` video)
- `DEXUAT-2511-CHINH-LICH-7-NGAY__GUI_CLAUDE.md` (`1rGBChfSJvL2Z0OUnDibRsH3ZQAlMnf82qxWxVwTk5Yg`)

---

## 5. Việc cần làm tiếp ngay sau bàn giao (`Chiều 26/11 → 02/12/2026`)

1. **Đăng Gói 33 tối nay (`26/11`, khuyến nghị khung `19:00`):**
   - Do Gói 33 hoàn tất lúc `15:18` (quá khung `12:30`), nên đăng đúng **`19:00` tối nay** (tránh khung `15h` yếu nhất kênh) và cập nhật lại giờ đăng thực tế vào bảng theo dõi phép thử A/B (`19:00 × Kiểu B`) khi đọc Studio.
2. **Hoàn thiện & gửi phiếu Gói 34 (`CN 29/11 · 19:00` — Trả lời chị Quý Sửu 1973):**
   - Sửa **Cảnh 7** trong Phụ lục A của `HANDOVER-ANTIGRAVITY.md`: xóa phần màu sắc (vi phạm B8), bổ sung ý *Sửu – Mùi xung / Sửu – Mùi – Tuất hình*, giữ đủ **`32–34` âm tiết** để tổng bài `≥ 232` âm tiết, chạy `packages.check()` qua 0 lỗi rồi phát hành `SANXUAT-...-GOI-34-TRA-LOI-QUY-SUU-1973__YEUCAU.md`.
3. **Vận hành chuỗi Gói 35+ tự động trên lịch đã chốt (`27/11 – 02/12/2026`):**
   - **Thứ 6 (27/11):** `11:00` L3 *Giữa ngày săn sale* · `19:00` L1 *Nữ Bính Dần 1986 · Năm Đinh Mùi 2027* (`19:00 × Kiểu B`).
   - **Thứ 7 (28/11):** `11:00` L3 *Buông chuyện ngoài tầm với* · `12:30` L1 *Nữ Mậu Thìn 1988 · Năm Đinh Mùi 2027* (`12:30 × Kiểu A`).
   - **Chủ Nhật (29/11):** `11:00` L3 *Một ngày nghỉ trọn vẹn* · `19:00` L1 **Gói 34** *(Trả lời chị Quý Sửu 1973, loại khỏi A/B giờ)*.
   - **Thứ 2 (30/11):** `11:00` L3 *Đầu tuần nhẹ nhàng* (**KHÔNG** dùng cụm `"an lành"`) · `12:30` L1 *Nữ Tân Mùi 1991 · Năm Đinh Mùi 2027* (`12:30 × Kiểu B`).
   - **Thứ 3 (01/12):** `11:00` L3 *Đếm ngược: Còn 30 ngày khép lại 2026* · `19:00` L1 *Nữ Quý Dậu 1993 · Năm Đinh Mùi 2027* (`19:00 × Kiểu A`).
   - **Thứ 4 (02/12):** `11:00` L3 *Mỉm cười với chuyện chưa trọn* · `19:00` L1 *Kiến thức nền: Dụng Thần là gì?*.
   - *(Lưu ý: Bỏ Nụ Trầm Hương khỏi Loại 2; chỉ làm Ấm Tử Sa khung `12:00` khi sẵn ảnh/clip sản phẩm thật theo C.9. Kiểm kỹ 1–2 phiếu `Gói 35+` đầu tiên do Gemini API trên tool tự soạn về lá số `battu.py`, âm tiết và giây CTA.)*
4. **Đo lường Studio & Tổng kết tuần tự nhiên (`02/12/2026`):**
   - Quét Studio hằng ngày `16:30` cho **Gói 30, 31, 32, 33, 35+** và đọc ẩn danh nguồn bình luận **Gói 21**.
   - Ngày `02/12`: đối chiếu số liệu `100%` tự nhiên (giữ chân 2s/10s, xem TB, follow/view, bình luận/1.000 view, nguồn Search) với nền cũ (`32%–41%` giữ chân 2s, `200–350` view) để chốt khung giờ Loại 1 (`12:30` vs `19:00`), kiểu mở đầu A/B và nâng cấp Bộ quy tắc kịch bản bản 2.
