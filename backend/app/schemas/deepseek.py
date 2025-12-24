"""
Schemas para DeepSeek Decisions
"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DeepSeekDecisionResponse(BaseModel):
    """Respuesta con decisión de DeepSeek"""
    id: int
    user_id: int
    strategy_id: Optional[int] = None
    trade_id: Optional[int] = None
    symbol: str
    current_price: float
    recommendation: str
    confidence: float
    risk_assessment: str
    suggested_entry: Optional[float] = None
    suggested_stop_loss: Optional[float] = None
    suggested_take_profit: Optional[float] = None
    reasoning: str
    was_executed: bool
    execution_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class DeepSeekDecisionListResponse(BaseModel):
    """Lista de decisiones de DeepSeek"""
    decisions: list[DeepSeekDecisionResponse]
    total: int

