from fastapi import APIRouter

from app.api.v1.endpoints import auth, users, trades, strategies, market, logs, websocket, bot, profile, deepseek

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(trades.router, prefix="/trades", tags=["Trades"])
api_router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
api_router.include_router(market.router, prefix="/market", tags=["Market Data"])
api_router.include_router(logs.router, prefix="/logs", tags=["Logs"])
api_router.include_router(bot.router, prefix="/bot", tags=["Trading Bot"])
api_router.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(deepseek.router, prefix="/deepseek", tags=["DeepSeek"])
