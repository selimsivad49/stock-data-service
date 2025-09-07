from typing import Optional, Union
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import auth_service
from app.services.user_service import user_service
from app.services.api_key_service import api_key_service
from app.services.rate_limit_service import rate_limit_service
from app.models.auth import User, APIKey, UserRole, APIKeyScope, RateLimitInfo
from datetime import datetime
import logging

logger = logging.getLogger("app.middleware.auth")

# HTTPBearer認証スキーム
security = HTTPBearer(auto_error=False)


class AuthContext:
    """認証コンテキスト（ユーザーまたはAPIキー情報を保持）"""
    def __init__(
        self,
        user: Optional[User] = None,
        api_key: Optional[APIKey] = None,
        auth_type: str = "none"
    ):
        self.user = user
        self.api_key = api_key
        self.auth_type = auth_type  # "jwt", "api_key", "none"
    
    @property
    def is_authenticated(self) -> bool:
        return self.user is not None or self.api_key is not None
    
    @property
    def user_id(self) -> Optional[str]:
        if self.user:
            return str(self.user.id)
        elif self.api_key:
            return str(self.api_key.user_id)
        return None
    
    @property
    def username(self) -> Optional[str]:
        return self.user.username if self.user else None
    
    @property
    def role(self) -> Optional[UserRole]:
        return self.user.role if self.user else None
    
    def has_role(self, required_role: UserRole) -> bool:
        """指定されたロールを持っているかチェック"""
        if not self.user:
            return False
        
        # Admin は全てのロールを持つ
        if self.user.role == UserRole.ADMIN:
            return True
        
        return self.user.role == required_role
    
    def has_scope(self, required_scope: APIKeyScope) -> bool:
        """APIキーが必要なスコープを持っているかチェック"""
        if self.api_key:
            return api_key_service.has_scope(self.api_key, required_scope)
        
        # JWTトークンの場合、ユーザーのロールベースでスコープを判定
        if self.user:
            if self.user.role == UserRole.ADMIN:
                return True
            if required_scope == APIKeyScope.READ and self.user.role in [UserRole.USER, UserRole.READONLY]:
                return True
            if required_scope == APIKeyScope.WRITE and self.user.role == UserRole.USER:
                return True
        
        return False


async def get_auth_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> AuthContext:
    """認証コンテキストを取得（JWT または APIキー）"""
    
    # APIキー認証をチェック（ヘッダーまたはクエリパラメータ）
    api_key_header = request.headers.get("X-API-Key")
    api_key_query = request.query_params.get("api_key")
    api_key_auth = api_key_header or api_key_query
    
    if api_key_auth:
        try:
            # APIキー形式: "key_id:api_key"
            if ":" in api_key_auth:
                key_id, raw_api_key = api_key_auth.split(":", 1)
                api_key = await api_key_service.authenticate_api_key(key_id, raw_api_key)
                
                if api_key:
                    return AuthContext(api_key=api_key, auth_type="api_key")
        except Exception as e:
            logger.warning(f"API key authentication failed: {e}")
    
    # JWT認証をチェック
    if credentials:
        try:
            token_data = auth_service.verify_token(credentials.credentials)
            user = await user_service.get_user_by_username(token_data.username)
            
            if user and user.is_active:
                return AuthContext(user=user, auth_type="jwt")
        except HTTPException:
            pass  # トークンが無効な場合は未認証として扱う
        except Exception as e:
            logger.warning(f"JWT authentication failed: {e}")
    
    # 未認証
    return AuthContext(auth_type="none")


async def require_authentication(
    auth_context: AuthContext = Depends(get_auth_context)
) -> AuthContext:
    """認証を必須とする"""
    if not auth_context.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return auth_context


async def require_role(required_role: UserRole):
    """指定されたロールを必須とする"""
    def role_checker(auth_context: AuthContext = Depends(require_authentication)) -> AuthContext:
        if not auth_context.has_role(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role.value}' required"
            )
        return auth_context
    
    return role_checker


async def require_scope(required_scope: APIKeyScope):
    """指定されたスコープを必須とする"""
    def scope_checker(auth_context: AuthContext = Depends(require_authentication)) -> AuthContext:
        if not auth_context.has_scope(required_scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{required_scope.value}' required"
            )
        return auth_context
    
    return scope_checker


# 便利な依存関数
async def require_admin(auth_context: AuthContext = Depends(require_role(UserRole.ADMIN))) -> AuthContext:
    """管理者権限を必須とする"""
    return auth_context


async def require_read_access(auth_context: AuthContext = Depends(require_scope(APIKeyScope.READ))) -> AuthContext:
    """読み取り権限を必須とする"""
    return auth_context


async def require_write_access(auth_context: AuthContext = Depends(require_scope(APIKeyScope.WRITE))) -> AuthContext:
    """書き込み権限を必須とする"""
    return auth_context


class RateLimitMiddleware:
    """レート制限ミドルウェア"""
    
    @staticmethod
    async def check_rate_limit(
        request: Request,
        auth_context: AuthContext = Depends(get_auth_context)
    ) -> RateLimitInfo:
        """レート制限をチェック"""
        
        endpoint = f"{request.method} {request.url.path}"
        
        try:
            if auth_context.user:
                # 認証ユーザーのレート制限
                rate_limit_info = await rate_limit_service.check_user_rate_limit(
                    auth_context.user, endpoint
                )
            elif auth_context.api_key:
                # APIキーのレート制限
                rate_limit_info = await rate_limit_service.check_api_key_rate_limit(
                    auth_context.api_key, endpoint
                )
            else:
                # IPアドレスベースのレート制限
                client_ip = request.client.host if request.client else "unknown"
                rate_limit_info = await rate_limit_service.check_ip_rate_limit(
                    client_ip, endpoint
                )
            
            # レート制限に達している場合はエラー
            if rate_limit_service.is_rate_limited(rate_limit_info):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(rate_limit_info.limit),
                        "X-RateLimit-Remaining": str(rate_limit_info.requests_remaining),
                        "X-RateLimit-Reset": rate_limit_info.reset_time.isoformat(),
                        "Retry-After": str(int((rate_limit_info.reset_time - datetime.utcnow()).total_seconds()))
                    }
                )
            
            return rate_limit_info
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # レート制限チェックでエラーが発生した場合はリクエストを通す
            return RateLimitInfo(
                requests_made=0,
                requests_remaining=1000,
                reset_time=datetime.utcnow(),
                limit=1000,
                window=3600
            )


# レート制限チェックの依存関数
check_rate_limit = RateLimitMiddleware.check_rate_limit