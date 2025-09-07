from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from app.models.financials import Financial, FinancialCreate
from app.services.stock_service import stock_service
from app.services.data_manager import data_manager

router = APIRouter()


@router.get("/{symbol}/financials", response_model=List[Financial])
async def get_financials(
    symbol: str,
    type: Optional[str] = Query(None, description="期間タイプ (quarterly | annual)")
):
    """銘柄の財務データを取得（不足分は自動でyfinanceから取得）"""
    try:
        # typeパラメータのバリデーション
        if type and type not in ["quarterly", "annual"]:
            raise HTTPException(
                status_code=400, 
                detail={
                    "error": {
                        "code": "INVALID_PARAMETER",
                        "message": "typeは 'quarterly' または 'annual' である必要があります",
                        "details": {"type": type}
                    }
                }
            )
        
        # 自動データ取得機能付きで財務データを取得
        financials = await data_manager.get_financials_with_auto_fetch(
            symbol=symbol.upper(),
            period_type=type
        )
        
        return financials
    except HTTPException:
        raise
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


@router.post("/{symbol}/financials", response_model=Financial)
async def create_financial(symbol: str, financial: FinancialCreate):
    """財務データを作成"""
    try:
        # period_typeのバリデーション
        if financial.period_type not in ["quarterly", "annual"]:
            raise HTTPException(
                status_code=400, 
                detail="period_typeは 'quarterly' または 'annual' である必要があります"
            )
        
        financial.symbol = symbol.upper()
        return await stock_service.create_financial(financial)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"データ作成エラー: {str(e)}")