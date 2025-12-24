from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.profile import (
    ProfileSettingsUpdate,
    ProfileSettingsResponse,
    ProfileInfoConfig,
    BinanceTestnetConfig,
    BinanceRealConfig,
    DeepSeekConfig,
    SMTPConfig,
    TelegramConfig
)

router = APIRouter()


@router.get("/settings", response_model=ProfileSettingsResponse)
async def get_profile_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get current user's profile settings"""
    # Reload user to get latest data
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    return ProfileSettingsResponse(
        profile_info=ProfileInfoConfig(
            profile_name=user.profile_name,
            summary_email=user.summary_email,
            phone_number=user.phone_number,
            platform_user_id=user.platform_user_id,
            paper_trading=user.paper_trading
        ),
        binance_testnet=BinanceTestnetConfig(
            api_key=user.binance_testnet_api_key if user.binance_testnet_api_key else None,
            secret_key="***" if user.binance_testnet_secret_key else None  # Don't expose secret
        ),
        binance_real=BinanceRealConfig(
            api_key=user.binance_real_api_key if user.binance_real_api_key else None,
            secret_key="***" if user.binance_real_secret_key else None  # Don't expose secret
        ),
        deepseek=DeepSeekConfig(
            api_key=user.deepseek_api_key if user.deepseek_api_key else None,
            enabled=user.deepseek_enabled if user.deepseek_enabled else False
        ),
        smtp=SMTPConfig(
            host=user.smtp_host,
            port=user.smtp_port,
            user=user.smtp_user,
            password="***" if user.smtp_password else None,  # Don't expose password
            from_email=user.smtp_from_email,
            enabled=user.smtp_enabled if user.smtp_enabled else False
        ),
        telegram=TelegramConfig(
            bot_token="***" if user.telegram_bot_token else None,  # Don't expose token
            chat_id=user.telegram_chat_id,
            enabled=user.telegram_enabled if user.telegram_enabled else False
        )
    )


