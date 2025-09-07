import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.logging_config import get_access_logger
import logging

logger = logging.getLogger("app.middleware")
access_logger = get_access_logger()


class LoggingMiddleware(BaseHTTPMiddleware):
    """リクエスト・レスポンスのログ記録ミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        # リクエストIDを生成
        request_id = str(uuid.uuid4())[:8]
        
        # リクエスト開始時間を記録
        start_time = time.time()
        
        # クライアント情報を取得
        client_ip = self.get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        
        # リクエスト情報をログに記録
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "user_ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "query_params": str(request.query_params)
            }
        )
        
        # リクエストIDをリクエストに追加（他のログで使用するため）
        request.state.request_id = request_id
        
        try:
            # リクエストを処理
            response = await call_next(request)
            
            # 処理時間を計算
            process_time = time.time() - start_time
            
            # アクセスログを記録
            access_logger.info(
                f"{client_ip} - {request.method} {request.url.path} "
                f"{response.status_code} {process_time:.3f}s \"{user_agent}\" [{request_id}]"
            )
            
            # レスポンス情報をログに記録
            logger.info(
                f"Request completed: {response.status_code}",
                extra={
                    "request_id": request_id,
                    "user_ip": client_ip,
                    "status_code": response.status_code,
                    "process_time_ms": round(process_time * 1000, 2)
                }
            )
            
            # レスポンスヘッダーにリクエストIDを追加
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"
            
            return response
            
        except Exception as e:
            # エラーログを記録
            process_time = time.time() - start_time
            
            logger.error(
                f"Request failed: {str(e)}",
                extra={
                    "request_id": request_id,
                    "user_ip": client_ip,
                    "error": str(e),
                    "process_time_ms": round(process_time * 1000, 2)
                },
                exc_info=True
            )
            
            # アクセスログにもエラーを記録
            access_logger.error(
                f"{client_ip} - {request.method} {request.url.path} "
                f"500 {process_time:.3f}s \"{user_agent}\" [{request_id}] ERROR: {str(e)}"
            )
            
            # 例外を再発生
            raise
    
    def get_client_ip(self, request: Request) -> str:
        """クライアントのIPアドレスを取得"""
        # プロキシ経由の場合のヘッダーを確認
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # 最初のIPアドレスを取得（複数の場合）
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # 直接接続の場合
        return request.client.host if request.client else "unknown"