## 補足事項

- yfinance APIの利用制限に注意し、適切な間隔でリクエストを実行
- 日本株の祝日・営業日カレンダーを考慮
- 米国株と日本株のタイムゾーンの違いに注意
- 株式分割、配当等の調整を考慮したデータ管理
- **効率的なデータ取得**:
  - yfinanceから株価・財務データを一度に取得
  - 不要な重複リクエストを避けるためのキャッシュ機能
  - APIレート制限を考慮した取得間隔制御
- **財務データの永続保持**:
  - yfinanceで取得不可になった古いデータも保持
  - データの歴史的価値を重視した設計
  - 企業の決算修正にも対応した更新ロジック
  - 長期的な財務分析を可能にするデータ蓄積# 株価データ管理サービス開発指示書

## プロジェクト概要

yfinanceのAPIを使用して株価データを取得し、MongoDBに保存して、REST APIとして情報を提供するマイクロサービスを構築してください。

## 技術スタック

- **バックエンド**: Python (FastAPI または Flask)
- **データベース**: MongoDB
- **コンテナ化**: Docker & Docker Compose
- **データソース**: yfinance Python ライブラリ
- **対象市場**: 日本株式市場、米国株式市場

## 機能要件

### 1. データ管理機能

#### 対象データ
- **日足データ**: 日付、始値、高値、安値、終値、出来高、調整後終値
- **財務データ**: 売上高、利益、資産、負債、自己資本比率等の主要財務指標

#### 対象銘柄
- **日本株**: Tokyo Stock Exchange (TSE) 上場銘柄
  - 銘柄コード形式: `1234.T` (4桁コード + .T)
- **米国株**: NASDAQ、NYSE上場銘柄
  - 銘柄コード形式: `AAPL`, `MSFT` 等

### 2. REST API エンドポイント

#### 株価データ取得
```
GET /api/stocks/{symbol}/daily
クエリパラメータ:
- start_date: 開始日 (YYYY-MM-DD)
- end_date: 終了日 (YYYY-MM-DD)
- period: 期間指定 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
```

#### 財務データ取得
```
GET /api/stocks/{symbol}/financials
クエリパラメータ:
- type: quarterly | annual (四半期 | 年次)
```

#### 銘柄情報取得
```
GET /api/stocks/{symbol}/info
```

#### 銘柄検索
```
GET /api/stocks/search
クエリパラメータ:
- query: 検索キーワード
- market: jp | us (日本 | 米国)
```

### 3. データ取得ロジック

#### 自動データ取得条件
以下の場合にyfinanceからデータを自動取得:

1. **新規銘柄**: データベースに存在しない銘柄のリクエスト時
2. **データ不足**: 要求された期間のデータが不完全な場合
3. **最新データ**: 最新の営業日のデータが存在しない場合

#### データ更新戦略
- 日足データ: 営業日の市場終了後に自動更新
- 財務データ: 決算発表後に更新（手動トリガーまたは定期チェック）

## 技術仕様

### 1. プロジェクト構成
```
stock-data-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI アプリケーション
│   ├── models/
│   │   ├── __init__.py
│   │   ├── stock.py         # データモデル定義
│   │   └── financials.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── yfinance_service.py  # yfinance API ラッパー
│   │   └── database_service.py  # MongoDB 操作
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints/
│   │       ├── stocks.py    # 株価関連エンドポイント
│   │       └── financials.py
│   └── config/
│       ├── __init__.py
│       └── settings.py      # 設定管理
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md
```

### 2. データベーススキーマ

#### 日足データコレクション (daily_prices)
```json
{
  "_id": ObjectId,
  "symbol": "AAPL",
  "date": "2024-01-15",
  "open": 185.50,
  "high": 187.20,
  "low": 184.30,
  "close": 186.75,
  "adj_close": 186.75,
  "volume": 45678900,
  "created_at": "2024-01-16T09:00:00Z",
  "updated_at": "2024-01-16T09:00:00Z"
}
```