@router.put("/settings", response_model=ProfileSettingsResponse)
async def update_profile_settings(
    settings: ProfileSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user's profile settings"""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    # Update Profile Info
    if settings.profile_info:
        if settings.profile_info.profile_name is not None:
            user.profile_name = settings.profile_info.profile_name
        if settings.profile_info.summary_email is not None:
            user.summary_email = settings.profile_info.summary_email
        if settings.profile_info.phone_number is not None:
            user.phone_number = settings.profile_info.phone_number
        if settings.profile_info.platform_user_id is not None:
            user.platform_user_id = settings.profile_info.platform_user_id
    
    # Update Binance Testnet config (para Paper Trading)
    if settings.binance_testnet:
        if settings.binance_testnet.api_key is not None:
            user.binance_testnet_api_key = settings.binance_testnet.api_key
        if settings.binance_testnet.secret_key and settings.binance_testnet.secret_key != "***":
            user.binance_testnet_secret_key = settings.binance_testnet.secret_key
    
    # Update Binance Real config (para Real Trading)
    if settings.binance_real:
        if settings.binance_real.api_key is not None:
            user.binance_real_api_key = settings.binance_real.api_key
        if settings.binance_real.secret_key and settings.binance_real.secret_key != "***":
            user.binance_real_secret_key = settings.binance_real.secret_key
    
    # Update DeepSeek config
    if settings.deepseek:
        if settings.deepseek.api_key is not None:
            user.deepseek_api_key = settings.deepseek.api_key
        if settings.deepseek.enabled is not None:
            user.deepseek_enabled = settings.deepseek.enabled
    
    # Update SMTP config
    if settings.smtp:
        # Host es requerido si se está habilitando SMTP
        if settings.smtp.host is not None:
            user.smtp_host = settings.smtp.host
        elif settings.smtp.enabled and not user.smtp_host:
            # Si se habilita pero no hay host, mantener el valor actual o usar gmail por defecto
            if not user.smtp_host:
                user.smtp_host = "smtp.gmail.com"  # Default para Gmail
        
        if settings.smtp.port is not None:
            user.smtp_port = settings.smtp.port
        elif settings.smtp.enabled and not user.smtp_port:
            user.smtp_port = 587  # Default para Gmail
        
        if settings.smtp.user is not None:
            user.smtp_user = settings.smtp.user
        if settings.smtp.password:
            user.smtp_password = settings.smtp.password
        if settings.smtp.from_email is not None:
            user.smtp_from_email = settings.smtp.from_email
        if settings.smtp.enabled is not None:
            user.smtp_enabled = settings.smtp.enabled
    
    # Update Telegram config
    if settings.telegram:
        # Solo actualizar bot_token si no es "***" (placeholder) y no está vacío
        if settings.telegram.bot_token and settings.telegram.bot_token != "***":
            user.telegram_bot_token = settings.telegram.bot_token
        if settings.telegram.chat_id is not None:
            user.telegram_chat_id = settings.telegram.chat_id
        if settings.telegram.enabled is not None:
            user.telegram_enabled = settings.telegram.enabled
    
    await db.commit()
    await db.refresh(user)
    
    return ProfileSettingsResponse(
        profile_info=ProfileInfoConfig(
            profile_name=user.profile_name,
            summary_email=user.summary_email,
            phone_number=user.phone_number,
            platform_user_id=user.platform_user_id,
            paper_trading=user.paper_trading
        ),
        binance_testnet=BinanceTestnetConfig(
            api_key=user.binance_testnet_api_key if user.binance_testnet_api_key else None,
            secret_key="***" if user.binance_testnet_secret_key else None
        ),
        binance_real=BinanceRealConfig(
            api_key=user.binance_real_api_key if user.binance_real_api_key else None,
            secret_key="***" if user.binance_real_secret_key else None
        ),
        deepseek=DeepSeekConfig(
            api_key=user.deepseek_api_key if user.deepseek_api_key else None,
            enabled=user.deepseek_enabled if user.deepseek_enabled else False
        ),
        smtp=SMTPConfig(
            host=user.smtp_host,
            port=user.smtp_port,
            user=user.smtp_user,
            password="***" if user.smtp_password else None,
            from_email=user.smtp_from_email,
            enabled=user.smtp_enabled if user.smtp_enabled else False
        ),
        telegram=TelegramConfig(
            bot_token="***" if user.telegram_bot_token else None,
            chat_id=user.telegram_chat_id,
            enabled=user.telegram_enabled if user.telegram_enabled else False
        )
    )


@router.post("/settings/test-email")
async def test_email(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test SMTP configuration by sending a test email"""
    from app.services.email_service import EmailService
    
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    if not user.smtp_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP notifications are not enabled. Please enable them in your profile settings."
        )
    
    if not user.smtp_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP host is not configured. Please configure the SMTP server (e.g., smtp.gmail.com) in your profile settings."
        )
    
    if not user.smtp_port:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP port is not configured. Please configure the SMTP port (e.g., 587 for Gmail) in your profile settings."
        )
    
    if not user.smtp_user or not user.smtp_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMTP credentials are incomplete. Please configure SMTP user and password in your profile settings."
        )
    
    email_service = EmailService(
        host=user.smtp_host,
        port=user.smtp_port or 587,
        user=user.smtp_user,
        password=user.smtp_password,
        from_email=user.smtp_from_email or user.email
    )
    
    try:
        await email_service.send_test_email(user.email)
        return {"success": True, "message": "Test email sent successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test email: {str(e)}"
        )


@router.post("/settings/test-telegram")
async def test_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Test Telegram bot configuration by sending a test message"""
    from app.services.telegram_service import TelegramService
    
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    if not user.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot token is not configured. Please add your bot token first."
        )
    
    if not user.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat ID is not configured. Please use the /getID command in your Telegram bot to obtain your Chat ID."
        )
    
    if not user.telegram_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram notifications are not enabled. Please enable them first."
        )
    
    try:
        # Limpiar el chat_id (eliminar espacios, etc.)
        chat_id = str(user.telegram_chat_id).strip()
        
        # Crear servicio con chat_id limpio
        telegram_service = TelegramService(
            bot_token=user.telegram_bot_token,
            chat_id=chat_id
        )
        
        await telegram_service.send_message("✅ Test message from 100toLoose Trading Bot!")
        return {"success": True, "message": "Test message sent successfully! Check your Telegram."}
    except Exception as e:
        error_msg = str(e).lower()
        
        # Mejorar mensajes de error
        if "chat not found" in error_msg or "bad request" in error_msg or "400" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Chat ID or bot cannot send messages to this chat. Please use the /getID command in your Telegram bot to get the correct Chat ID, make sure you've started a conversation with the bot first."
            )
        elif "unauthorized" in error_msg or "401" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bot token. Please check your Telegram bot token."
            )
        elif "forbidden" in error_msg or "403" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bot is blocked or cannot send messages. Please unblock the bot and try again."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send test message: {str(e)}"
            )


