import os
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # MongoDB設定
    mongodb_url: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    database_name: str = os.getenv("DATABASE_NAME", "stock_data")
    
    # API設定
    api_title: str = "Stock Data Service"
    api_description: str = "株価データ管理サービス API (yfinance統合版)"
    api_version: str = "2.0.0"
    
    # サーバー設定
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Logging設定
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # yfinance設定
    yfinance_timeout: int = int(os.getenv("YFINANCE_TIMEOUT", "30"))
    
    # Performance設定
    uvicorn_workers: int = int(os.getenv("UVICORN_WORKERS", "1"))
    uvicorn_max_workers: int = int(os.getenv("UVICORN_MAX_WORKERS", "4"))
    
    # Cache設定
    cache_default_ttl: int = int(os.getenv("CACHE_DEFAULT_TTL", "3600"))
    cache_stock_info_ttl: int = int(os.getenv("CACHE_STOCK_INFO_TTL", "86400"))
    cache_daily_prices_ttl: int = int(os.getenv("CACHE_DAILY_PRICES_TTL", "3600"))
    cache_financials_ttl: int = int(os.getenv("CACHE_FINANCIALS_TTL", "21600"))
    
    # Security設定
    mongo_password: str = os.getenv("MONGO_PASSWORD", "password")
    
    # JWT設定
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "your-super-secret-jwt-key-change-this-in-production")
    jwt_access_token_expire_minutes: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # API Key設定
    api_key_expire_days: int = int(os.getenv("API_KEY_EXPIRE_DAYS", "365"))
    
    # Rate Limiting設定（認証あり）
    authenticated_rate_limit: int = int(os.getenv("AUTHENTICATED_RATE_LIMIT", "2000"))
    unauthenticated_rate_limit: int = int(os.getenv("UNAUTHENTICATED_RATE_LIMIT", "100"))
    
    @property
    def is_production(self) -> bool:
        """本番環境かどうか"""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """開発環境かどうか"""
        return self.environment.lower() == "development"
    
    @property 
    def is_testing(self) -> bool:
        """テスト環境かどうか"""
        return self.environment.lower() == "test"
    
    class Config:
        env_file = ".env"


# 環境に応じた設定ファイルを選択
def get_env_file():
    env = os.getenv("ENVIRONMENT", "development").lower()
    env_files = {
        "production": ".env.prod",
        "development": ".env.dev", 
        "test": ".env.test"
    }
    return env_files.get(env, ".env")


# 設定を初期化
class EnvironmentSettings(Settings):
    class Config:
        env_file = get_env_file()


settings = EnvironmentSettings()