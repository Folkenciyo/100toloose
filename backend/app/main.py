from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.core.logging_config import logger, trade_logger
from app.api.v1.router import api_router
from app.services.binance_service import BinanceService
from app.services.realtime_trading_bot import start_realtime_bot, stop_realtime_bot
from app.services.telegram_bot_listener import telegram_listener
from app.middleware.logging_middleware import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Starting 100toLoose Trading Bot...")
    logger.info("=" * 60)
    
    # Create database tables
    # NOTE: In production, disable this and use: docker compose exec backend alembic upgrade head
    # This is kept for local development only.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise
    
    # Initialize Binance service
    try:
        app.state.binance = BinanceService()
        await app.state.binance.initialize()
        logger.info("✅ Binance service initialized")
        logger.info(f"   └─ Testnet mode: {settings.BINANCE_TESTNET}")
    except Exception as e:
        logger.error(f"❌ Binance service failed: {e}")
        raise
    
    # Start realtime trading bot
    try:
        await start_realtime_bot(app.state.binance)
        logger.info("✅ Realtime trading bot started")
    except Exception as e:
        logger.error(f"⚠️ Realtime bot failed to start: {e}")
        # No raise - el bot es opcional
    
    # Start Telegram bot listener
    try:
        await telegram_listener.start()
        logger.info("✅ Telegram bot listener started")
    except Exception as e:
        logger.error(f"⚠️ Telegram listener failed to start: {e}")
        # No raise - el listener es opcional
    
    logger.info("=" * 60)
    logger.info("🟢 100toLoose Trading Bot is READY")
    logger.info(f"   └─ API: http://0.0.0.0:8000")
    logger.info(f"   └─ Docs: http://0.0.0.0:8000/docs")
    logger.info(f"   └─ WebSocket: ws://0.0.0.0:8000/api/v1/ws/prices")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("🛑 Shutting down 100toLoose Trading Bot...")
    
    try:
        await stop_realtime_bot()
        logger.info("✅ Realtime bot stopped")
    except Exception as e:
        logger.error(f"Error stopping bot: {e}")
    
    try:
        await telegram_listener.stop()
        logger.info("✅ Telegram bot listener stopped")
    except Exception as e:
        logger.error(f"Error stopping Telegram listener: {e}")
    
    await app.state.binance.close()
    logger.info("✅ Binance service closed")
    logger.info("👋 Goodbye!")
    logger.info("=" * 60)


app = FastAPI(
    title="100toLoose Trading Bot",
    description="Autonomous crypto trading bot with AI-powered strategies",
    version="1.0.0",
    lifespan=lifespan
)

# Logging middleware (debe ir primero)
app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
        "https://100toloose.folkenland.online",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    from app.services.realtime_trading_bot import realtime_bot
    
    return {
        "status": "healthy",
        "service": "100toLoose Trading Bot",
        "version": "1.0.0",
        "bot_running": realtime_bot.running if realtime_bot else False
    }
