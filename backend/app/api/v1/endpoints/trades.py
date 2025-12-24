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
    """Get all trades for the current user"""
    query = select(Trade).where(Trade.user_id == current_user.id)
    
    if status_filter:
        query = query.where(Trade.status == status_filter)
    
    query = query.order_by(Trade.created_at.desc()).limit(limit)
    result = await db.execute(query)
    trades = result.scalars().all()
    
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
    """Close an open trade"""
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
    
    trade_logger.info(f"   └─ Symbol: {trade.symbol} | Entry: ${trade.entry_price:,.2f}")
    
    # Get current price
    binance_service = request.app.state.binance
    current_price = await binance_service.get_symbol_price(trade.symbol)
    trade_logger.info(f"   └─ Exit price: ${current_price:,.2f}")
    
    # Calculate P&L
    if trade.trade_type == TradeType.BUY:
        profit_loss = (current_price - trade.entry_price) * trade.quantity
    else:
        profit_loss = (trade.entry_price - current_price) * trade.quantity
    
    profit_loss_percent = (profit_loss / (trade.entry_price * trade.quantity)) * 100
    
    # Update trade
    trade.exit_price = current_price
    trade.profit_loss = profit_loss
    trade.profit_loss_percent = profit_loss_percent
    trade.status = TradeStatus.CLOSED
    trade.closed_at = datetime.utcnow()
    
    # Update user balance for paper trading
    if trade.is_paper_trade:
        trade_value = current_price * trade.quantity
        if trade.trade_type == TradeType.BUY:
            current_user.current_balance += trade_value
        else:
            current_user.current_balance += profit_loss
        trade_logger.info(f"   └─ New balance: ${current_user.current_balance:,.2f}")
    
    await db.commit()
    await db.refresh(trade)
    
    # Log result
    result_emoji = "✅ WIN" if profit_loss > 0 else "❌ LOSS" if profit_loss < 0 else "➖ BREAK-EVEN"
    trade_logger.info(f"   └─ {result_emoji} | P&L: ${profit_loss:,.2f} ({profit_loss_percent:+.2f}%)")
    
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
