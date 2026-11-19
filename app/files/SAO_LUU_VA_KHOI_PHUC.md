# Sao lưu và khôi phục toàn hệ thống TikTok Manager

## 1. Hệ thống gồm những gì, lưu ở đâu

| Thành phần | Nơi lưu chính | Bản sao lưu |
|---|---|---|
| **Mã nguồn + tài liệu** (app, tests, docs, scripts) | GitHub `nhonphan001/tool-tiktok`, nhánh `claude/elegant-tesla-xcj8h4` | File `git bundle` trong Drive `07_SAO_LUU_HE_THONG` (đủ lịch sử commit, khôi phục được kể cả khi mất GitHub) |
| **Dữ liệu tool** (SQLite: tài khoản, số liệu quét, video, gói, yêu cầu Gemini, cài đặt) | VPS `/root/tool-tiktok/data/` | `scripts/backup.sh` → `/root/backups/tiktok-manager-*.tar.gz` (giữ 14 bản) |
| **Bí mật** (`.env`, `secrets/service-account.json`) | VPS | Nằm trong cùng file `.tar.gz` (quyền 600). **Không** đưa lên Drive hay GitHub |
| **Hộp thư, ảnh, video, báo cáo** | Google Drive (thư mục 01–06) | Drive tự lưu phiên bản; tool không xoá file nào |
| **Bảng sản phẩm** | Google Sheets | Lịch sử phiên bản của Sheets (Tệp → Lịch sử phiên bản) |
| **Cuộc trò chuyện với Claude** | Phiên Claude Code | `CUOC_TRO_CHUYEN_CLAUDE_TIKTOK_MANAGER_<ngày>.md` trong Drive `07_SAO_LUU_HE_THONG` (đã che token, khoá, email) |
| **PDF quy trình, báo cáo Claude, thư DONGTHUAN** | `docs/` trong GitHub | Có trong `git bundle` và trong Drive 07 |

## 2. Sao lưu VPS (làm 1 lần, sau đó tự động)

Chạy tay một lần để kiểm tra:
```bash
cd /root/tool-tiktok && git pull && bash scripts/backup.sh
```

Bật lịch tự sao lưu mỗi ngày lúc 04:30 giờ Việt Nam:
```bash
(crontab -l 2>/dev/null; echo "30 21 * * * cd /root/tool-tiktok && bash scripts/backup.sh >> /root/backups/backup.log 2>&1") | crontab -
```

Tải bản mới nhất về máy tính cá nhân (chạy **trên máy tính**, không phải trên VPS):
```bash
scp "root@135.125.75.93:/root/backups/$(ssh root@135.125.75.93 'ls -1t /root/backups/*.tar.gz | head -n1 | xargs basename')" .
```

## 3. Khôi phục

### 3.1 Khôi phục trên VPS mới hoặc VPS hỏng
```bash
git clone https://github.com/nhonphan001/tool-tiktok.git /root/tool-tiktok
```
```bash
cd /root/tool-tiktok && git checkout claude/elegant-tesla-xcj8h4
```
```bash
tar -xzf /root/backups/tiktok-manager-YYYYmmdd-HHMM.tar.gz -C /root/tool-tiktok
```
```bash
cd /root/tool-tiktok && docker compose -f docker-compose.yml -f docker-compose.tunnel.yml up -d --build
```
Kiểm tra: mở trang web, vào **☰ → Báo cáo → Tình trạng hệ thống**, các dòng P1–P12 phải hiện ✅ hoặc ⚠️.

### 3.2 Khôi phục mã nguồn khi mất GitHub
Tải file `tool-tiktok-*.bundle` từ Drive `07_SAO_LUU_HE_THONG`, rồi:
```bash
git clone tool-tiktok-YYYYmmdd.bundle tool-tiktok
```

### 3.3 Chỉ khôi phục dữ liệu (DB) về một ngày cũ
```bash
cd /root/tool-tiktok && docker compose stop
```
```bash
mkdir -p /root/restore && tar -xzf /root/backups/tiktok-manager-YYYYmmdd-HHMM.tar.gz -C /root/restore
```
```bash
cp /root/restore/data/*.db /root/tool-tiktok/data/ && cd /root/tool-tiktok && docker compose up -d
```

## 4. Không bao giờ
- Đưa `.env` hoặc `service-account.json` lên Drive, GitHub hay chat.
- Xoá thư trong hộp thư 05. Tool chỉ đọc; Gemini và Claude chỉ thêm thư mới.
