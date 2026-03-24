"""
Bot de Trading en Tiempo Real
Toma decisiones basadas en datos de WebSocket, no polling
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from collections import deque
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, desc, update, func

from app.core.logging_config import logger, trade_logger, deepseek_logger, email_logger, telegram_logger
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.trade import Trade, TradeStatus, TradeType
from app.models.strategy import Strategy, StrategyType
from app.services.websocket_manager import binance_ws, client_ws_manager
from app.services.indicators import calculate_rsi, calculate_macd, calculate_bollinger_bands
from app.services.binance_service import BinanceService
from app.services.telegram_service import TelegramService
from app.services.email_service import EmailService
from app.services.deepseek_service import DeepSeekService
from app.models.deepseek_decision import DeepSeekDecision
from app.core.logging_config import deepseek_logger, email_logger, telegram_logger
import json


class RealtimeTradingBot:
    """
    Bot de trading que opera en tiempo real usando WebSocket.
    
    - Recibe precios cada ~100ms desde Binance
    - Analiza cuando cierra cada vela de 1 minuto
    - Ejecuta trades inmediatamente cuando hay señal
    - Monitorea stop-loss y take-profit en tiempo real
    """
    
    def __init__(self, binance_service: BinanceService):
        self.binance = binance_service
        self.running = False
        self.db_session_factory = AsyncSessionLocal
        
        # Cache de datos para análisis
        self.price_history: Dict[str, deque] = {}  # symbol -> últimos 100 precios
        self.kline_history: Dict[str, deque] = {}  # symbol -> últimas 100 velas
        
        # Símbolos activos (de estrategias activas)
        self.active_symbols: set = set()
        
        # Cooldown para evitar trades muy seguidos
        self.last_trade_time: Dict[str, datetime] = {}
        self.trade_cooldown_default = timedelta(minutes=5)
        self.trade_cooldown_scalping = timedelta(minutes=1)  # Scalping más rápido
        
        # Sistema de resúmenes por email
        self.email_summary_queue: Dict[int, List[Dict]] = {}  # user_id -> lista de trades para resumen
        self.last_summary_sent: Dict[int, datetime] = {}  # user_id -> última vez que se envió resumen
        
        # Estadísticas
        self.stats = {
            "signals_detected": 0,
            "trades_executed": 0,
            "trades_skipped": 0,
            "errors": 0
        }
    
    async def start(self):
        """Inicia el bot de trading en tiempo real"""
        if self.running:
            logger.warning("Realtime bot already running")
            return
        
        self.running = True
        trade_logger.info("=" * 60)
        trade_logger.info("🤖 REALTIME TRADING BOT STARTED")
        trade_logger.info("=" * 60)
        
        # Cargar símbolos de estrategias activas
        await self._load_active_symbols()
        
        if not self.active_symbols:
            trade_logger.warning("No active strategies found. Bot will wait...")
        else:
            trade_logger.info(f"Monitoring {len(self.active_symbols)} symbols: {self.active_symbols}")
        
        # Cargar datos históricos para cada símbolo
        await self._load_historical_data()
        
        # Iniciar WebSocket de Binance
        await binance_ws.start(list(self.active_symbols) if self.active_symbols else None)
        
        # Registrar callbacks
        for symbol in self.active_symbols:
            binance_ws.on_price_update(symbol, self._on_price_update)
            binance_ws.on_kline_close(symbol, self._on_kline_close)
        
        # Reconciliar trades abiertos en BD contra Binance (por si el bot se cayó)
        await self._reconcile_open_trades()

        # Iniciar loop de monitoreo de trades abiertos
        asyncio.create_task(self._monitor_open_trades())

        # Iniciar loop de recarga de estrategias
        asyncio.create_task(self._reload_strategies_loop())

        trade_logger.info("✅ Realtime bot fully initialized")
    
    async def _reconcile_open_trades(self):
        """Al arrancar, verifica el estado real de los trades OPEN en BD contra Binance.

        Detecta trades que se quedaron OPEN en BD pero la orden fue ejecutada/cancelada
        en Binance mientras el bot estaba caído, y los marca como CLOSED o CANCELLED.
        Solo actúa en trades con binance_order_id; los sin order ID (simulación pura) se dejan.
        """
        trade_logger.info("🔄 Reconciling open trades against Binance...")
        try:
            async with self.db_session_factory() as db:
                result = await db.execute(
                    select(Trade).where(Trade.status == TradeStatus.OPEN)
                )
                open_trades = result.scalars().all()

                if not open_trades:
                    trade_logger.info("   No open trades to reconcile")
                    return

                trade_logger.info(f"   Found {len(open_trades)} open trade(s) to check")

                for trade in open_trades:
                    # Trades sin order ID son simulaciones puras — no hay nada que verificar
                    if not trade.binance_order_id:
                        continue

                    # Obtener el usuario y sus API keys
                    user_result = await db.execute(
                        select(User).where(User.id == trade.user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if not user:
                        continue

                    api_key = user.binance_testnet_api_key if user.paper_trading else user.binance_real_api_key
                    secret_key = user.binance_testnet_secret_key if user.paper_trading else user.binance_real_secret_key

                    if not api_key or not secret_key:
                        continue

                    try:
                        svc = BinanceService(
                            api_key=api_key,
                            secret_key=secret_key,
                            use_testnet=user.paper_trading,
                        )
                        order = await svc.get_order_status(
                            symbol=trade.symbol,
                            order_id=int(trade.binance_order_id),
                        )
                        await svc.close()

                        order_status = order.get("status", "")

                        if order_status in ("FILLED", "PARTIALLY_FILLED"):
                            # La orden se ejecutó — el trade sigue abierto, correcto
                            trade_logger.info(
                                f"   ✅ Trade {trade.id} ({trade.symbol}) confirmed OPEN on Binance"
                            )
                        elif order_status in ("CANCELED", "REJECTED", "EXPIRED"):
                            # La orden fue cancelada en Binance — marcar como CANCELLED en BD
                            trade.status = TradeStatus.CANCELLED
                            trade.closed_at = datetime.utcnow()
                            await db.commit()
                            trade_logger.warning(
                                f"   ⚠️ Trade {trade.id} ({trade.symbol}) was {order_status} on Binance — marked CANCELLED"
                            )

                    except Exception as e:
                        trade_logger.error(
                            f"   ❌ Could not reconcile trade {trade.id} ({trade.symbol}): {e}"
                        )

        except Exception as e:
            trade_logger.error(f"Reconciliation error: {e}")

    async def stop(self):
        """Detiene el bot"""
        self.running = False
        await binance_ws.stop()
        trade_logger.info("🛑 Realtime trading bot stopped")
        trade_logger.info(f"Stats: {self.stats}")
    
    async def _load_active_symbols(self):
        """Carga símbolos de estrategias activas"""
        async with self.db_session_factory() as db:
            result = await db.execute(
                select(Strategy).where(Strategy.is_active == True)
            )
            strategies = result.scalars().all()
            
            self.active_symbols.clear()
            for strategy in strategies:
                symbols = json.loads(strategy.symbols)
                self.active_symbols.update(symbols)
    
    async def _load_historical_data(self):
        """Carga datos históricos para análisis inicial"""
        for symbol in self.active_symbols:
            try:
                klines = await self.binance.get_klines(symbol, "1m", 100)
                
                # Inicializar deques
                self.price_history[symbol] = deque(maxlen=100)
                self.kline_history[symbol] = deque(maxlen=100)
                
                for kline in klines:
                    self.price_history[symbol].append(kline["close"])
                    self.kline_history[symbol].append(kline)
                
                trade_logger.info(f"Loaded {len(klines)} historical klines for {symbol}")
            except Exception as e:
                logger.error(f"Failed to load history for {symbol}: {e}")
    
    async def _on_price_update(self, symbol: str, price: float, old_price: float):
        """Callback cuando se actualiza el precio (cada ~100ms)"""
        # Actualizar precio en cache
        if symbol in self.price_history:
            # Solo actualizar el último precio, no añadir
            if self.price_history[symbol]:
                self.price_history[symbol][-1] = price
        
        # Verificar stop-loss y take-profit de trades abiertos
        await self._check_price_triggers(symbol, price)
        
        # Enviar a clientes conectados
        change = ((price - old_price) / old_price * 100) if old_price else 0
        await client_ws_manager.send_price_update(symbol, price, change)
    
    async def _on_kline_close(self, symbol: str, kline: dict):
        """Callback cuando cierra una vela de 1 minuto - MOMENTO DE ANÁLISIS"""
        trade_logger.debug(f"📊 Kline closed: {symbol} @ {kline['close']}")
        
        # Añadir a historial
        if symbol not in self.kline_history:
            self.kline_history[symbol] = deque(maxlen=100)
        self.kline_history[symbol].append(kline)
        
        if symbol not in self.price_history:
            self.price_history[symbol] = deque(maxlen=100)
        self.price_history[symbol].append(kline["close"])
        
        # Analizar y buscar señales
        await self._analyze_and_trade(symbol)
    
    async def _analyze_and_trade(self, symbol: str):
        """Analiza el símbolo y ejecuta trades si hay señal"""
        if len(self.price_history.get(symbol, [])) < 30:
            return  # No hay suficientes datos
        
        prices = list(self.price_history[symbol])
        current_price = prices[-1]
        
        # Calcular indicadores
        rsi = calculate_rsi(prices, 14)
        macd = calculate_macd(prices)
        bollinger = calculate_bollinger_bands(prices)
        
        async with self.db_session_factory() as db:
            # Obtener estrategias activas para este símbolo
            result = await db.execute(
                select(Strategy).where(Strategy.is_active == True)
            )
            strategies = result.scalars().all()
            
            for strategy in strategies:
                strategy_symbols = json.loads(strategy.symbols)
                if symbol not in strategy_symbols:
                    continue
                
                # Verificar cooldown (más corto para scalping)
                cooldown_key = f"{strategy.id}_{symbol}"
                cooldown = self.trade_cooldown_scalping if strategy.strategy_type == StrategyType.SCALPING else self.trade_cooldown_default
                if cooldown_key in self.last_trade_time:
                    if datetime.utcnow() - self.last_trade_time[cooldown_key] < cooldown:
                        continue
                
                # Verificar trades abiertos
                open_trades = await db.execute(
                    select(Trade).where(
                        Trade.user_id == strategy.user_id,
                        Trade.symbol == symbol,
                        Trade.status == TradeStatus.OPEN
                    )
                )
                if open_trades.scalars().first():
                    continue  # Ya hay un trade abierto para este símbolo
                
                # Obtener usuario para verificar configuración de DeepSeek
                user_result = await db.execute(
                    select(User).where(User.id == strategy.user_id)
                )
                user = user_result.scalar_one_or_none()
                if not user:
                    continue

                # Verificar límite de pérdida diaria
                if await self._check_daily_loss_limit(db, user):
                    continue  # Límite superado, no operar

                # Obtener señal técnica según tipo de estrategia
                technical_signal = self._get_signal(strategy, rsi, macd, bollinger, current_price)
                
                if technical_signal:
                    self.stats["signals_detected"] += 1
                    trade_logger.info(f"🔔 TECHNICAL SIGNAL: {technical_signal} {symbol} | Strategy: {strategy.name}")
                    
                    # Si DeepSeek está habilitado, consultarlo antes de ejecutar
                    final_signal = technical_signal
                    execution_reason = "Technical signal"
                    deepseek_decision_id = None
                    
                    if user.deepseek_enabled and user.deepseek_api_key:
                        try:
                            deepseek_logger.info(f"🤖 Consulting DeepSeek for {symbol} | Signal: {technical_signal}")
                            
                            deepseek_service = DeepSeekService(api_key=user.deepseek_api_key)
                            
                            # Obtener trades recientes del usuario
                            recent_trades_result = await db.execute(
                                select(Trade)
                                .where(Trade.user_id == user.id)
                                .where(Trade.symbol == symbol)
                                .order_by(desc(Trade.opened_at))
                                .limit(10)
                            )
                            recent_trades = recent_trades_result.scalars().all()
                            
                            recent_trades_data = [
                                {
                                    "symbol": t.symbol,
                                    "type": t.trade_type.value,
                                    "entry_price": float(t.entry_price),
                                    "exit_price": float(t.exit_price) if t.exit_price else None,
                                    "profit_loss": float(t.profit_loss) if t.profit_loss else None,
                                    "status": t.status.value
                                }
                                for t in recent_trades
                            ]
                            
                            # Contexto del mercado
                            market_context = {
                                "volume_24h": "N/A",
                                "trend": "N/A",
                                "volatility": "N/A"
                            }
                            
                            # Análisis con DeepSeek
                            deepseek_analysis = await deepseek_service.analyze_trading_opportunity(
                                symbol=symbol,
                                current_price=current_price,
                                indicators={
                                    "rsi": rsi,
                                    "macd": macd,
                                    "bollinger_bands": bollinger,
                                    "ema": {"signal": "neutral"}
                                },
                                recent_trades=recent_trades_data,
                                market_context=market_context
                            )
                            
                            await deepseek_service.close()
                            
                            # Guardar decisión de DeepSeek
                            decision = DeepSeekDecision(
                                user_id=user.id,
                                strategy_id=strategy.id,
                                symbol=symbol,
                                current_price=current_price,
                                recommendation=deepseek_analysis["recommendation"],
                                confidence=deepseek_analysis["confidence"],
                                risk_assessment=deepseek_analysis["risk_assessment"],
                                suggested_entry=deepseek_analysis.get("suggested_entry"),
                                suggested_stop_loss=deepseek_analysis.get("suggested_stop_loss"),
                                suggested_take_profit=deepseek_analysis.get("suggested_take_profit"),
                                reasoning=deepseek_analysis["reasoning"],
                                indicators_snapshot=json.dumps({
                                    "rsi": rsi,
                                    "macd": macd,
                                    "bollinger": bollinger
                                }),
                                was_executed=False,
                                execution_reason=None
                            )
                            db.add(decision)
                            await db.flush()  # Para obtener el ID
                            deepseek_decision_id = decision.id
                            
                            deepseek_logger.info(
                                f"🤖 DeepSeek Analysis: {deepseek_analysis['recommendation']} "
                                f"(Confidence: {deepseek_analysis['confidence']:.2%}, "
                                f"Risk: {deepseek_analysis['risk_assessment']})"
                            )
                            
                            # Decidir si ejecutar basado en DeepSeek (modo conservador)
                            if (deepseek_analysis["confidence"] >= 0.7 and 
                                deepseek_analysis["risk_assessment"] != "HIGH" and
                                deepseek_analysis["recommendation"] in ["BUY", "SELL", "STRONG_BUY", "STRONG_SELL"]):
                                
                                # Verificar que la recomendación coincida con la señal técnica
                                if (deepseek_analysis["recommendation"] in ["BUY", "STRONG_BUY"] and technical_signal == "BUY") or \
                                   (deepseek_analysis["recommendation"] in ["SELL", "STRONG_SELL"] and technical_signal == "SELL"):
                                    
                                    final_signal = technical_signal
                                    execution_reason = f"DeepSeek approved (Confidence: {deepseek_analysis['confidence']:.2%}, Risk: {deepseek_analysis['risk_assessment']})"
                                    decision.was_executed = True
                                    decision.execution_reason = execution_reason
                                    
                                    deepseek_logger.info(f"✅ DeepSeek APPROVED trade: {technical_signal} {symbol}")
                                else:
                                    final_signal = None
                                    execution_reason = f"DeepSeek recommendation ({deepseek_analysis['recommendation']}) doesn't match technical signal ({technical_signal})"
                                    decision.execution_reason = execution_reason
                                    deepseek_logger.info(f"❌ DeepSeek REJECTED: {execution_reason}")
                            else:
                                final_signal = None
                                execution_reason = f"DeepSeek rejected: Low confidence ({deepseek_analysis['confidence']:.2%}) or High risk ({deepseek_analysis['risk_assessment']})"
                                decision.execution_reason = execution_reason
                                deepseek_logger.info(f"❌ DeepSeek REJECTED: {execution_reason}")
                            
                            await db.commit()
                            
                        except Exception as e:
                            deepseek_logger.error(f"❌ Error consulting DeepSeek: {e}")
                            # Si falla DeepSeek, usar señal técnica
                            final_signal = technical_signal
                            execution_reason = f"DeepSeek error, using technical signal: {str(e)}"
                    
                    # Ejecutar trade si hay señal final
                    if final_signal:
                        trade_logger.info(f"🔔 EXECUTING: {final_signal} {symbol} | Reason: {execution_reason}")
                        
                        # Ejecutar trade
                        trade = await self._execute_trade(db, strategy, symbol, final_signal, current_price)
                        
                        # Si se ejecutó y hay decisión de DeepSeek, actualizar trade_id
                        if trade and deepseek_decision_id:
                            try:
                                result = await db.execute(
                                    select(DeepSeekDecision).where(DeepSeekDecision.id == deepseek_decision_id)
                                )
                                decision = result.scalar_one_or_none()
                                if decision:
                                    decision.trade_id = trade.id
                                    await db.commit()
                            except Exception as e:
                                deepseek_logger.error(f"Error updating DeepSeek decision with trade_id: {e}")
                        
                        self.last_trade_time[cooldown_key] = datetime.utcnow()
                    else:
                        trade_logger.info(f"⏸️  TRADE SKIPPED: {symbol} | Reason: {execution_reason}")
    
    async def _check_daily_loss_limit(self, db: AsyncSession, user: User) -> bool:
        """Comprueba si el usuario ha superado el límite de pérdida diaria.

        Returns True si se debe bloquear el trading (límite alcanzado).
        Reinicia automáticamente el contador si ya pasó el día.
        """
        now = datetime.utcnow()

        # Reiniciar pausa si ya pasaron 24h desde que se activó
        if user.daily_loss_paused and user.daily_loss_reset_at:
            if now >= user.daily_loss_reset_at:
                user.daily_loss_paused = False
                user.daily_loss_reset_at = None
                await db.commit()
                trade_logger.info(f"🔄 Daily loss limit reset for user {user.username}")

        if user.daily_loss_paused:
            trade_logger.warning(
                f"⏸️  Trading paused for user {user.username} — daily loss limit reached"
            )
            return True

        # Calcular pérdidas del día (solo trades cerrados hoy con P&L negativo)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.sum(TradeModel.profit_loss)).where(
                TradeModel.user_id == user.id,
                TradeModel.status == TradeStatus.CLOSED,
                TradeModel.closed_at >= today_start,
                TradeModel.profit_loss < 0,
            )
        )
        daily_loss = abs(result.scalar() or 0.0)

        max_allowed_loss = user.initial_balance * (user.max_daily_loss_percent / 100)

        if daily_loss >= max_allowed_loss:
            user.daily_loss_paused = True
            user.daily_loss_reset_at = today_start + timedelta(days=1)
            await db.commit()

            trade_logger.critical(
                f"🚨 DAILY LOSS LIMIT REACHED for {user.username}: "
                f"${daily_loss:.2f} >= ${max_allowed_loss:.2f} "
                f"({user.max_daily_loss_percent}% of ${user.initial_balance:.2f}). "
                f"Trading paused until {user.daily_loss_reset_at}"
            )

            # Notificar por Telegram si está configurado
            if user.telegram_enabled and user.telegram_bot_token and user.telegram_chat_id:
                try:
                    tg = TelegramService(
                        bot_token=user.telegram_bot_token,
                        chat_id=user.telegram_chat_id
                    )
                    await tg.send_message(
                        f"🚨 *LÍMITE DE PÉRDIDA DIARIA ALCANZADO*\n\n"
                        f"Pérdida del día: *${daily_loss:.2f}*\n"
                        f"Límite configurado: *${max_allowed_loss:.2f}* ({user.max_daily_loss_percent}%)\n\n"
                        f"El bot ha pausado el trading automáticamente hasta mañana."
                    )
                    await tg.close()
                except Exception as e:
                    telegram_logger.error(f"Failed to send daily loss alert: {e}")

            return True

        return False

    def _get_signal(self, strategy: Strategy, rsi: dict, macd: dict,
                    bollinger: dict, price: float) -> Optional[str]:
        """Determina señal de trading según la estrategia"""
        
        if strategy.strategy_type == StrategyType.RSI:
            if rsi["oversold"]:
                return "BUY"
            elif rsi["overbought"]:
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.MACD:
            if macd["trend"] == "strong_bullish" and macd["histogram"] > 0:
                return "BUY"
            elif macd["trend"] == "strong_bearish" and macd["histogram"] < 0:
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.BOLLINGER:
            if bollinger["position"] == "below_lower":
                return "BUY"
            elif bollinger["position"] == "above_upper":
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.COMBINED:
            buy_signals = 0
            sell_signals = 0
            
            if rsi["oversold"]:
                buy_signals += 1
            elif rsi["overbought"]:
                sell_signals += 1
            
            if macd["histogram"] > 0:
                buy_signals += 1
            elif macd["histogram"] < 0:
                sell_signals += 1
            
            if bollinger["position"] == "below_lower":
                buy_signals += 1
            elif bollinger["position"] == "above_upper":
                sell_signals += 1
            
            if buy_signals >= 2:
                return "BUY"
            elif sell_signals >= 2:
                return "SELL"
        
        elif strategy.strategy_type == StrategyType.SCALPING:
            # Estrategia AGRESIVA para testing
            # Compra si RSI < 45 Y MACD positivo
            # Vende si RSI > 55 Y MACD negativo
            # Mucho más sensible que las otras estrategias
            
            if rsi["value"] < 45 and macd["histogram"] > 0:
                trade_logger.info(f"🎯 SCALPING BUY: RSI={rsi['value']:.1f}, MACD={macd['histogram']:.6f}")
                return "BUY"
            elif rsi["value"] > 55 and macd["histogram"] < 0:
                trade_logger.info(f"🎯 SCALPING SELL: RSI={rsi['value']:.1f}, MACD={macd['histogram']:.6f}")
                return "SELL"
            
            # Alternativa: Si el precio está en el tercio inferior de Bollinger, compra
            if bollinger["position"] == "lower_half" and rsi["value"] < 50:
                trade_logger.info(f"🎯 SCALPING BUY (BB): position={bollinger['position']}, RSI={rsi['value']:.1f}")
                return "BUY"
            elif bollinger["position"] == "upper_half" and rsi["value"] > 50:
                trade_logger.info(f"🎯 SCALPING SELL (BB): position={bollinger['position']}, RSI={rsi['value']:.1f}")
                return "SELL"
        
        return None
    
    async def _execute_trade(self, db: AsyncSession, strategy: Strategy, 
                            symbol: str, signal: str, price: float) -> Optional[Trade]:
        """Ejecuta un trade"""
        try:
            # Obtener usuario
            result = await db.execute(
                select(User).where(User.id == strategy.user_id)
            )
            user = result.scalar_one_or_none()
            if not user:
                return None
            
            # Calcular cantidad y validar reglas Binance (LOT_SIZE, MIN_NOTIONAL)
            raw_quantity = strategy.max_trade_amount / price
            try:
                quantity = await self.binance.validate_and_round_quantity(
                    symbol, raw_quantity, price
                )
            except ValueError as e:
                trade_logger.warning(f"⚠️ Skipping trade — Binance filter violation: {e}")
                self.stats["trades_skipped"] += 1
                return None
            trade_value = price * quantity
            
            # Obtener las API keys correctas según el modo
            if user.paper_trading:
                api_key = user.binance_testnet_api_key
                secret_key = user.binance_testnet_secret_key
            else:
                api_key = user.binance_real_api_key
                secret_key = user.binance_real_secret_key
            
            # Verificar balance (solo para paper trading simulado)
            if user.paper_trading and signal == "BUY" and not (api_key and secret_key):
                # Solo verificar balance si no tiene API keys (simulación pura)
                if trade_value > user.current_balance:
                    trade_logger.warning(f"Insufficient balance for {symbol}")
                    self.stats["trades_skipped"] += 1
                    return None
            
            # Calcular SL y TP
            if signal == "BUY":
                stop_loss = price * (1 - strategy.stop_loss_percent / 100)
                take_profit = price * (1 + strategy.take_profit_percent / 100)
                trade_type = TradeType.BUY
            else:
                stop_loss = price * (1 + strategy.stop_loss_percent / 100)
                take_profit = price * (1 - strategy.take_profit_percent / 100)
                trade_type = TradeType.SELL
            
            # Ejecutar orden en Binance si tiene API keys configuradas
            binance_order_id = None
            actual_executed_price = price
            actual_executed_quantity = quantity
            
            if api_key and secret_key:
                try:
                    # Crear servicio Binance con las credenciales del usuario
                    # Paper Trading usa Testnet, Real Trading usa Binance Real
                    binance_service = BinanceService(
                        api_key=api_key,
                        secret_key=secret_key,
                        use_testnet=user.paper_trading  # True = Testnet, False = Real
                    )
                    
                    trade_logger.info(f"📡 Executing order on Binance {'Testnet' if user.paper_trading else 'Real'}: {signal} {symbol}")
                    
                    # Ejecutar orden MARKET (más rápido y seguro para bots)
                    order_response = await binance_service.place_order(
                        symbol=symbol,
                        side=signal,
                        order_type="MARKET",
                        quote_order_qty=trade_value  # Cantidad en USDT
                    )
                    
                    binance_order_id = order_response.get("orderId")
                    actual_executed_price = float(order_response.get("price", price))
                    actual_executed_quantity = float(order_response.get("executedQty", quantity))
                    
                    trade_logger.info(f"✅ Binance order executed: OrderID={binance_order_id}, Price=${actual_executed_price:.2f}, Qty={actual_executed_quantity:.6f}")
                    
                    await binance_service.close()
                    
                except Exception as e:
                    trade_logger.error(f"❌ Failed to execute Binance order: {e}")
                    # Si falla la orden, no crear el trade
                    self.stats["trades_skipped"] += 1
                    return None
            
            # Crear trade
            trade = Trade(
                user_id=user.id,
                symbol=symbol,
                trade_type=trade_type,
                status=TradeStatus.OPEN,
                entry_price=actual_executed_price,  # Usar precio real de ejecución
                quantity=actual_executed_quantity,  # Usar cantidad real ejecutada
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_name=strategy.name,
                strategy_signals=json.dumps({
                    "signal": signal,
                    "price": price,
                    "timestamp": datetime.utcnow().isoformat()
                }),
                opened_at=datetime.utcnow(),
                is_paper_trade=1 if user.paper_trading else 0,
                binance_order_id=str(binance_order_id) if binance_order_id else None
            )
            
            # Actualizar balance solo si es paper trading simulado (sin API keys)
            if user.paper_trading and signal == "BUY" and not (api_key and secret_key):
                user.current_balance -= trade_value
            # Si tiene API keys, el balance se actualiza desde Binance
            
            # Actualizar estadísticas de estrategia
            strategy.total_trades += 1
            strategy.last_trade_at = datetime.utcnow()
            
            db.add(trade)
            await db.commit()
            await db.refresh(trade)
            
            self.stats["trades_executed"] += 1

            trade_logger.info("=" * 50)
            trade_logger.info(f"✅ TRADE EXECUTED")
            trade_logger.info(f"   Symbol: {symbol}")
            trade_logger.info(f"   Type: {signal}")
            trade_logger.info(f"   Price: ${actual_executed_price:,.2f}")
            trade_logger.info(f"   Quantity: {actual_executed_quantity:.6f}")
            trade_logger.info(f"   Value: ${trade_value:,.2f}")
            trade_logger.info(f"   Stop Loss: ${stop_loss:,.2f}")
            trade_logger.info(f"   Take Profit: ${take_profit:,.2f}")
            trade_logger.info(f"   Strategy: {strategy.name}")
            trade_logger.info(f"   Mode: {'Paper Trading (Testnet)' if user.paper_trading else 'Real Trading'}")
            if binance_order_id:
                trade_logger.info(f"   Binance Order ID: {binance_order_id}")
            trade_logger.info("=" * 50)

            # Notificar al cliente
            await client_ws_manager.send_trade_update(str(user.id), {
                "id": trade.id,
                "symbol": symbol,
                "type": signal,
                "price": actual_executed_price,
                "quantity": actual_executed_quantity,
                "status": "OPEN"
            })

            # Enviar notificaciones
            await self._send_trade_notifications(
                user=user,
                trade_type=signal.lower(),
                symbol=symbol,
                price=actual_executed_price,
                quantity=actual_executed_quantity,
                trade_id=trade.id
            )

            # Agregar a cola de resumen por email
            if user.summary_email:
                if user.id not in self.email_summary_queue:
                    self.email_summary_queue[user.id] = []
                self.email_summary_queue[user.id].append({
                    "symbol": symbol,
                    "type": signal,
                    "entry_price": actual_executed_price,
                    "exit_price": None,
                    "profit_loss": None,
                    "status": "OPEN",
                    "opened_at": datetime.utcnow(),
                    "closed_at": None
                })

            return trade
            
        except Exception as e:
            self.stats["errors"] += 1
            trade_logger.error(f"❌ Trade execution failed: {e}")
    
    async def _check_price_triggers(self, symbol: str, price: float):
        """Verifica SL/TP para trades abiertos en tiempo real.

        Usa SELECT FOR UPDATE para evitar la race condition donde dos callbacks
        concurrentes cierran el mismo trade dos veces.
        """
        async with self.db_session_factory() as db:
            result = await db.execute(
                select(Trade)
                .where(Trade.symbol == symbol, Trade.status == TradeStatus.OPEN)
                .with_for_update(skip_locked=True)  # skip_locked: otro callback ya lo está cerrando
            )
            trades = result.scalars().all()

            for trade in trades:
                should_close = False
                reason = ""

                if trade.trade_type == TradeType.BUY:
                    if trade.stop_loss and price <= trade.stop_loss:
                        should_close = True
                        reason = "STOP_LOSS"
                    elif trade.take_profit and price >= trade.take_profit:
                        should_close = True
                        reason = "TAKE_PROFIT"
                else:
                    if trade.stop_loss and price >= trade.stop_loss:
                        should_close = True
                        reason = "STOP_LOSS"
                    elif trade.take_profit and price <= trade.take_profit:
                        should_close = True
                        reason = "TAKE_PROFIT"

                if should_close:
                    await self._close_trade(db, trade, price, reason)
    
    async def _close_trade(self, db: AsyncSession, trade: Trade, 
                          exit_price: float, reason: str):
        """Cierra un trade"""
        # Obtener usuario
        result = await db.execute(
            select(User).where(User.id == trade.user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            return
        
        # Obtener las API keys correctas según el modo
        if user.paper_trading:
            api_key = user.binance_testnet_api_key
            secret_key = user.binance_testnet_secret_key
        else:
            api_key = user.binance_real_api_key
            secret_key = user.binance_real_secret_key
        
        # Ejecutar orden de cierre en Binance si tiene API keys
        binance_close_order_id = None
        actual_exit_price = exit_price
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
                    use_testnet=user.paper_trading
                )
                
                trade_logger.info(f"📡 Closing order on Binance {'Testnet' if user.paper_trading else 'Real'}: {close_side} {trade.symbol}")
                
                # Ejecutar orden MARKET para cerrar
                close_order_response = await binance_service.place_order(
                    symbol=trade.symbol,
                    side=close_side,
                    order_type="MARKET",
                    quantity=trade.quantity
                )
                
                binance_close_order_id = close_order_response.get("orderId")
                actual_exit_price = float(close_order_response.get("price", exit_price))
                actual_exit_quantity = float(close_order_response.get("executedQty", trade.quantity))
                
                trade_logger.info(f"✅ Binance close order executed: OrderID={binance_close_order_id}, Price=${actual_exit_price:.2f}")
                
                await binance_service.close()
                
            except Exception as e:
                trade_logger.error(f"❌ Failed to execute Binance close order: {e}")
                # Continuar con el cierre aunque falle la orden (para no perder el trade)
        
        # Calcular P&L neto (descontando comisiones de apertura y cierre)
        fee_rate = settings.TRADING_FEE_RATE
        entry_fee = trade.entry_price * actual_exit_quantity * fee_rate
        exit_fee = actual_exit_price * actual_exit_quantity * fee_rate
        total_fees = entry_fee + exit_fee

        if trade.trade_type == TradeType.BUY:
            gross_profit = (actual_exit_price - trade.entry_price) * actual_exit_quantity
        else:
            gross_profit = (trade.entry_price - actual_exit_price) * actual_exit_quantity

        profit_loss = gross_profit - total_fees
        profit_loss_percent = (profit_loss / (trade.entry_price * trade.quantity)) * 100
        
        # Actualizar trade
        trade.exit_price = actual_exit_price
        trade.profit_loss = profit_loss
        trade.profit_loss_percent = profit_loss_percent
        trade.status = TradeStatus.CLOSED
        trade.closed_at = datetime.utcnow()
        
        # Actualizar signals con order ID de cierre
        signals = json.loads(trade.strategy_signals) if trade.strategy_signals else {}
        signals["close_binance_order_id"] = binance_close_order_id
        trade.strategy_signals = json.dumps(signals)
        
        # Actualizar balance solo si es paper trading simulado (sin API keys)
        if trade.is_paper_trade and not (api_key and secret_key):
            if trade.trade_type == TradeType.BUY:
                user.current_balance += actual_exit_price * actual_exit_quantity
            else:
                user.current_balance += profit_loss
        # Si tiene API keys, el balance se actualiza desde Binance
        
        # Actualizar estrategia
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
        
        # Log
        emoji = "✅" if profit_loss > 0 else "❌"
        trade_logger.info("=" * 50)
        trade_logger.info(f"{emoji} TRADE CLOSED - {reason}")
        trade_logger.info(f"   Symbol: {trade.symbol}")
        trade_logger.info(f"   Entry: ${trade.entry_price:,.2f}")
        trade_logger.info(f"   Exit: ${exit_price:,.2f}")
        trade_logger.info(f"   P&L: ${profit_loss:,.2f} ({profit_loss_percent:+.2f}%)")
        trade_logger.info("=" * 50)
        
        # Obtener usuario para notificaciones
        result = await db.execute(
            select(User).where(User.id == trade.user_id)
        )
        user = result.scalar_one_or_none()
        
        # Notificar
        await client_ws_manager.send_trade_update(str(trade.user_id), {
            "id": trade.id,
            "symbol": trade.symbol,
            "status": "CLOSED",
            "reason": reason,
            "profit_loss": profit_loss,
            "profit_loss_percent": profit_loss_percent
        })
        
        # Enviar notificaciones
        if user:
            await self._send_trade_notifications(
                user=user,
                trade_type=trade.trade_type.value.lower(),
                symbol=trade.symbol,
                price=exit_price,
                quantity=trade.quantity,
                trade_id=trade.id,
                profit_loss=profit_loss,
                reason=reason
            )
            
            # Actualizar cola de resumen por email
            if user.summary_email:
                if user.id not in self.email_summary_queue:
                    self.email_summary_queue[user.id] = []
                # Buscar trade abierto en la cola y actualizarlo
                for trade_summary in self.email_summary_queue[user.id]:
                    if (trade_summary.get("symbol") == trade.symbol and 
                        trade_summary.get("status") == "OPEN" and
                        abs(trade_summary.get("entry_price", 0) - trade.entry_price) < 0.01):
                        trade_summary["exit_price"] = exit_price
                        trade_summary["profit_loss"] = profit_loss
                        trade_summary["status"] = "CLOSED"
                        trade_summary["closed_at"] = datetime.utcnow()
                        break
                
                # Verificar si debemos enviar resumen (cada 24 horas o cada 10 trades)
                await self._check_and_send_email_summary(user)
    
    async def _send_trade_notifications(
        self,
        user: User,
        trade_type: str,
        symbol: str,
        price: float,
        quantity: float,
        trade_id: int,
        profit_loss: Optional[float] = None,
        reason: Optional[str] = None
    ):
        """Envía notificaciones de trade (Telegram siempre, Email solo resúmenes)"""
        try:
            # Telegram: todas las notificaciones
            if user.telegram_enabled and user.telegram_bot_token and user.telegram_chat_id:
                try:
                    telegram_service = TelegramService(
                        bot_token=user.telegram_bot_token,
                        chat_id=user.telegram_chat_id
                    )
                    if profit_loss is not None:
                        telegram_logger.info(f"📱 Telegram notification sent: {trade_type.upper()} {symbol} | P&L: ${profit_loss:.2f}")
                        # Trade cerrado
                        await telegram_service.send_trade_notification(
                            trade_type=trade_type,
                            symbol=symbol,
                            price=price,
                            quantity=quantity,
                            profit_loss=profit_loss
                        )
                    else:
                        telegram_logger.info(f"📱 Telegram notification sent: {trade_type.upper()} {symbol} | Price: ${price:.2f}")
                        # Trade abierto
                        await telegram_service.send_trade_notification(
                            trade_type=trade_type,
                            symbol=symbol,
                            price=price,
                            quantity=quantity
                        )
                except Exception as e:
                    telegram_logger.error(f"❌ Failed to send Telegram notification: {e}")
                    trade_logger.error(f"Failed to send Telegram notification: {e}")
            
            # Email: NO enviamos notificaciones individuales, solo resúmenes
            # Los resúmenes se envían periódicamente o cuando se alcanza un número de trades
            
        except Exception as e:
            trade_logger.error(f"Error sending notifications: {e}")
    
    async def _check_and_send_email_summary(self, user: User):
        """Verifica si debe enviar resumen por email y lo envía si es necesario"""
        try:
            if not user.smtp_enabled or not user.summary_email or not user.smtp_host:
                return
            
            # Verificar condiciones para enviar resumen
            should_send = False
            
            # Condición 1: Han pasado 24 horas desde el último resumen
            if user.id in self.last_summary_sent:
                time_since_last = datetime.utcnow() - self.last_summary_sent[user.id]
                if time_since_last >= timedelta(hours=24):
                    should_send = True
            else:
                # Primera vez, enviar si hay trades
                if user.id in self.email_summary_queue and len(self.email_summary_queue[user.id]) > 0:
                    should_send = True
            
            # Condición 2: Hay 10 o más trades en la cola
            if user.id in self.email_summary_queue:
                if len(self.email_summary_queue[user.id]) >= 10:
                    should_send = True
            
            if not should_send:
                return
            
            # Preparar datos del resumen
            trades = self.email_summary_queue.get(user.id, [])
            if not trades:
                return
            
            # Calcular estadísticas
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.get("profit_loss", 0) > 0)
            losing_trades = sum(1 for t in trades if t.get("profit_loss", 0) < 0)
            total_profit_loss = sum(t.get("profit_loss", 0) or 0 for t in trades)
            
            # Enviar resumen
            try:
                email_service = EmailService(
                    host=user.smtp_host,
                    port=user.smtp_port or 587,
                    user=user.smtp_user,
                    password=user.smtp_password,
                    from_email=user.smtp_from_email or user.email
                )
                
                await email_service.send_trading_summary(
                    to_email=user.summary_email,
                    period="daily",
                    trades=trades,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=losing_trades,
                    total_profit_loss=total_profit_loss,
                    current_balance=user.current_balance
                )
                
                email_logger.info(f"📧 Email summary sent to {user.summary_email} | {total_trades} trades | P&L: ${total_profit_loss:.2f}")
                
                # Limpiar cola y actualizar timestamp
                self.email_summary_queue[user.id] = []
                self.last_summary_sent[user.id] = datetime.utcnow()
                
                trade_logger.info(f"📧 Email summary sent to {user.summary_email}")
                
            except Exception as e:
                email_logger.error(f"❌ Failed to send email summary: {e}")
                trade_logger.error(f"Failed to send email summary: {e}")
                
        except Exception as e:
            trade_logger.error(f"Error checking email summary: {e}")
    
    async def _monitor_open_trades(self):
        """Loop que monitorea trades abiertos periódicamente"""
        while self.running:
            try:
                async with self.db_session_factory() as db:
                    result = await db.execute(
                        select(Trade).where(Trade.status == TradeStatus.OPEN)
                    )
                    trades = result.scalars().all()
                    
                    for trade in trades:
                        price = binance_ws.get_price(trade.symbol)
                        if price:
                            await self._check_price_triggers(trade.symbol, price)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            
            await asyncio.sleep(1)  # Verificar cada segundo
    
    async def _reload_strategies_loop(self):
        """Recarga estrategias periódicamente por si hay cambios"""
        while self.running:
            await asyncio.sleep(60)  # Cada minuto
            try:
                old_symbols = self.active_symbols.copy()
                await self._load_active_symbols()
                
                # Suscribir a nuevos símbolos
                new_symbols = self.active_symbols - old_symbols
                if new_symbols:
                    await binance_ws.subscribe(list(new_symbols))
                    await self._load_historical_data()
                    for symbol in new_symbols:
                        binance_ws.on_price_update(symbol, self._on_price_update)
                        binance_ws.on_kline_close(symbol, self._on_kline_close)
                    trade_logger.info(f"Added {len(new_symbols)} new symbols")
            except Exception as e:
                logger.error(f"Strategy reload error: {e}")


# Instancia global
realtime_bot: Optional[RealtimeTradingBot] = None


async def start_realtime_bot(binance_service: BinanceService):
    """Inicia el bot de trading en tiempo real"""
    global realtime_bot
    realtime_bot = RealtimeTradingBot(binance_service)
    await realtime_bot.start()
    return realtime_bot


async def stop_realtime_bot():
    """Detiene el bot"""
    global realtime_bot
    if realtime_bot:
        await realtime_bot.stop()
        realtime_bot = None

