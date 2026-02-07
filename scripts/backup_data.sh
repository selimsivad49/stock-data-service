#!/bin/bash

# =============================================================================
# Stock Data Service - データバックアップスクリプト (Linux/macOS用)
# MongoDBのデータをエクスポートする (定期バックアップ・システム移行兼用)
# =============================================================================

set -euo pipefail

# ----- 設定 -----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_BASE_DIR="${PROJECT_DIR}/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="stock_data_migration_${DATE}"
MONGO_USERNAME="${MONGO_USERNAME:-admin}"
MONGO_PASSWORD="${MONGO_PASSWORD:-password}"
DATABASE_NAME="${DATABASE_NAME:-stock_data}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# バックアップ対象コレクション
# all: 全コレクション, data: 株価データのみ(users/api_keysを除外)
BACKUP_MODE="${1:-all}"

# ----- 関数 -----
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error_exit() {
    log "ERROR: $1"
    exit 1
}

cleanup() {
    if [ -n "${TEMP_DIR:-}" ] && [ -d "${TEMP_DIR}" ]; then
        rm -rf "${TEMP_DIR}"
    fi
}

trap cleanup EXIT

usage() {
    echo "Usage: $0 [all|data]"
    echo ""
    echo "  all   - 全コレクションをバックアップ (デフォルト)"
    echo "          (users, api_keys, daily_prices, stock_info, financials)"
    echo "  data  - 株価データのみバックアップ (users, api_keysを除外)"
    echo "          (daily_prices, stock_info, financials)"
    echo ""
    echo "Examples:"
    echo "  $0          # 全データをバックアップ"
    echo "  $0 all      # 全データをバックアップ"
    echo "  $0 data     # 株価データのみバックアップ"
    echo ""
    echo "Environment variables:"
    echo "  MONGO_USERNAME   - MongoDB username (default: admin)"
    echo "  MONGO_PASSWORD   - MongoDB password (default: password)"
    echo "  DATABASE_NAME    - Database name (default: stock_data)"
    echo "  RETENTION_DAYS   - 古いバックアップの保持日数 (default: 30, 0で無効)"
    echo "  CHECK_BACKUP     - 整合性チェックを実行 (true/false, default: false)"
    exit 0
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
fi

# ----- docker compose コマンドの検出 -----
detect_compose_cmd() {
    if docker compose version &>/dev/null; then
        echo "docker compose"
    elif docker-compose --version &>/dev/null; then
        echo "docker-compose"
    else
        error_exit "docker compose が見つかりません。Docker Composeをインストールしてください。"
    fi
}

COMPOSE_CMD=$(detect_compose_cmd)

# ----- メイン処理 -----
log "=== Stock Data Service データバックアップ ==="
log "バックアップモード: ${BACKUP_MODE}"
log "データベース: ${DATABASE_NAME}"

# バックアップモードのバリデーション
if [ "${BACKUP_MODE}" != "all" ] && [ "${BACKUP_MODE}" != "data" ]; then
    error_exit "無効なバックアップモード: ${BACKUP_MODE} (all または data を指定してください)"
fi

# MongoDBコンテナの起動確認
cd "${PROJECT_DIR}"
log "MongoDBコンテナの状態を確認中..."
if ! ${COMPOSE_CMD} exec -T mongo mongosh --eval "db.adminCommand('ping')" --quiet &>/dev/null; then
    error_exit "MongoDBコンテナが起動していません。先に 'docker compose up -d mongo' を実行してください。"
fi

# バックアップディレクトリを作成
mkdir -p "${BACKUP_BASE_DIR}"
TEMP_DIR=$(mktemp -d)
DUMP_DIR="${TEMP_DIR}/${BACKUP_NAME}"
mkdir -p "${DUMP_DIR}"

log "一時ディレクトリ: ${TEMP_DIR}"

# コレクションの選定
if [ "${BACKUP_MODE}" = "data" ]; then
    COLLECTIONS=("daily_prices" "stock_info" "financials")
    log "対象コレクション: daily_prices, stock_info, financials"
else
    COLLECTIONS=("users" "api_keys" "daily_prices" "stock_info" "financials")
    log "対象コレクション: users, api_keys, daily_prices, stock_info, financials"
fi

# コンテナ内でmongodumpを実行
log "MongoDBからデータをエクスポート中..."

COLLECTION_ARGS=""
for col in "${COLLECTIONS[@]}"; do
    COLLECTION_ARGS="${COLLECTION_ARGS} --collection=${col}"
done

# コンテナ内の一時ディレクトリをクリーンアップ
${COMPOSE_CMD} exec -T mongo rm -rf /tmp/migration_backup

# 各コレクションをダンプ
for col in "${COLLECTIONS[@]}"; do
    log "  エクスポート中: ${col}"
    ${COMPOSE_CMD} exec -T mongo mongodump \
        --username="${MONGO_USERNAME}" \
        --password="${MONGO_PASSWORD}" \
        --authenticationDatabase=admin \
        --db="${DATABASE_NAME}" \
        --collection="${col}" \
        --out="/tmp/migration_backup" \
        --quiet
done

# コンテナからホストにコピー
log "バックアップデータをコンテナからコピー中..."
CONTAINER_ID=$(${COMPOSE_CMD} ps -q mongo)
docker cp "${CONTAINER_ID}:/tmp/migration_backup/${DATABASE_NAME}" "${DUMP_DIR}/"

# コンテナ内の一時ファイルをクリーンアップ
${COMPOSE_CMD} exec -T mongo rm -rf /tmp/migration_backup

# メタデータファイルを作成
cat > "${DUMP_DIR}/backup_metadata.json" <<METAEOF
{
    "backup_date": "$(date -Iseconds)",
    "backup_mode": "${BACKUP_MODE}",
    "database_name": "${DATABASE_NAME}",
    "collections": [$(printf '"%s",' "${COLLECTIONS[@]}" | sed 's/,$//')]
}
METAEOF

# 各コレクションのドキュメント数を記録
log "コレクション統計情報を取得中..."
for col in "${COLLECTIONS[@]}"; do
    COUNT=$(${COMPOSE_CMD} exec -T mongo mongosh \
        --username="${MONGO_USERNAME}" \
        --password="${MONGO_PASSWORD}" \
        --authenticationDatabase=admin \
        --quiet \
        --eval "db.getSiblingDB('${DATABASE_NAME}').${col}.countDocuments({})")
    log "  ${col}: ${COUNT} documents"
done

# tar.gzに圧縮
log "バックアップを圧縮中..."
BACKUP_FILE="${BACKUP_BASE_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "${BACKUP_FILE}" -C "${TEMP_DIR}" "${BACKUP_NAME}"

# バックアップサイズ
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)

