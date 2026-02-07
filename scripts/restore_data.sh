#!/bin/bash

# =============================================================================
# Stock Data Service - データリストアスクリプト (Linux/macOS用)
# バックアップからMongoDBにデータを復元する (システム移行用)
# =============================================================================

set -euo pipefail

# ----- 設定 -----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_BASE_DIR="${PROJECT_DIR}/backups"
MONGO_USERNAME="${MONGO_USERNAME:-admin}"
MONGO_PASSWORD="${MONGO_PASSWORD:-password}"
DATABASE_NAME="${DATABASE_NAME:-stock_data}"

# リストアモード: merge(既存データに追加) / replace(既存データを削除して復元)
RESTORE_MODE="${2:-merge}"

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
    # コンテナ内の一時ファイルをクリーンアップ
    cd "${PROJECT_DIR}"
    ${COMPOSE_CMD} exec -T mongo rm -rf /tmp/migration_restore 2>/dev/null || true
}

trap cleanup EXIT

usage() {
    echo "Usage: $0 <backup_file> [merge|replace]"
    echo ""
    echo "  backup_file - バックアップファイル名 (backups/ 内のtar.gzファイル)"
    echo "  merge       - 既存データに追加/更新 (デフォルト、重複キーはスキップ)"
    echo "  replace     - 対象コレクションを削除してから復元"
    echo ""
    echo "Examples:"
    echo "  $0 stock_data_migration_20250101_120000.tar.gz"
    echo "  $0 stock_data_migration_20250101_120000.tar.gz merge"
    echo "  $0 stock_data_migration_20250101_120000.tar.gz replace"
    echo ""
    echo "Available backups:"
    ls -lh "${BACKUP_BASE_DIR}"/stock_data_migration_*.tar.gz 2>/dev/null || echo "  バックアップが見つかりません"
    echo ""
    echo "Environment variables:"
    echo "  MONGO_USERNAME  - MongoDB username (default: admin)"
    echo "  MONGO_PASSWORD  - MongoDB password (default: password)"
    echo "  DATABASE_NAME   - Database name (default: stock_data)"
    exit 0
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ] || [ $# -lt 1 ]; then
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

# ----- 引数の処理 -----
BACKUP_FILE="$1"

# バックアップファイルのパスを解決
if [ -f "${BACKUP_FILE}" ]; then
    BACKUP_PATH="${BACKUP_FILE}"
elif [ -f "${BACKUP_BASE_DIR}/${BACKUP_FILE}" ]; then
    BACKUP_PATH="${BACKUP_BASE_DIR}/${BACKUP_FILE}"
else
    error_exit "バックアップファイルが見つかりません: ${BACKUP_FILE}"
fi

# リストアモードのバリデーション
if [ "${RESTORE_MODE}" != "merge" ] && [ "${RESTORE_MODE}" != "replace" ]; then
    error_exit "無効なリストアモード: ${RESTORE_MODE} (merge または replace を指定してください)"
fi

# ----- メイン処理 -----
log "=== Stock Data Service データリストア ==="
log "バックアップファイル: ${BACKUP_PATH}"
log "リストアモード: ${RESTORE_MODE}"
log "データベース: ${DATABASE_NAME}"

# 確認プロンプト
if [ "${RESTORE_MODE}" = "replace" ]; then
    echo ""
    echo "WARNING: replaceモードでは対象コレクションの既存データが全て削除されます。"
    read -p "続行しますか? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log "リストアを中止しました。"
        exit 0
    fi
fi

# MongoDBコンテナの起動確認
cd "${PROJECT_DIR}"
log "MongoDBコンテナの状態を確認中..."
if ! ${COMPOSE_CMD} exec -T mongo mongosh --eval "db.adminCommand('ping')" --quiet &>/dev/null; then
    error_exit "MongoDBコンテナが起動していません。先に 'docker compose up -d mongo' を実行してください。"
fi

# バックアップを展開
TEMP_DIR=$(mktemp -d)
log "バックアップを展開中: ${TEMP_DIR}"
tar -xzf "${BACKUP_PATH}" -C "${TEMP_DIR}"

# 展開されたディレクトリを探す
EXTRACTED_DIR=$(find "${TEMP_DIR}" -name "stock_data_migration_*" -type d -maxdepth 1 | head -1)
if [ -z "${EXTRACTED_DIR}" ]; then
    error_exit "バックアップの展開に失敗しました。正しいバックアップファイルか確認してください。"
fi

# メタデータを表示
if [ -f "${EXTRACTED_DIR}/backup_metadata.json" ]; then
    log "バックアップ情報:"
    cat "${EXTRACTED_DIR}/backup_metadata.json"
    echo ""
fi

# BSONデータのディレクトリを確認
BSON_DIR="${EXTRACTED_DIR}/${DATABASE_NAME}"
if [ ! -d "${BSON_DIR}" ]; then
    # DATABASE_NAMEと異なる名前でダンプされている場合
    BSON_DIR=$(find "${EXTRACTED_DIR}" -name "*.bson" -exec dirname {} \; | head -1)
    if [ -z "${BSON_DIR}" ]; then
        error_exit "バックアップ内にBSONデータが見つかりません。"
    fi
fi

log "BSONデータ: ${BSON_DIR}"

# リストア対象コレクションを特定
COLLECTIONS=()
for bson_file in "${BSON_DIR}"/*.bson; do
    if [ -f "${bson_file}" ]; then
        col_name=$(basename "${bson_file}" .bson)
        COLLECTIONS+=("${col_name}")
    fi
done

if [ ${#COLLECTIONS[@]} -eq 0 ]; then
    error_exit "リストア対象のコレクションが見つかりません。"
fi

log "リストア対象コレクション: ${COLLECTIONS[*]}"

# replaceモードの場合、対象コレクションを削除
if [ "${RESTORE_MODE}" = "replace" ]; then
    log "既存コレクションを削除中..."
    for col in "${COLLECTIONS[@]}"; do
        log "  削除中: ${col}"
        ${COMPOSE_CMD} exec -T mongo mongosh \
            --username="${MONGO_USERNAME}" \
            --password="${MONGO_PASSWORD}" \
            --authenticationDatabase=admin \
            --quiet \
            --eval "db.getSiblingDB('${DATABASE_NAME}').${col}.drop()"
    done
fi

# BSONデータをコンテナにコピー
log "データをMongoDBコンテナにコピー中..."
CONTAINER_ID=$(${COMPOSE_CMD} ps -q mongo)
${COMPOSE_CMD} exec -T mongo rm -rf /tmp/migration_restore
docker cp "${BSON_DIR}" "${CONTAINER_ID}:/tmp/migration_restore"

# mongorestoreを実行
log "データを復元中..."
RESTORE_OPTS=""
if [ "${RESTORE_MODE}" = "merge" ]; then
    # mergeモード: 重複キーはスキップ (既存データを保持)
    RESTORE_OPTS="--drop=false"
fi

for col in "${COLLECTIONS[@]}"; do
    log "  復元中: ${col}"
    if [ "${RESTORE_MODE}" = "merge" ]; then
        # mergeモードでは重複エラーを無視
        ${COMPOSE_CMD} exec -T mongo mongorestore \
            --username="${MONGO_USERNAME}" \
            --password="${MONGO_PASSWORD}" \
            --authenticationDatabase=admin \
            --db="${DATABASE_NAME}" \
            --collection="${col}" \
            --noIndexRestore \
            "/tmp/migration_restore/${col}.bson" \
            2>&1 || log "  (${col}: 一部の重複ドキュメントはスキップされました)"
    else
        ${COMPOSE_CMD} exec -T mongo mongorestore \
            --username="${MONGO_USERNAME}" \
            --password="${MONGO_PASSWORD}" \
            --authenticationDatabase=admin \
            --db="${DATABASE_NAME}" \
            --collection="${col}" \
            --noIndexRestore \
            "/tmp/migration_restore/${col}.bson"
    fi
done

# インデックスを再作成
log "インデックスを再作成中..."
${COMPOSE_CMD} exec -T mongo mongosh \
    --username="${MONGO_USERNAME}" \
    --password="${MONGO_PASSWORD}" \
    --authenticationDatabase=admin \
    /docker-entrypoint-initdb.d/mongo-init.js 2>/dev/null || log "(インデックス作成: 一部は既に存在するためスキップ)"

# 復元結果の確認
log "復元結果を確認中..."
for col in "${COLLECTIONS[@]}"; do
    COUNT=$(${COMPOSE_CMD} exec -T mongo mongosh \
        --username="${MONGO_USERNAME}" \
        --password="${MONGO_PASSWORD}" \
        --authenticationDatabase=admin \
        --quiet \
        --eval "db.getSiblingDB('${DATABASE_NAME}').${col}.countDocuments({})")
    log "  ${col}: ${COUNT} documents"
done

log "=== リストア完了 ==="
log ""
log "注意事項:"
log "  - users/api_keysを復元した場合、移行元のJWT_SECRET_KEYも移行先に設定してください"
log "  - 移行先でアプリケーションを再起動してください: docker compose restart web"
