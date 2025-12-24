"""
Sistema de Logging con rotación automática
Máximo 5MB por archivo, mantiene histórico limitado
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

# Crear directorio de logs
LOGS_DIR = Path("/app/logs")
LOGS_DIR.mkdir(exist_ok=True)

# Configuración de tamaño máximo (5MB) y backups
MAX_BYTES = 5 * 1024 * 1024  # 5MB
BACKUP_COUNT = 3  # Mantiene 3 archivos de backup (20MB total máximo)

# Formato de logs
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class ColoredFormatter(logging.Formatter):
    """Formatter con colores para consola"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(app_name: str = "100toloose") -> logging.Logger:
    """
    Configura el sistema de logging con:
    - Archivo rotativo (máx 5MB, 3 backups)
    - Salida a consola con colores
    - Diferentes niveles por handler
    """
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    
    # Evitar duplicados si ya está configurado
    if logger.handlers:
        return logger
    
    # Handler para archivo (INFO y superior)
    file_handler = RotatingFileHandler(
        filename=LOGS_DIR / "app.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Handler para errores (archivo separado)
    error_handler = RotatingFileHandler(
        filename=LOGS_DIR / "error.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Handler para trades (archivo separado)
    trade_handler = RotatingFileHandler(
        filename=LOGS_DIR / "trades.log",
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding='utf-8'
    )
    trade_handler.setLevel(logging.INFO)
    trade_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ColoredFormatter(LOG_FORMAT, DATE_FORMAT))
    
    # Agregar handlers
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_trade_logger() -> logging.Logger:
    """Logger específico para operaciones de trading"""
    logger = logging.getLogger("100toloose.trades")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        trade_handler = RotatingFileHandler(
            filename=LOGS_DIR / "trades.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        trade_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(trade_handler)
        
        # También a consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(console_handler)
    
    return logger


def get_api_logger() -> logging.Logger:
    """Logger específico para requests API"""
    logger = logging.getLogger("100toloose.api")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        api_handler = RotatingFileHandler(
            filename=LOGS_DIR / "api.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        api_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(api_handler)
    
    return logger


def get_deepseek_logger() -> logging.Logger:
    """Logger específico para DeepSeek AI"""
    logger = logging.getLogger("100toloose.deepseek")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        deepseek_handler = RotatingFileHandler(
            filename=LOGS_DIR / "deepseek.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        deepseek_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(deepseek_handler)
        
        # También a consola
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(ColoredFormatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(console_handler)
    
    return logger


def get_email_logger() -> logging.Logger:
    """Logger específico para emails"""
    logger = logging.getLogger("100toloose.email")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        email_handler = RotatingFileHandler(
            filename=LOGS_DIR / "email.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        email_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(email_handler)
    
    return logger


def get_telegram_logger() -> logging.Logger:
    """Logger específico para Telegram bot"""
    logger = logging.getLogger("100toloose.telegram")
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        telegram_handler = RotatingFileHandler(
            filename=LOGS_DIR / "telegram.log",
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding='utf-8'
        )
        telegram_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(telegram_handler)
    
    return logger


# Logger principal
logger = setup_logging()
trade_logger = get_trade_logger()
api_logger = get_api_logger()
deepseek_logger = get_deepseek_logger()
email_logger = get_email_logger()
telegram_logger = get_telegram_logger()


