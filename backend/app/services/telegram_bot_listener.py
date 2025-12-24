"""
Telegram Bot Listener - Escucha comandos de Telegram y responde
"""
import asyncio
import httpx
from typing import Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.logging_config import logger
from app.models.user import User


class TelegramBotListener:
    """Escucha comandos de Telegram usando long polling"""
    
    def __init__(self):
        self.running = False
        self.last_update_id = 0
        
    async def start(self):
        """Inicia el listener en background"""
        if self.running:
            return
        
        self.running = True
        asyncio.create_task(self._poll_loop())
        logger.info("✅ Telegram bot listener started")
    
    async def stop(self):
        """Detiene el listener"""
        self.running = False
        logger.info("🛑 Telegram bot listener stopped")
    
    async def _poll_loop(self):
        """Loop principal que escucha comandos"""
        while self.running:
            try:
                # Obtener todos los usuarios con bots configurados
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(User).where(
                            User.telegram_bot_token.isnot(None),
                            User.telegram_enabled == True
                        )
                    )
                    users = result.scalars().all()
                    
                    # Procesar updates para cada usuario
                    for user in users:
                        try:
                            await self._process_updates(user)
                        except Exception as e:
                            logger.error(f"Error processing updates for user {user.id}: {e}")
                
                # Esperar antes de la siguiente iteración
                await asyncio.sleep(5)  # Poll cada 5 segundos
                
            except Exception as e:
                logger.error(f"Error in Telegram bot listener loop: {e}")
                await asyncio.sleep(10)  # Esperar más tiempo si hay error
    
    async def _process_updates(self, user: User):
        """Procesa updates para un usuario específico"""
        if not user.telegram_bot_token:
            return
        
        url = f"https://api.telegram.org/bot{user.telegram_bot_token}/getUpdates"
        
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 1,
            "allowed_updates": ["message"]
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if not data.get("ok"):
                    return
                
                updates = data.get("result", [])
                
                for update in updates:
                    update_id = update.get("update_id", 0)
                    self.last_update_id = max(self.last_update_id, update_id)
                    
                    message = update.get("message")
                    if not message:
                        continue
                    
                    # Obtener información del mensaje
                    chat = message.get("chat", {})
                    from_user = message.get("from", {})
                    text = message.get("text", "").strip()
                    
                    # Solo procesar si el mensaje viene de un usuario (no de un bot)
                    if from_user.get("is_bot"):
                        continue
                    
                    chat_id = str(chat.get("id"))
                    
                    # Procesar comandos
                    if text.startswith("/"):
                        await self._handle_command(user, chat_id, text, message)
        
        except httpx.TimeoutException:
            # Timeout es normal en long polling
            pass
        except Exception as e:
            logger.error(f"Error processing updates for user {user.id}: {e}")
    
    async def _handle_command(self, user: User, chat_id: str, command: str, message: dict):
        """Maneja comandos de Telegram"""
        command = command.lower()
        
        if command == "/getid" or command == "/getid@hundredtoloose_bot":
            # Responder con el Chat ID
            response_text = f"""
✅ <b>Tu Chat ID es:</b>

<code>{chat_id}</code>

📋 <b>Instrucciones:</b>
1. Copia el número de arriba
2. Ve a la página de Profile en la aplicación
3. Pega el número en el campo "Chat ID"
4. Guarda la configuración

💡 <b>Tip:</b> Una vez configurado, recibirás notificaciones de todos tus trades automáticamente.
            """.strip()
            
            await self._send_message(user.telegram_bot_token, chat_id, response_text)
            
            # Actualizar chat_id automáticamente si es diferente o no está configurado
            if not user.telegram_chat_id or str(user.telegram_chat_id) != chat_id:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(
                        select(User).where(User.id == user.id)
                    )
                    db_user = result.scalar_one()
                    db_user.telegram_chat_id = chat_id
                    await db.commit()
                    logger.info(f"Auto-updated Chat ID for user {user.id}: {chat_id}")
        
        elif command == "/start" or command == "/start@hundredtoloose_bot":
            response_text = f"""
👋 <b>¡Hola! Soy el bot de 100toLoose</b>

📊 Te enviaré notificaciones de todos tus trades automáticamente.

<b>Comandos disponibles:</b>
/getID - Obtener tu Chat ID

💡 <b>Configuración:</b>
1. Usa /getID para obtener tu Chat ID
2. Configura tu Chat ID en la aplicación
3. ¡Listo! Recibirás notificaciones automáticamente
            """.strip()
            
            await self._send_message(user.telegram_bot_token, chat_id, response_text)
        
        elif command == "/help" or command == "/help@hundredtoloose_bot":
            response_text = """
ℹ️ <b>Ayuda - 100toLoose Bot</b>

<b>Comandos:</b>
/getID - Obtener tu Chat ID para configurar notificaciones
/start - Mensaje de bienvenida
/help - Mostrar esta ayuda

<b>Notificaciones:</b>
Una vez configurado, recibirás notificaciones automáticas de:
• Trades abiertos (BUY/SELL)
• Trades cerrados (con P&L)
• Stop Loss y Take Profit activados
            """.strip()
            
            await self._send_message(user.telegram_bot_token, chat_id, response_text)
    
    async def _send_message(self, bot_token: str, chat_id: str, text: str):
        """Envía un mensaje a Telegram"""
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")


# Instancia global
telegram_listener = TelegramBotListener()

