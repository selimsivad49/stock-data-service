# Stock Data Service API 仕様書

## 概要

Stock Data Service は、yfinance を使用した株価データ管理 REST API サービスです。JWT 認証と API キー認証をサポートし、日本株・米国株の価格データ、銘柄情報、財務データを提供します。

**Base URL**: `http://localhost:8000`  
**API Documentation**: `http://localhost:8000/docs` (Swagger UI)

## 認証

このAPIは2つの認証方式をサポートしています：

### 1. JWT Bearer Token認証
```http
Authorization: Bearer <jwt_token>
```

### 2. APIキー認証
```http
X-API-Key: <key_id>:<api_key>
```

## レスポンス形式

### 成功レスポンス
通常のJSONオブジェクトまたは配列が返されます。

### エラーレスポンス
全てのエラーは以下の統一形式で返されます：

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ",
    "details": {
      "additional": "information"
    }
  }
}
```

### エラーコード一覧
- `STOCK_NOT_FOUND`: 銘柄が見つからない
- `DATA_UNAVAILABLE`: データが取得できない
- `NETWORK_ERROR`: ネットワークエラー
- `RATE_LIMIT_EXCEEDED`: レート制限超過
- `YFINANCE_ERROR`: yfinance関連エラー
- `DATABASE_ERROR`: データベースエラー
- `UNAUTHORIZED`: 認証が必要
- `FORBIDDEN`: アクセス権限なし
- `VALIDATION_ERROR`: リクエストデータが不正

## レート制限

- **認証済みユーザー**: 3600秒間に2000リクエスト（本番環境）
- **未認証ユーザー**: 3600秒間に100リクエスト（本番環境）
- **APIキー**: 個別に設定可能

レート制限に達した場合、HTTP 429 ステータスコードが返されます。

---

## 🔐 認証エンドポイント

### ユーザー登録

**POST** `/api/auth/register`

新規ユーザーアカウントを作成します。

**リクエスト**
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "SecurePass123!",
  "full_name": "Test User"
}
```

**レスポンス** (201 Created)
```json
{
  "id": "user_id",
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z"
}
```

**エラー**
- 400: バリデーションエラー（パスワード強度不足等）
- 409: ユーザー名またはメールアドレスが既に存在

---

### ログイン

**POST** `/api/auth/login`

JWTアクセストークンを取得します。

**リクエスト**
```json
{
  "username": "testuser",
  "password": "SecurePass123!"
}
```

**レスポンス** (200 OK)
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": "user_id",
    "username": "testuser",
    "role": "user"
  }
}
```

**エラー**
- 401: 認証情報が不正
- 403: アカウントが無効

---

### 現在のユーザー情報取得

**GET** `/api/auth/me`

**認証**: 必須

現在認証されているユーザーの情報を取得します。

**レスポンス** (200 OK)
```json
{
  "id": "user_id",
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "role": "user",
  "is_active": true,
  "created_at": "2024-01-15T10:30:00Z",
  "last_login": "2024-01-15T15:30:00Z"
}
```

---

### APIキー作成

**POST** `/api/auth/api-keys`

**認証**: 必須

新しいAPIキーを作成します。

**リクエスト**
```json
{
  "name": "My API Key",
  "scopes": ["read", "write"],
  "rate_limit_requests": 1000
}
```

**レスポンス** (201 Created)
```json
{
  "key_id": "ak_1234567890abcdef",
  "api_key": "sk_abcdef1234567890...",
  "name": "My API Key",
  "scopes": ["read", "write"],
  "rate_limit_requests": 1000,
  "created_at": "2024-01-15T10:30:00Z",
  "expires_at": "2025-01-15T10:30:00Z"
}
```

**注意**: `api_key` は作成時のみ表示されます。必ず安全に保管してください。

---

### APIキー一覧取得

**GET** `/api/auth/api-keys`

**認証**: 必須

現在のユーザーのAPIキー一覧を取得します。

**レスポンス** (200 OK)
```json
[
  {
    "key_id": "ak_1234567890abcdef",
    "name": "My API Key",
    "scopes": ["read", "write"],
    "last_used": "2024-01-15T14:30:00Z",
    "created_at": "2024-01-15T10:30:00Z",
    "expires_at": "2025-01-15T10:30:00Z",
    "is_active": true
  }
]
```

---

### APIキー削除

**DELETE** `/api/auth/api-keys/{key_id}`

**認証**: 必須

指定されたAPIキーを削除します。

**レスポンス** (200 OK)
```json
{
  "message": "APIキーを削除しました"
}
```

---

## 📈 株価データエンドポイント

### 日足データ取得

**GET** `/api/stocks/{symbol}/daily`

**認証**: 必須

指定銘柄の日足データを取得します。データが存在しない場合、yfinanceから自動取得します。

**パラメータ**
- `symbol` (path): 銘柄コード（例: `7203.T`, `AAPL`）
- `start_date` (query, optional): 開始日（YYYY-MM-DD）
- `end_date` (query, optional): 終了日（YYYY-MM-DD）
- `period` (query, optional): 期間指定（`1d`, `5d`, `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `10y`, `ytd`, `max`）

