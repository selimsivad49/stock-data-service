# Stock Data Service

yfinanceを使用した株価データ管理サービス（Phase 4: 認証・認可機能完了）

## 概要

MongoDBを使用して株価・財務データを管理し、REST APIで提供するエンタープライズレディなマイクロサービスです。JWT/APIキー認証、ロールベースアクセス制御、レート制限機能を搭載し、完全にセキュアな本番環境に対応しています。

## 技術スタック

- **Backend**: FastAPI (Uvicorn)
- **Database**: MongoDB 7.0 (最適化済み)
- **Container**: Docker & Docker Compose (マルチステージビルド)
- **Data Source**: yfinance
- **Authentication**: JWT + API Key認証
- **Authorization**: ロールベースアクセス制御 (RBAC)
- **Security**: bcrypt パスワードハッシュ、レート制限、セキュリティヘッダー
- **Cache**: インメモリキャッシュ
- **Monitoring**: 包括的ヘルスチェック・メトリクス
- **Logging**: 構造化ログ (JSON/テキスト)
- **Proxy**: Nginx (レート制限・セキュリティヘッダー)
- **Python**: 3.11

## 主要機能

### 🚀 データ取得・管理
✅ **自動データ取得**: データベースに存在しないデータはyfinanceから自動取得  
✅ **インテリジェントキャッシュ**: 多階層キャッシュによるAPIレスポンスの高速化  
✅ **レート制限**: yfinance APIの制限に配慮した取得間隔制御  
✅ **日本株・米国株対応**: 銘柄コード自動判定  

### 🔐 認証・認可（Phase 4新機能）
✅ **JWT認証**: セキュアなトークンベース認証  
✅ **APIキー認証**: 外部クライアント向け永続的認証  
✅ **ロールベースアクセス制御**: admin/user/readonly権限管理  
✅ **パスワードセキュリティ**: bcrypt ハッシュ化・強度検証  
✅ **ユーザー管理**: 登録・更新・無効化・統計取得  

### 🛡️ エラーハンドリング・セキュリティ
✅ **包括的エラーハンドリング**: ネットワークエラー、銘柄不存在等の適切な処理  
✅ **統一エラーレスポンス**: 構造化されたエラー情報  
✅ **多層レート制限**: ユーザー別・APIキー別・IP別の柔軟な制限  
✅ **セキュリティヘッダー**: XSS、CSRF、CSP保護  
✅ **CORS設定**: オリジン制限・認証情報対応  

### 📊 監視・運用
✅ **包括的ヘルスチェック**: 各サービスの詳細な健康状態監視  
✅ **メトリクス**: システム・アプリケーションレベルのメトリクス  
✅ **構造化ログ**: JSON形式の詳細ログ (リクエストID付き)  
✅ **バックアップ・リストア**: 自動化されたデータベースバックアップ  

### 🏗️ インフラストラクチャ
✅ **マルチステージビルド**: 最適化されたDockerイメージ  
✅ **環境分離**: 開発・本番・テスト環境の設定分離  
✅ **データ永続化**: ボリューム管理とバックアップ戦略  
✅ **MongoDB最適化**: インデックス最適化・バリデーションスキーマ

## セットアップ

### 1. プロジェクトのクローン

```bash
git clone <repository-url>
cd stock-data-service
```

### 2. 環境設定

```bash
# 開発環境 (デフォルト)
cp .env.example .env
# または
cp .env.dev .env

# 本番環境
cp .env.prod .env
# MONGO_PASSWORDを安全なパスワードに変更してください
```

### 3. 起動方法

#### 開発環境
```bash
# 開発環境で起動（ホットリロード有効）
docker-compose up -d

# ログを確認
docker-compose logs -f web
```

#### 本番環境
```bash
# 本番環境で起動（Nginx + 最適化済み）
ENVIRONMENT=production docker-compose -f docker-compose.prod.yml up -d

# ログを確認
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. 動作確認

```bash
# 包括的ヘルスチェック
curl http://localhost:8000/health

# システムメトリクス確認  
curl http://localhost:8000/api/monitoring/metrics

# API仕様確認（Swagger UI）
# ブラウザで http://localhost:8000/docs を開く
```

## API エンドポイント

### 基本情報
- **Base URL**: `http://localhost:8000`
- **Documentation**: `http://localhost:8000/docs`
- **認証**: JWT Bearer Token または APIキー

### 🔐 認証エンドポイント（Phase 4新機能）

