from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://redis:6379"

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"

    # Encriptación de campos sensibles en BD (Fernet key)
    # Genera con: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Binance
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_SECRET_KEY: Optional[str] = None
    BINANCE_TESTNET: bool = True

    # Trading
    DEFAULT_TRADE_AMOUNT: float = 100.0  # USDT
    MAX_OPEN_TRADES: int = 5
    STOP_LOSS_PERCENT: float = 2.0
    TAKE_PROFIT_PERCENT: float = 3.0
    TRADING_FEE_RATE: float = 0.001  # 0.1% por orden (Binance estándar)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


