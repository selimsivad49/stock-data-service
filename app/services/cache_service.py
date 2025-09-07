from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import json
import hashlib
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """インメモリキャッシュサービス"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._default_ttl = 3600  # 1時間
        self._stock_info_ttl = 86400  # 24時間（銘柄情報は長期キャッシュ）
        self._daily_prices_ttl = 3600  # 1時間（日足データ）
        self._financials_ttl = 21600  # 6時間（財務データ）
    
    def _generate_key(self, prefix: str, **kwargs) -> str:
        """キャッシュキーを生成"""
        key_data = json.dumps(kwargs, sort_keys=True)
        hash_object = hashlib.md5(key_data.encode())
        return f"{prefix}:{hash_object.hexdigest()}"
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """キャッシュが期限切れかチェック"""
        expiry_time = cache_entry.get('expires_at')
        if not expiry_time:
            return True
        return datetime.now() > expiry_time
    
    def _cleanup_expired(self):
        """期限切れのキャッシュをクリーンアップ"""
        expired_keys = []
        for key, value in self._cache.items():
            if self._is_expired(value):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get(self, prefix: str, **kwargs) -> Optional[Any]:
        """キャッシュからデータを取得"""
        key = self._generate_key(prefix, **kwargs)
        
        if key in self._cache:
            cache_entry = self._cache[key]
            if not self._is_expired(cache_entry):
                logger.debug(f"Cache hit for key: {key}")
                return cache_entry['data']
            else:
                # 期限切れのエントリを削除
                del self._cache[key]
                logger.debug(f"Cache expired for key: {key}")
        
        logger.debug(f"Cache miss for key: {key}")
        return None
    
    def set(self, prefix: str, data: Any, ttl: Optional[int] = None, **kwargs):
        """キャッシュにデータを保存"""
        key = self._generate_key(prefix, **kwargs)
        
        if ttl is None:
            if prefix == "stock_info":
                ttl = self._stock_info_ttl
            elif prefix == "daily_prices":
                ttl = self._daily_prices_ttl
            elif prefix == "financials":
                ttl = self._financials_ttl
            else:
                ttl = self._default_ttl
        
        expires_at = datetime.now() + timedelta(seconds=ttl)
        
        self._cache[key] = {
            'data': data,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
        
        logger.debug(f"Cache set for key: {key}, TTL: {ttl}s")
        
        # 定期的にクリーンアップ（10回に1回）
        if len(self._cache) % 10 == 0:
            self._cleanup_expired()
    
    def delete(self, prefix: str, **kwargs):
        """特定のキャッシュエントリを削除"""
        key = self._generate_key(prefix, **kwargs)
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache deleted for key: {key}")
    
    def clear(self, prefix: Optional[str] = None):
        """キャッシュをクリア"""
        if prefix:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(f"{prefix}:")]
            for key in keys_to_delete:
                del self._cache[key]
            logger.info(f"Cleared {len(keys_to_delete)} cache entries with prefix: {prefix}")
        else:
            self._cache.clear()
            logger.info("Cleared all cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        total_entries = len(self._cache)
        expired_count = sum(1 for v in self._cache.values() if self._is_expired(v))
        
        prefixes = {}
        for key in self._cache.keys():
            prefix = key.split(':')[0]
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
        
        return {
            'total_entries': total_entries,
            'expired_entries': expired_count,
            'active_entries': total_entries - expired_count,
            'entries_by_prefix': prefixes
        }
    
    # 特定のデータタイプ用の便利メソッド
    def get_stock_info(self, symbol: str) -> Optional[Any]:
        """銘柄情報キャッシュを取得"""
        return self.get("stock_info", symbol=symbol)
    
    def set_stock_info(self, symbol: str, data: Any):
        """銘柄情報キャッシュを設定"""
        self.set("stock_info", data, symbol=symbol)
    
    def get_daily_prices(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None, period: Optional[str] = None) -> Optional[Any]:
        """日足データキャッシュを取得"""
        return self.get("daily_prices", symbol=symbol, start_date=start_date, end_date=end_date, period=period)
    
    def set_daily_prices(self, symbol: str, data: Any, start_date: Optional[str] = None, end_date: Optional[str] = None, period: Optional[str] = None):
        """日足データキャッシュを設定"""
        self.set("daily_prices", data, symbol=symbol, start_date=start_date, end_date=end_date, period=period)
    
    def get_financials(self, symbol: str, period_type: Optional[str] = None) -> Optional[Any]:
        """財務データキャッシュを取得"""
        return self.get("financials", symbol=symbol, period_type=period_type)
    
    def set_financials(self, symbol: str, data: Any, period_type: Optional[str] = None):
        """財務データキャッシュを設定"""
        self.set("financials", data, symbol=symbol, period_type=period_type)


# グローバルインスタンス
cache_service = CacheService()