#### ユーザー登録
```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "testuser",
  "email": "test@example.com", 
  "password": "SecurePass123!",
  "full_name": "Test User"
}
```

#### ログイン（JWTトークン取得）
```http
POST /api/auth/login
Content-Type: application/json

{
  "username": "testuser",
  "password": "SecurePass123!"
}
```

#### 現在のユーザー情報取得
```http
GET /api/auth/me
Authorization: Bearer <jwt_token>
```

#### APIキー作成
```http
POST /api/auth/api-keys
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "name": "My API Key",
  "scopes": ["read", "write"],
  "rate_limit_requests": 1000
}
```

### 🔧 ユーザー管理（管理者専用）

#### ユーザー一覧取得
```http
GET /api/users/?role=user&skip=0&limit=100
Authorization: Bearer <admin_jwt_token>
```

#### ユーザー情報更新
```http
PUT /api/users/{user_id}
Authorization: Bearer <admin_jwt_token>
Content-Type: application/json

{
  "role": "user",
  "is_active": true,
  "rate_limit_requests": 2000
}
```

### 📈 株価データ（認証必須）

#### 日足データ取得
```http
GET /api/stocks/{symbol}/daily?start_date=2024-01-01&end_date=2024-12-31&period=1y
Authorization: Bearer <jwt_token>
# または
X-API-Key: <key_id>:<api_key>
```
**機能**: 認証必須・自動データ取得・レート制限適用

#### 日足データ作成
```http
POST /api/stocks/{symbol}/daily
Content-Type: application/json

{
  "symbol": "7203.T",
  "date": "2024-01-15",
  "open": 1500.0,
  "high": 1520.0,
  "low": 1495.0,
  "close": 1510.0,
  "adj_close": 1510.0,
  "volume": 1000000
}
```

#### 日足データ更新
```http
PUT /api/stocks/{symbol}/daily/{date}
```

#### 日足データ削除
```http
DELETE /api/stocks/{symbol}/daily/{date}
```

### 銘柄情報（自動取得機能付き）

#### 銘柄情報取得
```http
GET /api/stocks/{symbol}/info
```
**新機能**: 銘柄情報が存在しない場合、自動でyfinanceから取得して保存します

#### 銘柄情報作成
```http
POST /api/stocks/{symbol}/info
Content-Type: application/json

{
  "symbol": "7203.T",
  "name": "トヨタ自動車株式会社",
  "sector": "自動車",
  "industry": "自動車製造",
  "market": "jp",
  "currency": "JPY",
  "exchange": "TSE"
}
```

#### 銘柄検索
```http
GET /api/stocks/search?query=トヨタ&market=jp
```

### 財務データ（自動取得機能付き）

#### 財務データ取得
```http
GET /api/stocks/{symbol}/financials?type=quarterly
```
**新機能**: 財務データが古い場合、自動でyfinanceから最新データを取得します

#### 財務データ作成
```http
POST /api/stocks/{symbol}/financials
Content-Type: application/json

{
  "symbol": "7203.T",
  "period_type": "quarterly",
  "period_end": "2023-12-31",
  "revenue": 10000000000,
  "gross_profit": 2000000000,
  "operating_income": 1500000000,
  "net_income": 1000000000,
  "total_assets": 50000000000,
  "total_debt": 15000000000,
  "shareholders_equity": 30000000000
}
```

### 管理機能

#### システムステータス確認
```http
GET /api/admin/system/status
```

#### キャッシュ統計取得
```http
GET /api/admin/cache/stats
```

#### キャッシュクリア
```http
POST /api/admin/cache/clear?prefix=stock_info
```

#### 特定銘柄のデータ強制更新
```http
POST /api/admin/stocks/{symbol}/update
```

### 監視機能（Phase 3新機能）

#### 詳細ヘルスチェック（Kubernetesプローブ対応）
```http
GET /health                    # 包括的ヘルスチェック
GET /api/monitoring/readiness  # Readiness プローブ
GET /api/monitoring/liveness   # Liveness プローブ
```

#### システムメトリクス
```http
GET /api/monitoring/metrics    # CPU・メモリ・キャッシュメトリクス
GET /api/monitoring/info       # サービス情報
```

## エラーハンドリング

### 統一されたエラーレスポンス形式
```json
{
  "error": {
    "code": "STOCK_NOT_FOUND",
    "message": "指定された銘柄が見つかりません",
    "details": {
      "symbol": "INVALID.T"
    }
  }
}
```

