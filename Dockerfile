# マルチステージビルド: ベースイメージ
FROM python:3.11-slim as base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 依存関係ビルドステージ
FROM base as builder
WORKDIR /opt/venv

# 仮想環境を作成
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# システム依存関係をインストール
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をインストール
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# 本番用イメージ
FROM base as production

# 非rootユーザーを作成
RUN groupadd -r app && useradd -r -g app app

# システム依存関係（実行時のみ必要）
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 仮想環境をコピー
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 作業ディレクトリを設定
WORKDIR /app

# アプリケーションファイルをコピー
COPY --chown=app:app . .

# ログディレクトリを作成
RUN mkdir -p /app/logs && chown -R app:app /app/logs

# 非rootユーザーに切り替え
USER app

# ヘルスチェック（詳細版）
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# ポートを公開
EXPOSE 8000

# プロダクション用の起動設定
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--access-log"]

# 開発用イメージ
FROM production as development
USER root
RUN pip install --no-cache-dir debugpy ipython
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]