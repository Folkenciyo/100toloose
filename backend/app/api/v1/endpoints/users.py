from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


class TradingModeUpdate(BaseModel):
    paper_trading: bool


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard summary for the current user"""
    from sqlalchemy import select, func
    from app.models.trade import Trade, TradeStatus
    from app.services.binance_service import BinanceService
    from app.core.logging_config import logger
    
    # Get trade statistics
    trades_query = select(Trade).where(Trade.user_id == current_user.id)
    result = await db.execute(trades_query)
    trades = result.scalars().all()
    
    total_trades = len(trades)
    open_trades = len([t for t in trades if t.status == TradeStatus.OPEN])
    closed_trades = len([t for t in trades if t.status == TradeStatus.CLOSED])
    
    # Calculate P&L
    total_profit_loss = sum(t.profit_loss for t in trades if t.status == TradeStatus.CLOSED)
    winning_trades = len([t for t in trades if t.status == TradeStatus.CLOSED and t.profit_loss > 0])
    losing_trades = len([t for t in trades if t.status == TradeStatus.CLOSED and t.profit_loss < 0])
    
    win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0
    
    # Obtener información detallada de estrategias activas
    from app.models.strategy import Strategy
    import json
    
    strategies_query = select(Strategy).where(
        Strategy.user_id == current_user.id,
        Strategy.is_active == True
    )
    strategies_result = await db.execute(strategies_query)
    active_strategies = strategies_result.scalars().all()
    
    strategies_summary = []
    for strategy in active_strategies:
        # Obtener trades de esta estrategia
        strategy_trades = [t for t in trades if t.strategy_name == strategy.name]
        strategy_closed_trades = [t for t in strategy_trades if t.status == TradeStatus.CLOSED]
        strategy_open_trades = [t for t in strategy_trades if t.status == TradeStatus.OPEN]
        
        strategy_winning = len([t for t in strategy_closed_trades if t.profit_loss > 0])
        strategy_losing = len([t for t in strategy_closed_trades if t.profit_loss < 0])
        strategy_pnl = sum(t.profit_loss for t in strategy_closed_trades)
        strategy_win_rate = (strategy_winning / len(strategy_closed_trades) * 100) if len(strategy_closed_trades) > 0 else 0
        
        # Parsear símbolos
        try:
            symbols_list = json.loads(strategy.symbols) if strategy.symbols else []
        except:
            symbols_list = []
        
        strategies_summary.append({
            "id": strategy.id,
            "name": strategy.name,
            "type": strategy.strategy_type.value,
            "symbols": symbols_list,
            "is_active": strategy.is_active,
            "stats": {
                "total_trades": len(strategy_trades),
                "open_trades": len(strategy_open_trades),
                "closed_trades": len(strategy_closed_trades),
                "winning_trades": strategy_winning,
                "losing_trades": strategy_losing,
                "win_rate": round(strategy_win_rate, 2),
                "total_profit_loss": round(strategy_pnl, 2),
                "avg_profit_loss": round(strategy_pnl / len(strategy_closed_trades), 2) if len(strategy_closed_trades) > 0 else 0.0
            },
            "config": {
                "max_trade_amount": strategy.max_trade_amount,
                "stop_loss_percent": strategy.stop_loss_percent,
                "take_profit_percent": strategy.take_profit_percent,
                "max_open_trades": strategy.max_open_trades
            },
            "last_trade_at": strategy.last_trade_at.isoformat() if strategy.last_trade_at else None,
            "created_at": strategy.created_at.isoformat() if strategy.created_at else None
        })
    
    # Obtener balance real de Binance si tiene API keys configuradas
    # IMPORTANTE: Solo sincroniza con el modo configurado (Testnet si paper_trading=True, Real si paper_trading=False)
    current_balance = current_user.current_balance
    balance_synced = False
    trading_mode = "Paper Trading (Testnet)" if current_user.paper_trading else "Real Trading"
    binance_mode = "Testnet" if current_user.paper_trading else "Real"
    
    # Obtener las API keys correctas según el modo
    if current_user.paper_trading:
        api_key = current_user.binance_testnet_api_key
        secret_key = current_user.binance_testnet_secret_key
    else:
        api_key = current_user.binance_real_api_key
        secret_key = current_user.binance_real_secret_key
    
    if api_key and secret_key:
        try:
            # Crear servicio Binance con el modo correcto según paper_trading
            binance_service = BinanceService(
                api_key=api_key,
                secret_key=secret_key,
                use_testnet=current_user.paper_trading  # True = Testnet, False = Real Binance
            )
            await binance_service.initialize()
            
            logger.info(f"🔄 Syncing balance from Binance {binance_mode} for user {current_user.username} (Mode: {trading_mode})")
            
            # Obtener balance de USDT desde Binance (Testnet o Real según paper_trading)
            balances = await binance_service.get_account_balance()
            usdt_balance = balances.get("USDT", {}).get("total", 0.0) if balances else 0.0
            
            if usdt_balance > 0:
                # Sincronizar balance de BD con Binance
                current_user.current_balance = usdt_balance
                await db.commit()
                await db.refresh(current_user)
                current_balance = usdt_balance
                balance_synced = True
                logger.info(f"✅ Balance synced from Binance {binance_mode}: ${usdt_balance:,.2f} USDT (Mode: {trading_mode})")
            else:
                logger.warning(f"⚠️ Balance from Binance {binance_mode} is 0. Using database balance.")
            
            await binance_service.close()
        except Exception as e:
            logger.warning(f"⚠️ Could not sync balance from Binance {binance_mode} (Mode: {trading_mode}): {e}. Using database balance.")
            # Si falla, usar el balance de la BD
    else:
        logger.debug(f"📝 No API keys configured. Using simulated balance for {trading_mode}.")
    
    return {
        "user": {
            "username": current_user.username,
            "paper_trading": current_user.paper_trading,
            "trading_mode": trading_mode,  # "Paper Trading (Testnet)" o "Real Trading"
            "binance_mode": binance_mode,  # "Testnet" o "Real"
            "initial_balance": current_user.initial_balance,
            "current_balance": current_balance,
            "balance_synced": balance_synced,  # Indica si el balance viene de Binance
            "profit_loss": current_balance - current_user.initial_balance,
            "profit_loss_percent": ((current_balance - current_user.initial_balance) / current_user.initial_balance) * 100 if current_user.initial_balance > 0 else 0
        },
        "trades": {
            "total": total_trades,
            "open": open_trades,
            "closed": closed_trades,
            "winning": winning_trades,
            "losing": losing_trades,
            "win_rate": round(win_rate, 2)
        },
        "performance": {
            "total_profit_loss": round(total_profit_loss, 2),
            "best_trade": max([t.profit_loss for t in trades], default=0),
            "worst_trade": min([t.profit_loss for t in trades], default=0)
        },
        "strategies": strategies_summary  # Resumen de estrategias activas
    }


@router.put("/trading-mode")
async def update_trading_mode(
    mode: TradingModeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update trading mode (Paper Trading or Real Trading)"""
    # Verificar que tiene API keys si quiere usar Real Trading
    if not mode.paper_trading:
        if not current_user.binance_real_api_key or not current_user.binance_real_secret_key:
            raise HTTPException(
                status_code=400,
                detail="Binance Real API keys are required for Real Trading. Please configure them in Profile settings."
            )
    
    current_user.paper_trading = mode.paper_trading
    await db.commit()
    await db.refresh(current_user)
    
    return {
        "paper_trading": current_user.paper_trading,
        "message": f"Trading mode updated to {'Paper Trading (Testnet)' if current_user.paper_trading else 'Real Trading'}"
    }


