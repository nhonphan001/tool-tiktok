#!/usr/bin/env bash
# Sao lưu TikTok Manager trên VPS: DB SQLite (bản chụp nhất quán), .env, secrets/, exports/, cấu hình docker.
# Chạy:  bash scripts/backup.sh            → /root/backups/tiktok-manager-YYYYmmdd-HHMM.tar.gz (giữ 14 bản)
# Tự động mỗi ngày 04:30 giờ VN (21:30 UTC):
#   (crontab -l 2>/dev/null; echo "30 21 * * * cd /root/tool-tiktok && bash scripts/backup.sh >> /root/backups/backup.log 2>&1") | crontab -
# Khôi phục: xem docs/SAO_LUU_VA_KHOI_PHUC.md
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${BACKUP_DIR:-/root/backups}"
KEEP="${BACKUP_KEEP:-14}"
STAMP="$(date +%Y%m%d-%H%M)"
WORK="$(mktemp -d)"
trap 'rm -rf -- "$WORK"' EXIT

mkdir -p "$DEST"
chmod 700 "$DEST"
cd "$APP_DIR"

# 1) Bản chụp DB nhất quán (không cần dừng app): dùng sqlite3 trong container nếu có, nếu không thì Python trên máy
DB_FILE="$(ls data/*.db 2>/dev/null | head -n1 || true)"
mkdir -p "$WORK/data"
if [ -n "$DB_FILE" ]; then
  if docker compose ps --status running 2>/dev/null | grep -q tiktok-manager; then
    docker compose exec -T tiktok-manager python -c "
import sqlite3, sys
src = sqlite3.connect('/app/' + sys.argv[1]); dst = sqlite3.connect('/app/data/.backup_tmp.db')
src.backup(dst); dst.close(); src.close()" "$DB_FILE"
    mv "data/.backup_tmp.db" "$WORK/data/$(basename "$DB_FILE")"
  else
    python3 -c "
import sqlite3, sys
s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" "$DB_FILE" "$WORK/data/$(basename "$DB_FILE")"
  fi
fi

# 2) Cấu hình + bí mật + file xuất (không gồm mã nguồn: mã nằm trên GitHub)
for f in .env docker-compose.yml docker-compose.prod.yml docker-compose.tunnel.yml Caddyfile; do
  [ -f "$f" ] && cp "$f" "$WORK/"
done
[ -d secrets ] && cp -r secrets "$WORK/"
[ -d exports ] && cp -r exports "$WORK/"
git rev-parse HEAD > "$WORK/GIT_COMMIT.txt" 2>/dev/null || true

OUT="$DEST/tiktok-manager-$STAMP.tar.gz"
tar -czf "$OUT" -C "$WORK" .
chmod 600 "$OUT"
echo "$(date '+%F %T') Đã sao lưu: $OUT ($(du -h "$OUT" | cut -f1))"

# 3) Giữ $KEEP bản mới nhất
ls -1t "$DEST"/tiktok-manager-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r old; do
  rm -f -- "$old"
done
