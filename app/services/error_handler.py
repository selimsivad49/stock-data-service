import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException
from app.models.errors import ErrorCode, ErrorDetail, APIError, YFinanceException, DataFetchException, RateLimitException

logger = logging.getLogger(__name__)


class ErrorHandler:
    """エラーハンドリングを統一管理するクラス"""
    
    @staticmethod
    def handle_yfinance_error(e: Exception, symbol: str) -> HTTPException:
        """yfinance関連エラーのハンドリング"""
        error_msg = str(e)
        
        if "No data found" in error_msg or "No timezone found" in error_msg:
            logger.warning(f"Symbol not found in yfinance: {symbol}")
            return HTTPException(
                status_code=404,
                detail=APIError(
                    error=ErrorDetail(
                        code=ErrorCode.STOCK_NOT_FOUND,
                        message="指定された銘柄が見つかりません",
                        details={"symbol": symbol, "source": "yfinance"}
                    )
                ).dict()
            )
        
        elif "HTTPSConnectionPool" in error_msg or "Connection" in error_msg:
            logger.error(f"Network error for yfinance request: {error_msg}")
            return HTTPException(
                status_code=503,
                detail=APIError(
                    error=ErrorDetail(
                        code=ErrorCode.NETWORK_ERROR,
                        message="ネットワークエラーが発生しました",
                        details={"symbol": symbol, "error": error_msg}
                    )
                ).dict()
            )
        
        elif "rate limit" in error_msg.lower() or "too many requests" in error_msg.lower():
            logger.error(f"Rate limit exceeded for symbol: {symbol}")
            return HTTPException(
                status_code=429,
                detail=APIError(
                    error=ErrorDetail(
                        code=ErrorCode.RATE_LIMIT_EXCEEDED,
                        message="APIレート制限に達しました。しばらく待ってからお試しください",
                        details={"symbol": symbol}
                    )
                ).dict()
            )
        
        else:
            logger.error(f"Unknown yfinance error for {symbol}: {error_msg}")
            return HTTPException(
                status_code=500,
                detail=APIError(
                    error=ErrorDetail(
                        code=ErrorCode.YFINANCE_ERROR,
                        message="データ取得サービスでエラーが発生しました",
                        details={"symbol": symbol, "error": error_msg}
                    )
                ).dict()
            )
    
    @staticmethod
    def handle_database_error(e: Exception, operation: str, details: Optional[Dict] = None) -> HTTPException:
        """データベース関連エラーのハンドリング"""
        error_msg = str(e)
        logger.error(f"Database error during {operation}: {error_msg}")
        
        return HTTPException(
            status_code=500,
            detail=APIError(
                error=ErrorDetail(
                    code=ErrorCode.DATABASE_ERROR,
                    message="データベースエラーが発生しました",
                    details={
                        "operation": operation,
                        "error": error_msg,
                        **(details or {})
                    }
                )
            ).dict()
        )
    
    @staticmethod
    def handle_validation_error(message: str, details: Optional[Dict] = None) -> HTTPException:
        """バリデーションエラーのハンドリング"""
        return HTTPException(
            status_code=400,
            detail=APIError(
                error=ErrorDetail(
                    code=ErrorCode.INVALID_PARAMETER,
                    message=message,
                    details=details
                )
            ).dict()
        )
    
    @staticmethod
    def handle_date_range_error(start_date: Optional[str], end_date: Optional[str]) -> HTTPException:
        """日付範囲エラーのハンドリング"""
        return HTTPException(
            status_code=400,
            detail=APIError(
                error=ErrorDetail(
                    code=ErrorCode.INVALID_DATE_RANGE,
                    message="無効な日付範囲が指定されました",
                    details={"start_date": start_date, "end_date": end_date}
                )
            ).dict()
        )
    
    @staticmethod
    def handle_custom_exception(e: Exception) -> HTTPException:
        """カスタム例外のハンドリング"""
        if isinstance(e, YFinanceException):
            return HTTPException(
                status_code=500,
                detail=APIError(
                    error=ErrorDetail(
                        code=e.code,
                        message=e.message,
                        details=e.details
                    )
                ).dict()
            )
        
        elif isinstance(e, DataFetchException):
            return HTTPException(
                status_code=500,
                detail=APIError(
                    error=ErrorDetail(
                        code=e.code,
                        message=e.message,
                        details=e.details
                    )
                ).dict()
            )
        
        elif isinstance(e, RateLimitException):
            return HTTPException(
                status_code=429,
                detail=APIError(
                    error=ErrorDetail(
                        code=e.code,
                        message=e.message,
                        details=e.details
                    )
                ).dict()
            )
        
        else:
            logger.error(f"Unhandled exception: {e}")
            return HTTPException(
                status_code=500,
                detail=APIError(
                    error=ErrorDetail(
                        code=ErrorCode.DATA_UNAVAILABLE,
                        message="予期しないエラーが発生しました",
                        details={"error": str(e)}
                    )
                ).dict()
            )


# グローバルインスタンス
error_handler = ErrorHandler()