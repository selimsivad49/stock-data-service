from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from app.services.database_service import database_service
from app.services.auth_service import auth_service
from app.models.auth import APIKey, APIKeyCreate, APIKeyResponse, APIKeyScope
from pymongo import ASCENDING
import logging

logger = logging.getLogger("app.services.api_key")


class APIKeyService:
    def __init__(self):
        self.collection_name = "api_keys"
    
    async def create_api_key(self, user_id: str, api_key_data: APIKeyCreate) -> tuple[APIKeyResponse, str]:
        """新しいAPIキーを作成"""
        collection = database_service.get_collection(self.collection_name)
        
        # APIキーを生成
        key_id, raw_api_key = auth_service.generate_api_key()
        key_hash = auth_service.hash_api_key(raw_api_key)
        
        # 有効期限を設定
        expires_at = None
        if api_key_data.expires_at:
            expires_at = api_key_data.expires_at
        
        # APIキーオブジェクトを作成
        from bson import ObjectId
        api_key = APIKey(
            key_id=key_id,
            key_hash=key_hash,
            user_id=ObjectId(user_id),
            name=api_key_data.name,
            scopes=api_key_data.scopes,
            expires_at=expires_at,
            rate_limit_requests=api_key_data.rate_limit_requests
        )
        
        result = await collection.insert_one(api_key.dict(by_alias=True))
        
        created_api_key = await collection.find_one({"_id": result.inserted_id})
        
        logger.info(f"API key created for user {user_id}: {key_id}")
        
        # レスポンス用のAPIキー情報
        api_key_response = APIKeyResponse(
            key_id=key_id,
            name=api_key_data.name,
            scopes=api_key_data.scopes,
            is_active=True,
            created_at=api_key.created_at,
            expires_at=expires_at,
            total_requests=0,
            rate_limit_requests=api_key_data.rate_limit_requests
        )
        
        return api_key_response, raw_api_key
    
    async def get_api_key_by_key_id(self, key_id: str) -> Optional[APIKey]:
        """キーIDでAPIキーを取得"""
        collection = database_service.get_collection(self.collection_name)
        api_key_doc = await collection.find_one({"key_id": key_id})
        
        if api_key_doc:
            return APIKey(**api_key_doc)
        return None
    
    async def authenticate_api_key(self, key_id: str, raw_api_key: str) -> Optional[APIKey]:
        """APIキーを認証"""
        api_key = await self.get_api_key_by_key_id(key_id)
        
        if not api_key:
            return None
        
        if not api_key.is_active:
            return None
        
        # 有効期限チェック
        if api_key.expires_at and datetime.utcnow() > api_key.expires_at:
            logger.warning(f"API key expired: {key_id}")
            return None
        
        # キーの検証
        if not auth_service.verify_api_key(raw_api_key, api_key.key_hash):
            return None
        
        # 最終使用時刻を更新
        await self.update_last_used(key_id)
        
        logger.info(f"API key authenticated: {key_id}")
        return api_key
    
    async def update_last_used(self, key_id: str):
        """最終使用時刻を更新"""
        collection = database_service.get_collection(self.collection_name)
        
        await collection.update_one(
            {"key_id": key_id},
            {
                "$set": {"last_used": datetime.utcnow()},
                "$inc": {"total_requests": 1}
            }
        )
    
    async def list_user_api_keys(self, user_id: str) -> List[APIKeyResponse]:
        """ユーザーのAPIキー一覧を取得"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        cursor = collection.find({
            "user_id": ObjectId(user_id),
            "is_active": True
        }).sort("created_at", ASCENDING)
        
        api_keys = []
        async for api_key_doc in cursor:
            api_key = APIKey(**api_key_doc)
            api_keys.append(APIKeyResponse(
                key_id=api_key.key_id,
                name=api_key.name,
                scopes=api_key.scopes,
                is_active=api_key.is_active,
                created_at=api_key.created_at,
                expires_at=api_key.expires_at,
                last_used=api_key.last_used,
                total_requests=api_key.total_requests,
                rate_limit_requests=api_key.rate_limit_requests
            ))
        
        return api_keys
    
    async def revoke_api_key(self, user_id: str, key_id: str) -> bool:
        """APIキーを無効化"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        result = await collection.update_one(
            {
                "key_id": key_id,
                "user_id": ObjectId(user_id)
            },
            {"$set": {"is_active": False}}
        )
        
        if result.modified_count:
            logger.info(f"API key revoked: {key_id}")
            return True
        
        return False
    
    async def delete_api_key(self, user_id: str, key_id: str) -> bool:
        """APIキーを削除"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        result = await collection.delete_one({
            "key_id": key_id,
            "user_id": ObjectId(user_id)
        })
        
        if result.deleted_count:
            logger.info(f"API key deleted: {key_id}")
            return True
        
        return False
    
    async def get_api_key_stats(self, user_id: str) -> dict:
        """ユーザーのAPIキー統計を取得"""
        collection = database_service.get_collection(self.collection_name)
        from bson import ObjectId
        
        pipeline = [
            {"$match": {"user_id": ObjectId(user_id), "is_active": True}},
            {
                "$group": {
                    "_id": None,
                    "total_keys": {"$sum": 1},
                    "total_requests": {"$sum": "$total_requests"},
                    "last_used": {"$max": "$last_used"}
                }
            }
        ]
        
        result = await collection.aggregate(pipeline).to_list(1)
        
        if result:
            stats = result[0]
            return {
                "total_keys": stats.get("total_keys", 0),
                "total_requests": stats.get("total_requests", 0),
                "last_used": stats.get("last_used")
            }
        
        return {
            "total_keys": 0,
            "total_requests": 0,
            "last_used": None
        }
    
    async def cleanup_expired_keys(self):
        """期限切れのAPIキーを無効化"""
        collection = database_service.get_collection(self.collection_name)
        
        result = await collection.update_many(
            {
                "expires_at": {"$lt": datetime.utcnow()},
                "is_active": True
            },
            {"$set": {"is_active": False}}
        )
        
        if result.modified_count:
            logger.info(f"Deactivated {result.modified_count} expired API keys")
        
        return result.modified_count
    
    async def has_scope(self, api_key: APIKey, required_scope: APIKeyScope) -> bool:
        """APIキーが必要なスコープを持っているかチェック"""
        if APIKeyScope.ADMIN in api_key.scopes:
            return True
        
        return required_scope in api_key.scopes


# グローバルインスタンス
api_key_service = APIKeyService()