@router.post("/settings/test-telegram-trade")
async def test_telegram_trade_notification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Envía una notificación de trade de prueba para ver el formato"""
    from app.services.telegram_service import TelegramService
    
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    if not user.telegram_bot_token or not user.telegram_chat_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram is not configured. Please configure your bot token and chat ID first."
        )
    
    if not user.telegram_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram notifications are not enabled."
        )
    
    try:
        chat_id = str(user.telegram_chat_id).strip()
        telegram_service = TelegramService(
            bot_token=user.telegram_bot_token,
            chat_id=chat_id
        )
        
        # Enviar notificación de trade abierto (BUY)
        await telegram_service.send_trade_notification(
            trade_type="buy",
            symbol="BTCUSDT",
            price=50000.00,
            quantity=0.002
        )
        
        # Esperar un poco
        import asyncio
        await asyncio.sleep(2)
        
        # Enviar notificación de trade cerrado (con P&L)
        await telegram_service.send_trade_notification(
            trade_type="sell",
            symbol="BTCUSDT",
            price=51000.00,
            quantity=0.002,
            profit_loss=20.00
        )
        
        return {
            "success": True, 
            "message": "Test trade notifications sent! Check your Telegram. You should receive 2 messages: one for trade opened (BUY) and one for trade closed (SELL) with P&L."
        }
    except Exception as e:
        error_msg = str(e).lower()
        
        if "chat not found" in error_msg or "bad request" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Chat ID. Please use the /getID command in your Telegram bot to get the correct Chat ID."
            )
        elif "unauthorized" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bot token. Please check your Telegram bot token."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send test trade notification: {str(e)}"
            )


@router.get("/settings/get-telegram-chat-id")
async def get_telegram_chat_id(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene el Chat ID de Telegram usando la API de Telegram.
    El usuario debe enviar un mensaje al bot primero.
    """
    import httpx
    
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one()
    
    if not user.telegram_bot_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram bot token is not configured. Please add your bot token first."
        )
    
    try:
        # Primero, obtener información del bot para verificar que el token es válido
        bot_info_url = f"https://api.telegram.org/bot{user.telegram_bot_token}/getMe"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Verificar que el bot existe
            bot_response = await client.get(bot_info_url)
            bot_data = bot_response.json()
            
            if not bot_data.get("ok"):
                error_desc = bot_data.get("description", "Unknown error")
                if "Unauthorized" in error_desc or "401" in str(bot_response.status_code):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid bot token. Please check your Telegram bot token."
                    )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Telegram API error: {error_desc}"
                )
            
            bot_username = bot_data.get("result", {}).get("username", "Unknown")
            
            # Obtener actualizaciones recientes del bot
            updates_url = f"https://api.telegram.org/bot{user.telegram_bot_token}/getUpdates"
            
            # Intentar obtener updates con diferentes parámetros
            # Primero intentamos sin offset para obtener todos los mensajes pendientes
            params_options = [
                {"limit": 100, "timeout": 0},  # Últimos 100 mensajes
                {"limit": 50, "timeout": 0},   # Últimos 50
                {"limit": 10, "timeout": 0},   # Últimos 10
                {"timeout": 0},                 # Todos los disponibles
            ]
            
            updates = []
            for params in params_options:
                try:
                    response = await client.get(updates_url, params=params)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get("ok"):
                        updates = data.get("result", [])
                        if updates:
                            break
                except Exception as e:
                    continue
            
            if not updates:
                # Si no hay updates, intentar obtener el Chat ID de otra forma
                # Podemos pedirle al usuario que use @userinfobot o proporcionar instrucciones alternativas
                return {
                    "success": False,
                    "message": "No messages found in bot's update queue.",
                    "instructions": [
                        f"Option 1 (Recommended):",
                        f"  1. Open Telegram and search for @{bot_username}",
                        f"  2. Click 'Start' or send any message",
                        f"  3. Wait 5-10 seconds (important!)",
                        f"  4. Come back here and click 'Get Chat ID' again",
                        "",
                        "Option 2 (Alternative):",
                        "  1. Open Telegram and search for @userinfobot",
                        "  2. Send /start to @userinfobot",
                        "  3. It will show your Chat ID (a number like 123456789)",
                        "  4. Copy that number and paste it in the Chat ID field below",
                        "",
                        "Note: The bot doesn't need to reply. Just sending a message is enough."
                    ],
                    "bot_username": bot_username,
                    "alternative_method": True
                }
            
            # Buscar el mensaje más reciente del usuario (no del bot)
            chat_id = None
            chat_type = None
            chat_title = None
            
            # Recorrer updates de más reciente a más antiguo
            for update in reversed(updates):
                message = update.get("message") or update.get("edited_message") or update.get("callback_query", {}).get("message")
                
                if message:
                    chat = message.get("chat", {})
                    # Verificar que es un mensaje del usuario (no del bot)
                    from_user = message.get("from", {})
                    if from_user.get("is_bot") is False:  # Es un usuario real
                        chat_id = str(chat.get("id"))
                        chat_type = chat.get("type", "unknown")
                        chat_title = chat.get("title") or chat.get("first_name") or chat.get("username", "Unknown")
                        break
            
            if not chat_id:
                return {
                    "success": False,
                    "message": "No user messages found. Please send a message to your bot.",
                    "instructions": [
                        f"1. Open Telegram and search for @{bot_username}",
                        "2. Send any message to the bot",
                        "3. Wait a few seconds and try again"
                    ],
                    "bot_username": bot_username
                }
            
            return {
                "success": True,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "chat_name": chat_title,
                "bot_username": bot_username,
                "message": f"Chat ID encontrado: {chat_id} (Tipo: {chat_type})"
            }
            
    except httpx.HTTPStatusError as e:
        error_data = {}
        try:
            if e.response:
                error_data = e.response.json()
        except:
            pass
        
        error_description = error_data.get("description", str(e))
        
        if "Unauthorized" in error_description or "401" in str(e.status_code):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid bot token. Please check your Telegram bot token."
            )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telegram API error: {error_description}"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Chat ID: {str(e)}"
        )

