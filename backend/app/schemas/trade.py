from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.trade import TradeStatus, TradeType


class TradeCreate(BaseModel):
    symbol: str
    trade_type: TradeType
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    strategy_name: Optional[str] = None


class TradeUpdate(BaseModel):
    status: Optional[TradeStatus] = None
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class TradeResponse(BaseModel):
    id: int
    symbol: str
    trade_type: TradeType
    status: TradeStatus
    entry_price: Optional[float]
    exit_price: Optional[float]
    quantity: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    profit_loss: float
    profit_loss_percent: float
    strategy_name: Optional[str]
    created_at: datetime
    opened_at: Optional[datetime]
    closed_at: Optional[datetime]
    is_paper_trade: int
    
    class Config:
        from_attributes = True


