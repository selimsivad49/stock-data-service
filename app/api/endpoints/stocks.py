from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Optional
from app.models.stock import DailyPrice, DailyPriceCreate, StockInfo, StockInfoCreate
from app.services.stock_service import stock_service
from app.services.data_manager import data_manager
from app.services.error_handler import error_handler
from app.models.errors import YFinanceException, DataFetchException, RateLimitException
from app.models.auth import APIKeyScope
from app.middleware.auth_middleware import (
    AuthContext, get_auth_context, require_read_access, require_write_access, check_rate_limit
)

router = APIRouter()


@router.get("/{symbol}/daily", response_model=List[DailyPrice])
async def get_daily_prices(
    symbol: str,
    start_date: Optional[str] = Query(None, description="開始日 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="終了日 (YYYY-MM-DD)"),
    period: Optional[str] = Query(None, description="期間指定 (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)"),
    auth_context: AuthContext = Depends(require_read_access),
    _rate_limit = Depends(check_rate_limit)
):
    """銘柄の日足データを取得（不足分は自動でyfinanceから取得）"""
    try:
        # 自動データ取得機能付きで日足データを取得
        daily_prices = await data_manager.get_daily_prices_with_auto_fetch(
            symbol=symbol.upper(),
            start_date=start_date,
            end_date=end_date,
            period=period
        )
        
        if not daily_prices:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": {
                        "code": "STOCK_NOT_FOUND",
                        "message": "指定された銘柄が見つかりません",
                        "details": {"symbol": symbol}
                    }
                }
            )
        
        return daily_prices
    except HTTPException:
        raise
    except (YFinanceException, DataFetchException, RateLimitException) as e:
        raise error_handler.handle_custom_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "error": {
                    "code": "DATA_UNAVAILABLE",
                    "message": "データが取得できません",
                    "details": {"error": str(e)}
                }
            }
        )


@router.post("/{symbol}/daily", response_model=DailyPrice)
async def create_daily_price(
    symbol: str, 
    daily_price: DailyPriceCreate,
    auth_context: AuthContext = Depends(require_write_access),
    _rate_limit = Depends(check_rate_limit)
):
    """日足データを作成"""
    try:
        daily_price.symbol = symbol.upper()
        return await stock_service.create_daily_price(daily_price)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ作成エラー: {str(e)}")


@router.put("/{symbol}/daily/{date}", response_model=DailyPrice)
async def update_daily_price(symbol: str, date: str, daily_price: DailyPriceCreate):
    """日足データを更新"""
    try:
        daily_price.symbol = symbol.upper()
        updated_price = await stock_service.update_daily_price(
            symbol=symbol.upper(), 
            date=date, 
            daily_price_data=daily_price
        )
        if not updated_price:
            raise HTTPException(status_code=404, detail="データが見つかりません")
        return updated_price
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ更新エラー: {str(e)}")


@router.delete("/{symbol}/daily/{date}")
async def delete_daily_price(symbol: str, date: str):
    """日足データを削除"""
    try:
        deleted = await stock_service.delete_daily_price(symbol.upper(), date)
        if not deleted:
            raise HTTPException(status_code=404, detail="データが見つかりません")
        return {"message": "データを削除しました"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ削除エラー: {str(e)}")


@router.get("/{symbol}/info", response_model=StockInfo)
async def get_stock_info(symbol: str):
    """銘柄情報を取得（存在しない場合は自動でyfinanceから取得）"""
    try:
        # 自動取得機能付きで銘柄情報を取得
        stock_info = await data_manager.ensure_stock_info(symbol.upper())
        
        if not stock_info:
            raise HTTPException(
                status_code=404, 
                detail={
                    "error": {
                        "code": "STOCK_NOT_FOUND",
                        "message": "指定された銘柄が見つかりません",
                        "details": {"symbol": symbol}
                    }
                }
            )
        
        return stock_info
    except HTTPException:
        raise
    except (YFinanceException, DataFetchException, RateLimitException) as e:
        raise error_handler.handle_custom_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail={
                "error": {
                    "code": "DATA_UNAVAILABLE",
                    "message": "データが取得できません",
                    "details": {"error": str(e)}
                }
            }
        )


@router.post("/{symbol}/info", response_model=StockInfo)
async def create_stock_info(symbol: str, stock_info: StockInfoCreate):
    """銘柄情報を作成"""
    try:
        stock_info.symbol = symbol.upper()
        return await stock_service.create_stock_info(stock_info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ作成エラー: {str(e)}")


@router.put("/{symbol}/info", response_model=StockInfo)
async def update_stock_info(symbol: str, stock_info: StockInfoCreate):
    """銘柄情報を更新"""
    try:
        stock_info.symbol = symbol.upper()
        updated_info = await stock_service.update_stock_info(symbol.upper(), stock_info)
        if not updated_info:
            raise HTTPException(status_code=404, detail="銘柄情報が見つかりません")
        return updated_info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ更新エラー: {str(e)}")


@router.delete("/{symbol}/info")
async def delete_stock_info(symbol: str):
    """銘柄情報を削除"""
    try:
        deleted = await stock_service.delete_stock_info(symbol.upper())
        if not deleted:
            raise HTTPException(status_code=404, detail="銘柄情報が見つかりません")
        return {"message": "銘柄情報を削除しました"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ削除エラー: {str(e)}")


@router.get("/search", response_model=List[StockInfo])
async def search_stocks(
    query: str = Query(..., description="検索キーワード"),
    market: Optional[str] = Query(None, description="市場 (jp | us)")
):
    """銘柄検索"""
    try:
        stocks = await stock_service.search_stocks(query, market)
        return stocks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"検索エラー: {str(e)}")