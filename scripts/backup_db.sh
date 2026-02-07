#!/bin/bash

# MongoDB バックアップスクリプト

set -e

# 設定
BACKUP_DIR="/backup"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="stock_data_backup_${DATE}"
MONGO_HOST="mongo"
MONGO_PORT="27017"
MONGO_USERNAME="admin"
MONGO_PASSWORD="${MONGO_PASSWORD:-password}"
DATABASE_NAME="stock_data"
RETENTION_DAYS=7

# バックアップディレクトリを作成
mkdir -p "${BACKUP_DIR}"

echo "Starting backup of database: ${DATABASE_NAME}"
echo "Backup will be saved to: ${BACKUP_DIR}/${BACKUP_NAME}"

# mongodumpを使用してバックアップを作成
docker exec stock-data-service_mongo_1 mongodump \
  --host "${MONGO_HOST}:${MONGO_PORT}" \
  --username "${MONGO_USERNAME}" \
  --password "${MONGO_PASSWORD}" \
  --authenticationDatabase admin \
  --db "${DATABASE_NAME}" \
  --out "/backup/${BACKUP_NAME}"

# バックアップをコンテナからホストにコピー
docker cp stock-data-service_mongo_1:/backup/${BACKUP_NAME} "${BACKUP_DIR}/"

# バックアップを圧縮
cd "${BACKUP_DIR}"
tar -czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
rm -rf "${BACKUP_NAME}"

echo "Backup completed: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# 古いバックアップを削除（保持期間を超えたもの）
echo "Cleaning up old backups (older than ${RETENTION_DAYS} days)"
find "${BACKUP_DIR}" -name "stock_data_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

# バックアップサイズと使用可能領域を表示
BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)
DISK_USAGE=$(df -h "${BACKUP_DIR}" | tail -1 | awk '{print $5 " used, " $4 " available"}')

echo "Backup size: ${BACKUP_SIZE}"
echo "Disk usage: ${DISK_USAGE}"
echo "Backup completed successfully!"

# バックアップの整合性チェック（オプション）
if [ "${CHECK_BACKUP:-false}" = "true" ]; then
    echo "Performing backup integrity check..."
    tar -tzf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" > /dev/null
    echo "Backup integrity check passed!"
fi