**例**
```http
GET /api/stocks/7203.T/daily?period=1y
Authorization: Bearer <jwt_token>
```

**レスポンス** (200 OK)
```json
[
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
]
```

---

### 日足データ作成

**POST** `/api/stocks/{symbol}/daily`

**認証**: 必須（書き込み権限）

新しい日足データを作成します。

**リクエスト**
```json
{
  "date": "2024-01-15",
  "open": 1500.0,
  "high": 1520.0,
  "low": 1495.0,
  "close": 1510.0,
  "adj_close": 1510.0,
  "volume": 1000000
}
```

**レスポンス** (201 Created)
```json
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

---

### 日足データ更新

**PUT** `/api/stocks/{symbol}/daily/{date}`

**認証**: 必須（書き込み権限）

既存の日足データを更新します。

**リクエスト**
```json
{
  "open": 1505.0,
  "high": 1525.0,
  "low": 1500.0,
  "close": 1515.0,
  "adj_close": 1515.0,
  "volume": 1100000
}
```

**レスポンス** (200 OK)
```json
{
  "symbol": "7203.T",
  "date": "2024-01-15",
  "open": 1505.0,
  "high": 1525.0,
  "low": 1500.0,
  "close": 1515.0,
  "adj_close": 1515.0,
  "volume": 1100000
}
```

---

### 日足データ削除

**DELETE** `/api/stocks/{symbol}/daily/{date}`

**認証**: 必須（書き込み権限）

指定された日付の日足データを削除します。

**レスポンス** (200 OK)
```json
{
  "message": "データを削除しました"
}
```

---

## 🏢 銘柄情報エンドポイント

### 銘柄情報取得

**GET** `/api/stocks/{symbol}/info`

**認証**: 不要

指定銘柄の基本情報を取得します。存在しない場合、yfinanceから自動取得します。

**例**
```http
GET /api/stocks/7203.T/info
```

**レスポンス** (200 OK)
```json
{
  "symbol": "7203.T",
  "name": "トヨタ自動車株式会社",
  "sector": "Consumer Cyclical",
  "industry": "Auto Manufacturers",
  "market": "jp",
  "currency": "JPY",
  "exchange": "TSE",
  "market_cap": 28000000000000,
  "employees": 375235,
  "website": "https://www.toyota.co.jp",
  "business_summary": "トヨタ自動車株式会社は...",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 銘柄情報作成

**POST** `/api/stocks/{symbol}/info`

**認証**: 必須（書き込み権限）

新しい銘柄情報を作成します。

**リクエスト**
```json
{
  "name": "トヨタ自動車株式会社",
  "sector": "Consumer Cyclical",
  "industry": "Auto Manufacturers",
  "market": "jp",
  "currency": "JPY",
  "exchange": "TSE"
}
```

**レスポンス** (201 Created)
```json
{
  "symbol": "7203.T",
  "name": "トヨタ自動車株式会社",
  "sector": "Consumer Cyclical",
  "industry": "Auto Manufacturers",
  "market": "jp",
  "currency": "JPY",
  "exchange": "TSE",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

---

### 銘柄情報更新

**PUT** `/api/stocks/{symbol}/info`

**認証**: 必須（書き込み権限）

既存の銘柄情報を更新します。

---

### 銘柄情報削除

**DELETE** `/api/stocks/{symbol}/info`

**認証**: 必須（書き込み権限）

指定された銘柄情報を削除します。

---

### 銘柄検索

**GET** `/api/stocks/search`

**認証**: 不要

銘柄名またはシンボルで検索します。

**パラメータ**
- `query` (query, required): 検索キーワード
- `market` (query, optional): 市場指定（`jp` または `us`）

**例**
```http
GET /api/stocks/search?query=トヨタ&market=jp
```

**レスポンス** (200 OK)
```json
[
  {
    "symbol": "7203.T",
    "name": "トヨタ自動車株式会社",
    "sector": "Consumer Cyclical",
    "industry": "Auto Manufacturers",
    "market": "jp",
    "currency": "JPY",
    "exchange": "TSE"
  }
]
```

---

## 💰 財務データエンドポイント

### 財務データ取得

**GET** `/api/stocks/{symbol}/financials`

**認証**: 必須

指定銘柄の財務データを取得します。古いデータの場合、自動で最新データを取得します。

**パラメータ**
- `type` (query, optional): 期間タイプ（`quarterly` または `annual`、デフォルト: `quarterly`）

**例**
```http
GET /api/stocks/7203.T/financials?type=quarterly
Authorization: Bearer <jwt_token>
```

**レスポンス** (200 OK)
```json
[
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
    "shareholders_equity": 30000000000,
    "updated_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### 財務データ作成

**POST** `/api/stocks/{symbol}/financials`

**認証**: 必須（書き込み権限）

新しい財務データを作成します。

**リクエスト**
```json
{
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

---

## 👥 ユーザー管理エンドポイント（管理者専用）

### ユーザー一覧取得

**GET** `/api/users/`

**認証**: 必須（管理者権限）

システム内のユーザー一覧を取得します。

**パラメータ**
- `role` (query, optional): ロールフィルター（`admin`, `user`, `readonly`）
- `skip` (query, optional): スキップ件数（デフォルト: 0）
- `limit` (query, optional): 取得件数（デフォルト: 100）

**例**
```http
GET /api/users/?role=user&skip=0&limit=50
Authorization: Bearer <admin_jwt_token>
```

**レスポンス** (200 OK)
```json
[
  {
    "id": "user_id",
    "username": "testuser",
    "email": "test@example.com",
    "full_name": "Test User",
    "role": "user",
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z",
    "last_login": "2024-01-15T15:30:00Z"
  }
]
```

---

### ユーザー情報取得

**GET** `/api/users/{user_id}`

**認証**: 必須（管理者権限）

指定されたユーザーの詳細情報を取得します。

---

### ユーザー情報更新

**PUT** `/api/users/{user_id}`

**認証**: 必須（管理者権限）

指定されたユーザーの情報を更新します。

**リクエスト**
```json
{
  "role": "user",
  "is_active": true,
  "rate_limit_requests": 2000
}
```

**レスポンス** (200 OK)
```json
{
  "id": "user_id",
  "username": "testuser",
  "email": "test@example.com",
  "full_name": "Test User",
  "role": "user",
  "is_active": true,
  "rate_limit_requests": 2000,
  "updated_at": "2024-01-15T16:30:00Z"
}
```

---

### ユーザー統計取得

**GET** `/api/users/stats`

**認証**: 必須（管理者権限）

ユーザー統計情報を取得します。

**レスポンス** (200 OK)
```json
{
  "total_users": 150,
  "active_users": 142,
  "roles": {
    "admin": 3,
    "user": 140,
    "readonly": 7
  },
  "recent_registrations": 25
}
```

---

## 🛠️ 管理機能エンドポイント

### システムステータス確認

**GET** `/api/admin/system/status`

**認証**: 必須（管理者権限）

システム全体のステータスを確認します。

**レスポンス** (200 OK)
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T16:30:00Z",
  "services": {
    "api": "healthy",
    "database": "healthy",
    "yfinance": "healthy"
  },
  "metrics": {
    "uptime": 86400,
    "memory_usage": "45%",
    "cpu_usage": "12%"
  }
}
```

---

### キャッシュ統計取得

**GET** `/api/admin/cache/stats`

**認証**: 必須（管理者権限）

キャッシュの使用状況を取得します。

**レスポンス** (200 OK)
```json
{
  "total_keys": 1250,
  "hit_rate": 0.85,
  "memory_usage": "128MB",
  "categories": {
    "stock_info": 450,
    "daily_prices": 650,
    "financials": 150
  }
}
```

---

### キャッシュクリア

**POST** `/api/admin/cache/clear`

**認証**: 必須（管理者権限）

キャッシュをクリアします。

**パラメータ**
- `prefix` (query, optional): クリアするキーのプレフィックス

**例**
```http
POST /api/admin/cache/clear?prefix=stock_info
Authorization: Bearer <admin_jwt_token>
```

**レスポンス** (200 OK)
```json
{
  "message": "キャッシュをクリアしました",
  "cleared_keys": 450
}
```

---

## 📊 監視エンドポイント

### ヘルスチェック

**GET** `/health`

**認証**: 不要

サービスの健全性をチェックします。

**レスポンス** (200 OK)
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T16:30:00Z",
  "version": "1.0.0",
  "services": {
    "api": "healthy",
    "database": "healthy",
    "yfinance": "healthy"
  }
}
```

---

### Readinessプローブ

**GET** `/api/monitoring/readiness`

**認証**: 不要

Kubernetesのreadinessプローブ用エンドポイントです。

---

### Livenessプローブ

**GET** `/api/monitoring/liveness`

**認証**: 不要

Kubernetesのlivenessプローブ用エンドポイントです。

---

### システムメトリクス

**GET** `/api/monitoring/metrics`

**認証**: 不要

システムメトリクスを取得します。

**レスポンス** (200 OK)
```json
{
  "timestamp": "2024-01-15T16:30:00Z",
  "system": {
    "cpu_usage": 12.5,
    "memory_usage": 67.8,
    "disk_usage": 23.4
  },
  "application": {
    "active_connections": 15,
    "request_count": 12450,
    "error_rate": 0.02
  },
  "cache": {
    "hit_rate": 0.85,
    "total_keys": 1250
  }
}
```

---

## 使用例

### 基本的な使用フロー

1. **ユーザー登録とログイン**
```bash
# ユーザー登録
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader123",
    "email": "trader@example.com",
    "password": "SecurePass123!",
    "full_name": "Stock Trader"
  }'

