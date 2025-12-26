#!/usr/bin/env python3
"""Script para probar envío de mensaje de Telegram"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User
from app.services.telegram_service import TelegramService

async def test_telegram_send():
    # Usar la misma configuración que la aplicación
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as db:
        result = await db.execute(select(User))
        user = result.scalars().first()
        
        if not user:
            print("❌ No hay usuarios en la base de datos")
            return
        
        print("=" * 70)
        print("PRUEBA DE ENVÍO DE MENSAJE TELEGRAM")
        print("=" * 70)
        print(f"\n👤 Usuario: {user.username}")
        print(f"   Bot Token: {user.telegram_bot_token[:20]}...")
        print(f"   Chat ID: {user.telegram_chat_id}")
        
        try:
            telegram_service = TelegramService(
                bot_token=user.telegram_bot_token,
                chat_id=user.telegram_chat_id
            )
            
            print("\n📤 Enviando mensaje de prueba...")
            await telegram_service.send_message("🧪 Test de diagnóstico - Mensaje de prueba desde script")
            print("✅ Mensaje enviado correctamente")
            
            print("\n📤 Enviando notificación de trade abierto...")
            await telegram_service.send_trade_notification(
                trade_type="buy",
                symbol="BTCUSDT",
                price=50000.0,
                quantity=0.001
            )
            print("✅ Notificación de trade abierto enviada")
            
            print("\n📤 Enviando notificación de trade cerrado...")
            await telegram_service.send_trade_notification(
                trade_type="close",
                symbol="BTCUSDT",
                price=51000.0,
                quantity=0.001,
                profit_loss=10.0
            )
            print("✅ Notificación de trade cerrado enviada")
            
            print("\n" + "=" * 70)
            print("✅ TODOS LOS TESTS PASARON")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ ERROR al enviar mensajes:")
            print(f"   Tipo: {type(e).__name__}")
            print(f"   Mensaje: {str(e)}")
            import traceback
            traceback.print_exc()
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_telegram_send())
