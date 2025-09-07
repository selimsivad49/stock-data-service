from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
from enum import Enum
from bson import ObjectId
from app.models.stock import PyObjectId


class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class APIKeyScope(str, Enum):
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class User(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER
    is_active: bool = True
    is_verified: bool = False
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    
    # API使用制限
    rate_limit_requests: int = Field(default=1000, description="1時間あたりのリクエスト数")
    rate_limit_window: int = Field(default=3600, description="制限期間（秒）")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class APIKey(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    key_id: str = Field(..., description="API キーID（公開）")
    key_hash: str = Field(..., description="API キーのハッシュ値")
    user_id: PyObjectId = Field(..., description="所有者のユーザーID")
    name: str = Field(..., description="API キーの名前")
    scopes: List[APIKeyScope] = Field(default=[APIKeyScope.READ])
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    
    # 使用統計
    total_requests: int = 0
    rate_limit_requests: int = Field(default=500, description="1時間あたりのリクエスト数")
    rate_limit_window: int = Field(default=3600, description="制限期間（秒）")
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    role: UserRole = UserRole.USER


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    rate_limit_requests: Optional[int] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    rate_limit_requests: int


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[APIKeyScope] = Field(default=[APIKeyScope.READ])
    expires_at: Optional[datetime] = None
    rate_limit_requests: int = Field(default=500, ge=1, le=10000)


class APIKeyResponse(BaseModel):
    key_id: str
    name: str
    scopes: List[APIKeyScope]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    total_requests: int
    rate_limit_requests: int


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class RateLimitInfo(BaseModel):
    requests_made: int
    requests_remaining: int
    reset_time: datetime
    limit: int
    window: int