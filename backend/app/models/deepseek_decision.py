"""
Modelo para guardar decisiones de DeepSeek AI
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class DeepSeekDecision(Base):
    """Registro de decisiones tomadas por DeepSeek AI"""
    __tablename__ = "deepseek_decisions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True, index=True)
    trade_id = Column(Integer, ForeignKey("trades.id"), nullable=True, index=True)  # Si se ejecutó el trade
    
    # Información del análisis
    symbol = Column(String(20), nullable=False)
    current_price = Column(Float, nullable=False)
    
    # Recomendación de DeepSeek
    recommendation = Column(String(20), nullable=False)  # BUY, SELL, HOLD, STRONG_BUY, STRONG_SELL
    confidence = Column(Float, nullable=False)  # 0.0 - 1.0
    risk_assessment = Column(String(10), nullable=False)  # LOW, MEDIUM, HIGH
    
    # Precios sugeridos
    suggested_entry = Column(Float, nullable=True)
    suggested_stop_loss = Column(Float, nullable=True)
    suggested_take_profit = Column(Float, nullable=True)
    
    # Razonamiento completo
    reasoning = Column(Text, nullable=False)
    
    # Indicadores técnicos en el momento del análisis (JSON string)
    indicators_snapshot = Column(Text, nullable=True)
    
    # Resultado
    was_executed = Column(Boolean, default=False)  # Si finalmente se ejecutó el trade
    execution_reason = Column(String(100), nullable=True)  # Por qué se ejecutó o no
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", backref="deepseek_decisions")
    strategy = relationship("Strategy", backref="deepseek_decisions")
    trade = relationship("Trade", backref="deepseek_decisions")

