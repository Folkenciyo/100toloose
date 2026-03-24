from pydantic import BaseModel, EmailStr
from typing import Optional


class BinanceTestnetConfig(BaseModel):
    api_key: Optional[str] = None
    secret_key: Optional[str] = None


class BinanceRealConfig(BaseModel):
    api_key: Optional[str] = None
    secret_key: Optional[str] = None


class DeepSeekConfig(BaseModel):
    api_key: Optional[str] = None
    enabled: bool = False


class SMTPConfig(BaseModel):
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    from_email: Optional[EmailStr] = None
    enabled: bool = False


class TelegramConfig(BaseModel):
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = False


class RiskConfig(BaseModel):
    max_daily_loss_percent: Optional[float] = None  # % de initial_balance (ej: 5.0 = 5%)


class ProfileInfoConfig(BaseModel):
    profile_name: Optional[str] = None
    summary_email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    platform_user_id: Optional[str] = None
    paper_trading: Optional[bool] = None


class ProfileSettingsUpdate(BaseModel):
    profile_info: Optional[ProfileInfoConfig] = None
    binance_testnet: Optional[BinanceTestnetConfig] = None
    binance_real: Optional[BinanceRealConfig] = None
    deepseek: Optional[DeepSeekConfig] = None
    smtp: Optional[SMTPConfig] = None
    telegram: Optional[TelegramConfig] = None
    risk: Optional[RiskConfig] = None


class ProfileSettingsResponse(BaseModel):
    profile_info: ProfileInfoConfig
    binance_testnet: BinanceTestnetConfig
    binance_real: BinanceRealConfig
    deepseek: DeepSeekConfig
    smtp: SMTPConfig
    telegram: TelegramConfig
    risk: RiskConfig
    daily_loss_paused: bool = False
    
    class Config:
        from_attributes = True

