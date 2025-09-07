from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from bson import ObjectId
from app.models.stock import PyObjectId


class Financial(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    symbol: str = Field(..., description="銘柄コード")
    period_type: str = Field(..., description="期間タイプ (quarterly | annual)")
    period_end: str = Field(..., description="期間終了日 (YYYY-MM-DD)")
    revenue: Optional[float] = Field(None, description="売上高")
    gross_profit: Optional[float] = Field(None, description="売上総利益")
    operating_income: Optional[float] = Field(None, description="営業利益")
    net_income: Optional[float] = Field(None, description="純利益")
    total_assets: Optional[float] = Field(None, description="総資産")
    total_debt: Optional[float] = Field(None, description="総負債")
    shareholders_equity: Optional[float] = Field(None, description="株主資本")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class FinancialCreate(BaseModel):
    symbol: str
    period_type: str
    period_end: str
    revenue: Optional[float] = None
    gross_profit: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    total_assets: Optional[float] = None
    total_debt: Optional[float] = None
    shareholders_equity: Optional[float] = None