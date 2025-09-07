from typing import List, Optional, Tuple
from datetime import datetime, timedelta, date
from app.services.stock_service import stock_service
from app.services.yfinance_service import yfinance_service
from app.services.error_handler import error_handler
from app.services.cache_service import cache_service
from app.models.stock import DailyPrice, DailyPriceCreate, StockInfo, StockInfoCreate
from app.models.financials import Financial, FinancialCreate
from app.models.errors import YFinanceException, DataFetchException, RateLimitException
import logging

logger = logging.getLogger(__name__)


class DataManager:
    """データの自動取得と管理を行うクラス"""
    
    def __init__(self):
        self.cache_duration_days = 1  # キャッシュ有効期間（日）
    
    async def ensure_stock_info(self, symbol: str) -> Optional[StockInfo]:
        """銘柄情報が存在しない場合は自動取得（キャッシュ機能付き）"""
        # まずキャッシュをチェック
        cached_info = cache_service.get_stock_info(symbol)
        if cached_info:
            logger.info(f"Stock info found in cache for {symbol}")
            return StockInfo(**cached_info) if isinstance(cached_info, dict) else cached_info
        
        # 次に既存データをチェック
        stock_info = await stock_service.get_stock_info(symbol)
        
        if stock_info:
            logger.info(f"Stock info found in database for {symbol}")
            # データベースから取得した情報をキャッシュに保存
            cache_service.set_stock_info(symbol, stock_info.dict())
            return stock_info
        
        # 存在しない場合はyfinanceから取得
        logger.info(f"Fetching stock info from yfinance for {symbol}")
        try:
            stock_info_create = await yfinance_service.get_stock_info(symbol)
            if stock_info_create:
                stock_info = await stock_service.create_stock_info(stock_info_create)
                logger.info(f"Successfully created stock info for {symbol}")
                # 新しく作成した情報をキャッシュに保存
                cache_service.set_stock_info(symbol, stock_info.dict())
                return stock_info
            else:
                logger.warning(f"Failed to fetch stock info from yfinance for {symbol}")
                return None
                
        except (YFinanceException, RateLimitException) as e:
            # カスタム例外はそのまま再発生させる
            raise e
            
        except Exception as e:
            logger.error(f"Unexpected error fetching stock info for {symbol}: {e}")
            raise DataFetchException(
                f"銘柄情報の取得中に予期しないエラーが発生しました: {str(e)}",
                details={"symbol": symbol}
            )
    
    async def get_daily_prices_with_auto_fetch(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        period: Optional[str] = None
    ) -> List[DailyPrice]:
        """日足データを取得し、不足分は自動でyfinanceから補完（キャッシュ機能付き）"""
        
        # まずキャッシュをチェック
        cached_data = cache_service.get_daily_prices(symbol, start_date, end_date, period)
        if cached_data:
            logger.info(f"Daily prices found in cache for {symbol}")
            return [DailyPrice(**item) if isinstance(item, dict) else item for item in cached_data]
        
        # 銘柄情報を確保
        await self.ensure_stock_info(symbol)
        
        # 既存データをチェック
        existing_data = await stock_service.get_daily_prices(symbol, start_date, end_date)
        
        # データが完全に存在する場合は既存データを返す
        if await self._is_data_complete(symbol, start_date, end_date, existing_data):
            logger.info(f"Complete data found in database for {symbol}")
            # 完全なデータをキャッシュに保存
            cache_service.set_daily_prices(symbol, [dp.dict() for dp in existing_data], start_date, end_date, period)
            return existing_data
        
        # 不足データをyfinanceから取得
        logger.info(f"Fetching missing data from yfinance for {symbol}")
        try:
            # 期間を決定
            fetch_period = period or "1y"
            
            # yfinanceからデータ取得
            new_data = await yfinance_service.get_historical_data(
                symbol, 
                period=fetch_period,
                start_date=start_date,
                end_date=end_date
            )
            
            if not new_data:
                logger.warning(f"No data retrieved from yfinance for {symbol}")
                return existing_data
            
            # 新しいデータを保存（重複は無視）
            saved_count = 0
            for daily_price_data in new_data:
                try:
                    # 既存データと重複チェック
                    if not await self._is_duplicate_data(daily_price_data, existing_data):
                        await stock_service.create_daily_price(daily_price_data)
                        saved_count += 1
                except Exception as e:
                    # 重複エラーは無視（ユニーク制約）
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        continue
                    logger.error(f"Error saving daily price data: {e}")
            
            logger.info(f"Saved {saved_count} new daily price records for {symbol}")
            
            # 更新された全データを取得して返す
            updated_data = await stock_service.get_daily_prices(symbol, start_date, end_date)
            # 更新されたデータをキャッシュに保存
            cache_service.set_daily_prices(symbol, [dp.dict() for dp in updated_data], start_date, end_date, period)
            return updated_data
            
        except Exception as e:
            logger.error(f"Error auto-fetching data for {symbol}: {e}")
            return existing_data
    
    async def _is_data_complete(
        self, 
        symbol: str, 
        start_date: Optional[str], 
        end_date: Optional[str], 
        existing_data: List[DailyPrice]
    ) -> bool:
        """データが完全かどうかをチェック"""
        
        if not existing_data:
            return False
        
        # 最新営業日のデータがあるかチェック
        if not start_date and not end_date:
            latest_date = max(dp.date for dp in existing_data)
            today = date.today()
            latest_data_date = datetime.strptime(latest_date, '%Y-%m-%d').date()
            
            # 最新データが1日以内の場合は完全とみなす
            if (today - latest_data_date).days <= 1:
                return True
        
        # 指定期間のデータの連続性をチェック（簡易版）
        if len(existing_data) > 200:  # 十分なデータ量がある場合は完全とみなす
            return True
        
        return False
    
    async def _is_duplicate_data(self, new_data: DailyPriceCreate, existing_data: List[DailyPrice]) -> bool:
        """重複データかどうかをチェック"""
        for existing in existing_data:
            if existing.symbol == new_data.symbol and existing.date == new_data.date:
                return True
        return False
    
    async def get_financials_with_auto_fetch(
        self,
        symbol: str,
        period_type: Optional[str] = None
    ) -> List[Financial]:
        """財務データを取得し、不足分は自動でyfinanceから補完"""
        
        # 銘柄情報を確保
        await self.ensure_stock_info(symbol)
        
        # 既存データをチェック
        existing_data = await stock_service.get_financials(symbol, period_type)
        
        # 最近のデータがある場合はそのまま返す（財務データは頻繁に更新されない）
        if existing_data and len(existing_data) > 0:
            latest_data = max(existing_data, key=lambda x: x.period_end)
            latest_date = datetime.strptime(latest_data.period_end, '%Y-%m-%d')
            
            # 90日以内のデータがある場合は既存データを返す
            if (datetime.now() - latest_date).days <= 90:
                logger.info(f"Recent financial data found for {symbol}")
                return existing_data
        
        # yfinanceから財務データを取得
        logger.info(f"Fetching financial data from yfinance for {symbol}")
        try:
            # 四半期と年次の両方を取得（period_typeが指定されていない場合）
            quarterly_data = []
            annual_data = []
            
            if not period_type or period_type == "quarterly":
                quarterly_data = await yfinance_service.get_financials(symbol, quarterly=True)
            
            if not period_type or period_type == "annual":
                annual_data = await yfinance_service.get_financials(symbol, quarterly=False)
            
            new_data = quarterly_data + annual_data
            
            if not new_data:
                logger.warning(f"No financial data retrieved from yfinance for {symbol}")
                return existing_data
            
            # 新しいデータを保存
            saved_count = 0
            for financial_data in new_data:
                try:
                    # 重複チェック（簡易版）
                    duplicate = False
                    for existing in existing_data:
                        if (existing.symbol == financial_data.symbol and 
                            existing.period_type == financial_data.period_type and 
                            existing.period_end == financial_data.period_end):
                            duplicate = True
                            break
                    
                    if not duplicate:
                        await stock_service.create_financial(financial_data)
                        saved_count += 1
                except Exception as e:
                    if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                        continue
                    logger.error(f"Error saving financial data: {e}")
            
            logger.info(f"Saved {saved_count} new financial records for {symbol}")
            
            # 更新された全データを取得して返す
            updated_data = await stock_service.get_financials(symbol, period_type)
            return updated_data
            
        except Exception as e:
            logger.error(f"Error auto-fetching financial data for {symbol}: {e}")
            return existing_data
    
    async def update_latest_data(self, symbol: str) -> bool:
        """最新データを更新（日次バッチ処理用）"""
        try:
            logger.info(f"Updating latest data for {symbol}")
            
            # 最新の営業日データを取得
            latest_data = await yfinance_service.get_historical_data(symbol, period="5d")
            
            if not latest_data:
                logger.warning(f"No latest data found for {symbol}")
                return False
            
            # 最新データのみを保存
            saved_count = 0
            for daily_price_data in latest_data[-2:]:  # 最新2日分
                try:
                    await stock_service.create_daily_price(daily_price_data)
                    saved_count += 1
                except Exception as e:
                    if "duplicate" not in str(e).lower():
                        logger.error(f"Error saving latest data: {e}")
            
            logger.info(f"Updated {saved_count} latest records for {symbol}")
            return saved_count > 0
            
        except Exception as e:
            logger.error(f"Error updating latest data for {symbol}: {e}")
            return False


# グローバルインスタンス
data_manager = DataManager()