#### 財務データコレクション (financials)
```json
{
  "_id": ObjectId,
  "symbol": "AAPL",
  "period_type": "quarterly",  // quarterly | annual
  "period_end": "2023-12-31",
  "revenue": 119575000000,
  "gross_profit": 54735000000,
  "operating_income": 40273000000,
  "net_income": 33916000000,
  "total_assets": 352755000000,
  "total_debt": 104590000000,
  "shareholders_equity": 62146000000,
  "created_at": "2024-01-16T09:00:00Z",
  "updated_at": "2024-01-16T09:00:00Z"
}
```

#### 銘柄情報コレクション (stock_info)
```json
{
  "_id": ObjectId,
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "sector": "Technology",
  "industry": "Consumer Electronics",
  "market": "us",  // jp | us
  "currency": "USD",
  "exchange": "NMS",
  "created_at": "2024-01-16T09:00:00Z",
  "updated_at": "2024-01-16T09:00:00Z"
}
```

### 3. Docker設定

#### Dockerfile要件
- Python 3.11以上
- 必要なライブラリのインストール
- 非rootユーザーでの実行
- ヘルスチェック機能

#### Docker Compose要件
- Webアプリケーションサービス
- MongoDBサービス
- 環境変数設定
- ボリュームマウント（データ永続化）
- ネットワーク設定

### 4. エラーハンドリング

#### API エラーレスポンス
```json
{
  "error": {
    "code": "STOCK_NOT_FOUND",
    "message": "指定された銘柄が見つかりません",
    "details": {
      "symbol": "INVALID"
    }
  }
}
```

#### エラーコード定義
- `STOCK_NOT_FOUND`: 銘柄が見つからない
- `DATA_UNAVAILABLE`: データが取得できない
- `INVALID_DATE_RANGE`: 無効な日付範囲
- `YFINANCE_ERROR`: yfinance API エラー
- `DATABASE_ERROR`: データベースエラー

### 5. ログ機能

#### ログレベル
- DEBUG: 詳細なデバッグ情報
- INFO: 一般的な情報（API呼び出し、データ取得成功等）
- WARNING: 警告（データ不完全、API制限等）
- ERROR: エラー（API失敗、DB接続エラー等）

#### ログ出力項目
- タイムスタンプ
- ログレベル
- リクエストID
- 銘柄コード
- 処理時間
- エラーメッセージ

## パフォーマンス要件

### 1. レスポンス時間
- キャッシュありデータ: 100ms以下
- yfinance取得込み: 3秒以下

### 2. 同時接続数
- 100リクエスト/秒まで対応

### 3. データ保持
- 日足データ: 過去10年分
- 財務データ: 過去5年分

## セキュリティ要件

### 1. API認証
- API キー認証（オプション）
- レート制限: 1000リクエスト/時間/IP

### 2. データ保護
- MongoDB接続の暗号化
- 機密情報の環境変数管理

## 開発・運用要件

### 1. 開発環境
- 開発用docker-compose設定
- テストデータの自動生成
- API ドキュメント自動生成（Swagger/OpenAPI）

### 2. 監視・ヘルスチェック
- アプリケーションヘルスチェックエンドポイント
- データベース接続チェック
- yfinance API接続チェック

### 3. 設定管理
- 環境変数による設定切り替え
- 開発/本番環境の分離

## 実装優先順位

1. **Phase 1**: 基本的なREST API構築
   - FastAPI セットアップ
   - MongoDB接続
   - 基本的なCRUD操作

2. **Phase 2**: yfinance統合
   - データ自動取得ロジック
   - エラーハンドリング

3. **Phase 3**: Docker化
   - Dockerfile作成
   - docker-compose設定

4. **Phase 4**: 拡張機能
   - 認証機能
   - バックアップ/リストア機能
   - 監視機能
   - パフォーマンス最適化

## 補足事項

- yfinance APIの利用制限に注意し、適切な間隔でリクエストを実行
- 日本株の祝日・営業日カレンダーを考慮
- 米国株と日本株のタイムゾーンの違いに注意
- 株式分割、配当等の調整を考慮したデータ管理