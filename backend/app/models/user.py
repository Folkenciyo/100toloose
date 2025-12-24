from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Profile
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Trading settings
    paper_trading = Column(Boolean, default=True)  # True = dinero ficticio
    initial_balance = Column(Float, default=10000.0)  # Balance inicial ficticio
    current_balance = Column(Float, default=10000.0)  # Balance actual
    
    # Binance Testnet API keys (para Paper Trading)
    binance_testnet_api_key = Column(String(255), nullable=True)
    binance_testnet_secret_key = Column(String(255), nullable=True)
    
    # Binance Real API keys (para Real Trading)
    binance_real_api_key = Column(String(255), nullable=True)
    binance_real_secret_key = Column(String(255), nullable=True)
    
    # DeepSeek API
    deepseek_api_key = Column(String(255), nullable=True)
    deepseek_enabled = Column(Boolean, default=False)  # Toggle para activar/desactivar DeepSeek
    
    # SMTP Configuration for email notifications
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    smtp_from_email = Column(String(255), nullable=True)
    smtp_enabled = Column(Boolean, default=False)
    
    # Telegram Bot Configuration
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_enabled = Column(Boolean, default=False)
    
    # Profile Information
    profile_name = Column(String(100), nullable=True)  # Nombre de perfil personalizado
    summary_email = Column(String(255), nullable=True)  # Email para recibir resúmenes (puede ser diferente del email de login)
    phone_number = Column(String(50), nullable=True)  # Número de teléfono para notificaciones
    platform_user_id = Column(String(100), nullable=True)  # ID de usuario en la plataforma 100toLoose (para referencias internas)
    
    # Relationships
    trades = relationship("Trade", back_populates="user")
    strategies = relationship("Strategy", back_populates="user")


