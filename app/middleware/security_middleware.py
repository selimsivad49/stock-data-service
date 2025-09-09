from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from typing import List
import logging

logger = logging.getLogger("app.middleware.security")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """セキュリティヘッダーを追加するミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # セキュリティヘッダーを追加
        security_headers = {
            # XSS攻撃からの保護
            "X-XSS-Protection": "1; mode=block",
            
            # コンテンツタイプスニッフィングの防止
            "X-Content-Type-Options": "nosniff",
            
            # クリックジャッキング攻撃からの保護
            "X-Frame-Options": "DENY",
            
            # HTTPS強制（本番環境用）
            # "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
            
            # リファラー情報の制御
            "Referrer-Policy": "strict-origin-when-cross-origin",
            
            # 機能ポリシー（必要に応じて調整）
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
            
            # サーバー情報の非表示
            "Server": "Stock Data Service API"
        }
        
        # Content Security Policy（開発時は緩い設定）
        is_debug = getattr(request.app.state, 'debug', False) if hasattr(request.app, 'state') else False
        if is_debug:
            # 開発環境では Swagger UI が動作するよう緩い設定
            csp = "default-src 'self' 'unsafe-inline' 'unsafe-eval' data:; img-src 'self' data: https:; connect-src 'self' https:"
        else:
            # 本番環境では厳しい設定
            csp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'"
        
        security_headers["Content-Security-Policy"] = csp
        
        # ヘッダーを追加
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """レート制限情報をヘッダーに追加するミドルウェア"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # レート制限情報がレスポンスに含まれている場合はヘッダーに追加
        if hasattr(request.state, 'rate_limit_info'):
            rate_limit_info = request.state.rate_limit_info
            
            response.headers["X-RateLimit-Limit"] = str(rate_limit_info.limit)
            response.headers["X-RateLimit-Remaining"] = str(rate_limit_info.requests_remaining)
            response.headers["X-RateLimit-Reset"] = rate_limit_info.reset_time.isoformat()
        
        return response


def setup_cors_middleware(app):
    """CORSミドルウェアの設定"""
    
    # 本番環境では制限的なCORS設定
    allowed_origins = [
        "http://localhost:3000",  # React開発サーバー
        "http://localhost:8080",  # Vue開発サーバー
        "https://yourdomain.com",  # 本番ドメイン
    ]
    
    # 開発環境では全てのオリジンを許可（デバッグ用）
    # 本番環境では必ず制限すること
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 本番環境では allowed_origins を使用
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-API-Key",
            "X-Requested-With",
            "Accept",
            "Origin",
            "User-Agent"
        ],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining", 
            "X-RateLimit-Reset",
            "X-Request-ID",
            "X-Process-Time"
        ]
    )


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    """IP アドレス ホワイトリスト ミドルウェア（管理者エンドポイント用）"""
    
    def __init__(self, app, allowed_ips: List[str] = None):
        super().__init__(app)
        self.allowed_ips = allowed_ips or []
    
    async def dispatch(self, request: Request, call_next):
        # 管理者専用エンドポイントの場合のみ IP チェック
        if request.url.path.startswith("/api/admin") or request.url.path.startswith("/api/users"):
            client_ip = self._get_client_ip(request)
            
            # IP ホワイトリストが設定されていて、クライアントIPが含まれていない場合
            if self.allowed_ips and client_ip not in self.allowed_ips:
                logger.warning(f"IP whitelist check failed for {client_ip} accessing {request.url.path}")
                from fastapi import HTTPException, status
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: IP address not allowed"
                )
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """クライアントIPアドレスを取得"""
        # プロキシ経由の場合を考慮
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"


class RequestSizeMiddleware(BaseHTTPMiddleware):
    """リクエストサイズ制限ミドルウェア"""
    
    def __init__(self, app, max_size_bytes: int = 1024 * 1024):  # 1MB
        super().__init__(app)
        self.max_size_bytes = max_size_bytes
    
    async def dispatch(self, request: Request, call_next):
        # Content-Length ヘッダーをチェック
        content_length = request.headers.get("content-length")
        
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_size_bytes:
                    from fastapi import HTTPException, status
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request too large. Maximum size: {self.max_size_bytes} bytes"
                    )
            except ValueError:
                pass  # 無効な Content-Length は無視
        
        return await call_next(request)


def setup_security_middleware(app, debug: bool = False):
    """セキュリティミドルウェアの一括設定"""
    
    # セキュリティヘッダー
    app.add_middleware(SecurityHeadersMiddleware)
    
    # レート制限ヘッダー
    app.add_middleware(RateLimitHeaderMiddleware)
    
    # リクエストサイズ制限
    app.add_middleware(RequestSizeMiddleware, max_size_bytes=1024*1024)  # 1MB
    
    # CORS設定
    setup_cors_middleware(app)
    
    # 本番環境でのIP制限（必要に応じて有効化）
    if not debug:
        # IP ホワイトリストを設定（管理者エンドポイント用）
        # allowed_ips = ["192.168.1.0/24", "10.0.0.0/8"]  # 例
        # app.add_middleware(IPWhitelistMiddleware, allowed_ips=allowed_ips)
        pass
    
    logger.info("Security middleware configured")