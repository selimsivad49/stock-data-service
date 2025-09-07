from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from app.config.settings import settings
from app.models.auth import User, UserCreate, TokenData
import secrets
import hashlib
import logging

logger = logging.getLogger("app.services.auth")

# パスワードハッシュ化の設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT設定
ALGORITHM = "HS256"


class AuthService:
    def __init__(self):
        self.secret_key = settings.jwt_secret_key
        self.access_token_expire_minutes = settings.jwt_access_token_expire_minutes
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """パスワードを検証"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    def get_password_hash(self, password: str) -> str:
        """パスワードをハッシュ化"""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """JWTアクセストークンを作成"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=ALGORITHM)
            logger.info(f"Access token created for user: {data.get('sub')}")
            return encoded_jwt
        except Exception as e:
            logger.error(f"Token creation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Token creation failed"
            )
    
    def verify_token(self, token: str) -> TokenData:
        """JWTトークンを検証してTokenDataを返す"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            user_id: str = payload.get("user_id")
            role: str = payload.get("role")
            token_type: str = payload.get("type")
            
            if username is None or token_type != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return TokenData(username=username, user_id=user_id, role=role)
            
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def generate_api_key(self) -> tuple[str, str]:
        """API キーを生成（キーID, 実際のキー）"""
        # API キーID（公開情報）
        key_id = f"sk_{secrets.token_urlsafe(16)}"
        
        # 実際のAPIキー（秘密情報）
        api_key = f"sk_{secrets.token_urlsafe(32)}"
        
        return key_id, api_key
    
    def hash_api_key(self, api_key: str) -> str:
        """APIキーをハッシュ化"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    def verify_api_key(self, api_key: str, hashed_key: str) -> bool:
        """APIキーを検証"""
        return hashlib.sha256(api_key.encode()).hexdigest() == hashed_key
    
    def validate_password_strength(self, password: str) -> bool:
        """パスワード強度を検証"""
        if len(password) < 8:
            return False
        
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password)
        
        # 最低3つの条件を満たす必要がある
        conditions_met = sum([has_upper, has_lower, has_digit, has_special])
        
        return conditions_met >= 3
    
    def create_user_token_data(self, user: User) -> dict:
        """ユーザー情報からトークンデータを作成"""
        return {
            "sub": user.username,
            "user_id": str(user.id),
            "role": user.role.value,
            "email": user.email
        }
    
    def is_token_expired(self, token: str) -> bool:
        """トークンが期限切れかチェック"""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[ALGORITHM],
                options={"verify_exp": False}  # 期限切れでもデコード
            )
            exp = payload.get("exp")
            if exp:
                return datetime.utcnow() > datetime.fromtimestamp(exp)
            return True
        except JWTError:
            return True


# グローバルインスタンス
auth_service = AuthService()