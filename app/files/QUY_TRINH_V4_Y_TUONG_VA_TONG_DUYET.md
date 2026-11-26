# Quy trình Vận hành V4 — Đầu vào Ý tưởng & Kiểm toán Tổng duyệt Đầu cuối

- **Ngày hiệu lực:** 27/11/2026
- **Mục tiêu:** Giải phóng anh Nhơn khỏi việc tự soi từng khâu trung gian; anh Nhơn chỉ làm đúng **2 điểm chốt của chủ kênh**:
  1. **Đầu vào (`/y-tuong`):** Xem lô 5–7 ý tưởng đã chấm điểm & chống trùng → bấm **✓ Duyệt → Tạo Gói SX**.
  2. **Đầu cuối (`/tong-duyet`):** Xem duy nhất **1 trang đèn Xanh / Vàng / Đỏ** trong 3 phút mỗi sáng (~06:30) → bấm **✓ Ký duyệt bản tin hôm nay**.

---

## 1. Bản đồ 8 Bộ phận (V4)

| Khối | Bộ phận | Phụ trách | Module / Trang |
|---|---|---|---|
| **ĐẦU VÀO** | **1. Bộ phận Ý tưởng & Biên tập** | `app/ideation.py` + **An (Antigravity)** | `/y-tuong`, `POST /api/public/studio/ideas` |
| **SẢN XUẤT** | **2. Chiến lược & Kịch bản AI** | **Google AI Studio (Gemini API)** | `/strategy`, `/requests`, `app/script_ai.py` |
| **SẢN XUẤT** | **3. Lõi Bát Tự & Tuân thủ V2** | **TikTok Manager** | `app/battu.py`, `app/compliance.py`, `app/packages.py` |
| **SẢN XUẤT** | **4. Dựng video & Thành phẩm** | **Gemini + Veo + Drive `04`** | `/packages`, `app/finals.py`, `app/veo.py` |
| **ĐO LƯỜNG** | **5. Tầng 1 · Display API (24/7)** | **VPS APScheduler** (4 lần/ngày, 0 token) | `app/tiktok.py`, `app/scanner.py` |
| **ĐO LƯỜNG** | **6. Tầng 2/3 · Studio + Quảng bá + Bình luận** | **An (Antigravity)** (chỉ đọc 100%) | `/danh-gia`, `/binh-luan`, `/dong-thuan`, `/api/public/studio/*` |
| **CHĂM SÓC** | **7. Khách hàng & Mẫu trả lời nhanh** | **TikTok Manager** (0 token + AI) | `/khach-hang`, `/laso`, `app/customers.py` |
| **ĐẦU CUỐI** | **8. Bộ phận Kiểm toán Quy trình & Tối ưu (QA/Ops)** | `app/process_audit.py` + **An (Antigravity)** | `/tong-duyet`, `GET/POST /api/public/studio/audit` |

---

## 2. Nhịp vận hành chuẩn đã chốt (27/11/2026)

1. **Tự động 24/7 trên VPS (0 token):** Display API quét `05:00, 11:00, 17:00, 23:00` + kiểm hộp thư Drive mỗi 10 phút.
2. **Mỗi sáng `~06:00 → 06:30` (An chạy Tầng 2 + Kiểm toán):**
   - Quét nhanh bình luận mới `tiktokstudio/comment` → `/binh-luan`.
   - Quét chi tiết Studio **chỉ cho video mới 24–48 giờ** + xác nhận nhanh Promote → `/danh-gia` & gửi **Báo cáo đồng thuận**.
   - Chạy kiểm toán 6 chốt (Display API · Nhịp Studio · QA Kịch bản & chống trùng · BL xin lá số chưa TL · Hộp thư chờ duyệt · Chi phí AI) → nộp **Bản tin Tổng duyệt** lên `/tong-duyet`.
   - **Anh Nhơn (06:30 — 3 phút):** Mở duy nhất `/tong-duyet` → xem mục Đỏ/Vàng (nếu có) + Duyệt ý tưởng + bấm **✓ Ký duyệt**.
3. **Sáng Thứ Hai hằng tuần (An chạy Tầng 3 + Lô Ý tưởng tuần mới):**
   - Tổng hợp sâu 7 ngày tự nhiên, nguồn lưu lượng & từ khoá, nhân khẩu học tự nhiên, top Can Chi từ `/binh-luan`.
   - Cập nhật Báo cáo đồng thuận tuần → sinh **Lô 5–7 Ý tưởng tuần mới** trên `/y-tuong` để anh Nhơn chọn 1 lần cho cả tuần.
