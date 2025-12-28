"""
Telegram Service for sending notifications via Telegram Bot
"""
import aiohttp
from typing import Optional


class TelegramService:
    """Service for sending messages via Telegram Bot"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML"
    ):
        """Send a message to Telegram"""
        url = f"{self.base_url}/sendMessage"
        
        # Asegurar que chat_id sea string o int
        chat_id = self.chat_id
        if isinstance(chat_id, str):
            # Intentar convertir a int si es posible (para validar formato)
            try:
                int(chat_id)
            except ValueError:
                pass  # Mantener como string si no es numérico
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    error_data = await response.json() if response.content_type == 'application/json' else {}
                    error_description = error_data.get("description", await response.text())
                    error_code = error_data.get("error_code", response.status)
                    
                    # Crear mensaje de error más descriptivo
                    error_msg = f"Telegram API error ({error_code}): {error_description}"
                    raise Exception(error_msg)
                return await response.json()
    
    async def send_trade_notification(
        self,
        trade_type: str,
        symbol: str,
        price: float,
        quantity: float,
        profit_loss: Optional[float] = None
    ):
        """Send a trade notification to Telegram"""
        emoji = "🟢" if trade_type == "buy" else "🔴"
        
        if profit_loss is not None:
            pnl_emoji = "✅" if profit_loss >= 0 else "❌"
            message = f"""
{emoji} <b>Trade Notification</b>

<b>Type:</b> {trade_type.upper()}
<b>Symbol:</b> {symbol}
<b>Price:</b> ${price:.8f}
<b>Quantity:</b> {quantity:.8f}
<b>P&L:</b> {pnl_emoji} ${profit_loss:.2f}
            """
        else:
            message = f"""
{emoji} <b>Trade Opened</b>

<b>Type:</b> {trade_type.upper()}
<b>Symbol:</b> {symbol}
<b>Price:</b> ${price:.8f}
<b>Quantity:</b> {quantity:.8f}
            """
        
        await self.send_message(message.strip())
    
    async def send_alert(
        self,
        title: str,
        message: str,
        alert_type: str = "info"  # info, warning, error, success
    ):
        """Send an alert message"""
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅"
        }
        
        emoji = emojis.get(alert_type, "ℹ️")
        formatted_message = f"{emoji} <b>{title}</b>\n\n{message}"
        await self.send_message(formatted_message)

