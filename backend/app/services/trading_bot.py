"""
Autonomous Trading Bot
Executes trades based on strategy signals
"""
import asyncio
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User
from app.models.trade import Trade, TradeStatus, TradeType
from app.models.strategy import Strategy, StrategyType
from app.services.binance_service import BinanceService
from app.services.indicators import calculate_indicators


class TradingBot:
    """Autonomous trading bot that monitors markets and executes trades"""
    
    def __init__(
        self,
        binance_service: BinanceService,
        db_session_factory,
        check_interval: int = 60  # Check every 60 seconds
    ):
        self.binance = binance_service
        self.db_session_factory = db_session_factory
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the trading bot"""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._run_loop())
        print("🤖 Trading bot started")
    
    async def stop(self):
        """Stop the trading bot"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("🛑 Trading bot stopped")
    
    async def _run_loop(self):
        """Main loop that checks for trading opportunities"""
        while self.running:
            try:
                await self._check_strategies()
                await self._check_open_trades()
            except Exception as e:
                print(f"❌ Trading bot error: {e}")
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_strategies(self):
        """Check all active strategies for trading signals"""
        async with self.db_session_factory() as db:
            # Get all active strategies
            result = await db.execute(
                select(Strategy).where(Strategy.is_active == True)
            )
            strategies = result.scalars().all()
            
            for strategy in strategies:
                await self._process_strategy(db, strategy)
    
    async def _process_strategy(self, db: AsyncSession, strategy: Strategy):
        """Process a single strategy and execute trades if signals are found"""
        try:
            # Get user
            result = await db.execute(
                select(User).where(User.id == strategy.user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return
            
            # Parse symbols
            symbols = json.loads(strategy.symbols)
            
            for symbol in symbols:
                # Check if we already have max open trades
                open_trades = await db.execute(
                    select(Trade).where(
                        Trade.user_id == user.id,
                        Trade.status == TradeStatus.OPEN
                    )
                )
                open_count = len(open_trades.scalars().all())
                
                if open_count >= strategy.max_open_trades:
                    continue
                
                # Get market data and analyze
                try:
                    klines = await self.binance.get_klines(symbol, "1h", 100)
                    analysis = calculate_indicators(klines)
                    
                    # Check for trading signals based on strategy type
                    signal = self._get_strategy_signal(strategy, analysis)
                    
                    if signal:
                        await self._execute_trade(db, user, strategy, symbol, signal, analysis)
                
                except Exception as e:
                    print(f"Error analyzing {symbol}: {e}")
        
        except Exception as e:
            print(f"Error processing strategy {strategy.id}: {e}")
    
    def _get_strategy_signal(
        self,
        strategy: Strategy,
        analysis: Dict[str, Any]
    ) -> Optional[str]:
        """Determine if we should buy/sell based on strategy type"""
        
        if strategy.strategy_type == StrategyType.RSI:
            # RSI Strategy: Buy when oversold, sell when overbought
            rsi = analysis["rsi"]
            if rsi["oversold"]:
                return "BUY"
            elif rsi["overbought"]:
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.MACD:
            # MACD Strategy: Buy on bullish crossover
            macd = analysis["macd"]
            if macd["trend"] == "strong_bullish" and macd["histogram"] > 0:
                return "BUY"
            elif macd["trend"] == "strong_bearish" and macd["histogram"] < 0:
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.BOLLINGER:
            # Bollinger Bands Strategy: Buy at lower band, sell at upper
            bb = analysis["bollinger_bands"]
            if bb["position"] == "below_lower":
                return "BUY"
            elif bb["position"] == "above_upper":
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.EMA_CROSS:
            # EMA Crossover Strategy
            ema = analysis["ema"]
            if ema["signal"] == "bullish" and analysis["recommendation"] in ["BUY", "STRONG_BUY"]:
                return "BUY"
            elif ema["signal"] == "bearish" and analysis["recommendation"] in ["SELL", "STRONG_SELL"]:
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.COMBINED:
            # Combined Strategy: Requires multiple confirmations
            if analysis["recommendation"] == "STRONG_BUY":
                return "BUY"
            elif analysis["recommendation"] == "STRONG_SELL":
                return "SELL"
        
        return None
    
    async def _execute_trade(
        self,
        db: AsyncSession,
        user: User,
        strategy: Strategy,
        symbol: str,
        signal: str,
        analysis: Dict[str, Any]
    ):
        """Execute a trade based on the signal"""
        current_price = analysis["current_price"]
        
        # Calculate quantity based on trade amount
        quantity = strategy.max_trade_amount / current_price
        
        # Check balance for paper trading
        if user.paper_trading:
            trade_value = current_price * quantity
            if signal == "BUY" and trade_value > user.current_balance:
                return  # Not enough balance
        
        # Calculate stop loss and take profit
        if signal == "BUY":
            stop_loss = current_price * (1 - strategy.stop_loss_percent / 100)
            take_profit = current_price * (1 + strategy.take_profit_percent / 100)
            trade_type = TradeType.BUY
        else:
            stop_loss = current_price * (1 + strategy.stop_loss_percent / 100)
            take_profit = current_price * (1 - strategy.take_profit_percent / 100)
            trade_type = TradeType.SELL
        
        # Create trade
        trade = Trade(
            user_id=user.id,
            symbol=symbol,
            trade_type=trade_type,
            status=TradeStatus.OPEN,
            entry_price=current_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=strategy.name,
            strategy_signals=json.dumps(analysis),
            opened_at=datetime.utcnow(),
            is_paper_trade=1 if user.paper_trading else 0
        )
        
        # Update user balance for paper trading
        if user.paper_trading and signal == "BUY":
            user.current_balance -= current_price * quantity
        
        # Update strategy stats
        strategy.total_trades += 1
        strategy.last_trade_at = datetime.utcnow()
        
        db.add(trade)
        await db.commit()
        
        print(f"🔔 Trade executed: {signal} {symbol} @ {current_price} (Strategy: {strategy.name})")
    
    async def _check_open_trades(self):
        """Check open trades for stop loss / take profit"""
        async with self.db_session_factory() as db:
            # Get all open trades
            result = await db.execute(
                select(Trade).where(Trade.status == TradeStatus.OPEN)
            )
            trades = result.scalars().all()
            
            for trade in trades:
                await self._check_trade_exit(db, trade)
    
    async def _check_trade_exit(self, db: AsyncSession, trade: Trade):
        """Check if a trade should be closed (stop loss or take profit)"""
        try:
            current_price = await self.binance.get_symbol_price(trade.symbol)
            
            should_close = False
            
            if trade.trade_type == TradeType.BUY:
                # Check stop loss
                if trade.stop_loss and current_price <= trade.stop_loss:
                    should_close = True
                # Check take profit
                elif trade.take_profit and current_price >= trade.take_profit:
                    should_close = True
            else:  # SELL
                # Check stop loss
                if trade.stop_loss and current_price >= trade.stop_loss:
                    should_close = True
                # Check take profit
                elif trade.take_profit and current_price <= trade.take_profit:
                    should_close = True
            
            if should_close:
                await self._close_trade(db, trade, current_price)
        
        except Exception as e:
            print(f"Error checking trade {trade.id}: {e}")
    
    async def _close_trade(self, db: AsyncSession, trade: Trade, exit_price: float):
        """Close a trade"""
        # Calculate P&L
        if trade.trade_type == TradeType.BUY:
            profit_loss = (exit_price - trade.entry_price) * trade.quantity
        else:
            profit_loss = (trade.entry_price - exit_price) * trade.quantity
        
        profit_loss_percent = (profit_loss / (trade.entry_price * trade.quantity)) * 100
        
        # Update trade
        trade.exit_price = exit_price
        trade.profit_loss = profit_loss
        trade.profit_loss_percent = profit_loss_percent
        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.utcnow()
        
        # Update user balance for paper trading
        if trade.is_paper_trade:
            result = await db.execute(
                select(User).where(User.id == trade.user_id)
            )
            user = result.scalar_one_or_none()
            if user:
                if trade.trade_type == TradeType.BUY:
                    user.current_balance += exit_price * trade.quantity
                else:
                    user.current_balance += profit_loss
        
        # Update strategy stats
        if trade.strategy_name:
            result = await db.execute(
                select(Strategy).where(
                    Strategy.user_id == trade.user_id,
                    Strategy.name == trade.strategy_name
                )
            )
            strategy = result.scalar_one_or_none()
            if strategy:
                if profit_loss > 0:
                    strategy.winning_trades += 1
                else:
                    strategy.losing_trades += 1
                strategy.total_profit_loss += profit_loss
                if strategy.total_trades > 0:
                    strategy.win_rate = (strategy.winning_trades / strategy.total_trades) * 100
        
        await db.commit()
        
        status = "✅ WIN" if profit_loss > 0 else "❌ LOSS"
        print(f"{status} Trade closed: {trade.symbol} P&L: ${profit_loss:.2f} ({profit_loss_percent:.2f}%)")


