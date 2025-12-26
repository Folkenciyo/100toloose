from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.logging_config import trade_logger, logger
from app.models.user import User
from app.models.trade import Trade, TradeStatus, TradeType
from app.schemas.trade import TradeCreate, TradeResponse, TradeUpdate

router = APIRouter()


@router.get("/", response_model=List[TradeResponse])
async def get_trades(
    status_filter: TradeStatus = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all trades for the current user with current prices for open trades"""
    from app.services.binance_service import BinanceService
    
    query = select(Trade).where(Trade.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Trade.status == status_filter)
    
    query = query.order_by(Trade.created_at.desc()).limit(limit)
    result = await db.execute(query)
    trades = result.scalars().all()
    
    # Para trades abiertos, obtener precio actual y calcular valor actual
    open_trades = [t for t in trades if t.status == TradeStatus.OPEN]
    
    if open_trades:
        # Obtener API keys según el modo de trading
        if current_user.paper_trading:
            api_key = current_user.binance_testnet_api_key
            secret_key = current_user.binance_testnet_secret_key
        else:
            api_key = current_user.binance_real_api_key
            secret_key = current_user.binance_real_secret_key
        
        if api_key and secret_key:
            try:
                binance_service = BinanceService(
                    api_key=api_key,
                    secret_key=secret_key,
                    use_testnet=current_user.paper_trading
                )
                await binance_service.initialize()
                
                # Obtener todos los precios de una vez
                try:
                    all_prices = await binance_service.get_all_prices()
                except:
                    all_prices = {}
                
                # Crear diccionario de precios actuales para trades abiertos
                trade_extra_data = {}
                
                # Actualizar trades abiertos con precio actual
                for trade in open_trades:
                    if trade.quantity and trade.quantity > 0:
                        symbol = trade.symbol
                        current_price = all_prices.get(symbol)
                        
                        # Si no está en la lista, intentar obtenerlo individualmente
                        if not current_price:
                            try:
                                current_price = await binance_service.get_symbol_price(symbol)
                                all_prices[symbol] = current_price  # Cachear
                            except Exception as e:
                                logger.debug(f"Could not get price for {symbol}: {e}")
                                current_price = None
                        
                        if current_price:
                            # NUNCA modificar entry_price - es el precio al que se compró
                            # Si entry_price es 0 o None, el trade tiene un problema, pero no lo "arreglamos" con el precio actual
                            entry_price = trade.entry_price if trade.entry_price and trade.entry_price > 0 else None
                            
                            # Calcular invested_value: usar entry_price si existe, si no usar 0
                            # El invested_value puede ser 0 si entry_price es 0, pero entry_price NO se actualiza
                            if entry_price and entry_price > 0:
                                invested_value = trade.quantity * entry_price
                            else:
                                # Si no hay entry_price, el invested_value es 0 (trade inválido)
                                invested_value = 0
                            
                            current_value = trade.quantity * current_price
                            
                            if trade.trade_type == TradeType.BUY:
                                current_pnl = current_value - invested_value
                                current_pnl_percent = ((current_price - entry_price) / entry_price) * 100 if entry_price and entry_price > 0 else 0
                            else:  # SELL
                                current_pnl = invested_value - current_value  # Invertido para SELL
                                current_pnl_percent = ((entry_price - current_price) / entry_price) * 100 if entry_price and entry_price > 0 else 0
                            
                            # Guardar datos adicionales en diccionario
                            # IMPORTANTE: NO incluir entry_price aquí, solo datos calculados
                            trade_extra_data[trade.id] = {
                                "current_price": current_price,
                                "current_value": current_value,
                                "current_pnl": current_pnl,
                                "current_pnl_percent": current_pnl_percent,
                                "invested_value": invested_value
                            }
                
                # Asignar datos adicionales a los trades usando setattr (funciona con SQLAlchemy)
                for trade in trades:
                    if trade.id in trade_extra_data:
                        extra = trade_extra_data[trade.id]
                        setattr(trade, 'current_price', extra["current_price"])
                        setattr(trade, 'current_value', extra["current_value"])
                        setattr(trade, 'current_pnl', extra["current_pnl"])
                        setattr(trade, 'current_pnl_percent', extra["current_pnl_percent"])
                        setattr(trade, 'invested_value', extra["invested_value"])
                
                await binance_service.close()
            except Exception as e:
                logger.warning(f"Could not fetch current prices for open trades: {e}")
    
    logger.debug(f"User {current_user.username} fetched {len(trades)} trades")
    return trades


@router.post("/", response_model=TradeResponse)
async def create_trade(
    trade_data: TradeCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new trade (paper or real based on user settings)"""
    binance_service = request.app.state.binance
    
    trade_logger.info(f"📊 NEW TRADE REQUEST | User: {current_user.username} | Symbol: {trade_data.symbol} | Type: {trade_data.trade_type.value} | Qty: {trade_data.quantity}")
    
    # Get current price
    try:
        current_price = await binance_service.get_symbol_price(trade_data.symbol)
        trade_logger.info(f"   └─ Current price: ${current_price:,.2f}")
    except Exception as e:
        trade_logger.error(f"   └─ ❌ Failed to get price for {trade_data.symbol}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not get price for {trade_data.symbol}: {str(e)}"
        )
    
    # Calculate trade value
    trade_value = current_price * trade_data.quantity
    trade_logger.info(f"   └─ Trade value: ${trade_value:,.2f}")
    
    # Check if user has enough balance (for paper trading)
    if current_user.paper_trading and trade_data.trade_type == TradeType.BUY:
        if trade_value > current_user.current_balance:
            trade_logger.warning(f"   └─ ⚠️ Insufficient balance. Required: ${trade_value:.2f}, Available: ${current_user.current_balance:.2f}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Insufficient balance. Required: {trade_value:.2f}, Available: {current_user.current_balance:.2f}"
            )
    
    # Calculate stop loss and take profit if not provided
    stop_loss = trade_data.stop_loss
    take_profit = trade_data.take_profit
    
    if not stop_loss:
        stop_loss = current_price * 0.98 if trade_data.trade_type == TradeType.BUY else current_price * 1.02
    if not take_profit:
        take_profit = current_price * 1.03 if trade_data.trade_type == TradeType.BUY else current_price * 0.97
    
    trade_logger.info(f"   └─ Stop Loss: ${stop_loss:,.2f} | Take Profit: ${take_profit:,.2f}")
    
    # Create trade
    new_trade = Trade(
        user_id=current_user.id,
        symbol=trade_data.symbol,
        trade_type=trade_data.trade_type,
        status=TradeStatus.OPEN,
        entry_price=current_price,
        quantity=trade_data.quantity,
        stop_loss=stop_loss,
        take_profit=take_profit,
        strategy_name=trade_data.strategy_name,
        opened_at=datetime.utcnow(),
        is_paper_trade=1 if current_user.paper_trading else 0
    )
    
    # Update user balance for paper trading
    if current_user.paper_trading and trade_data.trade_type == TradeType.BUY:
        current_user.current_balance -= trade_value
        trade_logger.info(f"   └─ New balance: ${current_user.current_balance:,.2f}")
    
    db.add(new_trade)
    await db.commit()
    await db.refresh(new_trade)
    
    trade_logger.info(f"   └─ ✅ TRADE OPENED | ID: {new_trade.id} | {'📝 PAPER' if new_trade.is_paper_trade else '💰 REAL'}")
    
    return new_trade


@router.post("/{trade_id}/close", response_model=TradeResponse)
async def close_trade(
    trade_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Close an open trade and execute order on Binance"""
    from app.services.binance_service import BinanceService
    
    trade_logger.info(f"📊 CLOSE TRADE REQUEST | User: {current_user.username} | Trade ID: {trade_id}")
    
    # Get trade
    result = await db.execute(
        select(Trade).where(Trade.id == trade_id, Trade.user_id == current_user.id)
    )
    trade = result.scalar_one_or_none()
    
    if not trade:
        trade_logger.warning(f"   └─ ⚠️ Trade {trade_id} not found for user {current_user.username}")
        raise HTTPException(status_code=404, detail="Trade not found")
    
    if trade.status != TradeStatus.OPEN:
        trade_logger.warning(f"   └─ ⚠️ Trade {trade_id} is not open (status: {trade.status})")
        raise HTTPException(status_code=400, detail="Trade is not open")
    
    trade_logger.info(f"   └─ Symbol: {trade.symbol} | Entry: ${trade.entry_price:,.2f} | Qty: {trade.quantity:.6f}")
    
    # Obtener las API keys correctas según el modo
    if current_user.paper_trading:
        api_key = current_user.binance_testnet_api_key
        secret_key = current_user.binance_testnet_secret_key
        binance_mode = "Testnet"
    else:
        api_key = current_user.binance_real_api_key
        secret_key = current_user.binance_real_secret_key
        binance_mode = "Real"
    
    # Get current price
    binance_service_public = request.app.state.binance
    current_price = await binance_service_public.get_symbol_price(trade.symbol)
    trade_logger.info(f"   └─ Current price: ${current_price:,.2f}")
    
    # Ejecutar orden de cierre en Binance si tiene API keys
    binance_close_order_id = None
    actual_exit_price = current_price
    actual_exit_quantity = trade.quantity
    
    if api_key and secret_key:
        try:
            # Determinar lado de la orden de cierre
            # Si abrimos BUY, cerramos con SELL
            # Si abrimos SELL, cerramos con BUY
            close_side = "SELL" if trade.trade_type == TradeType.BUY else "BUY"
            
            binance_service = BinanceService(
                api_key=api_key,
                secret_key=secret_key,
                use_testnet=current_user.paper_trading
            )
            await binance_service.initialize()
            
            trade_logger.info(f"📡 Closing order on Binance {binance_mode}: {close_side} {trade.symbol}")
            
            # Para cerrar un BUY, vendemos (SELL) la cantidad que tenemos
            # Para cerrar un SELL, compramos (BUY) la cantidad que vendimos
            if close_side == "SELL":
                # Vender la cantidad que tenemos
                order_response = await binance_service.place_order(
                    symbol=trade.symbol,
                    side="SELL",
                    order_type="MARKET",
                    quantity=trade.quantity
                )
            else:
                # Comprar para cerrar un SELL (necesitamos USDT)
                # Calcular cuánto USDT necesitamos
                required_usdt = current_price * trade.quantity
                order_response = await binance_service.place_order(
                    symbol=trade.symbol,
                    side="BUY",
                    order_type="MARKET",
                    quote_order_qty=required_usdt
                )
            
            binance_close_order_id = str(order_response.get("orderId"))
            actual_exit_price = float(order_response.get("price", current_price))
            actual_exit_quantity = float(order_response.get("executedQty", trade.quantity))
            
            trade_logger.info(f"✅ Binance close order executed: OrderID={binance_close_order_id}, Price=${actual_exit_price:.2f}, Qty={actual_exit_quantity:.6f}")
            
            await binance_service.close()
            
        except Exception as e:
            trade_logger.error(f"❌ Failed to execute Binance close order: {e}")
            # Si falla la orden en Binance, aún así cerramos el trade en la BD
            # para evitar que quede "colgado"
            logger.warning(f"Closing trade {trade_id} manually in database due to Binance error")
    
    # Calcular P&L con el precio real de ejecución
    if trade.trade_type == TradeType.BUY:
        profit_loss = (actual_exit_price - trade.entry_price) * actual_exit_quantity
    else:
        profit_loss = (trade.entry_price - actual_exit_price) * actual_exit_quantity
    
    profit_loss_percent = (profit_loss / (trade.entry_price * trade.quantity)) * 100 if trade.entry_price * trade.quantity > 0 else 0
    
    # Update trade
    trade.exit_price = actual_exit_price
    trade.profit_loss = profit_loss
    trade.profit_loss_percent = profit_loss_percent
    trade.status = TradeStatus.CLOSED
    trade.closed_at = datetime.utcnow()
    if binance_close_order_id:
        # Guardar el order ID del cierre si existe
        trade.binance_order_id = f"{trade.binance_order_id or ''},close:{binance_close_order_id}".strip(',').strip()
    
    # Update user balance solo si es paper trading simulado (sin API keys)
    if trade.is_paper_trade and not (api_key and secret_key):
        trade_value = actual_exit_price * actual_exit_quantity
        if trade.trade_type == TradeType.BUY:
            current_user.current_balance += trade_value
        else:
            current_user.current_balance += profit_loss
        trade_logger.info(f"   └─ New balance: ${current_user.current_balance:,.2f}")
    # Si tiene API keys, el balance se actualiza desde Binance
    
    await db.commit()
    await db.refresh(trade)
    
    # Log result
    result_emoji = "✅ WIN" if profit_loss > 0 else "❌ LOSS" if profit_loss < 0 else "➖ BREAK-EVEN"
    trade_logger.info(f"   └─ {result_emoji} | P&L: ${profit_loss:,.2f} ({profit_loss_percent:+.2f}%)")
    
    # Enviar notificaciones de Telegram y Email
    try:
        from app.services.telegram_service import TelegramService
        from app.services.email_service import EmailService
        
        # Telegram notification
        telegram_configured = (
            current_user.telegram_enabled and 
            current_user.telegram_bot_token and 
            current_user.telegram_chat_id
        )
        
        if not telegram_configured:
            missing = []
            if not current_user.telegram_enabled:
                missing.append("telegram_enabled=False")
            if not current_user.telegram_bot_token:
                missing.append("bot_token missing")
            if not current_user.telegram_chat_id:
                missing.append("chat_id missing")
            trade_logger.warning(
                f"   └─ ⚠️ Telegram notification SKIPPED: Missing configuration: {', '.join(missing)}"
            )
        else:
            try:
                telegram_service = TelegramService(
                    bot_token=current_user.telegram_bot_token,
                    chat_id=current_user.telegram_chat_id
                )
                trade_logger.info(
                    f"   └─ 📱 Sending Telegram notification: CLOSE {trade.symbol} | "
                    f"P&L: ${profit_loss:.2f}"
                )
                await telegram_service.send_trade_notification(
                    trade_type="close",
                    symbol=trade.symbol,
                    price=actual_exit_price,
                    quantity=actual_exit_quantity,
                    profit_loss=profit_loss
                )
                trade_logger.info(f"   └─ ✅ Telegram notification sent successfully")
            except Exception as e:
                trade_logger.error(
                    f"   └─ ❌ Failed to send Telegram notification: {e}",
                    exc_info=True
                )
        
        # Email notification (opcional, solo si está configurado)
        if current_user.smtp_enabled and current_user.summary_email:
            try:
                email_service = EmailService(
                    host=current_user.smtp_host,
                    port=current_user.smtp_port,
                    user=current_user.smtp_user,
                    password=current_user.smtp_password,
                    from_email=current_user.smtp_from_email
                )
                # Enviar notificación de cierre de trade
                subject = f"Trade Closed: {trade.symbol} - {result_emoji}"
                body = f"""
Trade Closed Manually

Symbol: {trade.symbol}
Type: {trade.trade_type.value.upper()}
Entry Price: ${trade.entry_price:,.2f}
Exit Price: ${actual_exit_price:,.2f}
Quantity: {actual_exit_quantity:.6f}
Profit/Loss: ${profit_loss:,.2f} ({profit_loss_percent:+.2f}%)
Status: {result_emoji}

Closed at: {trade.closed_at}
                """
                await email_service.send_email(
                    to_email=current_user.summary_email,
                    subject=subject,
                    body=body.strip()
                )
                trade_logger.info(f"   └─ 📧 Email notification sent")
            except Exception as e:
                trade_logger.warning(f"   └─ ⚠️ Failed to send Email notification: {e}")
    except Exception as e:
        trade_logger.warning(f"   └─ ⚠️ Error sending notifications: {e}")
    
    return trade


@router.get("/open", response_model=List[TradeResponse])
async def get_open_trades(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all open trades for the current user"""
    query = select(Trade).where(
        Trade.user_id == current_user.id,
        Trade.status == TradeStatus.OPEN
    ).order_by(Trade.opened_at.desc())
    
    result = await db.execute(query)
    trades = result.scalars().all()
    
    logger.debug(f"User {current_user.username} has {len(trades)} open trades")
    return trades
