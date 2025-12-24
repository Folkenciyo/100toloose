from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import json

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.logging_config import logger
from app.models.user import User
from app.models.trade import Trade, TradeStatus
from app.models.strategy import Strategy, StrategyType
from app.schemas.strategy import StrategyCreate, StrategyResponse, StrategyUpdate
from app.services.websocket_manager import binance_ws
from app.services.indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands

router = APIRouter()


@router.get("/", response_model=List[StrategyResponse])
async def get_strategies(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all strategies for the current user"""
    query = select(Strategy).where(Strategy.user_id == current_user.id)
    result = await db.execute(query)
    strategies = result.scalars().all()
    
    return strategies


@router.get("/with-status")
async def get_strategies_with_status(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all strategies with real-time status and signals"""
    query = select(Strategy).where(Strategy.user_id == current_user.id)
    result = await db.execute(query)
    strategies = result.scalars().all()
    
    binance_service = request.app.state.binance
    
    strategies_with_status = []
    
    for strategy in strategies:
        symbols = json.loads(strategy.symbols)
        symbol_statuses = []
        
        for symbol in symbols:
            # Obtener precio actual
            price = binance_ws.get_price(symbol)
            if not price:
                try:
                    price = await binance_service.get_symbol_price(symbol)
                except:
                    price = None
            
            # Obtener trades abiertos para este símbolo
            open_trade_result = await db.execute(
                select(Trade).where(
                    Trade.user_id == current_user.id,
                    Trade.symbol == symbol,
                    Trade.status == TradeStatus.OPEN
                )
            )
            open_trade = open_trade_result.scalar_one_or_none()
            
            # Calcular indicadores si tenemos historial
            signal_info = await _get_signal_info(binance_service, symbol, strategy.strategy_type)
            
            symbol_status = {
                "symbol": symbol,
                "current_price": price,
                "has_open_trade": open_trade is not None,
                "open_trade_id": open_trade.id if open_trade else None,
                "open_trade_pnl": None,
                "signal": signal_info
            }
            
            # Calcular P&L del trade abierto
            if open_trade and price:
                if open_trade.trade_type.value == "buy":
                    pnl = (price - open_trade.entry_price) * open_trade.quantity
                else:
                    pnl = (open_trade.entry_price - price) * open_trade.quantity
                pnl_percent = (pnl / (open_trade.entry_price * open_trade.quantity)) * 100
                symbol_status["open_trade_pnl"] = {
                    "value": round(pnl, 2),
                    "percent": round(pnl_percent, 2),
                    "entry_price": open_trade.entry_price,
                    "stop_loss": open_trade.stop_loss,
                    "take_profit": open_trade.take_profit
                }
            
            symbol_statuses.append(symbol_status)
        
        # Determinar estado general de la estrategia
        waiting_reason = _get_waiting_reason(strategy, symbol_statuses)
        
        strategies_with_status.append({
            "id": strategy.id,
            "name": strategy.name,
            "strategy_type": strategy.strategy_type.value,
            "description": strategy.description,
            "is_active": strategy.is_active,
            "is_paper_trading": strategy.is_paper_trading,
            "max_trade_amount": strategy.max_trade_amount,
            "stop_loss_percent": strategy.stop_loss_percent,
            "take_profit_percent": strategy.take_profit_percent,
            "max_open_trades": strategy.max_open_trades,
            "total_trades": strategy.total_trades,
            "winning_trades": strategy.winning_trades,
            "losing_trades": strategy.losing_trades,
            "total_profit_loss": strategy.total_profit_loss,
            "win_rate": strategy.win_rate,
            "symbols": symbol_statuses,
            "waiting_reason": waiting_reason,
            "last_trade_at": strategy.last_trade_at.isoformat() if strategy.last_trade_at else None
        })
    
    return strategies_with_status


async def _get_signal_info(binance_service, symbol: str, strategy_type: StrategyType) -> dict:
    """Obtiene información de señales para un símbolo"""
    try:
        klines = await binance_service.get_klines(symbol, "1m", 50)
        prices = [k["close"] for k in klines]
        
        if len(prices) < 20:
            return {"status": "insufficient_data", "message": "Esperando más datos históricos"}
        
        current_price = prices[-1]
        
        # Calcular indicadores
        rsi = calculate_rsi(prices, 14)
        macd = calculate_macd(prices)
        bollinger = calculate_bollinger_bands(prices)
        
        # Determinar señal según tipo de estrategia
        if strategy_type == StrategyType.RSI:
            if rsi["oversold"]:
                return {
                    "status": "buy_signal",
                    "message": f"RSI en sobreventa ({rsi['value']:.1f})",
                    "indicator": "RSI",
                    "value": rsi["value"],
                    "action": "BUY"
                }
            elif rsi["overbought"]:
                return {
                    "status": "sell_signal",
                    "message": f"RSI en sobrecompra ({rsi['value']:.1f})",
                    "indicator": "RSI",
                    "value": rsi["value"],
                    "action": "SELL"
                }
            else:
                distance_to_buy = 30 - rsi["value"]
                distance_to_sell = rsi["value"] - 70
                if rsi["value"] < 50:
                    return {
                        "status": "waiting",
                        "message": f"RSI: {rsi['value']:.1f} | Esperando < 30 para comprar",
                        "indicator": "RSI",
                        "value": rsi["value"],
                        "distance": abs(distance_to_buy)
                    }
                else:
                    return {
                        "status": "waiting",
                        "message": f"RSI: {rsi['value']:.1f} | Esperando > 70 para vender",
                        "indicator": "RSI",
                        "value": rsi["value"],
                        "distance": abs(distance_to_sell)
                    }
        
        elif strategy_type == StrategyType.MACD:
            if macd["trend"] == "strong_bullish" and macd["histogram"] > 0:
                return {
                    "status": "buy_signal",
                    "message": f"MACD alcista fuerte (hist: {macd['histogram']:.4f})",
                    "indicator": "MACD",
                    "value": macd["histogram"],
                    "action": "BUY"
                }
            elif macd["trend"] == "strong_bearish" and macd["histogram"] < 0:
                return {
                    "status": "sell_signal",
                    "message": f"MACD bajista fuerte (hist: {macd['histogram']:.4f})",
                    "indicator": "MACD",
                    "value": macd["histogram"],
                    "action": "SELL"
                }
            else:
                return {
                    "status": "waiting",
                    "message": f"MACD: {macd['trend']} | Esperando señal fuerte",
                    "indicator": "MACD",
                    "value": macd["histogram"],
                    "trend": macd["trend"]
                }
        
        elif strategy_type == StrategyType.BOLLINGER:
            if bollinger["position"] == "below_lower":
                return {
                    "status": "buy_signal",
                    "message": f"Precio bajo banda inferior",
                    "indicator": "Bollinger",
                    "value": current_price,
                    "lower": bollinger["lower"],
                    "action": "BUY"
                }
            elif bollinger["position"] == "above_upper":
                return {
                    "status": "sell_signal",
                    "message": f"Precio sobre banda superior",
                    "indicator": "Bollinger",
                    "value": current_price,
                    "upper": bollinger["upper"],
                    "action": "SELL"
                }
            else:
                return {
                    "status": "waiting",
                    "message": f"Precio en zona media | Banda: {bollinger['lower']:.2f} - {bollinger['upper']:.2f}",
                    "indicator": "Bollinger",
                    "position": bollinger["position"],
                    "lower": bollinger["lower"],
                    "upper": bollinger["upper"]
                }
        
        elif strategy_type == StrategyType.COMBINED:
            buy_signals = 0
            sell_signals = 0
            details = []
            
            if rsi["oversold"]:
                buy_signals += 1
                details.append(f"RSI: {rsi['value']:.1f} (compra)")
            elif rsi["overbought"]:
                sell_signals += 1
                details.append(f"RSI: {rsi['value']:.1f} (venta)")
            else:
                details.append(f"RSI: {rsi['value']:.1f} (neutral)")
            
            if macd["histogram"] > 0:
                buy_signals += 1
                details.append("MACD: positivo")
            else:
                sell_signals += 1
                details.append("MACD: negativo")
            
            if bollinger["position"] == "below_lower":
                buy_signals += 1
                details.append("BB: bajo")
            elif bollinger["position"] == "above_upper":
                sell_signals += 1
                details.append("BB: alto")
            else:
                details.append("BB: medio")
            
            if buy_signals >= 2:
                return {
                    "status": "buy_signal",
                    "message": f"{buy_signals}/3 señales de compra",
                    "details": details,
                    "action": "BUY"
                }
            elif sell_signals >= 2:
                return {
                    "status": "sell_signal",
                    "message": f"{sell_signals}/3 señales de venta",
                    "details": details,
                    "action": "SELL"
                }
            else:
                return {
                    "status": "waiting",
                    "message": f"Compra: {buy_signals}/3 | Venta: {sell_signals}/3 | Necesita 2+",
                    "details": details
                }
        
        elif strategy_type == StrategyType.SCALPING:
            # Scalping: más agresivo
            if rsi["value"] < 45 and macd["histogram"] > 0:
                return {
                    "status": "buy_signal",
                    "message": f"RSI {rsi['value']:.1f} < 45 + MACD positivo",
                    "indicator": "Scalping",
                    "action": "BUY"
                }
            elif rsi["value"] > 55 and macd["histogram"] < 0:
                return {
                    "status": "sell_signal",
                    "message": f"RSI {rsi['value']:.1f} > 55 + MACD negativo",
                    "indicator": "Scalping",
                    "action": "SELL"
                }
            elif bollinger["position"] == "lower_half" and rsi["value"] < 50:
                return {
                    "status": "buy_signal",
                    "message": f"BB inferior + RSI {rsi['value']:.1f}",
                    "indicator": "Scalping",
                    "action": "BUY"
                }
            elif bollinger["position"] == "upper_half" and rsi["value"] > 50:
                return {
                    "status": "sell_signal",
                    "message": f"BB superior + RSI {rsi['value']:.1f}",
                    "indicator": "Scalping",
                    "action": "SELL"
                }
            else:
                return {
                    "status": "waiting",
                    "message": f"RSI: {rsi['value']:.1f} | MACD: {macd['histogram']:.4f}",
                    "rsi": rsi["value"],
                    "macd": macd["histogram"]
                }
        
        # EMA Cross u otros
        return {
            "status": "waiting",
            "message": "Analizando mercado...",
            "rsi": rsi["value"],
            "macd": macd["histogram"]
        }
        
    except Exception as e:
        logger.error(f"Error getting signal info for {symbol}: {e}")
        return {"status": "error", "message": str(e)}


def _get_waiting_reason(strategy: Strategy, symbol_statuses: list) -> str:
    """Determina por qué la estrategia está esperando"""
    if not strategy.is_active:
        return "⏸️ Estrategia desactivada"
    
    # Contar trades abiertos
    open_trades = sum(1 for s in symbol_statuses if s["has_open_trade"])
    
    if open_trades >= strategy.max_open_trades:
        return f"📊 Máximo de trades abiertos alcanzado ({open_trades}/{strategy.max_open_trades})"
    
    # Verificar señales
    signals = [s["signal"] for s in symbol_statuses if s["signal"]]
    buy_signals = [s for s in signals if s.get("status") == "buy_signal"]
    sell_signals = [s for s in signals if s.get("status") == "sell_signal"]
    
    if buy_signals:
        symbol = next(s["symbol"] for s in symbol_statuses if s["signal"].get("status") == "buy_signal")
        return f"🟢 Señal de COMPRA detectada en {symbol}"
    
    if sell_signals:
        symbol = next(s["symbol"] for s in symbol_statuses if s["signal"].get("status") == "sell_signal")
        return f"🔴 Señal de VENTA detectada en {symbol}"
    
    # Mostrar qué está esperando
    waiting_info = []
    for s in symbol_statuses:
        if s["signal"] and s["signal"].get("message"):
            waiting_info.append(f"{s['symbol']}: {s['signal']['message']}")
    
    if waiting_info:
        return "⏳ " + " | ".join(waiting_info[:2])  # Máximo 2 para no saturar
    
    return "⏳ Esperando señales del mercado..."


@router.post("/", response_model=StrategyResponse)
async def create_strategy(
    strategy_data: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new trading strategy"""
    new_strategy = Strategy(
        user_id=current_user.id,
        name=strategy_data.name,
        strategy_type=strategy_data.strategy_type,
        description=strategy_data.description,
        symbols=json.dumps(strategy_data.symbols),
        max_trade_amount=strategy_data.max_trade_amount,
        stop_loss_percent=strategy_data.stop_loss_percent,
        take_profit_percent=strategy_data.take_profit_percent,
        max_open_trades=strategy_data.max_open_trades,
        config=json.dumps(strategy_data.config) if strategy_data.config else None,
        is_paper_trading=current_user.paper_trading
    )
    
    db.add(new_strategy)
    await db.commit()
    await db.refresh(new_strategy)
    
    return new_strategy


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific strategy"""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id
        )
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: int,
    strategy_data: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a strategy"""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id
        )
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # Update fields
    update_data = strategy_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "symbols" and value is not None:
            value = json.dumps(value)
        if field == "config" and value is not None:
            value = json.dumps(value)
        setattr(strategy, field, value)
    
    await db.commit()
    await db.refresh(strategy)
    
    return strategy


@router.post("/{strategy_id}/activate", response_model=StrategyResponse)
async def activate_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Activate a strategy for automated trading"""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id
        )
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy.is_active = True
    await db.commit()
    await db.refresh(strategy)
    
    logger.info(f"Strategy {strategy.name} activated by user {current_user.username}")
    
    return strategy


@router.post("/{strategy_id}/deactivate", response_model=StrategyResponse)
async def deactivate_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Deactivate a strategy"""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id
        )
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    strategy.is_active = False
    await db.commit()
    await db.refresh(strategy)
    
    logger.info(f"Strategy {strategy.name} deactivated by user {current_user.username}")
    
    return strategy


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a strategy"""
    result = await db.execute(
        select(Strategy).where(
            Strategy.id == strategy_id,
            Strategy.user_id == current_user.id
        )
    )
    strategy = result.scalar_one_or_none()
    
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if strategy.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an active strategy. Deactivate it first."
        )
    
    await db.delete(strategy)
    await db.commit()
    
    return {"message": "Strategy deleted successfully"}