### エラーコード
- `STOCK_NOT_FOUND`: 銘柄が見つからない
- `DATA_UNAVAILABLE`: データが取得できない  
- `NETWORK_ERROR`: ネットワークエラー
- `RATE_LIMIT_EXCEEDED`: APIレート制限
- `YFINANCE_ERROR`: yfinance関連エラー
- `DATABASE_ERROR`: データベースエラー

## データベーススキーマ

### daily_prices コレクション
- `symbol`: 銘柄コード
- `date`: 取引日
- `open`, `high`, `low`, `close`: 四本値
- `adj_close`: 調整後終値
- `volume`: 出来高

### stock_info コレクション
- `symbol`: 銘柄コード
- `name`: 企業名
- `sector`: セクター
- `industry`: 業界
- `market`: 市場（jp/us）

### financials コレクション
- `symbol`: 銘柄コード
- `period_type`: 期間タイプ（quarterly/annual）
- `period_end`: 期間終了日
- 各種財務指標

## 開発

### ローカル開発環境

```bash
# 依存関係インストール
pip install -r requirements.txt

# 環境変数設定
cp .env.example .env

# MongoDB起動（Docker）
docker-compose up -d mongo

# アプリケーション起動
uvicorn app.main:app --reload
```

### コンテナ再ビルド

```bash
docker-compose down
docker-compose up --build -d
```

## パフォーマンス

### キャッシュ機能
- **銘柄情報**: 24時間キャッシュ
- **日足データ**: 1時間キャッシュ  
- **財務データ**: 6時間キャッシュ

### レート制限
- yfinance APIへのリクエスト間隔: 1秒
- 自動リトライとエラーハンドリング

## 使用例

### 日本株（トヨタ自動車）の取得
```bash
# 銘柄情報を自動取得・保存
curl http://localhost:8000/api/stocks/7203.T/info

# 日足データを自動取得（過去1年分）
curl "http://localhost:8000/api/stocks/7203.T/daily?period=1y"

# 財務データを自動取得
curl "http://localhost:8000/api/stocks/7203.T/financials?type=quarterly"
```

### 米国株（Apple）の取得
```bash
# 銘柄情報を自動取得・保存
curl http://localhost:8000/api/stocks/AAPL/info

# 日足データを自動取得
curl "http://localhost:8000/api/stocks/AAPL/daily?period=6mo"
```

## 運用・保守

### バックアップ・リストア

#### 自動バックアップ作成
```bash
# バックアップ作成
./scripts/backup_db.sh

# 定期バックアップ（cron例）
0 2 * * * /path/to/stock-data-service/scripts/backup_db.sh
```

#### データリストア
```bash
# バックアップファイルを指定してリストア
./scripts/restore_db.sh stock_data_backup_20241201_120000.tar.gz
```

### ログ管理

#### ログファイル場所
- **アプリケーションログ**: `logs/app.log`
- **エラーログ**: `logs/error.log`  
- **アクセスログ**: `logs/access.log`

#### ログローテーション
- ファイルサイズ: 10MB で自動ローテーション
- バックアップ世代数: 5世代保持

### パフォーマンス監視

#### 主要メトリクス
```bash
# システムリソース監視
curl http://localhost:8000/api/monitoring/metrics

# キャッシュ効率監視  
curl http://localhost:8000/api/admin/cache/stats

# データベースヘルスチェック
curl http://localhost:8000/health
```

## Docker最適化詳細

### マルチステージビルド効果
- **イメージサイズ削減**: 開発用依存関係を本番イメージから除外
- **セキュリティ向上**: 最小限のランタイム環境
- **ビルド時間短縮**: キャッシュ効率の向上

### リソース制限
```yaml
# 本番環境でのリソース制限例
deploy:
  resources:
    limits:
      memory: 512M
      cpus: '0.5'
    reservations:
      memory: 256M
      cpus: '0.25'
```

## 今後の実装予定

- **Phase 4**: 認証・認可機能（JWT、API Key）
- **Phase 5**: 高度な監視（Prometheus、Grafana）
- **Phase 6**: 分散キャッシュ（Redis）・スケーラビリティ強化

## トラブルシューティング

### MongoDBに接続できない場合
```bash
# コンテナの状態確認
docker-compose ps

# MongoDBログ確認
docker-compose logs mongo
```

### APIが応答しない場合
```bash
# Webサービスログ確認
docker-compose logs web
```