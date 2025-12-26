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
    # Campos adicionales para trades abiertos (calculados dinámicamente)
    current_price: Optional[float] = None  # Precio actual del símbolo
    current_value: Optional[float] = None  # Valor actual en USD (quantity * current_price)
    current_pnl: Optional[float] = None  # P&L actualizado (no persistido en BD)
    current_pnl_percent: Optional[float] = None  # P&L porcentual actualizado
    invested_value: Optional[float] = None  # Valor invertido (quantity * entry_price)
    
    class Config:
        from_attributes = True


