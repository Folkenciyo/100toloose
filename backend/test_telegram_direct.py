#!/usr/bin/env python3
"""Script para probar envío directo de Telegram con los valores exactos de la BD"""
import asyncio
import aiohttp
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User

async def test_direct():
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as db:
        result = await db.execute(select(User))
        user = result.scalars().first()
        
        if not user:
            print("❌ No hay usuarios")
            return
        
        print("=" * 70)
        print("PRUEBA DIRECTA DE TELEGRAM API")
        print("=" * 70)
        print(f"\n📋 Valores de la BD:")
        print(f"   Bot Token: '{user.telegram_bot_token}'")
        print(f"   Token length: {len(user.telegram_bot_token) if user.telegram_bot_token else 0}")
        print(f"   Chat ID: '{user.telegram_chat_id}'")
        print(f"   Chat ID type: {type(user.telegram_chat_id)}")
        print(f"   Chat ID repr: {repr(user.telegram_chat_id)}")
        print(f"   Enabled: {user.telegram_enabled}")
        
        # Verificar si hay espacios
        if user.telegram_chat_id:
            chat_id_clean = str(user.telegram_chat_id).strip()
            print(f"\n🔍 Análisis del Chat ID:")
            print(f"   Original: '{user.telegram_chat_id}'")
            print(f"   Limpiado: '{chat_id_clean}'")
            print(f"   Tiene espacios: {user.telegram_chat_id != chat_id_clean}")
            print(f"   Es numérico: {chat_id_clean.isdigit()}")
        
        # Probar con getMe primero
        print(f"\n📤 Test 1: Verificar bot (getMe)...")
        url = f"https://api.telegram.org/bot{user.telegram_bot_token}/getMe"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        bot_info = data.get("result", {})
                        print(f"   ✅ Bot válido: @{bot_info.get('username')} ({bot_info.get('first_name')})")
                    else:
                        print(f"   ❌ Error: {data.get('description')}")
                else:
                    print(f"   ❌ HTTP {response.status}")
        
        # Probar enviar mensaje con chat_id tal cual está
        print(f"\n📤 Test 2: Enviar mensaje con chat_id original...")
        url = f"https://api.telegram.org/bot{user.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": user.telegram_chat_id,
            "text": "🧪 Test directo con chat_id original"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("ok"):
                        print(f"   ✅ Mensaje enviado correctamente")
                        print(f"   Message ID: {data.get('result', {}).get('message_id')}")
                    else:
                        print(f"   ❌ Error: {data.get('description')}")
                else:
                    error_text = await response.text()
                    print(f"   ❌ HTTP {response.status}: {error_text}")
        
        # Probar con chat_id limpiado
        if user.telegram_chat_id:
            chat_id_clean = str(user.telegram_chat_id).strip()
            if chat_id_clean != str(user.telegram_chat_id):
                print(f"\n📤 Test 3: Enviar mensaje con chat_id limpiado...")
                url = f"https://api.telegram.org/bot{user.telegram_bot_token}/sendMessage"
                payload = {
                    "chat_id": chat_id_clean,
                    "text": "🧪 Test directo con chat_id limpiado"
                }
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get("ok"):
                                print(f"   ✅ Mensaje enviado correctamente con chat_id limpiado")
                                print(f"   ⚠️  El chat_id en la BD tiene espacios - necesita limpieza")
                            else:
                                print(f"   ❌ Error: {data.get('description')}")
                        else:
                            error_text = await response.text()
                            print(f"   ❌ HTTP {response.status}: {error_text}")
        
        # Probar con chat_id como int
        if user.telegram_chat_id and str(user.telegram_chat_id).strip().isdigit():
            chat_id_int = int(str(user.telegram_chat_id).strip())
            print(f"\n📤 Test 4: Enviar mensaje con chat_id como int...")
            url = f"https://api.telegram.org/bot{user.telegram_bot_token}/sendMessage"
            payload = {
                "chat_id": chat_id_int,
                "text": "🧪 Test directo con chat_id como int"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("ok"):
                            print(f"   ✅ Mensaje enviado correctamente con chat_id como int")
                        else:
                            print(f"   ❌ Error: {data.get('description')}")
                    else:
                        error_text = await response.text()
                        print(f"   ❌ HTTP {response.status}: {error_text}")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_direct())

