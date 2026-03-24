from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base
from app.core.crypto import EncryptedString


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

    # Gestión de riesgo
    max_daily_loss_percent = Column(Float, default=5.0)  # % máximo de pérdida diaria sobre initial_balance
    daily_loss_paused = Column(Boolean, default=False)  # True cuando el límite diario se ha superado
    daily_loss_reset_at = Column(DateTime, nullable=True)  # Cuándo se reinicia el contador diario
    
    # Binance Testnet API keys (para Paper Trading) — encriptados en BD
    binance_testnet_api_key = Column(EncryptedString(512), nullable=True)
    binance_testnet_secret_key = Column(EncryptedString(512), nullable=True)

    # Binance Real API keys (para Real Trading) — encriptados en BD
    binance_real_api_key = Column(EncryptedString(512), nullable=True)
    binance_real_secret_key = Column(EncryptedString(512), nullable=True)

    # DeepSeek API — encriptado en BD
    deepseek_api_key = Column(EncryptedString(512), nullable=True)
    deepseek_enabled = Column(Boolean, default=False)

    # SMTP Configuration for email notifications
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(EncryptedString(512), nullable=True)  # encriptado en BD
    smtp_from_email = Column(String(255), nullable=True)
    smtp_enabled = Column(Boolean, default=False)

    # Telegram Bot Configuration — token encriptado en BD
    telegram_bot_token = Column(EncryptedString(512), nullable=True)
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


