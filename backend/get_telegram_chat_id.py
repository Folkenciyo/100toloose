#!/usr/bin/env python3
"""Script para obtener el Chat ID de Telegram"""
import asyncio
import aiohttp
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User

async def get_chat_id():
    # Usar la misma configuración que la aplicación
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as db:
        result = await db.execute(select(User))
        user = result.scalars().first()
        
        if not user or not user.telegram_bot_token:
            print("❌ No hay usuario o bot_token configurado")
            return
        
        print("=" * 70)
        print("OBTENIENDO CHAT ID DE TELEGRAM")
        print("=" * 70)
        print(f"\n🤖 Bot Token: {user.telegram_bot_token[:20]}...")
        print(f"📝 Chat ID actual en BD: {user.telegram_chat_id}")
        
        print("\n📤 Consultando actualizaciones del bot...")
        print("   (Asegúrate de haber enviado /start al bot primero)")
        
        url = f"https://api.telegram.org/bot{user.telegram_bot_token}/getUpdates"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        updates = data.get("result", [])
                        if updates:
                            print(f"\n✅ Se encontraron {len(updates)} actualizaciones")
                            print("\n📋 Chat IDs encontrados:")
                            chat_ids = set()
                            for update in updates:
                                message = update.get("message", {})
                                chat = message.get("chat", {})
                                chat_id = chat.get("id")
                                if chat_id:
                                    chat_ids.add(chat_id)
                                    username = chat.get("username", "N/A")
                                    first_name = chat.get("first_name", "N/A")
                                    print(f"   - Chat ID: {chat_id}")
                                    print(f"     Usuario: {first_name} (@{username})")
                            
                            if chat_ids:
                                latest_chat_id = list(chat_ids)[-1]
                                print(f"\n💡 Chat ID más reciente: {latest_chat_id}")
                                if str(latest_chat_id) != str(user.telegram_chat_id):
                                    print(f"⚠️  El Chat ID en la BD ({user.telegram_chat_id}) es diferente del encontrado ({latest_chat_id})")
                                    print(f"   Deberías actualizar el chat_id en tu perfil a: {latest_chat_id}")
                                else:
                                    print(f"✅ El Chat ID coincide con el de la BD")
                            else:
                                print("\n❌ No se encontraron chat IDs en las actualizaciones")
                                print("   Asegúrate de haber enviado /start al bot primero")
                        else:
                            print("\n❌ No hay actualizaciones")
                            print("   Pasos a seguir:")
                            print("   1. Abre Telegram")
                            print("   2. Busca tu bot")
                            print("   3. Envía /start al bot")
                            print("   4. Ejecuta este script de nuevo")
                    else:
                        error = data.get("description", "Unknown error")
                        print(f"\n❌ Error de API: {error}")
                else:
                    error_text = await response.text()
                    print(f"\n❌ Error HTTP {response.status}: {error_text}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(get_chat_id())

