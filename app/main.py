from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.config.settings import settings
from app.config.logging_config import setup_logging
from app.services.database_service import database_service
from app.api.endpoints import stocks, financials, admin, monitoring, auth, users
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.security_middleware import setup_security_middleware
import logging

# ログ設定を初期化
setup_logging()
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # アプリケーション開始時
    logger.info("Starting Stock Data Service...")
    try:
        await database_service.connect()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise
    
    yield
    
    # アプリケーション終了時
    logger.info("Shutting down Stock Data Service...")
    try:
        await database_service.disconnect()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan
)

# セキュリティミドルウェアを設定
setup_security_middleware(app, debug=settings.debug)

# ミドルウェアを追加
app.add_middleware(LoggingMiddleware)

# ルーター登録
app.include_router(auth.router, prefix="/api/auth", tags=["authentication"])
app.include_router(users.router, prefix="/api/users", tags=["user-management"])
app.include_router(stocks.router, prefix="/api/stocks", tags=["stocks"])
app.include_router(financials.router, prefix="/api/stocks", tags=["financials"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["monitoring"])


@app.get("/")
async def root():
    return {"message": "Stock Data Service API", "version": settings.api_version}


@app.get("/health")
async def health_check():
    """包括的ヘルスチェックエンドポイント"""
    import time
    from datetime import datetime
    
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "stock-data-service",
        "version": settings.api_version,
        "status": "healthy",
        "checks": {}
    }
    
    # データベース接続チェック
    try:
        start_time = time.time()
        db_status = await database_service.health_check()
        db_response_time = time.time() - start_time
        
        health_status["checks"]["database"] = {
            "status": "healthy" if db_status else "unhealthy",
            "response_time_ms": round(db_response_time * 1000, 2),
            "details": "MongoDB connection successful" if db_status else "MongoDB connection failed"
        }
        
        if not db_status:
            health_status["status"] = "unhealthy"
            
    except Exception as e:
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "response_time_ms": 0,
            "details": f"Database error: {str(e)}"
        }
        health_status["status"] = "unhealthy"
    
    # キャッシュサービスチェック
    try:
        from app.services.cache_service import cache_service
        cache_stats = cache_service.get_stats()
        
        health_status["checks"]["cache"] = {
            "status": "healthy",
            "details": f"Cache active with {cache_stats['active_entries']} entries"
        }
        
    except Exception as e:
        health_status["checks"]["cache"] = {
            "status": "unhealthy",
            "details": f"Cache error: {str(e)}"
        }
        health_status["status"] = "unhealthy"
    
    # yfinanceサービステスト（軽量）
    try:
        from app.services.yfinance_service import yfinance_service
        # サービスの初期化状態のみチェック
        health_status["checks"]["yfinance"] = {
            "status": "healthy",
            "details": "yfinance service initialized"
        }
        
    except Exception as e:
        health_status["checks"]["yfinance"] = {
            "status": "unhealthy",
            "details": f"yfinance service error: {str(e)}"
        }
    
    # レスポンスのステータスコードを設定
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    from fastapi import Response
    import json
    return Response(
        content=json.dumps(health_status),
        status_code=status_code,
        media_type="application/json"
    )