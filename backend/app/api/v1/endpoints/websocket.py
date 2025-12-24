"""
WebSocket endpoints para comunicación en tiempo real con el frontend
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import JWTError, jwt

from app.core.config import settings
from app.core.logging_config import logger
from app.services.websocket_manager import client_ws_manager, binance_ws

router = APIRouter()


async def get_user_from_token(token: str) -> str:
    """Extrae user_id del token JWT"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


@router.websocket("/prices")
async def websocket_prices(
    websocket: WebSocket,
    token: str = Query(...)
):
    """
    WebSocket para recibir actualizaciones de precios en tiempo real.
    
    Conectar: ws://localhost/ws/prices?token=<jwt_token>
    
    Mensajes recibidos:
    - {"type": "price_update", "symbol": "BTCUSDT", "price": 50000.00, "change": 0.5}
    - {"type": "trade_update", "trade": {...}}
    """
    user_id = await get_user_from_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Invalid token")
        return
    
    await client_ws_manager.connect(websocket, user_id)
    logger.info(f"WebSocket client connected: user {user_id}")
    
    try:
        # Enviar precios actuales al conectar
        prices = binance_ws.get_all_prices()
        if prices:
            await websocket.send_json({
                "type": "initial_prices",
                "prices": prices
            })
        
        # Mantener conexión abierta
        while True:
            # Recibir mensajes del cliente (para suscripciones, etc.)
            data = await websocket.receive_json()
            
            if data.get("action") == "subscribe":
                symbols = data.get("symbols", [])
                await binance_ws.subscribe(symbols)
                await websocket.send_json({
                    "type": "subscribed",
                    "symbols": symbols
                })
            
            elif data.get("action") == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        client_ws_manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket client disconnected: user {user_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        client_ws_manager.disconnect(websocket, user_id)


@router.get("/status")
async def websocket_status():
    """Estado de las conexiones WebSocket"""
    return {
        "binance_connected": binance_ws.running,
        "subscribed_symbols": list(binance_ws.subscribed_symbols),
        "active_client_connections": sum(
            len(conns) for conns in client_ws_manager.active_connections.values()
        ),
        "latest_prices": binance_ws.get_all_prices()
    }