# ログイン
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "trader123",
    "password": "SecurePass123!"
  }'
```

2. **株価データ取得**
```bash
# JWTトークンを使用して株価データ取得
curl -X GET "http://localhost:8000/api/stocks/7203.T/daily?period=1y" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 銘柄情報取得（認証不要）
curl -X GET http://localhost:8000/api/stocks/7203.T/info
```

3. **APIキー作成と使用**
```bash
# APIキー作成
curl -X POST http://localhost:8000/api/auth/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Trading App",
    "scopes": ["read", "write"],
    "rate_limit_requests": 5000
  }'

# APIキーを使用してデータ取得
curl -X GET "http://localhost:8000/api/stocks/AAPL/daily?period=6mo" \
  -H "X-API-Key: ak_1234567890abcdef:sk_abcdef1234567890..."
```

### 日本株の例

```bash
# トヨタ自動車の株価データ取得
curl -X GET "http://localhost:8000/api/stocks/7203.T/daily?period=1y" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# ソフトバンクグループの財務データ取得  
curl -X GET "http://localhost:8000/api/stocks/9984.T/financials?type=quarterly" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 米国株の例

```bash
# Apple株価データ取得
curl -X GET "http://localhost:8000/api/stocks/AAPL/daily?period=6mo" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Microsoft銘柄情報取得
curl -X GET http://localhost:8000/api/stocks/MSFT/info
```

---

## サポートされる銘柄形式

### 日本株
- **東証**: `7203.T`（トヨタ自動車）
- **マザーズ**: `3994.T`（マネーフォワード）

### 米国株
- **NYSE/NASDAQ**: `AAPL`（Apple）、`MSFT`（Microsoft）

---

## 注意事項

1. **レート制限**: 過度なリクエストは制限されます。適切な間隔でリクエストしてください。

2. **データ遅延**: 株価データは15-20分程度の遅延があります。

3. **祝日・休場日**: 市場が閉まっている日のデータは取得できません。

4. **認証トークン**: JWTトークンには有効期限があります。期限切れの場合は再ログインが必要です。

5. **APIキー**: APIキーは作成時のみ表示されます。必ず安全に保管してください。

---

## サポート

技術的な問題や質問がある場合は、システム管理者にお問い合わせください。

**API仕様書バージョン**: 1.0.0  
**最終更新**: 2024-01-15