"""
WebSocket Manager para conexiones en tiempo real con Binance
"""
import asyncio
import json
from typing import Dict, Set, Callable, Optional
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosed

from app.core.logging_config import logger, trade_logger
from app.core.config import settings


class BinanceWebSocket:
    """Gestiona conexión WebSocket con Binance para datos en tiempo real"""
    
    def __init__(self):
        self.testnet = settings.BINANCE_TESTNET
        
        # Nota: Binance testnet NO tiene WebSocket de market data público
        # Usamos el WebSocket de producción para datos de mercado (son los mismos datos)
        # El testnet solo es para órdenes/trading
        self.ws_base_url = "wss://stream.binance.com:9443/ws"
        self.stream_url = "wss://stream.binance.com:9443/stream"
        
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.running = False
        self.subscribed_symbols: Set[str] = set()
        self.price_callbacks: Dict[str, Set[Callable]] = {}
        self.kline_callbacks: Dict[str, Set[Callable]] = {}
        self.latest_prices: Dict[str, float] = {}
        self.latest_klines: Dict[str, dict] = {}
        self._reconnect_delay = 5
        self._task: Optional[asyncio.Task] = None
    
    async def start(self, symbols: list[str] = None):
        """Inicia la conexión WebSocket"""
        if self.running:
            logger.warning("WebSocket already running")
            return
        
        self.running = True
        
        # Símbolos por defecto para monitorear
        if symbols is None:
            symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
        
        self.subscribed_symbols = set(symbols)
        self._task = asyncio.create_task(self._run())
        logger.info(f"🔌 WebSocket started for {len(symbols)} symbols")
    
    async def stop(self):
        """Detiene la conexión WebSocket"""
        self.running = False
        if self.websocket:
            await self.websocket.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🔌 WebSocket stopped")
    
    async def _run(self):
        """Loop principal de conexión"""
        while self.running:
            try:
                await self._connect_and_listen()
            except ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self.running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
    
    async def _connect_and_listen(self):
        """Conecta y escucha mensajes"""
        # Construir streams para múltiples símbolos
        streams = []
        for symbol in self.subscribed_symbols:
            symbol_lower = symbol.lower()
            streams.append(f"{symbol_lower}@ticker")      # Precio en tiempo real
            streams.append(f"{symbol_lower}@kline_1m")    # Velas de 1 minuto
        
        stream_path = "/".join(streams)
        url = f"{self.stream_url}?streams={stream_path}"
        
        logger.info(f"Connecting to Binance WebSocket...")
        
        async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
            self.websocket = ws
            logger.info(f"✅ WebSocket connected to Binance")
            
            async for message in ws:
                if not self.running:
                    break
                await self._handle_message(message)
    
    async def _handle_message(self, message: str):
        """Procesa mensajes recibidos"""
        try:
            data = json.loads(message)
            
            if "stream" not in data:
                return
            
            stream = data["stream"]
            payload = data["data"]
            
            # Ticker (precio en tiempo real)
            if "@ticker" in stream:
                symbol = payload["s"]
                price = float(payload["c"])  # Precio actual
                
                old_price = self.latest_prices.get(symbol, price)
                self.latest_prices[symbol] = price
                
                # Notificar callbacks
                if symbol in self.price_callbacks:
                    for callback in self.price_callbacks[symbol]:
                        try:
                            await callback(symbol, price, old_price)
                        except Exception as e:
                            logger.error(f"Price callback error: {e}")
            
            # Kline (vela)
            elif "@kline" in stream:
                kline = payload["k"]
                symbol = kline["s"]
                
                kline_data = {
                    "symbol": symbol,
                    "interval": kline["i"],
                    "open_time": kline["t"],
                    "open": float(kline["o"]),
                    "high": float(kline["h"]),
                    "low": float(kline["l"]),
                    "close": float(kline["c"]),
                    "volume": float(kline["v"]),
                    "is_closed": kline["x"],  # True si la vela está cerrada
                }
                
                self.latest_klines[symbol] = kline_data
                
                # Notificar callbacks solo cuando la vela cierra
                if kline_data["is_closed"] and symbol in self.kline_callbacks:
                    for callback in self.kline_callbacks[symbol]:
                        try:
                            await callback(symbol, kline_data)
                        except Exception as e:
                            logger.error(f"Kline callback error: {e}")
        
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON: {message[:100]}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Obtiene el último precio conocido de un símbolo"""
        return self.latest_prices.get(symbol)
    
    def get_all_prices(self) -> Dict[str, float]:
        """Obtiene todos los precios actuales"""
        return self.latest_prices.copy()
    
    def on_price_update(self, symbol: str, callback: Callable):
        """Registra un callback para actualizaciones de precio"""
        if symbol not in self.price_callbacks:
            self.price_callbacks[symbol] = set()
        self.price_callbacks[symbol].add(callback)
    
    def on_kline_close(self, symbol: str, callback: Callable):
        """Registra un callback para cuando una vela cierra"""
        if symbol not in self.kline_callbacks:
            self.kline_callbacks[symbol] = set()
        self.kline_callbacks[symbol].add(callback)
    
    async def subscribe(self, symbols: list[str]):
        """Suscribe a nuevos símbolos"""
        new_symbols = set(symbols) - self.subscribed_symbols
        if not new_symbols:
            return
        
        self.subscribed_symbols.update(new_symbols)
        
        # Reconectar para incluir nuevos símbolos
        if self.websocket:
            await self.websocket.close()
        
        logger.info(f"Subscribed to {len(new_symbols)} new symbols")
    
    async def unsubscribe(self, symbols: list[str]):
        """Desuscribe de símbolos"""
        self.subscribed_symbols -= set(symbols)
        
        # Limpiar callbacks
        for symbol in symbols:
            self.price_callbacks.pop(symbol, None)
            self.kline_callbacks.pop(symbol, None)
            self.latest_prices.pop(symbol, None)
            self.latest_klines.pop(symbol, None)


class ClientWebSocketManager:
    """Gestiona conexiones WebSocket con clientes del frontend"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set] = {}  # user_id -> connections
    
    async def connect(self, websocket, user_id: str):
        """Conecta un cliente"""
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = set()
        self.active_connections[user_id].add(websocket)
        logger.debug(f"Client connected: {user_id}")
    
    def disconnect(self, websocket, user_id: str):
        """Desconecta un cliente"""
        if user_id in self.active_connections:
            self.active_connections[user_id].discard(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        logger.debug(f"Client disconnected: {user_id}")
    
    async def send_to_user(self, user_id: str, message: dict):
        """Envía mensaje a un usuario específico"""
        if user_id not in self.active_connections:
            return
        
        dead_connections = set()
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        
        # Limpiar conexiones muertas
        self.active_connections[user_id] -= dead_connections
    
    async def broadcast(self, message: dict):
        """Envía mensaje a todos los usuarios conectados"""
        for user_id in list(self.active_connections.keys()):
            await self.send_to_user(user_id, message)
    
    async def send_price_update(self, symbol: str, price: float, change: float = 0):
        """Envía actualización de precio a todos"""
        await self.broadcast({
            "type": "price_update",
            "symbol": symbol,
            "price": price,
            "change": change,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def send_trade_update(self, user_id: str, trade: dict):
        """Envía actualización de trade a un usuario"""
        await self.send_to_user(user_id, {
            "type": "trade_update",
            "trade": trade,
            "timestamp": datetime.utcnow().isoformat()
        })


# Instancias globales
binance_ws = BinanceWebSocket()
client_ws_manager = ClientWebSocketManager()

