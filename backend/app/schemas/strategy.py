from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.models.strategy import StrategyType


class StrategyCreate(BaseModel):
    name: str
    strategy_type: StrategyType
    description: Optional[str] = None
    symbols: List[str]
    max_trade_amount: float = Field(default=100.0, gt=0, description="Maximum trade amount in USDT")
    stop_loss_percent: float = Field(default=2.0, ge=0.1, le=50.0, description="Stop loss percentage (0.1% to 50%)")
    take_profit_percent: float = Field(default=3.0, ge=0.1, le=100.0, description="Take profit percentage (0.1% to 100%)")
    max_open_trades: int = Field(default=3, ge=1, le=50, description="Maximum open trades (1 to 50)")
    config: Optional[dict] = None
    
    @field_validator('stop_loss_percent', 'take_profit_percent')
    @classmethod
    def validate_percentages(cls, v: float) -> float:
        if v < 0.1:
            raise ValueError("Stop loss and take profit must be at least 0.1% to account for market volatility and fees")
        return v


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    symbols: Optional[List[str]] = None
    max_trade_amount: Optional[float] = Field(default=None, gt=0)
    stop_loss_percent: Optional[float] = Field(default=None, ge=0.1, le=50.0)
    take_profit_percent: Optional[float] = Field(default=None, ge=0.1, le=100.0)
    max_open_trades: Optional[int] = Field(default=None, ge=1, le=50)
    is_active: Optional[bool] = None
    config: Optional[dict] = None
    
    @field_validator('stop_loss_percent', 'take_profit_percent', mode='before')
    @classmethod
    def validate_percentages(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0.1:
            raise ValueError("Stop loss and take profit must be at least 0.1% to account for market volatility and fees")
        return v


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


