import yfinance as yf
import pandas as pd
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from app.config.settings import settings
from app.models.stock import DailyPriceCreate, StockInfoCreate
from app.models.financials import FinancialCreate
from app.models.errors import YFinanceException, RateLimitException, ErrorCode
import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import requests.exceptions

logger = logging.getLogger(__name__)


class YFinanceService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1秒間隔でリクエスト制限
    
    def _rate_limit(self):
        """レート制限を適用"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    async def _run_in_executor(self, func, *args):
        """非同期でyfinanceの同期関数を実行"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)
    
    def _fetch_ticker_data(self, symbol: str, period: str = "1y") -> Optional[yf.Ticker]:
        """yfinanceからティッカーデータを取得（同期）"""
        try:
            self._rate_limit()
            ticker = yf.Ticker(symbol)
            
            # データ取得テスト
            hist = ticker.history(period="5d")
            if hist.empty:
                logger.warning(f"No data found for symbol: {symbol}")
                raise YFinanceException(
                    f"No data found for symbol: {symbol}",
                    code=ErrorCode.STOCK_NOT_FOUND,
                    details={"symbol": symbol}
                )
            
            return ticker
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Network connection error for {symbol}: {e}")
            raise YFinanceException(
                "ネットワーク接続エラーが発生しました",
                code=ErrorCode.NETWORK_ERROR,
                details={"symbol": symbol, "error": str(e)}
            )
        
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout error for {symbol}: {e}")
            raise YFinanceException(
                "リクエストがタイムアウトしました",
                code=ErrorCode.NETWORK_ERROR,
                details={"symbol": symbol, "error": str(e)}
            )
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.error(f"Rate limit exceeded for {symbol}")
                raise RateLimitException(
                    "APIレート制限に達しました",
                    details={"symbol": symbol}
                )
            else:
                logger.error(f"HTTP error for {symbol}: {e}")
                raise YFinanceException(
                    f"HTTPエラーが発生しました: {e.response.status_code}",
                    code=ErrorCode.YFINANCE_ERROR,
                    details={"symbol": symbol, "status_code": e.response.status_code}
                )
        
        except Exception as e:
            logger.error(f"Failed to fetch ticker data for {symbol}: {e}")
            if "No data found" in str(e) or "No timezone found" in str(e):
                raise YFinanceException(
                    f"銘柄が見つかりません: {symbol}",
                    code=ErrorCode.STOCK_NOT_FOUND,
                    details={"symbol": symbol}
                )
            else:
                raise YFinanceException(
                    f"データ取得中にエラーが発生しました: {str(e)}",
                    code=ErrorCode.YFINANCE_ERROR,
                    details={"symbol": symbol, "error": str(e)}
                )
    
    async def get_ticker_data(self, symbol: str) -> Optional[yf.Ticker]:
        """yfinanceからティッカーデータを非同期で取得"""
        return await self._run_in_executor(self._fetch_ticker_data, symbol)
    
    def _fetch_historical_data(self, ticker: yf.Ticker, period: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """履歴データを取得（同期）"""
        try:
            self._rate_limit()
            
            if start_date and end_date:
                hist = ticker.history(start=start_date, end=end_date)
            else:
                hist = ticker.history(period=period)
            
            return hist
        except Exception as e:
            logger.error(f"Failed to fetch historical data: {e}")
            return pd.DataFrame()
    
    async def get_historical_data(
        self, 
        symbol: str, 
        period: str = "1y",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[DailyPriceCreate]:
        """株価履歴データを取得してDailyPriceCreateのリストに変換"""
        ticker = await self.get_ticker_data(symbol)
        if not ticker:
            return []
        
        hist = await self._run_in_executor(
            self._fetch_historical_data, 
            ticker, 
            period, 
            start_date, 
            end_date
        )
        
        if hist.empty:
            logger.warning(f"No historical data found for {symbol}")
            return []
        
        daily_prices = []
        for date, row in hist.iterrows():
            try:
                daily_price = DailyPriceCreate(
                    symbol=symbol,
                    date=date.strftime('%Y-%m-%d'),
                    open=float(row['Open']) if pd.notna(row['Open']) else 0.0,
                    high=float(row['High']) if pd.notna(row['High']) else 0.0,
                    low=float(row['Low']) if pd.notna(row['Low']) else 0.0,
                    close=float(row['Close']) if pd.notna(row['Close']) else 0.0,
                    adj_close=float(row['Close']) if pd.notna(row['Close']) else 0.0,
                    volume=int(row['Volume']) if pd.notna(row['Volume']) else 0
                )
                daily_prices.append(daily_price)
            except Exception as e:
                logger.error(f"Error processing data for {symbol} on {date}: {e}")
                continue
        
        logger.info(f"Fetched {len(daily_prices)} daily prices for {symbol}")
        return daily_prices
    
    def _fetch_stock_info(self, ticker: yf.Ticker) -> Dict[str, Any]:
        """銘柄情報を取得（同期）"""
        try:
            self._rate_limit()
            return ticker.info
        except Exception as e:
            logger.error(f"Failed to fetch stock info: {e}")
            return {}
    
    async def get_stock_info(self, symbol: str) -> Optional[StockInfoCreate]:
        """銘柄情報を取得してStockInfoCreateに変換"""
        ticker = await self.get_ticker_data(symbol)
        if not ticker:
            return None
        
        info = await self._run_in_executor(self._fetch_stock_info, ticker)
        if not info:
            return None
        
        try:
            # 日本株かアメリカ株かを判定
            market = "jp" if ".T" in symbol else "us"
            
            stock_info = StockInfoCreate(
                symbol=symbol,
                name=info.get('longName', info.get('shortName', symbol)),
                sector=info.get('sector'),
                industry=info.get('industry'),
                market=market,
                currency=info.get('currency', 'JPY' if market == 'jp' else 'USD'),
                exchange=info.get('exchange')
            )
            
            logger.info(f"Fetched stock info for {symbol}: {stock_info.name}")
            return stock_info
            
        except Exception as e:
            logger.error(f"Error processing stock info for {symbol}: {e}")
            return None
    
    def _fetch_financials(self, ticker: yf.Ticker, quarterly: bool = True) -> pd.DataFrame:
        """財務データを取得（同期）"""
        try:
            self._rate_limit()
            if quarterly:
                return ticker.quarterly_financials
            else:
                return ticker.financials
        except Exception as e:
            logger.error(f"Failed to fetch financials: {e}")
            return pd.DataFrame()
    
    async def get_financials(self, symbol: str, quarterly: bool = True) -> List[FinancialCreate]:
        """財務データを取得してFinancialCreateのリストに変換"""
        ticker = await self.get_ticker_data(symbol)
        if not ticker:
            return []
        
        financials = await self._run_in_executor(self._fetch_financials, ticker, quarterly)
        
        if financials.empty:
            logger.warning(f"No financial data found for {symbol}")
            return []
        
        financial_data = []
        period_type = "quarterly" if quarterly else "annual"
        
        for date, column in financials.items():
            try:
                financial = FinancialCreate(
                    symbol=symbol,
                    period_type=period_type,
                    period_end=date.strftime('%Y-%m-%d'),
                    revenue=self._safe_float(column.get('Total Revenue')),
                    gross_profit=self._safe_float(column.get('Gross Profit')),
                    operating_income=self._safe_float(column.get('Operating Income')),
                    net_income=self._safe_float(column.get('Net Income')),
                    total_assets=self._safe_float(column.get('Total Assets')),
                    total_debt=self._safe_float(column.get('Total Debt')),
                    shareholders_equity=self._safe_float(column.get('Stockholders Equity'))
                )
                financial_data.append(financial)
            except Exception as e:
                logger.error(f"Error processing financial data for {symbol} on {date}: {e}")
                continue
        
        logger.info(f"Fetched {len(financial_data)} financial records for {symbol}")
        return financial_data
    
    def _safe_float(self, value) -> Optional[float]:
        """安全にfloatに変換"""
        if pd.isna(value) or value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def is_japanese_stock(self, symbol: str) -> bool:
        """日本株かどうかを判定"""
        return ".T" in symbol
    
    def is_us_stock(self, symbol: str) -> bool:
        """米国株かどうかを判定"""
        return not self.is_japanese_stock(symbol)


# グローバルインスタンス
yfinance_service = YFinanceService()