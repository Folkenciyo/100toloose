from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import asyncio

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
    
    # Calculate P&L from closed trades
    total_profit_loss_from_trades = sum(t.profit_loss for t in trades if t.status == TradeStatus.CLOSED)
    winning_trades = len([t for t in trades if t.status == TradeStatus.CLOSED and t.profit_loss > 0])
    losing_trades = len([t for t in trades if t.status == TradeStatus.CLOSED and t.profit_loss < 0])
    
    win_rate = (winning_trades / closed_trades * 100) if closed_trades > 0 else 0
    
    # Calculate P&L from balance (más preciso cuando se sincroniza con Binance)
    # El P&L real es la diferencia entre el balance actual y el inicial
    balance_profit_loss = current_user.current_balance - current_user.initial_balance
    
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
        # Obtener trades de esta estrategia (comparación case-insensitive y sin espacios)
        strategy_trades = [
            t for t in trades 
            if t.strategy_name and 
            t.strategy_name.strip().lower() == strategy.name.strip().lower()
        ]
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
    
    # Identificar trades abiertos sin estrategia activa o con estrategias inactivas
    active_strategy_names = [s.name.strip().lower() for s in active_strategies]
    trades_without_strategy = [
        t for t in trades 
        if t.status == TradeStatus.OPEN and 
        (not t.strategy_name or 
         t.strategy_name.strip() == "" or 
         t.strategy_name.strip().lower() not in active_strategy_names)
    ]
    
    if trades_without_strategy:
        logger.warning(f"⚠️ Found {len(trades_without_strategy)} open trades without active strategy. Symbols: {[t.symbol for t in trades_without_strategy]}")
    
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
            
            # Obtener todos los balances desde Binance (Testnet o Real según paper_trading)
            balances = await binance_service.get_account_balance()
            
            # IMPORTANTE: Calcular balance total de TODOS los assets correctamente
            # El breakdown puede limitarse para mostrar, pero el balance total debe ser exacto
            total_balance_usdt = 0.0
            balance_breakdown = []
            
            # Obtener todos los precios de una vez (esto es necesario para calcular el balance total correctamente)
            try:
                all_prices = await binance_service.get_all_prices()
                logger.info(f"✅ Obtained all prices from Binance ({len(all_prices)} symbols)")
            except Exception as e:
                logger.warning(f"Could not get all prices: {e}, will fetch individually")
                all_prices = {}
            
            # Ordenar assets por cantidad para procesar primero los más importantes
            assets_sorted = sorted(
                balances.items(), 
                key=lambda x: x[1].get("total", 0.0), 
                reverse=True
            )
            
            # Calcular balance total de TODOS los assets (esto es crítico para la precisión)
            for asset, balance_info in assets_sorted:
                total_amount = balance_info.get("total", 0.0)
                if total_amount > 0:
                    if asset == "USDT":
                        # USDT ya está en dólares
                        value_usdt = total_amount
                        total_balance_usdt += value_usdt
                    else:
                        # Convertir otras criptos a USDT
                        symbol = f"{asset}USDT"
                        price = all_prices.get(symbol)
                        if price:
                            value_usdt = total_amount * price
                            total_balance_usdt += value_usdt
                        else:
                            # Si no está en la lista de precios, intentar obtenerlo individualmente
                            # Esto es necesario para calcular el balance total correctamente
                            try:
                                price = await binance_service.get_symbol_price(symbol)
                                value_usdt = total_amount * price
                                total_balance_usdt += value_usdt
                                all_prices[symbol] = price  # Cachear para el breakdown
                            except Exception as e:
                                logger.debug(f"Could not get price for {symbol}: {e}")
                                value_usdt = 0.0
                                # No sumar al total si no podemos obtener el precio
                    
                    # Para el breakdown, solo agregar assets con valor significativo (> $0.01)
                    # Y limitar a los top 100 para no sobrecargar el frontend
                    if value_usdt > 0.01 and len(balance_breakdown) < 100:
                        balance_breakdown.append({
                            "asset": asset,
                            "amount": total_amount,
                            "value_usdt": value_usdt,
                            "free": balance_info.get("free", 0.0),
                            "locked": balance_info.get("locked", 0.0)
                        })
            
            # Ordenar breakdown por valor (mayor a menor)
            balance_breakdown.sort(key=lambda x: x["value_usdt"], reverse=True)
            
            logger.info(f"💰 Calculated total balance: ${total_balance_usdt:,.2f} USDT from {len(assets_sorted)} assets (showing top {len(balance_breakdown)} in breakdown)")
            
            if total_balance_usdt > 0:
                # Sincronizar balance total de BD con Binance
                current_user.current_balance = total_balance_usdt
                await db.commit()
                await db.refresh(current_user)
                current_balance = total_balance_usdt
                balance_synced = True
                logger.info(f"✅ Balance synced from Binance {binance_mode}: ${total_balance_usdt:,.2f} USDT total ({len(balance_breakdown)} assets) (Mode: {trading_mode})")
            else:
                logger.warning(f"⚠️ Balance from Binance {binance_mode} is 0. Using database balance.")
                balance_breakdown = []
            
            await binance_service.close()
        except Exception as e:
            logger.warning(f"⚠️ Could not sync balance from Binance {binance_mode} (Mode: {trading_mode}): {e}. Using database balance.")
            # Si falla, usar el balance de la BD
    else:
        logger.debug(f"📝 No API keys configured. Using simulated balance for {trading_mode}.")
    
    # balance_breakdown ya está inicializado arriba
    
    return {
        "user": {
            "username": current_user.username,
            "paper_trading": current_user.paper_trading,
            "trading_mode": trading_mode,  # "Paper Trading (Testnet)" o "Real Trading"
            "binance_mode": binance_mode,  # "Testnet" o "Real"
            "initial_balance": current_user.initial_balance,
            "current_balance": current_balance,
            "balance_synced": balance_synced,  # Indica si el balance viene de Binance
            "balance_breakdown": balance_breakdown,  # Distribución de fondos por criptomoneda
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
            "total_profit_loss": round(total_profit_loss_from_trades, 2),  # Solo de trades cerrados
            "balance_profit_loss": round(balance_profit_loss, 2),  # P&L real basado en balance
            "best_trade": max([t.profit_loss for t in trades if t.status == TradeStatus.CLOSED], default=0),
            "worst_trade": min([t.profit_loss for t in trades if t.status == TradeStatus.CLOSED], default=0)
        },
        "strategies": strategies_summary,  # Resumen de estrategias activas
        "trades_without_strategy": {
            "count": len(trades_without_strategy),
            "symbols": [t.symbol for t in trades_without_strategy],
            "strategy_names": [t.strategy_name or "Sin estrategia" for t in trades_without_strategy]
        }  # Trades abiertos sin estrategia activa
    }


