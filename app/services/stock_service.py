from typing import List, Optional
from datetime import datetime
from app.services.database_service import database_service
from app.models.stock import DailyPrice, DailyPriceCreate, StockInfo, StockInfoCreate
from app.models.financials import Financial, FinancialCreate
from pymongo import ASCENDING
import logging

logger = logging.getLogger(__name__)


class StockService:
    def __init__(self):
        self.daily_prices_collection = "daily_prices"
        self.stock_info_collection = "stock_info"
        self.financials_collection = "financials"
    
    # 日足データのCRUD操作
    async def create_daily_price(self, daily_price_data: DailyPriceCreate) -> DailyPrice:
        """日足データを作成"""
        collection = database_service.get_collection(self.daily_prices_collection)
        
        daily_price = DailyPrice(**daily_price_data.dict())
        result = await collection.insert_one(daily_price.dict(by_alias=True))
        
        created_daily_price = await collection.find_one({"_id": result.inserted_id})
        return DailyPrice(**created_daily_price)
    
    async def get_daily_prices(
        self, 
        symbol: str, 
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[DailyPrice]:
        """日足データを取得"""
        collection = database_service.get_collection(self.daily_prices_collection)
        
        query = {"symbol": symbol}
        if start_date or end_date:
            date_query = {}
            if start_date:
                date_query["$gte"] = start_date
            if end_date:
                date_query["$lte"] = end_date
            query["date"] = date_query
        
        cursor = collection.find(query).sort("date", ASCENDING)
        daily_prices = []
        async for doc in cursor:
            daily_prices.append(DailyPrice(**doc))
        
        return daily_prices
    
    async def update_daily_price(self, symbol: str, date: str, daily_price_data: DailyPriceCreate) -> Optional[DailyPrice]:
        """日足データを更新"""
        collection = database_service.get_collection(self.daily_prices_collection)
        
        update_data = daily_price_data.dict()
        update_data["updated_at"] = datetime.utcnow()
        
        result = await collection.update_one(
            {"symbol": symbol, "date": date},
            {"$set": update_data}
        )
        
        if result.modified_count:
            updated_doc = await collection.find_one({"symbol": symbol, "date": date})
            return DailyPrice(**updated_doc)
        return None
    
    async def delete_daily_price(self, symbol: str, date: str) -> bool:
        """日足データを削除"""
        collection = database_service.get_collection(self.daily_prices_collection)
        result = await collection.delete_one({"symbol": symbol, "date": date})
        return result.deleted_count > 0
    
    # 銘柄情報のCRUD操作
    async def create_stock_info(self, stock_info_data: StockInfoCreate) -> StockInfo:
        """銘柄情報を作成"""
        collection = database_service.get_collection(self.stock_info_collection)
        
        stock_info = StockInfo(**stock_info_data.dict())
        result = await collection.insert_one(stock_info.dict(by_alias=True))
        
        created_stock_info = await collection.find_one({"_id": result.inserted_id})
        return StockInfo(**created_stock_info)
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """銘柄情報を取得"""
        collection = database_service.get_collection(self.stock_info_collection)
        doc = await collection.find_one({"symbol": symbol})
        return StockInfo(**doc) if doc else None
    
    async def update_stock_info(self, symbol: str, stock_info_data: StockInfoCreate) -> Optional[StockInfo]:
        """銘柄情報を更新"""
        collection = database_service.get_collection(self.stock_info_collection)
        
        update_data = stock_info_data.dict()
        update_data["updated_at"] = datetime.utcnow()
        
        result = await collection.update_one(
            {"symbol": symbol},
            {"$set": update_data}
        )
        
        if result.modified_count:
            updated_doc = await collection.find_one({"symbol": symbol})
            return StockInfo(**updated_doc)
        return None
    
    async def delete_stock_info(self, symbol: str) -> bool:
        """銘柄情報を削除"""
        collection = database_service.get_collection(self.stock_info_collection)
        result = await collection.delete_one({"symbol": symbol})
        return result.deleted_count > 0
    
    # 財務データのCRUD操作
    async def create_financial(self, financial_data: FinancialCreate) -> Financial:
        """財務データを作成"""
        collection = database_service.get_collection(self.financials_collection)
        
        financial = Financial(**financial_data.dict())
        result = await collection.insert_one(financial.dict(by_alias=True))
        
        created_financial = await collection.find_one({"_id": result.inserted_id})
        return Financial(**created_financial)
    
    async def get_financials(self, symbol: str, period_type: Optional[str] = None) -> List[Financial]:
        """財務データを取得"""
        collection = database_service.get_collection(self.financials_collection)
        
        query = {"symbol": symbol}
        if period_type:
            query["period_type"] = period_type
        
        cursor = collection.find(query).sort("period_end", ASCENDING)
        financials = []
        async for doc in cursor:
            financials.append(Financial(**doc))
        
        return financials
    
    async def search_stocks(self, query: str, market: Optional[str] = None) -> List[StockInfo]:
        """銘柄検索"""
        collection = database_service.get_collection(self.stock_info_collection)
        
        search_query = {
            "$or": [
                {"name": {"$regex": query, "$options": "i"}},
                {"symbol": {"$regex": query, "$options": "i"}}
            ]
        }
        
        if market:
            search_query["market"] = market
        
        cursor = collection.find(search_query).limit(20)
        stocks = []
        async for doc in cursor:
            stocks.append(StockInfo(**doc))
        
        return stocks


# グローバルインスタンス
stock_service = StockService()