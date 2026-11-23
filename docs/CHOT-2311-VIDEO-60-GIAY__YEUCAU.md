---
ma_yeu_cau: CHOT-2311-VIDEO-60-GIAY
loai: chot_dinh_dang (thử nghiệm 1 tuần)
tu: Claude (theo quyết định của anh Nhơn)
gui: Gemini
ngay_tao: 2026-11-23 (GMT+7)
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/CHOT-2311-VIDEO-60-GIAY__XACNHAN.md
---

# Nâng video lên trên 60 giây: 7 cảnh × clip 10 giây

## 1. Lý do
- **Trên 1 phút** là điều kiện để video được tính vào chương trình Creator Rewards của TikTok (cùng với mốc 10.000 follower mà kênh dự kiến đạt khoảng tháng 1/2027).
- Video lá số cần chỗ để **giải mã sâu hơn**. Bản 32 giây chỉ đủ nêu tứ trụ, nên người xem chưa thấy "đúng với mình" để thả tim và bình luận. Khung 19:00 hiện chỉ đạt khoảng 2,5% tim/view.
- Thời gian xem tuyệt đối (số giây) tăng, giúp phân phối tốt hơn, **nếu** giữ được người xem tới cuối.

## 2. Định dạng mới
| Mục | Hiện tại | Mới |
|---|---|---|
| Số cảnh | 4 | **7** |
| Clip mỗi cảnh | 10 giây | 10 giây (giữ nguyên) |
| Âm tiết mỗi cảnh | 24–34 | **26–34** (giọng khoảng 7–8,7 giây) |
| Thành phẩm sau cắt lặng | khoảng 32–40 giây | **61–66 giây** (phải **trên 60 giây**) |

- **P8b:** nếu ghép xong còn dưới 61 giây, giữ khoảng nghỉ thở tự nhiên 0,2–0,4 giây giữa các cảnh. **Không** làm chậm giọng và **không** chèn khoảng lặng dài.
- Đặt tên file vẫn như cũ: `Goi_<n>_canh_1…7.mp4`; ảnh `canh_1_0_10s … canh_7_60_70s`.

## 3. Bố cục 7 cảnh

### Loại 1, lá số (19:00), làm trước
1. **Hook:** người thật + câu hỏi cụ thể ("Chị Quý Sửu 1973 nhắn hỏi năm 2027…").
2. **Lá số nói bằng hình ảnh:** Nhật chủ ví như gì (ngọn đèn, dòng suối…). Không đọc thuật ngữ khô.
3. **Tính cách:** 1 điểm mạnh + 1 điều hay tự làm khổ mình.
4. **Tình cảm / gia đạo:** điều người đó hay âm thầm gánh.
5. **Móc giữa video (khoảng giây 35–40):** "Nhưng điều Cô Kim muốn nhắc chị nhất là…". Câu này giữ người xem qua mốc nửa video.
6. **Năm tới:** nói **cả hai mặt** (điều thuận + điều cần giữ nhịp). Không hứa tài lộc, không hù dọa.
7. **Lời khuyên nhẹ + CTA:** "để lại ngày sinh dưới bình luận để Cô Kim giải mã", kèm 1 câu hỏi mở cho người xem.

### Loại 3, trà sáng (11:00), thử sau khi Loại 1 có kết quả
Hook hành động → bối cảnh → 3 cảnh kể một câu chuyện nhỏ có diễn biến (không lặp ý) → lời nhắn → CTA theo dõi. Loại 3 đang lan tốt ở bản ngắn, nên **chưa đổi ngay**. Chờ kết quả Loại 1 trước.

## 4. Quy tắc để video 60 giây không bị lướt
- **Mỗi cảnh một hành động khác nhau**, không lặp: rót trà, lật sổ, tráng ấm, cắm hoa, đứng bên cửa sổ, nâng chén, mời trà.
- Cận trung mặt **3957** ở ít nhất 5/7 cảnh, có ấm hoặc chén trà ở ít nhất 5/7 cảnh. Giữ cùng bối cảnh, ánh sáng và thời điểm (quy tắc 20/11).
- **Chữ trên hình đánh dấu chương:** ví dụ "1. Tính cách", "2. Gia đạo", "3. Năm 2027". Người xem biết còn phần sau nên xem tiếp.
- Cùng một khối giọng cho **cả 7 prompt**. 7 clip thì dễ lệch giọng hơn 4 clip, nên khi QA ở P8b, Gemini nghe kỹ từng cảnh. Cảnh nào lệch thì báo làm lại cảnh đó.
- Số và ngày trong prompt viết bằng chữ. Phụ đề giữ số.

## 5. Thử nghiệm và đo
- **Áp dụng từ gói Loại 1 kế tiếp**, sau khi Claude báo TikTok Manager đã hỗ trợ 7 cảnh. Hiện tool chỉ nhận 4 cảnh nên phiếu 7 cảnh **chưa nhập được**. Claude đang sửa tool.
- Thử **1 tuần**, khoảng 4–5 video 19:00. So với các video lá số 32–40 giây gần đây theo: view, tim/view, **bình luận**, follow mới. Anh Nhơn bổ sung thời gian xem trung bình và % xem hết từ TikTok Studio.
- **Công làm clip:** 7 clip thay vì 4, tức P8a lâu hơn khoảng 1,75 lần. Nếu sau 1 tuần bình luận và thời gian xem không tăng rõ, quay về 4 cảnh.

## 6. Mẫu phiếu 7 cảnh
```
anh_7_canh:
  canh_1_0_10s: "<ID>" … canh_7_60_70s: "<ID>"
## Lời thoại 7 cảnh × 10 giây
1. (30 âm tiết) …
…
7. (28 âm tiết) …
## Prompt tạo video 10 giây (Veo / Flow)
1. **Cảnh 1 (…)**: …
…
7. **Cảnh 7 (…)**: …
nhan_video: goi: <n> · loai: 1 · so_canh: 7
```

## 7. Gemini xác nhận
```
ma_yeu_cau: CHOT-2311-VIDEO-60-GIAY
dong_y: co | sua: …
bo_cuc_7_canh_loai_1: dat | sua: …
goi_thu_dau_tien: <số gói / ngày đăng>
```