@router.put("/reset-balance")
async def reset_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset balance to current balance and set it as new initial balance (useful for Testnet)"""
    from app.services.binance_service import BinanceService
    from app.core.logging_config import logger
    
    # Obtener balance actual de Binance si tiene API keys
    if current_user.paper_trading:
        api_key = current_user.binance_testnet_api_key
        secret_key = current_user.binance_testnet_secret_key
        binance_mode = "Testnet"
    else:
        api_key = current_user.binance_real_api_key
        secret_key = current_user.binance_real_secret_key
        binance_mode = "Real"
    
    if api_key and secret_key:
        try:
            binance_service = BinanceService(
                api_key=api_key,
                secret_key=secret_key,
                use_testnet=current_user.paper_trading
            )
            await binance_service.initialize()
            balances = await binance_service.get_account_balance()
            usdt_balance = balances.get("USDT", {}).get("total", 0.0) if balances else 0.0
            await binance_service.close()
            
            if usdt_balance > 0:
                # Resetear: el balance actual se convierte en el nuevo balance inicial
                current_user.initial_balance = usdt_balance
                current_user.current_balance = usdt_balance
                await db.commit()
                await db.refresh(current_user)
                
                logger.info(f"✅ Balance reset for user {current_user.username}: New initial balance = ${usdt_balance:,.2f} (from Binance {binance_mode})")
                
                return {
                    "message": f"Balance reset successfully. New initial balance: ${usdt_balance:,.2f}",
                    "initial_balance": usdt_balance,
                    "current_balance": usdt_balance,
                    "source": f"Binance {binance_mode}"
                }
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"No USDT balance found in Binance {binance_mode}. Please add funds first."
                )
        except Exception as e:
            logger.error(f"❌ Failed to reset balance from Binance {binance_mode}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Could not sync balance from Binance {binance_mode}: {str(e)}"
            )
    else:
        # Si no tiene API keys, resetear con el balance actual de la BD
        new_initial = current_user.current_balance
        current_user.initial_balance = new_initial
        await db.commit()
        await db.refresh(current_user)
        
        return {
            "message": f"Balance reset successfully. New initial balance: ${new_initial:,.2f}",
            "initial_balance": new_initial,
            "current_balance": new_initial,
            "source": "Database"
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


