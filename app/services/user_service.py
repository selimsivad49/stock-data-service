from typing import Optional, List
from datetime import datetime
from fastapi import HTTPException, status
from app.services.database_service import database_service
from app.services.auth_service import auth_service
from app.models.auth import User, UserCreate, UserUpdate, UserResponse, UserRole
from pymongo import ASCENDING
import logging

logger = logging.getLogger("app.services.user")


class UserService:
    def __init__(self):
        self.collection_name = "users"
    
    async def create_user(self, user_data: UserCreate) -> User:
        """新規ユーザーを作成"""
        collection = database_service.get_collection(self.collection_name)
        
        # ユーザー名とメールの重複チェック
        existing_user = await collection.find_one({
            "$or": [
                {"username": user_data.username},
                {"email": user_data.email}
            ]
        })
        
        if existing_user:
            if existing_user.get("username") == user_data.username:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists"
                )
        
        # パスワード強度チェック
        if not auth_service.validate_password_strength(user_data.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters and contain uppercase, lowercase, number, and special character"
            )
        
        # ユーザー作成
        hashed_password = auth_service.get_password_hash(user_data.password)
        
        user = User(
            username=user_data.username,
            email=user_data.email,
            full_name=user_data.full_name,
            role=user_data.role,
            hashed_password=hashed_password
        )
        
        result = await collection.insert_one(user.dict(by_alias=True))
        
        created_user = await collection.find_one({"_id": result.inserted_id})
        logger.info(f"User created: {user_data.username}")
        
        return User(**created_user)
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """ユーザー名でユーザーを取得"""
        collection = database_service.get_collection(self.collection_name)
        user_doc = await collection.find_one({"username": username})
        
        if user_doc:
            return User(**user_doc)
        return None
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """ユーザーIDでユーザーを取得"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        try:
            user_doc = await collection.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                return User(**user_doc)
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
        
        return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """メールアドレスでユーザーを取得"""
        collection = database_service.get_collection(self.collection_name)
        user_doc = await collection.find_one({"email": email})
        
        if user_doc:
            return User(**user_doc)
        return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """ユーザー認証"""
        user = await self.get_user_by_username(username)
        
        if not user:
            return None
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is disabled"
            )
        
        if not auth_service.verify_password(password, user.hashed_password):
            return None
        
        # ログイン時刻を更新
        await self.update_last_login(str(user.id))
        
        logger.info(f"User authenticated: {username}")
        return user
    
    async def update_user(self, user_id: str, user_update: UserUpdate) -> Optional[User]:
        """ユーザー情報を更新"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        update_data = user_update.dict(exclude_none=True)
        if update_data:
            update_data["updated_at"] = datetime.utcnow()
            
            result = await collection.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            
            if result.modified_count:
                updated_user = await collection.find_one({"_id": ObjectId(user_id)})
                logger.info(f"User updated: {user_id}")
                return User(**updated_user)
        
        return None
    
    async def update_last_login(self, user_id: str):
        """最終ログイン時刻を更新"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        await collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.utcnow()}}
        )
    
    async def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """パスワード変更"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # 現在のパスワードを確認
        if not auth_service.verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # 新しいパスワードの強度チェック
        if not auth_service.validate_password_strength(new_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters and contain uppercase, lowercase, number, and special character"
            )
        
        # パスワード更新
        hashed_password = auth_service.get_password_hash(new_password)
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        result = await collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "hashed_password": hashed_password,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Password changed for user: {user_id}")
        return result.modified_count > 0
    
    async def list_users(self, skip: int = 0, limit: int = 100, role: Optional[UserRole] = None) -> List[UserResponse]:
        """ユーザー一覧を取得"""
        collection = database_service.get_collection(self.collection_name)
        
        query = {}
        if role:
            query["role"] = role.value
        
        cursor = collection.find(query).skip(skip).limit(limit).sort("created_at", ASCENDING)
        
        users = []
        async for user_doc in cursor:
            user = User(**user_doc)
            users.append(UserResponse(
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
            ))
        
        return users
    
    async def delete_user(self, user_id: str) -> bool:
        """ユーザーを削除（論理削除）"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        result = await collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count:
            logger.info(f"User deactivated: {user_id}")
            return True
        
        return False
    
    async def get_user_count(self, role: Optional[UserRole] = None) -> int:
        """ユーザー数を取得"""
        collection = database_service.get_collection(self.collection_name)
        
        query = {"is_active": True}
        if role:
            query["role"] = role.value
        
        return await collection.count_documents(query)


# グローバルインスタンス
user_service = UserService()