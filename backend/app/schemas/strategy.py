from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.strategy import StrategyType


class StrategyCreate(BaseModel):
    name: str
    strategy_type: StrategyType
    description: Optional[str] = None
    symbols: List[str]
    max_trade_amount: float = 100.0
    stop_loss_percent: float = 2.0
    take_profit_percent: float = 3.0
    max_open_trades: int = 3
    config: Optional[dict] = None


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbols: Optional[List[str]] = None
    max_trade_amount: Optional[float] = None
    stop_loss_percent: Optional[float] = None
    take_profit_percent: Optional[float] = None
    max_open_trades: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[dict] = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    strategy_type: StrategyType
    description: Optional[str]
    symbols: str  # JSON string
    max_trade_amount: float
    stop_loss_percent: float
    take_profit_percent: float
    max_open_trades: int
    is_active: bool
    is_paper_trading: bool
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_profit_loss: float
    win_rate: float
    created_at: datetime
    last_trade_at: Optional[datetime]
    
    class Config:
        from_attributes = True


