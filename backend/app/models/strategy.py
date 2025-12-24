from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class StrategyType(enum.Enum):
    RSI = "rsi"
    MACD = "macd"
    BOLLINGER = "bollinger"
    EMA_CROSS = "ema_cross"
    COMBINED = "combined"
    SCALPING = "scalping"  # Estrategia agresiva para testing
    CUSTOM = "custom"


class Strategy(Base):
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Strategy info
    name = Column(String(100), nullable=False)
    strategy_type = Column(Enum(StrategyType), nullable=False)
    description = Column(Text, nullable=True)
    
    # Configuration (JSON)
    config = Column(Text, nullable=True)  # JSON with strategy parameters
    
    # Trading pairs
    symbols = Column(Text, nullable=False)  # JSON array of symbols to trade
    
    # Risk settings
    max_trade_amount = Column(Float, default=100.0)
    stop_loss_percent = Column(Float, default=2.0)
    take_profit_percent = Column(Float, default=3.0)
    max_open_trades = Column(Integer, default=3)
    
    # Status
    is_active = Column(Boolean, default=False)
    is_paper_trading = Column(Boolean, default=True)
    
    # Performance
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_profit_loss = Column(Float, default=0.0)
    win_rate = Column(Float, default=0.0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_trade_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="strategies")

