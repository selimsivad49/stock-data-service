from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        json_schema = handler(core_schema)
        json_schema.update(type="string")
        return json_schema


class DailyPrice(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    symbol: str = Field(..., description="銘柄コード (例: 7203.T)")
    date: str = Field(..., description="取引日 (YYYY-MM-DD)")
    open: float = Field(..., description="始値")
    high: float = Field(..., description="高値")
    low: float = Field(..., description="安値")
    close: float = Field(..., description="終値")
    adj_close: float = Field(..., description="調整後終値")
    volume: int = Field(..., description="出来高")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class StockInfo(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    symbol: str = Field(..., description="銘柄コード")
    name: str = Field(..., description="企業名")
    sector: Optional[str] = Field(None, description="セクター")
    industry: Optional[str] = Field(None, description="業界")
    market: str = Field(..., description="市場 (jp | us)")
    currency: str = Field(..., description="通貨")
    exchange: Optional[str] = Field(None, description="取引所")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class DailyPriceCreate(BaseModel):
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


class StockInfoCreate(BaseModel):
    symbol: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market: str
    currency: str
    exchange: Optional[str] = None