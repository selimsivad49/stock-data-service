from datetime import timedelta
from typing import List
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import OAuth2PasswordRequestForm
from app.models.auth import (
    Token, UserCreate, UserResponse, LoginRequest, ChangePasswordRequest,
    APIKeyCreate, APIKeyResponse
)
from app.services.auth_service import auth_service
from app.services.user_service import user_service
from app.services.api_key_service import api_key_service
from app.middleware.auth_middleware import (
    AuthContext, require_authentication, require_admin, check_rate_limit
)
from app.config.settings import settings

router = APIRouter()


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    _rate_limit = Depends(check_rate_limit)
):
    """新規ユーザー登録"""
    try:
        user = await user_service.create_user(user_data)
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            last_login=user.last_login,
            rate_limit_requests=user.rate_limit_requests
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.post("/login", response_model=Token)
async def login_user(
    login_data: LoginRequest,
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザーログイン"""
    try:
        user = await user_service.authenticate_user(login_data.username, login_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # アクセストークンを生成
        access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        token_data = auth_service.create_user_token_data(user)
        access_token = auth_service.create_access_token(
            data=token_data,
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post("/login/form", response_model=Token)
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    _rate_limit = Depends(check_rate_limit)
):
    """OAuth2フォームベースログイン（Swagger UI用）"""
    try:
        user = await user_service.authenticate_user(form_data.username, form_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
        token_data = auth_service.create_user_token_data(user)
        access_token = auth_service.create_access_token(
            data=token_data,
            expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    auth_context: AuthContext = Depends(require_authentication),
    _rate_limit = Depends(check_rate_limit)
):
    """現在のユーザー情報を取得"""
    if not auth_context.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    return UserResponse(
        id=str(auth_context.user.id),
        username=auth_context.user.username,
        email=auth_context.user.email,
        full_name=auth_context.user.full_name,
        role=auth_context.user.role,
        is_active=auth_context.user.is_active,
        is_verified=auth_context.user.is_verified,
        created_at=auth_context.user.created_at,
        last_login=auth_context.user.last_login,
        rate_limit_requests=auth_context.user.rate_limit_requests
    )


@router.post("/change-password")
async def change_password(
    password_data: ChangePasswordRequest,
    auth_context: AuthContext = Depends(require_authentication),
    _rate_limit = Depends(check_rate_limit)
):
    """パスワード変更"""
    if not auth_context.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    try:
        success = await user_service.change_password(
            str(auth_context.user.id),
            password_data.current_password,
            password_data.new_password
        )
        
        if success:
            return {"message": "Password changed successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password change failed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Password change failed: {str(e)}"
        )


# APIキー管理エンドポイント
@router.post("/api-keys", response_model=dict)
async def create_api_key(
    api_key_data: APIKeyCreate,
    auth_context: AuthContext = Depends(require_authentication),
    _rate_limit = Depends(check_rate_limit)
):
    """新しいAPIキーを作成"""
    if not auth_context.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    try:
        api_key_response, raw_api_key = await api_key_service.create_api_key(
            str(auth_context.user.id),
            api_key_data
        )
        
        return {
            "api_key_info": api_key_response,
            "api_key": raw_api_key,
            "warning": "Store this API key securely. It will not be shown again."
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key creation failed: {str(e)}"
        )


@router.get("/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(
    auth_context: AuthContext = Depends(require_authentication),
    _rate_limit = Depends(check_rate_limit)
):
    """ユーザーのAPIキー一覧を取得"""
    if not auth_context.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    try:
        api_keys = await api_key_service.list_user_api_keys(str(auth_context.user.id))
        return api_keys
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    auth_context: AuthContext = Depends(require_authentication),
    _rate_limit = Depends(check_rate_limit)
):
    """APIキーを無効化"""
    if not auth_context.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    try:
        success = await api_key_service.revoke_api_key(str(auth_context.user.id), key_id)
        
        if success:
            return {"message": "API key revoked successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"API key revocation failed: {str(e)}"
        )


@router.get("/api-keys/stats")
async def get_api_key_stats(
    auth_context: AuthContext = Depends(require_authentication),
    _rate_limit = Depends(check_rate_limit)
):
    """APIキー使用統計を取得"""
    if not auth_context.user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    try:
        stats = await api_key_service.get_api_key_stats(str(auth_context.user.id))
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get API key stats: {str(e)}"
        )