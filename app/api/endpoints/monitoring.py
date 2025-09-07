from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import time
import psutil
import os
from datetime import datetime
from app.services.database_service import database_service
from app.services.cache_service import cache_service

router = APIRouter()


@router.get("/readiness")
async def readiness_check():
    """Kubernetes readiness probe endpoint"""
    try:
        # データベース接続の簡易チェック
        db_status = await database_service.health_check()
        
        if db_status:
            return {
                "status": "ready",
                "timestamp": datetime.utcnow().isoformat()
            }
        else:
            raise HTTPException(status_code=503, detail="Service not ready")
            
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")


@router.get("/liveness")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": time.time() - psutil.boot_time()
    }


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """基本的なメトリクス情報を取得"""
    try:
        # システムメトリクス
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # プロセスメトリクス
        process = psutil.Process(os.getpid())
        process_memory = process.memory_info()
        
        # キャッシュメトリクス
        cache_stats = cache_service.get_stats()
        
        # データベースメトリクス（簡易）
        db_status = await database_service.health_check()
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_mb": round(memory.total / 1024 / 1024, 2),
                    "available_mb": round(memory.available / 1024 / 1024, 2),
                    "used_percent": memory.percent
                },
                "disk": {
                    "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                    "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                    "used_percent": (disk.used / disk.total) * 100
                }
            },
            "process": {
                "memory_mb": round(process_memory.rss / 1024 / 1024, 2),
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
            },
            "application": {
                "cache": {
                    "total_entries": cache_stats["total_entries"],
                    "active_entries": cache_stats["active_entries"],
                    "expired_entries": cache_stats["expired_entries"],
                    "entries_by_type": cache_stats["entries_by_prefix"]
                },
                "database": {
                    "status": "connected" if db_status else "disconnected"
                }
            }
        }
        
        return metrics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"メトリクス取得エラー: {str(e)}")


@router.get("/info")
async def get_service_info():
    """サービス情報を取得"""
    return {
        "service_name": "stock-data-service",
        "version": "2.0.0",
        "description": "株価データ管理サービス（yfinance統合版）",
        "author": "Claude Code",
        "timestamp": datetime.utcnow().isoformat(),
        "python_version": f"{psutil.sys.version_info.major}.{psutil.sys.version_info.minor}.{psutil.sys.version_info.micro}",
        "environment": os.getenv("DEBUG", "false"),
        "features": [
            "自動データ取得",
            "インメモリキャッシュ",
            "包括的エラーハンドリング",
            "日本株・米国株対応",
            "レート制限機能",
            "ヘルスチェック",
            "メトリクス監視"
        ]
    }