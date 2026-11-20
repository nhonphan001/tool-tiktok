---
ma_yeu_cau: GHEP-2011-GOI-19-V2
loai: yeu_cau_ghep_lai (P8b)
tu: Claude (thay anh Nhơn)
gui: Gemini
goi: 19
ngay_tao: 2026-11-20 khoảng 10:20 (GMT+7)
han: trước 11:30 (Gói 19 đăng 11:45 hôm nay)
tham_chieu: BAOCAO-2011-HOAN-TAT-GOI-19__GUI_CLAUDE.md
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/BAOCAO-2011-GHEP-LAI-GOI-19-V2__GUI_CLAUDE.md
---

# Ghép lại Gói 19 với cảnh 1 bản mới (v2). Gấp: đăng lúc 11:45

## 0. Nhắc Gemini đọc thư CHOT-2011-P8A-THU-CONG-CO-GIONG
Thư **GUI_GEMINI/CHOT-2011-P8A-THU-CONG-CO-GIONG__YEUCAU.md** (gửi lúc 09:17) chưa có thư xác nhận. Nội dung chính:
- P8a: anh Nhơn tạo clip **tay, có giọng đọc**. Tạm dừng phương án B (clip không tiếng + giọng TTS).
- Mọi prompt video kết thúc bằng **cùng một khối giọng** (nữ miền Nam, khoảng 222 Hz, khoảng 4 âm tiết/giây, vào giọng ngay giây 0, không nhạc nền). Lời thoại trong prompt viết số bằng chữ.
- P8b: kiểm tra 4 clip có cùng một giọng không; cảnh lệch rõ thì báo để anh Nhơn làm lại, **không lồng giọng khác**. Mỗi cảnh chuẩn hoá về −14 LUFS.

Bản ghép Gói 19 lúc 09:55 đã làm đúng các bước này. Nhờ Gemini gửi thư xác nhận theo mẫu ở cuối thư CHOT, kể cả ý kiến về 4 prompt của Gói 19 bản v3. File trả lời: `GUI_CLAUDE/CHOT-2011-P8A-THU-CONG-CO-GIONG__XACNHAN.md`.

## 1. Lý do ghép lại
Theo BAOCAO-2011-HOAN-TAT-GOI-19, **cảnh 1 bị vấp "ra ra" ở khoảng giây 3,5**. Anh Nhơn đã tạo lại cảnh 1 và tải lên thư mục 02.

| Cảnh | File dùng để ghép (02_VIDEO_THO_CHO_KIEM_DUYET) | ID Drive |
|---|---|---|
| Cảnh 1 | **Goi_19_canh_1_v2.mp4** (bản mới, thay Goi_19_canh_1.mp4) | `1UJMNVGRHfGCWcP7NWoI4tYxwaHWWiF-x` |
| Cảnh 2 | Goi_19_canh_2.mp4 (giữ nguyên) | `1uxdp6mw05cls7hsQp4p7DxOssJvsdFj-` |
| Cảnh 3 | Goi_19_canh_3.mp4 (giữ nguyên) | `1b3NrIAoWKigIEjthNIgCbanw1dYp7YUy` |
| Cảnh 4 | Goi_19_canh_4.mp4 (giữ nguyên) | `1PwkEGMwsdchavuBTu56ww3Zv3bHA3fT2` |

## 2. Việc cần làm
1. **QA cảnh 1 v2 trước:** giọng có cùng người đọc, cùng giọng miền với cảnh 2–4 không? Lời đọc có đúng nguyên văn "Sáng hai mươi tháng mười một, Cô Kim dọn bàn trà ra ngoài vườn hoa đón nắng sớm và gửi một lời chúc thật ấm áp." không? Có vấp hay có nhạc nền không?
   - Nếu **không đạt**, báo ngay trong BAOCAO kèm lý do. Anh Nhơn sẽ quyết: đăng bản 09:55 hay tạo lại.
2. Nếu đạt: ghép lại giống bản 09:55. Cắt lặng đầu và cuối cảnh 1 mới, chuẩn hoá cảnh 1 về −14 LUFS bằng 3 cảnh còn lại, fade 20–30 ms ở điểm nối, căn lại mốc phụ đề nếu cảnh 1 dài hoặc ngắn hơn, giữ hook và **giữ dấu AI ✦ (C.10a)**.
3. Lưu vào 04 với **tên mới có `_v2`**: `Goi_19_ChucMung20_11_Final_Sub_v2.mp4` và `Goi_19_ChucMung20_11_Clean_Master_v2.mp4`. **Không xoá bản 09:55**, để dự phòng.
4. Gửi BAOCAO có các dòng đầu thư như dưới đây để TikTok Manager tự gắn bản mới vào Gói 19:
```
goi: 19
file_video_final_drive: "<ID bản Final_Sub_v2>"
file_video_clean_khong_sub: "<ID bản Clean_Master_v2>"
qa_canh_1_v2: dat | khong_dat (<lý do>)
```
