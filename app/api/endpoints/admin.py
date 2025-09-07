from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from app.services.cache_service import cache_service
from app.services.data_manager import data_manager

router = APIRouter()


@router.get("/cache/stats")
async def get_cache_stats() -> Dict[str, Any]:
    """キャッシュ統計情報を取得"""
    try:
        stats = cache_service.get_stats()
        return {
            "cache_stats": stats,
            "status": "healthy"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"キャッシュ統計取得エラー: {str(e)}")


@router.post("/cache/clear")
async def clear_cache(prefix: str = None):
    """キャッシュをクリア"""
    try:
        cache_service.clear(prefix)
        return {
            "message": f"キャッシュがクリアされました" + (f" (prefix: {prefix})" if prefix else ""),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"キャッシュクリアエラー: {str(e)}")


@router.post("/stocks/{symbol}/update")
async def force_update_stock_data(symbol: str):
    """特定銘柄のデータを強制更新"""
    try:
        # キャッシュをクリア
        cache_service.delete("stock_info", symbol=symbol)
        cache_service.delete("daily_prices", symbol=symbol)
        cache_service.delete("financials", symbol=symbol)
        
        # 最新データを更新
        updated = await data_manager.update_latest_data(symbol.upper())
        
        return {
            "message": f"銘柄 {symbol} のデータを更新しました",
            "updated": updated,
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ更新エラー: {str(e)}")


@router.get("/system/status")
async def get_system_status():
    """システム全体のステータスを取得"""
    try:
        cache_stats = cache_service.get_stats()
        
        return {
            "status": "healthy",
            "cache": {
                "status": "active",
                "entries": cache_stats["total_entries"],
                "active_entries": cache_stats["active_entries"]
            },
            "services": {
                "yfinance": "active",
                "database": "active",
                "cache": "active"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"システムステータス取得エラー: {str(e)}")