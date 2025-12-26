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
from sqlalchemy import select, desc, update

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
        # NOTA: last_summary_sent ahora se guarda en user.last_email_summary_sent (base de datos)
        
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
        
        # Iniciar loop de monitoreo de trades abiertos
        asyncio.create_task(self._monitor_open_trades())
        
        # Iniciar loop de recarga de estrategias
        asyncio.create_task(self._reload_strategies_loop())
        
        trade_logger.info("✅ Realtime bot fully initialized")
    
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
            
            # Calcular cantidad
            quantity = strategy.max_trade_amount / price
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
                    # Obtener el precio real de ejecución de los fills
                    fills = order_response.get("fills", [])
                    if fills:
                        # Calcular precio promedio ponderado
                        total_qty = sum(float(f.get("qty", 0)) for f in fills)
                        if total_qty > 0:
                            actual_executed_price = sum(float(f.get("price", 0)) * float(f.get("qty", 0)) for f in fills) / total_qty
                        else:
                            actual_executed_price = float(fills[0].get("price", price))
                    else:
                        actual_executed_price = float(order_response.get("price", price))
                    
                    actual_executed_quantity = float(order_response.get("executedQty", quantity))
                    
                    trade_logger.info(f"✅ Binance order executed: OrderID={binance_order_id}, Price=${actual_executed_price:.2f}, Qty={actual_executed_quantity:.6f}")
                    
                    await binance_service.close()
                    
                except Exception as e:
                    trade_logger.error(f"❌ Failed to execute Binance order: {e}")
                    # Si falla la orden, no crear el trade
                    self.stats["trades_skipped"] += 1
                    return None
            
            # Validar que el precio de entrada sea válido
            if actual_executed_price <= 0:
                trade_logger.error(
                    f"❌ Invalid entry price ({actual_executed_price}) for {symbol}. Trade not created."
                )
                self.stats["errors"] += 1
                return None
            
            # Calcular SL y TP con el precio REAL de ejecución (no el estimado)
            if signal == "BUY":
                stop_loss = actual_executed_price * (1 - strategy.stop_loss_percent / 100)
                take_profit = actual_executed_price * (1 + strategy.take_profit_percent / 100)
                trade_type = TradeType.BUY
            else:
                stop_loss = actual_executed_price * (1 + strategy.stop_loss_percent / 100)
                take_profit = actual_executed_price * (1 - strategy.take_profit_percent / 100)
                trade_type = TradeType.SELL
            
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
            
            # Enviar notificaciones (ANTES del return para asegurar que se ejecute)
            trade_logger.info(f"📱 Preparing to send Telegram notification for trade {trade.id}")
            try:
                await self._send_trade_notifications(
                    user=user,
                    trade_type=signal.lower(),
                    symbol=symbol,
                    price=actual_executed_price,
                    quantity=actual_executed_quantity,
                    trade_id=trade.id
                )
                trade_logger.info(f"✅ Telegram notification process completed for trade {trade.id}")
            except Exception as notif_error:
                trade_logger.error(
                    f"❌ Error sending notifications for trade {trade.id}: {notif_error}",
                    exc_info=True
                )
                # No fallar el trade por un error de notificación
            
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
            
            return trade  # Retornar el trade creado
            
        except Exception as e:
            self.stats["errors"] += 1
            trade_logger.error(f"❌ Trade execution failed: {e}", exc_info=True)
            # Asegurar que las notificaciones se envíen incluso si hay un error parcial
            # (solo si el trade se creó pero falló algo después)
    
    async def _check_price_triggers(self, symbol: str, price: float):
        """Verifica SL/TP para trades abiertos en tiempo real"""
        async with self.db_session_factory() as db:
            result = await db.execute(
                select(Trade).where(
                    Trade.symbol == symbol,
                    Trade.status == TradeStatus.OPEN
                )
            )
            trades = result.scalars().all()
            
            for trade in trades:
                # Si no hay entry_price válido, no podemos verificar stop loss correctamente
                if not trade.entry_price or trade.entry_price <= 0:
                    trade_logger.warning(
                        f"⚠️ Trade {trade.id} ({trade.symbol}) has invalid entry_price ({trade.entry_price}). "
                        f"Cannot verify stop loss/take profit. Current price: ${price:.2f}"
                    )
                    continue
                
                should_close = False
                reason = ""
                
                if trade.trade_type == TradeType.BUY:
                    # Para BUY: cierra si precio cae por debajo del stop loss o sube por encima del take profit
                    if trade.stop_loss and price <= trade.stop_loss:
                        should_close = True
                        reason = "STOP_LOSS"
                        trade_logger.info(
                            f"🛑 STOP LOSS TRIGGERED | Trade {trade.id} | {trade.symbol} | "
                            f"Price: ${price:.2f} <= Stop Loss: ${trade.stop_loss:.2f} | "
                            f"Entry: ${trade.entry_price:.2f} | Loss: {((price - trade.entry_price) / trade.entry_price * 100):.2f}%"
                        )
                    elif trade.take_profit and price >= trade.take_profit:
                        should_close = True
                        reason = "TAKE_PROFIT"
                        trade_logger.info(
                            f"🎯 TAKE PROFIT TRIGGERED | Trade {trade.id} | {trade.symbol} | "
                            f"Price: ${price:.2f} >= Take Profit: ${trade.take_profit:.2f} | "
                            f"Entry: ${trade.entry_price:.2f} | Gain: {((price - trade.entry_price) / trade.entry_price * 100):.2f}%"
                        )
                else:  # SELL
                    # Para SELL: cierra si precio sube por encima del stop loss o cae por debajo del take profit
                    if trade.stop_loss and price >= trade.stop_loss:
                        should_close = True
                        reason = "STOP_LOSS"
                        trade_logger.info(
                            f"🛑 STOP LOSS TRIGGERED | Trade {trade.id} | {trade.symbol} | "
                            f"Price: ${price:.2f} >= Stop Loss: ${trade.stop_loss:.2f} | "
                            f"Entry: ${trade.entry_price:.2f} | Loss: {((trade.entry_price - price) / trade.entry_price * 100):.2f}%"
                        )
                    elif trade.take_profit and price <= trade.take_profit:
                        should_close = True
                        reason = "TAKE_PROFIT"
                        trade_logger.info(
                            f"🎯 TAKE PROFIT TRIGGERED | Trade {trade.id} | {trade.symbol} | "
                            f"Price: ${price:.2f} <= Take Profit: ${trade.take_profit:.2f} | "
                            f"Entry: ${trade.entry_price:.2f} | Gain: {((trade.entry_price - price) / trade.entry_price * 100):.2f}%"
                        )
                
                if should_close:
                    await self._close_trade(db, trade, price, reason)
                else:
                    # Log periódico para debug (cada 10 verificaciones aproximadamente)
                    if trade.id % 10 == 0:
                        trade_logger.debug(
                            f"📊 Price check | Trade {trade.id} | {trade.symbol} | "
                            f"Price: ${price:.2f} | Entry: ${trade.entry_price:.2f} | "
                            f"SL: ${trade.stop_loss:.2f if trade.stop_loss else 'N/A'} | "
                            f"TP: ${trade.take_profit:.2f if trade.take_profit else 'N/A'}"
                        )
    
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
                
                # Verificar balance antes de intentar cerrar
                if close_side == "BUY":
                    # Para cerrar un SELL, necesitamos comprar, verificar balance
                    try:
                        await binance_service.initialize()
                        balances = await binance_service.get_account_balance()
                        await binance_service.close()
                        
                        # Obtener el símbolo base (ej: BNBUSDT -> USDT)
                        quote_asset = trade.symbol[-4:]  # Asume que termina en USDT
                        required_balance = exit_price * trade.quantity
                        available_balance = balances.get(quote_asset, {}).get("free", 0)
                        
                        if available_balance < required_balance:
                            trade_logger.warning(
                                f"⚠️ Insufficient balance to close SELL trade {trade.id} ({trade.symbol}): "
                                f"Required ${required_balance:.2f}, Available ${available_balance:.2f}. "
                                f"Closing trade manually with current market price."
                            )
                            # Usar el precio de salida proporcionado (precio actual del mercado)
                            actual_exit_price = exit_price
                            actual_exit_quantity = trade.quantity
                            binance_close_order_id = None
                        else:
                            # Hay balance suficiente, intentar cerrar
                            await binance_service.initialize()
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
                    except Exception as balance_error:
                        trade_logger.warning(
                            f"⚠️ Could not verify balance for trade {trade.id}: {balance_error}. "
                            f"Closing trade manually with current market price."
                        )
                        actual_exit_price = exit_price
                        actual_exit_quantity = trade.quantity
                        binance_close_order_id = None
                else:
                    # Para cerrar un BUY, vendemos (no necesitamos verificar balance de USDT)
                    await binance_service.initialize()
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
                error_msg = str(e)
                # Si es error de balance insuficiente, cerrar manualmente
                if "insufficient balance" in error_msg.lower() or "-2010" in error_msg:
                    trade_logger.warning(
                        f"⚠️ Insufficient balance to close trade {trade.id} ({trade.symbol}). "
                        f"Closing trade manually with current market price: ${exit_price:.2f}"
                    )
                    actual_exit_price = exit_price
                    actual_exit_quantity = trade.quantity
                    binance_close_order_id = None
                else:
                    trade_logger.error(f"❌ Failed to execute Binance close order: {e}")
                    # Continuar con el cierre aunque falle la orden (para no perder el trade)
                    actual_exit_price = exit_price
                    actual_exit_quantity = trade.quantity
                    binance_close_order_id = None
        
        # Calcular P&L
        if trade.trade_type == TradeType.BUY:
            profit_loss = (actual_exit_price - trade.entry_price) * actual_exit_quantity
        else:
            profit_loss = (trade.entry_price - actual_exit_price) * actual_exit_quantity
        
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
            # Verificar configuración de Telegram
            telegram_configured = (
                user.telegram_enabled and 
                user.telegram_bot_token and 
                user.telegram_chat_id
            )
            
            if not telegram_configured:
                # Log detallado de qué falta
                missing = []
                if not user.telegram_enabled:
                    missing.append("telegram_enabled=False")
                if not user.telegram_bot_token:
                    missing.append("bot_token missing")
                if not user.telegram_chat_id:
                    missing.append("chat_id missing")
                
                telegram_logger.warning(
                    f"⚠️ Telegram notification SKIPPED for trade {trade_id} ({symbol}): "
                    f"Missing configuration: {', '.join(missing)}"
                )
                return
            
            # Telegram: todas las notificaciones
            try:
                telegram_service = TelegramService(
                    bot_token=user.telegram_bot_token,
                    chat_id=user.telegram_chat_id
                )
                
                if profit_loss is not None:
                    # Trade cerrado
                    telegram_logger.info(
                        f"📱 Sending Telegram notification: CLOSE {symbol} | "
                        f"P&L: ${profit_loss:.2f} | Trade ID: {trade_id}"
                    )
                    await telegram_service.send_trade_notification(
                        trade_type="close",  # Usar "close" para trades cerrados
                        symbol=symbol,
                        price=price,
                        quantity=quantity,
                        profit_loss=profit_loss
                    )
                    telegram_logger.info(f"✅ Telegram notification sent successfully for trade {trade_id}")
                else:
                    # Trade abierto
                    telegram_logger.info(
                        f"📱 Sending Telegram notification: OPEN {trade_type.upper()} {symbol} | "
                        f"Price: ${price:.2f} | Trade ID: {trade_id}"
                    )
                    await telegram_service.send_trade_notification(
                        trade_type=trade_type,  # "buy" o "sell"
                        symbol=symbol,
                        price=price,
                        quantity=quantity
                    )
                    telegram_logger.info(f"✅ Telegram notification sent successfully for trade {trade_id}")
                    
            except Exception as e:
                telegram_logger.error(
                    f"❌ Failed to send Telegram notification for trade {trade_id} ({symbol}): {e}",
                    exc_info=True
                )
                trade_logger.error(f"Failed to send Telegram notification: {e}")
            
            # Email: NO enviamos notificaciones individuales, solo resúmenes
            # Los resúmenes se envían periódicamente o cuando se alcanza un número de trades
            
        except Exception as e:
            trade_logger.error(f"Error sending notifications: {e}", exc_info=True)
    
    async def _check_and_send_email_summary(self, user: User):
        """Verifica si debe enviar resumen por email y lo envía si es necesario.
        SOLO envía un email cada 24 horas para evitar spam."""
        try:
            if not user.smtp_enabled or not user.summary_email or not user.smtp_host:
                return
            
            # Verificar si han pasado 24 horas desde el último resumen
            should_send = False
            reason = ""
            
            # Usar el campo de la base de datos en lugar del diccionario en memoria
            if user.last_email_summary_sent:
                time_since_last = datetime.utcnow() - user.last_email_summary_sent
                if time_since_last >= timedelta(hours=24):
                    should_send = True
                    reason = f"24 hours elapsed (last sent: {user.last_email_summary_sent})"
                else:
                    # No enviar - aún no han pasado 24 horas
                    hours_remaining = 24 - (time_since_last.total_seconds() / 3600)
                    email_logger.debug(
                        f"⏳ Email summary skipped for {user.summary_email} | "
                        f"Last sent: {user.last_email_summary_sent} | "
                        f"Hours remaining: {hours_remaining:.1f}"
                    )
                    return
            else:
                # Primera vez, enviar si hay al menos 1 trade cerrado
                if user.id in self.email_summary_queue:
                    closed_trades = [t for t in self.email_summary_queue[user.id] if t.get("status") == "CLOSED"]
                    if len(closed_trades) > 0:
                        should_send = True
                        reason = "first time with closed trades"
                    else:
                        # No hay trades cerrados aún, no enviar
                        return
                else:
                    # No hay cola, no enviar
                    return
            
            if not should_send:
                return
            
            # Preparar datos del resumen - solo incluir trades CERRADOS
            all_trades = self.email_summary_queue.get(user.id, [])
            if not all_trades:
                return
            
            # Filtrar solo trades cerrados para el resumen
            closed_trades = [t for t in all_trades if t.get("status") == "CLOSED"]
            if not closed_trades:
                # Si no hay trades cerrados, no enviar resumen
                return
            
            trades = closed_trades
            
            # Calcular estadísticas solo de trades cerrados
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t.get("profit_loss", 0) > 0)
            losing_trades = sum(1 for t in trades if t.get("profit_loss", 0) < 0)
            total_profit_loss = sum(t.get("profit_loss", 0) or 0 for t in trades)
            
            email_logger.info(
                f"📧 Preparing to send email summary to {user.summary_email} | "
                f"Reason: {reason} | Closed trades: {total_trades} | Open trades in queue: {len(all_trades) - total_trades}"
            )
            
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
                
                email_logger.info(
                    f"📧 Email summary sent to {user.summary_email} | "
                    f"Closed trades: {total_trades} | P&L: ${total_profit_loss:.2f}"
                )
                
                # ACTUALIZAR timestamp en la base de datos PRIMERO para evitar envíos duplicados
                # Usar UPDATE directo para evitar conflictos de sesión
                async with self.db_session_factory() as db:
                    await db.execute(
                        update(User)
                        .where(User.id == user.id)
                        .values(last_email_summary_sent=datetime.utcnow())
                    )
                    await db.commit()
                    # Actualizar el objeto user en memoria
                    user.last_email_summary_sent = datetime.utcnow()
                
                # Limpiar solo trades CERRADOS de la cola, mantener los abiertos
                open_trades = [t for t in all_trades if t.get("status") == "OPEN"]
                self.email_summary_queue[user.id] = open_trades
                
                email_logger.info(
                    f"✅ Email summary sent | Remaining open trades in queue: {len(open_trades)}"
                )
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

