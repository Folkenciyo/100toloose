"""
Script de diagnóstico para Telegram Bot
Verifica la configuración y envía mensajes de prueba
"""
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User
from app.services.telegram_service import TelegramService
from app.core.logging_config import logger, telegram_logger

async def diagnose_telegram():
    """Diagnostica la configuración de Telegram"""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as db:
        # Obtener el primer usuario (o el que quieras diagnosticar)
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        if not users:
            print("❌ No hay usuarios en la base de datos")
            return
        
        for user in users:
            print(f"\n{'='*60}")
            print(f"🔍 DIAGNÓSTICO TELEGRAM - Usuario: {user.username}")
            print(f"{'='*60}")
            
            # Verificar configuración
            print(f"\n📋 Configuración:")
            print(f"   telegram_enabled: {user.telegram_enabled}")
            print(f"   telegram_bot_token: {'✅ Configurado' if user.telegram_bot_token else '❌ No configurado'}")
            if user.telegram_bot_token:
                print(f"      Token: {user.telegram_bot_token[:10]}...{user.telegram_bot_token[-5:]}")
            print(f"   telegram_chat_id: {'✅ Configurado' if user.telegram_chat_id else '❌ No configurado'}")
            if user.telegram_chat_id:
                print(f"      Chat ID: {user.telegram_chat_id}")
            
            # Verificar condiciones
            print(f"\n🔍 Verificaciones:")
            conditions_met = []
            if not user.telegram_enabled:
                print("   ❌ Telegram NO está habilitado")
            else:
                print("   ✅ Telegram está habilitado")
                conditions_met.append("enabled")
            
            if not user.telegram_bot_token:
                print("   ❌ Bot token NO está configurado")
            else:
                print("   ✅ Bot token está configurado")
                conditions_met.append("token")
            
            if not user.telegram_chat_id:
                print("   ❌ Chat ID NO está configurado")
            else:
                print("   ✅ Chat ID está configurado")
                conditions_met.append("chat_id")
            
            # Intentar enviar mensaje de prueba
            if len(conditions_met) == 3:
                print(f"\n📤 Enviando mensaje de prueba...")
                try:
                    telegram_service = TelegramService(
                        bot_token=user.telegram_bot_token,
                        chat_id=user.telegram_chat_id
                    )
                    
                    # Test 1: Mensaje simple
                    print("   Test 1: Mensaje simple...")
                    await telegram_service.send_message("🧪 Test de diagnóstico - Mensaje simple")
                    print("   ✅ Mensaje simple enviado correctamente")
                    
                    # Test 2: Notificación de trade abierto
                    print("   Test 2: Notificación de trade abierto...")
                    await telegram_service.send_trade_notification(
                        trade_type="buy",
                        symbol="BTCUSDT",
                        price=50000.0,
                        quantity=0.001
                    )
                    print("   ✅ Notificación de trade abierto enviada")
                    
                    # Test 3: Notificación de trade cerrado
                    print("   Test 3: Notificación de trade cerrado...")
                    await telegram_service.send_trade_notification(
                        trade_type="close",
                        symbol="BTCUSDT",
                        price=51000.0,
                        quantity=0.001,
                        profit_loss=10.0
                    )
                    print("   ✅ Notificación de trade cerrado enviada")
                    
                    print(f"\n✅ TODOS LOS TESTS PASARON - Telegram está funcionando correctamente")
                    
                except Exception as e:
                    print(f"\n❌ ERROR al enviar mensajes:")
                    print(f"   Tipo: {type(e).__name__}")
                    print(f"   Mensaje: {str(e)}")
                    
                    # Análisis del error
                    error_str = str(e).lower()
                    if "unauthorized" in error_str or "401" in error_str:
                        print(f"\n   🔍 DIAGNÓSTICO: Token de bot inválido")
                        print(f"      - Verifica que el bot_token sea correcto")
                        print(f"      - Asegúrate de haber creado el bot con @BotFather")
                    elif "chat not found" in error_str or "400" in error_str:
                        print(f"\n   🔍 DIAGNÓSTICO: Chat ID inválido o bot bloqueado")
                        print(f"      - Verifica que el chat_id sea correcto")
                        print(f"      - Asegúrate de haber iniciado conversación con el bot")
                        print(f"      - Usa /getID en el bot para obtener tu chat_id")
                    elif "forbidden" in error_str or "403" in error_str:
                        print(f"\n   🔍 DIAGNÓSTICO: Bot bloqueado")
                        print(f"      - Desbloquea el bot en Telegram")
                        print(f"      - Inicia una conversación con el bot")
                    else:
                        print(f"\n   🔍 DIAGNÓSTICO: Error desconocido")
                        print(f"      - Revisa los logs para más detalles")
            else:
                print(f"\n⚠️  No se pueden enviar mensajes - Faltan configuraciones:")
                missing = []
                if "enabled" not in conditions_met:
                    missing.append("telegram_enabled = True")
                if "token" not in conditions_met:
                    missing.append("telegram_bot_token")
                if "chat_id" not in conditions_met:
                    missing.append("telegram_chat_id")
                print(f"   Configura: {', '.join(missing)}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(diagnose_telegram())

