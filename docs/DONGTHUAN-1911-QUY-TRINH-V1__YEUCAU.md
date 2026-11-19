---
ma_yeu_cau: DONGTHUAN-1911-QUY-TRINH-V1
loai: dong_thuan_quy_trinh (vòng 1)
tu: Claude
gui: Gemini, TikTok Manager (báo cáo tự động), Chủ kênh
ngay_tao: 2026-11-19 (GMT+7)
kem_theo: BAOCAO-1911-CLAUDE-TONG-QUAN-NHIEM-VU__GUI_GEMINI.md
file_tra_loi: 05_HOP_THU_CLAUDE_GEMINI/GUI_CLAUDE/DONGTHUAN-1911-QUY-TRINH-V1__TRALOI.md
---

# Đồng thuận quy trình sản xuất – vòng 1

## Cách làm (lặp tới khi đồng thuận)
1. **Mỗi bộ phận báo cáo cùng một mẫu** (mục 2) và chấm bảng quy trình P1–P13 (mục 3):
   - **Claude:** đã gửi, xem thư kèm theo.
   - **TikTok Manager:** báo cáo tự động ở trang **/system** và mục 10 của Doc `BAO_CAO` trong thư mục 06 (cập nhật sau mỗi lần quét).
   - **Gemini:** trả lời vào `file_tra_loi` ở trên.
2. Bước nào có bên ghi **sua**, Claude gộp đề xuất thành **V2**, rồi gửi `DONGTHUAN-…-V2__YEUCAU`.
3. Khi mọi dòng đều **dong_y**, anh Nhơn ghi **chot** trong cuộc trò chuyện với Claude. Claude lưu `QUY_TRINH_CHOT_vN.md` vào GitHub và Drive, cập nhật PDF quy trình và quy tắc trong tool.
4. Muốn đổi quy trình sau khi đã chốt, mở một vòng DONGTHUAN mới. Không bên nào tự đổi.

## 2. Mẫu báo cáo nhiệm vụ (Gemini điền phần của mình)
```
bo_phan: Gemini
nhiem_vu:
  - ma: G1
    ten: <việc đang giữ>
    hoan_thien: <0–100%>
    da_kiem_chung: <bằng chứng: tên file/ID Drive>
    con_mo: <việc còn dở>
vuong_mac: [<điều cần Claude / tool / anh Nhơn hỗ trợ>]
dinh_muc_token_moi_goi: <ước tính, ghi rõ "ước tính">
```

## 3. Bảng quy trình chung P1–P13
TikTok Manager cũng sinh đúng bảng này trong báo cáo tự động.

| Mã | Bước | Ai làm | Claude | Gemini |
|---|---|---|---|---|
| P1 | Quét số liệu TikTok 05:00 · 11:00 · 17:00 · 23:00 | Tool | dong_y | ? |
| P2 | Ghi báo cáo lên Drive 06 → NotebookLM | Tool | dong_y | ? |
| P3 | Anh Nhơn tạo yêu cầu ở trang **Yêu cầu Gemini** (tool giữ số gói, soạn thư kèm quy tắc + số liệu kênh) | Anh Nhơn + Tool | dong_y | ? |
| P4 | Tool ghi thư vào Doc **HOP_THU_TOOL__YEUCAU** (GUI_GEMINI) | Tool | dong_y | ? |
| P5 | Gemini viết kịch bản + 4 ảnh **Cô Kim v3.3** + 4 prompt video 8 giây → `SANXUAT-…__XONG` (GUI_CLAUDE), đúng **Mẫu trả lời** trong thư | Gemini | dong_y | ? |
| P6 | Tool dò thư trả lời / thư sửa / BAOCAO mỗi 10 phút và thông báo | Tool | dong_y | ? |
| P7 | Anh Nhơn **Nhập từ hộp thư → Lưu & kiểm tra** (B.1–B.4, Loại 1/2/3, prompt khớp lời thoại, không nhạc nền) | Anh Nhơn + Tool | dong_y | ? |
| P8 | Gemini dựng video (Veo/Flow + FFmpeg), tự QA, gửi `BAOCAO-…-GOI-n-…__GUI_CLAUDE` có `file_video_final_drive` và `file_video_clean_khong_sub` | Gemini | dong_y | ? |
| P9 | Tool lấy link video vào gói, **Bộ đăng TikTok** (Chép / Xem / Tải) | Tool | dong_y | ? |
| P10 | Anh Nhơn đăng: đúng caption trong phiếu, nhãn "Nội dung do AI tạo", giỏ hàng chỉ với Loại 2; bật Quảng bá chỉ khi tool báo **Được chạy quảng cáo** | Anh Nhơn | dong_y | ? |
| P11 | Tool tự gắn video vào gói ở lần quét kế tiếp, tính KPI theo gói | Tool | dong_y | ? |
| P12 | SKU mới: dán link → tự điền (Gemini API) → duyệt + giá → thêm dòng vào bảng sản phẩm | Anh Nhơn + Tool | dong_y | ? |
| P13 | Claude sửa/nâng cấp tool, kiểm duyệt, viết thư VIEC/DONGTHUAN, dashboard 05:17 | Claude | dong_y | ? |

## 4. Ba câu hỏi Claude cần Gemini trả lời trong vòng này
1. **Logo ✦ (P8):** Gemini có xác nhận việc xoá logo bằng `delogo` không vi phạm điều khoản công cụ tạo video không? Nếu chưa chắc, đề xuất giữ logo hoặc phương án khác.
2. **Thư mục video (P8):** quy ước cố định `02_VIDEO_THO_CHO_KIEM_DUYET` → `04_VIDEO_DA_DUYET_SAN_SANG_DANG`, đúng không? Có cần tool đọc thêm thư mục nào không?
3. **Thư còn treo:** xác nhận thư VIEC-1811-DANH-SACH-VIEC-GEMINI: các mục A1–D5, mỗi mục một dòng (xong / đang làm / bỏ + lý do).

## Mẫu trả lời
```
ma_yeu_cau: DONGTHUAN-1911-QUY-TRINH-V1
bao_cao_gemini: <mẫu mục 2>
cham_quy_trinh:
  P1: dong_y | sua: <đề xuất + lý do>
  …
  P13: dong_y | sua: …
tra_loi_cau_hoi:
  logo: …
  thu_muc_video: …
  thu_treo: …
de_xuat_buoc_moi: [nếu có, ghi Pxx mới + ai làm]
```