# バックアップの整合性チェック
if [ "${CHECK_BACKUP:-false}" = "true" ]; then
    log "バックアップの整合性チェック中..."
    tar -tzf "${BACKUP_FILE}" > /dev/null
    log "整合性チェック: OK"
fi

# 古いバックアップを削除（保持期間を超えたもの）
if [ "${RETENTION_DAYS}" -gt 0 ]; then
    OLD_COUNT=$(find "${BACKUP_BASE_DIR}" -name "stock_data_migration_*.tar.gz" -mtime +${RETENTION_DAYS} 2>/dev/null | wc -l)
    if [ "${OLD_COUNT}" -gt 0 ]; then
        log "古いバックアップを削除中 (${RETENTION_DAYS}日以上前: ${OLD_COUNT}件)..."
        find "${BACKUP_BASE_DIR}" -name "stock_data_migration_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
    fi
fi

# ディスク使用量
DISK_USAGE=$(df -h "${BACKUP_BASE_DIR}" | tail -1 | awk '{print $5 " used, " $4 " available"}')

log "=== バックアップ完了 ==="
log "出力ファイル: ${BACKUP_FILE}"
log "ファイルサイズ: ${BACKUP_SIZE}"
log "ディスク使用量: ${DISK_USAGE}"
log ""
log "リストア方法:"
log "  ./scripts/restore_data.sh ${BACKUP_NAME}.tar.gz"
