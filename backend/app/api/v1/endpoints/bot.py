"""
Endpoints para controlar el bot de trading
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.security import get_current_user
from app.core.logging_config import logger, trade_logger
from app.models.user import User
from app.services import realtime_trading_bot as bot_module

router = APIRouter()


@router.get("/status")
async def get_bot_status(current_user: User = Depends(get_current_user)):
    """Obtiene el estado del bot de trading"""
    bot = bot_module.realtime_bot
    
    if not bot:
        return {
            "running": False,
            "message": "Bot not initialized"
        }
    
    return {
        "running": bot.running,
        "active_symbols": list(bot.active_symbols),
        "stats": bot.stats,
        "latest_prices": {
            symbol: bot.price_history.get(symbol, [])[-1] 
            if bot.price_history.get(symbol) else None
            for symbol in bot.active_symbols
        }
    }


@router.post("/start")
async def start_bot(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """Inicia el bot de trading en tiempo real"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can start the bot")
    
    bot = bot_module.realtime_bot
    
    if bot and bot.running:
        return {"message": "Bot already running", "status": "running"}
    
    try:
        binance_service = request.app.state.binance
        await bot_module.start_realtime_bot(binance_service)
        trade_logger.info(f"Bot started by user {current_user.username}")
        return {"message": "Bot started successfully", "status": "running"}
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise HTTPException(status_code=500, detail="Failed to start bot. Check server logs.")


@router.post("/stop")
async def stop_bot(current_user: User = Depends(get_current_user)):
    """Detiene el bot de trading"""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superusers can stop the bot")
    
    bot = bot_module.realtime_bot
    
    if not bot or not bot.running:
        return {"message": "Bot not running", "status": "stopped"}
    
    try:
        await bot_module.stop_realtime_bot()
        trade_logger.info(f"Bot stopped by user {current_user.username}")
        return {"message": "Bot stopped successfully", "status": "stopped"}
    except Exception as e:
        logger.error(f"Failed to stop bot: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop bot. Check server logs.")


@router.get("/stats")
async def get_bot_stats(current_user: User = Depends(get_current_user)):
    """Obtiene estadísticas del bot"""
    bot = bot_module.realtime_bot
    
    if not bot:
        return {"error": "Bot not initialized"}
    
    return {
        "signals_detected": bot.stats["signals_detected"],
        "trades_executed": bot.stats["trades_executed"],
        "trades_skipped": bot.stats["trades_skipped"],
        "errors": bot.stats["errors"],
        "active_symbols": len(bot.active_symbols),
        "running": bot.running
    }
