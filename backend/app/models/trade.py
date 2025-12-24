from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.core.database import Base


class TradeStatus(enum.Enum):
    PENDING = "pending"
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class TradeType(enum.Enum):
    BUY = "buy"
    SELL = "sell"


class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Trade info
    symbol = Column(String(20), nullable=False, index=True)  # e.g., BTCUSDT
    trade_type = Column(Enum(TradeType), nullable=False)
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING)
    
    # Prices
    entry_price = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    
    # Risk management
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    
    # Results
    profit_loss = Column(Float, default=0.0)
    profit_loss_percent = Column(Float, default=0.0)
    fees = Column(Float, default=0.0)
    
    # Strategy used
    strategy_name = Column(String(100), nullable=True)
    strategy_signals = Column(Text, nullable=True)  # JSON with signals that triggered the trade
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    opened_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    
    # Binance order ID (for real trades)
    binance_order_id = Column(String(100), nullable=True)
    is_paper_trade = Column(Integer, default=1)  # 1 = paper, 0 = real
    
    # Relationships
    user = relationship("User", back_populates="trades")


