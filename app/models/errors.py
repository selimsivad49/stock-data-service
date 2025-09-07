from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any


class ErrorCode(str, Enum):
    STOCK_NOT_FOUND = "STOCK_NOT_FOUND"
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    INVALID_PARAMETER = "INVALID_PARAMETER"
    YFINANCE_ERROR = "YFINANCE_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    NETWORK_ERROR = "NETWORK_ERROR"


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None


class APIError(BaseModel):
    error: ErrorDetail


class YFinanceException(Exception):
    """yfinance関連のカスタム例外"""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.YFINANCE_ERROR, details: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class DataFetchException(Exception):
    """データ取得関連のカスタム例外"""
    def __init__(self, message: str, code: ErrorCode = ErrorCode.DATA_UNAVAILABLE, details: Optional[Dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class RateLimitException(Exception):
    """レート制限関連のカスタム例外"""
    def __init__(self, message: str = "API rate limit exceeded", details: Optional[Dict] = None):
        self.message = message
        self.code = ErrorCode.RATE_LIMIT_EXCEEDED
        self.details = details or {}
        super().__init__(message)