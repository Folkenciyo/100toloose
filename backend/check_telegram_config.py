#!/usr/bin/env python3
"""Script para verificar configuración de Telegram en la base de datos"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.core.config import settings
from app.models.user import User

async def check_telegram_config():
    # Usar la misma configuración que la aplicación
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    
    engine = create_async_engine(database_url, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession)
    
    async with async_session() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        print("=" * 70)
        print("CONFIGURACIÓN DE TELEGRAM EN BASE DE DATOS")
        print("=" * 70)
        
        for user in users:
            print(f"\n👤 Usuario: {user.username} (ID: {user.id})")
            print(f"   telegram_enabled: {user.telegram_enabled}")
            
            if user.telegram_bot_token:
                token_preview = user.telegram_bot_token[:20] + "..." if len(user.telegram_bot_token) > 20 else user.telegram_bot_token
                print(f"   telegram_bot_token: ✅ Configurado ({token_preview})")
            else:
                print(f"   telegram_bot_token: ❌ NULL o vacío")
            
            if user.telegram_chat_id:
                print(f"   telegram_chat_id: ✅ {user.telegram_chat_id}")
            else:
                print(f"   telegram_chat_id: ❌ NULL o vacío")
            
            # Verificar si está completamente configurado
            is_configured = (
                user.telegram_enabled and 
                user.telegram_bot_token and 
                user.telegram_chat_id
            )
            
            if is_configured:
                print(f"   ✅ Telegram está COMPLETAMENTE CONFIGURADO")
            else:
                missing = []
                if not user.telegram_enabled:
                    missing.append("telegram_enabled=False")
                if not user.telegram_bot_token:
                    missing.append("bot_token faltante")
                if not user.telegram_chat_id:
                    missing.append("chat_id faltante")
                print(f"   ⚠️  Telegram NO está configurado: {', '.join(missing)}")
        
        print("\n" + "=" * 70)
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_telegram_config())

