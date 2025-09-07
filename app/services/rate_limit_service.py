from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.services.cache_service import cache_service
from app.models.auth import RateLimitInfo, User, APIKey
from app.config.settings import settings
import logging

logger = logging.getLogger("app.services.rate_limit")


class RateLimitService:
    def __init__(self):
        self.cache_prefix = "rate_limit"
        # デフォルトレート制限（未認証ユーザー）
        self.default_limit = settings.unauthenticated_rate_limit
        self.default_window = 3600  # 1時間
    
    def _get_cache_key(self, identifier: str, endpoint: Optional[str] = None) -> str:
        """レート制限用のキャッシュキーを生成"""
        if endpoint:
            return f"{self.cache_prefix}:{identifier}:{endpoint}"
        return f"{self.cache_prefix}:{identifier}"
    
    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window: int = 3600,
        endpoint: Optional[str] = None
    ) -> RateLimitInfo:
        """レート制限をチェック"""
        
        cache_key = self._get_cache_key(identifier, endpoint)
        
        # 現在の時刻
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window)
        
        # キャッシュから現在のカウントを取得
        current_data = cache_service.get("rate_limit_data", key=cache_key)
        
        if current_data is None:
            # 初回リクエスト
            current_data = {
                "requests": [],
                "count": 0
            }
        
        # 古いリクエストを削除（ウィンドウ外）
        recent_requests = [
            req_time for req_time in current_data["requests"]
            if datetime.fromisoformat(req_time) > window_start
        ]
        
        current_count = len(recent_requests)
        
        # レート制限チェック
        if current_count >= limit:
            # 制限超過
            oldest_request = min(recent_requests) if recent_requests else now.isoformat()
            reset_time = datetime.fromisoformat(oldest_request) + timedelta(seconds=window)
            
            return RateLimitInfo(
                requests_made=current_count,
                requests_remaining=0,
                reset_time=reset_time,
                limit=limit,
                window=window
            )
        
        # 新しいリクエストを記録
        recent_requests.append(now.isoformat())
        
        # キャッシュを更新
        updated_data = {
            "requests": recent_requests,
            "count": len(recent_requests)
        }
        
        # TTLはウィンドウサイズ + 余裕を持たせる
        cache_service.set("rate_limit_data", updated_data, ttl=window + 300, key=cache_key)
        
        # 次のリセット時刻を計算
        reset_time = now + timedelta(seconds=window)
        
        return RateLimitInfo(
            requests_made=len(recent_requests),
            requests_remaining=limit - len(recent_requests),
            reset_time=reset_time,
            limit=limit,
            window=window
        )
    
    async def check_user_rate_limit(self, user: User, endpoint: Optional[str] = None) -> RateLimitInfo:
        """認証されたユーザーのレート制限をチェック"""
        identifier = f"user:{user.id}"
        
        return await self.check_rate_limit(
            identifier=identifier,
            limit=user.rate_limit_requests,
            window=user.rate_limit_window,
            endpoint=endpoint
        )
    
    async def check_api_key_rate_limit(self, api_key: APIKey, endpoint: Optional[str] = None) -> RateLimitInfo:
        """APIキーのレート制限をチェック"""
        identifier = f"api_key:{api_key.key_id}"
        
        return await self.check_rate_limit(
            identifier=identifier,
            limit=api_key.rate_limit_requests,
            window=api_key.rate_limit_window,
            endpoint=endpoint
        )
    
    async def check_ip_rate_limit(self, ip_address: str, endpoint: Optional[str] = None) -> RateLimitInfo:
        """IPアドレスベースのレート制限をチェック（未認証）"""
        identifier = f"ip:{ip_address}"
        
        return await self.check_rate_limit(
            identifier=identifier,
            limit=self.default_limit,
            window=self.default_window,
            endpoint=endpoint
        )
    
    async def reset_rate_limit(self, identifier: str, endpoint: Optional[str] = None):
        """レート制限をリセット（管理者用）"""
        cache_key = self._get_cache_key(identifier, endpoint)
        cache_service.delete("rate_limit_data", key=cache_key)
        logger.info(f"Rate limit reset for: {identifier}")
    
    async def get_rate_limit_stats(self, identifier: str) -> Dict[str, Any]:
        """レート制限統計を取得"""
        cache_key = self._get_cache_key(identifier)
        
        current_data = cache_service.get("rate_limit_data", key=cache_key)
        
        if not current_data:
            return {
                "total_requests": 0,
                "recent_requests": 0,
                "first_request": None,
                "last_request": None
            }
        
        requests = current_data.get("requests", [])
        
        if not requests:
            return {
                "total_requests": 0,
                "recent_requests": 0,
                "first_request": None,
                "last_request": None
            }
        
        # 過去1時間のリクエスト数
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        recent_requests = [
            req for req in requests
            if datetime.fromisoformat(req) > one_hour_ago
        ]
        
        return {
            "total_requests": len(requests),
            "recent_requests": len(recent_requests),
            "first_request": min(requests) if requests else None,
            "last_request": max(requests) if requests else None
        }
    
    def is_rate_limited(self, rate_limit_info: RateLimitInfo) -> bool:
        """レート制限に達しているかチェック"""
        return rate_limit_info.requests_remaining <= 0
    
    async def increment_request_count(self, identifier: str, endpoint: Optional[str] = None):
        """リクエストカウントを増加（レート制限チェック後に呼び出し）"""
        # この関数は check_rate_limit 内で既に処理されているため、
        # 追加の統計情報が必要な場合のみ使用
        pass
    
    async def get_global_rate_limit_stats(self) -> Dict[str, Any]:
        """グローバルレート制限統計を取得"""
        cache_stats = cache_service.get_stats()
        
        # レート制限関連のキャッシュエントリ数をカウント
        rate_limit_entries = cache_stats.get("entries_by_prefix", {}).get("rate_limit_data", 0)
        
        return {
            "active_rate_limits": rate_limit_entries,
            "cache_stats": cache_stats
        }


# グローバルインスタンス
rate_limit_service = RateLimitService()