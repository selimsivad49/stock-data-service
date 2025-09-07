from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import Optional
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.database: Optional[AsyncIOMotorDatabase] = None
    
    async def connect(self):
        """MongoDB接続を開始"""
        try:
            self.client = AsyncIOMotorClient(settings.mongodb_url)
            self.database = self.client[settings.database_name]
            
            # 接続テスト
            await self.client.admin.command('ping')
            logger.info(f"MongoDB connected successfully to {settings.database_name}")
            
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            raise
    
    async def disconnect(self):
        """MongoDB接続を切断"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    async def health_check(self) -> bool:
        """データベース接続の健康状態をチェック"""
        try:
            if self.client:
                await self.client.admin.command('ping')
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
        return False
    
    def get_collection(self, collection_name: str):
        """指定されたコレクションを取得"""
        if not self.database:
            raise Exception("Database not connected")
        return self.database[collection_name]


# グローバルインスタンス
database_service = DatabaseService()