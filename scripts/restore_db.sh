#!/bin/bash

# MongoDB リストアスクリプト

set -e

# 設定
BACKUP_DIR="/backup"
MONGO_HOST="mongo"
MONGO_PORT="27017"
MONGO_USERNAME="admin"
MONGO_PASSWORD="${MONGO_PASSWORD:-password}"
DATABASE_NAME="stock_data"

# 使用方法を表示する関数
usage() {
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Example:"
    echo "  $0 stock_data_backup_20241201_120000.tar.gz"
    echo ""
    echo "Available backups:"
    ls -la "${BACKUP_DIR}"/stock_data_backup_*.tar.gz 2>/dev/null || echo "No backups found"
    exit 1
}

# 引数チェック
if [ $# -ne 1 ]; then
    usage
fi

BACKUP_FILE="$1"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

# バックアップファイルの存在チェック
if [ ! -f "${BACKUP_PATH}" ]; then
    echo "Error: Backup file not found: ${BACKUP_PATH}"
    usage
fi

echo "Starting restore from backup: ${BACKUP_FILE}"
echo "Target database: ${DATABASE_NAME}"

# 確認プロンプト
read -p "This will replace the existing database. Are you sure? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 1
fi

# 一時ディレクトリを作成
TEMP_DIR=$(mktemp -d)
echo "Extracting backup to temporary directory: ${TEMP_DIR}"

# バックアップを展開
tar -xzf "${BACKUP_PATH}" -C "${TEMP_DIR}"

# 展開されたディレクトリを探す
EXTRACTED_DIR=$(find "${TEMP_DIR}" -name "stock_data_backup_*" -type d | head -1)

if [ -z "${EXTRACTED_DIR}" ]; then
    echo "Error: Could not find extracted backup directory"
    rm -rf "${TEMP_DIR}"
    exit 1
fi

echo "Found backup directory: ${EXTRACTED_DIR}"

# データベースをドロップ（既存データを削除）
echo "Dropping existing database: ${DATABASE_NAME}"
docker exec stock-data-service_mongo_1 mongosh \
  --host "${MONGO_HOST}:${MONGO_PORT}" \
  --username "${MONGO_USERNAME}" \
  --password "${MONGO_PASSWORD}" \
  --authenticationDatabase admin \
  --eval "db.getSiblingDB('${DATABASE_NAME}').dropDatabase()"

# バックアップを MongoDB コンテナにコピー
echo "Copying backup to MongoDB container..."
docker cp "${EXTRACTED_DIR}" stock-data-service_mongo_1:/tmp/restore/

# mongorestoreを使用してデータを復元
echo "Restoring database from backup..."
docker exec stock-data-service_mongo_1 mongorestore \
  --host "${MONGO_HOST}:${MONGO_PORT}" \
  --username "${MONGO_USERNAME}" \
  --password "${MONGO_PASSWORD}" \
  --authenticationDatabase admin \
  --db "${DATABASE_NAME}" \
  "/tmp/restore/$(basename "${EXTRACTED_DIR}")/${DATABASE_NAME}"

# 一時ファイルをクリーンアップ
echo "Cleaning up temporary files..."
docker exec stock-data-service_mongo_1 rm -rf /tmp/restore
rm -rf "${TEMP_DIR}"

# 復元確認
echo "Verifying restore..."
COLLECTION_COUNT=$(docker exec stock-data-service_mongo_1 mongosh \
  --host "${MONGO_HOST}:${MONGO_PORT}" \
  --username "${MONGO_USERNAME}" \
  --password "${MONGO_PASSWORD}" \
  --authenticationDatabase admin \
  --quiet \
  --eval "db.getSiblingDB('${DATABASE_NAME}').getCollectionNames().length")

echo "Database restored successfully!"
echo "Number of collections: ${COLLECTION_COUNT}"

# インデックスを再作成
echo "Recreating indexes..."
docker exec stock-data-service_mongo_1 mongosh \
  --host "${MONGO_HOST}:${MONGO_PORT}" \
  --username "${MONGO_USERNAME}" \
  --password "${MONGO_PASSWORD}" \
  --authenticationDatabase admin \
  "/docker-entrypoint-initdb.d/mongo-init.js"

echo "Restore completed successfully!"